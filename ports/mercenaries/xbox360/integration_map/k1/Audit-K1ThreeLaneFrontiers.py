#!/usr/bin/env python3
"""Read-only three-lane Merc360 hardware/source frontier audit.

Lane A: source-proven PFIFO DMA_PUT at original Xbox D3D 0028ED6B.
Lane B: 001E hot-region translated source lookup and historical tick share.
Lane C: Swap/PersistDisplay original-code membership and callsite inventory.
No guest data or copyrighted XBE bytes are exported. No hardware, XDK, or edits.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DAC_X86 = "0028ED54  mov byte ptr [ecx + 0x6813c8], 0"
PFIFO_X86 = "0028ED6B  mov edx, dword ptr [ecx + 0x3240]"
PFIFO_ADDRESS = "FD003240"
HOT_VAS = (0x001EF4CD, 0x001EF64E, 0x001EEFF1, 0x001EEFE0)
PRESENT = {"Swap": 0x0028BDB0, "PersistDisplay": 0x0028A530,
           "CreateDevice": 0x0028CAA0}
BLOCK = re.compile(r"PHASE4C_BUDGET_TICK\s*\(\s*0x([0-9A-Fa-f]{6,8})u\s*\)")
FUNCTION = re.compile(r"(?m)^\s*(?:static\s+)?void\s+sub_([0-9A-Fa-f]{8})\s*\(")
HOT_PROFILE = re.compile(r"P6DQ HOT PROFILE: total=(\d+) hot_001E=(\d+)")
LAST_FAULT = re.compile(r"FAULT ACCESS IMMEDIATE: READ width=4 guest=([0-9A-F]{8})")
STRIP = re.compile(r"[\r\n]+")


def audit(shards: Path, proof: Path, log: Path | None) -> dict:
    files = sorted(shards.glob("translated_???.cpp"))
    if len(files) != 64:
        raise ValueError(f"Expected 64 real translated TrueTUs, got {len(files)}")
    proof_text = proof.read_text(encoding="utf-8")
    for evidence in (
        "Focus guest block VA: 0028ED48",
        "MATCH 1: translated_055.cpp:21654",
        "GUEST_WRITE8(ecx + 0x6813C8, 0);",
        DAC_X86,
        PFIFO_X86,
    ):
        if evidence.lower() not in proof_text.lower():
            raise ValueError(f"Original retail XBE proof absent: {evidence}")

    presence: dict[str, list[dict]] = {n: [] for n in PRESENT}
    callsites: dict[str, list[dict]] = {n: [] for n in PRESENT}
    pfifo: list[dict] = []
    hot: dict[str, list[dict]] = {f"{a:08X}": [] for a in HOT_VAS}
    counts = {"files": len(files), "functions": 0, "blocks": 0}
    for file in files:
        lines = file.read_text(encoding="utf-8").splitlines()
        func, block = None, None
        for i, text in enumerate(lines):
            fm = FUNCTION.search(text)
            if fm:
                func = int(fm.group(1), 16)
                counts["functions"] += 1
                for name, va in PRESENT.items():
                    if va == func:
                        presence[name].append({"file": file.name, "line": i + 1})
            bm = BLOCK.search(text)
            if bm:
                block = int(bm.group(1), 16)
                counts["blocks"] += 1
                key = f"{block:08X}"
                if key in hot:
                    hot[key].append({
                        "file": file.name, "line": i + 1, "function": f"{func or 0:08X}",
                        "source": [x.strip()[:180] for x in lines[i:min(i + 9, len(lines))]]
                    })
                if block == 0x0028ED6B:
                    pfifo.append({"file": file.name, "line": i + 1,
                                  "function": f"{func or 0:08X}",
                                  "source": [x.strip()[:180] for x in lines[i:min(i + 10, len(lines))]]})
            if "sub_" in text and "(" in text and not fm:
                for name, va in PRESENT.items():
                    if re.search(r"\bsub_" + f"{va:08X}" + r"\s*\(", text, re.I):
                        if len(callsites[name]) < 100:
                            callsites[name].append({
                                "file": file.name, "line": i + 1,
                                "caller": f"{func or 0:08X}",
                                "guest_block": f"{block or 0:08X}",
                                "source": text.strip()[:230],
                            })

    if len(presence["Swap"]) > 1 or len(presence["PersistDisplay"]) > 1:
        raise ValueError("Duplicate translated display function definition")
    if len(pfifo) > 1:
        raise ValueError("Duplicate translated PFIFO exact guest block")
    recent = {"available": False}
    if log:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        faults = [m.group(1) for ln in lines if (m := LAST_FAULT.search(ln))]
        profiles = [m for ln in lines if (m := HOT_PROFILE.search(ln))]
        summary = next((ln for ln in reversed(lines) if "P6DQ AV FAMILY:" in ln), "")
        dac_seen = any("K1NV2A DAC WRITE INDEX:" in ln for ln in lines)
        if not faults or faults[-1] != PFIFO_ADDRESS or not dac_seen:
            raise ValueError("Hardware log does not prove DAC -> exact PFIFO READ32")
        if not profiles or "display_calls=0" not in summary:
            raise ValueError("Missing hardware hot profile or display telemetry")
        total, hot_count = (int(v) for v in profiles[-1].groups())
        recent = {
            "available": True,
            "last_fault": "READ32 " + faults[-1],
            "dac_index_witness": dac_seen,
            "translated_ticks": total,
            "hot_001e_ticks": hot_count,
            "hot_001e_percent": round(100.0 * hot_count / total, 2) if total else 0,
            "display_calls_zero": True,
            "original_source_verified": True,
        }

    return {
        "status": "SOURCE_ONLY_READ_ONLY_NO_XDK",
        "counts": counts,
        "pfifo": {
            "register": "NV_PFIFO_CACHE1_DMA_PUT",
            "address": PFIFO_ADDRESS,
            "pfifo_offset": "00001240",
            "exact_original_x86": PFIFO_X86,
            "guest_block": "0028ED6B",
            "translated_block_witnesses": pfifo,
            "note": "Observe/bridge exact register using real reset and guest write state; never blanket MMIO success",
        },
        "hot": {
            "target_region": "001E",
            "samples": hot,
            "hardware": recent,
            "note": "Counting guest ticks is not CPU wall time; do not optimize a loop by skipping it",
        },
        "presentation": {
            "functions": {
                n: {"address": f"{va:08X}", "definitions": presence[n],
                    "direct_callsites_first100": callsites[n]}
                for n, va in PRESENT.items()
            },
            "note": "Source membership/callsites do not prove execution, readiness or real pixels",
        },
        "translated_files_mutated": 0,
        "mmio_fences_changed": False,
        "synthetic_pixels": False,
    }


def self_test() -> None:
    with __import__("tempfile").TemporaryDirectory(prefix="k1_three_lanes_") as d:
        root = Path(d)
        shards = root / "t"
        shards.mkdir()
        for n in range(64):
            (shards / f"translated_{n:03d}.cpp").write_text(
                ("static void sub_0028BDB0(void)\n{\nPHASE4C_BUDGET_TICK(0x0028BDB0u);\n}\n"
                 "static void sub_0028A530(void)\n{\nPHASE4C_BUDGET_TICK(0x0028A530u);\n}\n"
                 "static void sub_001EF000(void)\n{\nPHASE4C_BUDGET_TICK(0x001EF4CDu);\n}\n"
                 "static void sub_0028ED48(void)\n{\nPHASE4C_BUDGET_TICK(0x0028ED6Bu);\n}\n")
                if n == 55 else "", encoding="utf-8"
            )
        proof = root / "focused.txt"
        proof.write_text("\n".join((
            "Focus guest block VA: 0028ED48",
            "MATCH 1: translated_055.cpp:21654",
            "GUEST_WRITE8(ecx + 0x6813C8, 0);",
            DAC_X86, PFIFO_X86,
        )), encoding="utf-8")
        log = root / "run.log"
        log.write_text(
            "[Merc360:P5] K1NV2A DAC WRITE INDEX: index=0\n"
            "[Merc360:P5] FAULT ACCESS IMMEDIATE: READ width=4 guest=FD003240\n"
            "[Merc360:P5] P6DQ HOT PROFILE: total=56902781 hot_001E=24862470\n"
            "[Merc360:P5] P6DQ AV FAMILY: display_calls=0 framebuffer=00000000\n",
            encoding="utf-8"
        )
        dct = audit(shards, proof, log)
        assert dct["hot"]["hardware"]["hot_001e_percent"] > 43.6
        assert dct["pfifo"]["translated_block_witnesses"]
        assert len(dct["presentation"]["functions"]["Swap"]["definitions"]) == 1
        assert len(dct["presentation"]["functions"]["PersistDisplay"]["definitions"]) == 1
        assert dct["translated_files_mutated"] == 0
    print("[K1-3LANE] SELFTEST PASS: exact PFIFO proof, 64 TrueTUs, 001E hot samples, Swap/PersistDisplay membership, read-only")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--shards", type=Path)
    ap.add_argument("--proof", type=Path)
    ap.add_argument("--hardware-log", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.shards or not args.proof:
        ap.error("--shards and --proof required")
    result = audit(args.shards, args.proof, args.hardware_log)
    output = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    print("[K1-3LANE] SOURCE AUDIT PASS: 64 real TrueTUs, exact retail PFIFO source proof")
    p = result["pfifo"]
    print(f"[K1-PFIFO] READ32 {p['address']} / {p['register']} translated_block_witnesses={len(p['translated_block_witnesses'])}")
    h = result["hot"]
    print(f"[K1-HOT] 001E region hardware={h['hardware']} source_hot_blocks=" +
          ",".join(f"{k}:{len(v)}" for k, v in h["samples"].items()))
    for n, f in result["presentation"]["functions"].items():
        print(f"[K1-PRESENT] {n} {f['address']} definitions={len(f['definitions'])} direct_callsites={len(f['direct_callsites_first100'])}")
    print("[K1-3LANE] READ-ONLY: no hardware/XDK, no guest modifications, no fabricated pixels")
    if args.out:
        print("[K1-3LANE] FULL REPORT:", args.out)


if __name__ == "__main__":
    main()

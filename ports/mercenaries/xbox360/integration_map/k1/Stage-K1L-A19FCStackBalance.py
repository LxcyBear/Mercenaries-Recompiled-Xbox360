#!/usr/bin/env python3
"""K1L experimental call-edge correction for hardware-proven DSOUND stack drift.

K1J hardware, FC4A -> A19FC:
  ESP before: 008BF8CC; ESP after: 008BF8D0 (+4).
K1K source: FC4A saves EBX, ESI, EDI on guest stack and later restores
them with POP32. The +4 drift shifts all three restores one slot:
  EDI <- old ESI (0); ESI <- old EBX (01B5C320);
  EBX <- first local dword, last loop iteration writes 0x18 there.
This is a narrowly scoped, guarded diagnostic repair, not proof of a
general fix to all A19FC callers. No guest read/write or fence is added.
Build/deploy separately; preserve K1J/G/E Xbox telemetry.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

TAG = "K1L-FC4A-A19FC-ESP-BALANCE-20261030"
BASE_MARKER = "K1J-DSOUND-RETURN-EBX-20261030"
OWNER = "translated_053.cpp"
FUNCTION = "sub_0029FC4A"
REGEX_OWNER = re.compile(
    r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_0029FC4A"
    r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{"
)
END = re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
MEM_OP = re.compile(r"\b(?:GUEST_|phase6ch_apu_)(?:read|write|READ|WRITE)(?:8|16|32|64|128)\s*\(", re.I)

ANCHOR = (
    "            const uint32_t r71_raw_ebx = ebx;\n"
    "            const uint32_t r71_raw_esi = esi;\n"
    "            const uint32_t r71_raw_edi = edi;\n"
    "            const uint32_t r71_raw_esp = esp;\n"
    "            /* Real x86 A19FC is required to preserve EBX/ESI/EDI. */"
)
FIX = """            /* K1L-FC4A-A19FC-ESP-BALANCE-20261030:
               K1J Xbox: this exact call returned ESP=before+4 despite
               having no explicit stack argument. The +4 shifts FC4A's
               saved EDI/ESI/EBX POP32 slots, and the later last-loop
               local dword 0x18 is loaded into EBX. Only repair the
               hardware-confirmed +4 delta, not any other return case. */
            {
                const uint32_t k1l_drift = r71_raw_esp - r71_before_esp;
                const unsigned int k1l_repair = (k1l_drift == 4u);
                if (k1l_repair)
                    esp = r71_before_esp;
                static uint32_t k1l_calls = 0u;
                ++k1l_calls;
                if (k1l_calls <= 8u || (k1l_drift != 0u && !k1l_repair))
                {
                    char k1l_line[256];
                    sprintf(k1l_line,
                        "K1L DSOUND ESP EDGE: n=%u before=%08X raw_after=%08X drift=%08X repaired=%u final=%08X ebx=%08X esi=%08X edi=%08X",
                        (unsigned)k1l_calls, (unsigned)r71_before_esp,
                        (unsigned)r71_raw_esp, (unsigned)k1l_drift,
                        (unsigned)k1l_repair, (unsigned)esp,
                        (unsigned)ebx, (unsigned)esi, (unsigned)edi);
                    trace(k1l_line);
                }
            }
"""

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def modify(source: str) -> str:
    if TAG in source:
        raise ValueError("K1L already staged")
    crlf = source.count("\r\n")
    if source.count("\r") != crlf or (crlf and crlf != source.count("\n")):
        raise ValueError("K1L: source line endings damaged")
    nl = "\r\n" if crlf else "\n"
    definitions = list(REGEX_OWNER.finditer(source))
    if len(definitions) != 1:
        raise ValueError("K1L: expected exactly one FC4A implementation")
    start = definitions[0].start()
    closing = END.search(source, definitions[0].end())
    if closing is None:
        raise ValueError("K1L: FC4A closing brace absent")
    end = closing.end()
    body = source[start:end]
    marker = ANCHOR.replace("\n", nl)
    if body.count(marker) != 1:
        raise ValueError("K1L: original R71 FC4A/A19FC return anchor drift")
    if body.count("PUSH32(esp, 0); sub_002A19FC(); /* call 0x002A19FC */") != 1:
        raise ValueError("K1L: original call shape drift")
    if body.count("    ebx = esi + 0x18;") != 1 or body.count("    POP32(esp, ebx);") != 1:
        raise ValueError("K1L: FC4A EBX failure-path source changed")
    if body.count("    PUSH32(esp, ebx);") != 2:
        raise ValueError("K1L: FC4A stack saved-EBX anchors changed")
    raw_index = body.index(marker)
    call_index = body.index("PUSH32(esp, 0); sub_002A19FC();")
    if not call_index < raw_index:
        raise ValueError("K1L: call not before raw ESP witness")
    patched = body.replace(
        marker,
        marker.replace(
            "            /* Real x86 A19FC is required to preserve EBX/ESI/EDI. */",
            FIX.rstrip("\n").replace("\n", nl)
            + nl
            + "            /* Real x86 A19FC is required to preserve EBX/ESI/EDI. */"
        ),
        1,
    )
    if patched.count(TAG) != 1:
        raise ValueError("K1L: missing single guarded source repair")
    if MEM_OP.findall(patched) != MEM_OP.findall(body):
        raise ValueError("K1L: guest memory ops changed")
    if patched.count("esp = r71_before_esp;") != 1:
        raise ValueError("K1L: must add exactly one guarded guest ESP write")
    if patched.index("esp = r71_before_esp;") < patched.index("const uint32_t r71_raw_esp = esp;"):
        raise ValueError("K1L: ESP repair must follow the raw witness")
    return source[:start] + patched + source[end:]

def stage(baseline: Path, manifest: Path, k1k_report: Path, out: Path) -> dict:
    baseline, manifest, k1k_report, out = (
        baseline.resolve(), manifest.resolve(), k1k_report.resolve(), out.resolve()
    )
    if baseline == out or baseline in out.parents or out in baseline.parents:
        raise ValueError("K1L refuses to stage over the proven K1J input")
    if out == manifest or out == k1k_report:
        raise ValueError("K1L output would overwrite a provenance input")
    doc = json.loads(manifest.read_text(encoding="utf-8-sig"))
    sources = sorted(baseline.glob("translated_*.cpp"))
    headers = sorted(baseline.glob("*.h"))
    originals = [*sources, *headers]
    base_owner = baseline / OWNER
    k1k = k1k_report.read_text(encoding="utf-8-sig")
    if (
        doc.get("marker") != BASE_MARKER
        or doc.get("status") != "STAGED_ONLY_NO_XDK_BUILD"
        or doc.get("modified_from_k1g") != ["translated_017.cpp", "translated_041.cpp"]
        or doc.get("translated_shards") != 64
        or doc.get("unchanged_from_k1g") != 62
        or doc.get("preserved_k1e_witness") is not True
        or doc.get("preserved_k1g_owner") is not True
        or Path(doc.get("staged_directory", "MISSING")).resolve() != baseline
        or len(sources) != 64
        or not any(h.name == "translated_runtime.h" for h in headers)
        or not base_owner.is_file()
        or sha(base_owner.read_bytes()).lower() != "e15535e2f9ae9758db06b439dcdebcc293f0bfea74ac9439dee7a1a79ab8d58f"
        or "K1K FC4A ORIGINAL EBX SAVE/RESTORE PATH - READ ONLY" not in k1k
        or "K1J Xbox FD83_AFTER_CF0B EBX=01B5C320; FD83_AFTER_FC4A EBX=00000018" not in k1k
        or "Function=sub_0029FC4A; owner=translated_053.cpp; original lines=17686..18123" not in k1k
        or "    ebx = esi + 0x18;" not in k1k
        or "    POP32(esp, ebx);" not in k1k
    ):
        raise ValueError("K1L expected K1J/K1K actual 64-TU and exact owner source identity")
    old = base_owner.read_bytes()
    updated = modify(old.decode("utf-8")).encode("utf-8")
    file_set = {p.name for p in originals}
    if out.exists() and any(out.iterdir()):
        if {p.name for p in out.iterdir()} != file_set:
            raise ValueError("K1L staged file set changed")
        for p in originals:
            expected = updated if p.name == OWNER else p.read_bytes()
            if (out / p.name).read_bytes() != expected:
                raise ValueError("K1L existing staged content differs: " + p.name)
        print("[K1L] REUSE PASS: 64 TrueTUs + headers already SHA-identical")
    else:
        out.mkdir(parents=True, exist_ok=True)
        for p in originals:
            target = out / p.name
            if p.name == OWNER:
                target.write_bytes(updated)
            else:
                shutil.copy2(p, target)
    for p in originals:
        if (out / p.name).read_bytes() != (updated if p.name == OWNER else p.read_bytes()):
            raise RuntimeError("K1L staged TrueTU source mismatch: " + p.name)
    record = {
        "status": "STAGED_ONLY_NO_XDK_BUILD",
        "marker": TAG,
        "baseline_directory": str(baseline),
        "staged_directory": str(out),
        "translated_shards": 64,
        "modified_from_k1j": [OWNER],
        "unchanged_from_k1j": 63,
        "old_owner_sha256": sha(old),
        "new_owner_sha256": sha(updated),
        "preserved_k1j_register_probes": True,
        "preserved_k1g_register_probes": True,
        "preserved_k1e_list_tail": True,
        "guest_reads_added": 0,
        "guest_writes_added": 0,
        "guest_register_writes_added": 1,
        "guest_register_write": "conditional ESP=r71_before_esp iff raw ESP==before+4",
        "hard_fences": "UNCHANGED",
        "repair_condition": "raw_esp - before_esp == 4; all other deltas unchanged",
    }
    file = out.parent / "k1l-a19fc-stack-balance-manifest.json"
    file.write_bytes((json.dumps(record, indent=2) + "\n").encode("utf-8"))
    return record

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--k1j-shards", type=Path, required=True)
    p.add_argument("--k1j-manifest", type=Path, required=True)
    p.add_argument("--k1k-report", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    doc = stage(a.k1j_shards,a.k1j_manifest,a.k1k_report,a.out)
    print("[K1L] STAGING PASS: guarded FC4A->A19FC ESP +4 imbalance repair")
    print("[K1L] 1 changed TrueTU; 63 others and all headers SHA identical to K1J")
    print("[K1L] Prior K1J/K1G/K1E telemetry preserved, no new guest memory ops")
    print("[K1L] One CONDITIONAL guest ESP assignment; all other deltas unchanged")
    print("[K1L] Hard fences intact; NO XDK build performed")
    print("[K1L] Manifest=" + str(a.out.parent / "k1l-a19fc-stack-balance-manifest.json"))

if __name__ == "__main__":
    main()

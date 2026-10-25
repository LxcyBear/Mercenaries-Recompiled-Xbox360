#!/usr/bin/env python3
"""Phase 6CK: combined static/live probe for the post-6CJ XACT FFFFFFFF fault.

6CJ proved the general Mm166 repair is valid:
  * 0x2000 / align 0x1000 canonical allocation succeeds at 0x024FA000;
  * retail immediately queries its size and physical address;
  * a following 0x6000 allocation succeeds at 0x024F4000.
The same READ32 FFFFFFFF fault remains 58 ticks later, so allocation starvation
is not the root cause.

The final VA ring is deterministic and ends:
  00283703 -> 0027DB23 -> ... -> 00283717 -> 00283722 -> 00283732
  -> 002832BB -> 002832CA -> READ32 FFFFFFFF

6CK makes no semantic repair. It prints/saves the generated source around those
blocks during emission and injects bounded live probes immediately after each
label. This gives the exact translated expression and the live register/stack/
object state in one hardware cycle.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CJ-MM166-GENERAL-TAIL-20261025-A"
BUILD_TAG = "P6CK-XACT-FFFFFFFF-PROBE-20261025-A"
COOKIE_OLD = "phase6cj_env_build_cookie"
COOKIE_NEW = "phase6ck_env_build_cookie"

PROBE_VAS = (
    0x00283703,
    0x00283717,
    0x00283722,
    0x00283732,
    0x002832BB,
    0x002832CA,
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CK] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CK] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def source_window(text: str, marker: str, before: int = 10, after: int = 18) -> str:
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit(f"[Phase6CK] source marker missing: {marker}")
    lines = text.splitlines()
    line_no = text.count("\n", 0, pos)
    lo = max(0, line_no - before)
    hi = min(len(lines), line_no + after + 1)
    out = []
    for i in range(lo, hi):
        out.append(f"{i+1:07d}: {lines[i]}")
    return "\n".join(out)


def install_state(text: str) -> str:
    anchor = "static uint32_t s_phase6cjGeneralTailLastActual = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CK] expected one 6CJ state anchor, found {text.count(anchor)}"
        )
    rows = []
    for va in PROBE_VAS:
        rows.append(f"static uint32_t s_phase6ckHit_{va:08X} = 0u;")
    state = "\n".join(rows) + "\n\n"
    return text.replace(anchor, anchor + state, 1)


def live_probe(va: int) -> str:
    counter = f"s_phase6ckHit_{va:08X}"
    return f'''
    ++{counter};
    if ({counter} <= 4u)
    {{
        char phase6ckLine[960];
        uint32_t phase6ckS0 = (g_esp <= 0x03FFFFFCu) ? GUEST_READ32(g_esp) : 0xDEAD0000u;
        uint32_t phase6ckS1 = (g_esp <= 0x03FFFFF8u) ? GUEST_READ32(g_esp + 4u) : 0xDEAD0001u;
        uint32_t phase6ckS2 = (g_esp <= 0x03FFFFF4u) ? GUEST_READ32(g_esp + 8u) : 0xDEAD0002u;
        uint32_t phase6ckS3 = (g_esp <= 0x03FFFFF0u) ? GUEST_READ32(g_esp + 12u) : 0xDEAD0003u;
        uint32_t phase6ckEdi0 = (g_edi <= 0x03FFFFFCu) ? GUEST_READ32(g_edi) : 0xDEAD1000u;
        uint32_t phase6ckEdi4 = (g_edi <= 0x03FFFFF8u) ? GUEST_READ32(g_edi + 4u) : 0xDEAD1001u;
        uint32_t phase6ckEdi8 = (g_edi <= 0x03FFFFF4u) ? GUEST_READ32(g_edi + 8u) : 0xDEAD1002u;
        uint32_t phase6ckEdiC = (g_edi <= 0x03FFFFF0u) ? GUEST_READ32(g_edi + 12u) : 0xDEAD1003u;
        sprintf(
            phase6ckLine,
            "P6CK XACT PATH va={va:08X} hit=%u eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X s0=%08X s1=%08X s2=%08X s3=%08X edi0=%08X edi4=%08X edi8=%08X ediC=%08X",
            (unsigned int){counter},
            (unsigned int)g_eax,
            (unsigned int)g_ecx,
            (unsigned int)g_edx,
            (unsigned int)g_ebx,
            (unsigned int)g_esi,
            (unsigned int)g_edi,
            (unsigned int)g_esp,
            (unsigned int)phase6ckS0,
            (unsigned int)phase6ckS1,
            (unsigned int)phase6ckS2,
            (unsigned int)phase6ckS3,
            (unsigned int)phase6ckEdi0,
            (unsigned int)phase6ckEdi4,
            (unsigned int)phase6ckEdi8,
            (unsigned int)phase6ckEdiC);
        trace(phase6ckLine);
    }}
'''


def instrument_labels(text: str) -> str:
    for va in PROBE_VAS:
        marker = f"loc_{va:08X}: ;\n"
        if text.count(marker) != 1:
            raise SystemExit(
                f"[Phase6CK] expected one live probe label {marker.strip()}, "
                f"found {text.count(marker)}"
            )
        text = text.replace(marker, marker + live_probe(va), 1)
    return text


def insert_summary(text: str) -> str:
    marker = "P6CJ MM166 GENERAL TAIL:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CK] inherited 6CJ summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 7000:
        raise SystemExit("[Phase6CK] could not locate summary insertion point")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]

    fmt = " ".join(
        f"{va:08X}=%u" for va in PROBE_VAS
    )
    args = ",\n".join(
        f"{indent}    (unsigned int)s_phase6ckHit_{va:08X}"
        for va in PROBE_VAS
    )
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CK XACT PATH SUMMARY: {fmt}",\n'
        f'{args});\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CJ", "PHASE 6CK")
        .replace("Phase 6CJ", "Phase 6CK")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CK] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6ck_base")
    p6bl = load(args.phase6bl_emitter, "phase6ck_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cj-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CK] missing cached 6CJ input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CK] cached Phase 6CJ identity mismatch")

    cj = manifest.get("phase6cj_mm166_general_tail", {})
    if (
        cj.get("translated_membership_changed") is not False
        or cj.get("apu_gp_ep_semantics_changed") is not False
        or cj.get("guest_irql_semantics_changed") is not False
        or cj.get("xacteng_membership_changed") is not False
        or cj.get("execution_budget_inherited") != 32000000
    ):
        raise SystemExit("[Phase6CK] inherited 6CJ policy mismatch")

    required = (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "P6CJ MM166 GENERAL TAIL:",
        "P6CJ APU DSP:",
        "static uint32_t s_phase6cjGeneralTailLastActual = 0u;",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6CK] inherited marker missing: {marker}")

    report = []
    report.append("Phase 6CK generated XACT fault-path source report")
    report.append(f"baseline={BASE_TAG}")
    report.append(
        "hardware=6CJ alloc 0x2000+0x6000 succeeded; READ32 FFFFFFFF remained at tick 26711574"
    )
    for va in PROBE_VAS:
        marker = f"loc_{va:08X}: ;"
        window = source_window(main_text, marker)
        report.append("")
        report.append(f"===== {marker} =====")
        report.append(window)
        print(f"[Phase6CK] SOURCE WINDOW {va:08X} BEGIN")
        for row in window.splitlines():
            print(f"[Phase6CK] | {row}")
        print(f"[Phase6CK] SOURCE WINDOW {va:08X} END")

    main_text = install_state(main_text)
    main_text = instrument_labels(main_text)
    main_text = insert_summary(main_text)

    main_text = replace_once(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = (
        main_text.replace("PHASE 6CJ", "PHASE 6CK")
        .replace("Phase 6CJ", "Phase 6CK")
        .replace('"P6CJ ', '"P6CK ')
    )
    env_text = patch_env(env_text)

    required_after = (
        BUILD_TAG,
        COOKIE_NEW,
        "P6CK XACT PATH va=002832BB",
        "P6CK XACT PATH va=002832CA",
        "P6CK XACT PATH SUMMARY:",
        "P6CK MM166 GENERAL TAIL:",
        "P6CK APU DSP:",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
    )
    for marker in required_after:
        if marker not in main_text:
            raise SystemExit(f"[Phase6CK] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")
    report_path = args.out_dir / "phase6ck-xact-fault-source.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    manifest["phase"] = "6CK"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6ck_xact_ffffffff_probe"] = {
        "source_phase": "6CJ",
        "phase6cj_hardware": {
            "general_tail_calls": 2,
            "general_tail_successes": 2,
            "first_allocation": {
                "size": "0x00002000",
                "alignment": "0x00001000",
                "base": "0x024FA000",
            },
            "second_allocation": {
                "size": "0x00006000",
                "alignment": "0x00001000",
                "base": "0x024F4000",
            },
            "following_boundary": {
                "kind": "GUEST_FAULT",
                "access": "READ32",
                "target": "0xFFFFFFFF",
                "ticks": 26711574,
                "trace": 1017580,
                "eax": "0x00041D70",
                "ecx": "0xFFFFFFFF",
                "edx": "0x00000000",
                "edi": "0x01B5C3F8",
            },
            "final_va_ring_tail": [
                "0x00283703",
                "0x0027DB23",
                "0x0027DB3B",
                "0x0027DB41",
                "0x0027DB43",
                "0x00283717",
                "0x00283722",
                "0x00283732",
                "0x002832BB",
                "0x002832CA",
            ],
        },
        "probe_vas": [f"0x{x:08X}" for x in PROBE_VAS],
        "semantic_repair": False,
        "translated_membership_changed": False,
        "allocator_policy_changed": False,
        "apu_gp_ep_semantics_changed": False,
        "guest_irql_semantics_changed": False,
        "xacteng_membership_changed": False,
        "execution_budget_inherited": 32000000,
        "source_report": report_path.name,
        "source_layout": layout,
    }

    (args.out_dir / "phase6ck-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6CK] 6CJ allocator repair validated by hardware: 2/2 canonical tail allocations")
    print("[Phase6CK] READ32 FFFFFFFF remains; allocator is not the root cause")
    print("[Phase6CK] static source windows emitted for six XACT fault-path blocks")
    print("[Phase6CK] bounded live probes armed at the same six blocks")
    print(f"[Phase6CK] source report: {report_path}")
    print("[Phase6CK] no XACT/MMIO/allocator semantics changed")
    print("[Phase6CK] 32M execution budget preserved")
    print("[Phase6CK] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

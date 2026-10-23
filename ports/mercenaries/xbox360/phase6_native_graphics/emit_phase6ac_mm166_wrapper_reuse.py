#!/usr/bin/env python3
"""Phase 6AC: generalize the proven sub_0022AEE9 Mm166 wrapper ABI.

Hardware Phase 6AB proved:
  * HalBootSMCVideoMode DATA relocation is correct;
  * the 0x02880000 / 0x01680000 retail graphics pool remains valid;
  * execution advanced to direct=1816 with last_direct=0x0022AEE9;
  * the next stop is KERNEL_FRAME target 0x800000A6 (ordinal 166),
    esp=0x008BF7C0 saved_esp=0x008BF7DC (delta 28), fault=0;
  * boundary registers are EAX=0xFFFFFFFF, ECX=0x00000060,
    EDX=0x00000000, ESI=0x00299380.

Phase 6Y already structurally proved that generated sub_0022AEE9 snapshots
_icall_esp, saves ESI, then pushes the five MmAllocateContiguousMemoryEx
arguments plus a dummy return. That makes its kernel frame 24 bytes plus a
wrapper-owned 4-byte saved-ESI spill.

The original 6Y runtime gate intentionally accepted that +28 shape only for
the first hardware-observed 0x01680000 graphics-pool request. Phase 6AB has
now shown the same exact translated wrapper reuses the same ABI for a later
allocation. From the proved push mapping, the boundary registers decode that
request as size=0x60, low=0, high=0xFFFFFFFF.

6AC therefore does not special-case 0x60. It marks entry to the one proved
RECOMP_ICALL_SAFE inside sub_0022AEE9 and accepts +28 only while that wrapper
call is actively in flight and c+24 still equals live ESI. Canonical +24
ordinal-166 calls are unchanged. The graphics-pool special allocation path
remains restricted to its existing exact retail request/protection shape.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6AB-HAL-BOOT-VIDEO-MODE-DATA-20261023-A"
BUILD_TAG = "P6AC-MM166-WRAPPER-REUSE-20261023-A"
WRAPPER_VA = 0x0022AEE9
COOKIE_OLD = "phase6ab_env_build_cookie"
COOKIE_NEW = "phase6ac_env_build_cookie"
COOKIE_NUM_OLD = "50366262"
COOKIE_NUM_NEW = "50366363"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AC] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AC] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, new_policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AC] runtime Policy trace is missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AC] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    replacement = indent + 'trace("' + new_policy + '");'
    return text[:line_start] + replacement + text[line_end:]


def prove_generated_wrapper_shape(base, generated_root: Path, functions: Path) -> dict:
    by_va, by_name = base.load_ranges(functions)
    generated = base.load_generated(generated_root, by_name)
    row = generated.get(WRAPPER_VA)
    if row is None:
        raise SystemExit(
            "[Phase6AC] generated sub_0022AEE9 body is missing; cannot prove wrapper provenance"
        )

    source = row["source"]
    call_count = source.count("RECOMP_ICALL_SAFE")
    if call_count != 1:
        raise SystemExit(
            f"[Phase6AC] expected exactly one RECOMP_ICALL_SAFE in sub_0022AEE9, "
            f"found {call_count}; refusing ABI widening"
        )

    save_match = re.search(
        r"\{\s*uint32_t\s+_icall_esp\s*=\s*g_esp\s*;",
        source,
    )
    call_match = re.search(
        r"RECOMP_ICALL_SAFE\([^;]*?_icall_esp\s*\)\s*;",
        source,
        re.S,
    )
    if save_match is None or call_match is None or call_match.start() <= save_match.end():
        raise SystemExit(
            "[Phase6AC] sub_0022AEE9 no longer snapshots _icall_esp before its "
            "kernel ICALL; refusing ABI widening"
        )

    call_setup = source[save_match.end():call_match.start()]
    push_exprs = re.findall(
        r"PUSH32\(esp,\s*(.*?)\)\s*;",
        call_setup,
        re.S,
    )
    normalized = [re.sub(r"\s+", "", expr) for expr in push_exprs]
    expected = [
        "esi",
        "GUEST_READ32(ebp+0x14)",
        "GUEST_READ32(ebp+0x10)",
        "eax",
        "edx",
        "ecx",
        "0",
    ]
    if normalized != expected:
        raise SystemExit(
            "[Phase6AC] sub_0022AEE9 kernel-call push shape changed; expected "
            "saved ESI + five Mm166 args + dummy return. Observed: "
            + ", ".join(normalized)
        )

    return {
        "name": row["name"],
        "recomp_icall_safe_count": call_count,
        "saved_esp_snapshot": "_icall_esp = g_esp",
        "push_sequence": normalized,
        "canonical_kernel_frame_bytes": 24,
        "wrapper_spill": "esi",
        "wrapper_spill_bytes": 4,
        "wrapper_frame_bytes": 28,
        "argument_register_mapping": {
            "size": "ecx",
            "low": "edx",
            "high": "eax",
            "alignment": "guest [ebp+0x10]",
            "protect": "guest [ebp+0x14]",
        },
    }


def function_span_for_name(text: str, name: str) -> tuple[int, int]:
    pattern = re.compile(
        r"(?m)^[^\n;{}]*\b" + re.escape(name) + r"\s*\([^;{}]*\)\s*\{"
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"[Phase6AC] expected one rendered definition for {name}, found {len(matches)}"
        )

    start = matches[0].start()
    brace = text.find("{", matches[0].start(), matches[0].end())
    if brace < 0:
        raise SystemExit(f"[Phase6AC] opening brace missing for {name}")

    depth = 0
    in_string = False
    escape = False
    i = brace
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return start, i + 1
        i += 1

    raise SystemExit(f"[Phase6AC] unterminated rendered definition for {name}")


def instrument_rendered_wrapper(main_text: str, wrapper_name: str) -> str:
    start, end = function_span_for_name(main_text, wrapper_name)
    rendered = main_text[start:end]
    calls = list(re.finditer(r"RECOMP_ICALL_SAFE\s*\([^;]*?\)\s*;", rendered, re.S))
    if len(calls) != 1:
        raise SystemExit(
            f"[Phase6AC] rendered {wrapper_name} expected one RECOMP_ICALL_SAFE, "
            f"found {len(calls)}"
        )

    call = calls[0]
    call_text = rendered[call.start():call.end()]

    # Preserve the surrounding generated syntax exactly.  The ICALL may be the
    # body of an if/else or share a generated line with other syntax, so replacing
    # from the beginning of the source line is unsafe.  A do/while wrapper is one
    # statement in every such context and scopes only this proven ICALL.
    replacement = (
        "do { "
        "s_phase6acMm166WrapperActive = 1; "
        + call_text
        + " s_phase6acMm166WrapperActive = 0; "
        "} while (0);"
    )
    rendered = rendered[:call.start()] + replacement + rendered[call.end():]
    return main_text[:start] + rendered + main_text[end:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6aa-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6ac_base")
    p6aa = load(args.phase6aa_emitter, "phase6ac_p6aa")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6ab-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AC] cached Phase 6AB baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AB" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AC] cached Phase 6AB baseline identity mismatch")

    ab = manifest.get("phase6ab_hal_boot_video_mode") or {}
    data_export = ab.get("data_export") or {}
    if (
        data_export.get("ordinal") != 356
        or data_export.get("guest_va") != "0x0087E098"
        or data_export.get("initial_value") != "0x00000000"
        or ab.get("graphics_pool_model_inherited_unchanged") is not True
    ):
        raise SystemExit("[Phase6AC] inherited Phase 6AB data/graphics proof drift")

    required_base = (
        BASE_TAG,
        "size!=0x01680000u || extra!=g_esi",
        "resumeEsp=c+24u",
        "PASS: Phase 6AB retail graphics pool claim",
        "case 356u: return 0x0087E098u; /* HalBootSMCVideoMode ULONG */",
        "PASS: Phase 6AB HalBootSMCVideoMode initialized ordinal=356 va=0087E098 value=00000000",
        "static int s_phase6aaRootEntered;",
        "    s_phase6aaRootEntered = 0;\n",
        "P6AB HALDATA SUMMARY:",
        "PHASE 6AB HAL BOOT VIDEO MODE RESULT",
    )
    for marker in required_base:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AC] inherited Phase 6AB marker changed: {marker}")

    proof = prove_generated_wrapper_shape(base, args.generated_root, args.functions)
    wrapper_name = str(proof["name"])
    print(
        "[Phase6AC] GENERATED ABI PROOF: sub_0022AEE9 maps "
        "ECX=size EDX=low EAX=high and owns a saved-ESI spill below the +24 kernel frame"
    )

    # The Mm166 handler can appear before the later Phase-6 root-state block.
    # Declare the provenance flag immediately before the handler so every use is
    # guaranteed to have a prior declaration in old MSVC/XDK C++ mode.
    main_text = replace_unique(
        main_text,
        "static void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)",
        "static int s_phase6acMm166WrapperActive;\n\n"
        "static void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)",
        "wrapper provenance state declaration",
    )
    main_text = replace_unique(
        main_text,
        "    s_phase6aaRootEntered = 0;\n",
        "    s_phase6aaRootEntered = 0;\n"
        "    s_phase6acMm166WrapperActive = 0;\n",
        "wrapper provenance state reset",
    )

    main_text = instrument_rendered_wrapper(main_text, wrapper_name)

    main_text = replace_unique(
        main_text,
        "        if(size!=0x01680000u || extra!=g_esi)\n"
        "            phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A6u,savedEsp);\n"
        "        repaired=1u;",
        "        if(!s_phase6acMm166WrapperActive || extra!=g_esi)\n"
        "            phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A6u,savedEsp);\n"
        "        repaired=1u;\n"
        "        sprintf(\n"
        "            line,\n"
        '            "PASS: Phase 6AC Mm166 wrapper provenance size=%u spill=%08X live_esi=%08X active=%u",\n'
        "            (unsigned)size,\n"
        "            (unsigned)extra,\n"
        "            (unsigned)g_esi,\n"
        "            (unsigned)s_phase6acMm166WrapperActive);\n"
        "        trace(line);",
        "Mm166 +28 wrapper provenance gate",
    )

    policy = (
        "Policy: inherit hardware-proven Phase-6AB HalBootSMCVideoMode DATA "
        "relocation and the 02880000-03EFFFFF retail graphics pool; accept the "
        "+28 ordinal-166 frame only while structurally-proven sub_0022AEE9 is "
        "actively issuing its one kernel ICALL and the saved-ESI spill matches; "
        "preserve canonical +24 Mm166 plus all NV2A/platform/ABI/guest-fault "
        "hard stops"
    )
    main_text = replace_policy_line(main_text, policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "Phase 6AB build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = main_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)
    env_text = env_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)

    main_text = (
        main_text
        .replace("P6AB HALDATA SUMMARY:", "P6AC MM166WRAP SUMMARY:")
        .replace(
            "PHASE 6AB HAL BOOT VIDEO MODE RESULT",
            "PHASE 6AC MM166 WRAPPER REUSE RESULT",
        )
        .replace("PHASE 6AB", "PHASE 6AC")
        .replace("Phase 6AB", "Phase 6AC")
        .replace('"P6AB ', '"P6AC ')
    )
    env_text = (
        env_text
        .replace("PHASE 6AB", "PHASE 6AC")
        .replace("Phase 6AB", "Phase 6AC")
    )

    required = (
        BUILD_TAG,
        "static int s_phase6acMm166WrapperActive;",
        "s_phase6acMm166WrapperActive = 1;",
        "s_phase6acMm166WrapperActive = 0;",
        "if(!s_phase6acMm166WrapperActive || extra!=g_esi)",
        "PASS: Phase 6AC Mm166 wrapper provenance",
        "resumeEsp=c+24u",
        "PASS: Phase 6AC retail graphics pool claim",
        "case 356u: return 0x0087E098u; /* HalBootSMCVideoMode ULONG */",
        "PASS: Phase 6AC HalBootSMCVideoMode initialized ordinal=356 va=0087E098 value=00000000",
        "P6AC MM166WRAP SUMMARY:",
        "PHASE 6AC MM166 WRAPPER REUSE RESULT",
        "phase6ac_env_build_cookie",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AC] generated main lost marker: {marker}")

    if "size!=0x01680000u || extra!=g_esi" in main_text:
        raise SystemExit("[Phase6AC] stale one-size-only +28 gate remains")
    if "phase6ab_env_build_cookie" in main_text or "phase6ab_env_build_cookie" in env_text:
        raise SystemExit("[Phase6AC] stale Phase 6AB env cookie remains")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = p6aa.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6AC",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6ac_mm166_wrapper_reuse"] = {
        "source_phase": "6AB",
        "phase6ab_hardware_pass": True,
        "phase6ab_hardware": {
            "summary": {
                "direct": 1816,
                "last_direct": "0x0022AEE9",
                "icall": 9075,
                "last_icall": "0x00209720",
            },
            "boundary": {
                "kind": "KERNEL_FRAME",
                "caller": "0x0023A3CE",
                "target": "0x800000A6",
                "ordinal": 166,
                "name": "MmAllocateContiguousMemoryEx",
                "esp": "0x008BF7C0",
                "saved_esp": "0x008BF7DC",
                "frame_bytes": 28,
                "ticks": 670830,
                "trace": 179938,
                "fault": 0,
                "eax": "0xFFFFFFFF",
                "ecx": "0x00000060",
                "edx": "0x00000000",
                "esi": "0x00299380",
            },
        },
        "generated_wrapper_proof": proof,
        "decoded_boundary_request": {
            "size": "0x00000060",
            "low": "0x00000000",
            "high": "0xFFFFFFFF",
            "basis": (
                "hardware registers decoded through the structurally-proven "
                "sub_0022AEE9 push mapping ECX=size EDX=low EAX=high"
            ),
        },
        "repair_policy": (
            "canonical +24 Mm166 calls unchanged; +28 accepted only while the "
            "single structurally-proven sub_0022AEE9 RECOMP_ICALL_SAFE is active "
            "and c+24 equals live ESI; request size is no longer artificially "
            "restricted to the first 0x01680000 observation"
        ),
        "graphics_pool_special_case_inherited_unchanged": True,
        "hal_boot_video_mode_data_inherited_unchanged": True,
        "source_layout": source_layout,
    }

    (args.out_dir / "phase6ac-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print("[Phase6AC] MM166 WRAPPER REUSE: READY")
    print("[Phase6AC] Wrapper       : exact generated sub_0022AEE9")
    print("[Phase6AC] Canonical ABI : +24 unchanged")
    print("[Phase6AC] Wrapper ABI   : +28 only while wrapper-active and spill==live ESI")
    print("[Phase6AC] New hardware request decoded: size=0x60 low=0 high=0xFFFFFFFF")
    print("[Phase6AC] Graphics pool : existing exact 0x01680000 special claim unchanged")
    print("[Phase6AC] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

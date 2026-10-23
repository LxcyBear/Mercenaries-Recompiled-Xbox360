#!/usr/bin/env python3
"""Phase 6Y: repair the hardware-proven graphics-pool MmAllocateContiguousMemoryEx frame.

Phase 6X crossed sub_0020F9C0 and reached:
  KERNEL_FRAME target=0x800000A6 (ordinal 166 MmAllocateContiguousMemoryEx)
  esp=0x008BF9E0 saved_esp=0x008BF9FC delta=28
  ticks=670780 trace=179922 fault=0
  direct=1813 last_direct=0x0020F9C0, icall=9075

The maintained ordinal-166 continuation already implements the five-argument
kernel semantics, but historically required a 24-byte return+argument frame.
Upstream's retail graphics-memory test identifies sub_0022AEE9 as the physical
allocation wrapper used by sub_0020F9C0 and proves the retail request is
0x01680000 bytes.

6Y does not blindly widen ordinal 166. At emission time it inspects the locally
generated sub_0022AEE9 body and requires exactly one RECOMP_ICALL_SAFE plus a
saved-ESP expression containing +28. Only then does it permit the observed
28-byte frame, and only for the retail 0x01680000 graphics-pool request. The
existing 24-byte ABI remains accepted for all normal ordinal-166 calls.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BUILD_TAG = "P6Y-GFXPOOL-MM166-FRAME-20261023-B"
BASE_TAG = "P6X-GFXPOOL-FRONTIER-0020F9C0-20261023-A"
WRAPPER_VA = 0x0022AEE9
RETAIL_POOL_SIZE = 0x01680000
OBSERVED_FRAME_BYTES = 28
COOKIE_OLD = "phase6x_env_build_cookie"
COOKIE_NEW = "phase6y_env_build_cookie"
COOKIE_NUM_OLD = "50365858"
COOKIE_NUM_NEW = "50365959"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6Y] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6Y] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def function_span(text: str, signature: str) -> tuple[int, int]:
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"[Phase6Y] function marker missing: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"[Phase6Y] opening brace missing: {signature}")
    depth = 0
    i = brace
    in_string = False
    escape = False
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
    raise SystemExit(f"[Phase6Y] unterminated function: {signature}")


def prove_generated_wrapper_shape(base, generated_root: Path, functions: Path) -> dict:
    by_va, by_name = base.load_ranges(functions)
    generated = base.load_generated(generated_root, by_name)
    row = generated.get(WRAPPER_VA)
    if row is None:
        raise SystemExit(
            "[Phase6Y] generated sub_0022AEE9 body is missing; cannot prove ABI repair"
        )

    source = row["source"]
    call_count = source.count("RECOMP_ICALL_SAFE")
    if call_count != 1:
        raise SystemExit(
            f"[Phase6Y] expected exactly one RECOMP_ICALL_SAFE in sub_0022AEE9, "
            f"found {call_count}; refusing ABI guess"
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
            "[Phase6Y] sub_0022AEE9 no longer snapshots _icall_esp before its "
            "kernel ICALL; refusing ABI guess"
        )

    call_setup = source[save_match.end():call_match.start()]
    push_exprs = re.findall(
        r"PUSH32\(esp,\s*(.*?)\)\s*;",
        call_setup,
        re.S,
    )
    normalized = [re.sub(r"\s+", "", expr) for expr in push_exprs]
    print(
        "[Phase6Y] GENERATED PUSH SEQUENCE: "
        + " | ".join(normalized)
    )
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
            "[Phase6Y] sub_0022AEE9 kernel-call push shape changed; expected "
            "saved ESI + five Mm166 args + dummy return. Observed: "
            + ", ".join(normalized)
        )

    canonical_bytes = 6 * 4  # dummy return + five stdcall arguments
    spill_bytes = 4          # wrapper-saved ESI below the kernel frame
    proven_bytes = canonical_bytes + spill_bytes
    if proven_bytes != OBSERVED_FRAME_BYTES:
        raise SystemExit("[Phase6Y] internal Mm166 frame proof arithmetic drift")

    return {
        "name": row["name"],
        "recomp_icall_safe_count": call_count,
        "saved_esp_snapshot": "_icall_esp = g_esp",
        "push_sequence": normalized,
        "canonical_kernel_frame_bytes": canonical_bytes,
        "wrapper_spill": "esi",
        "wrapper_spill_bytes": spill_bytes,
        "observed_saved_esp_delta_proven": proven_bytes,
        "resume_policy": "consume 24-byte kernel frame; leave saved ESI on stack",
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6y_base")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6x-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6Y] cached Phase 6X baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6X" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6Y] cached Phase 6X baseline identity mismatch")

    proof = prove_generated_wrapper_shape(
        base, args.generated_root, args.functions
    )
    print(
        "[Phase6Y] GENERATED ABI PROOF: sub_0022AEE9 snapshots _icall_esp, "
        "then pushes saved ESI + five Mm166 args + dummy return = 28 bytes"
    )

    signature = "static void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)"
    start, end = function_span(main_text, signature)

    replacement = r'''static void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,size,low,high,align,prot,actual=0u,va;
    uint32_t frameBytes=savedEsp-c;
    uint32_t extra=0u;
    uint32_t repaired=0u;
    uint32_t resumeEsp=0u;
    char line[704];

    if(frameBytes!=24u && frameBytes!=28u)
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A6u,savedEsp);

    ret=GUEST_READ32(c);
    size=GUEST_READ32(c+4u);
    low=GUEST_READ32(c+8u);
    high=GUEST_READ32(c+12u);
    align=GUEST_READ32(c+16u);
    prot=GUEST_READ32(c+20u);
    if(frameBytes==28u)
        extra=GUEST_READ32(c+24u);

    if(s_accessFault)
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000A6u,savedEsp);
    if(ret!=0u)
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A6u,savedEsp);

    /*
     * Local generated sub_0022AEE9 proves the +28 shape is:
     *   c+00 dummy return
     *   c+04..c+20 five MmAllocateContiguousMemoryEx arguments
     *   c+24 saved ESI spill owned by the wrapper
     *
     * The ordinal owns only the first 24 bytes. Require the spill to still
     * equal live ESI; the proven wrapper does not modify ESI between PUSH esi
     * and RECOMP_ICALL_SAFE.
     */
    if(frameBytes==28u)
    {
        if(size!=0x01680000u || extra!=g_esi)
            phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A6u,savedEsp);
        repaired=1u;
    }

    /*
     * Consume only the canonical kernel frame. For +24 this equals savedEsp.
     * For the +28 wrapper it equals savedEsp-4, preserving saved ESI for the
     * wrapper's later POP32(esp, esi).
     */
    resumeEsp=c+24u;

    ++s_phase5bbMmCallCount;
    s_phase5bbMmLastOrdinal=166u;
    va=phase5bb_alloc_guest_pages(size,align,prot?prot:0x4u,&actual);
    if(va) ++s_phase5bbMmAllocSuccessCount;
    s_phase5bbMmLastBase=va;
    s_phase5bbMmLastSize=actual;
    g_eax=va;
    g_esp=resumeEsp;

    sprintf(
        line,
        "PASS: Phase 6Y ordinal 166 MmAllocateContiguousMemoryEx size=%u low=%08X high=%08X align=%u protect=%08X base=%08X rounded=%u frame=%u spill=%08X repair=%u resume_esp=%08X saved_esp=%08X",
        (unsigned)size,(unsigned)low,(unsigned)high,(unsigned)align,
        (unsigned)prot,(unsigned)va,(unsigned)actual,(unsigned)frameBytes,
        (unsigned)extra,(unsigned)repaired,(unsigned)g_esp,(unsigned)savedEsp);
    trace(line);
}'''

    main_text = main_text[:start] + replacement + main_text[end:]

    main_text = replace_unique(
        main_text, BASE_TAG, BUILD_TAG, "Phase 6X build tag"
    )
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = main_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)
    env_text = env_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)

    main_text = main_text.replace("P6X GFXPOOL SUMMARY:", "P6Y MM166 SUMMARY:")
    main_text = main_text.replace(
        "PHASE 6X GRAPHICS-POOL FRONTIER RESULT",
        "PHASE 6Y GRAPHICS-POOL MM166 RESULT",
    )
    main_text = main_text.replace("PHASE 6X", "PHASE 6Y")
    main_text = main_text.replace("Phase 6X", "Phase 6Y")
    main_text = main_text.replace('"P6X ', '"P6Y ')
    env_text = env_text.replace("PHASE 6X", "PHASE 6Y")
    env_text = env_text.replace("Phase 6X", "Phase 6Y")

    required = (
        BUILD_TAG,
        "phase6y_env_build_cookie",
        "PASS: Phase 6Y ordinal 166 MmAllocateContiguousMemoryEx",
        "frameBytes!=24u && frameBytes!=28u",
        "size!=0x01680000u || extra!=g_esi",
        "resumeEsp=c+24u",
        "P6Y XENOS: PASS Direct3D_CreateDevice",
        "P6Y FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6Y FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "#define PHASE4C_EXEC_BUDGET 2000000u",
        "#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6Y] generated main lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Reuse Phase 6X's sharding helper by loading its emitter module.
    # The build wrapper must remain small; monolithic source is cache only.
    base6x_path = Path(__file__).with_name(
        "emit_phase6x_graphics_pool_frontier_0020f9c0.py"
    )
    p6x = load(base6x_path, "phase6y_phase6x")
    source_layout = p6x.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6Y",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6y_mm166_frame_repair"] = {
        "source_phase": "6X",
        "phase6x_hardware_pass": True,
        "boundary": {
            "kind": "KERNEL_FRAME",
            "caller": "0x0023A3CE",
            "target": "0x800000A6",
            "ordinal": 166,
            "name": "MmAllocateContiguousMemoryEx",
            "esp": "0x008BF9E0",
            "saved_esp": "0x008BF9FC",
            "frame_bytes": 28,
            "ticks": 670780,
            "trace": 179922,
            "fault": 0,
            "eax": "0xFFFFFFFF",
            "ecx": "0x01680000",
        },
        "phase6x_summary": {
            "direct": 1813,
            "last_direct": "0x0020F9C0",
            "icall": 9075,
            "last_icall": "0x00209720",
        },
        "generated_wrapper_proof": proof,
        "retail_pool_size": "0x01680000",
        "canonical_frame_bytes": 24,
        "repaired_frame_bytes": 28,
        "repair_policy": (
            "accept +28 only when local generated sub_0022AEE9 proves saved ESI "
            "+ five Mm166 args + dummy return, runtime size is retail 0x01680000, "
            "and spill equals live ESI; consume only the canonical 24-byte kernel "
            "frame so the wrapper can later POP its saved ESI"
        ),
        "source_layout": source_layout,
    }

    (args.out_dir / "phase6y-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print("[Phase6Y] MM166 ABI REPAIR: +28 = 24-byte Mm166 frame + saved ESI spill")
    print("[Phase6Y] CANONICAL MM166 FRAME: +24 accepted; +28 resumes at savedEsp-4")
    print("[Phase6Y] RETAIL REPAIR GATE: size=0x01680000 and spill==live ESI")
    print("[Phase6Y] EXECUTION BUDGET: inherited 2000000 ticks")
    print("[Phase6Y] TITLE HEAP: inherited 32 MiB")
    print("[Phase6Y] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

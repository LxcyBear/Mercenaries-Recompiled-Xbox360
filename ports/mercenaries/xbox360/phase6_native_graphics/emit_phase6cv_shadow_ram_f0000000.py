#!/usr/bin/env python3
r"""Phase 6CV: retail 64 MiB NV2A BAR1/shadow-RAM alias.

6CU hardware crossed the post-XACT GetLastError frontier and then stopped on
the first translated graphics-memory access:
    GUEST_FAULT READ32 F08B0000
    caller=0023A3CE ticks=27020833 trace=1071564
    "P6CU FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached"

On a retail 64 MiB Xbox, the 0xF0000000-0xF3FFFFFF BAR1/shadow aperture maps
the same 64 MiB physical memory visible at 0x00000000-0x03FFFFFF. 6CV adds
only that alias to the existing checked guest-memory router.

Everything else is preserved:
  * 0xFDxxxxxx NV2A MMIO remains owned by the existing narrow bridges/fences;
  * 0xF4000000+ is not admitted by this alias;
  * existing KSEG/fence/kernel checks are unchanged;
  * 6CU XACT async-read/GetLastError semantics are unchanged;
  * D3D/XGRPH, APU, storage, Partition0 and the 64M watchdog are unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CU-POST-ASYNC-GETLASTERROR-0022B150-20261025-A"
BUILD_TAG = "P6CV-SHADOW-RAM-F0000000-20261025-A"
COOKIE_OLD = "phase6cu_env_build_cookie"
COOKIE_NEW = "phase6cv_env_build_cookie"
EMITTER_REVISION = "6CV-R2"

SHADOW_BASE = 0xF0000000
SHADOW_END = 0xF4000000
FAULT_ADDRESS = 0xF08B0000
FAULT_PHYSICAL = 0x008B0000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CV] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def function_span(text: str, signature: str) -> tuple[int, int]:
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"[Phase6CV] function missing: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"[Phase6CV] function brace missing: {signature}")

    depth = 0
    for i in range(brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                if end < len(text) and text[end] == "\n":
                    end += 1
                return start, end
    raise SystemExit(f"[Phase6CV] function unterminated: {signature}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"[Phase6CV] expected one {label}, found {count}"
        )
    return text.replace(old, new, 1)


def install_shadow_router(text: str) -> str:
    signature = "static int guest_offset(DWORD address, DWORD width, DWORD* out)"
    start, end = function_span(text, signature)
    body = text[start:end]

    for marker in (
        "if (address < MIRROR_END)",
        "else if (address >= KSEG_BASE && address < KSEG_END)",
        "offset = address & RAM_MASK;",
        "if (offset >= RAM_SIZE || width > RAM_SIZE - offset)",
    ):
        if marker not in body:
            raise SystemExit(
                f"[Phase6CV] inherited guest router lost marker: {marker}"
            )

    branch_anchor = (
        "    else if (address >= KSEG_BASE && address < KSEG_END)\n"
    )
    shadow_branch = r'''    else if (address >= PHASE6CV_SHADOW_BASE &&
             address < PHASE6CV_SHADOW_END)
    {
        /*
         * Retail Xbox NV2A BAR1/shadow-RAM aperture. The retail title has
         * 64 MiB, so this aperture aliases exactly the existing guest arena.
         */
        offset = address - PHASE6CV_SHADOW_BASE;
    }
    else if (address >= KSEG_BASE && address < KSEG_END)
'''
    if body.count(branch_anchor) != 1:
        raise SystemExit(
            f"[Phase6CV] expected one KSEG branch anchor, "
            f"found {body.count(branch_anchor)}"
        )
    body = body.replace(branch_anchor, shadow_branch, 1)
    text = text[:start] + body + text[end:]

    support = r'''#define PHASE6CV_SHADOW_BASE 0xF0000000u
#define PHASE6CV_SHADOW_END  0xF4000000u

static uint32_t s_phase6cvShadowReadCount;
static uint32_t s_phase6cvShadowWriteCount;
static uint32_t s_phase6cvShadowFirstAddress;
static uint32_t s_phase6cvShadowFirstPhysical;
static uint32_t s_phase6cvShadowLastAddress;
static uint32_t s_phase6cvShadowLastPhysical;
static uint32_t s_phase6cvShadowLastWidth;
static uint32_t s_phase6cvShadowLastWrite;

static int phase6cv_shadow_range(
    uint32_t address,
    uint32_t width,
    uint32_t* outPhysical)
{
    uint32_t physical;

    if (width == 0u)
        return 0;
    if (address < PHASE6CV_SHADOW_BASE ||
        address >= PHASE6CV_SHADOW_END)
        return 0;

    physical = address - PHASE6CV_SHADOW_BASE;
    if (physical >= RAM_SIZE || width > RAM_SIZE - physical)
        return 0;

    if (outPhysical)
        *outPhysical = physical;
    return 1;
}

static void phase6cv_shadow_note(
    uint32_t address,
    uint32_t width,
    int isWrite)
{
    uint32_t physical;
    uint32_t count;
    char line[256];

    if (!phase6cv_shadow_range(address, width, &physical))
        return;

    if (s_phase6cvShadowReadCount == 0u &&
        s_phase6cvShadowWriteCount == 0u)
    {
        s_phase6cvShadowFirstAddress = address;
        s_phase6cvShadowFirstPhysical = physical;
    }

    if (isWrite)
        count = ++s_phase6cvShadowWriteCount;
    else
        count = ++s_phase6cvShadowReadCount;

    s_phase6cvShadowLastAddress = address;
    s_phase6cvShadowLastPhysical = physical;
    s_phase6cvShadowLastWidth = width;
    s_phase6cvShadowLastWrite = isWrite ? 1u : 0u;

    if (count <= 32u || (count & 0xFFFu) == 0u)
    {
        if (isWrite)
        {
            sprintf(
                line,
                "P6CV SHADOW RAM WRITE addr=%08X physical=%08X width=%u count=%u",
                (unsigned int)address,
                (unsigned int)physical,
                (unsigned int)width,
                (unsigned int)count);
        }
        else
        {
            sprintf(
                line,
                "P6CV SHADOW RAM READ addr=%08X physical=%08X width=%u count=%u",
                (unsigned int)address,
                (unsigned int)physical,
                (unsigned int)width,
                (unsigned int)count);
        }
        trace(line);
    }
}

'''
    if text.count(signature) != 1:
        raise SystemExit("[Phase6CV] guest router definition count changed")
    return text.replace(signature, support + signature, 1)


def instrument_access(
    text: str,
    signature: str,
    width: int,
    is_write: bool,
) -> str:
    start, end = function_span(text, signature)
    body = text[start:end]
    brace = body.find("{")
    if brace < 0:
        raise SystemExit(
            f"[Phase6CV] access function brace missing: {signature}"
        )

    note = (
        f"\n    phase6cv_shadow_note(address, {width}u, "
        + ("1" if is_write else "0")
        + ");"
    )
    if "phase6cv_shadow_note(address," in body:
        raise SystemExit(
            f"[Phase6CV] access function already instrumented: {signature}"
        )

    body = body[:brace + 1] + note + body[brace + 1:]
    return text[:start] + body + text[end:]


def instrument_accesses(text: str) -> str:
    funcs = (
        ("uint8_t recomp_guest_read8(uint32_t address)", 1, False),
        ("uint16_t recomp_guest_read16(uint32_t address)", 2, False),
        ("uint32_t recomp_guest_read32(uint32_t address)", 4, False),
        ("uint64_t recomp_guest_read64(uint32_t address)", 8, False),
        ("void recomp_guest_write8(uint32_t address, uint8_t value)", 1, True),
        ("void recomp_guest_write16(uint32_t address, uint16_t value)", 2, True),
        ("void recomp_guest_write32(uint32_t address, uint32_t value)", 4, True),
        ("void recomp_guest_write64(uint32_t address, uint64_t value)", 8, True),
        ("static void recomp_guest_read128(uint32_t address, uint32_t words[4])", 16, False),
        ("static void recomp_guest_write128(", 16, True),
    )
    for signature, width, is_write in funcs:
        text = instrument_access(text, signature, width, is_write)
    return text


def insert_summary(text: str) -> str:
    marker = "P6CU GETLASTERROR:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CV] inherited 6CU summary missing")

    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6CV] final summary insertion point missing")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CV SHADOW RAM: reads=%u writes=%u first=%08X first_physical=%08X last=%08X last_physical=%08X last_width=%u last_write=%u",\n'
        f'{indent}    (unsigned int)s_phase6cvShadowReadCount,\n'
        f'{indent}    (unsigned int)s_phase6cvShadowWriteCount,\n'
        f'{indent}    (unsigned int)s_phase6cvShadowFirstAddress,\n'
        f'{indent}    (unsigned int)s_phase6cvShadowFirstPhysical,\n'
        f'{indent}    (unsigned int)s_phase6cvShadowLastAddress,\n'
        f'{indent}    (unsigned int)s_phase6cvShadowLastPhysical,\n'
        f'{indent}    (unsigned int)s_phase6cvShadowLastWidth,\n'
        f'{indent}    (unsigned int)s_phase6cvShadowLastWrite);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6cv_base")
    p6bl = load(args.phase6bl_emitter, "phase6cv_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cu-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CV] missing cached 6CU input: {path}")

    text = main_path.read_text(encoding="utf-8")
    env = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CU" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CV] cached 6CU identity mismatch")

    inherited = manifest.get("phase6cu_post_async_get_last_error", {})
    dispatch = inherited.get("dispatch_policy", {})
    if (
        inherited.get("execution_budget_inherited") != 64000000
        or inherited.get("async_read_semantics_changed") is not False
        or inherited.get("partition0_semantics_changed") is not False
        or inherited.get("graphics_bridge_semantics_changed") is not False
        or inherited.get("hard_fences_weakened") is not False
        or dispatch.get("canonical_support_helper_reused") is not True
    ):
        raise SystemExit("[Phase6CV] inherited 6CU policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "static int guest_offset(DWORD address, DWORD width, DWORD* out)",
        "if (address < MIRROR_END)",
        "else if (address >= KSEG_BASE && address < KSEG_END)",
        "#define RAM_SIZE           0x04000000u",
        "PASS: Phase 6CU maintained GetLastError",
        "P6CU GETLASTERROR:",
        "P6CU ASYNC STREAM READ:",
        "P6CU PIXEL CHASE:",
        "P6CU PRESENT PROXIMITY:",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in text:
            raise SystemExit(f"[Phase6CV] inherited marker missing: {marker}")

    text = install_shadow_router(text)
    text = instrument_accesses(text)
    text = insert_summary(text)

    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6CV] expected one inherited build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    env = env.replace(COOKIE_OLD, COOKIE_NEW)

    text = (
        text.replace("PHASE 6CU", "PHASE 6CV")
        .replace("Phase 6CU", "Phase 6CV")
        .replace('"P6CU ', '"P6CV ')
    )
    env = (
        env.replace("PHASE 6CU", "PHASE 6CV")
        .replace("Phase 6CU", "Phase 6CV")
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE6CV_SHADOW_END  0xF4000000u",
        "offset = address - PHASE6CV_SHADOW_BASE;",
        "P6CV SHADOW RAM READ",
        "P6CV SHADOW RAM:",
        "PASS: Phase 6CV maintained GetLastError",
        "P6CV ASYNC STREAM READ:",
        "P6CV PIXEL CHASE:",
        "P6CV PRESENT PROXIMITY:",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    )
    for marker in required:
        if marker not in text:
            raise SystemExit(f"[Phase6CV] generated source lost marker: {marker}")

    # Safety gates: admit only the exact retail 64 MiB BAR1 window.
    if "PHASE6CV_SHADOW_END  0xF4000000u" not in text:
        raise SystemExit("[Phase6CV] shadow aperture upper bound changed")
    if "address >= PHASE6CV_SHADOW_BASE &&" not in text:
        raise SystemExit("[Phase6CV] shadow aperture lower-bound gate missing")
    if "address < PHASE6CV_SHADOW_END" not in text:
        raise SystemExit("[Phase6CV] shadow aperture upper-bound gate missing")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env, encoding="utf-8")

    manifest.update({
        "phase": "6CV",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6cv_shadow_ram_alias"] = {
        "source_phase": "6CU",
        "phase6cu_hardware": {
            "boundary_kind": "GUEST_FAULT",
            "caller": "0x0023A3CE",
            "target": "0xF08B0000",
            "access": "READ",
            "width": 4,
            "ticks": 27020833,
            "trace": 1071564,
            "fault": 1,
            "classification": "NV2A VRAM/BAR1 shadow-RAM aperture",
            "get_last_error_calls": 1,
            "get_last_error_value": "0x000003E5",
            "async_read_calls": 1,
            "async_read_successes": 1,
            "async_pending_returns": 1,
            "async_bytes": 2048,
            "display_calls": 0,
            "framebuffer": "0x00000000",
        },
        "mapping": {
            "guest_start": f"0x{SHADOW_BASE:08X}",
            "guest_end_exclusive": f"0x{SHADOW_END:08X}",
            "physical_start": "0x00000000",
            "physical_end_exclusive": "0x04000000",
            "fault_example_guest": f"0x{FAULT_ADDRESS:08X}",
            "fault_example_physical": f"0x{FAULT_PHYSICAL:08X}",
            "size_bytes": 0x04000000,
            "policy": "retail 64 MiB unified-memory shadow alias only",
        },
        "telemetry": {
            "read_write_counters": True,
            "first_last_guest_address": True,
            "first_last_physical_offset": True,
            "access_width": True,
        },
        "execution_budget_inherited": 64000000,
        "translated_pack_changed": False,
        "async_read_semantics_changed": False,
        "partition0_semantics_changed": False,
        "xact_semantics_changed": False,
        "graphics_mmio_semantics_changed": False,
        "apu_mmio_semantics_changed": False,
        "kseg_semantics_changed": False,
        "null_page_semantics_changed": False,
        "seh_terminator_semantics_changed": False,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }

    (args.out_dir / "phase6cv-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6CV] emitter revision: {EMITTER_REVISION}")
    print("[Phase6CV] 6CU hardware boundary: READ32 F08B0000")
    print("[Phase6CV] shadow alias: F0000000-F3FFFFFF -> 00000000-03FFFFFF")
    print("[Phase6CV] proof example: F08B0000 -> 008B0000")
    print("[Phase6CV] FD/FE scoped MMIO bridges unchanged")
    print("[Phase6CV] F4000000+ remains outside shadow alias")
    print("[Phase6CV] 6CU XACT/GetLastError/D3D semantics preserved")
    print("[Phase6CV] 64M watchdog preserved")
    print("[Phase6CV] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

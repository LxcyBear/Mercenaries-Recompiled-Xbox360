#!/usr/bin/env python3
"""Phase 6CC: route hardware-proven manual PblMath trig frontier 0x001F9D70.

6CB hardware balanced the synthetic FILE_OBJECT lifetime and then reached:
  DIRECT_FRONTIER caller=0x0023A3CE target=0x001F9D70
  esp=saved_esp=0x008BF988 ticks=956060 trace=180293 fault=0

The retail function is intentionally marked --manual-function by Recompile.ps1,
so absence from runtime/gen is expected. The maintained PC/manual port already
contains reviewed source-matched replacements for the PblMath 8192-entry sine
family at 0x001F9D70/0x001F9DA0/0x001F9DE0. 6CC ports that exact family into
this Xbox 360 harness rather than inventing a translated body.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CB-OBFDEREF250-SENTINEL-20261024-A"
BUILD_TAG = "P6CC-DIRECT-FRONTIER-001F9D70-20261024-A"
COOKIE_OLD = "phase6cb_env_build_cookie"
COOKIE_NEW = "phase6cc_env_build_cookie"

ROOT = 0x001F9D70
CALLER = 0x0023A3CE
MANUAL_FAMILY = (0x001F9D70, 0x001F9DA0, 0x001F9DE0)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CC] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CC] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def validate_inventory(address: int, by_va: dict) -> None:
    row = by_va.get(address)
    if row is None:
        containing = [
            r for r in by_va.values()
            if int(r["start"]) < address < int(r["end"])
        ]
        if containing:
            owner = sorted(containing, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6CC] 0x{address:08X} is not an exact function start; "
                f"owner=0x{int(owner['start']):08X}-0x{int(owner['end']):08X} "
                f"{owner['name']}"
            )
        raise SystemExit(
            f"[Phase6CC] manual address 0x{address:08X} absent from inventory"
        )


def install_manual_trig_family(text: str) -> str:
    anchor = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CC] expected one pack lookup anchor, found {text.count(anchor)}"
        )

    support = r'''#include <math.h>
#include <string.h>

/*
 * Phase 6CC reviewed manual PblMath trig family.
 * Source semantics mirror ports/mercenaries/src/recomp_manual.c.
 * Retail normally fills an 8192-entry writable sine table from a C++ global
 * constructor. The maintained port deliberately computes the same quantized
 * samples natively so an absent constructor cannot poison geometry/gameplay.
 */
static uint32_t s_phase6ccPblSinCalls = 0u;
static uint32_t s_phase6ccPblCosCalls = 0u;
static uint32_t s_phase6ccPblSinCosCalls = 0u;
static uint32_t s_phase6ccPblLastEsp = 0u;
static uint32_t s_phase6ccPblLastAngleBits = 0u;

static float phase6cc_guest_f32(uint32_t address)
{
    uint32_t bits = GUEST_READ32(address);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static void phase6cc_guest_store_f32(uint32_t address, float value)
{
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    GUEST_WRITE32(address, bits);
}

static int32_t phase6cc_pbl_trig_index(float angle)
{
    const float table_scale = 8192.0f / 6.28318530717958647692f;
    return (int32_t)(0.5f + angle * table_scale);
}

static float phase6cc_pbl_sine_sample(int32_t index)
{
    const float table_step = 6.28318530717958647692f / 8192.0f;
    return sinf((float)(index & 0x1FFF) * table_step);
}

static void phase6cc_fp_return(float value)
{
    g_fp_stack[--g_fp_top & 7u] = (double)value;
    g_esp += 4u;
}

static void phase6cc_pbl_sin_001f9d70(void)
{
    const uint32_t entryEsp = g_esp;
    const uint32_t angleBits = GUEST_READ32(entryEsp + 4u);
    float angle;
    char line[320];

    memcpy(&angle, &angleBits, sizeof(angle));
    ++s_phase6ccPblSinCalls;
    s_phase6ccPblLastEsp = entryEsp;
    s_phase6ccPblLastAngleBits = angleBits;

    if (s_phase6ccPblSinCalls == 1u)
    {
        sprintf(
            line,
            "PASS: Phase 6CC entered manual PblMath sin 001F9D70 esp=%08X angle_bits=%08X",
            (unsigned int)entryEsp,
            (unsigned int)angleBits);
        trace(line);
    }

    phase6cc_fp_return(
        phase6cc_pbl_sine_sample(phase6cc_pbl_trig_index(angle)));
}

static void phase6cc_pbl_cos_001f9da0(void)
{
    const float angle = phase6cc_guest_f32(g_esp + 4u);
    const int32_t index = phase6cc_pbl_trig_index(angle);
    ++s_phase6ccPblCosCalls;
    phase6cc_fp_return(-phase6cc_pbl_sine_sample(index - 0x800));
}

static void phase6cc_pbl_sincos_001f9de0(void)
{
    const uint32_t sineAddress = GUEST_READ32(g_esp + 4u);
    const uint32_t cosineAddress = GUEST_READ32(g_esp + 8u);
    const float angle = phase6cc_guest_f32(g_esp + 12u);
    const int32_t index = phase6cc_pbl_trig_index(angle);

    ++s_phase6ccPblSinCosCalls;
    phase6cc_guest_store_f32(
        sineAddress,
        phase6cc_pbl_sine_sample(index));
    phase6cc_guest_store_f32(
        cosineAddress,
        -phase6cc_pbl_sine_sample(index - 0x800));
    g_esp += 4u;
}

'''
    text = text.replace(anchor, support + anchor, 1)

    lookup_start = text.find(anchor)
    lookup_end = text.find("\n}\n", lookup_start)
    if lookup_start < 0 or lookup_end < 0:
        raise SystemExit("[Phase6CC] could not isolate pack lookup")
    lookup = text[lookup_start:lookup_end + 3]

    if "case 0x001F9D70u:" in lookup:
        raise SystemExit("[Phase6CC] manual PblMath root already present in lookup")

    switch_anchor = "    switch (xbox_va) {\n"
    if switch_anchor not in lookup:
        raise SystemExit("[Phase6CC] pack lookup switch marker changed")

    cases = (
        "    case 0x001F9D70u: return phase6cc_pbl_sin_001f9d70;\n"
        "    case 0x001F9DA0u: return phase6cc_pbl_cos_001f9da0;\n"
        "    case 0x001F9DE0u: return phase6cc_pbl_sincos_001f9de0;\n"
    )
    patched = lookup.replace(switch_anchor, switch_anchor + cases, 1)
    text = text[:lookup_start] + patched + text[lookup_end + 3:]

    for marker in (
        "phase6cc_pbl_sin_001f9d70",
        "case 0x001F9D70u: return phase6cc_pbl_sin_001f9d70;",
        "case 0x001F9DA0u: return phase6cc_pbl_cos_001f9da0;",
        "case 0x001F9DE0u: return phase6cc_pbl_sincos_001f9de0;",
    ):
        if marker not in text:
            raise SystemExit(f"[Phase6CC] manual trig installation lost marker: {marker}")

    return text


def insert_summary(text: str) -> str:
    marker = "P6CB OBFDEREF250:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CC] inherited ObfDereference summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6CC] could not locate inherited summary block")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CC MANUAL PBL TRIG: sin=%u cos=%u sincos=%u last_esp=%08X angle_bits=%08X",\n'
        f'{indent}    (unsigned int)s_phase6ccPblSinCalls,\n'
        f'{indent}    (unsigned int)s_phase6ccPblCosCalls,\n'
        f'{indent}    (unsigned int)s_phase6ccPblSinCosCalls,\n'
        f'{indent}    (unsigned int)s_phase6ccPblLastEsp,\n'
        f'{indent}    (unsigned int)s_phase6ccPblLastAngleBits);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase5bb-emitter", type=Path, required=False)
    ap.add_argument("--phase5bc-emitter", type=Path, required=False)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6cc_base")
    p6bl = load(args.phase6bl_emitter, "phase6cc_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cb-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CC] cached Phase 6CB input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    env_before = env_text
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CB" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CC] cached Phase 6CB identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6CC] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "_phase4c_target == 0x800000FAu",
        "PASS: Phase 6CB ObfDereferenceObject sentinel release",
        "P6CB OBFDEREF250:",
        "P6CB KFLOWERIRQL161:",
        "P6CB IDEX QUEUE HEAD:",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CC] inherited 6CB marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)

    for address in MANUAL_FAMILY:
        validate_inventory(address, by_va)

    if ROOT in generated:
        raise SystemExit(
            "[Phase6CC] 0x001F9D70 unexpectedly has a generated body; "
            "manual-function policy changed, review before routing both"
        )

    main_text = install_manual_trig_family(main_text)
    main_text = insert_summary(main_text)

    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6CC route hardware-proven DIRECT_FRONTIER 0023A3CE -> 001F9D70 through the maintained source-matched manual PblMath 8192-entry trig family (001F9D70/001F9DA0/001F9DE0); preserve 6CB balanced FILE_OBJECT release, all graphics/file/fence/allocator semantics and 8M budget",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6CB", "PHASE 6CC")
        .replace("Phase 6CB", "Phase 6CC")
        .replace('"P6CB ', '"P6CC ')
    )
    env_text = (
        env_text.replace("PHASE 6CB", "PHASE 6CC")
        .replace("Phase 6CB", "Phase 6CC")
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "case 0x001F9D70u: return phase6cc_pbl_sin_001f9d70;",
        "case 0x001F9DA0u: return phase6cc_pbl_cos_001f9da0;",
        "case 0x001F9DE0u: return phase6cc_pbl_sincos_001f9de0;",
        "PASS: Phase 6CC entered manual PblMath sin 001F9D70",
        "P6CC MANUAL PBL TRIG:",
        "P6CC OBFDEREF250:",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CC] generated source lost marker: {marker}")

    expected_env = (
        env_before.replace(COOKIE_OLD, COOKIE_NEW)
        .replace("PHASE 6CB", "PHASE 6CC")
        .replace("Phase 6CB", "Phase 6CC")
    )
    if env_text != expected_env:
        raise SystemExit(
            "[Phase6CC] phase5_env.cpp changed beyond expected tag/cookie renames"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6CC",
            "build_tag": BUILD_TAG,
            "pack_members": pack_count,
            "members": members,
        }
    )
    manifest["phase6cc_direct_frontier"] = {
        "source_phase": "6CB",
        "phase6cb_hardware": {
            "obf_dereference_calls": 1,
            "obf_dereference_successes": 1,
            "synthetic_object": "0x04000000",
            "synthetic_outstanding": 0,
            "ntclose_handle": "0x48000001",
            "ntclose_status": "0x00000000",
            "next_boundary_kind": "DIRECT_FRONTIER",
            "next_boundary_caller": "0x0023A3CE",
            "next_boundary_target": "0x001F9D70",
            "boundary_esp": "0x008BF988",
            "boundary_saved_esp": "0x008BF988",
            "boundary_eax": "0x0085BC44",
            "boundary_ecx": "0x0085BC04",
            "boundary_edx": "0x00000002",
            "fault": 0,
            "ticks": 956060,
            "trace": 180293,
            "xapi_return": 0,
        },
        "root": "0x001F9D70",
        "root_name": by_va[ROOT]["name"],
        "frontier_caller": "0x0023A3CE",
        "root_is_declared_manual_function": True,
        "generated_body_expected": False,
        "manual_source_basis": "ports/mercenaries/src/recomp_manual.c",
        "manual_family": [
            "0x001F9D70",
            "0x001F9DA0",
            "0x001F9DE0",
        ],
        "manual_semantics": (
            "source-matched PblMath 8192-entry quantized sine/cosine family; "
            "native sinf replaces writable retail table constructor dependency"
        ),
        "translated_membership_changed": False,
        "phase5_env_semantics_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6cc-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6CC] 001F9D70 is an intentional --manual-function; no generated body expected")
    print("[Phase6CC] installed maintained PblMath trig family: 001F9D70/001F9DA0/001F9DE0")
    print("[Phase6CC] semantics: source-matched 8192-step quantized sine/cosine via native sinf")
    print("[Phase6CC] translated pack membership unchanged")
    print("[Phase6CC] 6CB hardware provenance: fault=0 ticks=956060 trace=180293")
    print("[Phase6CC] execution budget: inherited 8000000 ticks")
    print("[Phase6CC] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

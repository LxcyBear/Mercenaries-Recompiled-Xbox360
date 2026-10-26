#!/usr/bin/env python3
r"""Phase 6CW: post-shadow-RAM DSOUND sibling sweep rooted at 0x002A6713.

6CV hardware proved the retail F0000000-F3FFFFFF shadow-RAM alias:
  * three READ32 accesses at F08B0000 mapped to physical 008B0000;
  * no shadow writes were observed;
  * the old graphics-aperture guest fault disappeared;
  * execution continued to a clean DIRECT_FRONTIER:
        caller=0x0023A3CE -> target=0x002A6713
        ticks=27,021,442 trace=1,071,655 fault=0.

0x002A6713 lies inside the retail DSOUND section. Earlier Phase 6S/6T
hardware showed that this caller can walk closely-spaced DSOUND siblings, so
6CW uses the already-proven support-clean sibling-sweep shape instead of one
hardware run per address.

Safety policy:
  * 0x002A6713 must be an exact generated function start;
  * interior entries are never redirected to a containing prologue;
  * unresolved support is pruned by the existing Phase-5BC support scanner;
  * the mandatory root may not be pruned;
  * the 6CV shadow-RAM alias, scoped FD/FE MMIO bridges, XACT async semantics,
    Partition0 behavior, D3D/XGRPH state and 64M watchdog are unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CV-SHADOW-RAM-F0000000-20261025-A"
BUILD_TAG = "P6CW-DSOUND-SWEEP-002A6713-20261026-A"
COOKIE_OLD = "phase6cv_env_build_cookie"
COOKIE_NEW = "phase6cw_env_build_cookie"
EMITTER_REVISION = "6CW-R3"

ROOT = 0x002A6713
CALLER = 0x0023A3CE
DSOUND_START = 0x0029CB80
DSOUND_END = 0x002BB274
SWEEP_CAP = 1024


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CW] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validate_exact_dsound_target(root: int, by_va: dict, generated: dict) -> dict:
    if not (DSOUND_START <= root < DSOUND_END):
        raise SystemExit(
            f"[Phase6CW] target 0x{root:08X} is outside DSOUND "
            f"0x{DSOUND_START:08X}-0x{DSOUND_END:08X}"
        )

    row = by_va.get(root)
    if row is None:
        containing = [
            r for r in by_va.values()
            if int(r["start"]) < root < int(r["end"])
        ]
        if containing:
            r = sorted(containing, key=lambda x: int(x["start"]))[-1]
            start = int(r["start"])
            end = int(r["end"])
            state = "generated" if start in generated else "not-generated"
            raise SystemExit(
                f"[Phase6CW] DSOUND target 0x{root:08X} is an interior entry, "
                f"not an exact function start; containing function "
                f"0x{start:08X}-0x{end:08X} {r['name']} ({state}). "
                "Refusing to redirect an interior entry to the prologue."
            )
        raise SystemExit(
            f"[Phase6CW] DSOUND target 0x{root:08X} is absent from the function inventory"
        )

    if row.get("name") != "sub_002A6713":
        raise SystemExit(
            f"[Phase6CW] exact root name changed: {row.get('name')}"
        )

    # 0x002A6713 is deliberately a --manual-function in Recompile.ps1.
    # Its maintained source-equivalent DSOUND decryptor lives in
    # ports/mercenaries/src/recomp_manual.c, so absence from runtime/gen is
    # expected and must not be treated as missing translation coverage.
    if root in generated:
        raise SystemExit(
            "[Phase6CW] 0x002A6713 unexpectedly has a generated body; "
            "manual-function ownership changed and needs review"
        )
    return row


def instrument_root(rendered: str, name: str) -> str:
    name_pos = rendered.find(name)
    brace_pos = rendered.find("{", name_pos)
    if name_pos < 0 or brace_pos < 0:
        raise SystemExit("[Phase6CW] could not instrument mandatory DSOUND root")
    probe = r'''
    RECOMP_TRACE_FUNC(0x002A6713u);
    trace("PASS: Phase 6CW entered DSOUND frontier 002A6713");
'''
    return rendered[:brace_pos + 1] + probe + rendered[brace_pos + 1:]


def install_manual_dsound_root(text: str) -> str:
    """Install the maintained source-equivalent 0x002A6713 DSOUND decryptor."""
    lookup_marker = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    lookup_pos = text.find(lookup_marker)
    if lookup_pos < 0:
        raise SystemExit("[Phase6CW] pack lookup definition marker changed")
    if "static void sub_002A6713(void)\n{" in text:
        raise SystemExit("[Phase6CW] manual DSOUND root is already defined")

    body = r'''
static uint32_t s_phase6cwDsoundDecryptCalls;
static uint32_t s_phase6cwDsoundDecryptBytes;
static uint32_t s_phase6cwDsoundDecryptLastBytes;
static uint32_t s_phase6cwDsoundDecryptLastHeader;
static uint32_t s_phase6cwDsoundDecryptLastInput;
static uint32_t s_phase6cwDsoundDecryptLastOutput;

static void phase6cw_dsound_rng_step(
    uint32_t low,
    uint32_t high,
    uint32_t* nextLow,
    uint32_t* nextHigh)
{
    uint32_t feedback = low;

    feedback = (feedback << 2) ^ low;
    feedback = (feedback << 1) ^ low;
    feedback = (feedback << 28) ^ high;

    *nextLow = (low >> 1) | (high << 31);
    *nextHigh = (high >> 1) | (feedback & 0x80000000u);
}

static void phase6cw_dsound_rng_store(uint32_t low, uint32_t high)
{
    GUEST_WRITE32(0x002BB168u, low);
    GUEST_WRITE32(0x002BB16Cu, high);
}

static void phase6cw_dsound_rng_advance(uint32_t* low, uint32_t* high)
{
    uint32_t nextLow;
    uint32_t nextHigh;

    phase6cw_dsound_rng_step(*low, *high, &nextLow, &nextHigh);
    *low = nextLow;
    *high = nextHigh;
    phase6cw_dsound_rng_store(nextLow, nextHigh);
}

/*
 * Source-equivalent manual replacement from ports/mercenaries/src/recomp_manual.c.
 * The production runtime keeps this manual because the retail XDK DirectSound
 * image loader decrypts dsstdfx.bin through a PRNG byte loop. Running that loop
 * through translated calls is needlessly expensive. This Xbox 360 copy uses the
 * checked guest-memory ABI and spells out little-endian state bytes explicitly,
 * because Xenon itself is big-endian.
 */
static void sub_002A6713(void)
{
    const uint32_t stateAddress = GUEST_READ32(g_esp + 4u);
    uint32_t inputAddress = GUEST_READ32(g_esp + 8u);
    uint32_t length = GUEST_READ32(g_esp + 12u);
    const uint32_t outputAddress = GUEST_READ32(g_esp + 16u);
    const uint32_t decodeHeader = GUEST_READ32(g_esp + 20u);
    uint8_t initialState[8];
    uint8_t decodedState[8];
    uint32_t rngLow = 0x49DE12BAu;
    uint32_t rngHigh = 0x7FA49BCAu;
    uint32_t index;
    uint32_t processed;

    RECOMP_TRACE_FUNC(0x002A6713u);
    PHASE4C_BUDGET_TICK(0x002A6713u);
    trace("PASS: Phase 6CW entered DSOUND frontier 002A6713");

    ++s_phase6cwDsoundDecryptCalls;
    s_phase6cwDsoundDecryptLastHeader = decodeHeader;
    s_phase6cwDsoundDecryptLastInput = inputAddress;
    s_phase6cwDsoundDecryptLastOutput = outputAddress;

    /* sub_002A66E6 advances constants once, then advances state 80 times. */
    for (index = 0u; index < 81u; ++index)
        phase6cw_dsound_rng_advance(&rngLow, &rngHigh);

    /* The retail state bytes are little-endian even though Xenon is not. */
    initialState[0] = (uint8_t)(rngLow);
    initialState[1] = (uint8_t)(rngLow >> 8);
    initialState[2] = (uint8_t)(rngLow >> 16);
    initialState[3] = (uint8_t)(rngLow >> 24);
    initialState[4] = (uint8_t)(rngHigh);
    initialState[5] = (uint8_t)(rngHigh >> 8);
    initialState[6] = (uint8_t)(rngHigh >> 16);
    initialState[7] = (uint8_t)(rngHigh >> 24);

    if (decodeHeader != 0u) {
        for (index = 0u; index < 8u; ++index)
            decodedState[index] =
                GUEST_READ8(inputAddress + index) ^ initialState[index];
        if (stateAddress != 0u) {
            for (index = 0u; index < 8u; ++index)
                GUEST_WRITE8(stateAddress + index, decodedState[index]);
        }
    } else {
        if (stateAddress == 0u) {
            g_eax = 0xFFFFFFFFu;
            g_esp += 24u;
            return;
        }
        for (index = 0u; index < 8u; ++index)
            decodedState[index] = GUEST_READ8(stateAddress + index);
    }

    rngLow =
        (uint32_t)initialState[0] |
        ((uint32_t)initialState[1] << 8) |
        ((uint32_t)initialState[2] << 16) |
        ((uint32_t)initialState[3] << 24);
    rngHigh =
        (uint32_t)initialState[4] |
        ((uint32_t)initialState[5] << 8) |
        ((uint32_t)initialState[6] << 16) |
        ((uint32_t)initialState[7] << 24);
    phase6cw_dsound_rng_advance(&rngLow, &rngHigh);

    if (decodeHeader != 0u) {
        inputAddress += 8u;
        length -= 8u;
    }

    processed = length;
    for (index = 0u; index < length; ++index) {
        const uint32_t keyIndex = index & 7u;
        const uint8_t input = GUEST_READ8(inputAddress + index);
        const uint8_t product = (uint8_t)(
            decodedState[keyIndex] * initialState[keyIndex]);
        const uint8_t mixed = (uint8_t)(input - product);

        phase6cw_dsound_rng_advance(&rngLow, &rngHigh);
        GUEST_WRITE8(
            outputAddress + index,
            (uint8_t)(initialState[keyIndex] ^ (uint8_t)rngLow ^ mixed));
    }

    s_phase6cwDsoundDecryptBytes += processed;
    s_phase6cwDsoundDecryptLastBytes = processed;

    if (s_phase6cwDsoundDecryptCalls <= 8u) {
        char line[256];
        sprintf(
            line,
            "PASS: Phase 6CW manual DSOUND decrypt call=%u bytes=%u header=%u input=%08X output=%08X total=%u",
            (unsigned int)s_phase6cwDsoundDecryptCalls,
            (unsigned int)processed,
            (unsigned int)decodeHeader,
            (unsigned int)inputAddress,
            (unsigned int)outputAddress,
            (unsigned int)s_phase6cwDsoundDecryptBytes);
        trace(line);
    }

    g_eax = 0u;
    g_esp += 24u;
}

'''
    text = text[:lookup_pos] + body + text[lookup_pos:]

    lookup_pos = text.find(lookup_marker)
    default_marker = "    default: return (recomp_func_t)0;"
    default_pos = text.find(default_marker, lookup_pos)
    if default_pos < 0:
        raise SystemExit("[Phase6CW] pack lookup default marker changed")
    case_line = "    case 0x002A6713u: return sub_002A6713;\n"
    if case_line in text:
        raise SystemExit("[Phase6CW] manual DSOUND dispatch already present")
    text = text[:default_pos] + case_line + text[default_pos:]
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase5bb-emitter", type=Path, required=True)
    ap.add_argument("--phase5bc-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6cw_base")
    p5bb = load(args.phase5bb_emitter, "phase6cw_p5bb")
    p5bc = load(args.phase5bc_emitter, "phase6cw_p5bc")
    p6bl = load(args.phase6bl_emitter, "phase6cw_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cv-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CW] missing cached 6CV input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CV" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CW] cached 6CV identity mismatch")

    inherited = manifest.get("phase6cv_shadow_ram_alias", {})
    mapping = inherited.get("mapping", {})
    if (
        inherited.get("execution_budget_inherited") != 64000000
        or inherited.get("async_read_semantics_changed") is not False
        or inherited.get("partition0_semantics_changed") is not False
        or inherited.get("graphics_mmio_semantics_changed") is not False
        or inherited.get("apu_mmio_semantics_changed") is not False
        or inherited.get("kseg_semantics_changed") is not False
        or inherited.get("hard_fences_weakened") is not False
        or mapping.get("guest_start") != "0xF0000000"
        or mapping.get("guest_end_exclusive") != "0xF4000000"
        or mapping.get("physical_end_exclusive") != "0x04000000"
    ):
        raise SystemExit("[Phase6CW] inherited 6CV policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE6CV_SHADOW_END  0xF4000000u",
        "offset = address - PHASE6CV_SHADOW_BASE;",
        "P6CV SHADOW RAM:",
        "P6CV ASYNC STREAM READ:",
        "P6CV PIXEL CHASE:",
        "P6CV PRESENT PROXIMITY:",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CW] inherited marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    root_row = validate_exact_dsound_target(ROOT, by_va, generated)

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    old = {int(x, 0) for x in manifest.get("members", [])}

    dsound_generated = sorted(
        va for va in generated if DSOUND_START <= va < DSOUND_END
    )
    remaining = [va for va in dsound_generated if va not in old]
    forward = [va for va in remaining if va > ROOT]
    prefrontier = [va for va in remaining if va < ROOT]
    candidate_order = forward + prefrontier
    candidate_new = candidate_order[:SWEEP_CAP]
    truncated = max(0, len(candidate_order) - len(candidate_new))

    new_members = list(candidate_new)
    expanded = old | set(new_members)

    # The mandatory root is maintained manual support, not a generated member.
    # Sweep generated siblings independently; then install the exact root body
    # and dispatch case from recomp_manual.c semantics.
    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument_root
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text,
        base,
        p5bb,
        generated,
        new_members,
        expanded,
        require_sweep_root=False,
    )
    main_text = install_manual_dsound_root(main_text)

    # p5bc may prune candidates in place; recompute the authoritative generated
    # pack. The manual root is tracked separately in the manifest.
    total_pack = old | set(new_members)

    if main_text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6CW] expected one inherited build tag, found {main_text.count(BASE_TAG)}"
        )
    main_text = main_text.replace(BASE_TAG, BUILD_TAG, 1)
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6CV", "PHASE 6CW")
        .replace("Phase 6CV", "Phase 6CW")
        .replace('"P6CV ', '"P6CW ')
    )
    env_text = (
        env_text.replace("PHASE 6CV", "PHASE 6CW")
        .replace("Phase 6CV", "Phase 6CW")
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "case 0x002A6713u:",
        "PASS: Phase 6CW entered DSOUND frontier 002A6713",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE6CV_SHADOW_END  0xF4000000u",
        "offset = address - PHASE6CV_SHADOW_BASE;",
        "P6CW SHADOW RAM:",
        "P6CW ASYNC STREAM READ:",
        "P6CW PIXEL CHASE:",
        "P6CW PRESENT PROXIMITY:",
        "PASS: Phase 6CW manual DSOUND decrypt",
        "GUEST_WRITE32(0x002BB168u, low);",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6CW] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6CW",
        "build_tag": BUILD_TAG,
        "pack_members": len(total_pack),
        "members": [f"0x{x:08X}" for x in sorted(total_pack)],
    })
    manifest["phase6cw_dsound_sweep"] = {
        "source_phase": "6CV",
        "phase6cv_hardware": {
            "boundary_kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x002A6713",
            "ticks": 27021442,
            "trace": 1071655,
            "fault": 0,
            "shadow_reads": 3,
            "shadow_writes": 0,
            "shadow_guest": "0xF08B0000",
            "shadow_physical": "0x008B0000",
            "display_calls": 0,
            "framebuffer": "0x00000000",
        },
        "root": f"0x{ROOT:08X}",
        "root_name": root_row["name"],
        "frontier_caller": f"0x{CALLER:08X}",
        "target_section": "DSOUND",
        "target_section_start": f"0x{DSOUND_START:08X}",
        "target_section_end": f"0x{DSOUND_END:08X}",
        "candidate_cap": SWEEP_CAP,
        "total_generated_dsound_members": len(dsound_generated),
        "remaining_generated_dsound_members": len(remaining),
        "forward_remaining_members": len(forward),
        "prefrontier_remaining_members": len(prefrontier),
        "selected_candidate_members": len(candidate_new),\n        "manual_root_dispatch": True,\n        "manual_root_source": "ports/mercenaries/src/recomp_manual.c",
        "truncated_candidate_members": truncated,
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(total_pack),
        "new_direct_frontier_targets": [
            f"0x{x:08X}" for x in sorted(frontiers)
        ],
        "execution_budget_inherited": 64000000,
        "shadow_ram_alias_preserved": True,
        "shadow_ram_guest_start": "0xF0000000",
        "shadow_ram_guest_end_exclusive": "0xF4000000",
        "translated_existing_pack_changed": False,
        "async_read_semantics_changed": False,
        "partition0_semantics_changed": False,
        "graphics_mmio_semantics_changed": False,
        "apu_mmio_semantics_changed": False,
        "kseg_semantics_changed": False,
        "null_page_semantics_changed": False,
        "seh_terminator_semantics_changed": False,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }
    manifest["phase6cw_candidate_new_members"] = [
        f"0x{x:08X}" for x in candidate_new
    ]
    manifest["phase6cw_new_members"] = [
        f"0x{x:08X}" for x in sorted(new_members)
    ]
    manifest["phase6cw_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6cw-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6CW] emitter revision: {EMITTER_REVISION}")
    print(
        f"[Phase6CW] DSOUND root: 0x{ROOT:08X} "
        f"{root_row['name']} (maintained manual)"
    )
    print(
        f"[Phase6CW] sibling sweep: generated={len(dsound_generated)} "
        f"remaining={len(remaining)} selected={len(candidate_new)} "
        f"truncated={truncated} pruned={len(pruned)} "
        f"packed_new={len(new_members)} total={len(total_pack)}"
    )
    print("[Phase6CW] 6CV shadow RAM alias preserved")
    print("[Phase6CW] XACT/Partition0/D3D/XGRPH/APU semantics preserved")
    print("[Phase6CW] 64M watchdog preserved")
    print("[Phase6CW] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

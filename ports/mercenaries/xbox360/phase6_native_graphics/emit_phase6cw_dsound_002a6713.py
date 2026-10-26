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
EMITTER_REVISION = "6CW-R2"

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


def validate_exact_dsound_target(root: int, by_va: dict, generated: dict) -> None:
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

    if root not in generated:
        raise SystemExit(
            f"[Phase6CW] DSOUND target 0x{root:08X} is exact function "
            f"{row['name']} but has no generated translated body. "
            "Translation coverage must be extended; refusing to fabricate a return."
        )


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
    validate_exact_dsound_target(ROOT, by_va, generated)

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    old = {int(x, 0) for x in manifest.get("members", [])}
    if ROOT in old:
        raise SystemExit(
            "[Phase6CW] target 0x002A6713 is already in the manifest pack; "
            "the observed direct frontier would then require dispatch-bookkeeping diagnosis"
        )

    dsound_generated = sorted(
        va for va in generated if DSOUND_START <= va < DSOUND_END
    )
    remaining = [va for va in dsound_generated if va not in old]
    if ROOT not in remaining:
        raise SystemExit(
            "[Phase6CW] mandatory root is not an unpacked exact generated DSOUND start"
        )

    forward = [ROOT] + [va for va in remaining if va > ROOT]
    prefrontier = [va for va in remaining if va < ROOT]
    candidate_order = forward + prefrontier
    candidate_new = candidate_order[:SWEEP_CAP]
    truncated = max(0, len(candidate_order) - len(candidate_new))

    if ROOT not in candidate_new:
        raise SystemExit("[Phase6CW] candidate construction lost mandatory root")

    new_members = list(candidate_new)
    expanded = old | set(new_members)

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument_root
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text,
        base,
        p5bb,
        generated,
        new_members,
        expanded,
        require_sweep_root=True,
    )

    if ROOT not in new_members:
        names = pruned.get(ROOT, [])
        raise SystemExit(
            "[Phase6CW] support-clean pruning removed mandatory 002A6713: "
            + ", ".join(names)
        )

    # p5bc may prune candidates in place; recompute the authoritative pack.
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
        "root_name": generated[ROOT]["name"],
        "frontier_caller": f"0x{CALLER:08X}",
        "target_section": "DSOUND",
        "target_section_start": f"0x{DSOUND_START:08X}",
        "target_section_end": f"0x{DSOUND_END:08X}",
        "candidate_cap": SWEEP_CAP,
        "total_generated_dsound_members": len(dsound_generated),
        "remaining_generated_dsound_members": len(remaining),
        "forward_remaining_members": len(forward),
        "prefrontier_remaining_members": len(prefrontier),
        "selected_candidate_members": len(candidate_new),
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
        f"{generated[ROOT]['name']}"
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

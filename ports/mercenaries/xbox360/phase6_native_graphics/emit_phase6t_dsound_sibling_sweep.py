#!/usr/bin/env python3
"""Phase 6T: broad support-clean DSOUND sibling sweep.

Phase 6S proved exact DSOUND entry 0x002A0159 executes on hardware, then the
same table-walk caller stopped five ticks later at ICALL_SAFE
0x0023A3CE -> 0x002A0164 with fault=0, ticks=430997, trace=131963.

The 0xB-byte step shows that a call-graph closure is the wrong batching shape.
6T enumerates exact generated function starts across DSOUND itself, prioritizes
0x002A0164 and every remaining generated start after it, then uses spare
capacity on pre-frontier DSOUND starts. The existing support-clean pruner stays
authoritative; no unresolved helper is guessed or stubbed.

A 1024-member candidate cap intentionally amortizes hardware testing while
preserving hard stops for interior entries, missing bodies, unresolved support,
NV2A/platform/ABI boundaries, and guest faults.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BUILD_TAG = "P6T-DSOUND-SIBLING-SWEEP-002A0164-20261022-A"
ROOT = 0x002A0164
CALLER = 0x0023A3CE
DSOUND_START = 0x0029CB80
DSOUND_END = 0x002BB274
SWEEP_CAP = 1024
SHARD_TARGET_CHARS = 750000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6T] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validate_exact_dsound_target(root: int, by_va: dict, generated: dict) -> None:
    if not (DSOUND_START <= root < DSOUND_END):
        raise SystemExit(
            f"[Phase6T] target 0x{root:08X} is outside expected DSOUND "
            f"range 0x{DSOUND_START:08X}-0x{DSOUND_END:08X}"
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
            generated_state = "generated" if start in generated else "not-generated"
            raise SystemExit(
                f"[Phase6T] DSOUND target 0x{root:08X} is an interior entry, "
                f"not an exact function start; containing function "
                f"0x{start:08X}-0x{end:08X} {r['name']} ({generated_state}). "
                "Refusing to redirect an interior entry to the function prologue."
            )
        raise SystemExit(
            f"[Phase6T] DSOUND target 0x{root:08X} is absent from the function inventory"
        )

    if root not in generated:
        raise SystemExit(
            f"[Phase6T] DSOUND target 0x{root:08X} is exact function "
            f"{row['name']} but has no generated translated body. "
            "The next step must extend translation coverage into XPP; "
            "refusing to fabricate a platform return."
        )


def instrument_root(rendered: str, name: str) -> str:
    name_pos = rendered.find(name)
    brace_pos = rendered.find("{", name_pos)
    if name_pos < 0 or brace_pos < 0:
        raise SystemExit("[Phase6T] could not instrument DSOUND root 0x002A0164")
    return (
        rendered[:brace_pos + 1]
        + "\n    s_phase6tRootEntered = 1;"
        + rendered[brace_pos + 1:]
    )


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'

    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6T] translated-body optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6T] translated-body optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6T] translated-body block contains no functions")

    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6T] translated function opening brace missing")
        function_ends.append(base.closing_brace(masked, open_index))

    cut_points = []
    chunk_start = 0
    last_end = 0
    for end in function_ends:
        last_end = end
        if end - chunk_start >= SHARD_TARGET_CHARS:
            cut_points.append(end)
            chunk_start = end
    if last_end < len(body):
        last_end = len(body)
    if not cut_points or cut_points[-1] != last_end:
        cut_points.append(last_end)

    shard_dir = out_dir / "translated_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale in shard_dir.glob("phase6t_*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cut_points):
        if end <= start:
            continue
        name = f"phase6t_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({
            "name": name,
            "chars": len(payload),
            "lines": payload.count("\n") + 1,
        })
        start = end

    if start != len(body):
        raise SystemExit("[Phase6T] shard writer did not consume full body block")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n'
        for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]

    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8")
        for row in shards
    )
    if reconstructed != body:
        raise SystemExit("[Phase6T] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_count": len(shards),
        "target_chars": SHARD_TARGET_CHARS,
        "body_chars": len(body),
        "body_lines": body.count("\n") + 1,
        "wrapper_chars": len(wrapper),
        "wrapper_lines": wrapper.count("\n") + 1,
        "shards": shards,
    }


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"[Phase6T] expected exactly one {label}, found {count}"
        )
    return text.replace(old, new, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bb-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bc-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6t_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6t_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6t_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6s-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6T] cached Phase 6S baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6S":
        raise SystemExit("[Phase6T] cached baseline manifest is not Phase 6S")
    if manifest.get("build_tag") != "P6S-DSOUND-FRONTIER-002A0159-20261022-A":
        raise SystemExit("[Phase6T] cached Phase 6S baseline build tag mismatch")

    s = manifest.get("phase6s_dsound_frontier", {})
    if s.get("phase_owned_crt_support") != ["cos", "sin"]:
        raise SystemExit("[Phase6T] Phase 6S CRT support identity mismatch")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact_dsound_target(ROOT, by_va, generated)

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")
    if "#include <math.h>" not in main_text:
        raise SystemExit("[Phase6T] inherited Phase 6S source lost <math.h>")

    old = {int(x, 0) for x in manifest.get("members", [])}
    if ROOT in old:
        raise SystemExit("[Phase6T] DSOUND target 0x002A0164 is already packed")

    dsound_generated = sorted(
        va for va in generated
        if DSOUND_START <= va < DSOUND_END
    )
    remaining = [va for va in dsound_generated if va not in old]
    if ROOT not in remaining:
        raise SystemExit(
            "[Phase6T] DSOUND sibling root 0x002A0164 is not an unpacked exact generated start"
        )

    forward = [ROOT] + [va for va in remaining if va > ROOT]
    prefrontier = [va for va in remaining if va < ROOT]
    candidate_order = forward + prefrontier
    candidate_new = candidate_order[:SWEEP_CAP]
    truncated_candidates = max(0, len(candidate_order) - len(candidate_new))

    if ROOT not in candidate_new:
        raise SystemExit("[Phase6T] sibling sweep lost mandatory root 0x002A0164")

    new_members = list(candidate_new)
    expanded = old | set(new_members)

    marker = "static int s_phase6sRootEntered;"
    if marker not in main_text:
        raise SystemExit("[Phase6T] inherited Phase 6S root-state marker changed")
    main_text = main_text.replace(
        marker,
        marker + "\nstatic int s_phase6tRootEntered;",
        1,
    )

    marker = "    s_phase6sRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6T] inherited Phase 6S reset marker changed")
    main_text = main_text.replace(
        marker,
        marker + "    s_phase6tRootEntered = 0;\n",
        1,
    )

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument_root
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text,
        base,
        p5bb,
        generated,
        new_members,
        expanded,
    )
    if ROOT not in new_members:
        raise SystemExit(
            "[Phase6T] support-clean pruning removed mandatory DSOUND root; "
            "a real DSOUND/platform support implementation is required"
        )

    main_text = replace_unique(
        main_text,
        "P6S DSOUND FRONTIER SUMMARY:",
        "P6T DSOUND SIBLING SUMMARY:",
        "Phase 6S summary token",
    )
    main_text = replace_unique(
        main_text,
        "s_phase6sRootEntered &&",
        "s_phase6tRootEntered &&",
        "Phase 6S root result gate",
    )

    result_old = "PHASE 6S DSOUND FRONTIER RESULT"
    result_count = main_text.count(result_old)
    if result_count < 1:
        raise SystemExit("[Phase6T] Phase 6S result token missing")
    main_text = main_text.replace(
        result_old,
        "PHASE 6T DSOUND SIBLING SWEEP RESULT",
    )

    old_policy = (
        "Policy: start from hardware-proven Phase-6R XPP frontier pass, resolve exact "
        "ICALL_SAFE DSOUND target 002A0159 with a bounded depth-4/cap-256 generated DSOUND closure, "
        "retain proven cos()/sin() CRT support, and hard-stop on interior-entry, missing-body, "
        "NV2A/platform/ABI/guest-fault/missing-support boundaries"
    )
    new_policy = (
        "Policy: start from hardware-proven Phase-6S DSOUND frontier pass, sweep exact generated "
        "DSOUND sibling entrypoints from 002A0164 forward with a 1024-member candidate cap, "
        "support-clean prune every unresolved helper, retain proven cos()/sin() CRT support, "
        "and hard-stop on interior-entry, missing-body, NV2A/platform/ABI/guest-fault boundaries"
    )
    if old_policy in main_text:
        main_text = main_text.replace(old_policy, new_policy, 1)

    main_text = replace_unique(
        main_text,
        "P6S-DSOUND-FRONTIER-002A0159-20261022-A",
        BUILD_TAG,
        "Phase 6S build tag",
    )
    main_text = main_text.replace(
        "phase6s_env_build_cookie",
        "phase6t_env_build_cookie",
    )
    env_text = env_text.replace(
        "phase6s_env_build_cookie",
        "phase6t_env_build_cookie",
    )
    main_text = main_text.replace("50365353", "50365454")
    env_text = env_text.replace("50365353", "50365454")

    main_text = (
        main_text
        .replace("PHASE 6S", "PHASE 6T")
        .replace("Phase 6S", "Phase 6T")
        .replace('"P6S ', '"P6T ')
    )
    env_text = (
        env_text
        .replace("PHASE 6S", "PHASE 6T")
        .replace("Phase 6S", "Phase 6T")
    )

    required = (
        BUILD_TAG,
        "case 0x002A0164u:",
        "s_phase6tRootEntered = 1;",
        "P6T XENOS: PASS Direct3D_CreateDevice",
        "P6T FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6T FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "P6T DSOUND SIBLING SUMMARY",
        "PHASE 6T DSOUND SIBLING SWEEP RESULT",
        "#pragma warning(disable:4102)",
    )
    for item in required:
        if item not in main_text:
            raise SystemExit(f"[Phase6T] generated main lost marker: {item}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6T",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6t_dsound_sibling_sweep"] = {
        "source_phase": "6S",
        "cached_base": True,
        "phase6s_hardware_pass": True,
        "phase6s_observed_boundary": {
            "kind": "ICALL_SAFE",
            "caller": "0x0023A3CE",
            "target": "0x002A0164",
            "esp": "0x008BFF40",
            "saved_esp": "0x008BFF44",
            "fault": 0,
            "ticks": 430997,
            "trace": 131963,
            "direct_dispatches_before_boundary": 1765,
            "icall_dispatches_before_boundary": 9067,
            "last_packed_direct": "0x0023BE3C",
            "last_packed_icall": "0x002A0159",
        },
        "execution_budget_inherited": 600000,
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
        "truncated_candidate_members": truncated_candidates,
        "candidate_new_members": len(candidate_new),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(expanded),
        "new_direct_frontier_targets": [
            f"0x{x:08X}" for x in sorted(frontiers)
        ],
        "phase_owned_crt_support": ["cos", "sin"],
        "xenos_surface_inherited": True,
        "source_layout": source_layout,
        "runtime_policy": (
            "exact generated DSOUND sibling sweep from 0x002A0164 forward with 1024-member cap; "
            "interior-entry, missing-body, unresolved support, NV2A, platform/ABI, "
            "and guest-memory faults remain hard stops"
        ),
    }
    manifest["phase6t_candidate_new_members"] = [
        f"0x{x:08X}" for x in candidate_new
    ]
    manifest["phase6t_new_members"] = [
        f"0x{x:08X}" for x in sorted(new_members)
    ]
    manifest["phase6t_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6t-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"[Phase6T] DSOUND SIBLING SWEEP: root=0x{ROOT:08X} "
        f"name={generated[ROOT]['name']} total_generated={len(dsound_generated)} "
        f"remaining={len(remaining)} selected={len(candidate_new)} "
        f"truncated={truncated_candidates} pruned={len(pruned)} "
        f"packed_new={len(new_members)} total_pack={len(expanded)}"
    )
    print(
        f"[Phase6T] SOURCE SHARDS: wrapper_lines={source_layout['wrapper_lines']} "
        f"translated_body_lines={source_layout['body_lines']} "
        f"shards={source_layout['shard_count']}"
    )
    print("[Phase6T] HARD STOPS: interior DSOUND entry / missing DSOUND body / unresolved support / NV2A / ABI / guest fault")
    print("[Phase6T] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

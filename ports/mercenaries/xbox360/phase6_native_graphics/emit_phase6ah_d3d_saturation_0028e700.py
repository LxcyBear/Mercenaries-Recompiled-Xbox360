#!/usr/bin/env python3
"""Phase 6AH: advance the hardware-proven retail-D3D frontier at 0x0028E700.

Phase 6AG-D hardware proved:
  * native Xenos CreateDevice remains PASS;
  * the exact retail CreateDevice handoff again publishes guest device 0x00299380;
  * regenerated exact sub_00290895 executes successfully on real Xbox 360;
  * Phase 6AG's independent D3D-neighborhood result reports PASS;
  * the next clean boundary is:
      DIRECT_FRONTIER 0x0023A3CE -> 0x0028E700
      esp=saved_esp=0x008BF918, fault=0;
  * last direct progress reached 0x0028EB90 inside the retail D3D section.

6AH promotes 0x0028E700 as the next reviewed hardware root. It packs a deeper
support-clean closure, then performs ONE bounded D3D-only saturation round:
newly exposed direct frontiers are pre-armed only when they are exact generated
entries inside the retail D3D section. Anything ambiguous, outside D3D, or
support-unsafe remains fenced.

The proven native-Xenos CreateDevice handoff, exact 0x00290895 split, graphics
pool, platform compatibility, and NV2A/MMIO/VRAM hard-stop policy are inherited
unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6AG-D3D-NEIGHBORHOOD-00290895-20261023-D"
BUILD_TAG = "P6AH-D3D-SATURATION-0028E700-20261023-B"
COOKIE_OLD = "phase6ag_env_build_cookie"
COOKIE_NEW = "phase6ah_env_build_cookie"

ROOT = 0x0028E700
CALLER = 0x0023A3CE
ROOT_DEPTH = 8
ROOT_CAP = 512

D3D_START = 0x00288640
D3D_END = 0x0029B874
SATURATION_ROOT_LIMIT = 6
SATURATION_DEPTH = 2
SATURATION_CAP_PER_ROOT = 64
SATURATION_TOTAL_NEW_CAP = 192

SHARD_TARGET_CHARS = 750000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AH] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AH] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, new_policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AH] runtime Policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AH] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return text[:line_start] + indent + 'trace("' + new_policy + '");' + text[line_end:]


def validate_exact(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        hit = [r for r in by_va.values() if int(r["start"]) < root < int(r["end"])]
        if hit:
            row = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6AH] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "Refusing an interior-entry redirect; regenerate from the reviewed "
                "manual seed before emission."
            )
        raise SystemExit(
            f"[Phase6AH] target 0x{root:08X} is absent from function inventory"
        )
    if root not in generated:
        raise SystemExit(
            f"[Phase6AH] target 0x{root:08X} is exact function "
            f"{by_va[root]['name']} but has no generated translated body"
        )


def instrument_root(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6AH] could not instrument D3D root 0x0028E700")
    injected = (
        "\n    s_phase6ahRootEntered = 1;"
        '\n    trace("PASS: Phase 6AH retail D3D root 0028E700 entered");'
    )
    return rendered[: b + 1] + injected + rendered[b + 1 :]


def install_state(main_text: str) -> str:
    marker = "static int s_phase6agRootEntered;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AH] inherited Phase 6AG root state marker missing")
    return main_text.replace(
        marker,
        "static int s_phase6ahRootEntered;\n" + marker,
        1,
    )


def reset_state(main_text: str) -> str:
    marker = "    s_phase6agRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AH] inherited Phase 6AG root reset marker missing")
    return main_text.replace(
        marker,
        "    s_phase6ahRootEntered = 0;\n" + marker,
        1,
    )


def install_phase_result(main_text: str) -> str:
    # Preserve the prior 6AG result as a historical sub-proof, but give 6AH its
    # own authoritative result tied to this root plus the already-proven chain.
    prior = "PHASE 6AG D3D NEIGHBORHOOD RESULT: %s"
    if prior not in main_text:
        raise SystemExit("[Phase6AH] inherited Phase 6AG independent result missing")
    main_text = main_text.replace(
        prior,
        "P6AH PRIOR D3D ROOT 00290895 RESULT: %s",
        1,
    )

    marker = "P6AG D3D DEVICE:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6AH] inherited P6AG D3D device summary missing")

    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 3200:
        raise SystemExit("[Phase6AH] could not locate inherited D3D summary statement")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "PHASE 6AH D3D SATURATION RESULT: %s",\n'
        f'{indent}    (s_phase6ahRootEntered && s_phase6agRootEntered && '
        f's_phase6afCreateDeviceBridgeCount != 0u) ? "PASS" : "FAIL");\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + block + main_text[line_start:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AH] optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6AH] optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AH] translated body contains no functions")

    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6AH] translated function opening brace missing")
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
    for stale in shard_dir.glob("*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cut_points):
        if end <= start:
            continue
        name = f"phase6ah_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append(
            {
                "name": name,
                "chars": len(payload),
                "lines": payload.count("\n") + 1,
            }
        )
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AH] shard writer did not consume body")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n' for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]
    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8") for row in shards
    )
    if reconstructed != body:
        raise SystemExit("[Phase6AH] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6ah_",
        "shard_count": len(shards),
        "body_chars": len(body),
        "body_lines": body.count("\n") + 1,
        "wrapper_chars": len(wrapper),
        "wrapper_lines": wrapper.count("\n") + 1,
        "shards": shards,
    }


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

    base = load(args.base_emitter, "phase6ah_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6ah_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6ah_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6ag-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AH] cached Phase 6AG-D baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AG" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AH] cached Phase 6AG-D baseline identity mismatch")

    ag = manifest.get("phase6ag_d3d_neighborhood") or {}
    if (
        ag.get("phase6af_hardware_pass") is not True
        or ag.get("independent_phase_result_gate") is not True
        or ag.get("native_createdevice_handoff_inherited_unchanged") is not True
        or ag.get("root") != "0x00290895"
    ):
        raise SystemExit("[Phase6AH] inherited Phase 6AG proof/model drift")

    for marker in (
        BASE_TAG,
        "PASS: Phase 6AG retail D3D root 00290895 entered",
        "PHASE 6AG D3D NEIGHBORHOOD RESULT: %s",
        "PASS: Phase 6AG native D3D CreateDevice handoff",
        "static int s_phase6agRootEntered;",
        "phase6ag_env_build_cookie",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6AH] inherited marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact(ROOT, by_va, generated)

    old = {int(x, 0) for x in manifest.get("members", [])}
    if not old:
        raise SystemExit("[Phase6AH] inherited translated pack membership is empty")
    if ROOT in old:
        raise SystemExit(
            "[Phase6AH] root 0x0028E700 is already present in inherited pack; "
            "inspect dispatch bookkeeping instead of repacking it"
        )

    root_closure = set(
        p5bb.bounded_promoted_members(base, ROOT, generated, ROOT_DEPTH, ROOT_CAP)
    )
    root_closure.add(ROOT)
    root_new = sorted(va for va in root_closure if va not in old)
    if ROOT not in root_new:
        raise SystemExit("[Phase6AH] closure construction lost mandatory D3D root")

    main_text = install_state(main_text)
    main_text = reset_state(main_text)

    expanded = old | set(root_new)
    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument_root

    main_text, rendered_root, first_frontiers, first_pruned = p5bc.insert_pack_members(
        main_text,
        base,
        p5bb,
        generated,
        root_new,
        expanded,
    )

    if ROOT in first_pruned or ROOT not in root_new:
        names = first_pruned.get(ROOT, [])
        joined = ", ".join(str(x) for x in names) if names else "<unknown>"
        raise SystemExit(
            f"[Phase6AH] support-clean pruning removed mandatory D3D root "
            f"0x{ROOT:08X}; unresolved support={joined}"
        )

    # One bounded saturation round. Only exact generated direct frontiers still
    # inside the retail D3D section are eligible. Interior/unknown targets and
    # anything outside D3D remain normal hardware fences.
    eligible = [
        va
        for va in sorted(first_frontiers)
        if D3D_START <= va < D3D_END
        and va in generated
        and va not in expanded
    ]
    saturation_roots = eligible[:SATURATION_ROOT_LIMIT]

    saturation_candidates = set()
    for seed in saturation_roots:
        members = set(
            p5bb.bounded_promoted_members(
                base,
                seed,
                generated,
                SATURATION_DEPTH,
                SATURATION_CAP_PER_ROOT,
            )
        )
        members.add(seed)
        saturation_candidates.update(members)

    saturation_new_all = sorted(
        va for va in saturation_candidates if va not in expanded
    )

    # Prioritize the direct frontier roots themselves, then fill the remaining
    # bounded budget with their shallow closure members.
    prioritized = []
    for va in saturation_roots:
        if va in saturation_new_all and va not in prioritized:
            prioritized.append(va)
    for va in saturation_new_all:
        if va not in prioritized:
            prioritized.append(va)
    saturation_new = prioritized[:SATURATION_TOTAL_NEW_CAP]

    second_frontiers = set()
    second_pruned = {}
    saturation_fallback = False
    if saturation_new:
        pre_sat_expanded = set(expanded)
        pre_sat_main = main_text
        expanded.update(saturation_new)
        try:
            main_text, rendered_sat, second_frontiers, second_pruned = (
                p5bc.insert_pack_members(
                    main_text,
                    base,
                    p5bb,
                    generated,
                    saturation_new,
                    expanded,
                    require_sweep_root=False,
                )
            )
        except SystemExit as exc:
            # The saturation round is opportunistic only. If every optional
            # candidate requires support we do not yet own, preserve the
            # already-clean mandatory root pack and leave those D3D frontiers
            # fenced for hardware instead of failing the whole 6AH stage.
            msg = str(exc)
            if "support-clean sweep unexpectedly lost all candidates" not in msg:
                raise
            saturation_fallback = True
            main_text = pre_sat_main
            expanded = pre_sat_expanded
            second_frontiers = set()
            second_pruned = {}
            saturation_new[:] = []
            print(
                "[Phase6AH] SATURATION FALLBACK: optional D3D saturation had "
                "no support-clean candidates; keeping mandatory root-only pack"
            )

    retained_saturation_roots = [
        va for va in saturation_roots if va in expanded
    ]
    final_frontiers = (set(first_frontiers) | set(second_frontiers)) - expanded

    main_text = install_phase_result(main_text)

    new_policy = (
        "Policy: inherit 6AG-D CreateDevice and exact 00290895; pack support-clean "
        "D3D root 0028E700 plus one exact-entry D3D saturation round; continue "
        "translated D3D; keep NV2A/MMIO/VRAM, platform, ABI and guest faults hard"
    )
    if len(new_policy) > 240:
        raise SystemExit("[Phase6AH] startup policy trace exceeds safe length")
    main_text = replace_policy_line(main_text, new_policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text
        .replace("PHASE 6AG", "PHASE 6AH")
        .replace("Phase 6AG", "Phase 6AH")
        .replace('"P6AG ', '"P6AH ')
    )
    env_text = (
        env_text
        .replace("PHASE 6AG", "PHASE 6AH")
        .replace("Phase 6AG", "Phase 6AH")
    )

    # Make the inherited ancient gate visibly non-authoritative rather than
    # presenting a confusing FAIL beside the real Phase-6AH result.
    if "PHASE 6AH COS HARVEST RESULT" in main_text:
        main_text = main_text.replace(
            "PHASE 6AH COS HARVEST RESULT",
            "P6AH LEGACY COS HARVEST RESULT (NON-AUTHORITATIVE)",
            1,
        )

    required = (
        BUILD_TAG,
        "case 0x0028E700u:",
        "s_phase6ahRootEntered = 1;",
        "PASS: Phase 6AH retail D3D root 0028E700 entered",
        "PHASE 6AH D3D SATURATION RESULT: %s",
        "s_phase6ahRootEntered && s_phase6agRootEntered && "
        "s_phase6afCreateDeviceBridgeCount != 0u",
        "P6AH PRIOR D3D ROOT 00290895 RESULT: %s",
        "PASS: Phase 6AH native D3D CreateDevice handoff",
        "P6AH XENOS: PASS Direct3D_CreateDevice",
        "P6AH FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6AH FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "phase6ah_env_build_cookie",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AH] generated source lost marker: {marker}")

    if COOKIE_OLD in main_text or COOKIE_OLD in env_text:
        raise SystemExit("[Phase6AH] stale Phase 6AG cookie remains")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    all_new_retained = sorted(set(root_new) | set(saturation_new))
    manifest.update(
        {
            "phase": "6AH",
            "build_tag": BUILD_TAG,
            "pack_members": len(expanded),
            "members": [f"0x{x:08X}" for x in sorted(expanded)],
        }
    )
    manifest["phase6ah_d3d_saturation"] = {
        "source_phase": "6AG",
        "phase6ag_hardware_pass": True,
        "phase6ag_hardware": {
            "native_createdevice": {
                "result": "PASS",
                "guest_device": "0x00299380",
                "device_out": "0x007AD604",
                "width": 640,
                "height": 480,
                "format": "0x00000006",
                "back_buffers": 1,
                "multisample": "0x00000011",
                "swap": 1,
                "auto_depth": 1,
                "depth_format": "0x0000002A",
            },
            "prior_root": {
                "target": "0x00290895",
                "result": "PASS",
            },
            "next_boundary": {
                "kind": "DIRECT_FRONTIER",
                "caller": "0x0023A3CE",
                "target": "0x0028E700",
                "esp": "0x008BF918",
                "saved_esp": "0x008BF918",
                "ticks": 670874,
                "trace": 179944,
                "fault": 0,
                "eax": "0x00000000",
                "ecx": "0x00000000",
                "edx": "0x00000003",
            },
            "last_direct": "0x0028EB90",
            "independent_result": "PASS",
            "xapi_return": 0,
        },
        "root": f"0x{ROOT:08X}",
        "root_name": generated[ROOT]["name"],
        "frontier_caller": f"0x{CALLER:08X}",
        "root_closure_depth": ROOT_DEPTH,
        "root_closure_cap": ROOT_CAP,
        "root_candidate_members": len(root_closure),
        "root_retained_new_members": len(root_new),
        "root_pruned_members": len(first_pruned),
        "d3d_section": {
            "start": f"0x{D3D_START:08X}",
            "end_exclusive": f"0x{D3D_END:08X}",
        },
        "saturation": {
            "rounds": 1,
            "eligible_exact_generated_frontiers": [
                f"0x{x:08X}" for x in eligible
            ],
            "selected_roots": [f"0x{x:08X}" for x in saturation_roots],
            "retained_roots": [
                f"0x{x:08X}" for x in retained_saturation_roots
            ],
            "depth": SATURATION_DEPTH,
            "cap_per_root": SATURATION_CAP_PER_ROOT,
            "total_new_cap": SATURATION_TOTAL_NEW_CAP,
            "candidate_new_members": len(saturation_new_all),
            "retained_new_members": len(saturation_new),
            "pruned_members": len(second_pruned),
            "fallback_to_root_only": saturation_fallback,
        },
        "expanded_pack_members": len(expanded),
        "all_new_retained_members": len(all_new_retained),
        "remaining_direct_frontiers": [
            f"0x{x:08X}" for x in sorted(final_frontiers)
        ],
        "native_createdevice_handoff_inherited_unchanged": True,
        "exact_00290895_split_inherited_unchanged": True,
        "authoritative_result": (
            "s_phase6ahRootEntered && s_phase6agRootEntered && "
            "s_phase6afCreateDeviceBridgeCount != 0"
        ),
        "legacy_cos_result_non_authoritative": True,
        "source_layout": source_layout,
        "runtime_policy": (
            "support-clean D3D closure rooted at hardware-proven 0x0028E700 plus "
            "one D3D-only exact-generated frontier saturation round; preserve all "
            "proven graphics/platform semantics and hard-stop genuine NV2A/MMIO/VRAM"
        ),
    }

    (args.out_dir / "phase6ah-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6AH] D3D SATURATION 0028E700: READY")
    print(f"[Phase6AH] Root candidate members: {len(root_closure)}")
    print(f"[Phase6AH] Root retained new members: {len(root_new)}")
    print(
        "[Phase6AH] Saturation exact D3D roots: "
        + (
            ", ".join(f"{x:08X}" for x in saturation_roots)
            if saturation_roots
            else "<none>"
        )
    )
    print(f"[Phase6AH] Saturation retained new members: {len(saturation_new)}")
    print(f"[Phase6AH] Saturation fallback root-only: {int(saturation_fallback)}")
    print(f"[Phase6AH] Remaining direct frontiers: {len(final_frontiers)}")
    print("[Phase6AH] Native CreateDevice + exact 00290895: inherited unchanged")
    print("[Phase6AH] Purple remains reserved for genuine NV2A MMIO/VRAM")
    print("[Phase6AH] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

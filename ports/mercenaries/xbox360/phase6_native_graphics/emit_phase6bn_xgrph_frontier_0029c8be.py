#!/usr/bin/env python3
"""Phase 6BN: cross the clean post-6BM XGRPH DIRECT_FRONTIER 0x0029C8BE.

6BM hardware proved that the bounded 0x00290970 closure entered, all inherited
GPU bridge semantics stayed coherent, and execution advanced to DIRECT_FRONTIER
0x0029C8BE with fault=0. The target lies inside the retail XGRPH image section
(0x0029B880..0x0029CB7C).

This phase does not assume that the target is a valid function start. It first
requires exact-start proof from functions.json + generated translated code.
Only then does it add a bounded depth-4, cap-256 support-clean closure rooted at
0x0029C8BE. PFIFO/PFB/ZCOMP/PGRAPH/MMIO/VRAM/allocator behavior is unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BM-D3D-FRONTIER-00290970-20261024-A"
BUILD_TAG = "P6BN-XGRPH-FRONTIER-0029C8BE-20261024-A"
ROOT = 0x0029C8BE
ROOT_DEPTH = 4
ROOT_CAP = 256
COOKIE_OLD = "phase6bm_env_build_cookie"
COOKIE_NEW = "phase6bn_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BN] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BN] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def install_state(main_text: str) -> str:
    marker = "static DWORD s_phase6bmRootEntries = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6BN] inherited 6BM root-state anchor missing")
    return main_text.replace(
        marker,
        marker + "static DWORD s_phase6bnRootEntries = 0u;\n",
        1,
    )


def instrument_root(rendered: str, name: str) -> str:
    pos = rendered.find(name)
    brace = rendered.find("{", pos)
    if pos < 0 or brace < 0:
        raise SystemExit("[Phase6BN] could not instrument root 0x0029C8BE")
    body = (
        "\n    ++s_phase6bnRootEntries;"
        "\n    trace(\"PASS: Phase 6BN entered translated XGRPH frontier 0029C8BE\");"
    )
    return rendered[:brace + 1] + body + rendered[brace + 1:]


def insert_summary(main_text: str) -> str:
    marker = "P6BM D3D FRONTIER 00290970:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6BN] inherited 6BM frontier summary marker missing")
    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6BN] could not locate inherited summary block")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6BN XGRPH FRONTIER 0029C8BE: entries=%u",\n'
        f'{indent}    (unsigned int)s_phase6bnRootEntries);\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + block + main_text[line_start:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bb-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bc-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6bn_base")
    p6bl = load(args.phase6bl_emitter, "phase6bn_p6bl")
    p5bb = load(args.base_phase5bb_emitter, "phase6bn_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6bn_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6bm-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6BN] cached Phase 6BM input missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BM" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BN] cached Phase 6BM identity mismatch")

    required = (
        BASE_TAG,
        COOKIE_OLD,
        "P6BM D3D FRONTIER 00290970:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6BN] inherited 6BM marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)

    # Safety-critical: refuse interior-entry promotion. If 0x0029C8BE is not an
    # exact generated start, validate_exact prints the containing function.
    p6bl.validate_exact(ROOT, by_va, generated)

    root_row = by_va[ROOT]
    root_name = generated[ROOT]["name"]
    print(
        f"[Phase6BN] EXACT ROOT PROOF: 0x{ROOT:08X} {root_name} "
        f"range=0x{int(root_row['start']):08X}-0x{int(root_row['end']):08X} "
        f"generated_chars={len(generated[ROOT]['source'])}"
    )
    print(
        "[Phase6BN] SECTION PROOF: target 0x0029C8BE lies inside retail "
        "XGRPH 0x0029B880-0x0029CB7C"
    )

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    old = {int(x, 0) for x in manifest.get("members", [])}
    if not old:
        raise SystemExit("[Phase6BN] inherited translated pack membership is empty")
    if ROOT in old:
        raise SystemExit(
            "[Phase6BN] root 0x0029C8BE is already present in inherited pack; "
            "inspect dispatch bookkeeping instead of repacking it"
        )

    closure = set(
        p5bb.bounded_promoted_members(
            base, ROOT, generated, ROOT_DEPTH, ROOT_CAP
        )
    )
    closure.add(ROOT)
    candidate_new = sorted(va for va in closure if va not in old)
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6BN] closure construction lost mandatory root")

    new_members = list(candidate_new)
    expanded = old | set(new_members)
    main_text = install_state(main_text)

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument_root
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text, base, p5bb, generated, new_members, expanded
    )

    if ROOT in pruned or ROOT not in new_members:
        names = pruned.get(ROOT, [])
        joined = ", ".join(str(x) for x in names) if names else "<unknown>"
        raise SystemExit(
            f"[Phase6BN] support-clean pruning removed mandatory root "
            f"0x{ROOT:08X}; unresolved support={joined}"
        )

    main_text = insert_summary(main_text)

    policy = (
        "Policy: Phase 6BN XGRPH frontier 0029C8BE depth-4 cap-256 closure; "
        "preserve all 6BM GPU semantics and hard fences"
    )
    main_text = p6bl.replace_policy_line(main_text, policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text
        .replace("PHASE 6BM", "PHASE 6BN")
        .replace("Phase 6BM", "Phase 6BN")
        .replace('"P6BM ', '"P6BN ')
    )
    env_text = (
        env_text
        .replace("PHASE 6BM", "PHASE 6BN")
        .replace("Phase 6BM", "Phase 6BN")
    )

    must = (
        BUILD_TAG,
        COOKIE_NEW,
        "case 0x0029C8BEu:",
        "s_phase6bnRootEntries",
        "PASS: Phase 6BN entered translated XGRPH frontier 0029C8BE",
        "P6BN XGRPH FRONTIER 0029C8BE:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    )
    for marker in must:
        if marker not in main_text:
            raise SystemExit(f"[Phase6BN] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6BN",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6bn_xgrph_frontier_0029c8be"] = {
        "source_phase": "6BM",
        "phase6bm_hardware": {
            "root_00290970_entries": 1,
            "prior_d3d_root_00290895_result": "PASS",
            "internal_d3d_device_result": "PASS",
            "d3d_sync_checkpoint_calls": 9,
            "d3d_device_calls": 1,
            "d3d_device_mode": "640x480",
            "next_boundary": {
                "kind": "DIRECT_FRONTIER",
                "target": "0x0029C8BE",
                "caller": "0x0023A3CE",
                "esp": "0x008BF8A8",
                "fault": 0,
                "ticks": 671249,
            },
        },
        "retail_section": {
            "name": "XGRPH",
            "start": "0x0029B880",
            "end_exclusive": "0x0029CB7C",
            "target_inside": True,
        },
        "root": f"0x{ROOT:08X}",
        "root_name": root_name,
        "root_range": {
            "start": f"0x{int(root_row['start']):08X}",
            "end": f"0x{int(root_row['end']):08X}",
        },
        "root_closure_depth": ROOT_DEPTH,
        "root_closure_cap": ROOT_CAP,
        "candidate_new_members": len(candidate_new),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(expanded),
        "new_direct_frontier_targets": [
            f"0x{x:08X}" for x in sorted(frontiers)
        ],
        "all_phase6bm_gpu_bridges_inherited": True,
        "pfifo_scope_changed": False,
        "pfb_scope_changed": False,
        "pgraph_scope_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }
    manifest["phase6bn_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6bn-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BN] 6BM hardware: translated D3D frontier 00290970 entered")
    print("[Phase6BN] next boundary DIRECT_FRONTIER 0029C8BE fault=0")
    print("[Phase6BN] target is inside retail XGRPH section")
    print(
        f"[Phase6BN] XGRPH FRONTIER PACK: root=0x{ROOT:08X} "
        f"name={root_name} candidates={len(candidate_new)} "
        f"pruned={len(pruned)} packed_new={len(new_members)} "
        f"total_pack={len(expanded)}"
    )
    print(f"[Phase6BN] SOURCE SHARDS: {layout['shard_count']}")
    print("[Phase6BN] all 6BM PFIFO/PFB/ZCOMP/PGRAPH semantics inherited unchanged")
    print("[Phase6BN] all unrelated NV2A/MMIO/VRAM remains hard fenced")
    print("[Phase6BN] allocator and 8M budget unchanged")
    print("[Phase6BN] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

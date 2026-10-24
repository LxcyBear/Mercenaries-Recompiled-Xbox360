#!/usr/bin/env python3
"""Phase 6BM: cross the clean post-6BL D3D DIRECT_FRONTIER 0x00290970.

6BL hardware proved that the bounded 0x0028B180 closure entered, all inherited
GPU bridge semantics stayed coherent, and execution advanced to exact generated
function start 0x00290970 with fault=0. This phase adds a bounded depth-4,
cap-256 support-clean closure rooted at 0x00290970. It does not widen PFIFO,
PFB, PGRAPH, MMIO, VRAM or allocator behavior.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BL-D3D-FRONTIER-0028B180-20261024-A"
BUILD_TAG = "P6BM-D3D-FRONTIER-00290970-20261024-A"
ROOT = 0x00290970
ROOT_DEPTH = 4
ROOT_CAP = 256
COOKIE_OLD = "phase6bl_env_build_cookie"
COOKIE_NEW = "phase6bm_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BM] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BM] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def install_state(main_text: str) -> str:
    marker = "static DWORD s_phase6blRootEntries = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6BM] inherited 6BL root-state anchor missing")
    return main_text.replace(
        marker,
        marker + "static DWORD s_phase6bmRootEntries = 0u;\n",
        1,
    )


def instrument_root(rendered: str, name: str) -> str:
    pos = rendered.find(name)
    brace = rendered.find("{", pos)
    if pos < 0 or brace < 0:
        raise SystemExit("[Phase6BM] could not instrument root 0x00290970")
    body = (
        "\n    ++s_phase6bmRootEntries;"
        "\n    trace(\"PASS: Phase 6BM entered translated D3D frontier 00290970\");"
    )
    return rendered[:brace + 1] + body + rendered[brace + 1:]


def insert_summary(main_text: str) -> str:
    marker = "P6BL D3D FRONTIER 0028B180:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6BM] inherited 6BL frontier summary marker missing")
    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6BM] could not locate inherited summary block")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6BM D3D FRONTIER 00290970: entries=%u",\n'
        f'{indent}    (unsigned int)s_phase6bmRootEntries);\n'
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

    base = load(args.base_emitter, "phase6bm_base")
    p6bl = load(args.phase6bl_emitter, "phase6bm_p6bl")
    p5bb = load(args.base_phase5bb_emitter, "phase6bm_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6bm_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6bl-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6BM] cached Phase 6BL input missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BL" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BM] cached Phase 6BL identity mismatch")

    required = (
        BASE_TAG,
        COOKIE_OLD,
        "P6BL D3D FRONTIER 0028B180:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6BM] inherited 6BL marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    p6bl.validate_exact(ROOT, by_va, generated)

    root_row = by_va[ROOT]
    root_name = generated[ROOT]["name"]
    print(
        f"[Phase6BM] EXACT ROOT PROOF: 0x{ROOT:08X} {root_name} "
        f"range=0x{int(root_row['start']):08X}-0x{int(root_row['end']):08X} "
        f"generated_chars={len(generated[ROOT]['source'])}"
    )

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    old = {int(x, 0) for x in manifest.get("members", [])}
    if not old:
        raise SystemExit("[Phase6BM] inherited translated pack membership is empty")
    if ROOT in old:
        raise SystemExit(
            "[Phase6BM] root 0x00290970 is already present in inherited pack; "
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
        raise SystemExit("[Phase6BM] closure construction lost mandatory root")

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
            f"[Phase6BM] support-clean pruning removed mandatory root "
            f"0x{ROOT:08X}; unresolved support={joined}"
        )

    main_text = insert_summary(main_text)

    policy = (
        "Policy: Phase 6BM D3D frontier 00290970 depth-4 cap-256 closure; "
        "preserve all 6BL GPU semantics and hard fences"
    )
    main_text = p6bl.replace_policy_line(main_text, policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text
        .replace("PHASE 6BL", "PHASE 6BM")
        .replace("Phase 6BL", "Phase 6BM")
        .replace('"P6BL ', '"P6BM ')
    )
    env_text = (
        env_text
        .replace("PHASE 6BL", "PHASE 6BM")
        .replace("Phase 6BL", "Phase 6BM")
    )

    must = (
        BUILD_TAG,
        COOKIE_NEW,
        "case 0x00290970u:",
        "s_phase6bmRootEntries",
        "PASS: Phase 6BM entered translated D3D frontier 00290970",
        "P6BM D3D FRONTIER 00290970:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    )
    for marker in must:
        if marker not in main_text:
            raise SystemExit(f"[Phase6BM] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6BM",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6bm_d3d_frontier_00290970"] = {
        "source_phase": "6BL",
        "phase6bl_hardware": {
            "root_0028b180_entries": 1,
            "prior_d3d_root_00290895_result": "PASS",
            "internal_d3d_device_result": "PASS",
            "d3d_sync_checkpoint_calls": 9,
            "d3d_device_calls": 1,
            "d3d_device_mode": "640x480",
            "next_boundary": {
                "kind": "DIRECT_FRONTIER",
                "target": "0x00290970",
                "observed_caller_trace": "0x0023A3CE",
                "esp": "0x008BF8F0",
                "fault": 0,
                "ticks": 671232,
            },
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
        "all_phase6bl_gpu_bridges_inherited": True,
        "pfifo_scope_changed": False,
        "pfb_scope_changed": False,
        "pgraph_scope_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }
    manifest["phase6bm_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6bm-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BM] 6BL hardware: translated D3D frontier 0028B180 entered")
    print("[Phase6BM] next boundary DIRECT_FRONTIER 00290970 fault=0")
    print(
        f"[Phase6BM] D3D FRONTIER PACK: root=0x{ROOT:08X} "
        f"name={root_name} candidates={len(candidate_new)} "
        f"pruned={len(pruned)} packed_new={len(new_members)} "
        f"total_pack={len(expanded)}"
    )
    print(f"[Phase6BM] SOURCE SHARDS: {layout['shard_count']}")
    print("[Phase6BM] all 6BL PFIFO/PFB/ZCOMP/PGRAPH semantics inherited unchanged")
    print("[Phase6BM] all unrelated NV2A/MMIO/VRAM remains hard fenced")
    print("[Phase6BM] allocator and 8M budget unchanged")
    print("[Phase6BM] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

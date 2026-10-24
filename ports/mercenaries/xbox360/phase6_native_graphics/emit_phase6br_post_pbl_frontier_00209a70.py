#!/usr/bin/env python3
"""Phase 6BR: cross the clean post-PBL DIRECT_FRONTIER 0x00209A70.

6BQ hardware proved both caller-local ABI repairs, completed the native
NtQueryVolumeInformationFile continuation, advanced the maintained PBL
checkpoint through phases 1 and 2, and then reached a fault-free direct
frontier at 0x00209A70 from caller 0x0023A3CE.

This stage changes no ABI repair, GPU/MMIO/VRAM policy, allocator geometry, or
execution budget. Exact-start proof against functions.json + generated code is
mandatory; only an exact generated start receives a bounded depth-4, cap-256
support-clean translated closure.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BQ-VOLUME-A3CE-FRAME-REPAIR-20261024-A"
BUILD_TAG = "P6BR-POST-PBL-FRONTIER-00209A70-20261024-A"
ROOT = 0x00209A70
ROOT_DEPTH = 4
ROOT_CAP = 256
COOKIE_OLD = "phase6bq_env_build_cookie"
COOKIE_NEW = "phase6br_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BR] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BR] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def install_state(main_text: str) -> str:
    marker = "static DWORD s_phase6boRootEntries = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6BR] inherited post-XGRPH root-state anchor missing")
    return main_text.replace(
        marker,
        marker + "static DWORD s_phase6brRootEntries = 0u;\n",
        1,
    )


def instrument_root(rendered: str, name: str) -> str:
    pos = rendered.find(name)
    brace = rendered.find("{", pos)
    if pos < 0 or brace < 0:
        raise SystemExit("[Phase6BR] could not instrument root 0x00209A70")
    body = (
        "\n    ++s_phase6brRootEntries;"
        "\n    trace(\"PASS: Phase 6BR entered translated post-PBL frontier 00209A70\");"
    )
    return rendered[: brace + 1] + body + rendered[brace + 1 :]


def insert_summary(main_text: str) -> str:
    marker = "P6BQ POST-XGRPH FRONTIER 00209810:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6BR] inherited 6BQ post-XGRPH summary marker missing")
    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6BR] could not locate inherited summary block")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6BR POST-PBL FRONTIER 00209A70: entries=%u",\n'
        f'{indent}    (unsigned int)s_phase6brRootEntries);\n'
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

    base = load(args.base_emitter, "phase6br_base")
    p6bl = load(args.phase6bl_emitter, "phase6br_p6bl")
    p5bb = load(args.base_phase5bb_emitter, "phase6br_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6br_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6bq-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6BR] cached Phase 6BQ input missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BQ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BR] cached Phase 6BQ identity mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6BQ POST-XGRPH FRONTIER 00209810:",
        "P6BQ PBL CHECKPOINT:",
        "NtQueryVolumeInformationFile SAVEDESP REPAIR PROBE:",
        "RtlInitAnsiString SAVEDESP REPAIR PROBE:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BR] inherited 6BQ marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    p6bl.validate_exact(ROOT, by_va, generated)

    root_row = by_va[ROOT]
    root_name = generated[ROOT]["name"]
    print(
        f"[Phase6BR] EXACT ROOT PROOF: 0x{ROOT:08X} {root_name} "
        f"range=0x{int(root_row['start']):08X}-0x{int(root_row['end']):08X} "
        f"generated_chars={len(generated[ROOT]['source'])}"
    )
    print(
        "[Phase6BR] SECTION PROOF: target 0x00209A70 lies inside retail .text "
        "0x00011000-0x0025561C"
    )

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    old = {int(x, 0) for x in manifest.get("members", [])}
    if not old:
        raise SystemExit("[Phase6BR] inherited translated pack membership is empty")
    if ROOT in old:
        raise SystemExit(
            "[Phase6BR] root 0x00209A70 is already present in inherited pack; "
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
        raise SystemExit("[Phase6BR] closure construction lost mandatory root")

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
            f"[Phase6BR] support-clean pruning removed mandatory root "
            f"0x{ROOT:08X}; unresolved support={joined}"
        )

    expanded = old | set(new_members)
    main_text = insert_summary(main_text)

    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6BR post-PBL .text frontier 00209A70 depth-4 cap-256 closure; preserve both 6BQ ABI repairs and all GPU semantics/hard fences",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6BQ", "PHASE 6BR")
        .replace("Phase 6BQ", "Phase 6BR")
        .replace('"P6BQ ', '"P6BR ')
    )
    env_text = (
        env_text.replace("PHASE 6BQ", "PHASE 6BR")
        .replace("Phase 6BQ", "Phase 6BR")
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "case 0x00209A70u:",
        "s_phase6brRootEntries",
        "PASS: Phase 6BR entered translated post-PBL frontier 00209A70",
        "P6BR POST-PBL FRONTIER 00209A70:",
        "P6BR POST-XGRPH FRONTIER 00209810:",
        "P6BR PBL CHECKPOINT:",
        "NtQueryVolumeInformationFile SAVEDESP REPAIR PROBE:",
        "RtlInitAnsiString SAVEDESP REPAIR PROBE:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BR] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6BR",
            "build_tag": BUILD_TAG,
            "pack_members": len(expanded),
            "members": [f"0x{x:08X}" for x in sorted(expanded)],
        }
    )
    manifest["phase6br_post_pbl_frontier_00209a70"] = {
        "source_phase": "6BQ",
        "phase6bq_hardware": {
            "volume_a3ce_frame_repair": "PASS",
            "volume_query_calls": 3,
            "pbl_checkpoint_calls": 2,
            "pbl_checkpoint_phase1": 1,
            "pbl_checkpoint_phase2": 1,
            "post_xgrph_root_00209810_entries": 1,
            "prior_d3d_root_00290895_result": "PASS",
            "internal_d3d_device_result": "PASS",
            "d3d_sync_checkpoint_calls": 9,
            "next_boundary": {
                "kind": "DIRECT_FRONTIER",
                "target": "0x00209A70",
                "caller": "0x0023A3CE",
                "esp": "0x008BF908",
                "fault": 0,
                "ticks": 689243,
            },
        },
        "retail_section": {
            "name": ".text",
            "start": "0x00011000",
            "end_exclusive": "0x0025561C",
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
        "all_phase6bq_abi_repairs_inherited": True,
        "all_phase6bq_gpu_bridges_inherited": True,
        "pfifo_scope_changed": False,
        "pfb_scope_changed": False,
        "pgraph_scope_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }
    manifest["phase6br_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6br-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BR] 6BQ hardware: ordinal-218 A3CE frame repair PASS")
    print("[Phase6BR] 6BQ hardware: PBL checkpoint phase1=1 phase2=1")
    print("[Phase6BR] next boundary DIRECT_FRONTIER 00209A70 fault=0")
    print(
        f"[Phase6BR] POST-PBL PACK: root=0x{ROOT:08X} name={root_name} "
        f"candidates={len(candidate_new)} pruned={len(pruned)} "
        f"packed_new={len(new_members)} total_pack={len(expanded)}"
    )
    print(f"[Phase6BR] SOURCE SHARDS: {layout['shard_count']}")
    print("[Phase6BR] both 6BQ ABI repairs inherited unchanged")
    print("[Phase6BR] all 6BQ GPU semantics, allocator geometry and 8M budget inherited unchanged")
    print("[Phase6BR] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

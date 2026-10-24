#!/usr/bin/env python3
"""Phase 6BL: cross the clean post-D3D DIRECT_FRONTIER at 0x0028B180.

6BK hardware proved:
  * the later PFIFO DMA_PUSH zero clear at FD003220 completed;
  * the retail D3D root 0x00290895 now reports PASS;
  * internal D3D device publication, D3D sync checkpoints and the 640x480
    device summary all report PASS;
  * execution then reaches a clean DIRECT_FRONTIER target 0x0028B180 with
    fault=0, after leaving the prior NV2A/MMIO choke point.

This phase preserves every 6BK graphics semantic bridge and hard fence, then
packs a bounded support-clean translated closure rooted at exact generated
function start 0x0028B180.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BK-PFIFO-DMA-PUSH-CLEAR-20261024-A"
BUILD_TAG = "P6BL-D3D-FRONTIER-0028B180-20261024-A"
ROOT = 0x0028B180
ROOT_DEPTH = 4
ROOT_CAP = 256
SHARD_TARGET_CHARS = 750000
COOKIE_OLD = "phase6bk_env_build_cookie"
COOKIE_NEW = "phase6bl_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BL] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BL] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6BL] runtime Policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6BL] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return text[:line_start] + indent + 'trace("' + policy + '");' + text[line_end:]


def validate_exact(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        hit = [
            r for r in by_va.values()
            if int(r["start"]) < root < int(r["end"])
        ]
        if hit:
            row = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6BL] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. Refusing interior entry."
            )
        raise SystemExit(
            f"[Phase6BL] target 0x{root:08X} is absent from function inventory"
        )
    if root not in generated:
        raise SystemExit(
            f"[Phase6BL] target 0x{root:08X} is exact function "
            f"{by_va[root]['name']} but has no generated translated body"
        )


def install_state(main_text: str) -> str:
    marker = "static DWORD s_phase6auRootEntries = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6BL] inherited Phase 6AU root-state anchor missing")
    return main_text.replace(
        marker,
        marker + "static DWORD s_phase6blRootEntries = 0u;\n",
        1,
    )


def instrument_root(rendered: str, name: str) -> str:
    pos = rendered.find(name)
    brace = rendered.find("{", pos)
    if pos < 0 or brace < 0:
        raise SystemExit("[Phase6BL] could not instrument root 0x0028B180")
    body = (
        "\n    ++s_phase6blRootEntries;"
        "\n    trace(\"PASS: Phase 6BL entered translated D3D frontier 0028B180\");"
    )
    return rendered[:brace + 1] + body + rendered[brace + 1:]


def insert_summary(main_text: str) -> str:
    marker = "P6BK D3D FRONTIER 00292586:"
    pos = main_text.find(marker)
    if pos < 0:
        # The global phase rename may already have changed the text in future reuse.
        marker = "P6BL D3D FRONTIER 00292586:"
        pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6BL] inherited D3D frontier summary marker missing")
    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6BL] could not locate summary insertion point")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6BL D3D FRONTIER 0028B180: entries=%u",\n'
        f'{indent}    (unsigned int)s_phase6blRootEntries);\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + block + main_text[line_start:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6BL] optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6BL] optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6BL] translated body contains no functions")

    ends = []
    for match in matches:
        brace = masked.find("{", match.start(), match.end())
        if brace < 0:
            raise SystemExit("[Phase6BL] translated function opening brace missing")
        ends.append(base.closing_brace(masked, brace))

    cuts = []
    chunk_start = 0
    last_end = 0
    for end in ends:
        last_end = end
        if end - chunk_start >= SHARD_TARGET_CHARS:
            cuts.append(end)
            chunk_start = end
    if last_end < len(body):
        last_end = len(body)
    if not cuts or cuts[-1] != last_end:
        cuts.append(last_end)

    shard_dir = out_dir / "translated_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale in shard_dir.glob("*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cuts):
        if end <= start:
            continue
        name = f"phase6bl_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({
            "name": name,
            "chars": len(payload),
            "lines": payload.count("\n") + 1,
        })
        start = end

    if start != len(body):
        raise SystemExit("[Phase6BL] shard writer did not consume translated body")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n' for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]
    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8")
        for row in shards
    )
    if reconstructed != body:
        raise SystemExit("[Phase6BL] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6bl_",
        "shard_count": len(shards),
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

    base = load(args.base_emitter, "phase6bl_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6bl_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6bl_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6bk-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6BL] cached Phase 6BK input missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BK" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BL] cached Phase 6BK identity mismatch")

    required = (
        BASE_TAG,
        COOKIE_OLD,
        "P6BK PFIFO WRITE32 addr=FD003220",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6BL] inherited 6BK marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact(ROOT, by_va, generated)

    root_row = by_va[ROOT]
    root_name = generated[ROOT]["name"]
    print(
        f"[Phase6BL] EXACT ROOT PROOF: 0x{ROOT:08X} {root_name} "
        f"range=0x{int(root_row['start']):08X}-0x{int(root_row['end']):08X} "
        f"generated_chars={len(generated[ROOT]['source'])}"
    )

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    old = {int(x, 0) for x in manifest.get("members", [])}
    if not old:
        raise SystemExit("[Phase6BL] inherited translated pack membership is empty")
    if ROOT in old:
        raise SystemExit(
            "[Phase6BL] root 0x0028B180 is already present in inherited pack; "
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
        raise SystemExit("[Phase6BL] closure construction lost mandatory root")

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
            f"[Phase6BL] support-clean pruning removed mandatory root "
            f"0x{ROOT:08X}; unresolved support={joined}"
        )

    main_text = insert_summary(main_text)

    policy = (
        "Policy: Phase 6BL D3D frontier 0028B180 depth-4 cap-256 closure; "
        "preserve all 6BK GPU semantics and hard fences"
    )
    main_text = replace_policy_line(main_text, policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text
        .replace("PHASE 6BK", "PHASE 6BL")
        .replace("Phase 6BK", "Phase 6BL")
        .replace('"P6BK ', '"P6BL ')
    )
    env_text = (
        env_text
        .replace("PHASE 6BK", "PHASE 6BL")
        .replace("Phase 6BK", "Phase 6BL")
    )

    must = (
        BUILD_TAG,
        COOKIE_NEW,
        "case 0x0028B180u:",
        "s_phase6blRootEntries",
        "PASS: Phase 6BL entered translated D3D frontier 0028B180",
        "P6BL D3D FRONTIER 0028B180:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    )
    for marker in must:
        if marker not in main_text:
            raise SystemExit(f"[Phase6BL] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6BL",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6bl_d3d_frontier_0028b180"] = {
        "source_phase": "6BK",
        "phase6bk_hardware": {
            "later_pfifo_zero_clear_pass": True,
            "prior_d3d_root_00290895_result": "PASS",
            "internal_d3d_device_result": "PASS",
            "d3d_sync_checkpoint_calls": 9,
            "d3d_device_calls": 1,
            "d3d_device_mode": "640x480",
            "next_boundary": {
                "kind": "DIRECT_FRONTIER",
                "target": "0x0028B180",
                "observed_caller_trace": "0x0023A3CE",
                "esp": "0x008BF908",
                "fault": 0,
                "ticks": 671223,
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
        "all_phase6bk_gpu_bridges_inherited": True,
        "pfifo_scope_changed": False,
        "pfb_scope_changed": False,
        "pgraph_scope_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }
    manifest["phase6bl_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6bl-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BL] 6BK hardware: old NV2A choke point fully crossed")
    print("[Phase6BL] 6BK hardware: D3D root/internal-device/sync summaries PASS")
    print("[Phase6BL] next boundary DIRECT_FRONTIER 0028B180 fault=0")
    print(
        f"[Phase6BL] D3D FRONTIER PACK: root=0x{ROOT:08X} "
        f"name={root_name} candidates={len(candidate_new)} "
        f"pruned={len(pruned)} packed_new={len(new_members)} "
        f"total_pack={len(expanded)}"
    )
    print(f"[Phase6BL] SOURCE SHARDS: {layout['shard_count']}")
    print("[Phase6BL] all 6BK PFIFO/PFB/ZCOMP/PGRAPH semantics inherited unchanged")
    print("[Phase6BL] all unrelated NV2A/MMIO/VRAM remains hard fenced")
    print("[Phase6BL] allocator and 8M budget unchanged")
    print("[Phase6BL] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

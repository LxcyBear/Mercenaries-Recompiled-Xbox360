#!/usr/bin/env python3
"""Phase 6X: graphics-pool DIRECT_FRONTIER 0x0020F9C0 over proven Phase 6W.

Phase 6W crossed the previously support-pruned 0x0017FE90 root and reached:
    caller 0x0023A3CE -> target 0x0020F9C0
    ticks=670776, trace=179920, fault=0
    summary direct=1812, icall=9075

Upstream Mercenaries-Recompiled specifically exercises sub_0020F9C0 as the
retail graphics-pool initializer. Its optional extended-graphics-memory patches
touch 0x0020F9C0/0x0020F9D3 and require no host helper at that guest site.

6X keeps the exact Phase-6W timing-helper support, 2M execution budget, 32 MiB
title heap, native Xenos surface, and every NV2A/platform/ABI/guest-fault hard
stop. It validates 0x0020F9C0 as an exact generated function start and packs a
bounded depth-4/cap-256 support-clean closure rooted there.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BUILD_TAG = "P6X-GFXPOOL-FRONTIER-0020F9C0-20261023-A"
BASE_TAG = "P6W-DIRECT-FRONTIER-0017FE90-20261023-A"
ROOT = 0x0020F9C0
CALLER = 0x0023A3CE
ROOT_DEPTH = 4
ROOT_CAP = 256
SHARD_TARGET_CHARS = 750000

EXPECTED_ROOT_SUPPORT = {
    "xbox_GetExtendedGraphicsPool",
}


def install_phase6x_graphics_support(main_text: str) -> str:
    """Install the reviewed extended-graphics-pool query before support audit.

    Canonical upstream semantics:
        return g_memory_base && g_extended_graphics_memory ? 0x04000000 : 0;

    This Xbox 360 port deliberately exposes the retail 64 MiB guest layout and
    does not enable the optional PC-only second graphics bank, so the canonical
    disabled-state result is 0. This preserves the original retail graphics-pool
    initialization path at sub_0020F9C0.
    """
    marker = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if marker not in main_text:
        raise SystemExit("[Phase6X] graphics support insertion marker changed")

    support = r"""
/* Phase 6X reviewed graphics-memory support.
 * Canonical upstream:
 *   xbox_GetExtendedGraphicsPool() returns 0x04000000 only when the optional
 *   PC extended graphics bank is enabled and mapped.
 *
 * This Xbox 360 port intentionally keeps the original retail 64 MiB guest
 * layout, so extended graphics memory is disabled and the canonical return is
 * zero. sub_0020F9C0 therefore follows the retail graphics-pool path.
 */
static uint32_t xbox_GetExtendedGraphicsPool(void)
{
    return 0u;
}

"""
    return main_text.replace(marker, support + marker, 1)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6X] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6X] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def validate_exact(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        hit = [r for r in by_va.values() if int(r["start"]) < root < int(r["end"])]
        if hit:
            row = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6X] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "Refusing an interior-entry prologue redirect."
            )
        raise SystemExit(f"[Phase6X] target 0x{root:08X} is absent from function inventory")
    if root not in generated:
        raise SystemExit(
            f"[Phase6X] target 0x{root:08X} is exact function "
            f"{by_va[root]['name']} but has no generated translated body"
        )


def instrument_root(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6X] could not instrument root 0x0020F9C0")
    return rendered[:b + 1] + "\n    s_phase6xRootEntered = 1;" + rendered[b + 1:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6X] translated-body optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6X] translated-body optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6X] translated-body block contains no functions")

    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6X] translated function opening brace missing")
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
    for stale in shard_dir.glob("phase6x_*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cut_points):
        if end <= start:
            continue
        name = f"phase6x_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({"name": name, "chars": len(payload), "lines": payload.count("\n") + 1})
        start = end

    if start != len(body):
        raise SystemExit("[Phase6X] shard writer did not consume full body block")

    include_block = "".join(f'#include "translated_shards/{row["name"]}"\n' for row in shards)
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]
    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join((shard_dir / row["name"]).read_text(encoding="utf-8") for row in shards)
    if reconstructed != body:
        raise SystemExit("[Phase6X] shard reconstruction identity mismatch")

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

    base = load(args.base_emitter, "phase6x_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6x_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6x_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6w-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6X] cached Phase 6W baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6W" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6X] cached Phase 6W baseline identity mismatch")

    for marker in (
        "static double recomp_frame_ticks_with_remainder(double ticks)",
        "static uint32_t recomp_freecam_game_ticks(uint32_t ticks)",
    ):
        if marker not in main_text:
            raise SystemExit("[Phase6X] inherited Phase 6W reviewed timing support is missing")

    inherited_pruned = manifest.get("phase6q_pruned_members", [])
    root_prune = None
    for row in inherited_pruned:
        if str(row.get("address", "")).upper() == f"0X{ROOT:08X}":
            root_prune = row
            break

    if root_prune is None:
        raise SystemExit(
            "[Phase6X] expected inherited 6Q prune record for graphics root "
            "0x0020F9C0, but none was found"
        )

    observed_support = set(str(x) for x in root_prune.get("unresolved_support", []))
    if observed_support != EXPECTED_ROOT_SUPPORT:
        raise SystemExit(
            "[Phase6X] graphics-root support dependency set changed: expected "
            + ", ".join(sorted(EXPECTED_ROOT_SUPPORT))
            + "; observed "
            + (", ".join(sorted(observed_support)) or "<none>")
        )

    print(
        "[Phase6X] REVIEWED GRAPHICS SUPPORT: "
        + ", ".join(sorted(observed_support))
        + " -> retail disabled-state return 0"
    )

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact(ROOT, by_va, generated)
    validate_exact(CALLER, by_va, generated)
    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    # Install reviewed graphics-memory support before Phase5BC snapshots the
    # support symbols, so the normal unresolved-dependency audit validates the
    # root against an actual compiled implementation.
    main_text = install_phase6x_graphics_support(main_text)

    old = {int(x, 0) for x in manifest.get("members", [])}
    if ROOT in old:
        raise SystemExit(
            "[Phase6X] root 0x0020F9C0 is already present in inherited pack; "
            "inspect dispatch bookkeeping instead of repacking it"
        )

    closure = set(p5bb.bounded_promoted_members(base, ROOT, generated, ROOT_DEPTH, ROOT_CAP))
    closure.add(ROOT)
    candidate_new = sorted(va for va in closure if va not in old)
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6X] closure construction lost mandatory root")

    new_members = list(candidate_new)
    expanded = old | set(new_members)

    marker = "static int s_phase6wRootEntered;"
    if marker not in main_text:
        raise SystemExit("[Phase6X] inherited Phase 6W root-state marker changed")
    main_text = main_text.replace(marker, marker + "\nstatic int s_phase6xRootEntered;", 1)

    marker = "    s_phase6wRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6X] inherited Phase 6W reset marker changed")
    main_text = main_text.replace(marker, marker + "    s_phase6xRootEntered = 0;\n", 1)

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument_root
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text, base, p5bb, generated, new_members, expanded
    )

    if ROOT not in new_members:
        names = pruned.get(ROOT, [])
        joined = ", ".join(str(x) for x in names) if names else "<unknown>"
        raise SystemExit(
            f"[Phase6X] support-clean pruning removed mandatory graphics root "
            f"0x{ROOT:08X}; unresolved support = {joined}. "
            "Implement real semantics before continuing."
        )

    main_text = replace_unique(
        main_text, "P6W FRONTIER SUMMARY:", "P6X GFXPOOL SUMMARY:", "Phase 6W summary token"
    )
    main_text = replace_unique(
        main_text, "s_phase6wRootEntered &&", "s_phase6xRootEntered &&", "Phase 6W root result gate"
    )

    if "PHASE 6W DIRECT FRONTIER RESULT" not in main_text:
        raise SystemExit("[Phase6X] inherited Phase 6W result token missing")
    main_text = main_text.replace(
        "PHASE 6W DIRECT FRONTIER RESULT", "PHASE 6X GRAPHICS-POOL FRONTIER RESULT"
    )

    old_policy = (
        "Policy: start from the hardware-proven Phase-6V 2M-budget image, resolve exact "
        "DIRECT_FRONTIER 0023A3CE -> 0017FE90 with a bounded depth-4/cap-256 generated closure, "
        "retain the 32 MiB heap plus proven cos()/sin() CRT support, and hard-stop on "
        "unresolved support/NV2A/platform/ABI/guest-fault boundaries"
    )
    new_policy = (
        "Policy: start from hardware-proven Phase-6W, resolve graphics-pool DIRECT_FRONTIER "
        "0023A3CE -> 0020F9C0 with a bounded depth-4/cap-256 generated closure, retain reviewed "
        "frame/freecam timing support plus the 32 MiB heap and 2M budget, and hard-stop on "
        "unresolved support/NV2A/platform/ABI/guest-fault boundaries"
    )
    main_text = replace_unique(main_text, old_policy, new_policy, "Phase 6W runtime policy")

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "Phase 6W build tag")
    main_text = main_text.replace("phase6w_env_build_cookie", "phase6x_env_build_cookie")
    env_text = env_text.replace("phase6w_env_build_cookie", "phase6x_env_build_cookie")
    main_text = main_text.replace("50365757", "50365858")
    env_text = env_text.replace("50365757", "50365858")

    main_text = (
        main_text
        .replace("PHASE 6W", "PHASE 6X")
        .replace("Phase 6W", "Phase 6X")
        .replace('"P6W ', '"P6X ')
    )
    env_text = env_text.replace("PHASE 6W", "PHASE 6X").replace("Phase 6W", "Phase 6X")

    required = (
        BUILD_TAG,
        "case 0x0020F9C0u:",
        "s_phase6xRootEntered = 1;",
        "P6X XENOS: PASS Direct3D_CreateDevice",
        "P6X FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6X FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "P6X GFXPOOL SUMMARY:",
        "PHASE 6X GRAPHICS-POOL FRONTIER RESULT",
        "#define PHASE4C_EXEC_BUDGET 2000000u",
        "#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)",
        "static double recomp_frame_ticks_with_remainder(double ticks)",
        "static uint32_t recomp_freecam_game_ticks(uint32_t ticks)",
        "static uint32_t xbox_GetExtendedGraphicsPool(void)",
    )
    for item in required:
        if item not in main_text:
            raise SystemExit(f"[Phase6X] generated main lost marker: {item}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6X",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6x_graphics_pool_frontier"] = {
        "source_phase": "6W",
        "phase6w_hardware_pass": True,
        "phase6w_observed_boundary": {
            "kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x0020F9C0",
            "esp": "0x008BFA14",
            "saved_esp": "0x008BFA14",
            "fault": 0,
            "ticks": 670776,
            "trace": 179920,
            "direct_dispatches": 1812,
            "last_direct": "0x001F66C0",
            "icall_dispatches": 9075,
            "last_icall": "0x00209720",
        },
        "large_heap_request_still_succeeds": {
            "requested_bytes": 19503520,
            "result": "0x008C2980",
        },
        "upstream_context": {
            "role": "retail graphics-pool initialization root",
            "extended_graphics_patch_sites": ["0x0020F9C0", "0x0020F9D3"],
            "patch_site_host_helpers": [],
        },
        "execution_budget_inherited": 2000000,
        "title_heap_end_inherited": "0x028C0000",
        "reviewed_phase6w_timing_support_inherited": True,
        "reviewed_graphics_support": {
            "xbox_GetExtendedGraphicsPool": (
                "canonical disabled-state semantics for retail 64 MiB guest layout; returns 0"
            ),
        },
        "root": f"0x{ROOT:08X}",
        "root_name": generated[ROOT]["name"],
        "frontier_caller": f"0x{CALLER:08X}",
        "root_closure_depth": ROOT_DEPTH,
        "root_closure_cap": ROOT_CAP,
        "candidate_new_members": len(candidate_new),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(expanded),
        "new_direct_frontier_targets": [f"0x{x:08X}" for x in sorted(frontiers)],
        "source_layout": source_layout,
        "runtime_policy": (
            "exact generated graphics-pool root/closure only; inherited reviewed timing support; "
            "reviewed canonical disabled-state xbox_GetExtendedGraphicsPool support; "
            "support-clean pruning authoritative; no unknown helper stubs; "
            "NV2A/platform/ABI/guest-fault remain hard stops"
        ),
    }
    manifest["phase6x_pruned_members"] = [
        {"address": f"0x{va:08X}", "name": generated[va]["name"], "unresolved_support": names}
        for va, names in sorted(pruned.items())
    ]
    (args.out_dir / "phase6x-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(
        f"[Phase6X] GRAPHICS-POOL FRONTIER PACK: root=0x{ROOT:08X} "
        f"name={generated[ROOT]['name']} candidates={len(candidate_new)} "
        f"pruned={len(pruned)} packed_new={len(new_members)} total_pack={len(expanded)}"
    )
    print(
        f"[Phase6X] SOURCE SHARDS: wrapper_lines={source_layout['wrapper_lines']} "
        f"translated_body_lines={source_layout['body_lines']} shards={source_layout['shard_count']}"
    )
    print("[Phase6X] UPSTREAM CONTEXT: 0020F9C0 is retail graphics-pool initialization")
    print("[Phase6X] EXECUTION BUDGET: inherited 2000000 ticks")
    print("[Phase6X] TITLE HEAP: inherited 32 MiB")
    print("[Phase6X] REVIEWED PHASE 6W TIMING SUPPORT: inherited unchanged")
    print("[Phase6X] REVIEWED GRAPHICS SUPPORT: xbox_GetExtendedGraphicsPool -> 0 (retail mode)")
    print("[Phase6X] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

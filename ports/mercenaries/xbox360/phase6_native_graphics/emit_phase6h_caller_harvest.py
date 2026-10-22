#!/usr/bin/env python3
"""Phase 6H: cached caller-closure frontier harvester.

Phase 6G proved the symmetric harvester on hardware:
  0x00150E20 -> packed
  0x00153080 -> packed
  next DIRECT_FRONTIER: 0x00015B30, fault=0

All recent direct frontiers still originate at caller 0x0023A3CE. Instead of
guessing the next neighborhood, Phase 6H harvests exact generated direct-call
targets from that caller itself, adds its bounded closure, then adds the new
frontier root's closure and a local reserve.

Unlike 6B..6G, 6H consumes the already-generated Phase 6G output directory as
a frozen local baseline. It does not recursively regenerate the full Phase-5/
Phase-6 ancestry. Unknown support remains pruned; NV2A/platform/ABI/guest-fault
and genuinely missing generated bodies remain hard stops.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BUILD_TAG = "P6H-CALLER-HARVEST-00015B30-20261022-A"
ROOT = 0x00015B30
CALLER = 0x0023A3CE
TEXT_START = 0x00011000
TEXT_END = 0x00255620
ROOT_DIRECT_DEPTH = 12
ROOT_DIRECT_CAP = 512
CALLER_CLOSURE_DEPTH = 2
CALLER_CLOSURE_CAP = 2048
LOCAL_RESERVE = 128
TOTAL_NEW_CAP = 1024

CALL_COMMENT_RE = re.compile(r"/\*\s*call\s+0x([0-9A-Fa-f]{8})\s*\*/")

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6H] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def validate(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        hit = [r for r in by_va.values() if int(r["start"]) < root < int(r["end"])]
        if hit:
            r = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6H] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(r['start']):08X}-0x{int(r['end']):08X} {r['name']}"
            )
        raise SystemExit(f"[Phase6H] target 0x{root:08X} is absent from function inventory")
    if root not in generated:
        raise SystemExit(
            f"[Phase6H] target 0x{root:08X} is an exact function start "
            f"({by_va[root]['name']}) but has no generated translated body"
        )

def instrument(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6H] could not instrument root 0x00015B30")
    return rendered[:b + 1] + "\n    s_phase6hRootEntered = 1;" + rendered[b + 1:]

def unique_in_order(values):
    seen = set()
    out = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out

def patch_quiet_dispatch_logging(main_text: str) -> str:
    old_icall = r'''    sprintf(
        line,
        "PASS: Phase 6G broad-sweep ICALL_SAFE caller=%08X target=%08X saved_esp=%08X dispatches=%u",
        (unsigned int)s_phase5bcPackedIcallLastCaller,
        (unsigned int)target,
        (unsigned int)savedEsp,
        (unsigned int)s_phase5bcPackedIcallDispatchCount);
    trace(line);'''

    new_icall = r'''    if (s_phase5bcPackedIcallDispatchCount <= 8u ||
        (s_phase5bcPackedIcallDispatchCount >= 1268u &&
         s_phase5bcPackedIcallDispatchCount <= 1304u) ||
        (s_phase5bcPackedIcallDispatchCount & 0xFFu) == 0u)
    {
        sprintf(
            line,
            "PASS: Phase 6G broad-sweep ICALL_SAFE caller=%08X target=%08X saved_esp=%08X dispatches=%u",
            (unsigned int)s_phase5bcPackedIcallLastCaller,
            (unsigned int)target,
            (unsigned int)savedEsp,
            (unsigned int)s_phase5bcPackedIcallDispatchCount);
        trace(line);
    }'''

    old_direct = r'''        sprintf(
            line,
            "PASS: Phase 6G broad-sweep DIRECT caller=%08X target=%08X dispatches=%u",
            (unsigned int)s_phase5bcPackedDirectLastCaller,
            (unsigned int)target,
            (unsigned int)s_phase5bcPackedDirectDispatchCount);
        trace(line);'''

    new_direct = r'''        if (s_phase5bcPackedDirectDispatchCount <= 8u ||
            (s_phase5bcPackedDirectDispatchCount >= 1008u &&
             s_phase5bcPackedDirectDispatchCount <= 1056u) ||
            (s_phase5bcPackedDirectDispatchCount & 0xFFu) == 0u)
        {
            sprintf(
                line,
                "PASS: Phase 6G broad-sweep DIRECT caller=%08X target=%08X dispatches=%u",
                (unsigned int)s_phase5bcPackedDirectLastCaller,
                (unsigned int)target,
                (unsigned int)s_phase5bcPackedDirectDispatchCount);
            trace(line);
        }'''

    if old_icall not in main_text:
        raise SystemExit("[Phase6H] Phase 6G ICALL logging marker changed")
    if old_direct not in main_text:
        raise SystemExit("[Phase6H] Phase 6G DIRECT logging marker changed")

    main_text = main_text.replace(old_icall, new_icall, 1)
    main_text = main_text.replace(old_direct, new_direct, 1)
    return main_text

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

    base = load(args.base_emitter, "phase6h_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6h_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6h_p5bc")

    base_main = args.base_dir / "main.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6g-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6H] cached Phase 6G baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6G":
        raise SystemExit("[Phase6H] cached baseline manifest is not Phase 6G")
    if manifest.get("build_tag") != "P6G-SIBLING-HARVEST-00150E20-20261022-A":
        raise SystemExit("[Phase6H] cached Phase 6G baseline build tag mismatch")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate(ROOT, by_va, generated)
    validate(CALLER, by_va, generated)

    old = {int(x, 0) for x in manifest.get("members", [])}
    if ROOT in old:
        raise SystemExit("[Phase6H] 0x00015B30 already packed by Phase 6G")

    caller_source = generated[CALLER]["source"]
    caller_targets_all = unique_in_order(
        int(match.group(1), 16)
        for match in CALL_COMMENT_RE.finditer(caller_source)
    )
    caller_targets_generated = [
        va for va in caller_targets_all
        if va in generated
    ]
    caller_targets_unpacked = [
        va for va in caller_targets_generated
        if va not in old
    ]
    caller_targets_ungenerated = [
        va for va in caller_targets_all
        if va not in generated
    ]

    caller_closure = set(
        p5bb.bounded_promoted_members(
            base,
            CALLER,
            generated,
            CALLER_CLOSURE_DEPTH,
            CALLER_CLOSURE_CAP,
        )
    )
    root_closure = set(
        p5bb.bounded_promoted_members(
            base,
            ROOT,
            generated,
            ROOT_DIRECT_DEPTH,
            ROOT_DIRECT_CAP,
        )
    )
    root_closure.add(ROOT)

    local = [
        va for va in generated
        if TEXT_START <= va < TEXT_END and va not in old
    ]
    local.sort(key=lambda va: (abs(va - ROOT), va))

    candidate_order = [ROOT]

    # Highest-value set: exact generated direct targets encoded in the caller
    # that has produced every recent hardware frontier.
    for va in caller_targets_unpacked:
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in candidate_order:
            candidate_order.append(va)

    # Then include the caller's shallow generated closure.
    for va in sorted(caller_closure, key=lambda x: (x != CALLER, abs(x - CALLER), x)):
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in old and va not in candidate_order:
            candidate_order.append(va)

    # Then include the newly observed frontier root's deeper closure.
    for va in sorted(root_closure, key=lambda x: (x != ROOT, abs(x - ROOT), x)):
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in old and va not in candidate_order:
            candidate_order.append(va)

    # Reserve nearby exact generated siblings as insurance for dynamic tables.
    local_added = 0
    for va in local:
        if len(candidate_order) >= TOTAL_NEW_CAP or local_added >= LOCAL_RESERVE:
            break
        if va not in candidate_order:
            candidate_order.append(va)
            local_added += 1

    # Fill any remaining budget by nearest text functions.
    for va in local:
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in candidate_order:
            candidate_order.append(va)

    candidate_order = candidate_order[:TOTAL_NEW_CAP]
    candidate_new = sorted(set(candidate_order))
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6H] candidate batch lost mandatory root 0x00015B30")

    expanded = old | set(candidate_new)
    new_members = list(candidate_new)

    marker = "static int s_phase6gRootEntered;"
    if marker not in main_text:
        raise SystemExit("[Phase6H] Phase 6G root-state marker changed")
    main_text = main_text.replace(marker, marker + "\nstatic int s_phase6hRootEntered;", 1)

    marker = "    s_phase6gRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6H] Phase 6G reset marker changed")
    main_text = main_text.replace(marker, marker + "    s_phase6hRootEntered = 0;\n", 1)

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text,
        base,
        p5bb,
        generated,
        new_members,
        expanded,
    )

    if ROOT not in new_members:
        raise SystemExit("[Phase6H] support-clean pruning removed mandatory root 0x00015B30")

    main_text = patch_quiet_dispatch_logging(main_text)

    old_result = '''    if (s_phase6gRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6G SIBLING HARVEST RESULT: PASS");
    else
        trace("PHASE 6G SIBLING HARVEST RESULT: FAIL");'''

    new_result = '''    {
        char phase6hSummary[256];
        sprintf(
            phase6hSummary,
            "P6H HARVEST SUMMARY: direct=%u last_direct=%08X caller=%08X icall=%u last_icall=%08X icall_caller=%08X",
            (unsigned int)s_phase5bcPackedDirectDispatchCount,
            (unsigned int)s_phase5bcPackedDirectLastTarget,
            (unsigned int)s_phase5bcPackedDirectLastCaller,
            (unsigned int)s_phase5bcPackedIcallDispatchCount,
            (unsigned int)s_phase5bcPackedIcallLastTarget,
            (unsigned int)s_phase5bcPackedIcallLastCaller);
        trace(phase6hSummary);
    }

    if (s_phase6hRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6H CALLER HARVEST RESULT: PASS");
    else
        trace("PHASE 6H CALLER HARVEST RESULT: FAIL");'''

    if old_result not in main_text:
        raise SystemExit("[Phase6H] Phase 6G result gate changed")
    main_text = main_text.replace(old_result, new_result, 1)

    old_policy = (
        "Policy: inherit the hardware-proven Phase-6F runtime/Xenos path, seed exact frontier "
        "00150E20, reserve symmetric nearby translated siblings before static closure expansion, "
        "continue automatically only through exact packed targets, and hard-stop on genuine NV2A/"
        "platform/ABI/guest-fault or missing-body boundaries without fabricating success"
    )
    new_policy = (
        "Policy: start from the frozen hardware-proven Phase-6G generated baseline, seed exact "
        "frontier 00015B30, harvest exact generated direct targets encoded by caller 0023A3CE "
        "plus bounded caller/root closures, continue only through exact packed targets, and "
        "hard-stop on genuine NV2A/platform/ABI/guest-fault or missing-body boundaries"
    )
    if old_policy not in main_text:
        raise SystemExit("[Phase6H] Phase 6G policy marker changed")

    main_text = main_text.replace(
        "P6G-SIBLING-HARVEST-00150E20-20261022-A",
        BUILD_TAG,
        1,
    )
    main_text = main_text.replace(old_policy, new_policy, 1)
    main_text = main_text.replace("phase6g_env_build_cookie", "phase6h_env_build_cookie")
    env_text = env_text.replace("phase6g_env_build_cookie", "phase6h_env_build_cookie")
    main_text = main_text.replace("50364747", "50364848")
    env_text = env_text.replace("50364747", "50364848")
    main_text = main_text.replace("PHASE 6G", "PHASE 6H").replace("Phase 6G", "Phase 6H").replace('"P6G ', '"P6H ')
    env_text = env_text.replace("PHASE 6G", "PHASE 6H").replace("Phase 6G", "Phase 6H")

    required = (
        BUILD_TAG,
        "case 0x00015B30u: return sub_00015B30;",
        "s_phase6hRootEntered = 1;",
        "P6H XENOS: PASS Direct3D_CreateDevice",
        "P6H FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6H FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "P6H HARVEST SUMMARY",
        "PHASE 6H CALLER HARVEST RESULT",
    )
    for item in required:
        if item not in main_text:
            raise SystemExit(f"[Phase6H] generated main lost marker: {item}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6H",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6h_caller_harvest"] = {
        "source_phase": "6G",
        "cached_base": True,
        "phase6g_hardware_pass": True,
        "phase6g_observed_boundary": {
            "kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x00015B30",
            "esp": "0x008BFF18",
            "saved_esp": "0x008BFF18",
            "fault": 0,
            "ticks": 75063,
            "trace": 7455,
            "direct_dispatches_before_boundary": 1015,
            "icall_dispatches_before_boundary": 1273,
            "last_packed_direct": "0x00153080",
        },
        "root": f"0x{ROOT:08X}",
        "root_name": generated[ROOT]["name"],
        "frontier_caller": f"0x{CALLER:08X}",
        "caller_name": generated[CALLER]["name"],
        "caller_direct_targets_total": len(caller_targets_all),
        "caller_direct_targets_generated": len(caller_targets_generated),
        "caller_direct_targets_unpacked": len(caller_targets_unpacked),
        "caller_direct_targets_ungenerated": len(caller_targets_ungenerated),
        "caller_ungenerated_targets": [
            f"0x{x:08X}" for x in caller_targets_ungenerated
        ],
        "caller_closure_depth": CALLER_CLOSURE_DEPTH,
        "caller_closure_cap": CALLER_CLOSURE_CAP,
        "root_closure_depth": ROOT_DIRECT_DEPTH,
        "root_closure_cap": ROOT_DIRECT_CAP,
        "local_reserve": LOCAL_RESERVE,
        "total_new_cap": TOTAL_NEW_CAP,
        "base_pack_members": len(old),
        "candidate_new_members": len(candidate_new),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(expanded),
        "new_direct_frontier_targets": [f"0x{x:08X}" for x in sorted(frontiers)],
        "quiet_dispatch_logging": True,
        "xenos_surface_inherited": True,
        "strategy": (
            "frozen Phase-6G base; mandatory 0x00015B30 root; caller 0x0023A3CE "
            "direct-call targets in source order; caller depth-2 closure; root depth-12 "
            "closure; 128 nearest text siblings; nearest-text fill to 1024 candidates"
        ),
        "runtime_policy": (
            "exact packed DIRECT/ICALL_SAFE targets continue automatically; early proven "
            "dispatch logging is throttled while a dense window around the old frontier "
            "and the final dispatch summary remain visible; NV2A/platform/ABI/guest-fault/"
            "missing-body boundaries remain hard stops"
        ),
    }
    manifest["phase6h_candidate_new_members"] = [f"0x{x:08X}" for x in candidate_new]
    manifest["phase6h_new_members"] = [f"0x{x:08X}" for x in sorted(new_members)]
    manifest["phase6h_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6h-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    total_new_source = sum(len(rendered[va]) for va in new_members)
    print(
        f"[Phase6H] CACHED CALLER HARVEST: base={len(old)} "
        f"caller_targets={len(caller_targets_all)} "
        f"generated={len(caller_targets_generated)} "
        f"unpacked={len(caller_targets_unpacked)} "
        f"ungenerated={len(caller_targets_ungenerated)} "
        f"candidate_new={len(candidate_new)} pruned={len(pruned)} "
        f"packed_new={len(new_members)} total={len(expanded)} "
        f"new_source_bytes={total_new_source}"
    )
    print(
        "[Phase6H] FAST BASE: reused existing Phase 6G generated main/env/manifest; "
        "no recursive Phase-5/6 regeneration"
    )
    print(
        "[Phase6H] CALLER HARVEST: 0x0023A3CE exact generated direct targets are "
        "prioritized ahead of neighborhood guessing"
    )
    print(
        "[Phase6H] QUIET LOG: proven DIRECT/ICALL spam throttled; old-frontier window "
        "and final dispatch summary retained"
    )
    print(
        "[Phase6H] HARD STOP: NV2A/platform/ABI/guest-fault/missing-body boundaries "
        "remain fenced and logged"
    )
    print("[Phase6H] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Phase 6I: cached caller-closure frontier harvester.

Phase 6H hardware PASS reached a new fault-free DIRECT_FRONTIER:
  caller 0x0023A3CE -> target 0x00202680
  fault=0, ticks=93854, trace=8082

6I reuses the already-generated Phase 6H main/env/manifest as a frozen local
baseline. It prioritizes still-unpacked exact generated direct targets encoded
by caller 0x0023A3CE, adds shallow caller closure, adds a deeper closure rooted
at 0x00202680, then fills the remaining budget with nearest exact generated
.text functions. Unknown support is pruned rather than stubbed.

Exact packed DIRECT/ICALL_SAFE targets continue automatically. Genuine NV2A
MMIO/VRAM, unknown platform/kernel/device semantics, ABI/frame failures, guest
faults, and genuinely missing generated bodies remain hard stops.
"""
from __future__ import annotations
import argparse, importlib.util, json, re
from pathlib import Path

BUILD_TAG = "P6I-CALLER-HARVEST-00202680-20261022-A"
ROOT = 0x00202680
CALLER = 0x0023A3CE
TEXT_START = 0x00011000
TEXT_END = 0x00255620
ROOT_DIRECT_DEPTH = 12
ROOT_DIRECT_CAP = 768
CALLER_CLOSURE_DEPTH = 2
CALLER_CLOSURE_CAP = 2048
LOCAL_RESERVE = 192
TOTAL_NEW_CAP = 1024

CALL_COMMENT_RE = re.compile(r"/\*\s*call\s+0x([0-9A-Fa-f]{8})\s*\*/")

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6I] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def validate(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        hit = [r for r in by_va.values() if int(r["start"]) < root < int(r["end"])]
        if hit:
            r = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6I] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(r['start']):08X}-0x{int(r['end']):08X} {r['name']}"
            )
        raise SystemExit(f"[Phase6I] target 0x{root:08X} is absent from function inventory")
    if root not in generated:
        raise SystemExit(
            f"[Phase6I] target 0x{root:08X} is an exact function start "
            f"({by_va[root]['name']}) but has no generated translated body"
        )

def instrument(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6I] could not instrument root 0x00202680")
    return rendered[:b + 1] + "\n    s_phase6iRootEntered = 1;" + rendered[b + 1:]

def unique_in_order(values):
    seen = set()
    out = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out

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

    base = load(args.base_emitter, "phase6i_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6i_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6i_p5bc")

    base_main = args.base_dir / "main.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6h-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6I] cached Phase 6H baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6H":
        raise SystemExit("[Phase6I] cached baseline manifest is not Phase 6H")
    if manifest.get("build_tag") != "P6H-CALLER-HARVEST-00015B30-20261022-A":
        raise SystemExit("[Phase6I] cached Phase 6H baseline build tag mismatch")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate(ROOT, by_va, generated)
    validate(CALLER, by_va, generated)

    old = {int(x, 0) for x in manifest.get("members", [])}
    if ROOT in old:
        raise SystemExit("[Phase6I] 0x00202680 already packed by Phase 6H")

    caller_source = generated[CALLER]["source"]
    caller_targets_all = unique_in_order(
        int(m.group(1), 16) for m in CALL_COMMENT_RE.finditer(caller_source)
    )
    caller_targets_generated = [va for va in caller_targets_all if va in generated]
    caller_targets_unpacked = [va for va in caller_targets_generated if va not in old]
    caller_targets_ungenerated = [va for va in caller_targets_all if va not in generated]

    caller_closure = set(
        p5bb.bounded_promoted_members(
            base, CALLER, generated, CALLER_CLOSURE_DEPTH, CALLER_CLOSURE_CAP
        )
    )
    root_closure = set(
        p5bb.bounded_promoted_members(
            base, ROOT, generated, ROOT_DIRECT_DEPTH, ROOT_DIRECT_CAP
        )
    )
    root_closure.add(ROOT)

    local = [
        va for va in generated
        if TEXT_START <= va < TEXT_END and va not in old
    ]
    local.sort(key=lambda va: (abs(va - ROOT), va))

    candidate_order = [ROOT]

    for va in caller_targets_unpacked:
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in candidate_order:
            candidate_order.append(va)

    for va in sorted(caller_closure, key=lambda x: (x != CALLER, abs(x - CALLER), x)):
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in old and va not in candidate_order:
            candidate_order.append(va)

    for va in sorted(root_closure, key=lambda x: (x != ROOT, abs(x - ROOT), x)):
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in old and va not in candidate_order:
            candidate_order.append(va)

    local_added = 0
    for va in local:
        if len(candidate_order) >= TOTAL_NEW_CAP or local_added >= LOCAL_RESERVE:
            break
        if va not in candidate_order:
            candidate_order.append(va)
            local_added += 1

    for va in local:
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in candidate_order:
            candidate_order.append(va)

    candidate_order = candidate_order[:TOTAL_NEW_CAP]
    candidate_new = sorted(set(candidate_order))
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6I] candidate batch lost mandatory root 0x00202680")

    expanded = old | set(candidate_new)
    new_members = list(candidate_new)

    marker = "static int s_phase6hRootEntered;"
    if marker not in main_text:
        raise SystemExit("[Phase6I] Phase 6H root-state marker changed")
    main_text = main_text.replace(marker, marker + "\nstatic int s_phase6iRootEntered;", 1)

    marker = "    s_phase6hRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6I] Phase 6H reset marker changed")
    main_text = main_text.replace(marker, marker + "    s_phase6iRootEntered = 0;\n", 1)

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text, base, p5bb, generated, new_members, expanded
    )

    if ROOT not in new_members:
        raise SystemExit("[Phase6I] support-clean pruning removed mandatory root 0x00202680")

    old_result = '''    {
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

    new_result = '''    {
        char phase6iSummary[256];
        sprintf(
            phase6iSummary,
            "P6I HARVEST SUMMARY: direct=%u last_direct=%08X caller=%08X icall=%u last_icall=%08X icall_caller=%08X",
            (unsigned int)s_phase5bcPackedDirectDispatchCount,
            (unsigned int)s_phase5bcPackedDirectLastTarget,
            (unsigned int)s_phase5bcPackedDirectLastCaller,
            (unsigned int)s_phase5bcPackedIcallDispatchCount,
            (unsigned int)s_phase5bcPackedIcallLastTarget,
            (unsigned int)s_phase5bcPackedIcallLastCaller);
        trace(phase6iSummary);
    }

    if (s_phase6iRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6I CALLER HARVEST RESULT: PASS");
    else
        trace("PHASE 6I CALLER HARVEST RESULT: FAIL");'''

    if old_result not in main_text:
        raise SystemExit("[Phase6I] Phase 6H result gate changed")
    main_text = main_text.replace(old_result, new_result, 1)

    old_policy = (
        "Policy: start from the frozen hardware-proven Phase-6G generated baseline, seed exact "
        "frontier 00015B30, harvest exact generated direct targets encoded by caller 0023A3CE "
        "plus bounded caller/root closures, continue only through exact packed targets, and "
        "hard-stop on genuine NV2A/platform/ABI/guest-fault or missing-body boundaries"
    )
    new_policy = (
        "Policy: start from the frozen hardware-proven Phase-6H generated baseline, seed exact "
        "frontier 00202680, continue harvesting exact generated targets encoded by caller "
        "0023A3CE plus bounded caller/root closures, and hard-stop on genuine NV2A/platform/"
        "ABI/guest-fault or missing-body boundaries without fabricating success"
    )
    if old_policy not in main_text:
        raise SystemExit("[Phase6I] Phase 6H policy marker changed")

    main_text = main_text.replace(
        "P6H-CALLER-HARVEST-00015B30-20261022-A", BUILD_TAG, 1
    )
    main_text = main_text.replace(old_policy, new_policy, 1)
    main_text = main_text.replace("phase6h_env_build_cookie", "phase6i_env_build_cookie")
    env_text = env_text.replace("phase6h_env_build_cookie", "phase6i_env_build_cookie")
    main_text = main_text.replace("50364848", "50364949")
    env_text = env_text.replace("50364848", "50364949")
    main_text = main_text.replace("PHASE 6H", "PHASE 6I").replace("Phase 6H", "Phase 6I").replace('"P6H ', '"P6I ')
    env_text = env_text.replace("PHASE 6H", "PHASE 6I").replace("Phase 6H", "Phase 6I")

    required = (
        BUILD_TAG,
        "case 0x00202680u: return sub_00202680;",
        "s_phase6iRootEntered = 1;",
        "P6I XENOS: PASS Direct3D_CreateDevice",
        "P6I FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6I FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "P6I HARVEST SUMMARY",
        "PHASE 6I CALLER HARVEST RESULT",
    )
    for item in required:
        if item not in main_text:
            raise SystemExit(f"[Phase6I] generated main lost marker: {item}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6I",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6i_caller_harvest"] = {
        "source_phase": "6H",
        "cached_base": True,
        "phase6h_hardware_pass": True,
        "phase6h_observed_boundary": {
            "kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x00202680",
            "esp": "0x008BFF30",
            "saved_esp": "0x008BFF30",
            "fault": 0,
            "ticks": 93854,
            "trace": 8082,
            "direct_dispatches_before_boundary": 1151,
            "icall_dispatches_before_boundary": 1556,
            "last_packed_direct": "0x000443D0",
            "last_packed_icall": "0x00250600",
        },
        "root": f"0x{ROOT:08X}",
        "root_name": generated[ROOT]["name"],
        "frontier_caller": f"0x{CALLER:08X}",
        "caller_name": generated[CALLER]["name"],
        "caller_direct_targets_total": len(caller_targets_all),
        "caller_direct_targets_generated": len(caller_targets_generated),
        "caller_direct_targets_unpacked": len(caller_targets_unpacked),
        "caller_direct_targets_ungenerated": len(caller_targets_ungenerated),
        "caller_ungenerated_targets": [f"0x{x:08X}" for x in caller_targets_ungenerated],
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
        "quiet_dispatch_logging_inherited": True,
        "xenos_surface_inherited": True,
        "strategy": (
            "frozen Phase-6H base; mandatory 0x00202680 root; still-unpacked exact "
            "caller 0x0023A3CE direct targets; caller depth-2 closure; root depth-12 "
            "closure; 192 nearest text siblings; nearest-text fill to 1024 candidates"
        ),
        "runtime_policy": (
            "exact packed DIRECT/ICALL_SAFE targets continue automatically; inherited "
            "quiet dispatch logging preserves the dense frontier window and summaries; "
            "NV2A/platform/ABI/guest-fault/missing-body boundaries remain hard stops"
        ),
    }
    manifest["phase6i_candidate_new_members"] = [f"0x{x:08X}" for x in candidate_new]
    manifest["phase6i_new_members"] = [f"0x{x:08X}" for x in sorted(new_members)]
    manifest["phase6i_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6i-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    total_new_source = sum(len(rendered[va]) for va in new_members)
    print(
        f"[Phase6I] CACHED CALLER HARVEST: base={len(old)} "
        f"caller_targets={len(caller_targets_all)} "
        f"generated={len(caller_targets_generated)} "
        f"unpacked={len(caller_targets_unpacked)} "
        f"ungenerated={len(caller_targets_ungenerated)} "
        f"candidate_new={len(candidate_new)} pruned={len(pruned)} "
        f"packed_new={len(new_members)} total={len(expanded)} "
        f"new_source_bytes={total_new_source}"
    )
    print(
        "[Phase6I] FAST BASE: reused existing Phase 6H generated main/env/manifest; "
        "no recursive ancestry regeneration"
    )
    print(
        "[Phase6I] HARD STOP: NV2A/platform/ABI/guest-fault/missing-body boundaries "
        "remain fenced and logged"
    )
    print("[Phase6I] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

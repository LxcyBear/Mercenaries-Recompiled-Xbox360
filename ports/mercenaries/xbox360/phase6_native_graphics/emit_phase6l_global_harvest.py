#!/usr/bin/env python3
"""Phase 6L: cached global-gap caller harvester.

Phase 6K hardware PASS consumed 0x000D4A30 and stopped cleanly at:
  DIRECT_FRONTIER 0x0023A3CE -> 0x0016B7F0
  fault=0, ticks=97909, trace=9423

Recent frontiers from caller 0x0023A3CE remain non-local, so 6L
keeps the exact root/caller closures but also reserves a stratified global set
of still-unpacked generated .text functions. This increases the chance that a
dynamic function-table target is already packed when encountered.

The already-generated Phase 6K output is reused as a frozen local baseline.
Unknown support is pruned. Exact packed DIRECT/ICALL_SAFE targets continue
automatically. Genuine NV2A/platform/ABI/guest-fault/missing-body boundaries
remain hard stops.
"""
from __future__ import annotations
import argparse, importlib.util, json, re
from pathlib import Path

BUILD_TAG = "P6L-GLOBAL-HARVEST-0016B7F0-20261022-A"
ROOT = 0x0016B7F0
CALLER = 0x0023A3CE
TEXT_START = 0x00011000
TEXT_END = 0x00255620
ROOT_DIRECT_DEPTH = 12
ROOT_DIRECT_CAP = 768
CALLER_CLOSURE_DEPTH = 2
CALLER_CLOSURE_CAP = 2048
GLOBAL_RESERVE = 768
LOCAL_RESERVE = 192
TOTAL_NEW_CAP = 1536
CALL_COMMENT_RE = re.compile(r"/\*\s*call\s+0x([0-9A-Fa-f]{8})\s*\*/")

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6L] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def validate(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        hit = [r for r in by_va.values() if int(r["start"]) < root < int(r["end"])]
        if hit:
            r = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6L] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(r['start']):08X}-0x{int(r['end']):08X} {r['name']}"
            )
        raise SystemExit(f"[Phase6L] target 0x{root:08X} is absent from function inventory")
    if root not in generated:
        raise SystemExit(
            f"[Phase6L] target 0x{root:08X} is an exact function start "
            f"({by_va[root]['name']}) but has no generated translated body"
        )

def instrument(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6L] could not instrument root 0x0016B7F0")
    return rendered[:b + 1] + "\n    s_phase6lRootEntered = 1;" + rendered[b + 1:]

def unique_in_order(values):
    seen = set()
    out = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out

def stratified(values, count):
    if count <= 0 or not values:
        return []
    if len(values) <= count:
        return list(values)
    if count == 1:
        return [values[len(values) // 2]]
    last = len(values) - 1
    return unique_in_order(values[(i * last) // (count - 1)] for i in range(count))

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

    base = load(args.base_emitter, "phase6l_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6l_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6l_p5bc")

    base_main = args.base_dir / "main.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6k-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6L] cached Phase 6K baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6K":
        raise SystemExit("[Phase6L] cached baseline manifest is not Phase 6K")
    if manifest.get("build_tag") != "P6K-GLOBAL-HARVEST-000D4A30-20261022-A":
        raise SystemExit("[Phase6L] cached Phase 6K baseline build tag mismatch")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate(ROOT, by_va, generated)
    validate(CALLER, by_va, generated)

    old = {int(x, 0) for x in manifest.get("members", [])}
    if ROOT in old:
        raise SystemExit("[Phase6L] 0x0016B7F0 already packed by Phase 6K")

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

    remaining = sorted(
        va for va in generated
        if TEXT_START <= va < TEXT_END and va not in old
    )
    global_samples = stratified(remaining, GLOBAL_RESERVE)
    local = sorted(remaining, key=lambda va: (abs(va - ROOT), va))

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

    global_added = 0
    for va in global_samples:
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in candidate_order:
            candidate_order.append(va)
            global_added += 1

    local_added = 0
    for va in local:
        if len(candidate_order) >= TOTAL_NEW_CAP or local_added >= LOCAL_RESERVE:
            break
        if va not in candidate_order:
            candidate_order.append(va)
            local_added += 1

    for va in remaining:
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in candidate_order:
            candidate_order.append(va)

    candidate_new = sorted(set(candidate_order[:TOTAL_NEW_CAP]))
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6L] candidate batch lost mandatory root 0x0016B7F0")

    expanded = old | set(candidate_new)
    new_members = list(candidate_new)

    marker = "static int s_phase6kRootEntered;"
    if marker not in main_text:
        raise SystemExit("[Phase6L] Phase 6K root-state marker changed")
    main_text = main_text.replace(marker, marker + "\nstatic int s_phase6lRootEntered;", 1)

    marker = "    s_phase6kRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6L] Phase 6K reset marker changed")
    main_text = main_text.replace(marker, marker + "    s_phase6lRootEntered = 0;\n", 1)

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text, base, p5bb, generated, new_members, expanded
    )
    if ROOT not in new_members:
        raise SystemExit("[Phase6L] support-clean pruning removed mandatory root 0x0016B7F0")

    old_result = '''    {
        char phase6kSummary[256];
        sprintf(
            phase6kSummary,
            "P6K HARVEST SUMMARY: direct=%u last_direct=%08X caller=%08X icall=%u last_icall=%08X icall_caller=%08X",
            (unsigned int)s_phase5bcPackedDirectDispatchCount,
            (unsigned int)s_phase5bcPackedDirectLastTarget,
            (unsigned int)s_phase5bcPackedDirectLastCaller,
            (unsigned int)s_phase5bcPackedIcallDispatchCount,
            (unsigned int)s_phase5bcPackedIcallLastTarget,
            (unsigned int)s_phase5bcPackedIcallLastCaller);
        trace(phase6kSummary);
    }

    if (s_phase6kRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6K GLOBAL HARVEST RESULT: PASS");
    else
        trace("PHASE 6K GLOBAL HARVEST RESULT: FAIL");'''

    new_result = '''    {
        char phase6lSummary[256];
        sprintf(
            phase6lSummary,
            "P6L HARVEST SUMMARY: direct=%u last_direct=%08X caller=%08X icall=%u last_icall=%08X icall_caller=%08X",
            (unsigned int)s_phase5bcPackedDirectDispatchCount,
            (unsigned int)s_phase5bcPackedDirectLastTarget,
            (unsigned int)s_phase5bcPackedDirectLastCaller,
            (unsigned int)s_phase5bcPackedIcallDispatchCount,
            (unsigned int)s_phase5bcPackedIcallLastTarget,
            (unsigned int)s_phase5bcPackedIcallLastCaller);
        trace(phase6lSummary);
    }

    if (s_phase6lRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6L GLOBAL HARVEST RESULT: PASS");
    else
        trace("PHASE 6L GLOBAL HARVEST RESULT: FAIL");'''

    if old_result not in main_text:
        raise SystemExit("[Phase6L] Phase 6K result gate changed")
    main_text = main_text.replace(old_result, new_result, 1)

    old_policy = (
        "Policy: start from the frozen hardware-proven Phase-6J generated baseline, seed exact "
        "frontier 000D4A30, combine caller/root closures with stratified global generated-text "
        "coverage, and hard-stop on genuine NV2A/platform/ABI/guest-fault or missing-body "
        "boundaries without fabricating success"
    )
    new_policy = (
        "Policy: start from the frozen hardware-proven Phase-6K generated baseline, seed exact "
        "frontier 0016B7F0, combine caller/root closures with stratified global generated-text "
        "coverage, and hard-stop on genuine NV2A/platform/ABI/guest-fault or missing-body "
        "boundaries without fabricating success"
    )
    if old_policy not in main_text:
        raise SystemExit("[Phase6L] Phase 6K policy marker changed")

    main_text = main_text.replace(
        "P6K-GLOBAL-HARVEST-000D4A30-20261022-A", BUILD_TAG, 1
    )
    main_text = main_text.replace(old_policy, new_policy, 1)
    main_text = main_text.replace("phase6k_env_build_cookie", "phase6l_env_build_cookie")
    env_text = env_text.replace("phase6k_env_build_cookie", "phase6l_env_build_cookie")
    main_text = main_text.replace("50364B4B", "50364C4C")
    env_text = env_text.replace("50364B4B", "50364C4C")
    main_text = main_text.replace("PHASE 6K", "PHASE 6L").replace("Phase 6K", "Phase 6L").replace('"P6K ', '"P6L ')
    env_text = env_text.replace("PHASE 6K", "PHASE 6L").replace("Phase 6K", "Phase 6L")

    required = (
        BUILD_TAG,
        "case 0x0016B7F0u: return sub_0016B7F0;",
        "s_phase6lRootEntered = 1;",
        "P6L XENOS: PASS Direct3D_CreateDevice",
        "P6L FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6L FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "P6L HARVEST SUMMARY",
        "PHASE 6L GLOBAL HARVEST RESULT",
        "#pragma warning(disable:4102)",
    )
    for item in required:
        if item not in main_text:
            raise SystemExit(f"[Phase6L] generated main lost marker: {item}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6L",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6l_global_harvest"] = {
        "source_phase": "6K",
        "cached_base": True,
        "phase6k_hardware_pass": True,
        "phase6k_observed_boundary": {
            "kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x0016B7F0",
            "esp": "0x008BFF3C",
            "saved_esp": "0x008BFF3C",
            "fault": 0,
            "ticks": 97909,
            "trace": 9423,
            "direct_dispatches_before_boundary": 1162,
            "icall_dispatches_before_boundary": 2156,
            "last_packed_direct": "0x0023BE3C",
            "last_packed_icall": "0x00250700",
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
        "global_reserve_requested": GLOBAL_RESERVE,
        "global_reserve_added": global_added,
        "local_reserve_requested": LOCAL_RESERVE,
        "local_reserve_added": local_added,
        "total_new_cap": TOTAL_NEW_CAP,
        "base_pack_members": len(old),
        "remaining_generated_text_members": len(remaining),
        "candidate_new_members": len(candidate_new),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(expanded),
        "new_direct_frontier_targets": [f"0x{x:08X}" for x in sorted(frontiers)],
        "quiet_dispatch_logging_inherited": True,
        "c4102_generated_label_warning_suppressed": True,
        "xenos_surface_inherited": True,
        "strategy": (
            "frozen Phase-6K base; mandatory 0x0016B7F0 root; remaining exact caller "
            "0x0023A3CE targets; caller depth-2 closure; root depth-12 closure; "
            "768 stratified global generated-text entries; 192 nearest root siblings; "
            "address-ordered fill to 1536 candidates"
        ),
        "runtime_policy": (
            "exact packed DIRECT/ICALL_SAFE targets continue automatically; "
            "NV2A/platform/ABI/guest-fault/missing-body boundaries remain hard stops"
        ),
    }
    manifest["phase6l_candidate_new_members"] = [f"0x{x:08X}" for x in candidate_new]
    manifest["phase6l_new_members"] = [f"0x{x:08X}" for x in sorted(new_members)]
    manifest["phase6l_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6l-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    total_new_source = sum(len(rendered[va]) for va in new_members)
    print(
        f"[Phase6L] CACHED GLOBAL HARVEST: base={len(old)} "
        f"caller_unpacked={len(caller_targets_unpacked)} "
        f"remaining_text={len(remaining)} global_added={global_added} local_added={local_added} "
        f"candidate_new={len(candidate_new)} pruned={len(pruned)} "
        f"packed_new={len(new_members)} total={len(expanded)} "
        f"new_source_bytes={total_new_source}"
    )
    print("[Phase6L] FAST BASE: reused existing Phase 6K generated main/env/manifest")
    print("[Phase6L] GLOBAL COVERAGE: stratified generated-text reserve enabled")
    print("[Phase6L] HARD STOP: NV2A/platform/ABI/guest-fault/missing-body boundaries remain fenced")
    print("[Phase6L] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

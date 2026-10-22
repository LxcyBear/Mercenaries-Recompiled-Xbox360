#!/usr/bin/env python3
"""Phase 6M: cached global-gap caller harvester.

Phase 6L hardware PASS consumed 0x0016B7F0 and stopped cleanly at:
  DIRECT_FRONTIER 0x0023A3CE -> 0x00179850
  fault=0, ticks=129724, trace=19928

Recent frontiers from caller 0x0023A3CE remain non-local, so 6M
keeps the exact root/caller closures but also reserves a stratified global set
of still-unpacked generated .text functions. This increases the chance that a
dynamic function-table target is already packed when encountered.

The already-generated Phase 6L monolithic cache is reused as a frozen local baseline.
Unknown support is pruned. Exact packed DIRECT/ICALL_SAFE targets continue
automatically. Genuine NV2A/platform/ABI/guest-fault/missing-body boundaries
remain hard stops.
"""
from __future__ import annotations
import argparse, importlib.util, json, re
from pathlib import Path

BUILD_TAG = "P6M-GLOBAL-HARVEST-00179850-20261022-A"
ROOT = 0x00179850
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
        raise SystemExit(f"[Phase6M] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def validate(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        hit = [r for r in by_va.values() if int(r["start"]) < root < int(r["end"])]
        if hit:
            r = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6M] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(r['start']):08X}-0x{int(r['end']):08X} {r['name']}"
            )
        raise SystemExit(f"[Phase6M] target 0x{root:08X} is absent from function inventory")
    if root not in generated:
        raise SystemExit(
            f"[Phase6M] target 0x{root:08X} is an exact function start "
            f"({by_va[root]['name']}) but has no generated translated body"
        )

def instrument(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6M] could not instrument root 0x00179850")
    return rendered[:b + 1] + "\n    s_phase6mRootEntered = 1;" + rendered[b + 1:]

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


SHARD_TARGET_CHARS = 750000

def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    """Write an editor-friendly wrapper while preserving one C++ translation unit.

    The monolithic source remains available for the next emitter's static analysis.
    The build-facing main.cpp includes function-boundary .inl shards between the
    existing optimize-off/on pragmas, so preprocessing reconstructs the same source
    order and linkage semantics.
    """
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'

    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6M] translated-body optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6M] translated-body optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6M] translated-body block contains no functions")

    # Cut only after complete translated functions. Preserve all whitespace and
    # directives between functions verbatim inside the same shard/order.
    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6M] translated function opening brace missing")
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
        # Trailing whitespace/directives belong to the final shard.
        last_end = len(body)
    if not cut_points or cut_points[-1] != last_end:
        cut_points.append(last_end)

    shard_dir = out_dir / "translated_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale in shard_dir.glob("phase6m_*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cut_points):
        if end <= start:
            continue
        name = f"phase6m_{index:03d}.inl"
        path = shard_dir / name
        payload = body[start:end]
        path.write_text(payload, encoding="utf-8")
        shards.append({
            "name": name,
            "chars": len(payload),
            "lines": payload.count("\n") + 1,
        })
        start = end

    if start != len(body):
        raise SystemExit("[Phase6M] shard writer did not consume full body block")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n'
        for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]

    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    # Strong reconstruction check: replacing the include block with shard text
    # must reproduce the exact monolithic source byte-for-byte.
    reconstructed_body = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8")
        for row in shards
    )
    if reconstructed_body != body:
        raise SystemExit("[Phase6M] shard reconstruction identity mismatch")

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

    base = load(args.base_emitter, "phase6m_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6m_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6m_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6l-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6M] cached Phase 6L baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6L":
        raise SystemExit("[Phase6M] cached baseline manifest is not Phase 6L")
    if manifest.get("build_tag") != "P6L-GLOBAL-HARVEST-0016B7F0-20261022-A":
        raise SystemExit("[Phase6M] cached Phase 6L baseline build tag mismatch")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate(ROOT, by_va, generated)
    validate(CALLER, by_va, generated)

    old = {int(x, 0) for x in manifest.get("members", [])}
    if ROOT in old:
        raise SystemExit("[Phase6M] 0x00179850 already packed by Phase 6L")

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
        raise SystemExit("[Phase6M] candidate batch lost mandatory root 0x00179850")

    expanded = old | set(candidate_new)
    new_members = list(candidate_new)

    marker = "static int s_phase6lRootEntered;"
    if marker not in main_text:
        raise SystemExit("[Phase6M] Phase 6L root-state marker changed")
    main_text = main_text.replace(marker, marker + "\nstatic int s_phase6mRootEntered;", 1)

    marker = "    s_phase6lRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6M] Phase 6L reset marker changed")
    main_text = main_text.replace(marker, marker + "    s_phase6mRootEntered = 0;\n", 1)

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text, base, p5bb, generated, new_members, expanded
    )
    if ROOT not in new_members:
        raise SystemExit("[Phase6M] support-clean pruning removed mandatory root 0x00179850")

    old_result = '''    {
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

    new_result = '''    {
        char phase6mSummary[256];
        sprintf(
            phase6mSummary,
            "P6M HARVEST SUMMARY: direct=%u last_direct=%08X caller=%08X icall=%u last_icall=%08X icall_caller=%08X",
            (unsigned int)s_phase5bcPackedDirectDispatchCount,
            (unsigned int)s_phase5bcPackedDirectLastTarget,
            (unsigned int)s_phase5bcPackedDirectLastCaller,
            (unsigned int)s_phase5bcPackedIcallDispatchCount,
            (unsigned int)s_phase5bcPackedIcallLastTarget,
            (unsigned int)s_phase5bcPackedIcallLastCaller);
        trace(phase6mSummary);
    }

    if (s_phase6mRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6M GLOBAL HARVEST RESULT: PASS");
    else
        trace("PHASE 6M GLOBAL HARVEST RESULT: FAIL");'''

    if old_result not in main_text:
        raise SystemExit("[Phase6M] Phase 6L result gate changed")
    main_text = main_text.replace(old_result, new_result, 1)

    old_policy = (
        "Policy: start from the frozen hardware-proven Phase-6K generated baseline, seed exact "
        "frontier 0016B7F0, combine caller/root closures with stratified global generated-text "
        "coverage, and hard-stop on genuine NV2A/platform/ABI/guest-fault or missing-body "
        "boundaries without fabricating success"
    )
    new_policy = (
        "Policy: start from the frozen hardware-proven Phase-6L generated baseline, seed exact "
        "frontier 00179850, combine caller/root closures with stratified global generated-text "
        "coverage, and hard-stop on genuine NV2A/platform/ABI/guest-fault or missing-body "
        "boundaries without fabricating success"
    )
    if old_policy not in main_text:
        raise SystemExit("[Phase6M] Phase 6L policy marker changed")

    main_text = main_text.replace(
        "P6L-GLOBAL-HARVEST-0016B7F0-20261022-A", BUILD_TAG, 1
    )
    main_text = main_text.replace(old_policy, new_policy, 1)
    main_text = main_text.replace("phase6k_env_build_cookie", "phase6m_env_build_cookie")
    env_text = env_text.replace("phase6k_env_build_cookie", "phase6m_env_build_cookie")
    main_text = main_text.replace("50364C4C", "50364D4D")
    env_text = env_text.replace("50364C4C", "50364D4D")
    main_text = main_text.replace("PHASE 6L", "PHASE 6M").replace("Phase 6L", "Phase 6M").replace('"P6L ', '"P6M ')
    env_text = env_text.replace("PHASE 6L", "PHASE 6M").replace("Phase 6L", "Phase 6M")

    required = (
        BUILD_TAG,
        "case 0x00179850u: return sub_00179850;",
        "s_phase6mRootEntered = 1;",
        "P6M XENOS: PASS Direct3D_CreateDevice",
        "P6M FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6M FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "P6M HARVEST SUMMARY",
        "PHASE 6M GLOBAL HARVEST RESULT",
        "#pragma warning(disable:4102)",
    )
    for item in required:
        if item not in main_text:
            raise SystemExit(f"[Phase6M] generated main lost marker: {item}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6M",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6m_global_harvest"] = {
        "source_phase": "6L",
        "cached_base": True,
        "phase6l_hardware_pass": True,
        "phase6l_observed_boundary": {
            "kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x00179850",
            "esp": "0x008BFF3C",
            "saved_esp": "0x008BFF3C",
            "fault": 0,
            "ticks": 129724,
            "trace": 19928,
            "direct_dispatches_before_boundary": 1196,
            "icall_dispatches_before_boundary": 6832,
            "last_packed_direct": "0x0023BE3C",
            "last_packed_icall": "0x00250D50",
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
        "source_layout": source_layout,
        "strategy": (
            "frozen Phase-6L monolithic base; mandatory 0x00179850 root; remaining exact caller "
            "0x0023A3CE targets; caller depth-2 closure; root depth-12 closure; "
            "768 stratified global generated-text entries; 192 nearest root siblings; "
            "address-ordered fill to 1536 candidates"
        ),
        "runtime_policy": (
            "exact packed DIRECT/ICALL_SAFE targets continue automatically; "
            "NV2A/platform/ABI/guest-fault/missing-body boundaries remain hard stops"
        ),
    }
    manifest["phase6m_candidate_new_members"] = [f"0x{x:08X}" for x in candidate_new]
    manifest["phase6m_new_members"] = [f"0x{x:08X}" for x in sorted(new_members)]
    manifest["phase6m_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6m-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    total_new_source = sum(len(rendered[va]) for va in new_members)
    print(
        f"[Phase6M] CACHED GLOBAL HARVEST: base={len(old)} "
        f"caller_unpacked={len(caller_targets_unpacked)} "
        f"remaining_text={len(remaining)} global_added={global_added} local_added={local_added} "
        f"candidate_new={len(candidate_new)} pruned={len(pruned)} "
        f"packed_new={len(new_members)} total={len(expanded)} "
        f"new_source_bytes={total_new_source}"
    )
    print("[Phase6M] FAST BASE: reused existing Phase 6L monolithic cache/env/manifest")
    print(
        f"[Phase6M] SOURCE SHARDS: wrapper_lines={source_layout['wrapper_lines']} "
        f"translated_body_lines={source_layout['body_lines']} "
        f"shards={source_layout['shard_count']} "
        f"monolithic_cache={source_layout['monolithic_cache']}"
    )
    print("[Phase6M] GLOBAL COVERAGE: stratified generated-text reserve enabled")
    print("[Phase6M] HARD STOP: NV2A/platform/ABI/guest-fault/missing-body boundaries remain fenced")
    print("[Phase6M] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

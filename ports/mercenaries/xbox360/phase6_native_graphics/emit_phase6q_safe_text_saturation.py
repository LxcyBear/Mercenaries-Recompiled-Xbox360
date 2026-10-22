#!/usr/bin/env python3
"""Phase 6Q: saturate the remaining support-clean generated .text surface.

Phase 6P cleared the old 200000-block watchdog and reached a genuine new
translated-code boundary:
  DIRECT_FRONTIER 0x0023A3CE -> 0x001F9FD0
  fault=0, ticks=415202, trace=129649

Rather than sampling another subset, 6Q starts from the exact hardware-proven
Phase-6P 600k-budget baseline and attempts to pack every still-unpacked generated
.text function, subject to the existing support-clean pruning rules. The already
certified cos() CRT support remains allowed; no new support symbol is invented.

The goal is to eliminate ordinary generated-body coverage as a recurring source
of blue frontiers. Genuine NV2A/platform/ABI/guest-fault/missing-support
boundaries remain hard stops.
"""
from __future__ import annotations
import argparse, importlib.util, json, re
from pathlib import Path

BUILD_TAG = "P6Q-SAFE-TEXT-SATURATION-001F9FD0-20261022-A"
ROOT = 0x001F9FD0
CALLER = 0x0023A3CE
TEXT_START = 0x00011000
TEXT_END = 0x00255620
ROOT_DIRECT_DEPTH = 16
ROOT_DIRECT_CAP = 2048
CALLER_CLOSURE_DEPTH = 4
CALLER_CLOSURE_CAP = 4096
GLOBAL_RESERVE = 4096
LOCAL_RESERVE = 0
TOTAL_NEW_CAP = 4096
CALL_COMMENT_RE = re.compile(r"/\*\s*call\s+0x([0-9A-Fa-f]{8})\s*\*/")

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6Q] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def validate(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        hit = [r for r in by_va.values() if int(r["start"]) < root < int(r["end"])]
        if hit:
            r = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6Q] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(r['start']):08X}-0x{int(r['end']):08X} {r['name']}"
            )
        raise SystemExit(f"[Phase6Q] target 0x{root:08X} is absent from function inventory")
    if root not in generated:
        raise SystemExit(
            f"[Phase6Q] target 0x{root:08X} is an exact function start "
            f"({by_va[root]['name']}) but has no generated translated body"
        )

def instrument(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6Q] could not instrument root 0x001F9FD0")
    return rendered[:b + 1] + "\n    s_phase6qRootEntered = 1;" + rendered[b + 1:]

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
        raise SystemExit("[Phase6Q] translated-body optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6Q] translated-body optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6Q] translated-body block contains no functions")

    # Cut only after complete translated functions. Preserve all whitespace and
    # directives between functions verbatim inside the same shard/order.
    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6Q] translated function opening brace missing")
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
    for stale in shard_dir.glob("phase6q_*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cut_points):
        if end <= start:
            continue
        name = f"phase6q_{index:03d}.inl"
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
        raise SystemExit("[Phase6Q] shard writer did not consume full body block")

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
        raise SystemExit("[Phase6Q] shard reconstruction identity mismatch")

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

    base = load(args.base_emitter, "phase6q_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6q_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6q_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6p-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6Q] cached Phase 6P baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6P":
        raise SystemExit("[Phase6Q] cached baseline manifest is not Phase 6P")
    if manifest.get("build_tag") != "P6P-BUDGET600K-20261022-A":
        raise SystemExit("[Phase6Q] cached Phase 6P baseline build tag mismatch")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate(ROOT, by_va, generated)
    validate(CALLER, by_va, generated)

    # Phase 6O proved native CRT cos() support on hardware; keep that one
    # support exception available while all other unresolved helpers remain fenced.
    base.STANDARD_CALLS.add("cos")
    if "#include <math.h>" not in main_text:
        raise SystemExit("[Phase6Q] inherited Phase 6P source lost <math.h>")

    old = {int(x, 0) for x in manifest.get("members", [])}
    if ROOT in old:
        raise SystemExit("[Phase6Q] 0x001F9FD0 already packed by Phase 6P")

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

    # Saturation phase: preserve the live root first, then caller/root closures,
    # then every remaining generated .text function. Support-clean pruning below
    # remains authoritative.
    candidate_order = [ROOT]

    for va in caller_targets_unpacked:
        if va not in candidate_order:
            candidate_order.append(va)

    for va in sorted(caller_closure, key=lambda x: (x != CALLER, abs(x - CALLER), x)):
        if va not in old and va not in candidate_order:
            candidate_order.append(va)

    for va in sorted(root_closure, key=lambda x: (x != ROOT, abs(x - ROOT), x)):
        if va not in old and va not in candidate_order:
            candidate_order.append(va)

    for va in remaining:
        if va not in candidate_order:
            candidate_order.append(va)

    if len(candidate_order) > TOTAL_NEW_CAP:
        raise SystemExit(
            f"[Phase6Q] remaining generated-text surface ({len(candidate_order)}) "
            f"exceeds saturation safety cap {TOTAL_NEW_CAP}; raise deliberately"
        )

    candidate_new = sorted(set(candidate_order))
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6Q] saturation batch lost mandatory root 0x001F9FD0")

    expanded = old | set(candidate_new)
    new_members = list(candidate_new)

    marker = "static int s_phase6oRootEntered;"
    if marker not in main_text:
        raise SystemExit("[Phase6Q] Phase 6P inherited root-state marker changed")
    main_text = main_text.replace(marker, marker + "\nstatic int s_phase6qRootEntered;", 1)

    marker = "    s_phase6oRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6Q] Phase 6P inherited reset marker changed")
    main_text = main_text.replace(marker, marker + "    s_phase6qRootEntered = 0;\n", 1)

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text, base, p5bb, generated, new_members, expanded
    )
    if ROOT not in new_members:
        raise SystemExit("[Phase6Q] support-clean pruning removed mandatory root 0x001F9FD0")

    # Phase 6P changed only identity/budget; its result gate still uses the
    # Phase-6O root-state variable. Replace that gate with the 6Q live root.
    old_result = '''    {
        char phase6oSummary[256];
        sprintf(
            phase6oSummary,
            "P6P HARVEST SUMMARY: direct=%u last_direct=%08X caller=%08X icall=%u last_icall=%08X icall_caller=%08X",
            (unsigned int)s_phase5bcPackedDirectDispatchCount,
            (unsigned int)s_phase5bcPackedDirectLastTarget,
            (unsigned int)s_phase5bcPackedDirectLastCaller,
            (unsigned int)s_phase5bcPackedIcallDispatchCount,
            (unsigned int)s_phase5bcPackedIcallLastTarget,
            (unsigned int)s_phase5bcPackedIcallLastCaller);
        trace(phase6oSummary);
    }

    if (s_phase6oRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6P BUDGET EXTENSION RESULT: PASS");
    else
        trace("PHASE 6P BUDGET EXTENSION RESULT: FAIL");'''

    new_result = '''    {
        char phase6qSummary[256];
        sprintf(
            phase6qSummary,
            "P6Q SATURATION SUMMARY: direct=%u last_direct=%08X caller=%08X icall=%u last_icall=%08X icall_caller=%08X",
            (unsigned int)s_phase5bcPackedDirectDispatchCount,
            (unsigned int)s_phase5bcPackedDirectLastTarget,
            (unsigned int)s_phase5bcPackedDirectLastCaller,
            (unsigned int)s_phase5bcPackedIcallDispatchCount,
            (unsigned int)s_phase5bcPackedIcallLastTarget,
            (unsigned int)s_phase5bcPackedIcallLastCaller);
        trace(phase6qSummary);
    }

    if (s_phase6qRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6Q SAFE-TEXT SATURATION RESULT: PASS");
    else
        trace("PHASE 6Q SAFE-TEXT SATURATION RESULT: FAIL");'''

    if old_result not in main_text:
        raise SystemExit("[Phase6Q] Phase 6P result gate changed")
    main_text = main_text.replace(old_result, new_result, 1)

    old_policy = (
        "Policy: start from the frozen hardware-proven Phase-6N generated baseline, certify "
        "the proven cos() CRT dependency for exact ICALL_SAFE root 00251CD0, combine caller/root "
        "closures with stratified global generated-text coverage, and hard-stop on genuine "
        "NV2A/platform/ABI/guest-fault or other missing-support boundaries without fabricating success"
    )
    new_policy = (
        "Policy: start from the hardware-proven Phase-6P 600k-budget baseline, seed exact "
        "DIRECT_FRONTIER root 001F9FD0, saturate every remaining support-clean generated .text "
        "function, retain only the hardware-proven cos() CRT support exception, and hard-stop "
        "on genuine NV2A/platform/ABI/guest-fault/missing-support boundaries"
    )
    if old_policy not in main_text:
        raise SystemExit("[Phase6Q] Phase 6P policy marker changed")

    main_text = main_text.replace(
        "P6P-BUDGET600K-20261022-A", BUILD_TAG, 1
    )
    main_text = main_text.replace(old_policy, new_policy, 1)
    main_text = main_text.replace("phase6p_env_build_cookie", "phase6q_env_build_cookie")
    env_text = env_text.replace("phase6p_env_build_cookie", "phase6q_env_build_cookie")
    main_text = main_text.replace("50365050", "50365151")
    env_text = env_text.replace("50365050", "50365151")
    main_text = main_text.replace("PHASE 6P", "PHASE 6Q").replace("Phase 6P", "Phase 6Q").replace('"P6P ', '"P6Q ')
    env_text = env_text.replace("PHASE 6P", "PHASE 6Q").replace("Phase 6P", "Phase 6Q")

    required = (
        BUILD_TAG,
        "case 0x001F9FD0u: return sub_001F9FD0;",
        "s_phase6qRootEntered = 1;",
        "P6Q XENOS: PASS Direct3D_CreateDevice",
        "P6Q FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6Q FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "P6Q SATURATION SUMMARY",
        "PHASE 6Q SAFE-TEXT SATURATION RESULT",
        "#pragma warning(disable:4102)",
    )
    for item in required:
        if item not in main_text:
            raise SystemExit(f"[Phase6Q] generated main lost marker: {item}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6Q",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6q_safe_text_saturation"] = {
        "source_phase": "6P",
        "cached_base": True,
        "phase6p_hardware_pass": True,
        "phase6p_observed_boundary": {
            "kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x001F9FD0",
            "esp": "0x008BFF40",
            "saved_esp": "0x008BFF40",
            "fault": 0,
            "ticks": 415202,
            "trace": 129649,
            "direct_dispatches_before_boundary": 1357,
            "icall_dispatches_before_boundary": 8204,
            "last_packed_direct": "0x0023BE3C",
            "last_packed_icall": "0x00252A20",
        },
        "execution_budget_inherited": 600000,
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
        "saturation_candidate_cap": TOTAL_NEW_CAP,
        "base_pack_members": len(old),
        "remaining_generated_text_members": len(remaining),
        "candidate_new_members": len(candidate_new),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(expanded),
        "remaining_after_support_clean": len(remaining) - len(pruned),
        "new_direct_frontier_targets": [f"0x{x:08X}" for x in sorted(frontiers)],
        "quiet_dispatch_logging_inherited": True,
        "c4102_generated_label_warning_suppressed": True,
        "xenos_surface_inherited": True,
        "phase_owned_crt_support": ["cos"],
        "source_layout": source_layout,
        "strategy": (
            "frozen hardware-proven Phase-6P monolithic base with 600k execution budget; "
            "mandatory 0x001F9FD0 live root; exact caller/root closures; then every remaining "
            "generated .text function up to the 4096-member saturation cap; support-clean pruning authoritative"
        ),
        "runtime_policy": (
            "exact packed DIRECT/ICALL_SAFE targets continue automatically; "
            "NV2A/platform/ABI/guest-fault/missing-support boundaries remain hard stops"
        ),
    }
    manifest["phase6q_candidate_new_members"] = [f"0x{x:08X}" for x in candidate_new]
    manifest["phase6q_new_members"] = [f"0x{x:08X}" for x in sorted(new_members)]
    manifest["phase6q_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6q-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    total_new_source = sum(len(rendered[va]) for va in new_members)
    print(
        f"[Phase6Q] SAFE-TEXT SATURATION: base={len(old)} "
        f"remaining_text={len(remaining)} candidate_new={len(candidate_new)} "
        f"pruned={len(pruned)} packed_new={len(new_members)} total={len(expanded)} "
        f"new_source_bytes={total_new_source}"
    )
    print("[Phase6Q] FAST BASE: reused existing Phase 6P 600k-budget monolithic cache/env/manifest")
    print(
        f"[Phase6Q] SOURCE SHARDS: wrapper_lines={source_layout['wrapper_lines']} "
        f"translated_body_lines={source_layout['body_lines']} "
        f"shards={source_layout['shard_count']} "
        f"monolithic_cache={source_layout['monolithic_cache']}"
    )
    print("[Phase6Q] COVERAGE: every remaining generated .text member attempted; unresolved support pruned")
    print("[Phase6Q] HARD STOP: NV2A/platform/ABI/guest-fault/missing-support boundaries remain fenced")
    print("[Phase6Q] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

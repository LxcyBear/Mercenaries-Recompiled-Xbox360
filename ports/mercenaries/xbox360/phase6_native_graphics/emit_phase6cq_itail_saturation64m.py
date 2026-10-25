#!/usr/bin/env python3
"""Phase 6CQ: 64M support-clean text saturation + exact packed ITAIL dispatch.

6CP hardware cleared the XACT FFFFFFFF/string-overrun fault and advanced to:
  ITAIL caller=0023A3CE target=0010D1A0 fault=0 ticks=26811021.

6CQ is the rocket-mode continuation:
  * preserve the proven 6CP XACT sentinel exit and every prior subsystem fix;
  * resolve 0010D1A0 as an exact generated function start;
  * pack a deep root closure, caller closure, local neighborhood and stratified
    global support-clean generated .text set, up to 4096 new members;
  * auto-dispatch RECOMP_ITAIL / RECOMP_ITAIL_SAFE only when the exact target
    resolves through phase4c_lookup_pack_func;
  * unknown, mid-function, unsupported, guest-fault, ABI, MMIO and kernel/device
    targets remain hard stops;
  * raise the execution watchdog from 32M to 64M translated blocks.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6CP-XACT-FIELD8-SENTINEL-20261025-A"
BUILD_TAG = "P6CQ-ITAIL-SATURATION64M-0010D1A0-20261025-A"
COOKIE_OLD = "phase6cp_env_build_cookie"
COOKIE_NEW = "phase6cq_env_build_cookie"
EMITTER_REVISION = "6CQ-R4"

OBSERVED_TARGET = 0x0010D1A0
CALLER = 0x0023A3CE
TEXT_START = 0x00011000
TEXT_END = 0x00255620

ROOT_DIRECT_DEPTH = 20
ROOT_DIRECT_CAP = 2048
CALLER_CLOSURE_DEPTH = 6
CALLER_CLOSURE_CAP = 4096
GLOBAL_RESERVE = 2048
LOCAL_RESERVE = 1024
TOTAL_NEW_CAP = 4096

CALL_COMMENT_RE = re.compile(r"/\*\s*call\s+0x([0-9A-Fa-f]{8})\s*\*/")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CQ] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def resolve_exact_root(target: int, by_va: dict, generated: dict) -> int:
    if target in by_va:
        if target not in generated:
            raise SystemExit(
                f"[Phase6CQ] ITAIL target 0x{target:08X} is exact function start "
                f"{by_va[target]['name']} but has no generated translated body"
            )
        return target

    containing = [
        row for row in by_va.values()
        if int(row["start"]) < target < int(row["end"])
    ]
    if containing:
        row = sorted(containing, key=lambda item: int(item["start"]))[-1]
        raise SystemExit(
            f"[Phase6CQ] ITAIL target 0x{target:08X} is MID-FUNCTION inside "
            f"0x{int(row['start']):08X}-0x{int(row['end']):08X} {row['name']}; "
            "exact packed ITAIL dispatch refuses to redirect to a different entry"
        )

    raise SystemExit(
        f"[Phase6CQ] ITAIL target 0x{target:08X} absent from function inventory"
    )


def instrument_root(rendered: str, name: str) -> str:
    pos = rendered.find(name)
    brace = rendered.find("{", pos)
    if pos < 0 or brace < 0:
        raise SystemExit("[Phase6CQ] could not instrument resolved ITAIL root")
    return rendered[:brace + 1] + "\n    s_phase6cqRootEntered = 1;" + rendered[brace + 1:]


def patch_state(text: str) -> str:
    anchor = "static DWORD s_phase6cpCurrentVa = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CQ] expected one inherited 6CP early-state anchor, found {text.count(anchor)}"
        )
    state = """static int s_phase6cqRootEntered = 0;
static DWORD s_phase6cqPackedItailDispatches = 0u;
static DWORD s_phase6cqPackedItailSafeDispatches = 0u;
static DWORD s_phase6cqPackedItailLastTarget = 0u;
static DWORD s_phase6cqPackedItailLastCaller = 0u;
static DWORD s_phase6cqPackedItailLastSavedEsp = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def patch_itail_dispatch(text: str) -> str:
    typedef_anchor = "typedef void (*recomp_func_t)(void);\n"
    if text.count(typedef_anchor) != 1:
        raise SystemExit(
            f"[Phase6CQ] expected one recomp_func_t typedef, found {text.count(typedef_anchor)}"
        )

    decls = r"""
static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va);
static void phase6cq_dispatch_packed_itail(
    uint32_t target,
    uint32_t savedEsp,
    uint32_t isSafe);
"""
    text = text.replace(typedef_anchor, typedef_anchor + decls, 1)

    def replace_macro(source: str, macro_name: str, new_block: str) -> str:
        # Earlier phases have legitimately reformatted/wrapped these macros.
        # Match the live preprocessor definition structurally instead of
        # depending on the original Phase4C byte-for-byte spelling.
        pattern = re.compile(
            rf"(?m)^#define[ \t]+{re.escape(macro_name)}\("
        )
        matches = list(pattern.finditer(source))
        if len(matches) != 1:
            raise SystemExit(
                f"[Phase6CQ] expected one {macro_name} definition, found {len(matches)}"
            )

        start_pos = matches[0].start()

        # A function-like macro continues while each physical source line ends
        # in a backslash. Consume the complete definition, including the final
        # non-continuation line, without assuming its body/indentation.
        line_start = start_pos
        line_end = source.find("\n", line_start)
        if line_end < 0:
            line_end = len(source)

        while True:
            line = source[line_start:line_end]
            if not line.rstrip().endswith("\\"):
                block_end = line_end
                if block_end < len(source):
                    block_end += 1
                break

            line_start = line_end + 1
        line_end = source.find("\n", line_start)
            if line_end < 0:
                line_end = len(source)

        return source[:start_pos] + new_block + source[block_end:]

    itail_new = r"""#define RECOMP_ITAIL(xbox_va) do { \
    phase6cq_dispatch_packed_itail( \
        (uint32_t)(xbox_va), \
        (uint32_t)g_esp, \
        0u); \
    return; \
} while (0)
"""

    itail_safe_new = r"""#define RECOMP_ITAIL_SAFE(xbox_va, saved_esp) do { \
    phase6cq_dispatch_packed_itail( \
        (uint32_t)(xbox_va), \
        (uint32_t)(saved_esp), \
        1u); \
    return; \
} while (0)
"""

    text = replace_macro(text, "RECOMP_ITAIL", itail_new)
    text = replace_macro(text, "RECOMP_ITAIL_SAFE", itail_safe_new)

    lookup_marker = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    lookup_pos = text.find(lookup_marker)
    if lookup_pos < 0:
        raise SystemExit("[Phase6CQ] pack lookup definition missing")

    # Install helper immediately before the translated optimize-off block. The
    # lookup has a forward declaration above, so source order remains valid.
    optimize_off = '#pragma optimize("", off)\n'
    insert_pos = text.find(optimize_off)
    if insert_pos < 0:
        raise SystemExit("[Phase6CQ] translated optimize-off marker missing")

    helper = r"""
static void phase6cq_dispatch_packed_itail(
    uint32_t target,
    uint32_t savedEsp,
    uint32_t isSafe)
{
    recomp_func_t fn = phase4c_lookup_pack_func(target);

    if (!fn)
    {
        phase4c_escape(
            isSafe ? PHASE4C_BOUNDARY_ITAIL_SAFE : PHASE4C_BOUNDARY_ITAIL,
            target,
            savedEsp);
        return;
    }

    if (isSafe)
        ++s_phase6cqPackedItailSafeDispatches;
    else
        ++s_phase6cqPackedItailDispatches;

    if (target == 0x0010D1A0u)
        s_phase6cqRootEntered = 1;

    s_phase6cqPackedItailLastTarget = target;
    s_phase6cqPackedItailLastCaller = phase4c_current_caller();
    s_phase6cqPackedItailLastSavedEsp = savedEsp;

    {
        DWORD total =
            s_phase6cqPackedItailDispatches +
            s_phase6cqPackedItailSafeDispatches;
        if (total <= 16u || (total & (total - 1u)) == 0u)
        {
            char line[420];
            sprintf(
                line,
                "PASS: Phase 6CQ packed %s caller=%08X target=%08X saved_esp=%08X direct=%u safe=%u total=%u",
                isSafe ? "ITAIL_SAFE" : "ITAIL",
                (unsigned int)s_phase6cqPackedItailLastCaller,
                (unsigned int)target,
                (unsigned int)savedEsp,
                (unsigned int)s_phase6cqPackedItailDispatches,
                (unsigned int)s_phase6cqPackedItailSafeDispatches,
                (unsigned int)total);
            trace(line);
        }
    }

    fn();
}

"""
    return text[:insert_pos] + helper + text[insert_pos:]

def patch_budget(text: str) -> str:
    old = "#define PHASE4C_EXEC_BUDGET 32000000u"
    new = "#define PHASE4C_EXEC_BUDGET 64000000u"
    if text.count(old) != 1:
        raise SystemExit(
            f"[Phase6CQ] expected one 32M budget define, found {text.count(old)}"
        )
    return text.replace(old, new, 1)


def insert_summary(text: str) -> str:
    marker = "P6CP XACT FIELD8:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CQ] inherited 6CP summary insertion marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 10000:
        raise SystemExit("[Phase6CQ] summary insertion point not found")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CQ ITAIL SATURATION: root_entered=%u itail=%u itail_safe=%u last_target=%08X last_caller=%08X last_saved_esp=%08X",\n'
        f'{indent}    (unsigned int)s_phase6cqRootEntered,\n'
        f'{indent}    (unsigned int)s_phase6cqPackedItailDispatches,\n'
        f'{indent}    (unsigned int)s_phase6cqPackedItailSafeDispatches,\n'
        f'{indent}    (unsigned int)s_phase6cqPackedItailLastTarget,\n'
        f'{indent}    (unsigned int)s_phase6cqPackedItailLastCaller,\n'
        f'{indent}    (unsigned int)s_phase6cqPackedItailLastSavedEsp);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_policy(text: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0 or text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6CQ] expected one runtime policy trace")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    policy = (
        "Phase 6CQ rocket mode preserves 6CP XACT sentinel and all prior subsystem "
        "repairs, packs up to 4096 additional support-clean generated .text members "
        "around exact ITAIL 0010D1A0 plus caller/global coverage, auto-dispatches only "
        "exact packed ITAIL/ITAIL_SAFE targets, raises watchdog to 64M, and retains "
        "hard stops for unknown/mid-function/unsupported/guest-fault/MMIO/ABI targets"
    )
    return text[:line_start] + indent + f'trace("Policy: {policy}");' + text[line_end:]


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CP", "PHASE 6CQ")
        .replace("Phase 6CP", "Phase 6CQ")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CQ] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bb-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bc-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6cq_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6cq_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6cq_p5bc")
    p6bl = load(args.phase6bl_emitter, "phase6cq_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cp-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CQ] missing cached 6CP input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CP" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CQ] cached Phase 6CP identity mismatch")

    cp = manifest.get("phase6cp_xact_field8_sentinel", {})
    if (
        cp.get("phase6co_hardware", {}).get("fault_address") != "0x782E657F"
        or cp.get("sentinel_value") != "0xFFFFFFFF"
        or cp.get("hard_fences_changed") is not False
        or cp.get("execution_budget_inherited") != 32000000
    ):
        raise SystemExit("[Phase6CQ] inherited 6CP policy mismatch")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    root = resolve_exact_root(OBSERVED_TARGET, by_va, generated)

    if CALLER not in generated:
        raise SystemExit("[Phase6CQ] caller 0x0023A3CE lost generated body")

    # Preserve previously certified CRT dependencies used by saturated text.
    base.STANDARD_CALLS.add("sin")
    base.STANDARD_CALLS.add("cos")

    old = {int(item, 0) for item in manifest.get("members", [])}
    if root in old:
        print(
            f"[Phase6CQ] root 0x{root:08X} is already packed; "
            "continuing with ITAIL dispatcher + remaining saturation"
        )

    root_closure = set(
        p5bb.bounded_promoted_members(
            base, root, generated, ROOT_DIRECT_DEPTH, ROOT_DIRECT_CAP
        )
    )
    root_closure.add(root)

    caller_closure = set(
        p5bb.bounded_promoted_members(
            base, CALLER, generated, CALLER_CLOSURE_DEPTH, CALLER_CLOSURE_CAP
        )
    )

    caller_source = generated[CALLER]["source"]
    caller_targets = unique_in_order(
        int(m.group(1), 16) for m in CALL_COMMENT_RE.finditer(caller_source)
    )

    remaining = sorted(
        va for va in generated
        if TEXT_START <= va < TEXT_END and va not in old
    )
    global_samples = stratified(remaining, GLOBAL_RESERVE)
    local = sorted(remaining, key=lambda va: (abs(va - root), va))

    candidate_order = []

    def add(va):
        if (
            va in generated
            and TEXT_START <= va < TEXT_END
            and va not in old
            and va not in candidate_order
            and len(candidate_order) < TOTAL_NEW_CAP
        ):
            candidate_order.append(va)

    add(root)
    for va in caller_targets:
        add(va)
    for va in sorted(root_closure, key=lambda x: (x != root, abs(x - root), x)):
        add(va)
    for va in sorted(caller_closure, key=lambda x: (x != CALLER, abs(x - CALLER), x)):
        add(va)
    for va in local[:LOCAL_RESERVE]:
        add(va)
    for va in global_samples:
        add(va)
    for va in remaining:
        add(va)
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break

    candidate_new = sorted(set(candidate_order))
    expanded = set(old) | set(candidate_new)
    new_members = list(candidate_new)

    main_text = patch_state(main_text)

    p5bc.SWEEP_ROOT = root
    p5bc.instrument_root_entry = instrument_root

    rendered = {}
    frontiers = set()
    pruned = {}

    # If the live ITAIL root is already in the inherited pack, additional
    # saturation is optional. At this late stage the remaining generated-text
    # inventory can legitimately consist entirely of members with unresolved
    # support. The generic Phase5BC helper treats "all candidates pruned" as a
    # fatal broad-sweep condition, but for 6CQ that must not prevent us from
    # enabling exact ITAIL dispatch over the already-large proven pack.
    if new_members:
        if root in old:
            candidate_members = list(new_members)
            existing_defs = set(base.support_symbols(main_text))

            def render_candidate(va: int, allowed_members: set[int]):
                row = generated[va]
                name = row["name"]
                rendered_one = base.localize_and_instrument(row["source"], name)
                return p5bb.rewrite_direct_frontier(
                    base,
                    rendered_one,
                    generated,
                    allowed_members,
                )

            translated_names = {generated[va]["name"] for va in candidate_members}
            supplied = existing_defs | translated_names
            retained = []
            for va in candidate_members:
                rendered_one, _ = render_candidate(va, expanded)
                local_supplied = set(supplied)
                local_supplied.update(base.DEFINE_RE.findall(rendered_one))
                calls = set(base.CALL_RE.findall(base.mask_noncode(rendered_one)))
                calls.discard(generated[va]["name"])
                missing = sorted(
                    name for name in calls
                    if name not in local_supplied and name not in base.STANDARD_CALLS
                )
                if missing:
                    pruned[va] = missing
                else:
                    retained.append(va)

            if not retained:
                print(
                    "[Phase6CQ] SATURATION NOTE: remaining candidate surface is "
                    "entirely support-fenced; keeping inherited pack and proceeding "
                    "with exact ITAIL dispatch"
                )
                for va in candidate_members:
                    expanded.discard(va)
                new_members[:] = []
            else:
                # Let the proven helper do final convergence/rendering over the
                # subset that passed the lightweight support filter.
                for va in candidate_members:
                    if va not in retained:
                        expanded.discard(va)
                new_members[:] = retained
                main_text, rendered, frontiers, helper_pruned = p5bc.insert_pack_members(
                    main_text,
                    base,
                    p5bb,
                    generated,
                    new_members,
                    expanded,
                    require_sweep_root=False,
                )
                pruned.update(helper_pruned)
        else:
            main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
                main_text,
                base,
                p5bb,
                generated,
                new_members,
                expanded,
                require_sweep_root=True,
            )

    if root not in old and root not in new_members:
        raise SystemExit("[Phase6CQ] support-clean pruning removed mandatory ITAIL root")

    main_text = patch_itail_dispatch(main_text)
    main_text = patch_budget(main_text)
    main_text = insert_summary(main_text)
    main_text = patch_policy(main_text)

    if main_text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6CQ] expected one inherited build tag, found {main_text.count(BASE_TAG)}"
        )
    main_text = main_text.replace(BASE_TAG, BUILD_TAG, 1)
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = (
        main_text.replace("PHASE 6CP", "PHASE 6CQ")
        .replace("Phase 6CP", "Phase 6CQ")
        .replace('"P6CP ', '"P6CQ ')
    )
    env_text = patch_env(env_text)

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "P6CQ ITAIL SATURATION:",
        "PASS: Phase 6CQ packed %s",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "PASS: Phase 6CQ XACT field8 sentinel exit",
        "P6CQ XACT FIELD8:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CQ] generated source lost marker: {marker}")

    lookup_case = f"case 0x{root:08X}u: return {generated[root]['name']};"
    if lookup_case not in main_text:
        raise SystemExit(
            f"[Phase6CQ] exact ITAIL root lookup missing: {lookup_case}"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "6CQ"
    manifest["build_tag"] = BUILD_TAG
    manifest["pack_members"] = len(expanded)
    manifest["members"] = [f"0x{x:08X}" for x in sorted(expanded)]
    manifest["phase6cq_itail_saturation64m"] = {
        "source_phase": "6CP",
        "phase6cp_hardware": {
            "boundary_kind": "ITAIL",
            "caller": "0x0023A3CE",
            "target": "0x0010D1A0",
            "fault": 0,
            "ticks": 26811021,
            "trace": 1035188,
            "xact_sentinel_exits": 1,
            "xact_ffffffff_writes": 1,
            "display_calls": 0,
        },
        "resolved_root": f"0x{root:08X}",
        "resolved_root_name": generated[root]["name"],
        "root_closure_depth": ROOT_DIRECT_DEPTH,
        "root_closure_cap": ROOT_DIRECT_CAP,
        "caller_closure_depth": CALLER_CLOSURE_DEPTH,
        "caller_closure_cap": CALLER_CLOSURE_CAP,
        "global_reserve": GLOBAL_RESERVE,
        "local_reserve": LOCAL_RESERVE,
        "candidate_cap": TOTAL_NEW_CAP,
        "base_members": len(old),
        "remaining_generated_text": len(remaining),
        "candidate_new_members": len(candidate_new),
        "packed_new_members": len(new_members),
        "all_remaining_candidates_support_fenced": bool(candidate_new) and not bool(new_members),
        "pruned_members": len(pruned),
        "expanded_members": len(expanded),
        "itail_auto_dispatch": "exact phase4c_lookup_pack_func target only",
        "itail_safe_auto_dispatch": "exact phase4c_lookup_pack_func target only",
        "ordinary_icall_changed": False,
        "translated_membership_changed": bool(new_members),
        "allocator_policy_changed": False,
        "apu_semantics_changed": False,
        "guest_irql_semantics_changed": False,
        "graphics_semantics_changed": False,
        "null_page_semantics_changed": False,
        "seh_terminator_semantics_changed": False,
        "hard_fences_changed": False,
        "execution_budget": 64000000,
        "source_layout": layout,
    }
    manifest["phase6cq_new_members"] = [f"0x{x:08X}" for x in sorted(new_members)]
    manifest["phase6cq_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]
    manifest["phase6cq_new_direct_frontiers"] = [
        f"0x{x:08X}" for x in sorted(frontiers)
    ]

    (args.out_dir / "phase6cq-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    total_source = sum(len(rendered[va]) for va in new_members)
    print(f"[Phase6CQ] emitter revision: {EMITTER_REVISION}")
    print(
        f"[Phase6CQ] ROOT: observed=0x{OBSERVED_TARGET:08X} "
        f"resolved=0x{root:08X} name={generated[root]['name']}"
    )
    print(
        f"[Phase6CQ] ROCKET PACK: base={len(old)} remaining_text={len(remaining)} "
        f"candidate_new={len(candidate_new)} pruned={len(pruned)} "
        f"packed_new={len(new_members)} total={len(expanded)} "
        f"new_source_bytes={total_source}"
    )
    print(
        "[Phase6CQ] ITAIL AUTO-DISPATCH: exact packed ITAIL + ITAIL_SAFE only; "
        "unknown/mid-function targets remain hard stops"
    )
    if candidate_new and not new_members:
        print("[Phase6CQ] SATURATION RESULT: 0 new support-clean members; inherited pack is authoritative")
    print("[Phase6CQ] 64M execution budget armed")
    print("[Phase6CQ] 6CP XACT sentinel repair preserved")
    print("[Phase6CQ] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Phase 5BC: broad translated frontier sweep.

Builds on the hardware-proven Phase 5BB package, then widens the translated
pack around the new fault-free ICALL_SAFE target 0x00237052. Exact generated
targets already present in the widened pack may be entered automatically from
safe indirect calls and from previously fenced direct calls. Unknown targets,
kernel/device boundaries, guest faults, ABI/frame failures, heap exhaustion,
and the existing execution-budget watchdog remain hard stops.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SWEEP_ROOT = 0x00237052
SWEEP_DIRECT_DEPTH = 6
SWEEP_DIRECT_CAP = 256
BUILD_TAG = "P5BC-BROADSWEEP237052-20261020-C"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase5BC] could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_exact_generated_target(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        containing = [
            row
            for row in by_va.values()
            if int(row["start"]) < root < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                f"[Phase5BC] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "Broad sweep refuses mid-function promotion."
            )
        raise SystemExit(
            f"[Phase5BC] target 0x{root:08X} is absent from the function inventory"
        )

    if root not in generated:
        row = by_va[root]
        raise SystemExit(
            f"[Phase5BC] target 0x{root:08X} is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )


def instrument_root_entry(rendered: str, name: str) -> str:
    name_pos = rendered.find(name)
    brace_pos = rendered.find("{", name_pos)
    if name_pos < 0 or brace_pos < 0:
        raise SystemExit("[Phase5BC] could not instrument broad-sweep root")
    return (
        rendered[: brace_pos + 1]
        + "\n    s_phase5bcSweepRootEntered = 1;"
        + rendered[brace_pos + 1 :]
    )


def patch_direct_frontier(main_text: str) -> str:
    old = r'''static void phase4c_direct_frontier(uint32_t target)
{
    char line[192];
    sprintf(
        line,
        "DIRECT FRONTIER: caller=%08X target=%08X esp=%08X",
        (unsigned int)phase4c_current_caller(),
        (unsigned int)target,
        (unsigned int)g_esp);
    trace(line);
    phase4c_escape(
        PHASE4C_BOUNDARY_DIRECT_FRONTIER,
        target,
        g_esp);
}'''

    new = r'''static int s_phase5bcSweepRootEntered;
static uint32_t s_phase5bcPackedIcallDispatchCount;
static uint32_t s_phase5bcPackedIcallLastTarget;
static uint32_t s_phase5bcPackedIcallLastCaller;
static uint32_t s_phase5bcPackedIcallLastSavedEsp;
static uint32_t s_phase5bcPackedDirectDispatchCount;
static uint32_t s_phase5bcPackedDirectLastTarget;
static uint32_t s_phase5bcPackedDirectLastCaller;

static void phase5bc_dispatch_packed_icall(
    uint32_t target,
    uint32_t savedEsp)
{
    recomp_func_t fn = phase4c_lookup_pack_func(target);
    char line[256];

    if (!fn)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_ICALL_SAFE,
            target,
            savedEsp);
        return;
    }

    ++s_phase5bcPackedIcallDispatchCount;
    s_phase5bcPackedIcallLastTarget = target;
    s_phase5bcPackedIcallLastCaller = phase4c_current_caller();
    s_phase5bcPackedIcallLastSavedEsp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5BC broad-sweep ICALL_SAFE caller=%08X target=%08X saved_esp=%08X dispatches=%u",
        (unsigned int)s_phase5bcPackedIcallLastCaller,
        (unsigned int)target,
        (unsigned int)savedEsp,
        (unsigned int)s_phase5bcPackedIcallDispatchCount);
    trace(line);

    fn();
}

static void phase4c_direct_frontier(uint32_t target)
{
    recomp_func_t fn = phase4c_lookup_pack_func(target);
    char line[256];

    if (fn)
    {
        ++s_phase5bcPackedDirectDispatchCount;
        s_phase5bcPackedDirectLastTarget = target;
        s_phase5bcPackedDirectLastCaller = phase4c_current_caller();

        sprintf(
            line,
            "PASS: Phase 5BC broad-sweep DIRECT caller=%08X target=%08X dispatches=%u",
            (unsigned int)s_phase5bcPackedDirectLastCaller,
            (unsigned int)target,
            (unsigned int)s_phase5bcPackedDirectDispatchCount);
        trace(line);

        fn();
        return;
    }

    sprintf(
        line,
        "DIRECT FRONTIER: caller=%08X target=%08X esp=%08X",
        (unsigned int)phase4c_current_caller(),
        (unsigned int)target,
        (unsigned int)g_esp);
    trace(line);
    phase4c_escape(
        PHASE4C_BOUNDARY_DIRECT_FRONTIER,
        target,
        g_esp);
}'''

    if old not in main_text:
        raise SystemExit("[Phase5BC] direct-frontier helper marker changed")
    return main_text.replace(old, new, 1)


def patch_safe_icall(main_text: str) -> str:
    old = r'''    } else { \
        phase4c_escape( \
            PHASE4C_BOUNDARY_ICALL_SAFE, \
            _phase4c_target, \
            (DWORD)(saved_esp)); \
    } \
} while (0)'''

    new = r'''    } else { \
        phase5bc_dispatch_packed_icall( \
            _phase4c_target, \
            (uint32_t)(saved_esp)); \
    } \
} while (0)'''

    marker = "_phase4c_target == 0x0023D550u"
    marker_pos = main_text.find(marker)
    if marker_pos < 0:
        raise SystemExit("[Phase5BC] retained 0x0023D550 ICALL branch marker changed")

    tail_pos = main_text.find(old, marker_pos)
    if tail_pos < 0:
        raise SystemExit("[Phase5BC] RECOMP_ICALL_SAFE final escape marker changed")

    return main_text[:tail_pos] + new + main_text[tail_pos + len(old) :]


def insert_pack_members(
    main_text: str,
    base,
    phase5bb,
    generated: dict,
    new_members: list[int],
    expanded_members: set[int],
    require_sweep_root: bool = True,
) -> tuple[str, dict[int, str], set[int], dict[int, list[str]]]:
    candidate_members = list(new_members)
    existing_defs = set(base.support_symbols(main_text))

    def render_member(va: int, allowed_members: set[int]) -> tuple[str, list[int]]:
        row = generated[va]
        name = row["name"]
        rendered = base.localize_and_instrument(row["source"], name)
        if va == SWEEP_ROOT:
            rendered = instrument_root_entry(rendered, name)
        return phase5bb.rewrite_direct_frontier(
            base,
            rendered,
            generated,
            allowed_members,
        )

    def find_unknown(
        rendered_by_va: dict[int, str],
        member_list: list[int],
    ) -> tuple[dict[int, list[str]], dict[int, list[dict]]]:
        translated_names = {generated[va]["name"] for va in member_list}
        supplied = set(existing_defs) | translated_names
        unknown: dict[int, list[str]] = {}
        contexts: dict[int, list[dict]] = {}

        for va in member_list:
            row = generated[va]
            rendered = rendered_by_va[va]
            calls = set(base.CALL_RE.findall(base.mask_noncode(rendered)))
            calls.discard(row["name"])

            # Generated translated bodies can carry function-local helper
            # macros (notably the x87 fp_push/fp_pop/fp_top/fp_st family).
            # They are definitions, not unresolved runtime dependencies.
            # Phase 5BB already accounts for these with DEFINE_RE; preserve
            # that rule in the broad-sweep dependency audit.
            local_supplied = set(supplied)
            local_supplied.update(base.DEFINE_RE.findall(rendered))

            missing = sorted(
                name
                for name in calls
                if name not in local_supplied and name not in base.STANDARD_CALLS
            )
            if not missing:
                continue

            unknown[va] = missing
            lines = rendered.splitlines()
            owner_contexts = []
            for helper in missing:
                call_re = re.compile(rf"\b{re.escape(helper)}\s*\(")
                found = False
                for index, line in enumerate(lines):
                    if not call_re.search(line):
                        continue
                    found = True
                    first = max(0, index - 4)
                    last = min(len(lines), index + 5)
                    owner_contexts.append(
                        {
                            "helper": helper,
                            "first_line": first + 1,
                            "last_line": last,
                            "context": "\n".join(
                                f"{n + 1:04d}: {lines[n]}"
                                for n in range(first, last)
                            ),
                        }
                    )
                if not found:
                    owner_contexts.append(
                        {
                            "helper": helper,
                            "first_line": 0,
                            "last_line": 0,
                            "context": "<call not found in rendered source>",
                        }
                    )
            contexts[va] = owner_contexts

        return unknown, contexts

    # First render the complete candidate closure. A broad static closure can
    # legitimately include cold/side branches that require support we have not
    # modeled yet. Those members should not prevent the hardware sweep from
    # running through the support-clean portion of the graph.
    rendered_candidate: dict[int, str] = {}
    for va in candidate_members:
        rendered_candidate[va], _ = render_member(va, expanded_members)

    unsafe, unsafe_contexts = find_unknown(
        rendered_candidate,
        candidate_members,
    )

    if require_sweep_root and SWEEP_ROOT in unsafe:
        names = unsafe[SWEEP_ROOT]
        print(
            "[Phase5BC] sweep root 0x00237052 itself has unresolved support "
            f"dependencies: {', '.join(names)}"
        )
        for item in unsafe_contexts.get(SWEEP_ROOT, []):
            print(
                f"[Phase5BC]   helper={item['helper']} "
                f"source-lines={item['first_line']}-{item['last_line']}"
            )
            for line in item["context"].splitlines():
                print(f"[Phase5BC]     {line}")
        raise SystemExit(
            "[Phase5BC] broad-sweep seed requires a real support implementation; "
            "refusing to guess"
        )

    pruned = {
        va: names
        for va, names in unsafe.items()
        if va != SWEEP_ROOT
    }

    retained = [va for va in candidate_members if va not in pruned]
    if require_sweep_root:
        if not retained or SWEEP_ROOT not in retained:
            raise SystemExit("[Phase5BC] support-clean sweep unexpectedly lost root")
    elif not retained and candidate_members:
        raise SystemExit("[Phase5BC] support-clean sweep unexpectedly lost all candidates")

    # Mutate the caller-owned collections so all later manifest accounting and
    # lookup generation describe the actual pack, not merely the candidate set.
    if pruned:
        for va in pruned:
            expanded_members.discard(va)
        new_members[:] = retained

        print(
            "[Phase5BC] SUPPORT-CLEAN PRUNE: "
            f"candidate_new={len(candidate_members)} "
            f"pruned={len(pruned)} retained_new={len(retained)}"
        )
        for va in sorted(pruned):
            print(
                f"[Phase5BC]   fenced 0x{va:08X} {generated[va]['name']}: "
                + ", ".join(pruned[va])
            )

    # Re-render against the final retained pack. Direct calls into a pruned
    # translated member now become normal DIRECT_FRONTIER fences instead of
    # unresolved link dependencies.
    rendered_by_va: dict[int, str] = {}
    direct_frontiers: set[int] = set()
    for va in new_members:
        rendered, frontier = render_member(va, expanded_members)
        rendered_by_va[va] = rendered
        direct_frontiers.update(frontier)

    final_unknown, final_contexts = find_unknown(
        rendered_by_va,
        new_members,
    )
    if final_unknown:
        for va, names in final_unknown.items():
            print(
                f"[Phase5BC] retained member 0x{va:08X} "
                f"{generated[va]['name']} still has unresolved support: "
                + ", ".join(names)
            )
            for item in final_contexts.get(va, []):
                print(
                    f"[Phase5BC]   helper={item['helper']} "
                    f"source-lines={item['first_line']}-{item['last_line']}"
                )
                for line in item["context"].splitlines():
                    print(f"[Phase5BC]     {line}")
        raise SystemExit(
            "[Phase5BC] support-clean pruning did not converge; refusing unsafe pack"
        )

    lookup_marker = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    lookup_pos = main_text.find(lookup_marker)
    if lookup_pos < 0:
        raise SystemExit("[Phase5BC] pack lookup definition marker changed")

    declarations = "\n".join(
        f"static void {generated[va]['name']}(void);" for va in new_members
    )
    main_text = (
        main_text[:lookup_pos]
        + declarations
        + "\n\n"
        + main_text[lookup_pos:]
    )

    lookup_pos = main_text.find(lookup_marker)
    default_marker = "    default: return (recomp_func_t)0;"
    default_pos = main_text.find(default_marker, lookup_pos)
    if default_pos < 0:
        raise SystemExit("[Phase5BC] pack lookup default marker changed")

    lookup_cases = "".join(
        f"    case 0x{va:08X}u: return {generated[va]['name']};\n"
        for va in new_members
    )
    main_text = main_text[:default_pos] + lookup_cases + main_text[default_pos:]

    optimize_on = '#pragma optimize("", on)'
    optimize_pos = main_text.find(optimize_on, lookup_pos)
    if optimize_pos < 0:
        raise SystemExit("[Phase5BC] translated-body optimization marker changed")

    bodies = "\n\n".join(rendered_by_va[va] for va in new_members)
    main_text = (
        main_text[:optimize_pos]
        + bodies
        + "\n\n"
        + main_text[optimize_pos:]
    )

    return main_text, rendered_by_va, direct_frontiers, pruned

def patch_driver_contract(main_text: str) -> str:
    gate = "            s_phase5bbManualHeapAllocCount > 0u &&\n"
    replacement = (
        gate
        + "            s_phase5bcSweepRootEntered &&\n"
        + "            s_phase5bcPackedIcallDispatchCount > 0u &&\n"
    )
    if gate not in main_text:
        raise SystemExit("[Phase5BC] Phase 5BB PASS gate marker changed")
    main_text = main_text.replace(gate, replacement, 1)

    reset_marker = "    s_accessFault = 0;\n"
    reset = (
        reset_marker
        + "    s_phase5bcSweepRootEntered = 0;\n"
        + "    s_phase5bcPackedIcallDispatchCount = 0u;\n"
        + "    s_phase5bcPackedIcallLastTarget = 0u;\n"
        + "    s_phase5bcPackedIcallLastCaller = 0u;\n"
        + "    s_phase5bcPackedIcallLastSavedEsp = 0u;\n"
        + "    s_phase5bcPackedDirectDispatchCount = 0u;\n"
        + "    s_phase5bcPackedDirectLastTarget = 0u;\n"
        + "    s_phase5bcPackedDirectLastCaller = 0u;\n"
    )
    if reset_marker not in main_text:
        raise SystemExit("[Phase5BC] execution-state reset marker changed")
    main_text = main_text.replace(reset_marker, reset, 1)

    main_text = main_text.replace(
        "PHASE 5BB POST-PERSIST CLOSURE RESULT",
        "PHASE 5BC BROAD TRANSLATED SWEEP RESULT",
    )
    main_text = main_text.replace(
        "Policy: retain P5AM disk-data proof, add bounded Partition0 writeback, map cache Partition3/4/5, and execute a depth-2 closure rooted at 0022C5C6",
        "Policy: retain prior Phase-5 proofs, seed ICALL_SAFE 0022C3FA -> 00237052, sweep a depth-6/cap-256 exact generated closure, and auto-dispatch only exact targets already present in the widened pack",
    )
    main_text = main_text.replace(
        "P5BB-FRONTIER22DDA4-20261020-A",
        BUILD_TAG,
    )
    return main_text


def relabel_phase(main_text: str, env_text: str) -> tuple[str, str]:
    main_text = main_text.replace("phase5bb_env_build_cookie", "phase5bc_env_build_cookie")
    env_text = env_text.replace("phase5bb_env_build_cookie", "phase5bc_env_build_cookie")
    main_text = main_text.replace("50354242", "50354243")
    env_text = env_text.replace("50354242", "50354243")
    main_text = main_text.replace("PHASE 5BB", "PHASE 5BC")
    env_text = env_text.replace("PHASE 5BB", "PHASE 5BC")
    main_text = main_text.replace("Phase 5BB", "Phase 5BC")
    env_text = env_text.replace("Phase 5BB", "Phase 5BC")
    return main_text, env_text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-phase5bb-emitter", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--entry-report", type=Path, required=True)
    ap.add_argument("--thread-report", type=Path, required=True)
    ap.add_argument("--phase3n-template", type=Path, required=True)
    ap.add_argument("--phase2e-source", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load_module(args.base_emitter, "phase5bc_phase4c_base")
    phase5bb = load_module(args.base_phase5bb_emitter, "phase5bc_phase5bb_base")

    args.out_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="phase5bc-base-",
        dir=str(args.out_dir.parent),
    ) as temp_name:
        temp_dir = Path(temp_name)
        cmd = [
            sys.executable,
            str(args.base_phase5bb_emitter),
            "--base-emitter",
            str(args.base_emitter),
            "--generated-root",
            str(args.generated_root),
            "--functions",
            str(args.functions),
            "--entry-report",
            str(args.entry_report),
            "--thread-report",
            str(args.thread_report),
            "--phase3n-template",
            str(args.phase3n_template),
            "--phase2e-source",
            str(args.phase2e_source),
            "--out-dir",
            str(temp_dir),
        ]
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.returncode != 0:
            return completed.returncode

        base_main = temp_dir / "main.cpp"
        base_env = temp_dir / "phase5_env.cpp"
        base_manifest_path = temp_dir / "phase5bb-manifest.json"
        for required in (base_main, base_env, base_manifest_path):
            if not required.exists():
                raise SystemExit(
                    f"[Phase5BC] Phase 5BB base emitter did not produce {required.name}"
                )

        main_text = base_main.read_text(encoding="utf-8")
        env_text = base_env.read_text(encoding="utf-8")
        manifest = json.loads(base_manifest_path.read_text(encoding="utf-8"))

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact_generated_target(SWEEP_ROOT, by_va, generated)

    sweep_members = set(
        phase5bb.bounded_promoted_members(
            base,
            SWEEP_ROOT,
            generated,
            SWEEP_DIRECT_DEPTH,
            SWEEP_DIRECT_CAP,
        )
    )
    if SWEEP_ROOT not in sweep_members:
        raise SystemExit("[Phase5BC] sweep closure lost root 0x00237052")

    old_members = {int(item, 0) for item in manifest.get("members", [])}
    new_members = sorted(sweep_members - old_members)
    expanded_members = set(old_members) | sweep_members

    if not new_members:
        raise SystemExit(
            "[Phase5BC] broad sweep added no translated members; "
            "expected 0x00237052 to be new relative to Phase 5BB"
        )

    candidate_new_members = list(new_members)
    main_text, rendered_by_va, new_direct_frontiers, pruned_members = insert_pack_members(
        main_text,
        base,
        phase5bb,
        generated,
        new_members,
        expanded_members,
    )

    main_text = patch_direct_frontier(main_text)
    main_text = patch_safe_icall(main_text)
    main_text = patch_driver_contract(main_text)
    main_text, env_text = relabel_phase(main_text, env_text)

    required_main_markers = (
        BUILD_TAG,
        "case 0x00237052u: return sub_00237052;",
        "s_phase5bcSweepRootEntered = 1;",
        "PASS: Phase 5BC broad-sweep ICALL_SAFE",
        "PASS: Phase 5BC broad-sweep DIRECT",
        "s_phase5bcPackedIcallDispatchCount > 0u",
        "PHASE 5BC BROAD TRANSLATED SWEEP RESULT",
    )
    for marker in required_main_markers:
        if marker not in main_text:
            raise SystemExit(
                f"[Phase5BC] generated main lost required broad-sweep marker: {marker}"
            )

    if "PHASE 5BC RETAIL ENVIRONMENT PREP START" not in env_text:
        raise SystemExit("[Phase5BC] environment phase label patch failed")
    if "phase5bc_env_build_cookie" not in env_text or "50354243" not in env_text:
        raise SystemExit("[Phase5BC] environment cookie patch failed")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "5BC"
    manifest["build_tag"] = BUILD_TAG
    manifest["pack_members"] = len(expanded_members)
    manifest["members"] = [f"0x{va:08X}" for va in sorted(expanded_members)]
    manifest["phase5bc_broad_sweep"] = {
        "observed_phase": "5BB",
        "boundary_kind": "ICALL_SAFE",
        "observed_caller": "0x0022C3FA",
        "root": "0x00237052",
        "observed_fault": 0,
        "observed_esp": "0x008BFF48",
        "observed_saved_esp": "0x008BFF4C",
        "direct_closure_depth": SWEEP_DIRECT_DEPTH,
        "direct_closure_cap": SWEEP_DIRECT_CAP,
        "base_pack_members": len(old_members),
        "sweep_members": len(sweep_members),
        "candidate_new_members": len(candidate_new_members),
        "new_members": len(new_members),
        "pruned_members": len(pruned_members),
        "expanded_pack_members": len(expanded_members),
        "auto_dispatch": {
            "safe_icall": "exact target must resolve through phase4c_lookup_pack_func",
            "previously_fenced_direct": "exact target must resolve through phase4c_lookup_pack_func",
            "ordinary_icall": "fenced",
            "itail": "fenced",
            "itail_safe": "fenced",
        },
        "hard_stops": [
            "unknown kernel/device behavior",
            "mid-function or non-generated target",
            "guest-memory fault",
            "heap exhaustion",
            "kernel/frame ABI mismatch",
            "unknown indirect target",
            "execution budget",
            "debug break",
        ],
        "execution_budget_blocks": 200000,
        "pass_policy": (
            "all retained Phase 5BB invariants must hold; 0x00237052 must "
            "actually enter through generic packed ICALL_SAFE dispatch; stop "
            "only at a newer real boundary"
        ),
    }
    manifest["phase5bc_sweep_members"] = [
        f"0x{va:08X}" for va in sorted(sweep_members)
    ]
    manifest["phase5bc_candidate_new_members"] = [
        f"0x{va:08X}" for va in candidate_new_members
    ]
    manifest["phase5bc_new_members"] = [
        f"0x{va:08X}" for va in new_members
    ]
    manifest["phase5bc_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned_members.items())
    ]
    manifest["phase5bc_new_direct_frontier_targets"] = [
        f"0x{va:08X}" for va in sorted(new_direct_frontiers)
    ]

    (args.out_dir / "phase5bc-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    total_new_source = sum(len(rendered_by_va[va]) for va in new_members)
    print(
        "[Phase5BC] BROAD SWEEP PACK: "
        f"base={len(old_members)} sweep={len(sweep_members)} "
        f"candidate_new={len(candidate_new_members)} "
        f"pruned={len(pruned_members)} new={len(new_members)} "
        f"total={len(expanded_members)} "
        f"new_source_bytes={total_new_source}"
    )
    print(
        "[Phase5BC] AUTO-DISPATCH: exact packed ICALL_SAFE + "
        "previously fenced exact packed direct targets"
    )
    print(
        "[Phase5BC] HARD STOPS RETAINED: unknown indirect/kernel/device, "
        "guest fault, ABI/frame mismatch, heap exhaustion, debug break, "
        "and 200000-block execution budget"
    )
    print("[Phase5BC] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

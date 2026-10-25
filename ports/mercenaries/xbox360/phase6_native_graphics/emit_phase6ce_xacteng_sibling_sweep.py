#!/usr/bin/env python3
"""Phase 6CE: broad support-clean XACTENG sibling sweep from 0x0027DB5C.

6CD ran fault-free for 26,711,180 translated ticks, far beyond the former 8M
watchdog, and stopped on a genuine DIRECT_FRONTIER:
  caller=0x0023A3CE target=0x0027DB5C
  esp=saved_esp=0x008BF98C fault=0

0x0027DB5C lies inside XACTENG (0x0027D5C0-0x00288630). The final 6CD VA ring
also proved execution was already traversing XACTENG/DSOUND-adjacent startup
code. Rather than promote one function, 6CE enumerates every still-unpacked
exact generated XACTENG function, prioritizes the live root and all entries
after it, then uses remaining capacity on pre-frontier siblings.

The existing support-clean pruner remains authoritative. Missing bodies,
interior entries, unresolved helpers, platform/NV2A/ABI boundaries and guest
faults remain hard stops.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CD-LONGRUN32M-20261025-A"
BUILD_TAG = "P6CE-XACTENG-SIBLING-SWEEP-0027DB5C-20261025-A"
COOKIE_OLD = "phase6cd_env_build_cookie"
COOKIE_NEW = "phase6ce_env_build_cookie"

ROOT = 0x0027DB5C
CALLER = 0x0023A3CE
XACT_START = 0x0027D5C0
XACT_END = 0x00288630
SWEEP_CAP = 1024


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CE] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CE] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def validate_root(root: int, by_va: dict, generated: dict) -> None:
    if not (XACT_START <= root < XACT_END):
        raise SystemExit(
            f"[Phase6CE] target 0x{root:08X} outside XACTENG "
            f"0x{XACT_START:08X}-0x{XACT_END:08X}"
        )

    row = by_va.get(root)
    if row is None:
        owners = [
            r for r in by_va.values()
            if int(r["start"]) < root < int(r["end"])
        ]
        if owners:
            owner = sorted(owners, key=lambda x: int(x["start"]))[-1]
            start = int(owner["start"])
            end = int(owner["end"])
            state = "generated" if start in generated else "not-generated"
            raise SystemExit(
                f"[Phase6CE] XACTENG target 0x{root:08X} is an interior entry; "
                f"owner=0x{start:08X}-0x{end:08X} {owner['name']} ({state}). "
                "Refusing to redirect an interior entry to a function prologue."
            )
        raise SystemExit(
            f"[Phase6CE] XACTENG target 0x{root:08X} absent from function inventory"
        )

    if root not in generated:
        raise SystemExit(
            f"[Phase6CE] XACTENG target 0x{root:08X} is exact function "
            f"{row['name']} but has no generated translated body"
        )


def install_state(text: str) -> str:
    anchor = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CE] expected one pack lookup anchor, found {text.count(anchor)}"
        )
    state = """static uint32_t s_phase6ceXactRootEntries = 0u;
static uint32_t s_phase6ceXactLastEsp = 0u;
static uint32_t s_phase6ceXactLastEax = 0u;
static uint32_t s_phase6ceXactLastEcx = 0u;
static uint32_t s_phase6ceXactLastEdx = 0u;

"""
    return text.replace(anchor, state + anchor, 1)


def instrument_root(rendered: str, name: str) -> str:
    name_pos = rendered.find(name)
    brace_pos = rendered.find("{", name_pos)
    if name_pos < 0 or brace_pos < 0:
        raise SystemExit("[Phase6CE] could not instrument XACTENG root")

    probe = r'''
    ++s_phase6ceXactRootEntries;
    s_phase6ceXactLastEsp = g_esp;
    s_phase6ceXactLastEax = g_eax;
    s_phase6ceXactLastEcx = g_ecx;
    s_phase6ceXactLastEdx = g_edx;
    if (s_phase6ceXactRootEntries == 1u)
    {
        char phase6ceLine[320];
        sprintf(
            phase6ceLine,
            "PASS: Phase 6CE entered XACTENG frontier 0027DB5C eax=%08X ecx=%08X edx=%08X esp=%08X",
            (unsigned int)g_eax,
            (unsigned int)g_ecx,
            (unsigned int)g_edx,
            (unsigned int)g_esp);
        trace(phase6ceLine);
    }
'''
    return rendered[:brace_pos + 1] + probe + rendered[brace_pos + 1:]


def insert_summary(text: str) -> str:
    marker = "P6CD HOT PROFILE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CE] inherited 6CD hot-profile summary missing")

    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6CE] could not locate final summary insertion point")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CE XACTENG ROOT: entries=%u eax=%08X ecx=%08X edx=%08X esp=%08X",\n'
        f'{indent}    (unsigned int)s_phase6ceXactRootEntries,\n'
        f'{indent}    (unsigned int)s_phase6ceXactLastEax,\n'
        f'{indent}    (unsigned int)s_phase6ceXactLastEcx,\n'
        f'{indent}    (unsigned int)s_phase6ceXactLastEdx,\n'
        f'{indent}    (unsigned int)s_phase6ceXactLastEsp);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase5bb-emitter", type=Path, required=True)
    ap.add_argument("--phase5bc-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6ce_base")
    p5bb = load(args.phase5bb_emitter, "phase6ce_p5bb")
    p5bc = load(args.phase5bc_emitter, "phase6ce_p5bc")
    p6bl = load(args.phase6bl_emitter, "phase6ce_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cd-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CE] missing cached 6CD input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    env_before = env_text
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CD" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CE] cached Phase 6CD identity mismatch")

    p6cd = manifest.get("phase6cd_longrun32m", {})
    if (
        p6cd.get("new_budget_ticks") != 32000000
        or p6cd.get("translated_membership_changed") is not False
        or p6cd.get("hard_fences_changed") is not False
    ):
        raise SystemExit("[Phase6CE] inherited 6CD policy identity mismatch")

    members = list(manifest.get("members", []))
    if not members or int(manifest.get("pack_members", 0)) != len(members):
        raise SystemExit("[Phase6CE] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "P6CD HOT PROFILE:",
        "P6CD MANUAL PBL TRIG:",
        "(s_phase5bcPackedIcallDispatchCount & 0xFFFu) == 0u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CE] inherited 6CD marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_root(ROOT, by_va, generated)

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    old = {int(x, 0) for x in members}
    if ROOT in old:
        raise SystemExit(
            "[Phase6CE] root 0x0027DB5C is already in inherited pack; "
            "runtime frontier bookkeeping must be inspected"
        )

    xact_generated = sorted(
        va for va in generated
        if XACT_START <= va < XACT_END
    )
    remaining = [va for va in xact_generated if va not in old]
    if ROOT not in remaining:
        raise SystemExit(
            "[Phase6CE] root is not an unpacked exact generated XACTENG start"
        )

    forward = [ROOT] + [va for va in remaining if va > ROOT]
    prefrontier = [va for va in remaining if va < ROOT]
    candidate_order = forward + prefrontier
    candidate_new = candidate_order[:SWEEP_CAP]
    truncated = max(0, len(candidate_order) - len(candidate_new))

    if ROOT not in candidate_new:
        raise SystemExit("[Phase6CE] XACTENG sweep lost mandatory root")

    expanded = old | set(candidate_new)
    new_members = list(candidate_new)

    main_text = install_state(main_text)

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument_root
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text,
        base,
        p5bb,
        generated,
        new_members,
        expanded,
    )

    if ROOT not in new_members:
        names = pruned.get(ROOT, [])
        joined = ", ".join(str(x) for x in names) if names else "<unknown>"
        raise SystemExit(
            f"[Phase6CE] support-clean pruning removed mandatory XACTENG root; "
            f"unresolved support={joined}"
        )

    main_text = insert_summary(main_text)

    old_policy = (
        "Policy: Phase 6CD long-run continuation after fault-free 6CC budget stop; "
        "preserve translated membership/manual PblMath/graphics/file/IDEX/IRQL/allocator "
        "semantics, raise watchdog 8M->32M, reduce broad-sweep log cadence to 4096, "
        "and profile recurring runtime regions while all genuine hard fences remain armed"
    )
    new_policy = (
        "Policy: Phase 6CE starts from hardware-proven 6CD 26.7M-tick DIRECT_FRONTIER "
        "0027DB5C and sweeps remaining exact generated XACTENG siblings with a 1024-member "
        "candidate cap under support-clean pruning; preserve the 32M watchdog, quiet "
        "dispatch logging, manual PblMath, graphics/file/IDEX/IRQL/allocator semantics "
        "and every genuine hard fence"
    )
    main_text = replace_once(main_text, old_policy, new_policy, "runtime policy")
    main_text = replace_once(main_text, BASE_TAG, BUILD_TAG, "build tag")

    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6CD", "PHASE 6CE")
        .replace("Phase 6CD", "Phase 6CE")
        .replace('"P6CD ', '"P6CE ')
    )
    env_text = (
        env_text.replace("PHASE 6CD", "PHASE 6CE")
        .replace("Phase 6CD", "Phase 6CE")
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "case 0x0027DB5Cu:",
        "PASS: Phase 6CE entered XACTENG frontier 0027DB5C",
        "P6CE XACTENG ROOT:",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "(s_phase5bcPackedIcallDispatchCount & 0xFFFu) == 0u",
        "case 0x001F9D70u: return phase6cc_pbl_sin_001f9d70;",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6CE] generated source lost marker: {marker}")

    expected_env = (
        env_before.replace(COOKIE_OLD, COOKIE_NEW)
        .replace("PHASE 6CD", "PHASE 6CE")
        .replace("Phase 6CD", "Phase 6CE")
    )
    if env_text != expected_env:
        raise SystemExit(
            "[Phase6CE] phase5_env.cpp changed beyond expected tag/cookie renames"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6CE",
            "build_tag": BUILD_TAG,
            "pack_members": len(old | set(new_members)),
            "members": [
                f"0x{x:08X}" for x in sorted(old | set(new_members))
            ],
        }
    )
    manifest["phase6ce_xacteng_sibling_sweep"] = {
        "source_phase": "6CD",
        "phase6cd_hardware": {
            "boundary_kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x0027DB5C",
            "esp": "0x008BF98C",
            "saved_esp": "0x008BF98C",
            "ticks": 26711180,
            "trace": 1017495,
            "fault": 0,
            "eax": "0x01B5C320",
            "ecx": "0x01B5C320",
            "edx": "0x01B5C320",
            "ebx": "0x00000001",
            "esi": "0x00000000",
            "edi": "0x0070000C",
            "xapi_return": 0,
        },
        "root": f"0x{ROOT:08X}",
        "root_name": generated[ROOT]["name"],
        "frontier_caller": f"0x{CALLER:08X}",
        "target_section": "XACTENG",
        "target_section_start": f"0x{XACT_START:08X}",
        "target_section_end": f"0x{XACT_END:08X}",
        "candidate_cap": SWEEP_CAP,
        "total_generated_xacteng_members": len(xact_generated),
        "remaining_generated_xacteng_members": len(remaining),
        "forward_remaining_members": len(forward),
        "prefrontier_remaining_members": len(prefrontier),
        "selected_candidate_members": len(candidate_new),
        "truncated_candidate_members": truncated,
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(old | set(new_members)),
        "new_direct_frontier_targets": [
            f"0x{x:08X}" for x in sorted(frontiers)
        ],
        "execution_budget_inherited": 32000000,
        "dispatch_log_stride_inherited": 4096,
        "phase_owned_crt_support": ["cos", "sin"],
        "manual_pbl_semantics_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "hard_fences_changed": False,
        "source_layout": layout,
        "runtime_policy": (
            "exact generated XACTENG sibling sweep with support-clean pruning; "
            "interior-entry, missing-body, unresolved-support, NV2A/platform/ABI "
            "and guest-memory faults remain hard stops"
        ),
    }
    manifest["phase6ce_candidate_new_members"] = [
        f"0x{x:08X}" for x in candidate_new
    ]
    manifest["phase6ce_new_members"] = [
        f"0x{x:08X}" for x in sorted(new_members)
    ]
    manifest["phase6ce_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6ce-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    total_source = sum(len(rendered[va]) for va in new_members)
    print(
        f"[Phase6CE] XACTENG SIBLING SWEEP: root=0x{ROOT:08X} "
        f"name={generated[ROOT]['name']} total_generated={len(xact_generated)} "
        f"remaining={len(remaining)} selected={len(candidate_new)} "
        f"truncated={truncated} pruned={len(pruned)} "
        f"packed_new={len(new_members)} total_pack={len(old | set(new_members))} "
        f"new_source_bytes={total_source}"
    )
    print("[Phase6CE] 6CD provenance: DIRECT_FRONTIER at 26,711,180 ticks; fault=0")
    print("[Phase6CE] 32M execution budget preserved")
    print("[Phase6CE] 4096-dispatch quiet logging preserved")
    print(
        "[Phase6CE] HARD STOPS: interior/missing XACTENG body / unresolved support "
        "/ NV2A / ABI / guest fault"
    )
    print("[Phase6CE] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

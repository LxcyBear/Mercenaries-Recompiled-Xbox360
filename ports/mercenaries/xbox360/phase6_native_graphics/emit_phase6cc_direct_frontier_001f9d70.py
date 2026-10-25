#!/usr/bin/env python3
"""Phase 6CC: promote the hardware-proven DIRECT_FRONTIER 0x001F9D70.

6CB hardware proved the synthetic FILE_OBJECT lifecycle is balanced:
  ObReferenceObjectByHandle -> 0x04000000 sentinel
  KeRaiseIrqlToDpcLevel 0 -> 2
  KfLowerIrql 2 -> 0
  ObfDereferenceObject sentinel release -> outstanding 0
  NtClose(handle=0x48000001) -> success

Execution then advanced fault-free to a normal translated direct frontier:
  caller 0x0023A3CE -> target 0x001F9D70
  esp=saved_esp=0x008BF988
  ticks=956060 trace=180293 fault=0

6CC does not emulate this target. It validates 0x001F9D70 as an exact
generated function start and packs a bounded support-clean generated closure.
Unknown support remains a hard stop.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CB-OBFDEREF250-SENTINEL-20261024-A"
BUILD_TAG = "P6CC-DIRECT-FRONTIER-001F9D70-20261024-A"
COOKIE_OLD = "phase6cb_env_build_cookie"
COOKIE_NEW = "phase6cc_env_build_cookie"

ROOT = 0x001F9D70
CALLER = 0x0023A3CE
ROOT_DEPTH = 4
ROOT_CAP = 256


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CC] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CC] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def validate_exact(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < root < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                f"[Phase6CC] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "Refusing to redirect an interior entry to a prologue."
            )
        raise SystemExit(
            f"[Phase6CC] target 0x{root:08X} is absent from function inventory"
        )
    if root not in generated:
        raise SystemExit(
            f"[Phase6CC] target 0x{root:08X} is exact function "
            f"{by_va[root]['name']} but has no generated translated body"
        )


def install_state(text: str) -> str:
    marker = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6CC] expected one lookup anchor, found {text.count(marker)}"
        )
    state = """static uint32_t s_phase6ccRootEnterCount = 0u;
static uint32_t s_phase6ccRootLastEax = 0u;
static uint32_t s_phase6ccRootLastEcx = 0u;
static uint32_t s_phase6ccRootLastEdx = 0u;
static uint32_t s_phase6ccRootLastEsp = 0u;

"""
    return text.replace(marker, state + marker, 1)


def instrument_root(rendered: str, name: str) -> str:
    name_pos = rendered.find(name)
    brace_pos = rendered.find("{", name_pos)
    if name_pos < 0 or brace_pos < 0:
        raise SystemExit("[Phase6CC] could not instrument root 0x001F9D70")

    probe = r'''
    ++s_phase6ccRootEnterCount;
    s_phase6ccRootLastEax = g_eax;
    s_phase6ccRootLastEcx = g_ecx;
    s_phase6ccRootLastEdx = g_edx;
    s_phase6ccRootLastEsp = g_esp;
    if (s_phase6ccRootEnterCount == 1u)
    {
        char phase6ccLine[320];
        sprintf(
            phase6ccLine,
            "PASS: Phase 6CC entered translated direct frontier 001F9D70 eax=%08X ecx=%08X edx=%08X esp=%08X",
            (unsigned int)g_eax,
            (unsigned int)g_ecx,
            (unsigned int)g_edx,
            (unsigned int)g_esp);
        trace(phase6ccLine);
    }
'''
    return rendered[:brace_pos + 1] + probe + rendered[brace_pos + 1:]


def insert_summary(text: str) -> str:
    marker = "P6CB OBFDEREF250:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CC] inherited ObfDereference summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6CC] could not locate inherited summary block")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CC DIRECT FRONTIER 001F9D70: entries=%u eax=%08X ecx=%08X edx=%08X esp=%08X",\n'
        f'{indent}    (unsigned int)s_phase6ccRootEnterCount,\n'
        f'{indent}    (unsigned int)s_phase6ccRootLastEax,\n'
        f'{indent}    (unsigned int)s_phase6ccRootLastEcx,\n'
        f'{indent}    (unsigned int)s_phase6ccRootLastEdx,\n'
        f'{indent}    (unsigned int)s_phase6ccRootLastEsp);\n'
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

    base = load(args.base_emitter, "phase6cc_base")
    p5bb = load(args.phase5bb_emitter, "phase6cc_p5bb")
    p5bc = load(args.phase5bc_emitter, "phase6cc_p5bc")
    p6bl = load(args.phase6bl_emitter, "phase6cc_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cb-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CC] cached Phase 6CB input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    env_before = env_text
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CB" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CC] cached Phase 6CB identity mismatch")

    obfderef = manifest.get("phase6cb_obf_dereference_object", {})
    if (
        obfderef.get("phase6ca_hardware", {}).get("next_boundary_target")
        != "0x800000FA"
        or obfderef.get("continuation", {}).get("expected_object")
        != "0x04000000"
    ):
        raise SystemExit("[Phase6CC] inherited 6CB sentinel-release identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6CC] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "_phase4c_target == 0x800000FAu",
        "PASS: Phase 6CB ObfDereferenceObject sentinel release",
        "P6CB OBFDEREF250:",
        "P6CB KFLOWERIRQL161:",
        "P6CB IDEX QUEUE HEAD:",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CC] inherited 6CB marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact(ROOT, by_va, generated)
    validate_exact(CALLER, by_va, generated)

    # Preserve previously accepted native CRT math calls during support audit.
    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    old = {int(x, 0) for x in members}
    if ROOT in old:
        raise SystemExit(
            "[Phase6CC] root 0x001F9D70 is already in inherited pack; "
            "dispatch bookkeeping must be inspected instead of repacking it"
        )

    closure = set(
        p5bb.bounded_promoted_members(
            base, ROOT, generated, ROOT_DEPTH, ROOT_CAP
        )
    )
    closure.add(ROOT)
    candidate_new = sorted(va for va in closure if va not in old)
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6CC] closure construction lost mandatory root")

    new_members = list(candidate_new)
    expanded = old | set(new_members)

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
            f"[Phase6CC] support-clean pruning removed mandatory root "
            f"0x{ROOT:08X}; unresolved support={joined}"
        )

    main_text = insert_summary(main_text)
    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6CC promote hardware-proven DIRECT_FRONTIER 0023A3CE -> 001F9D70 as exact generated game code with bounded depth-4/cap-256 support-clean closure; preserve 6CB balanced FILE_OBJECT release, graphics/file/fence/allocator semantics and 8M execution budget",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6CB", "PHASE 6CC")
        .replace("Phase 6CB", "Phase 6CC")
        .replace('"P6CB ', '"P6CC ')
    )
    env_text = (
        env_text.replace("PHASE 6CB", "PHASE 6CC")
        .replace("Phase 6CB", "Phase 6CC")
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "case 0x001F9D70u:",
        "PASS: Phase 6CC entered translated direct frontier 001F9D70",
        "P6CC DIRECT FRONTIER 001F9D70:",
        "P6CC OBFDEREF250:",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CC] generated source lost marker: {marker}")

    expected_env = (
        env_before.replace(COOKIE_OLD, COOKIE_NEW)
        .replace("PHASE 6CB", "PHASE 6CC")
        .replace("Phase 6CB", "Phase 6CC")
    )
    if env_text != expected_env:
        raise SystemExit(
            "[Phase6CC] phase5_env.cpp changed beyond expected tag/cookie renames"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6CC",
            "build_tag": BUILD_TAG,
            "pack_members": len(expanded),
            "members": [f"0x{x:08X}" for x in sorted(expanded)],
        }
    )
    manifest["phase6cc_direct_frontier"] = {
        "source_phase": "6CB",
        "phase6cb_hardware": {
            "obf_dereference_calls": 1,
            "obf_dereference_successes": 1,
            "synthetic_object": "0x04000000",
            "synthetic_outstanding": 0,
            "ntclose_handle": "0x48000001",
            "ntclose_status": "0x00000000",
            "next_boundary_kind": "DIRECT_FRONTIER",
            "next_boundary_caller": "0x0023A3CE",
            "next_boundary_target": "0x001F9D70",
            "boundary_esp": "0x008BF988",
            "boundary_saved_esp": "0x008BF988",
            "boundary_eax": "0x0085BC44",
            "boundary_ecx": "0x0085BC04",
            "boundary_edx": "0x00000002",
            "fault": 0,
            "ticks": 956060,
            "trace": 180293,
            "xapi_return": 0,
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
        "new_direct_frontier_targets": [
            f"0x{x:08X}" for x in sorted(frontiers)
        ],
        "translated_membership_changed": True,
        "phase5_env_semantics_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
        "runtime_policy": (
            "exact generated root/closure only; support-clean pruning authoritative; "
            "unknown helper/NV2A/platform/ABI/guest-fault boundaries remain hard stops"
        ),
    }
    manifest["phase6cc_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6cc-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"[Phase6CC] DIRECT FRONTIER PACK: root=0x{ROOT:08X} "
        f"name={generated[ROOT]['name']} candidates={len(candidate_new)} "
        f"pruned={len(pruned)} packed_new={len(new_members)} "
        f"total_pack={len(expanded)}"
    )
    print(
        f"[Phase6CC] NEW DIRECT FRONTIERS: "
        + (
            ", ".join(f"0x{x:08X}" for x in sorted(frontiers))
            if frontiers else "<none in packed closure>"
        )
    )
    print("[Phase6CC] 6CB hardware provenance: fault=0 ticks=956060 trace=180293")
    print("[Phase6CC] execution budget: inherited 8000000 ticks")
    print("[Phase6CC] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

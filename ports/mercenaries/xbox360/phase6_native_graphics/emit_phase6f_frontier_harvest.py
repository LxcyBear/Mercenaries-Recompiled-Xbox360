#!/usr/bin/env python3
'''Phase 6F: batched translated frontier harvester.

Hardware-proven Phase 6E advanced fault-free through 0x0014E770 and stopped at
DIRECT_FRONTIER 0x0023A3CE -> 0x00150E40. 6F promotes that exact root, keeps
the native Xenos device alive, and pre-packs a wider support-clean translated
neighborhood so ordinary direct/frontier siblings can be crossed in one
hardware run. Genuine NV2A, kernel/device, ABI, guest-fault, and missing-body
boundaries remain hard stops.
'''
from __future__ import annotations
import argparse, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

BUILD_TAG = "P6F-FRONTIER-HARVEST-00150E40-20261021-A"
ROOT = 0x00150E40
REGION_START = 0x0014C000
REGION_END = 0x00180000
DIRECT_DEPTH = 12
DIRECT_CAP = 256
TOTAL_NEW_CAP = 256

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6F] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def validate(root, by_va, generated):
    if root not in by_va:
        hit = [r for r in by_va.values() if int(r["start"]) < root < int(r["end"])]
        if hit:
            r = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6F] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(r['start']):08X}-0x{int(r['end']):08X} {r['name']}"
            )
        raise SystemExit(f"[Phase6F] target 0x{root:08X} is absent from function inventory")
    if root not in generated:
        raise SystemExit(
            f"[Phase6F] target 0x{root:08X} is an exact function start "
            f"({by_va[root]['name']}) but has no generated translated body"
        )

def instrument(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6F] could not instrument root 0x00150E40")
    return rendered[:b + 1] + "\n    s_phase6fRootEntered = 1;" + rendered[b + 1:]

def replace_flag(argv, flag, value):
    out = list(argv)
    i = out.index(flag)
    out[i + 1] = str(value)
    return out

def remove_flag(argv, flag):
    out = list(argv)
    i = out.index(flag)
    del out[i:i + 2]
    return out

def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--base-phase6e-emitter", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bb-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bc-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args, _ = ap.parse_known_args()

    base = load(args.base_emitter, "phase6f_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6f_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6f_p5bc")
    args.out_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="phase6f-base-", dir=str(args.out_dir.parent)) as td:
        td = Path(td)
        forwarded = remove_flag(sys.argv[1:], "--base-phase6e-emitter")
        forwarded = replace_flag(forwarded, "--out-dir", td)
        cp = subprocess.run(
            [sys.executable, str(args.base_phase6e_emitter), *forwarded],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if cp.stdout:
            print(cp.stdout, end="")
        if cp.returncode:
            return cp.returncode

        main_path = td / "main.cpp"
        env_path = td / "phase5_env.cpp"
        mf_path = td / "phase6e-manifest.json"
        for p in (main_path, env_path, mf_path):
            if not p.exists():
                raise SystemExit(f"[Phase6F] Phase 6E base emitter did not produce {p.name}")

        main_text = main_path.read_text(encoding="utf-8")
        env_text = env_path.read_text(encoding="utf-8")
        manifest = json.loads(mf_path.read_text(encoding="utf-8"))

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate(ROOT, by_va, generated)

    old = {int(x, 0) for x in manifest.get("members", [])}
    if ROOT in old:
        raise SystemExit("[Phase6F] 0x00150E40 already packed by Phase 6E")

    direct = set(
        p5bb.bounded_promoted_members(
            base,
            ROOT,
            generated,
            DIRECT_DEPTH,
            DIRECT_CAP,
        )
    )
    direct.add(ROOT)

    regional = [
        va
        for va in generated
        if REGION_START <= va < REGION_END and va not in old
    ]
    # The observed hardware frontier chain is monotonically moving forward in
    # this band. Prefer addresses at/above the new root, then nearest backward
    # neighbors only if the forward side does not fill the batch.
    regional.sort(key=lambda va: (va < ROOT, abs(va - ROOT), va))

    candidate_order = []
    for va in sorted(direct, key=lambda value: (value != ROOT, value)):
        if va not in old and va not in candidate_order:
            candidate_order.append(va)
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break

    for va in regional:
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in candidate_order:
            candidate_order.append(va)

    if ROOT not in candidate_order:
        candidate_order.insert(0, ROOT)
    if len(candidate_order) > TOTAL_NEW_CAP:
        candidate_order = candidate_order[:TOTAL_NEW_CAP]
        if ROOT not in candidate_order:
            candidate_order[-1] = ROOT

    candidate_new = sorted(set(candidate_order))
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6F] candidate batch lost mandatory root 0x00150E40")

    expanded = old | set(candidate_new)
    new_members = list(candidate_new)

    marker = "static int s_phase6eRootEntered;"
    if marker not in main_text:
        raise SystemExit("[Phase6F] Phase 6E root-state marker changed")
    main_text = main_text.replace(marker, marker + "\nstatic int s_phase6fRootEntered;", 1)

    marker = "    s_phase6eRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6F] Phase 6E reset marker changed")
    main_text = main_text.replace(marker, marker + "    s_phase6fRootEntered = 0;\n", 1)

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
        raise SystemExit("[Phase6F] support-clean pruning removed mandatory root 0x00150E40")

    old_result = '''    if (s_phase6eRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6E GRAPHICS FRONTIER RESULT: PASS");
    else
        trace("PHASE 6E GRAPHICS FRONTIER RESULT: FAIL");'''
    new_result = '''    if (s_phase6fRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6F FRONTIER HARVEST RESULT: PASS");
    else
        trace("PHASE 6F FRONTIER HARVEST RESULT: FAIL");'''
    if old_result not in main_text:
        raise SystemExit("[Phase6F] Phase 6E result gate changed")
    main_text = main_text.replace(old_result, new_result, 1)

    old_policy = (
        "Policy: inherit the hardware-proven Phase 6E runtime/Xenos path, add exact direct frontier "
        "0014E770 plus a bounded direct closure, keep the native Xenos device alive, and stop at the "
        "next genuine graphics/platform/ABI boundary without fabricating backend success"
    )
    new_policy = (
        "Policy: inherit the hardware-proven prior Phase-6E runtime/Xenos path, seed exact frontier "
        "00150E40, pre-pack a support-clean forward-biased translated neighborhood, automatically "
        "continue only through exact packed targets, and hard-stop on genuine NV2A/platform/ABI/"
        "guest-fault or missing-body boundaries without fabricating success"
    )
    if old_policy not in main_text:
        raise SystemExit("[Phase6F] Phase 6E policy marker changed")

    main_text = main_text.replace(
        "P6E-GRAPHICS-FRONTIER-0014E770-20261021-A",
        BUILD_TAG,
        1,
    )
    main_text = main_text.replace(old_policy, new_policy, 1)
    main_text = main_text.replace("phase6e_env_build_cookie", "phase6f_env_build_cookie")
    env_text = env_text.replace("phase6e_env_build_cookie", "phase6f_env_build_cookie")
    main_text = main_text.replace("50364545", "50364646")
    env_text = env_text.replace("50364545", "50364646")
    main_text = main_text.replace("PHASE 6E", "PHASE 6F").replace("Phase 6E", "Phase 6F").replace('"P6E ', '"P6F ')
    env_text = env_text.replace("PHASE 6E", "PHASE 6F").replace("Phase 6E", "Phase 6F")

    required = (
        BUILD_TAG,
        "case 0x00150E40u: return sub_00150E40;",
        "s_phase6fRootEntered = 1;",
        "P6F XENOS: PASS Direct3D_CreateDevice",
        "P6F FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6F FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "PHASE 6F FRONTIER HARVEST RESULT",
        "PASS: Phase 6F broad-sweep DIRECT",
        "PASS: Phase 6F broad-sweep ICALL_SAFE",
    )
    for x in required:
        if x not in main_text:
            raise SystemExit(f"[Phase6F] generated main lost marker: {x}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6F",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6f_frontier_harvest"] = {
        "source_phase": "6E",
        "phase6e_hardware_pass": True,
        "phase6e_observed_boundary": {
            "kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x00150E40",
            "esp": "0x008BFF40",
            "saved_esp": "0x008BFF40",
            "fault": 0,
            "ticks": 75040,
            "trace": 7446,
        },
        "root": f"0x{ROOT:08X}",
        "root_name": generated[ROOT]["name"],
        "region_start": f"0x{REGION_START:08X}",
        "region_end_exclusive": f"0x{REGION_END:08X}",
        "direct_closure_depth": DIRECT_DEPTH,
        "direct_closure_cap": DIRECT_CAP,
        "total_new_cap": TOTAL_NEW_CAP,
        "base_pack_members": len(old),
        "direct_candidate_members": len(direct - old),
        "regional_generated_candidates": len(regional),
        "candidate_new_members": len(candidate_new),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(expanded),
        "new_direct_frontier_targets": [f"0x{x:08X}" for x in sorted(frontiers)],
        "xenos_surface_inherited": True,
        "strategy": (
            "mandatory Phase-6E hardware frontier root plus depth-12 direct closure, "
            "then forward-biased nearest still-unpacked exact generated entries from "
            "0x0014C000..0x0017FFFF up to 256 total new members; unresolved-support "
            "members are pruned rather than stubbed"
        ),
        "runtime_policy": (
            "generic exact-packed DIRECT and ICALL_SAFE targets continue automatically; "
            "NV2A MMIO/VRAM, unknown platform/kernel/device semantics, ABI/frame failure, "
            "guest fault, or genuinely missing translated body remain hard stops"
        ),
    }
    manifest["phase6f_candidate_new_members"] = [f"0x{x:08X}" for x in candidate_new]
    manifest["phase6f_new_members"] = [f"0x{x:08X}" for x in sorted(new_members)]
    manifest["phase6f_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6f-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    total_new_source = sum(len(rendered[va]) for va in new_members)
    print(
        f"[Phase6F] FRONTIER HARVEST PACK: base={len(old)} "
        f"direct_candidates={len(direct - old)} regional_candidates={len(regional)} "
        f"candidate_new={len(candidate_new)} pruned={len(pruned)} "
        f"packed_new={len(new_members)} total={len(expanded)} "
        f"new_source_bytes={total_new_source}"
    )
    print(
        "[Phase6F] AUTO-DISPATCH: exact packed DIRECT + ICALL_SAFE targets continue "
        "without requiring one-build-per-address"
    )
    print(
        "[Phase6F] REGION: 0x0014C000-0x0017FFFF, mandatory root 0x00150E40, "
        "forward-biased fill, cap=256"
    )
    print(
        "[Phase6F] HARD STOP: NV2A/platform/ABI/guest-fault/missing-body boundaries "
        "remain fenced and logged"
    )
    print("[Phase6F] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

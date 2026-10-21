#!/usr/bin/env python3
'''Phase 6D: continue Phase-6C hardware frontier 0023A3CE -> 0014E2D0
while keeping the proven native Xenos surface and GPU-boundary classifier live.'''
from __future__ import annotations
import argparse, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

BUILD_TAG = "P6D-GRAPHICS-FRONTIER-0014E2D0-20261021-A"
ROOT = 0x0014E2D0
DEPTH = 12
CAP = 512

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6D] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def validate(root, by_va, generated):
    if root not in by_va:
        hit = [r for r in by_va.values() if int(r["start"]) < root < int(r["end"])]
        if hit:
            r = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6D] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(r['start']):08X}-0x{int(r['end']):08X} {r['name']}"
            )
        raise SystemExit(f"[Phase6D] target 0x{root:08X} is absent from function inventory")
    if root not in generated:
        raise SystemExit(
            f"[Phase6D] target 0x{root:08X} is an exact function start "
            f"({by_va[root]['name']}) but has no generated translated body"
        )

def instrument(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6D] could not instrument root 0x0014E2D0")
    return rendered[:b + 1] + "\n    s_phase6dRootEntered = 1;" + rendered[b + 1:]

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
    ap.add_argument("--base-phase6c-emitter", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bb-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bc-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args, _ = ap.parse_known_args()

    base = load(args.base_emitter, "phase6d_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6d_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6d_p5bc")
    args.out_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="phase6d-base-", dir=str(args.out_dir.parent)) as td:
        td = Path(td)
        forwarded = remove_flag(sys.argv[1:], "--base-phase6c-emitter")
        forwarded = replace_flag(forwarded, "--out-dir", td)
        cp = subprocess.run(
            [sys.executable, str(args.base_phase6c_emitter), *forwarded],
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
        mf_path = td / "phase6c-manifest.json"
        for p in (main_path, env_path, mf_path):
            if not p.exists():
                raise SystemExit(f"[Phase6D] Phase 6C base emitter did not produce {p.name}")
        main_text = main_path.read_text(encoding="utf-8")
        env_text = env_path.read_text(encoding="utf-8")
        manifest = json.loads(mf_path.read_text(encoding="utf-8"))

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate(ROOT, by_va, generated)

    old = {int(x, 0) for x in manifest.get("members", [])}
    if ROOT in old:
        raise SystemExit("[Phase6D] 0x0014E2D0 already packed by Phase 6C")

    direct = set(p5bb.bounded_promoted_members(base, ROOT, generated, DEPTH, CAP))
    direct.add(ROOT)
    candidates = sorted(direct - old, key=lambda va: (va != ROOT, va))[:CAP]
    if ROOT not in candidates:
        candidates = ([ROOT] + candidates)[:CAP]
    expanded = old | set(candidates)

    marker = "static int s_phase6cRootEntered;"
    if marker not in main_text:
        raise SystemExit("[Phase6D] Phase 6C root-state marker changed")
    main_text = main_text.replace(marker, marker + "\nstatic int s_phase6dRootEntered;", 1)

    marker = "    s_phase6cRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6D] Phase 6C reset marker changed")
    main_text = main_text.replace(marker, marker + "    s_phase6dRootEntered = 0;\n", 1)

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text, base, p5bb, generated, candidates, expanded
    )
    if ROOT not in rendered:
        raise SystemExit("[Phase6D] support-clean pruning removed mandatory root 0x0014E2D0")

    new = sorted(rendered)
    expanded = old | set(new)

    old_result = '''    if (s_phase6cRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6C GRAPHICS FRONTIER RESULT: PASS");
    else
        trace("PHASE 6C GRAPHICS FRONTIER RESULT: FAIL");'''
    new_result = '''    if (s_phase6dRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6D GRAPHICS FRONTIER RESULT: PASS");
    else
        trace("PHASE 6D GRAPHICS FRONTIER RESULT: FAIL");'''
    if old_result not in main_text:
        raise SystemExit("[Phase6D] Phase 6C result gate changed")
    main_text = main_text.replace(old_result, new_result, 1)

    old_policy = (
        "Policy: inherit the hardware-proven Phase 6B runtime/Xenos path, add exact direct frontier "
        "0014D820 plus a bounded direct closure, keep the native Xenos device alive, and stop at the "
        "next genuine graphics/platform/ABI boundary without fabricating backend success"
    )
    new_policy = (
        "Policy: inherit the hardware-proven Phase 6C runtime/Xenos path, add exact direct frontier "
        "0014E2D0 plus a bounded direct closure, keep the native Xenos device alive, and stop at the "
        "next genuine graphics/platform/ABI boundary without fabricating backend success"
    )
    if old_policy not in main_text:
        raise SystemExit("[Phase6D] Phase 6C policy marker changed")

    main_text = main_text.replace("P6C-GRAPHICS-FRONTIER-0014D820-20261021-A", BUILD_TAG, 1)
    main_text = main_text.replace(old_policy, new_policy, 1)
    main_text = main_text.replace("phase6c_env_build_cookie", "phase6d_env_build_cookie")
    env_text = env_text.replace("phase6c_env_build_cookie", "phase6d_env_build_cookie")
    main_text = main_text.replace("50364343", "50364444")
    env_text = env_text.replace("50364343", "50364444")
    main_text = main_text.replace("PHASE 6C", "PHASE 6D").replace("Phase 6C", "Phase 6D").replace('"P6C ', '"P6D ')
    env_text = env_text.replace("PHASE 6C", "PHASE 6D").replace("Phase 6C", "Phase 6D")

    required = (
        BUILD_TAG,
        "case 0x0014E2D0u: return sub_0014E2D0;",
        "s_phase6dRootEntered = 1;",
        "P6D XENOS: PASS Direct3D_CreateDevice",
        "P6D FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6D FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "PHASE 6D GRAPHICS FRONTIER RESULT",
    )
    for x in required:
        if x not in main_text:
            raise SystemExit(f"[Phase6D] generated main lost marker: {x}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6D",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6d_graphics_frontier"] = {
        "source_phase": "6C",
        "phase6c_hardware_pass": True,
        "phase6c_observed_boundary": {
            "kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x0014E2D0",
            "fault": 0,
            "ticks": 74380,
            "trace": 7402,
        },
        "root": f"0x{ROOT:08X}",
        "root_name": generated[ROOT]["name"],
        "direct_closure_depth": DEPTH,
        "direct_closure_cap": CAP,
        "candidate_new_members": len(candidates),
        "packed_new_members": len(new),
        "pruned_members": len(pruned),
        "new_direct_frontier_targets": [f"0x{x:08X}" for x in sorted(frontiers)],
        "xenos_surface_inherited": True,
    }
    manifest["phase6d_new_members"] = [f"0x{x:08X}" for x in new]

    (args.out_dir / "phase6d-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"[Phase6D] GRAPHICS FRONTIER PACK: base={len(old)} "
        f"candidate_new={len(candidates)} packed_new={len(new)} "
        f"pruned={len(pruned)} total={len(expanded)}"
    )
    print(
        f"[Phase6D] ROOT: 0x0014E2D0 exact generated title function; "
        f"direct depth={DEPTH} cap={CAP}"
    )
    print(
        "[Phase6D] XENOS: inherited real native 640x480 D3D device remains "
        "live during translated execution"
    )
    print(
        "[Phase6D] HARD STOP: next genuine unimplemented graphics/platform "
        "boundary remains fenced and logged"
    )
    print("[Phase6D] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

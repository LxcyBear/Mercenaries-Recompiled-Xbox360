#!/usr/bin/env python3
"""Phase 6B: merge the proven Xenos surface with the frozen Phase-5 runtime.

Starting evidence:
  - Phase 5BV: 3/3 identical hardware boots, stable direct frontier
        0x0023A3CE -> 0x0014CD30
  - Phase 5 exit recon: 0x0014CD30 is an exact generated title function
  - Phase 6A: real Xbox 360 D3D device/clear/present visibly works

This emitter:
  1. regenerates the exact Phase-5BV pack;
  2. adds 0x0014CD30 plus a bounded direct closure;
  3. initializes the proven native Xenos surface before translated execution;
  4. resumes Mercenaries until the next genuine boundary;
  5. classifies first rejected NV2A/MMIO/VRAM access without faking success.

The purple diagnostic screen is only a "title reached GPU boundary" marker.
It is NOT claimed as a guest-rendered Mercenaries frame.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BUILD_TAG = "P6B-FIRST-GRAPHICS-TOUCH-20261021-A"
ROOT = 0x0014CD30
DIRECT_DEPTH = 12
DIRECT_CAP = 512


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6B] could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_exact_generated_target(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < root < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                f"[Phase6B] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}"
            )
        raise SystemExit(
            f"[Phase6B] target 0x{root:08X} is absent from function inventory"
        )
    if root not in generated:
        row = by_va[root]
        raise SystemExit(
            f"[Phase6B] target 0x{root:08X} is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )


def instrument_root(rendered: str, name: str) -> str:
    name_pos = rendered.find(name)
    brace_pos = rendered.find("{", name_pos)
    if name_pos < 0 or brace_pos < 0:
        raise SystemExit("[Phase6B] could not instrument 0x0014CD30")
    return (
        rendered[: brace_pos + 1]
        + "\n    s_phase6bRootEntered = 1;"
        + rendered[brace_pos + 1 :]
    )


def xenos_support() -> str:
    return r'''
/* -------------------------------------------------------------------------
 * Phase 6B native Xbox 360 graphics probe.
 *
 * This is the same minimal native D3D path proven visually by Phase 6A.
 * It intentionally implements no guest NV2A semantics yet.
 * ------------------------------------------------------------------------- */
static D3DDevice* s_phase6bXenosDevice = NULL;
static int s_phase6bXenosReady = 0;

static int phase6b_xenos_create(void)
{
    D3DPRESENT_PARAMETERS pp;
    HRESULT hr;

    ZeroMemory(&pp, sizeof(pp));
    pp.BackBufferWidth = 640;
    pp.BackBufferHeight = 480;
    pp.BackBufferFormat = D3DFMT_A8R8G8B8;
    pp.BackBufferCount = 1;
    pp.MultiSampleType = D3DMULTISAMPLE_NONE;
    pp.MultiSampleQuality = 0;
    pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
    pp.hDeviceWindow = NULL;
    pp.Windowed = FALSE;
    pp.EnableAutoDepthStencil = FALSE;
    pp.AutoDepthStencilFormat = D3DFMT_UNKNOWN;
    pp.Flags = 0;
    pp.FullScreen_RefreshRateInHz = 0;
    pp.PresentationInterval = D3DPRESENT_INTERVAL_ONE;

    trace("P6B XENOS: CreateDevice 640x480 A8R8G8B8, vsync, no depth");
    hr = Direct3D_CreateDevice(
        0,
        D3DDEVTYPE_HAL,
        NULL,
        D3DCREATE_HARDWARE_VERTEXPROCESSING,
        &pp,
        &s_phase6bXenosDevice);

    if (FAILED(hr) || s_phase6bXenosDevice == NULL)
    {
        trace("P6B XENOS: FAIL Direct3D_CreateDevice");
        s_phase6bXenosDevice = NULL;
        return 0;
    }

    s_phase6bXenosReady = 1;
    trace("P6B XENOS: PASS Direct3D_CreateDevice");
    return 1;
}

static void phase6b_xenos_present_solid(D3DCOLOR color)
{
    if (!s_phase6bXenosReady || !s_phase6bXenosDevice)
        return;

    D3DDevice_Clear(
        s_phase6bXenosDevice,
        0,
        NULL,
        D3DCLEAR_TARGET,
        color,
        1.0f,
        0,
        FALSE);
    D3DDevice_Present(s_phase6bXenosDevice);
}

static int phase6b_is_nv2a_mmio(uint32_t address)
{
    return address >= 0xFD000000u && address < 0xFE000000u;
}

static int phase6b_is_nv2a_vram(uint32_t address)
{
    return address >= 0xF0000000u && address < 0xF8000000u;
}

static void phase6b_report_boundary_visual(void)
{
    char line[256];

    if (s_phase4cBoundaryKind == PHASE4C_BOUNDARY_GUEST_FAULT)
    {
        sprintf(
            line,
            "P6B ACCESS BOUNDARY: %s width=%u guest=%08X",
            s_phase4cFaultWrite ? "WRITE" : "READ",
            (unsigned int)s_phase4cFaultWidth,
            (unsigned int)s_phase4cFaultAddress);
        trace(line);

        if (phase6b_is_nv2a_mmio(s_phase4cFaultAddress))
        {
            trace("P6B FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached");
            /* Diagnostic marker only -- NOT guest rendering. */
            phase6b_xenos_present_solid(0xFF7A00FFu);
        }
        else if (phase6b_is_nv2a_vram(s_phase4cFaultAddress))
        {
            trace("P6B FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached");
            /* Diagnostic marker only -- NOT guest rendering. */
            phase6b_xenos_present_solid(0xFF7A00FFu);
        }
        else
        {
            phase6b_xenos_present_solid(0xFF7A3800u);
        }
    }
    else
    {
        /* New translated/kernel/indirect frontier: keep a visible native
         * heartbeat without implying graphics semantics were implemented. */
        phase6b_xenos_present_solid(0xFF102A43u);
    }
}
'''


def patch_xenos(main_text: str) -> str:
    if "#include <d3d9.h>" not in main_text:
        include_marker = "#include <xtl.h>"
        if include_marker not in main_text:
            raise SystemExit("[Phase6B] main.cpp lost <xtl.h> include marker")
        main_text = main_text.replace(
            include_marker,
            include_marker + "\n#include <d3d9.h>",
            1,
        )

    driver_marker = "VOID __cdecl main()"
    driver_pos = main_text.find(driver_marker)
    if driver_pos < 0:
        raise SystemExit("[Phase6B] main driver marker missing")
    main_text = (
        main_text[:driver_pos]
        + xenos_support()
        + "\n"
        + main_text[driver_pos:]
    )

    env_marker = "    if (!phase4c_env_prepare())"
    if env_marker not in main_text:
        raise SystemExit("[Phase6B] environment-prepare marker missing")
    init = r'''    if (!phase6b_xenos_create())
    {
        trace("PHASE 6B XENOS DEVICE RESULT: FAIL");
        goto wait_for_exit;
    }

    phase6b_xenos_present_solid(0xFF101018u);
    trace("PHASE 6B XENOS DEVICE RESULT: PASS");
    trace("P6B: frozen Mercenaries runtime resumes with native Xenos surface alive");

'''
    main_text = main_text.replace(env_marker, init + env_marker, 1)

    trace_marker = "    phase4c_log_trace();"
    if trace_marker not in main_text:
        raise SystemExit("[Phase6B] trace-tail marker missing")
    main_text = main_text.replace(
        trace_marker,
        "    phase6b_report_boundary_visual();\n\n" + trace_marker,
        1,
    )

    return main_text


def relabel(main_text: str, env_text: str) -> tuple[str, str]:
    old_tag = "P5BV-REPEATABILITY-20261021-A"
    if old_tag not in main_text:
        raise SystemExit("[Phase6B] inherited 5BV build tag missing")

    main_text = main_text.replace(old_tag, BUILD_TAG)
    main_text = main_text.replace(
        "phase5bv_env_build_cookie",
        "phase6b_env_build_cookie",
    )
    env_text = env_text.replace(
        "phase5bv_env_build_cookie",
        "phase6b_env_build_cookie",
    )
    main_text = main_text.replace("50354256", "50364242")
    env_text = env_text.replace("50354256", "50364242")

    main_text = main_text.replace("PHASE 5BV", "PHASE 6B")
    env_text = env_text.replace("PHASE 5BV", "PHASE 6B")
    main_text = main_text.replace("Phase 5BV", "Phase 6B")
    env_text = env_text.replace("Phase 5BV", "Phase 6B")
    main_text = main_text.replace(
        "PHASE 6B REPEATABILITY RESULT",
        "PHASE 6B FIRST GRAPHICS TOUCH RESULT",
    )

    old_policy = (
        "Policy: freeze the exact Phase 5BU translated pack with zero new members; "
        "repeat the same retail boot path unchanged and require the fault-free "
        "stable endpoint candidate DIRECT_FRONTIER 0023A3CE -> 0014CD30 with "
        "identical translated dispatch/heap/trace invariants before Phase-5 exit "
        "reconnaissance; preserve all genuine subsystem/ABI/kernel hard stops"
    )
    new_policy = (
        "Policy: inherit the hardware-proven Phase 5BV runtime, add exact title "
        "root 0014CD30 plus a bounded direct closure, keep the proven native "
        "Xenos device alive during translated execution, and stop at the first "
        "new genuine graphics/platform/ABI boundary without fabricating backend "
        "success"
    )
    if old_policy not in main_text:
        raise SystemExit("[Phase6B] inherited policy marker changed")
    main_text = main_text.replace(old_policy, new_policy, 1)

    return main_text, env_text


def main() -> int:
    ap = argparse.ArgumentParser()

    ap.add_argument("--base-phase5bv-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bu-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bt-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bs-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5br-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bq-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bp-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bo-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bn-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bm-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bl-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bk-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bj-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bi-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bh-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bg-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bf-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5be-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bd-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bc-emitter", type=Path, required=True)
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

    base = load_module(args.base_emitter, "phase6b_phase4c_base")
    phase5bb = load_module(args.base_phase5bb_emitter, "phase6b_phase5bb")
    phase5bc = load_module(args.base_phase5bc_emitter, "phase6b_phase5bc")

    args.out_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="phase6b-base-",
        dir=str(args.out_dir.parent),
    ) as temp_name:
        temp_dir = Path(temp_name)
        cmd = [
            sys.executable,
            str(args.base_phase5bv_emitter),
            "--base-phase5bu-emitter", str(args.base_phase5bu_emitter),
            "--base-phase5bt-emitter", str(args.base_phase5bt_emitter),
            "--base-phase5bs-emitter", str(args.base_phase5bs_emitter),
            "--base-phase5br-emitter", str(args.base_phase5br_emitter),
            "--base-phase5bq-emitter", str(args.base_phase5bq_emitter),
            "--base-phase5bp-emitter", str(args.base_phase5bp_emitter),
            "--base-phase5bo-emitter", str(args.base_phase5bo_emitter),
            "--base-phase5bn-emitter", str(args.base_phase5bn_emitter),
            "--base-phase5bm-emitter", str(args.base_phase5bm_emitter),
            "--base-phase5bl-emitter", str(args.base_phase5bl_emitter),
            "--base-phase5bk-emitter", str(args.base_phase5bk_emitter),
            "--base-phase5bj-emitter", str(args.base_phase5bj_emitter),
            "--base-phase5bi-emitter", str(args.base_phase5bi_emitter),
            "--base-phase5bh-emitter", str(args.base_phase5bh_emitter),
            "--base-phase5bg-emitter", str(args.base_phase5bg_emitter),
            "--base-phase5bf-emitter", str(args.base_phase5bf_emitter),
            "--base-phase5be-emitter", str(args.base_phase5be_emitter),
            "--base-phase5bd-emitter", str(args.base_phase5bd_emitter),
            "--base-phase5bc-emitter", str(args.base_phase5bc_emitter),
            "--base-phase5bb-emitter", str(args.base_phase5bb_emitter),
            "--base-emitter", str(args.base_emitter),
            "--generated-root", str(args.generated_root),
            "--functions", str(args.functions),
            "--entry-report", str(args.entry_report),
            "--thread-report", str(args.thread_report),
            "--phase3n-template", str(args.phase3n_template),
            "--phase2e-source", str(args.phase2e_source),
            "--out-dir", str(temp_dir),
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
        base_manifest_path = temp_dir / "phase5bv-manifest.json"
        for required in (base_main, base_env, base_manifest_path):
            if not required.exists():
                raise SystemExit(
                    f"[Phase6B] Phase 5BV base emitter did not produce "
                    f"{required.name}"
                )

        main_text = base_main.read_text(encoding="utf-8")
        env_text = base_env.read_text(encoding="utf-8")
        manifest = json.loads(base_manifest_path.read_text(encoding="utf-8"))

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact_generated_target(ROOT, by_va, generated)

    old_members = {int(item, 0) for item in manifest.get("members", [])}
    if ROOT in old_members:
        raise SystemExit(
            "[Phase6B] 0x0014CD30 is already in the frozen 5BV pack; "
            "repeatability evidence and manifest disagree"
        )

    direct_members = set(
        phase5bb.bounded_promoted_members(
            base,
            ROOT,
            generated,
            DIRECT_DEPTH,
            DIRECT_CAP,
        )
    )
    direct_members.add(ROOT)

    candidate_new_members = sorted(
        direct_members - old_members,
        key=lambda va: (va != ROOT, va),
    )
    if ROOT not in candidate_new_members:
        candidate_new_members.insert(0, ROOT)
    if len(candidate_new_members) > DIRECT_CAP:
        candidate_new_members = candidate_new_members[:DIRECT_CAP]
        if ROOT not in candidate_new_members:
            candidate_new_members[-1] = ROOT

    expanded_members = set(old_members) | set(candidate_new_members)

    declaration_marker = "static int s_phase5buMidTextRootEntered;"
    if declaration_marker not in main_text:
        raise SystemExit("[Phase6B] inherited Phase 5BU root state marker changed")
    main_text = main_text.replace(
        declaration_marker,
        declaration_marker + "\nstatic int s_phase6bRootEntered;",
        1,
    )

    reset_marker = "    s_phase5buMidTextRootEntered = 0;\n"
    if reset_marker not in main_text:
        raise SystemExit("[Phase6B] inherited execution reset marker changed")
    main_text = main_text.replace(
        reset_marker,
        reset_marker + "    s_phase6bRootEntered = 0;\n",
        1,
    )

    phase5bc.SWEEP_ROOT = ROOT
    phase5bc.instrument_root_entry = instrument_root

    (
        main_text,
        rendered_by_va,
        new_direct_frontiers,
        pruned_members,
    ) = phase5bc.insert_pack_members(
        main_text,
        base,
        phase5bb,
        generated,
        candidate_new_members,
        expanded_members,
    )

    if ROOT not in rendered_by_va:
        raise SystemExit(
            "[Phase6B] support-clean pruning removed mandatory 0x0014CD30 root"
        )

    new_members = sorted(rendered_by_va)
    expanded_members = old_members | set(new_members)

    # insert_pack_members rebuilds the lookup with the surviving set.
    main_text, env_text = relabel(main_text, env_text)
    main_text = patch_xenos(main_text)

    # Replace the inherited repeatability-result gate with a Phase-6 probe gate.
    old_result = r'''    if (boundedPass)
        trace("PHASE 6B FIRST GRAPHICS TOUCH RESULT: PASS");
    else
        trace("PHASE 6B FIRST GRAPHICS TOUCH RESULT: FAIL");'''
    if old_result not in main_text:
        raise SystemExit("[Phase6B] inherited result block changed")
    new_result = r'''    if (s_phase6bRootEntered &&
        s_traceCount > 0u &&
        (s_phase4cBoundaryKind != PHASE4C_BOUNDARY_NONE ||
         boundedPass))
        trace("PHASE 6B FIRST GRAPHICS TOUCH RESULT: PASS");
    else
        trace("PHASE 6B FIRST GRAPHICS TOUCH RESULT: FAIL");'''
    main_text = main_text.replace(old_result, new_result, 1)

    required_main_markers = (
        BUILD_TAG,
        "#include <d3d9.h>",
        "static int s_phase6bRootEntered;",
        "s_phase6bRootEntered = 1;",
        "case 0x0014CD30u: return sub_0014CD30;",
        "P6B XENOS: PASS Direct3D_CreateDevice",
        "P6B FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6B FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "PHASE 6B FIRST GRAPHICS TOUCH RESULT",
        "without fabricating backend success",
    )
    for marker in required_main_markers:
        if marker not in main_text:
            raise SystemExit(
                f"[Phase6B] generated main lost required marker: {marker}"
            )

    required_env_markers = (
        "PHASE 6B RETAIL ENVIRONMENT PREP START",
        "PHASE 6B EXACT RETAIL VERIFICATION: PASS",
        "PHASE 6B EXECUTION ENVIRONMENT RESULT: PASS",
        "phase6b_env_build_cookie",
        "50364242",
        "PHASE 6B RETAIL ENVIRONMENT PREP END",
    )
    for marker in required_env_markers:
        if marker not in env_text:
            raise SystemExit(
                f"[Phase6B] generated environment lost marker: {marker}"
            )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    root_row = generated[ROOT]
    manifest["phase"] = "6B"
    manifest["build_tag"] = BUILD_TAG
    manifest["pack_members"] = len(expanded_members)
    manifest["members"] = [
        f"0x{va:08X}" for va in sorted(expanded_members)
    ]
    manifest["phase6b_first_graphics_touch"] = {
        "source_phase": "5BV",
        "phase5_frozen_baseline": True,
        "phase6a_xenos_visual_proof": True,
        "root": f"0x{ROOT:08X}",
        "root_name": root_row["name"],
        "direct_closure_depth": DIRECT_DEPTH,
        "direct_closure_cap": DIRECT_CAP,
        "candidate_new_members": len(candidate_new_members),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned_members),
        "new_direct_frontier_targets": [
            f"0x{va:08X}" for va in sorted(new_direct_frontiers)
        ],
        "xenos_surface": {
            "width": 640,
            "height": 480,
            "format": "D3DFMT_A8R8G8B8",
            "vsync": True,
            "depth": False,
        },
        "graphics_boundary_policy": (
            "rejected 0xFDxxxxxx NV2A MMIO or 0xF0xxxxxx-0xF7xxxxxx VRAM "
            "access is logged and remains a hard boundary; purple output is "
            "diagnostic-only and does not count as guest-rendered pixels"
        ),
        "pass_policy": (
            "native Xenos device must initialize, exact title root 0x0014CD30 "
            "must enter, and execution must reach a new boundary or return "
            "without fabricating graphics/platform success"
        ),
    }
    manifest["phase6b_new_members"] = [
        f"0x{va:08X}" for va in new_members
    ]
    manifest["phase6b_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned_members.items())
    ]

    (args.out_dir / "phase6b-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "[Phase6B] FIRST GRAPHICS TOUCH PACK: "
        f"base={len(old_members)} candidate_new={len(candidate_new_members)} "
        f"packed_new={len(new_members)} pruned={len(pruned_members)} "
        f"total={len(expanded_members)}"
    )
    print(
        "[Phase6B] ROOT: 0x0014CD30 exact generated title function; "
        f"direct depth={DIRECT_DEPTH} cap={DIRECT_CAP}"
    )
    print(
        "[Phase6B] XENOS: real native 640x480 D3D device kept alive during "
        "translated execution"
    )
    print(
        "[Phase6B] HARD STOP: first genuine unimplemented graphics/platform "
        "boundary remains fenced and logged"
    )
    print("[Phase6B] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

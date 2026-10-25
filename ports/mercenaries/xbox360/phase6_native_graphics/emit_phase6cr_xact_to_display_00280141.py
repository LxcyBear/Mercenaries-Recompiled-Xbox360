#!/usr/bin/env python3
"""Phase 6CR: accelerate the new XACTENG frontier toward display/presentation.

6CQ-R7 hardware proved rocket ITAIL dispatch works:
  * packed ITAIL 0010D1A0 consumed three times;
  * XACT continuity/sentinel fixes remained healthy;
  * native Xenos + D3D device remained healthy;
  * new clean DIRECT_FRONTIER 0023A3CE -> 00280141 at tick 26,814,224;
  * fault=0, display_calls=0, framebuffer=0.

6CR makes 00280141 mandatory, packs a deep direct closure from it, and spends
remaining capacity on still-unpacked generated XACTENG, D3D and XGRPH members.
The existing support-clean pruner and all hard fences remain authoritative.

It also adds a compact PRESENT PROXIMITY summary so a single hardware run tells
us whether the new frontier reached the already-armed AvSetDisplayMode handoff
while confirming native Xenos/D3D are still alive.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CQ-ITAIL-SATURATION64M-0010D1A0-20261025-A"
BUILD_TAG = "P6CR-XACT-TO-DISPLAY-00280141-20261025-A"
COOKIE_OLD = "phase6cq_env_build_cookie"
COOKIE_NEW = "phase6cr_env_build_cookie"
EMITTER_REVISION = "6CR-R2"

ROOT = 0x00280141
CALLER = 0x0023A3CE

XACT_START = 0x0027D5C0
XACT_END = 0x00288630
D3D_START = 0x00288640
D3D_END = 0x0029B874
XGRPH_START = 0x0029B880
XGRPH_END = 0x0029CB7C

ROOT_CLOSURE_DEPTH = 16
ROOT_CLOSURE_CAP = 2048
TOTAL_NEW_CAP = 4096


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CR] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CR] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def validate_root(root: int, by_va: dict, generated: dict) -> None:
    if not (XACT_START <= root < XACT_END):
        raise SystemExit(
            f"[Phase6CR] target 0x{root:08X} outside XACTENG "
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
                f"[Phase6CR] target 0x{root:08X} is MID-FUNCTION inside "
                f"0x{start:08X}-0x{end:08X} {owner['name']} ({state}); "
                "refusing to redirect a direct frontier to a prologue"
            )
        raise SystemExit(
            f"[Phase6CR] target 0x{root:08X} absent from function inventory"
        )

    if root not in generated:
        raise SystemExit(
            f"[Phase6CR] target 0x{root:08X} is exact function "
            f"{row['name']} but has no generated translated body"
        )


def install_state(text: str) -> str:
    anchor = "static DWORD s_phase6awVaRingCount = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CR] expected one VA-ring state anchor, found {text.count(anchor)}"
        )
    state = """static uint32_t s_phase6crFrontierEntries = 0u;
static uint32_t s_phase6crFrontierLastEsp = 0u;
static uint32_t s_phase6crFrontierLastEax = 0u;
static uint32_t s_phase6crFrontierLastEcx = 0u;
static uint32_t s_phase6crFrontierLastEdx = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def normalize_root_to_retail(rendered: str) -> str:
    """Remove two optional PC enhancement hooks from the live Xbox retail root.

    The retail 0x00280141 body predates both generated patches:
      * Main-menu shell_stream category rewrite.
      * PS2 authored sound-bank replacement.

    Neither hook is required by retail Xbox startup, while the latter pulls in
    the desktop resource/options/upgrade stack. Phase 6CR therefore restores
    this one translated function to the retail path instead of inventing
    partial helper semantics on Xbox 360.
    """
    menu_hook = (
        "    { void recomp_fix_menu_music_bank(uint32_t, uint32_t);\n"
        "      recomp_fix_menu_music_bank(GUEST_READ32(esp + 4), GUEST_READ32(esp + 8)); }\n"
    )
    ps2_hook = (
        "    GUEST_WRITE32(esp + 4, "
        "recomp_ps2_sound_bank(GUEST_READ32(esp + 4), esp + 8));\n"
    )

    if rendered.count(menu_hook) != 1:
        raise SystemExit(
            f"[Phase6CR] expected one localized menu-music enhancement hook, "
            f"found {rendered.count(menu_hook)}"
        )
    if rendered.count(ps2_hook) != 1:
        raise SystemExit(
            f"[Phase6CR] expected one localized PS2 sound-bank enhancement hook, "
            f"found {rendered.count(ps2_hook)}"
        )

    rendered = rendered.replace(menu_hook, "", 1)
    rendered = rendered.replace(ps2_hook, "", 1)

    if "recomp_fix_menu_music_bank" in rendered or "recomp_ps2_sound_bank" in rendered:
        raise SystemExit(
            "[Phase6CR] optional audio enhancement helper remains in retail-normalized root"
        )
    return rendered


def instrument_root(rendered: str, name: str) -> str:
    rendered = normalize_root_to_retail(rendered)

    name_pos = rendered.find(name)
    brace_pos = rendered.find("{", name_pos)
    if name_pos < 0 or brace_pos < 0:
        raise SystemExit("[Phase6CR] could not instrument mandatory root")

    probe = r'''
    ++s_phase6crFrontierEntries;
    s_phase6crFrontierLastEsp = g_esp;
    s_phase6crFrontierLastEax = g_eax;
    s_phase6crFrontierLastEcx = g_ecx;
    s_phase6crFrontierLastEdx = g_edx;
    if (s_phase6crFrontierEntries <= 4u)
    {
        char phase6crLine[420];
        sprintf(
            phase6crLine,
            "PASS: Phase 6CR entered XACTENG frontier 00280141 entry=%u eax=%08X ecx=%08X edx=%08X esp=%08X display_calls=%u framebuffer=%08X",
            (unsigned int)s_phase6crFrontierEntries,
            (unsigned int)g_eax,
            (unsigned int)g_ecx,
            (unsigned int)g_edx,
            (unsigned int)g_esp,
            (unsigned int)s_phase6aeDisplayModeCount,
            (unsigned int)s_phase6aeDisplayFrameBuffer);
        trace(phase6crLine);
    }
'''
    return rendered[:brace_pos + 1] + probe + rendered[brace_pos + 1:]


def insert_summary(text: str) -> str:
    marker = "P6CQ ITAIL SATURATION:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CR] inherited 6CQ ITAIL summary missing")

    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 10000:
        raise SystemExit("[Phase6CR] could not locate final summary insertion point")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CR PRESENT PROXIMITY: root_entries=%u root_eax=%08X root_ecx=%08X root_edx=%08X root_esp=%08X xenos_ready=%u d3d_calls=%u guest_device=%08X display_calls=%u mode=%08X format=%08X pitch=%u framebuffer=%08X",\n'
        f'{indent}    (unsigned int)s_phase6crFrontierEntries,\n'
        f'{indent}    (unsigned int)s_phase6crFrontierLastEax,\n'
        f'{indent}    (unsigned int)s_phase6crFrontierLastEcx,\n'
        f'{indent}    (unsigned int)s_phase6crFrontierLastEdx,\n'
        f'{indent}    (unsigned int)s_phase6crFrontierLastEsp,\n'
        f'{indent}    (unsigned int)s_phase6bXenosReady,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceBridgeCount,\n'
        f'{indent}    (unsigned int)s_phase6afGuestDevice,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayModeCount,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayMode,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayFormat,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayPitch,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayFrameBuffer);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_policy(text: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0 or text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6CR] expected one runtime Policy trace")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    policy = (
        "Phase 6CR starts from hardware-proven 6CQ packed-ITAIL success and clean "
        "DIRECT_FRONTIER 00280141; make that XACTENG root mandatory, add a deep "
        "direct closure plus remaining support-clean XACTENG/D3D/XGRPH members up "
        "to 4096 new functions, preserve 64M/6CP/ITAIL/kernel-tail semantics and "
        "all hard fences, and report presentation proximity"
    )
    return text[:line_start] + indent + f'trace("Policy: {policy}");' + text[line_end:]


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CQ", "PHASE 6CR")
        .replace("Phase 6CQ", "Phase 6CR")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CR] environment cookie rewrite failed")
    return text


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

    base = load(args.base_emitter, "phase6cr_base")
    p5bb = load(args.phase5bb_emitter, "phase6cr_p5bb")
    p5bc = load(args.phase5bc_emitter, "phase6cr_p5bc")
    p6bl = load(args.phase6bl_emitter, "phase6cr_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cq-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CR] missing cached 6CQ input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CQ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CR] cached 6CQ identity mismatch")

    cq = manifest.get("phase6cq_itail_saturation64m", {})
    if (
        cq.get("execution_budget") != 64000000
        or cq.get("hard_fences_changed") is not False
        or cq.get("allocator_policy_changed") is not False
        or cq.get("graphics_semantics_changed") is not False
    ):
        raise SystemExit("[Phase6CR] inherited 6CQ policy mismatch")

    members = list(manifest.get("members", []))
    if not members or int(manifest.get("pack_members", 0)) != len(members):
        raise SystemExit("[Phase6CR] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6CQ ITAIL SATURATION:",
        "PASS: Phase 6CQ packed %s",
        "0x80000018u",
        "phase4c_ex_query_nonvolatile_setting",
        "P6CQ AV FAMILY:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CR] inherited 6CQ marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_root(ROOT, by_va, generated)

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    old = {int(x, 0) for x in members}
    if ROOT in old:
        raise SystemExit(
            "[Phase6CR] root 0x00280141 is already packed; "
            "the DIRECT_FRONTIER must be diagnosed as lookup/dispatch bookkeeping"
        )

    closure = list(
        p5bb.bounded_promoted_members(
            base,
            ROOT,
            generated,
            ROOT_CLOSURE_DEPTH,
            ROOT_CLOSURE_CAP,
        )
    )
    if ROOT not in closure:
        closure.insert(0, ROOT)

    regions = [
        (XACT_START, XACT_END),
        (D3D_START, D3D_END),
        (XGRPH_START, XGRPH_END),
    ]

    candidate_order = []

    def add(va: int) -> None:
        if (
            va in generated
            and va not in old
            and va not in candidate_order
            and len(candidate_order) < TOTAL_NEW_CAP
        ):
            candidate_order.append(va)

    add(ROOT)
    for va in closure:
        add(va)

    # Prefer XACT members at/after the live root, then the rest of XACT,
    # then D3D and XGRPH. This keeps the live startup chain first while using
    # spare capacity on the actual path needed to make display_calls nonzero.
    xact_remaining = sorted(
        va for va in generated
        if XACT_START <= va < XACT_END and va not in old
    )
    for va in [x for x in xact_remaining if x >= ROOT]:
        add(va)
    for va in [x for x in xact_remaining if x < ROOT]:
        add(va)

    for start, end in regions[1:]:
        for va in sorted(
            va for va in generated
            if start <= va < end and va not in old
        ):
            add(va)

    candidate_new = list(candidate_order)
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6CR] candidate construction lost mandatory root")

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
        require_sweep_root=True,
    )

    if ROOT not in new_members:
        names = pruned.get(ROOT, [])
        joined = ", ".join(str(x) for x in names) if names else "<unknown>"
        raise SystemExit(
            f"[Phase6CR] support-clean pruning removed mandatory root 00280141; "
            f"unresolved support={joined}"
        )

    main_text = insert_summary(main_text)
    main_text = patch_policy(main_text)

    main_text = replace_once(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = patch_env(env_text)

    main_text = (
        main_text.replace("PHASE 6CQ", "PHASE 6CR")
        .replace("Phase 6CQ", "Phase 6CR")
        .replace('"P6CQ ', '"P6CR ')
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "case 0x00280141u:",
        "PASS: Phase 6CR entered XACTENG frontier 00280141",
        "P6CR PRESENT PROXIMITY:",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "PASS: Phase 6CR packed %s",
        "0x80000018u",
        "phase4c_ex_query_nonvolatile_setting",
        "P6CR AV FAMILY:",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6CR] generated source lost marker: {marker}")

    root_case_pos = main_text.find("case 0x00280141u:")
    root_body_pos = main_text.find("static void " + generated[ROOT]["name"] + "(void)")
    if root_case_pos < 0 or root_body_pos < 0:
        raise SystemExit("[Phase6CR] retail-normalized root was not packed")
    root_tail = main_text[root_body_pos:root_body_pos + 12000]
    if "recomp_fix_menu_music_bank" in root_tail or "recomp_ps2_sound_bank" in root_tail:
        raise SystemExit(
            "[Phase6CR] packed 00280141 still contains deferred PC audio enhancement hooks"
        )

    # The proximity summary relies only on long-lived, already-proven state.
    for marker in (
        "s_phase6bXenosReady",
        "s_phase6afCreateDeviceBridgeCount",
        "s_phase6afGuestDevice",
        "s_phase6aeDisplayModeCount",
        "s_phase6aeDisplayFrameBuffer",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CR] presentation state marker missing: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    total_pack = old | set(new_members)
    manifest.update(
        {
            "phase": "6CR",
            "build_tag": BUILD_TAG,
            "pack_members": len(total_pack),
            "members": [f"0x{x:08X}" for x in sorted(total_pack)],
        }
    )

    manifest["phase6cr_xact_to_display"] = {
        "source_phase": "6CQ",
        "phase6cq_hardware": {
            "boundary_kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x00280141",
            "ticks": 26814224,
            "trace": 1035503,
            "fault": 0,
            "packed_itail_target": "0x0010D1A0",
            "packed_itail_dispatches": 3,
            "xact_sentinel_exits": 1,
            "d3d_device_calls": 1,
            "guest_device": "0x00299380",
            "display_calls": 0,
            "framebuffer": "0x00000000",
        },
        "root": f"0x{ROOT:08X}",
        "root_name": generated[ROOT]["name"],
        "frontier_caller": f"0x{CALLER:08X}",
        "root_closure_depth": ROOT_CLOSURE_DEPTH,
        "root_closure_cap": ROOT_CLOSURE_CAP,
        "candidate_cap": TOTAL_NEW_CAP,
        "candidate_members": len(candidate_new),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(total_pack),
        "target_regions": [
            "XACTENG 0x0027D5C0-0x00288630",
            "D3D 0x00288640-0x0029B874",
            "XGRPH 0x0029B880-0x0029CB7C",
        ],
        "new_direct_frontier_targets": [
            f"0x{x:08X}" for x in sorted(frontiers)
        ],
        "root_audio_policy": {
            "retail_semantics_restored": True,
            "deferred_generated_hooks": [
                "recomp_fix_menu_music_bank",
                "recomp_ps2_sound_bank",
            ],
            "reason": (
                "these are post-recomp PC enhancement hooks, not retail Xbox "
                "startup requirements; avoid importing desktop PS2-resource/options "
                "stack or inventing partial helper behavior during Phase 6"
            ),
        },
        "presentation_proximity": {
            "native_xenos_state": "s_phase6bXenosReady",
            "d3d_device_calls": "s_phase6afCreateDeviceBridgeCount",
            "guest_device": "s_phase6afGuestDevice",
            "display_calls": "s_phase6aeDisplayModeCount",
            "framebuffer": "s_phase6aeDisplayFrameBuffer",
            "goal": "first nonzero AvSetDisplayMode/framebuffer or downstream render/present frontier",
        },
        "execution_budget_inherited": 64000000,
        "itail_dispatch_inherited": True,
        "kernel_itail_ordinal24_preserved": True,
        "xact_sentinel_repair_preserved": True,
        "allocator_policy_changed": False,
        "apu_semantics_changed": False,
        "guest_irql_semantics_changed": False,
        "graphics_bridge_semantics_changed": False,
        "null_page_semantics_changed": False,
        "seh_terminator_semantics_changed": False,
        "hard_fences_changed": False,
        "source_layout": layout,
    }

    manifest["phase6cr_new_members"] = [
        f"0x{x:08X}" for x in sorted(new_members)
    ]
    manifest["phase6cr_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6cr-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    total_source = sum(len(rendered[va]) for va in new_members)
    print(f"[Phase6CR] emitter revision: {EMITTER_REVISION}")
    print(
        f"[Phase6CR] ROOT: 0x{ROOT:08X} {generated[ROOT]['name']} "
        f"closure={len(closure)}"
    )
    print(
        f"[Phase6CR] XACT->DISPLAY PACK: candidates={len(candidate_new)} "
        f"pruned={len(pruned)} packed_new={len(new_members)} "
        f"total={len(total_pack)} new_source_bytes={total_source}"
    )
    print("[Phase6CR] ROOT AUDIO POLICY: retail 00280141 semantics restored; PC enhancement hooks deferred")\n    print("[Phase6CR] PRESENT PROXIMITY telemetry armed")
    print("[Phase6CR] 64M execution budget preserved")
    print("[Phase6CR] packed ITAIL + ordinal-24 kernel tail preserved")
    print("[Phase6CR] 6CP XACT continuity/sentinel repairs preserved")
    print("[Phase6CR] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

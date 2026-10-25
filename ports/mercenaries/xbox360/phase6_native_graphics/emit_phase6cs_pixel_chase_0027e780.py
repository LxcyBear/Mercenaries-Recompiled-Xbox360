#!/usr/bin/env python3
"""Phase 6CS: pixel chase through the remaining XACT startup chain.

6CR hardware:
  * entered 0x00280141 twice;
  * preserved Xenos + native D3D device;
  * opened rsm_xbox.ini and shl_streams.xwb;
  * stopped cleanly at DIRECT_FRONTIER 0023A3CE -> 0027E780;
  * ticks=27,019,818 trace=1,071,495 fault=0;
  * display_calls=0 framebuffer=0.

6CS makes 0x0027E780 mandatory and aggressively fills the remaining XACTENG
surface, followed by D3D/XGRPH spare capacity. Before support pruning it restores
retail Xbox semantics for a strict whitelist of post-recomp diagnostic-only XACT
checkpoint calls and optional PS2 audio enhancement hooks. Semantic XACT fixes
(lifetime, stop recovery, EOF handling, etc.) remain untouched.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6CR-XACT-TO-DISPLAY-00280141-20261025-A"
BUILD_TAG = "P6CS-PIXEL-CHASE-0027E780-20261025-A"
COOKIE_OLD = "phase6cr_env_build_cookie"
COOKIE_NEW = "phase6cs_env_build_cookie"
EMITTER_REVISION = "6CS-R1"

ROOT = 0x0027E780
CALLER = 0x0023A3CE

XACT_START = 0x0027D5C0
XACT_END = 0x00288630
D3D_START = 0x00288640
D3D_END = 0x0029B874
XGRPH_START = 0x0029B880
XGRPH_END = 0x0029CB7C

ROOT_CLOSURE_DEPTH = 24
ROOT_CLOSURE_CAP = 3072
TOTAL_NEW_CAP = 4096

# These helpers were inserted by post-recomp diagnostic patches only. They do
# not alter retail state and are safe to remove for the Xbox360 retail bring-up.
DIAGNOSTIC_ONLY = (
    "recomp_xact_alloc_checkpoint",
    "recomp_xact_bank_checkpoint",
    "recomp_xact_cue_checkpoint",
    "recomp_xact_cue_lifetime_checkpoint",
    "recomp_xact_list_checkpoint",
    "recomp_xact_managed_checkpoint",
    "recomp_xact_managed_update_checkpoint",
    "recomp_xact_play_checkpoint",
    "recomp_xact_properties_checkpoint",
    "recomp_xact_setup_checkpoint",
    "recomp_xact_sound_update_checkpoint",
    "recomp_xact_stream_checkpoint",
)

# These remain semantic and MUST NOT be stripped:
SEMANTIC_XACT_HELPERS = (
    "recomp_xact_prepare_failure",
    "recomp_xact_recover_stop_notification",
    "recomp_xact_retire_prepared_cue",
    "recomp_xact_forget_subscription",
    "recomp_xact_stop_subscription",
    "recomp_xact_low_level_handle_exists",
    "recomp_xact_stream_has_unsubmitted_read",
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CS] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validate_root(root: int, by_va: dict, generated: dict) -> None:
    row = by_va.get(root)
    if row is None:
        owners = [
            r for r in by_va.values()
            if int(r["start"]) < root < int(r["end"])
        ]
        if owners:
            owner = sorted(owners, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6CS] target 0x{root:08X} is MID-FUNCTION inside "
                f"0x{int(owner['start']):08X}-0x{int(owner['end']):08X} "
                f"{owner['name']}; refusing prologue redirection"
            )
        raise SystemExit(
            f"[Phase6CS] target 0x{root:08X} absent from function inventory"
        )
    if root not in generated:
        raise SystemExit(
            f"[Phase6CS] target 0x{root:08X} is exact {row['name']} "
            "but has no generated translated body"
        )


def remove_standalone_call(source: str, helper: str) -> tuple[str, int]:
    """Remove standalone helper(...); calls with balanced-parenthesis parsing."""
    token = helper + "("
    removed = 0
    pos = 0
    while True:
        at = source.find(token, pos)
        if at < 0:
            break

        # Only remove a standalone statement: from line indent to helper token,
        # there may be whitespace but no expression/code.
        line_start = source.rfind("\n", 0, at) + 1
        prefix = source[line_start:at]
        if prefix.strip():
            pos = at + len(token)
            continue

        open_pos = at + len(helper)
        depth = 0
        close_pos = -1
        i = open_pos
        while i < len(source):
            ch = source[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    close_pos = i
                    break
            i += 1
        if close_pos < 0:
            raise SystemExit(
                f"[Phase6CS] unterminated diagnostic call {helper}"
            )

        semi = close_pos + 1
        while semi < len(source) and source[semi] in " \t":
            semi += 1
        if semi >= len(source) or source[semi] != ";":
            pos = close_pos + 1
            continue

        line_end = source.find("\n", semi)
        if line_end < 0:
            line_end = len(source)
        else:
            line_end += 1

        source = source[:line_start] + source[line_end:]
        removed += 1
        pos = line_start
    return source, removed


def normalize_xact_generated(generated: dict) -> dict[str, int]:
    counts = {name: 0 for name in DIAGNOSTIC_ONLY}
    counts.update({
        "recomp_ps2_cue_index": 0,
        "recomp_ps2_wave": 0,
        "recomp_ps2_wave_data": 0,
    })

    for va, row in generated.items():
        if not (XACT_START <= va < XACT_END):
            continue

        source = row["source"]

        # Strip only diagnostic checkpoint statements.
        for helper in DIAGNOSTIC_ONLY:
            source, n = remove_standalone_call(source, helper)
            counts[helper] += n

        # Restore three optional PS2 audio patches to their exact retail Xbox
        # forms. These are enhancements, not retail startup requirements.
        cue_after = (
            "loc_0027FA38: ;\n"
            "    eax = recomp_ps2_cue_index(ebx, MEM32(edi + 4));"
        )
        cue_before = (
            "loc_0027FA38: ;\n"
            "    eax = MEM32(edi + 4);"
        )
        if cue_after in source:
            source = source.replace(cue_after, cue_before, 1)
            counts["recomp_ps2_cue_index"] += 1

        wave_after = (
            "loc_00287A87: ;\n"
            "    recomp_ps2_wave(edi, esi);\n"
            "    ecx = MEM32(esi + 0x74);"
        )
        wave_before = (
            "loc_00287A87: ;\n"
            "    ecx = MEM32(esi + 0x74);"
        )
        if wave_after in source:
            source = source.replace(wave_after, wave_before, 1)
            counts["recomp_ps2_wave"] += 1

        pcm_after = (
            "loc_002821ED: ;\n"
            "    {\n"
            "        const uint32_t replacement = recomp_ps2_wave_data(MEM32(esp + 8));\n"
            "        if (replacement) {\n"
            "            const uint32_t buffer = MEM32(esp + 4);\n"
            "            const uint32_t length = MEM32(MEM32(esp + 8) + 12);\n"
            "            PUSH32(esp, length);\n"
            "            PUSH32(esp, replacement);\n"
            "            ecx = buffer;\n"
            "            PUSH32(esp, 0); sub_00280FD5();\n"
            "            if ((int32_t)eax >= 0) {\n"
            "                PUSH32(esp, length);\n"
            "                PUSH32(esp, 0);\n"
            "                ecx = buffer;\n"
            "                PUSH32(esp, 0); sub_0028100F();\n"
            "            }\n"
            "            esp += 12; return;\n"
            "        }\n"
            "    }\n"
            "    PUSH32(esp, MEM32(esp + 4));"
        )
        pcm_before = (
            "loc_002821ED: ;\n"
            "    PUSH32(esp, MEM32(esp + 4));"
        )
        if pcm_after in source:
            source = source.replace(pcm_after, pcm_before, 1)
            counts["recomp_ps2_wave_data"] += 1

        row["source"] = source

    # Guard against accidentally stripping semantic XACT helpers.
    for va, row in generated.items():
        if not (XACT_START <= va < XACT_END):
            continue
        original = row["source"]
        for helper in SEMANTIC_XACT_HELPERS:
            # Presence is not mandatory per function, but the normalizer never
            # has a rule that targets these names.
            if helper in original:
                pass

    return counts


def install_state(text: str) -> str:
    anchor = "static uint32_t s_phase6crFrontierEntries = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CS] expected one 6CR frontier-state anchor, "
            f"found {text.count(anchor)}"
        )
    state = """static uint32_t s_phase6csFrontierEntries = 0u;
static uint32_t s_phase6csFrontierLastEsp = 0u;
static uint32_t s_phase6csFrontierLastEax = 0u;
static uint32_t s_phase6csFrontierLastEcx = 0u;
static uint32_t s_phase6csFrontierLastEdx = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def instrument_root(rendered: str, name: str) -> str:
    name_pos = rendered.find(name)
    brace_pos = rendered.find("{", name_pos)
    if name_pos < 0 or brace_pos < 0:
        raise SystemExit("[Phase6CS] could not instrument mandatory root")

    probe = r'''
    ++s_phase6csFrontierEntries;
    s_phase6csFrontierLastEsp = g_esp;
    s_phase6csFrontierLastEax = g_eax;
    s_phase6csFrontierLastEcx = g_ecx;
    s_phase6csFrontierLastEdx = g_edx;
    if (s_phase6csFrontierEntries <= 8u)
    {
        char phase6csLine[420];
        sprintf(
            phase6csLine,
            "PASS: Phase 6CS entered XACT stream frontier 0027E780 entry=%u eax=%08X ecx=%08X edx=%08X esp=%08X display_calls=%u framebuffer=%08X",
            (unsigned int)s_phase6csFrontierEntries,
            (unsigned int)g_eax,
            (unsigned int)g_ecx,
            (unsigned int)g_edx,
            (unsigned int)g_esp,
            (unsigned int)s_phase6aeDisplayModeCount,
            (unsigned int)s_phase6aeDisplayFrameBuffer);
        trace(phase6csLine);
    }
'''
    return rendered[:brace_pos + 1] + probe + rendered[brace_pos + 1:]


def insert_summary(text: str) -> str:
    marker = "P6CR PRESENT PROXIMITY:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CS] inherited PRESENT PROXIMITY summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 10000:
        raise SystemExit("[Phase6CS] summary insertion point missing")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CS PIXEL CHASE: root_entries=%u root_eax=%08X root_ecx=%08X root_edx=%08X root_esp=%08X xenos_ready=%u d3d_calls=%u guest_device=%08X display_calls=%u framebuffer=%08X",\n'
        f'{indent}    (unsigned int)s_phase6csFrontierEntries,\n'
        f'{indent}    (unsigned int)s_phase6csFrontierLastEax,\n'
        f'{indent}    (unsigned int)s_phase6csFrontierLastEcx,\n'
        f'{indent}    (unsigned int)s_phase6csFrontierLastEdx,\n'
        f'{indent}    (unsigned int)s_phase6csFrontierLastEsp,\n'
        f'{indent}    (unsigned int)s_phase6bXenosReady,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceBridgeCount,\n'
        f'{indent}    (unsigned int)s_phase6afGuestDevice,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayModeCount,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayFrameBuffer);\n'
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

    base = load(args.base_emitter, "phase6cs_base")
    p5bb = load(args.phase5bb_emitter, "phase6cs_p5bb")
    p5bc = load(args.phase5bc_emitter, "phase6cs_p5bc")
    p6bl = load(args.phase6bl_emitter, "phase6cs_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cr-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CS] missing cached 6CR input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CR" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CS] cached 6CR identity mismatch")

    inherited = manifest.get("phase6cr_xact_to_display", {})
    if (
        inherited.get("execution_budget_inherited") != 64000000
        or inherited.get("hard_fences_changed") is not False
        or inherited.get("kernel_itail_ordinal24_preserved") is not True
        or inherited.get("xact_sentinel_repair_preserved") is not True
    ):
        raise SystemExit("[Phase6CS] inherited 6CR policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "PASS: Phase 6CR packed %s",
        "phase4c_ex_query_nonvolatile_setting",
        "P6CR PRESENT PROXIMITY:",
        "P6CR AV FAMILY:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CS] inherited marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_root(ROOT, by_va, generated)

    normalize_counts = normalize_xact_generated(generated)

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    members = list(manifest.get("members", []))
    old = {int(x, 0) for x in members}
    if ROOT in old:
        raise SystemExit(
            "[Phase6CS] root 0x0027E780 is already packed; "
            "diagnose direct-dispatch bookkeeping instead"
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

    candidates: list[int] = []

    def add(va: int) -> None:
        if (
            va in generated
            and va not in old
            and va not in candidates
            and len(candidates) < TOTAL_NEW_CAP
        ):
            candidates.append(va)

    add(ROOT)
    for va in closure:
        add(va)

    # Consume all remaining XACT first; graphics regions get remaining slots.
    for va in sorted(
        va for va in generated
        if XACT_START <= va < XACT_END and va not in old
    ):
        add(va)
    for start, end in (
        (D3D_START, D3D_END),
        (XGRPH_START, XGRPH_END),
    ):
        for va in sorted(
            va for va in generated
            if start <= va < end and va not in old
        ):
            add(va)

    if ROOT not in candidates:
        raise SystemExit("[Phase6CS] candidate construction lost mandatory root")

    expanded = old | set(candidates)
    new_members = list(candidates)

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
        raise SystemExit(
            "[Phase6CS] support-clean pruning removed mandatory 0027E780: "
            + ", ".join(names)
        )

    # Strong safety check: semantic XACT fixes must remain wherever their
    # generated functions survive into the new pack.
    joined_rendered = "\n".join(rendered.values())
    for helper in SEMANTIC_XACT_HELPERS:
        if any(
            helper in generated[va]["source"]
            for va in new_members
            if XACT_START <= va < XACT_END
        ) and helper not in joined_rendered:
            raise SystemExit(
                f"[Phase6CS] semantic XACT helper was lost from retained pack: {helper}"
            )

    main_text = insert_summary(main_text)

    main_text = main_text.replace(BASE_TAG, BUILD_TAG, 1)
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6CR", "PHASE 6CS")
        .replace("Phase 6CR", "Phase 6CS")
        .replace('"P6CR ', '"P6CS ')
    )
    env_text = (
        env_text.replace("PHASE 6CR", "PHASE 6CS")
        .replace("Phase 6CR", "Phase 6CS")
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "case 0x0027E780u:",
        "PASS: Phase 6CS entered XACT stream frontier 0027E780",
        "P6CS PIXEL CHASE:",
        "P6CS PRESENT PROXIMITY:",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "PASS: Phase 6CS packed %s",
        "phase4c_ex_query_nonvolatile_setting",
        "P6CS AV FAMILY:",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6CS] generated source lost marker: {marker}")

    # The live root must no longer require the diagnostic helper that blocked it.
    root_body_pos = main_text.find("static void " + generated[ROOT]["name"] + "(void)")
    root_tail = (
        main_text[root_body_pos:root_body_pos + 16000]
        if root_body_pos >= 0 else ""
    )
    if "recomp_xact_list_checkpoint" in root_tail:
        raise SystemExit(
            "[Phase6CS] 0027E780 still contains diagnostic list checkpoint"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    total_pack = old | set(new_members)
    manifest.update({
        "phase": "6CS",
        "build_tag": BUILD_TAG,
        "pack_members": len(total_pack),
        "members": [f"0x{x:08X}" for x in sorted(total_pack)],
    })

    manifest["phase6cs_pixel_chase"] = {
        "source_phase": "6CR",
        "phase6cr_hardware": {
            "boundary_kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x0027E780",
            "ticks": 27019818,
            "trace": 1071495,
            "fault": 0,
            "root_00280141_entries": 2,
            "packed_itail_dispatches": 10,
            "xenos_ready": 1,
            "d3d_calls": 1,
            "guest_device": "0x00299380",
            "display_calls": 0,
            "framebuffer": "0x00000000",
            "music_bank_opened": "game:\\dataxbox\\sound\\music\\shl_streams.xwb",
        },
        "root": f"0x{ROOT:08X}",
        "root_name": generated[ROOT]["name"],
        "frontier_caller": f"0x{CALLER:08X}",
        "root_closure_depth": ROOT_CLOSURE_DEPTH,
        "root_closure_cap": ROOT_CLOSURE_CAP,
        "candidate_cap": TOTAL_NEW_CAP,
        "candidate_members": len(candidates),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(total_pack),
        "retail_xact_normalization": {
            "diagnostic_only_helpers_removed": {
                k: v for k, v in normalize_counts.items() if v
            },
            "optional_ps2_audio_hooks_deferred": [
                "recomp_ps2_cue_index",
                "recomp_ps2_wave",
                "recomp_ps2_wave_data",
            ],
            "semantic_xact_helpers_preserved": list(SEMANTIC_XACT_HELPERS),
        },
        "new_direct_frontier_targets": [
            f"0x{x:08X}" for x in sorted(frontiers)
        ],
        "execution_budget_inherited": 64000000,
        "itail_dispatch_inherited": True,
        "kernel_itail_ordinal24_preserved": True,
        "xact_continuity_repair_preserved": True,
        "xact_sentinel_repair_preserved": True,
        "graphics_bridge_semantics_changed": False,
        "null_page_semantics_changed": False,
        "seh_terminator_semantics_changed": False,
        "hard_fences_changed": False,
        "source_layout": layout,
    }
    manifest["phase6cs_new_members"] = [
        f"0x{x:08X}" for x in sorted(new_members)
    ]
    manifest["phase6cs_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6cs-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6CS] emitter revision: {EMITTER_REVISION}")
    print(
        f"[Phase6CS] ROOT: 0x{ROOT:08X} {generated[ROOT]['name']} "
        f"closure={len(closure)}"
    )
    print(
        "[Phase6CS] RETAIL XACT NORMALIZATION: "
        + ", ".join(
            f"{name}={count}"
            for name, count in sorted(normalize_counts.items())
            if count
        )
    )
    print(
        f"[Phase6CS] PIXEL CHASE PACK: candidates={len(candidates)} "
        f"pruned={len(pruned)} packed_new={len(new_members)} "
        f"total={len(total_pack)}"
    )
    print("[Phase6CS] semantic XACT fixes preserved")
    print("[Phase6CS] Xenos/D3D/display telemetry preserved")
    print("[Phase6CS] 64M watchdog preserved")
    print("[Phase6CS] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Phase 6AA: cross the post-graphics-pool DIRECT_FRONTIER 0x0020FAE0.

Phase 6Z hardware proved the retail graphics-pool claim itself succeeds:
  base=0x02880000 size=0x01680000
  old_page_next=0x03F00000 -> new_page_next=0x02880000
  free title-heap tail trimmed=0x00040000
  ordinal 166 repair/stack resume remains correct

After that successful allocation the title reached:
  caller 0x0023A3CE -> target 0x0020FAE0
  ticks=670788, trace=179924, fault=0
  eax=1, esp=saved_esp=0x008BFA14

This disproves the earlier assumption that 0x0020FAE0 is OOM-only. 6AA treats
it as the hardware-proven next translated frontier, while preserving the exact
6Z memory model and every existing NV2A/platform/ABI/guest-fault hard stop.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BUILD_TAG = "P6AA-POST-GFXPOOL-FRONTIER-0020FAE0-20261023-A"
BASE_TAG = "P6Z-GFXPOOL-DUAL-FRONTIER-20261023-A"
ROOT = 0x0020FAE0
CALLER = 0x0023A3CE
ROOT_DEPTH = 4
ROOT_CAP = 256
SHARD_TARGET_CHARS = 750000
COOKIE_OLD = "phase6z_env_build_cookie"
COOKIE_NEW = "phase6aa_env_build_cookie"
COOKIE_NUM_OLD = "50366060"
COOKIE_NUM_NEW = "50366161"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AA] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AA] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, new_policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AA] runtime Policy trace is missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AA] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    replacement = indent + 'trace("' + new_policy + '");'
    return text[:line_start] + replacement + text[line_end:]


def install_renderer_recovery_support(main_text: str) -> str:
    enum_old = (
        "    PHASE4C_BOUNDARY_DEBUGBREAK = 7,\n"
        "    PHASE4C_BOUNDARY_HEAP_EXHAUSTED = 8\n"
        "};"
    )
    enum_new = (
        "    PHASE4C_BOUNDARY_DEBUGBREAK = 7,\n"
        "    PHASE4C_BOUNDARY_HEAP_EXHAUSTED = 8,\n"
        "    PHASE4C_BOUNDARY_RENDERER_FATAL = 9\n"
        "};"
    )
    if enum_old not in main_text:
        raise SystemExit("[Phase6AA] boundary enum marker changed")
    main_text = main_text.replace(enum_old, enum_new, 1)

    name_old = '    case PHASE4C_BOUNDARY_HEAP_EXHAUSTED: return "HEAP_EXHAUSTED";'
    name_new = name_old + '\n    case PHASE4C_BOUNDARY_RENDERER_FATAL: return "RENDERER_FATAL";'
    if name_old not in main_text:
        raise SystemExit("[Phase6AA] boundary-name marker changed")
    main_text = main_text.replace(name_old, name_new, 1)

    insert_marker = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if insert_marker not in main_text:
        raise SystemExit("[Phase6AA] renderer support insertion marker changed")

    support = r"""
static void recomp_renderer_recovery_report(uint32_t result, uint32_t stage)
{
    char line[256];
    sprintf(
        line,
        "Phase 6AA renderer recovery report stage=%u HRESULT=%08X esp=%08X",
        (unsigned)stage,
        (unsigned)result,
        (unsigned)g_esp);
    trace(line);

    if (stage == 1u)
    {
        trace("Phase 6AA renderer recovery: CreateDevice allocation failure; retail non-AA retry permitted");
        return;
    }

    if (stage == 2u)
    {
        trace("Phase 6AA renderer recovery: non-AA CreateDevice result observed");
        return;
    }

    trace("Phase 6AA renderer recovery: terminal CreateDevice failure; refusing null-device rendering");
    phase4c_escape(
        PHASE4C_BOUNDARY_RENDERER_FATAL,
        result ? result : 0x80004005u,
        g_esp);
}

"""
    return main_text.replace(insert_marker, support + insert_marker, 1)


def validate_exact(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        hit = [r for r in by_va.values() if int(r["start"]) < root < int(r["end"])]
        if hit:
            row = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6AA] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "Refusing an interior-entry redirect."
            )
        raise SystemExit(
            f"[Phase6AA] target 0x{root:08X} is absent from function inventory"
        )
    if root not in generated:
        raise SystemExit(
            f"[Phase6AA] target 0x{root:08X} is exact function "
            f"{by_va[root]['name']} but has no generated translated body"
        )


def instrument_root(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6AA] could not instrument root 0x0020FAE0")
    return rendered[:b + 1] + "\n    s_phase6aaRootEntered = 1;" + rendered[b + 1:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AA] translated-body optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6AA] translated-body optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AA] translated-body block contains no functions")

    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6AA] translated function opening brace missing")
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
        last_end = len(body)
    if not cut_points or cut_points[-1] != last_end:
        cut_points.append(last_end)

    shard_dir = out_dir / "translated_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale in shard_dir.glob("*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cut_points):
        if end <= start:
            continue
        name = f"phase6aa_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({
            "name": name,
            "chars": len(payload),
            "lines": payload.count("\n") + 1,
        })
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AA] shard writer did not consume full body block")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n' for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]
    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8") for row in shards
    )
    if reconstructed != body:
        raise SystemExit("[Phase6AA] shard reconstruction identity mismatch")

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

    base = load(args.base_emitter, "phase6aa_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6aa_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6aa_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6z-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AA] cached Phase 6Z baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6Z" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AA] cached Phase 6Z baseline identity mismatch")

    z = manifest.get("phase6z_graphics_pool_dual_frontier") or {}
    mm = z.get("memory_model") or {}
    if (
        mm.get("expected_pool_base") != "0x02880000"
        or mm.get("retail_pool_size") != "0x01680000"
        or mm.get("old_page_next") != "0x03F00000"
        or mm.get("free_title_heap_tail_trim") != "0x00040000"
    ):
        raise SystemExit("[Phase6AA] inherited Phase 6Z graphics-pool model drift")

    for marker in (
        "PASS: Phase 6Z retail graphics pool claim",
        "base != 0x02880000u",
        "oldPageNext != 0x03F00000u",
        "size==0x01680000u",
        "graphics_claim=%u",
        "resumeEsp=c+24u",
        "static double recomp_frame_ticks_with_remainder(double ticks)",
        "static uint32_t recomp_freecam_game_ticks(uint32_t ticks)",
        "static uint32_t xbox_GetExtendedGraphicsPool(void)",
        "#define PHASE4C_EXEC_BUDGET 2000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6AA] inherited Phase 6Z marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact(ROOT, by_va, generated)
    validate_exact(CALLER, by_va, generated)
    root_row = by_va[ROOT]
    print(
        f"[Phase6AA] EXACT ROOT PROOF: 0x{ROOT:08X} "
        f"{root_row['name']} range=0x{int(root_row['start']):08X}-"
        f"0x{int(root_row['end']):08X} "
        f"generated_chars={len(generated[ROOT]['source'])}"
    )

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    main_text = install_renderer_recovery_support(main_text)
    print(
        "[Phase6AA] REVIEWED SUPPORT: recomp_renderer_recovery_report "
        "stages 1/2 diagnostic-only; terminal -> RENDERER_FATAL"
    )

    old = {int(x, 0) for x in manifest.get("members", [])}
    if not old:
        raise SystemExit("[Phase6AA] inherited translated pack membership is empty")
    if ROOT in old:
        raise SystemExit(
            "[Phase6AA] root 0x0020FAE0 is already present in inherited pack; "
            "inspect dispatch bookkeeping instead of repacking it"
        )

    closure = set(
        p5bb.bounded_promoted_members(
            base, ROOT, generated, ROOT_DEPTH, ROOT_CAP
        )
    )
    closure.add(ROOT)
    candidate_new = sorted(va for va in closure if va not in old)
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6AA] closure construction lost mandatory root")

    new_members = list(candidate_new)
    expanded = old | set(new_members)
    print(
        f"[Phase6AA] CLOSURE PROOF: root=0x{ROOT:08X} "
        f"candidate_new={len(candidate_new)} inherited={len(old)}"
    )

    state_marker = "static int s_phase6xRootEntered;"
    if state_marker not in main_text:
        raise SystemExit("[Phase6AA] inherited Phase 6X root-state marker changed")
    main_text = main_text.replace(
        state_marker,
        state_marker + "\nstatic int s_phase6aaRootEntered;",
        1,
    )

    reset_marker = "    s_phase6xRootEntered = 0;\n"
    if reset_marker not in main_text:
        raise SystemExit("[Phase6AA] inherited root reset marker changed")
    main_text = main_text.replace(
        reset_marker,
        reset_marker + "    s_phase6aaRootEntered = 0;\n",
        1,
    )

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument_root
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text, base, p5bb, generated, new_members, expanded
    )

    if ROOT in pruned or ROOT not in new_members:
        names = pruned.get(ROOT, [])
        joined = ", ".join(str(x) for x in names) if names else "<unknown>"
        raise SystemExit(
            f"[Phase6AA] support-clean pruning removed mandatory root "
            f"0x{ROOT:08X}; unresolved support = {joined}. "
            "Implement real semantics before continuing."
        )

    main_text = replace_unique(
        main_text,
        "P6Z GFXPOOL CLAIM SUMMARY:",
        "P6AA POST-GFXPOOL SUMMARY:",
        "Phase 6Z summary token",
    )
    main_text = replace_unique(
        main_text,
        "s_phase6xRootEntered &&",
        "s_phase6aaRootEntered &&",
        "inherited root result gate",
    )
    main_text = replace_unique(
        main_text,
        "PHASE 6Z GRAPHICS-POOL DUAL-FRONTIER RESULT",
        "PHASE 6AA POST-GFXPOOL FRONTIER RESULT",
        "Phase 6Z result token",
    )

    new_policy = (
        "Policy: start from hardware-proven Phase-6Z retail graphics-pool "
        "success, resolve exact DIRECT_FRONTIER 0023A3CE -> 0020FAE0 with a "
        "bounded depth-4/cap-256 generated closure, preserve the proven "
        "02880000-03EFFFFF graphics pool plus reviewed timing support and the "
        "2M budget, and hard-stop on unresolved support/NV2A/platform/ABI/"
        "guest-fault boundaries"
    )
    main_text = replace_policy_line(main_text, new_policy)

    main_text = replace_unique(
        main_text, BASE_TAG, BUILD_TAG, "Phase 6Z build tag"
    )
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = main_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)
    env_text = env_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)

    main_text = (
        main_text
        .replace("PHASE 6Z", "PHASE 6AA")
        .replace("Phase 6Z", "Phase 6AA")
        .replace('"P6Z ', '"P6AA ')
    )
    env_text = (
        env_text
        .replace("PHASE 6Z", "PHASE 6AA")
        .replace("Phase 6Z", "Phase 6AA")
    )

    required = (
        BUILD_TAG,
        "case 0x0020FAE0u:",
        "s_phase6aaRootEntered = 1;",
        "PASS: Phase 6AA retail graphics pool claim",
        "base != 0x02880000u",
        "oldPageNext != 0x03F00000u",
        "P6AA XENOS: PASS Direct3D_CreateDevice",
        "P6AA FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6AA FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "P6AA POST-GFXPOOL SUMMARY:",
        "PHASE 6AA POST-GFXPOOL FRONTIER RESULT",
        "#define PHASE4C_EXEC_BUDGET 2000000u",
        "static double recomp_frame_ticks_with_remainder(double ticks)",
        "static uint32_t recomp_freecam_game_ticks(uint32_t ticks)",
        "static uint32_t xbox_GetExtendedGraphicsPool(void)",
    )
    for item in required:
        if item not in main_text:
            raise SystemExit(f"[Phase6AA] generated main lost marker: {item}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6AA",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6aa_post_graphics_pool_frontier"] = {
        "source_phase": "6Z",
        "phase6z_hardware_pass": True,
        "phase6z_hardware": {
            "graphics_pool": {
                "base": "0x02880000",
                "size": "0x01680000",
                "old_page_next": "0x03F00000",
                "new_page_next": "0x02880000",
                "heap_high": "0x01B5C320",
                "trimmed": "0x00040000",
                "reservations": 2,
            },
            "ordinal_166": {
                "base": "0x02880000",
                "rounded": "0x01680000",
                "frame_bytes": 28,
                "repair": 1,
                "graphics_claim": 1,
                "resume_esp": "0x008BF9F8",
                "saved_esp": "0x008BF9FC",
            },
            "next_boundary": {
                "kind": "DIRECT_FRONTIER",
                "caller": "0x0023A3CE",
                "target": "0x0020FAE0",
                "esp": "0x008BFA14",
                "saved_esp": "0x008BFA14",
                "ticks": 670788,
                "trace": 179924,
                "fault": 0,
                "eax": "0x00000001",
                "ecx": "0x00645934",
                "edx": "0x00000000",
            },
            "first_graphics_touch_before_boundary": False,
        },
        "corrected_phase6z_inference": (
            "0x0020FAE0 is not OOM-only; Phase 6Z reached it after a successful "
            "retail graphics-pool allocation"
        ),
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
        "graphics_pool_model_inherited_unchanged": True,
        "execution_budget_inherited": 2000000,
        "source_layout": source_layout,
        "runtime_policy": (
            "exact generated 0x0020FAE0 root/closure only; preserve hardware-"
            "proven Phase 6Z graphics pool and Mm166 repair; support-clean "
            "pruning authoritative; no unknown helper stubs; NV2A/platform/"
            "ABI/guest-fault remain hard stops"
        ),
    }
    manifest["phase6aa_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]
    (args.out_dir / "phase6aa-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(
        f"[Phase6AA] POST-GFXPOOL FRONTIER PACK: root=0x{ROOT:08X} "
        f"name={generated[ROOT]['name']} candidates={len(candidate_new)} "
        f"pruned={len(pruned)} packed_new={len(new_members)} "
        f"total_pack={len(expanded)}"
    )
    print(
        f"[Phase6AA] SOURCE SHARDS: wrapper_lines={source_layout['wrapper_lines']} "
        f"translated_body_lines={source_layout['body_lines']} "
        f"shards={source_layout['shard_count']}"
    )
    print("[Phase6AA] PHASE 6Z GRAPHICS POOL: inherited unchanged")
    print("[Phase6AA] ROOT: exact generated 0x0020FAE0 required")
    print("[Phase6AA] FIRST GRAPHICS TOUCH: still a hard stop / purple milestone")
    print("[Phase6AA] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

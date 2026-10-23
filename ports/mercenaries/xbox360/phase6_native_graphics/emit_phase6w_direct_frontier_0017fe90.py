#!/usr/bin/env python3
"""Phase 6W: exact DIRECT_FRONTIER 0x0017FE90 over the hardware-proven 6V image.

6V cleared the old 600k harness ceiling and reached a genuine new direct-code
frontier:
    caller 0x0023A3CE -> target 0x0017FE90
    ticks=670295, trace=179827, fault=0

Before packing anything, 6W consults the inherited Phase-6Q support-clean prune
table. Hardware reached a root previously fenced only by two upstream host-patch
helpers: recomp_frame_ticks_with_remainder and recomp_freecam_game_ticks.

6W now installs reviewed support-owned implementations before the normal
support-clean audit:
  * frame tick helper: canonical fractional carry/remainder semantics;
  * freecam tick helper: retail/default identity semantics because this Xbox 360
    port exposes no freecam enable/time-control path.

Any additional or changed unresolved dependency still hard-stops. The target
must also validate as an exact generated function start before a bounded
generated closure is packed.

The 2,000,000 tick budget, 32 MiB title heap, native Xenos surface, and all
existing NV2A/platform/ABI/guest-fault hard stops remain unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BUILD_TAG = "P6W-DIRECT-FRONTIER-0017FE90-20261023-A"
BASE_TAG = "P6V-BUDGET2M-20261023-A"
ROOT = 0x0017FE90
CALLER = 0x0023A3CE
ROOT_DEPTH = 4
ROOT_CAP = 256
SHARD_TARGET_CHARS = 750000

EXPECTED_ROOT_SUPPORT = {
    "recomp_frame_ticks_with_remainder",
    "recomp_freecam_game_ticks",
}


def install_phase6w_support(main_text: str) -> str:
    """Install reviewed host-patch support before the support-clean audit.

    The first helper follows the canonical upstream implementation's behavior
    for valid non-negative values while avoiding a new modf/isfinite dependency
    in the XDK build. For valid inputs floor()+subtraction is equivalent to
    modf(); NaN/negative/too-large values reset the carry and pass through.

    The second helper is intentionally retail-preserving for Xbox 360. Upstream
    only changes ticks when its optional free-camera mode is enabled; this port
    has no freecam enable/time-control path, so normal/off-mode semantics are
    exactly an identity transform.
    """
    marker = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if marker not in main_text:
        raise SystemExit("[Phase6W] support insertion marker changed")

    support = r"""
/* Phase 6W reviewed host-patch support.
 * Canonical source basis:
 * KraftMacAndChee/Mercenaries-Recompiled
 *   recomp_frame_ticks_with_remainder()
 *   recomp_freecam_game_ticks()
 */
static double s_phase6wFrameTickRemainder;

static double recomp_frame_ticks_with_remainder(double ticks)
{
    double whole;

    /* Canonical reset/pass-through conditions. ticks != ticks is the
     * portable NaN test for this XDK build; +/-infinity are caught by bounds. */
    if (ticks != ticks || ticks < 0.0 || ticks > 2147483647.0)
    {
        s_phase6wFrameTickRemainder = 0.0;
        return ticks;
    }

    ticks += s_phase6wFrameTickRemainder;
    whole = floor(ticks);
    s_phase6wFrameTickRemainder = ticks - whole;
    return whole;
}

static uint32_t recomp_freecam_game_ticks(uint32_t ticks)
{
    /* Upstream optional freecam normal/off mode is identity. The Xbox 360
     * port has no freecam enable/time-control path, so preserve retail ticks. */
    return ticks;
}

"""
    return main_text.replace(marker, support + marker, 1)




def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6W] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6W] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def validate_exact(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        hit = [
            r for r in by_va.values()
            if int(r["start"]) < root < int(r["end"])
        ]
        if hit:
            row = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6W] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "Refusing to redirect an interior entry to a prologue."
            )
        raise SystemExit(
            f"[Phase6W] target 0x{root:08X} is absent from function inventory"
        )
    if root not in generated:
        raise SystemExit(
            f"[Phase6W] target 0x{root:08X} is exact function "
            f"{by_va[root]['name']} but has no generated translated body"
        )


def instrument_root(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6W] could not instrument root 0x0017FE90")
    return rendered[:b + 1] + "\n    s_phase6wRootEntered = 1;" + rendered[b + 1:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'

    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6W] translated-body optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6W] translated-body optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6W] translated-body block contains no functions")

    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6W] translated function opening brace missing")
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
    for stale in shard_dir.glob("phase6w_*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cut_points):
        if end <= start:
            continue
        name = f"phase6w_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({
            "name": name,
            "chars": len(payload),
            "lines": payload.count("\n") + 1,
        })
        start = end

    if start != len(body):
        raise SystemExit("[Phase6W] shard writer did not consume full body block")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n' for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]

    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8")
        for row in shards
    )
    if reconstructed != body:
        raise SystemExit("[Phase6W] shard reconstruction identity mismatch")

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

    base = load(args.base_emitter, "phase6w_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6w_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6w_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6v-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6W] cached Phase 6V baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6V" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6W] cached Phase 6V baseline identity mismatch")

    # 6V hardware provenance is mandatory.
    deep = manifest.get("phase6v_deep_budget")
    if not isinstance(deep, dict) or deep.get("new_budget_ticks") != 2000000:
        raise SystemExit("[Phase6W] inherited Phase 6V 2M-budget provenance missing")

    # Hardware proved this exact previously-pruned target is now live. Accept
    # only the two reviewed upstream host-patch helpers discovered by 6Q. Any
    # dependency drift remains a hard stop.
    inherited_pruned = manifest.get("phase6q_pruned_members", [])
    root_prune = None
    for row in inherited_pruned:
        if str(row.get("address", "")).upper() == f"0X{ROOT:08X}":
            root_prune = row
            break

    if root_prune is None:
        raise SystemExit(
            "[Phase6W] expected inherited 6Q prune record for live root "
            "0x0017FE90, but none was found"
        )

    observed_support = set(str(x) for x in root_prune.get("unresolved_support", []))
    if observed_support != EXPECTED_ROOT_SUPPORT:
        raise SystemExit(
            "[Phase6W] live-root support dependency set changed: expected "
            + ", ".join(sorted(EXPECTED_ROOT_SUPPORT))
            + "; observed "
            + (", ".join(sorted(observed_support)) or "<none>")
        )

    print(
        "[Phase6W] REVIEWED ROOT SUPPORT: "
        + ", ".join(sorted(observed_support))
    )

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact(ROOT, by_va, generated)
    validate_exact(CALLER, by_va, generated)

    base.STANDARD_CALLS.add("cos")
    base.STANDARD_CALLS.add("sin")

    # Install the reviewed support-owned bodies before Phase5BC snapshots
    # support_symbols(main_text), so the normal unresolved-dependency audit
    # proves the root against real compiled definitions.
    main_text = install_phase6w_support(main_text)

    old = {int(x, 0) for x in manifest.get("members", [])}
    if ROOT in old:
        raise SystemExit(
            "[Phase6W] root 0x0017FE90 is already present in the inherited pack; "
            "runtime dispatch bookkeeping must be inspected instead of repacking it"
        )

    closure = set(
        p5bb.bounded_promoted_members(
            base, ROOT, generated, ROOT_DEPTH, ROOT_CAP
        )
    )
    closure.add(ROOT)
    candidate_new = sorted(va for va in closure if va not in old)
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6W] closure construction lost mandatory root")

    new_members = list(candidate_new)
    expanded = old | set(new_members)

    marker = "static int s_phase6tRootEntered;"
    if marker not in main_text:
        raise SystemExit("[Phase6W] inherited Phase 6T root-state marker changed")
    main_text = main_text.replace(
        marker, marker + "\nstatic int s_phase6wRootEntered;", 1
    )

    marker = "    s_phase6tRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6W] inherited Phase 6T reset marker changed")
    main_text = main_text.replace(
        marker, marker + "    s_phase6wRootEntered = 0;\n", 1
    )

    p5bc.SWEEP_ROOT = ROOT
    p5bc.instrument_root_entry = instrument_root
    main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
        main_text, base, p5bb, generated, new_members, expanded
    )

    if ROOT not in new_members:
        names = pruned.get(ROOT, [])
        joined = ", ".join(str(x) for x in names) if names else "<unknown>"
        raise SystemExit(
            f"[Phase6W] support-clean pruning removed mandatory root 0x{ROOT:08X}; "
            f"unresolved support = {joined}. Implement real semantics before continuing."
        )

    main_text = replace_unique(
        main_text,
        "P6V BUDGET2M SUMMARY:",
        "P6W FRONTIER SUMMARY:",
        "Phase 6V summary token",
    )
    main_text = replace_unique(
        main_text,
        "s_phase6tRootEntered &&",
        "s_phase6wRootEntered &&",
        "inherited root result gate",
    )

    result_old = "PHASE 6V DEEP-BUDGET RESULT"
    if result_old not in main_text:
        raise SystemExit("[Phase6W] inherited Phase 6V result token missing")
    main_text = main_text.replace(
        result_old, "PHASE 6W DIRECT FRONTIER RESULT"
    )

    old_policy = (
        "Policy: reuse the hardware-proven Phase-6U 32 MiB heap image unchanged, raise only "
        "the translated execution budget from 600000 to 2000000 ticks, and retain every "
        "existing NV2A/platform/ABI/guest-fault/support hard stop"
    )
    new_policy = (
        "Policy: start from the hardware-proven Phase-6V 2M-budget image, resolve exact "
        "DIRECT_FRONTIER 0023A3CE -> 0017FE90 with a bounded depth-4/cap-256 generated closure, "
        "retain the 32 MiB heap plus proven cos()/sin() CRT support, and hard-stop on "
        "unresolved support/NV2A/platform/ABI/guest-fault boundaries"
    )
    main_text = replace_unique(
        main_text, old_policy, new_policy, "Phase 6V runtime policy"
    )

    main_text = replace_unique(
        main_text, BASE_TAG, BUILD_TAG, "Phase 6V build tag"
    )
    main_text = main_text.replace(
        "phase6v_env_build_cookie", "phase6w_env_build_cookie"
    )
    env_text = env_text.replace(
        "phase6v_env_build_cookie", "phase6w_env_build_cookie"
    )
    main_text = main_text.replace("50365656", "50365757")
    env_text = env_text.replace("50365656", "50365757")

    main_text = (
        main_text
        .replace("PHASE 6V", "PHASE 6W")
        .replace("Phase 6V", "Phase 6W")
        .replace('"P6V ', '"P6W ')
    )
    env_text = (
        env_text
        .replace("PHASE 6V", "PHASE 6W")
        .replace("Phase 6V", "Phase 6W")
    )

    required = (
        BUILD_TAG,
        "case 0x0017FE90u:",
        "s_phase6wRootEntered = 1;",
        "P6W XENOS: PASS Direct3D_CreateDevice",
        "P6W FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6W FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "P6W FRONTIER SUMMARY:",
        "PHASE 6W DIRECT FRONTIER RESULT",
        "#define PHASE4C_EXEC_BUDGET 2000000u",
        "#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)",
    )
    for item in required:
        if item not in main_text:
            raise SystemExit(f"[Phase6W] generated main lost marker: {item}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6W",
        "build_tag": BUILD_TAG,
        "pack_members": len(expanded),
        "members": [f"0x{x:08X}" for x in sorted(expanded)],
    })
    manifest["phase6w_direct_frontier"] = {
        "source_phase": "6V",
        "phase6v_hardware_pass": True,
        "phase6v_observed_boundary": {
            "kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x0017FE90",
            "esp": "0x008BFF3C",
            "saved_esp": "0x008BFF3C",
            "fault": 0,
            "ticks": 670295,
            "trace": 179827,
            "direct_dispatches_before_boundary": 1795,
            "icall_dispatches_before_boundary": 9073,
            "last_packed_direct": "0x001F6D80",
            "last_packed_icall": "0x00252E70",
        },
        "execution_budget_inherited": 2000000,
        "title_heap_end_inherited": "0x028C0000",
        "root": f"0x{ROOT:08X}",
        "root_name": generated[ROOT]["name"],
        "frontier_caller": f"0x{CALLER:08X}",
        "root_closure_depth": ROOT_DEPTH,
        "root_closure_cap": ROOT_CAP,
        "candidate_new_members": len(candidate_new),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(expanded),
        "new_direct_frontier_targets": [f"0x{x:08X}" for x in sorted(frontiers)],
        "phase_owned_crt_support": ["cos", "sin"],
        "reviewed_host_patch_support": {
            "recomp_frame_ticks_with_remainder": (
                "canonical fractional carry/remainder semantics; invalid input resets carry"
            ),
            "recomp_freecam_game_ticks": (
                "retail/default identity semantics; Xbox 360 port has no freecam enable path"
            ),
        },
        "source_layout": source_layout,
        "runtime_policy": (
            "exact generated root/closure only; reviewed canonical/default host-patch "
            "support for frame ticks/freecam ticks; support-clean pruning authoritative; "
            "no unknown helper stubs; NV2A/platform/ABI/guest-fault remain hard stops"
        ),
    }
    manifest["phase6w_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6w-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"[Phase6W] DIRECT FRONTIER PACK: root=0x{ROOT:08X} "
        f"name={generated[ROOT]['name']} candidates={len(candidate_new)} "
        f"pruned={len(pruned)} packed_new={len(new_members)} "
        f"total_pack={len(expanded)}"
    )
    print(
        f"[Phase6W] SOURCE SHARDS: wrapper_lines={source_layout['wrapper_lines']} "
        f"translated_body_lines={source_layout['body_lines']} "
        f"shards={source_layout['shard_count']}"
    )
    print(
        "[Phase6W] REVIEWED SUPPORT: recomp_frame_ticks_with_remainder + "
        "recomp_freecam_game_ticks"
    )
    print("[Phase6W] EXECUTION BUDGET: inherited 2000000 ticks")
    print("[Phase6W] TITLE HEAP: inherited 32 MiB")
    print("[Phase6W] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

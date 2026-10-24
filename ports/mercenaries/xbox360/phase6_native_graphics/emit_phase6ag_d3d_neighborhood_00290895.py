#!/usr/bin/env python3
"""Phase 6AG: expand the live retail-D3D neighborhood after native CreateDevice.

Phase 6AF-B hardware proved the exact retail CreateDevice handoff:
  * native Xenos CreateDevice remains PASS;
  * retail sub_0028CAA0 executes with the expected 640x480 contract;
  * the bridge publishes guest device 0x00299380 through 0x007AD604;
  * execution continues instead of terminal HRESULT 0x8007000E;
  * next clean boundary:
      DIRECT_FRONTIER 0x0023A3CE -> 0x00290895
      esp=saved_esp=0x008BF92C, fault=0.

6AG treats 0x00290895 as the hardware-proven D3D root and packs a bounded,
support-clean translated closure around it. It also opportunistically carries
the already-reviewed local D3D format-dispatch entry seeds 0x00290881,
0x00290884 and 0x00290887 when generated bodies are available. This is a
single renderer-neighborhood expansion, not a blanket D3D unlock.

The 6AF CreateDevice bridge remains unchanged. The stale inherited AV-result
requirements are removed because 6AF hardware proved that the successful
CreateDevice path no longer executes those optional AV calls. Genuine
NV2A/MMIO/VRAM, platform, ABI and guest faults remain hard stops.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6AF-NATIVE-D3D-CREATEDEVICE-HANDOFF-20261023-B"
BUILD_TAG = "P6AG-D3D-NEIGHBORHOOD-00290895-20261023-D"
COOKIE_OLD = "phase6af_env_build_cookie"
COOKIE_NEW = "phase6ag_env_build_cookie"

ROOT = 0x00290895
CALLER = 0x0023A3CE
ROOT_DEPTH = 6
ROOT_CAP = 384
LOCAL_SEEDS = (0x00290881, 0x00290884, 0x00290887)
LOCAL_DEPTH = 2
LOCAL_CAP = 64
SHARD_TARGET_CHARS = 750000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AG] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AG] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, new_policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AG] runtime Policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AG] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return text[:line_start] + indent + 'trace("' + new_policy + '");' + text[line_end:]


def validate_exact(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        hit = [r for r in by_va.values() if int(r["start"]) < root < int(r["end"])]
        if hit:
            row = sorted(hit, key=lambda x: int(x["start"]))[-1]
            raise SystemExit(
                f"[Phase6AG] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "Refusing an interior-entry redirect; promote the hardware target "
                "through function-ID/manual-seed regeneration first."
            )
        raise SystemExit(
            f"[Phase6AG] target 0x{root:08X} is absent from function inventory"
        )
    if root not in generated:
        raise SystemExit(
            f"[Phase6AG] target 0x{root:08X} is exact function "
            f"{by_va[root]['name']} but has no generated translated body"
        )


def instrument_root(rendered: str, name: str) -> str:
    p = rendered.find(name)
    b = rendered.find("{", p)
    if p < 0 or b < 0:
        raise SystemExit("[Phase6AG] could not instrument D3D root 0x00290895")
    injected = (
        "\n    s_phase6agRootEntered = 1;"
        '\n    trace("PASS: Phase 6AG retail D3D root 00290895 entered");'
    )
    return rendered[: b + 1] + injected + rendered[b + 1 :]


def install_state(main_text: str) -> str:
    marker = "static uint32_t s_phase6afCreateDeviceBridgeCount;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AG] Phase 6AF CreateDevice state marker missing")
    return main_text.replace(
        marker,
        "static int s_phase6agRootEntered;\n" + marker,
        1,
    )


def reset_state(main_text: str) -> str:
    marker = "    s_phase6afCreateDeviceBridgeCount = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AG] Phase 6AF CreateDevice reset marker missing")
    return main_text.replace(
        marker,
        "    s_phase6agRootEntered = 0;\n" + marker,
        1,
    )


def install_phase_result(main_text: str) -> str:
    # Do not mutate the inherited 6AF/AV-era boolean result expression. The
    # successful 6AF hardware path proved those optional AV conditions are no
    # longer authoritative. Emit a separate Phase-6AG result beside the durable
    # D3D-device summary using only the two states this stage actually requires.
    marker = "P6AF D3D DEVICE:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6AG] inherited P6AF D3D device summary missing")

    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 2600:
        raise SystemExit("[Phase6AG] could not locate inherited D3D summary statement")

    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "PHASE 6AG D3D NEIGHBORHOOD RESULT: %s",\n'
        f'{indent}    (s_phase6agRootEntered && '
        f's_phase6afCreateDeviceBridgeCount != 0u) ? "PASS" : "FAIL");\n'
        f'{indent}trace(line);\n'
    )

    return main_text[:line_start] + block + main_text[line_start:]

def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AG] optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6AG] optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AG] translated body contains no functions")

    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6AG] translated function opening brace missing")
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
        name = f"phase6ag_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append(
            {
                "name": name,
                "chars": len(payload),
                "lines": payload.count("\n") + 1,
            }
        )
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AG] shard writer did not consume body")

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
        raise SystemExit("[Phase6AG] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6ag_",
        "shard_count": len(shards),
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

    base = load(args.base_emitter, "phase6ag_base")
    p5bb = load(args.base_phase5bb_emitter, "phase6ag_p5bb")
    p5bc = load(args.base_phase5bc_emitter, "phase6ag_p5bc")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6af-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AG] cached Phase 6AF baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AF" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AG] cached Phase 6AF-B baseline identity mismatch")

    af = manifest.get("phase6af_native_d3d_createdevice_handoff") or {}
    if af.get("phase6ae_hardware_pass") is not True:
        raise SystemExit("[Phase6AG] inherited 6AE-B hardware proof missing")
    native = af.get("native_handoff") or {}
    if (
        native.get("guest_device_identity") != "0x00299380"
        or native.get("strict_contract_validation") is not True
    ):
        raise SystemExit("[Phase6AG] inherited native CreateDevice contract drift")

    for marker in (
        BASE_TAG,
        "PASS: Phase 6AF native D3D CreateDevice handoff",
        "static int phase6af_native_xenos_ready(void)",
        "return s_phase6bXenosReady && s_phase6bXenosDevice != NULL;",
        "P6AF XENOS: PASS Direct3D_CreateDevice",
        "phase6af_env_build_cookie",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6AG] inherited marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact(ROOT, by_va, generated)

    old = {int(x, 0) for x in manifest.get("members", [])}
    if not old:
        raise SystemExit("[Phase6AG] inherited translated pack membership is empty")
    if ROOT in old:
        raise SystemExit(
            "[Phase6AG] root 0x00290895 is already present in inherited pack; "
            "inspect dispatch bookkeeping instead of repacking it"
        )

    root_closure = set(
        p5bb.bounded_promoted_members(base, ROOT, generated, ROOT_DEPTH, ROOT_CAP)
    )
    root_closure.add(ROOT)

    local_present = []
    local_closure = set()
    for seed in LOCAL_SEEDS:
        if seed not in generated:
            print(
                f"[Phase6AG] LOCAL D3D SEED 0x{seed:08X}: no generated body; "
                "leave fenced"
            )
            continue
        local_present.append(seed)
        members = set(
            p5bb.bounded_promoted_members(
                base, seed, generated, LOCAL_DEPTH, LOCAL_CAP
            )
        )
        members.add(seed)
        local_closure.update(members)

    combined = root_closure | local_closure
    candidate_new = sorted(va for va in combined if va not in old)
    if ROOT not in candidate_new:
        raise SystemExit("[Phase6AG] closure construction lost mandatory D3D root")

    new_members = list(candidate_new)
    expanded = old | set(new_members)

    print(
        f"[Phase6AG] EXACT ROOT PROOF: 0x{ROOT:08X} "
        f"{by_va[ROOT]['name']} range=0x{int(by_va[ROOT]['start']):08X}-"
        f"0x{int(by_va[ROOT]['end']):08X} "
        f"generated_chars={len(generated[ROOT]['source'])}"
    )
    print(
        f"[Phase6AG] D3D NEIGHBORHOOD: root_candidate={len(root_closure)} "
        f"local_seeds={len(local_present)} combined={len(combined)} "
        f"new={len(candidate_new)} inherited={len(old)}"
    )

    main_text = install_state(main_text)
    main_text = reset_state(main_text)

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

    if ROOT in pruned or ROOT not in new_members:
        names = pruned.get(ROOT, [])
        joined = ", ".join(str(x) for x in names) if names else "<unknown>"
        raise SystemExit(
            f"[Phase6AG] support-clean pruning removed mandatory D3D root "
            f"0x{ROOT:08X}; unresolved support={joined}"
        )

    main_text = install_phase_result(main_text)

    new_policy = (
        "Policy: inherit 6AF-B native CreateDevice; pack support-clean D3D "
        "root 00290895 plus reviewed local format tails; continue translated "
        "D3D; keep NV2A/MMIO/VRAM, platform, ABI and guest-fault fences hard"
    )
    if len(new_policy) > 240:
        raise SystemExit("[Phase6AG] startup policy trace exceeds safe length")
    main_text = replace_policy_line(main_text, new_policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text
        .replace("PHASE 6AF", "PHASE 6AG")
        .replace("Phase 6AF", "Phase 6AG")
        .replace('"P6AF ', '"P6AG ')
    )
    env_text = (
        env_text
        .replace("PHASE 6AF", "PHASE 6AG")
        .replace("Phase 6AF", "Phase 6AG")
    )

    required = (
        BUILD_TAG,
        "case 0x00290895u:",
        "s_phase6agRootEntered = 1;",
        "PASS: Phase 6AG retail D3D root 00290895 entered",
        "PASS: Phase 6AG native D3D CreateDevice handoff",
        "PHASE 6AG D3D NEIGHBORHOOD RESULT: %s",
        "s_phase6agRootEntered && s_phase6afCreateDeviceBridgeCount != 0u",
        "P6AG XENOS: PASS Direct3D_CreateDevice",
        "P6AG FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6AG FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "phase6ag_env_build_cookie",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AG] generated source lost marker: {marker}")

    if COOKIE_OLD in main_text or COOKIE_OLD in env_text:
        raise SystemExit("[Phase6AG] stale Phase 6AF cookie remains")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6AG",
            "build_tag": BUILD_TAG,
            "pack_members": len(expanded),
            "members": [f"0x{x:08X}" for x in sorted(expanded)],
        }
    )
    manifest["phase6ag_d3d_neighborhood"] = {
        "source_phase": "6AF",
        "phase6af_hardware_pass": True,
        "phase6af_hardware": {
            "native_createdevice": {
                "result": "PASS",
                "guest_device": "0x00299380",
                "device_out": "0x007AD604",
                "width": 640,
                "height": 480,
                "format": "0x00000006",
                "back_buffers": 1,
                "multisample": "0x00000011",
                "swap": 1,
                "auto_depth": 1,
                "depth_format": "0x0000002A",
            },
            "next_boundary": {
                "kind": "DIRECT_FRONTIER",
                "caller": "0x0023A3CE",
                "target": "0x00290895",
                "esp": "0x008BF92C",
                "saved_esp": "0x008BF92C",
                "ticks": 670838,
                "trace": 179938,
                "fault": 0,
                "eax": "0x00000201",
                "ecx": "0x00000000",
                "edx": "0x00000008",
            },
        },
        "root": f"0x{ROOT:08X}",
        "root_name": generated[ROOT]["name"],
        "frontier_caller": f"0x{CALLER:08X}",
        "root_closure_depth": ROOT_DEPTH,
        "root_closure_cap": ROOT_CAP,
        "reviewed_local_seeds_requested": [f"0x{x:08X}" for x in LOCAL_SEEDS],
        "reviewed_local_seeds_generated": [f"0x{x:08X}" for x in local_present],
        "local_closure_depth": LOCAL_DEPTH,
        "local_closure_cap": LOCAL_CAP,
        "candidate_new_members": len(candidate_new),
        "packed_new_members": len(new_members),
        "pruned_members": len(pruned),
        "expanded_pack_members": len(expanded),
        "new_direct_frontier_targets": [
            f"0x{x:08X}" for x in sorted(frontiers)
        ],
        "independent_phase_result_gate": True,
        "inherited_av_result_gate_left_untouched": True,
        "native_createdevice_handoff_inherited_unchanged": True,
        "source_layout": source_layout,
        "runtime_policy": (
            "support-clean D3D neighborhood expansion rooted at hardware-proven "
            "0x00290895 plus reviewed local format-dispatch tails; preserve native "
            "Xenos CreateDevice bridge and genuine graphics/platform hard stops"
        ),
    }

    (args.out_dir / "phase6ag-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6AG] D3D NEIGHBORHOOD 00290895: READY")
    print(f"[Phase6AG] Packed new translated members: {len(new_members)}")
    print(f"[Phase6AG] Support-clean pruned members: {len(pruned)}")
    print(
        "[Phase6AG] Reviewed local seeds available: "
        + (
            ", ".join(f"{x:08X}" for x in local_present)
            if local_present
            else "<none>"
        )
    )
    print("[Phase6AG] 6AF native CreateDevice bridge inherited unchanged")
    print("[Phase6AG] Independent phase result: root-entered + CreateDevice bridge")
    print("[Phase6AG] Purple remains reserved for genuine NV2A MMIO/VRAM")
    print("[Phase6AG] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

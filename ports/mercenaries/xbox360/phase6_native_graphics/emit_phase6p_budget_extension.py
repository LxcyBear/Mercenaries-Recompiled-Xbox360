#!/usr/bin/env python3
"""Phase 6P: extend the proven Phase-6O execution watchdog only.

Phase 6O crossed the cos() support fence and exhausted the 200000-block
watchdog inside already-packed translated execution:
  BUDGET 0x0023A3CE -> 0x002527B5
  fault=0, ticks=200001, trace=43586

No new translated members or support exceptions are introduced here.  The
hardware-proven Phase-6O monolithic source is reused byte-for-byte except for
phase identity, environment cookie, and a finite watchdog increase to 600000.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

BUILD_TAG = "P6P-BUDGET600K-20261022-A"
OLD_TAG = "P6O-COS-HARVEST-00251CD0-20261022-A"
OLD_BUDGET = 200000
NEW_BUDGET = 600000
SHARD_TARGET_CHARS = 750000

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6P] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6P] translated-body optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6P] translated-body optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6P] translated-body block contains no functions")

    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6P] translated function opening brace missing")
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
    shards = []
    start = 0
    for index, end in enumerate(cut_points):
        if end <= start:
            continue
        name = f"phase6p_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({"name": name, "chars": len(payload), "lines": payload.count("\n") + 1})
        start = end
    if start != len(body):
        raise SystemExit("[Phase6P] shard writer did not consume full body block")

    include_block = "".join(f'#include "translated_shards/{row["name"]}"\n' for row in shards)
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]
    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join((shard_dir / row["name"]).read_text(encoding="utf-8") for row in shards)
    if reconstructed != body:
        raise SystemExit("[Phase6P] shard reconstruction identity mismatch")

    return {
        "build_main":"main.cpp",
        "monolithic_cache":"main_monolithic.cpp",
        "shard_directory":"translated_shards",
        "shard_count":len(shards),
        "target_chars":SHARD_TARGET_CHARS,
        "body_chars":len(body),
        "body_lines":body.count("\n")+1,
        "wrapper_chars":len(wrapper),
        "wrapper_lines":wrapper.count("\n")+1,
        "shards":shards,
    }

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6P] {label} expected exactly once, found {count}")
    return text.replace(old, new, 1)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6p_base")
    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6o-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6P] cached Phase 6O baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6O" or manifest.get("build_tag") != OLD_TAG:
        raise SystemExit("[Phase6P] cached Phase 6O identity mismatch")
    g = manifest.get("phase6o_global_harvest", {})
    if g.get("root") != "0x00251CD0":
        raise SystemExit("[Phase6P] cached Phase 6O root mismatch")
    if g.get("phase_owned_crt_support") != ["cos"]:
        raise SystemExit("[Phase6P] cached Phase 6O cos-support identity mismatch")

    main_text = replace_once(
        main_text,
        f"#define PHASE4C_EXEC_BUDGET {OLD_BUDGET}u",
        f"#define PHASE4C_EXEC_BUDGET {NEW_BUDGET}u",
        "execution budget",
    )
    main_text = replace_once(main_text, OLD_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace("phase6o_env_build_cookie", "phase6p_env_build_cookie")
    env_text = env_text.replace("phase6o_env_build_cookie", "phase6p_env_build_cookie")
    main_text = main_text.replace("50364F4F", "50365050")
    env_text = env_text.replace("50364F4F", "50365050")
    main_text = main_text.replace("PHASE 6O", "PHASE 6P").replace("Phase 6O", "Phase 6P").replace('"P6O ', '"P6P ')
    env_text = env_text.replace("PHASE 6O", "PHASE 6P").replace("Phase 6O", "Phase 6P")
    main_text = main_text.replace(
        "PHASE 6P COS HARVEST RESULT",
        "PHASE 6P BUDGET EXTENSION RESULT",
        1,
    )

    required = (
        BUILD_TAG,
        "#define PHASE4C_EXEC_BUDGET 600000u",
        "case 0x00251CD0u: return sub_00251CD0;",
        "P6P XENOS: PASS Direct3D_CreateDevice",
        "P6P FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6P FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "P6P HARVEST SUMMARY",
        "PHASE 6P BUDGET EXTENSION RESULT",
        "#include <math.h>",
        "#pragma warning(disable:4102)",
    )
    for item in required:
        if item not in main_text:
            raise SystemExit(f"[Phase6P] generated main lost marker: {item}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase":"6P",
        "build_tag":BUILD_TAG,
    })
    manifest["phase6p_budget_extension"] = {
        "source_phase":"6O",
        "cached_base":True,
        "phase6o_hardware_pass":True,
        "phase6o_observed_boundary":{
            "kind":"BUDGET",
            "caller":"0x0023A3CE",
            "target":"0x002527B5",
            "esp":"0x008BFF40",
            "saved_esp":"0x008BFF40",
            "fault":0,
            "ticks":200001,
            "trace":43586,
            "direct_dispatches_before_boundary":1354,
            "icall_dispatches_before_boundary":8185,
            "last_packed_direct":"0x0023BE3C",
            "last_packed_icall":"0x002527A0",
        },
        "old_execution_budget":OLD_BUDGET,
        "new_execution_budget":NEW_BUDGET,
        "pack_members_unchanged":True,
        "pack_members":manifest.get("pack_members"),
        "phase_owned_crt_support":["cos"],
        "xenos_surface_inherited":True,
        "source_layout":source_layout,
        "runtime_policy":(
            "reuse exact Phase-6O translated pack; increase only finite execution watchdog; "
            "NV2A/platform/ABI/guest-fault/missing-support boundaries remain hard stops"
        ),
    }
    (args.out_dir / "phase6p-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[Phase6P] FAST BUDGET EXTENSION: {OLD_BUDGET} -> {NEW_BUDGET} blocks")
    print(f"[Phase6P] PACK MEMBERS UNCHANGED: {manifest.get('pack_members')}")
    print(
        f"[Phase6P] SOURCE SHARDS: wrapper_lines={source_layout['wrapper_lines']} "
        f"translated_body_lines={source_layout['body_lines']} "
        f"shards={source_layout['shard_count']}"
    )
    print("[Phase6P] HARD STOPS RETAINED: NV2A/platform/ABI/guest-fault/missing-support")
    print("[Phase6P] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

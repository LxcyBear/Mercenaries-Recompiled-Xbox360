#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path

BUILD_TAG = "P6AV-BUDGET8M-20261024-A"
BASE_TAG = "P6AU-D3D-FRONTIER-00292586-20261024-A"
OLD_BUDGET = "#define PHASE4C_EXEC_BUDGET 2000000u"
NEW_BUDGET = "#define PHASE4C_EXEC_BUDGET 8000000u"
OLD_TICKS = 2000000
NEW_TICKS = 8000000

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"[Phase6AV] expected one {label}, found {n}")
    return text.replace(old, new, 1)

def patch_main(text):
    text = replace_once(text, OLD_BUDGET, NEW_BUDGET, "execution budget definition")
    text = replace_once(text, BASE_TAG, BUILD_TAG, "Phase 6AU build tag")
    text = text.replace("phase6au_env_build_cookie", "phase6av_env_build_cookie")
    old_policy = "Policy: Phase 6AU D3D frontier 00292586; depth-4 cap-256 closure; preserve 6AT allocator and fences"
    new_policy = "Policy: Phase 6AV reuses 6AU exactly; budget 2M->8M only; preserve allocator, closure and all hard fences"
    text = replace_once(text, old_policy, new_policy, "Phase 6AU runtime policy")
    text = text.replace("PHASE 6AU", "PHASE 6AV").replace("Phase 6AU", "Phase 6AV").replace('"P6AU ', '"P6AV ')
    if "phase6au_env_build_cookie" in text:
        raise SystemExit("[Phase6AV] stale Phase 6AU cookie remains in main")
    return text

def patch_env(text):
    text = text.replace("phase6au_env_build_cookie", "phase6av_env_build_cookie")
    text = text.replace("PHASE 6AU", "PHASE 6AV").replace("Phase 6AU", "Phase 6AV")
    if "phase6av_env_build_cookie" not in text:
        raise SystemExit("[Phase6AV] env cookie rewrite did not land")
    if "phase6au_env_build_cookie" in text:
        raise SystemExit("[Phase6AV] stale Phase 6AU cookie remains in env")
    return text

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    a=ap.parse_args()
    for p in (a.base_dir/"main.cpp", a.base_dir/"main_monolithic.cpp", a.base_dir/"phase5_env.cpp", a.base_dir/"phase6au-manifest.json", a.base_dir/"translated_shards"):
        if not p.exists(): raise SystemExit(f"[Phase6AV] missing baseline input: {p}")
    m=json.loads((a.base_dir/"phase6au-manifest.json").read_text(encoding="utf-8"))
    if m.get("phase")!="6AU" or m.get("build_tag")!=BASE_TAG:
        raise SystemExit("[Phase6AV] baseline identity mismatch")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    sd=a.out_dir/"translated_shards"
    if sd.exists(): shutil.rmtree(sd)
    shutil.copytree(a.base_dir/"translated_shards", sd)
    main_text=patch_main((a.base_dir/"main.cpp").read_text(encoding="utf-8"))
    mono_text=patch_main((a.base_dir/"main_monolithic.cpp").read_text(encoding="utf-8"))
    env_text=patch_env((a.base_dir/"phase5_env.cpp").read_text(encoding="utf-8"))
    (a.out_dir/"main.cpp").write_text(main_text, encoding="utf-8")
    (a.out_dir/"main_monolithic.cpp").write_text(mono_text, encoding="utf-8")
    (a.out_dir/"phase5_env.cpp").write_text(env_text, encoding="utf-8")
    m["phase"]="6AV"; m["build_tag"]=BUILD_TAG
    m["phase6av_budget8m"]={
        "source_phase":"6AU",
        "phase6au_hardware_pass":True,
        "phase6au_observed_boundary":{"kind":"BUDGET","target":"0x00291D4E","fault":0,"ticks":2000001,"trace":290705},
        "translated_pack_unchanged":True,
        "allocator_policy_unchanged":True,
        "hard_fences_unchanged":True,
        "old_budget_ticks":OLD_TICKS,
        "new_budget_ticks":NEW_TICKS
    }
    (a.out_dir/"phase6av-manifest.json").write_text(json.dumps(m,indent=2)+"\n",encoding="utf-8")
    print(f"[Phase6AV] EXECUTION BUDGET: {OLD_TICKS} -> {NEW_TICKS}")
    print(f"[Phase6AV] REUSED TRANSLATED SHARDS: {len(list(sd.glob('*.inl')))}")
    print("[Phase6AV] TRANSLATED PACK CHANGES: 0")
    print("[Phase6AV] EMIT RESULT: PASS")
    return 0
if __name__=="__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path

BUILD_TAG = "P6AW-D3D-SPIN-PROBE-20261024-A"
BASE_TAG = "P6AV-BUDGET8M-20261024-A"
COOKIE_OLD = "phase6av_env_build_cookie"
COOKIE_NEW = "phase6aw_env_build_cookie"

def replace_once(text, old, new, label):
    n=text.count(old)
    if n!=1:
        raise SystemExit(f"[Phase6AW] expected one {label}, found {n}")
    return text.replace(old,new,1)

def patch_main(text):
    text=replace_once(text, BASE_TAG, BUILD_TAG, "Phase 6AV build tag")
    old_policy="Policy: Phase 6AV reuses 6AU exactly; budget 2M->8M only; preserve allocator, closure and all hard fences"
    new_policy="Policy: Phase 6AW keeps 6AV behavior; probe the 8M D3D spin without relaxing any fence"
    text=replace_once(text, old_policy, new_policy, "Phase 6AV runtime policy")
    text=text.replace(COOKIE_OLD, COOKIE_NEW)
    text=text.replace("PHASE 6AV","PHASE 6AW").replace("Phase 6AV","Phase 6AW").replace('"P6AV ','"P6AW ')

    state_old="static DWORD s_phase4cBlockTicks = 0u;\n"
    state_new="""static DWORD s_phase4cBlockTicks = 0u;
static DWORD s_phase6awVaRing[32];
static DWORD s_phase6awVaRingPos = 0u;
static DWORD s_phase6awVaRingCount = 0u;
"""
    text=replace_once(text,state_old,state_new,"budget state anchor")

    tick_old="""static void phase4c_budget_tick(DWORD va)
{
    ++s_phase4cBlockTicks;

    if (s_accessFault)
"""
    tick_new="""static void phase4c_budget_tick(DWORD va)
{
    ++s_phase4cBlockTicks;

    s_phase6awVaRing[s_phase6awVaRingPos] = va;
    s_phase6awVaRingPos = (s_phase6awVaRingPos + 1u) & 31u;
    if (s_phase6awVaRingCount < 32u)
        ++s_phase6awVaRingCount;

    if (s_phase4cBlockTicks == 2000000u ||
        s_phase4cBlockTicks == 4000000u ||
        s_phase4cBlockTicks == 6000000u ||
        s_phase4cBlockTicks == 8000000u)
    {
        char sample[256];
        sprintf(
            sample,
            "P6AW SPIN SAMPLE tick=%u va=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
            (unsigned int)s_phase4cBlockTicks,
            (unsigned int)va,
            (unsigned int)g_eax,
            (unsigned int)g_ecx,
            (unsigned int)g_edx,
            (unsigned int)g_ebx,
            (unsigned int)g_esi,
            (unsigned int)g_edi,
            (unsigned int)g_esp);
        trace(sample);
    }

    if (s_accessFault)
"""
    text=replace_once(text,tick_old,tick_new,"budget tick body")

    insert_anchor="#define PHASE4C_BUDGET_TICK(va) \\\n    do { phase4c_budget_tick((DWORD)(va)); } while (0)\n"
    dump_helper="""static void phase6aw_dump_va_ring(void)
{
    DWORD i;
    DWORD start;
    char line[96];

    if (s_phase6awVaRingCount == 0u)
        return;

    start = (s_phase6awVaRingPos + 32u - s_phase6awVaRingCount) & 31u;
    trace("P6AW FINAL VA RING BEGIN");
    for (i = 0u; i < s_phase6awVaRingCount; ++i)
    {
        DWORD index = (start + i) & 31u;
        sprintf(
            line,
            "P6AW VA[%02u]=%08X",
            (unsigned int)i,
            (unsigned int)s_phase6awVaRing[index]);
        trace(line);
    }
    trace("P6AW FINAL VA RING END");
}

"""
    text=replace_once(text,insert_anchor,dump_helper+insert_anchor,"budget macro anchor")

    text=replace_once(text,"    phase4c_log_trace();\n","    phase4c_log_trace();\n    phase6aw_dump_va_ring();\n","trace dump call")

    required=(BUILD_TAG,COOKIE_NEW,"#define PHASE4C_EXEC_BUDGET 8000000u","P6AW SPIN SAMPLE","P6AW FINAL VA RING BEGIN","phase6aw_dump_va_ring();")
    for marker in required:
        if marker not in text:
            raise SystemExit(f"[Phase6AW] patched main lost marker: {marker}")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6AW] stale Phase 6AV cookie remains in main")
    return text

def patch_env(text):
    text=text.replace(COOKIE_OLD,COOKIE_NEW)
    text=text.replace("PHASE 6AV","PHASE 6AW").replace("Phase 6AV","Phase 6AW")
    if COOKIE_NEW not in text:
        raise SystemExit("[Phase6AW] env cookie rewrite did not land")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6AW] stale Phase 6AV cookie remains in env")
    return text

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-dir",type=Path,required=True)
    ap.add_argument("--out-dir",type=Path,required=True)
    a=ap.parse_args()
    for p in (a.base_dir/"main.cpp",a.base_dir/"main_monolithic.cpp",a.base_dir/"phase5_env.cpp",a.base_dir/"phase6av-manifest.json",a.base_dir/"translated_shards"):
        if not p.exists(): raise SystemExit(f"[Phase6AW] missing baseline input: {p}")
    m=json.loads((a.base_dir/"phase6av-manifest.json").read_text(encoding="utf-8"))
    if m.get("phase")!="6AV" or m.get("build_tag")!=BASE_TAG:
        raise SystemExit("[Phase6AW] baseline identity mismatch")

    a.out_dir.mkdir(parents=True,exist_ok=True)
    sd=a.out_dir/"translated_shards"
    if sd.exists(): shutil.rmtree(sd)
    shutil.copytree(a.base_dir/"translated_shards",sd)

    main_text=patch_main((a.base_dir/"main.cpp").read_text(encoding="utf-8"))
    mono_text=patch_main((a.base_dir/"main_monolithic.cpp").read_text(encoding="utf-8"))
    env_text=patch_env((a.base_dir/"phase5_env.cpp").read_text(encoding="utf-8"))
    (a.out_dir/"main.cpp").write_text(main_text,encoding="utf-8")
    (a.out_dir/"main_monolithic.cpp").write_text(mono_text,encoding="utf-8")
    (a.out_dir/"phase5_env.cpp").write_text(env_text,encoding="utf-8")

    m["phase"]="6AW"; m["build_tag"]=BUILD_TAG
    m["phase6aw_d3d_spin_probe"]={
        "source_phase":"6AV",
        "phase6av_hardware":{"boundary":"BUDGET","target":"0x00291D4E","ticks":8000001,"trace":790705,"fault":0},
        "execution_budget_unchanged":8000000,
        "translated_pack_unchanged":True,
        "allocator_policy_unchanged":True,
        "hard_fences_unchanged":True,
        "samples":[2000000,4000000,6000000,8000000],
        "va_ring_entries":32
    }
    (a.out_dir/"phase6aw-manifest.json").write_text(json.dumps(m,indent=2)+"\n",encoding="utf-8")
    print("[Phase6AW] 8M budget preserved")
    print("[Phase6AW] translated pack changes: 0")
    print("[Phase6AW] D3D spin samples: 2M/4M/6M/8M")
    print("[Phase6AW] final VA ring: 32 basic-block addresses")
    print("[Phase6AW] EMIT RESULT: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

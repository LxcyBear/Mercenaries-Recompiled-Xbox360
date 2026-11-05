#!/usr/bin/env python3
"""V6e source-only: add original RedCamera 0x001F89F0 to proven V6d.
The original recomp_options_scale_draw_distance is identity in tracked
recomp_options.c; inline identity so Xbox 360 build needs no Win32 options DLL.
No edits to retail generated files, TrueTUs, callback bounds, or hard fences.
"""
from pathlib import Path
import hashlib, json, re, sys

TAG="[K1-V6e]"
MARKER="K1-V6E-RED-CAMERA-001F89F0-20261105"
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
PARENT="build/phase6_integration_map/k1_pixel_ntread_apc_third_v6d"
TARGET="build/phase6_integration_map/k1_pixel_redcamera_direct_v6e"
ORIGINAL="build/phase3n_final_abi_scale/runtime/gen/recomp_0010.c"
OPTIONS="ports/mercenaries/src/recomp_options.c"
SHARDS="build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"

def sha(b): return hashlib.sha256(b).hexdigest()
def require(ok,message):
    if not ok: raise RuntimeError(message)
def once(s,a,b):
    require(s.count(a)==1,"Expected exactly one source insertion anchor: "+a[:110])
    return s.replace(a,b,1)
def main():
    repo=Path.cwd()
    prior=repo/PARENT
    target=repo/TARGET
    manifest=json.loads((prior/"v6d-third-apc-manifest.json").read_text(encoding="utf-8-sig"))
    parent_bytes=(prior/"main.cpp").read_bytes()
    require(manifest["retail_sha256"]==RETAIL,"Retail XBE identity mismatch")
    require(manifest["staged_v6d_sha256"]==sha(parent_bytes),"V6d source hash mismatch")
    require(manifest["true_tu_count"]==64,"V6d TrueTU count mismatch")
    true_tus=sorted((repo/SHARDS).glob("translated_???.cpp"))
    require(len(true_tus)==64,"TrueTU source count mismatch")
    tu_hash={p.name:sha(p.read_bytes()) for p in true_tus}
    require(tu_hash==manifest["true_tu_sha256"],"V6d TrueTU source hash mismatch")
    opts=(repo/OPTIONS).read_text(encoding="utf-8-sig").replace("\r\n","\n")
    expected='float recomp_options_scale_draw_distance(float distance) {\n    /* Keep the generated hook ABI, but always preserve the authored distance. */\n    return distance;\n}'
    require(opts.count(expected)==1,"Options helper is not the verified identity function")
    original_bytes=(repo/ORIGINAL).read_bytes()
    # Specific generated-code snapshot hardware owner confirmed on 2026-11-05.
    require(sha(original_bytes).upper()=="BF21064BF05C69974031E822AE39B8EA4B2E6519C35F08B0B6C708B9F4FDDE1E","Original recomp_0010.c SHA mismatch")
    original=original_bytes.decode("utf-8-sig").replace("\r\n","\n")
    m=re.search(r"(?m)^void sub_001F89F0\(void\)\s*\{.*?^\}",original,re.S|re.M)
    require(m is not None,"Original RedCamera implementation missing")
    fn=m.group(0)
    require(fn.count("recomp_options_scale_draw_distance(xmm0)")==1,"Helper call differs")
    require(fn.count("esp += 8; return; /* ret 4 */")==1,"Original ret4 differs")
    require("sub_" not in fn.replace("sub_001F89F0",""),"Unexpected translated dependency")
    require(fn.count("GUEST_WRITEF32(")==4,"Unexpected RedCamera writes")
    # Identity hook is verified above, so preserving xmm0 is equivalent.
    fn=once(fn,"    xmm0 = recomp_options_scale_draw_distance(xmm0);",
        "    /* "+MARKER+": exact tracked options helper is identity (return distance). */")
    source=parent_bytes.decode("utf-8-sig")
    newline="\r\n" if "\r\n" in source else "\n"
    source=source.replace("\r\n","\n")
    require("void sub_001F89F0(void)" not in source,"V6e function already staged")
    require("case 0x001F89F0u:" not in source,"V6e dispatch already staged")
    require("case 0x0020EB00u: return sub_0020EB00;" in source,"V6c dispatch unavailable")
    require("K1-V6D-THIRD-APC-0ACE8000-20261104" in source,"V6d read evidence missing")
    # V6c's implementation may live in translated shards, rather than main.cpp.
    # Insert before the *lookup function* that owns its dispatch case, ensuring
    # the added function is a top-level definition visible to that lookup.
    dispatch="    case 0x0020EB00u: return sub_0020EB00;"
    require(source.count(dispatch)==1,"V6c dispatch not unique")
    case_pos=source.index(dispatch)
    lookup_headers=list(re.finditer(
        r"(?m)^[ \t]*(?:(?:static|inline)\s+)*recomp_func_t\s+"
        r"[A-Za-z_][A-Za-z_0-9]*\s*\([^;{}]*\)\s*\{",
        source[:case_pos]))
    require(bool(lookup_headers),"Could not identify enclosing lookup function")
    lookup=lookup_headers[-1]
    require("switch" in source[lookup.end():case_pos],
            "V6c dispatch is not within selected lookup")
    source=source[:lookup.start()]+fn+"\n\n"+source[lookup.start():]
    source=once(source,"    case 0x0020EB00u: return sub_0020EB00;",
        "    case 0x0020EB00u: return sub_0020EB00;\n    case 0x001F89F0u: return sub_001F89F0;")
    require(source.count(MARKER)==1,"V6e marker count mismatch")
    require(source.count("case 0x001F89F0u:")==1,"V6e dispatch count mismatch")
    # Verify V6d behavior anchors remain unchanged.
    for anchor in ("K1-V6b APC QUEUED","K1-V6b APC DELIVERED",
       "0x0ACE8000u","s_k1v6Delivered >= 16u","P6DQ ROCKET HARD STOP"):
        require(source.count(anchor)==parent_bytes.decode("utf-8-sig").count(anchor),
           "Existing V6d behavior anchor count changed: "+anchor)
    result=source.replace("\n",newline).encode("utf-8")
    result_manifest={
       "stage":"V6E_SOURCE_ONLY_NOT_BUILT_OR_HARDWARE_TESTED",
       "retail_sha256":RETAIL,
       "target":"0x001F89F0","marker":MARKER,
       "parent_v6d_sha256":sha(parent_bytes),
       "original_recomp_0010_sha256":sha(original_bytes),
       "options_helper":"recomp_options_scale_draw_distance: verified identity",
       "options_source_sha256":sha((repo/OPTIONS).read_bytes()),
       "staged_sha256":sha(result),
       "true_tu_count":64,"true_tu_sha256":tu_hash,
       "parent_unmodified":True,"hard_fences_preserved":True,
       "hardware_tested":False,"display_calls_proven":False}
    payload=json.dumps(result_manifest,indent=2)+"\n"
    outputs=((target/"main.cpp",result),(target/"v6e-redcamera-manifest.json",payload.encode()))
    for path,data in outputs:
        if path.exists(): require(path.read_bytes()==data,"Refuse overwrite of changed candidate: "+str(path))
    target.mkdir(parents=True,exist_ok=True)
    for path,data in outputs:
        if not path.exists():path.write_bytes(data)
    require((prior/"main.cpp").read_bytes()==parent_bytes,"V6d source changed during staging")
    print(TAG+" SOURCE PASS: original 0x001F89F0 (4 F32 writes, ret4)")
    print(TAG+" PASS: repo options helper is exact identity; no fake scaling")
    print(TAG+" PASS: new direct dispatch; V6d APC, hard fences, 64 TrueTUs unchanged")
    print(TAG+" SOURCE-ONLY: no XDK compile or hardware validation")
    print(TAG+" MAIN: "+str(target/"main.cpp"))
    print(TAG+" SHA256: "+sha(result))
if __name__=="__main__":
    try:main()
    except Exception as e:
        print(TAG+" BLOCKED: "+str(e),file=sys.stderr)
        sys.exit(1)

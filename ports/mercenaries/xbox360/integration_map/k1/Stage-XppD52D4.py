#!/usr/bin/env python3
"""Stage only retail XInputGetCapabilities XPP D52D4 in an inherited 64-TU set.

Proven retail-generated body SHA is verified before any transform. The native
Xbox 360 XInput capability query is serialized to the *original Xbox* 28-byte
guest buffer, NOT memcpy'd from the X360's different XINPUT_CAPABILITIES struct.
No game code/bytes are shipped in this script. Never relax MMIO hard fences.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

MARKER="XPP-D52D4-NATIVE-CAPABILITIES-20261031"
PARENT="XPP-D5272-NATIVE-XINPUTOPEN-20261031"
TARGET=0x002D52D4
END=0x002D54AC
ORIGINAL="recomp_0013.c"
ORIGINAL_SHA="80aa0150e3d680d11925e2b2c3465509930b557fc511f625bafbbdea39e09ed5"
HELPER="recomp_xinput_get_capabilities"
FENCE="phase4c_direct_frontier(0x002D52D4u);"
CALL="sub_002D52D4();"
HEADER='#include "translated_runtime.h"'
SHARD=re.compile(r"translated_\d{3}\.cpp\Z")
DEFINITION=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})[ \t]*\([ \t]*void[ \t]*\)\s*\{")
SUBCALL=re.compile(r"\bsub_([0-9A-Fa-f]{8})\s*\(")
HELPERCALL=re.compile(r"\b(recomp_[A-Za-z_0-9]+)\s*\(")
SHAPE=(r"\beax\s*=\s*recomp_xinput_get_capabilities\(\s*"
       r"GUEST_READ32\(\s*esp\s*\+\s*4u\s*\)\s*,\s*"
       r"GUEST_READ32\(\s*esp\s*\+\s*8u\s*\)\s*\)\s*;\s*"
       r"esp\s*\+=\s*12u\s*;\s*return\s*;")
NATIVE=r'''/* XPP-D52D4-NATIVE-CAPABILITIES-20261031: original Xbox 28-byte guest ABI.
 * The X360 XINPUT_CAPABILITIES layout is NOT an original-Xbox XPP layout.
 * Original Mercenaries recomp_manual.c zeroes 28 guest bytes on success and
 * copies only Type/SubType/Flags from its host capability probe.
 */
static uint32_t recomp_xinput_get_capabilities(uint32_t handle,
                                               uint32_t capabilities_address)
{
    const uint32_t port=handle-1u; /* matches D5272 handle=port+1 */
    uint32_t result=ERROR_DEVICE_NOT_CONNECTED;
    XINPUT_CAPABILITIES caps;
    ZeroMemory(&caps,sizeof(caps));
    if (handle>=1u && handle<=4u)
        result=(uint32_t)XInputGetCapabilities((DWORD)port,0u,&caps);
    if (result==ERROR_SUCCESS &&
        capabilities_address>=0x00010000u &&
        capabilities_address<=0x04000000u-28u)
    {
        /* Use guest-memory byte-order adapters; never memcpy a native struct.
         * Seven DWORD writes exactly cover the original 28-byte output.
         * Original host intentionally leaves unsupported analog/motor caps 0.
         */
        for (uint32_t i=0u;i<28u;i+=4u)
            GUEST_WRITE32(capabilities_address+i,0u);
        const uint32_t first=(uint32_t)caps.Type
            | ((uint32_t)caps.SubType<<8u)
            | ((uint32_t)caps.Flags<<16u);
        GUEST_WRITE32(capabilities_address,first);
    }
    static unsigned trace_count=0u;
    if (++trace_count<=8u)
    {
        char line[160];
        sprintf(line,"XPP XINPUT capabilities: handle=%u port=%u status=%08X out=%08X",
                (unsigned)handle,(unsigned)port,(unsigned)result,
                (unsigned)capabilities_address);
        trace(line);
    }
    return result;
}
'''

def sha(data):
    return hashlib.sha256(data).hexdigest()

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path))
    if not spec or not spec.loader:
        raise ValueError("Original source reader unavailable")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def nl(text):
    if text.count("\r")!=text.count("\r\n"):
        raise ValueError("Mixed newline source, refuse silent normalization")
    return "\r\n" if "\r\n" in text else "\n"

def original_body_dependencies(masked):
    # SUBCALL matches function definitions too. Search AFTER the source
    # declaration, not the whole translated C function: the declaration
    # "void sub_002D52D4(void)" is NOT a recursive guest call.
    entry=list(re.finditer(
        r"(?m)^[ \t]*void[ \t]+sub_002D52D4[ \t]*\([ \t]*void[ \t]*\)\s*\{",
        masked))
    if len(entry)!=1:
        raise ValueError("Original D52D4 masked function declaration missing or ambiguous")
    body=masked[entry[0].end():]
    calls=sorted(set(SUBCALL.findall(body)))
    helpers=sorted(set(HELPERCALL.findall(body)))
    return calls,helpers

def parse_original(source,reader):
    if sha(source.encode("utf-8"))!=ORIGINAL_SHA:
        raise ValueError("Original XPP D52D4 function SHA changed; no build")
    m=list(re.finditer(r"(?m)^[ \t]*(?:static\s+)?void\s+sub_002D52D4\s*\(\s*void\s*\)\s*\{",source))
    if len(m)!=1:
        raise ValueError("Original retail D52D4 declaration not unique")
    prefix=source[:m[0].start()]
    if re.sub(r"/\*.*?\*/|//[^\n]*","",prefix,flags=re.S).strip():
        raise ValueError("Unexpected executable source prefix")
    canonical=prefix+"void sub_002D52D4(void)\n{"+source[m[0].end():]
    code=reader.mask_noncode(canonical)
    if (len(re.findall(r"\bRECOMP_TRACE_FUNC\(\s*0x002D52D4u\s*\);",code))!=1 or
        len(re.findall(SHAPE,code))!=1 or
        HELPER not in code):
        raise ValueError("Exact original capabilities EAX/ESP+12/ret ABI not found")
    calls,helpers=original_body_dependencies(code)
    if calls or helpers!=[HELPER]:
        raise ValueError(
            "Original translated D52D4 has unreviewed dependencies: "
            "direct_callees="+",".join(calls)+" helpers="+",".join(helpers))
    output=[]
    probes=0
    for line in canonical.splitlines():
        output.append(line.replace("__debugbreak()","PHASE4C_DEBUGBREAK()"))
        if re.fullmatch(r"\s*RECOMP_TRACE_FUNC\(\s*0x002D52D4u\s*\);\s*",line):
            probes+=1
            output.extend([
                "    PHASE4C_BUDGET_TICK(0x002D52D4u);",
                "    {",
                "        static unsigned entries=0u;",
                "        if (++entries<=8u)",
                "        {",
                "            char msg[128];",
                '            sprintf(msg,"XPP D52D4 ENTRY n=%u esp=%08X eax=%08X",',
                "                (unsigned)entries,(unsigned)esp,(unsigned)eax);",
                "            trace(msg);",
                "        }",
                "    }",
            ])
    if probes!=1:
        raise ValueError("No exact generated entry instrumentation site")
    emitted="\n".join(output)+"\n"
    if len(re.findall(SHAPE,reader.mask_noncode(emitted)))!=1:
        raise ValueError("Original capabilities guest return ABI changed")
    return emitted

def rewrite(text,is_host=False):
    count=text.count(FENCE)
    if not count:
        return text,0
    if not is_host and HEADER not in text:
        raise ValueError("Direct caller lacks known translated runtime header")
    newline=nl(text)
    proto="void sub_002D52D4(void);"
    if proto not in text:
        if HEADER in text:
            text=text.replace(HEADER,HEADER+newline+proto,1)
        else:
            text=proto+newline+text
    text=text.replace(FENCE,CALL)
    if FENCE in text:
        raise ValueError("Unreplaced live frontier")
    return text,count

def stage(a):
    for p in (a.shards,a.parent_main,a.parent_manifest,a.generated,a.functions,a.emitter):
        if not p.exists():
            raise ValueError("Missing original user-local input "+str(p))
    parent=json.loads(a.parent_manifest.read_text(encoding="utf-8-sig"))
    if (parent.get("marker")!=PARENT or
        parent.get("status")!="SOURCE_CLOSED_STAGED_NO_XDK" or
        parent.get("hardware_target")!="0x002D5272" or
        parent.get("native_bridge")!=PARENT or
        parent.get("native_real_input") is not True or
        parent.get("guest_display_calls_injected") is not False or
        parent.get("mmio_fences")!="UNCHANGED" or
        parent.get("hard_fences")!="UNCHANGED" or
        Path(parent.get("staged_directory","MISSING")).resolve()!=a.shards.resolve() or
        Path(parent.get("staged_main","MISSING")).resolve()!=a.parent_main.resolve() or
        sha(a.parent_main.read_bytes())!=parent.get("new_main_sha")):
        raise ValueError("Previously proven D5272 parent stage/manifest changed")
    files=sorted(p for p in a.shards.iterdir() if SHARD.fullmatch(p.name))
    headers=sorted(a.shards.glob("*.h"))
    if len(files)!=64 or not (a.shards/"translated_runtime.h").is_file():
        raise ValueError("D5272 source must have exactly 64 TrueTUs")
    for p in files+headers:
        expected=parent.get("new_owner_hashes",{}).get(
            p.name,parent.get("original_owner_hashes",{}).get(p.name))
        if not expected or sha(p.read_bytes())!=expected:
            raise ValueError("D5272 parent source SHA drift: "+p.name)
    before={p.name:p.read_text(encoding="utf-8") for p in files}
    host=a.parent_main.read_text(encoding="utf-8")
    owners=[name for name,text in before.items()
            if "/* "+PARENT+";" in text]
    if len(owners)!=1 or before[owners[0]].count("#include <xtl.h>")!=1:
        raise ValueError("Prior native XInput owner ambiguous or absent")
    owner=owners[0]
    if (sum("XPP D5272 ENTRY" in t for t in before.values())!=1 or
        sum("XPP 002D559B ENTRY" in t for t in before.values())!=1 or
        "K1S HALGETVECTOR44 ESI SLOT:" not in before["translated_044.cpp"] or
        "P6DQ-R51-MM173-FRAME-20261029-A" not in host):
        raise ValueError("Known-good native controller chain/K1S/host provenance missing")
    if any(MARKER in t for t in list(before.values())+[host]):
        raise ValueError("D52D4 native helper already staged")
    if any(DEFINITION.search(t) and any(int(m,16)==TARGET for m in DEFINITION.findall(t))
           for t in list(before.values())+[host]):
        raise ValueError("D52D4 already defined; no duplicate guest function")
    base=load(a.emitter,"xpp_d52d4_local_reader")
    ranges,by_name=base.load_ranges(a.functions)
    funcs=base.load_generated(a.generated,by_name)
    rg=ranges.get(TARGET)
    item=funcs.get(TARGET)
    if not rg or rg["start"]!=TARGET or rg["end"]!=END:
        raise ValueError("Retail D52D4 start/end mismatch")
    if not item or item["file"]!=ORIGINAL:
        raise ValueError("Exact original D52D4 generated source not found")
    src=item["source"]
    body=parse_original(src,base)
    # Only metadata is published. Private exact original source saved OUTSIDE git
    # on the user's own PC, for review when any strict semantic gate fails.
    a.private.parent.mkdir(parents=True,exist_ok=True)
    a.private.write_text("USER-LOCAL ORIGINAL RETAIL SOURCE: DO NOT COMMIT\n\n"+src,encoding="utf-8")
    n=nl(before[owner])
    if before[owner].count("#include <xtl.h>"+n)!=1:
        raise ValueError("Unique XDK include anchor required")
    extra=before[owner].replace(
        "#include <xtl.h>"+n,
        "#include <xtl.h>"+n+NATIVE.replace("\n",n)+n,1)
    extra=extra.rstrip("\r\n")+n+n+(
        "/* "+MARKER+" original retail XPP D52D4 */"+n+body.replace("\n",n))
    altered={}
    calls=0
    for name,text in before.items():
        candidate=extra if name==owner else text
        candidate,found=rewrite(candidate)
        calls+=found
        if candidate!=text:
            altered[name]=candidate.encode("utf-8")
    new_main,host_calls=rewrite(host,is_host=True)
    calls+=host_calls
    if calls<1 or not altered or len(altered)>12:
        raise ValueError("No exact hardware-observed direct callsites, or broad TU mutations")
    if sum("XPP D52D4 ENTRY" in z.decode("utf-8") for z in altered.values())!=1:
        raise ValueError("D52D4 entry instrumentation missing/duplicate")
    if sum("/* "+MARKER+";" in z.decode("utf-8") for z in altered.values())!=1:
        raise ValueError("Unique capabilities backend absent")
    if a.out.resolve()==a.shards.resolve() or a.out_main.resolve()==a.parent_main.resolve():
        raise ValueError("Refusing to overwrite original known-good D5272 stage")
    expected={p.name:altered.get(p.name,p.read_bytes()) for p in files+headers}
    a.out.mkdir(parents=True,exist_ok=True)
    if {p.name for p in a.out.iterdir()} not in (set(),set(expected)):
        raise ValueError("Existing output incompatible; no overwrites")
    for name,buf in expected.items():
        dest=a.out/name
        if dest.exists() and dest.read_bytes()!=buf:
            raise ValueError("Existing staged shard differs: "+name)
        if not dest.exists():
            dest.write_bytes(buf)
    a.out_main.parent.mkdir(parents=True,exist_ok=True)
    main_bytes=new_main.encode("utf-8")
    if a.out_main.exists() and a.out_main.read_bytes()!=main_bytes:
        raise ValueError("Existing staged host differs")
    if not a.out_main.exists():
        a.out_main.write_bytes(main_bytes)
    manifest={
        "marker":MARKER,"status":"SOURCE_CLOSED_STAGED_NO_XDK",
        "hardware_target":"0x002D52D4","hardware_ticks":27107602,
        "original_function_sha256":ORIGINAL_SHA,
        "source_file":ORIGINAL,"source_return":"EAX/ESP_PLUS_12_RET8",
        "native_bridge":MARKER,
        "native_capability_buffer_bytes":28,"native_struct_memcpy":False,
        "previous_manifest":str(a.parent_manifest),
        "original_owner_hashes":{p.name:sha(p.read_bytes()) for p in files+headers},
        "new_owner_hashes":{name:sha(buf) for name,buf in altered.items()},
        "changed_true_tus":sorted(altered),
        "staged_directory":str(a.out.resolve()),
        "staged_main":str(a.out_main.resolve()),
        "new_main_sha":sha(main_bytes),
        "parent_input_owner":owner,
        "original_direct_frontier_replacements":calls,
        "guest_display_calls_injected":False,
        "mmio_fences":"UNCHANGED","hard_fences":"UNCHANGED",
    }
    a.manifest.parent.mkdir(parents=True,exist_ok=True)
    a.manifest.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("[XPP-D52D4] SOURCE CLOSED: original XInputGetCapabilities EAX + ret8")
    print("[XPP-D52D4] NATIVE: real XInputGetCapabilities(port,0,caps) + 28-byte guest output")
    print("[XPP-D52D4] Original direct callsites=%d, changed TrueTUs=%s"%
          (calls,",".join(sorted(altered))))
    print("[XPP-D52D4] STAGE PASS: 64 inherited TUs, no XDK, no display injection")

def self_test():
    assert TARGET==0x002D52D4 and END-TARGET==472
    declaration="void sub_002D52D4(void)\n{\n"
    body=declaration+" eax = recomp_xinput_get_capabilities(1u,2u);\n}\n"
    assert original_body_dependencies(body)==([],[HELPER])
    recursive=declaration+" sub_002D52D4();\n}\n"
    assert original_body_dependencies(recursive)==(["002D52D4"],[])
    other=declaration+" sub_002D6B3E();\n}\n"
    assert original_body_dependencies(other)==(["002D6B3E"],[])
    assert "XInputGetCapabilities((DWORD)port,0u,&caps)" in NATIVE
    assert "i<28u;i+=4u" in NATIVE
    assert "GUEST_WRITE32(capabilities_address+i,0u)" in NATIVE
    assert "GUEST_WRITE32(capabilities_address,first)" in NATIVE
    assert "handle>=1u && handle<=4u" in NATIVE
    assert "memcpy(" not in NATIVE and "GUEST_WRITE8" not in NATIVE
    assert re.search(SHAPE,"eax = recomp_xinput_get_capabilities(GUEST_READ32(esp + 4u), GUEST_READ32(esp + 8u));\n esp += 12u; return;")
    for newline in ("\n","\r\n"):
        original=HEADER+newline+"void caller(void) { "+FENCE+" }"+newline
        edited,count=rewrite(original)
        assert count==1 and FENCE not in edited and CALL in edited
        again,count2=rewrite(edited)
        assert count2==0 and again==edited
    print("[XPP-D52D4] SYNTHETIC PASS: native XInput capability guest buffer and direct-call ABI")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    for k in ("shards","parent_main","parent_manifest","generated","functions",
              "emitter","out","out_main","manifest","private"):
        p.add_argument("--"+k.replace("_","-"),type=Path)
    a=p.parse_args()
    if a.self_test:
        self_test()
        return
    for k in ("shards","parent_main","parent_manifest","generated","functions",
              "emitter","out","out_main","manifest","private"):
        if getattr(a,k) is None:
            p.error("--"+k.replace("_","-")+" is required")
    stage(a)

if __name__=="__main__":
    main()

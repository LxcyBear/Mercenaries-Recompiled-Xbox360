#!/usr/bin/env python3
"""Stage retail XInputGetState XPP D54AC after hardware-proven capabilities.

Source-hash-validated original translated function + native X360 poll;
exact Xbox original 22-byte state ABI, 8 analog buttons and four thumb axes.
No private game code published; no synthetic input or display, no MMIO changes.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

MARKER="XPP-D54AC-NATIVE-GETSTATE-20261031"
PARENT="XPP-D52D4-NATIVE-CAPABILITIES-20261031"
TARGET=0x002D54AC
END=0x002D551F
ORIGINAL="recomp_0013.c"
ORIGINAL_SHA="48e4ccc7ccc0ae3bfa852d584996f6f1ed034d0491f05433722054038f42a0e2"
HELPER="recomp_xinput_get_state"
FENCE="phase4c_direct_frontier(0x002D54ACu);"
CALL="sub_002D54AC();"
HEADER='#include "translated_runtime.h"'
SHARD=re.compile(r"translated_\d{3}\.cpp\Z")
DEFINITION=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})[ \t]*\([ \t]*void[ \t]*\)\s*\{")
SUBCALL=re.compile(r"\bsub_([0-9A-Fa-f]{8})\s*\(")
HELPERCALL=re.compile(r"\b(recomp_[A-Za-z_0-9]+)\s*\(")
SHAPE=(r"\beax\s*=\s*recomp_xinput_get_state\(\s*"
       r"GUEST_READ32\(\s*esp\s*\+\s*4u\s*\)\s*,\s*"
       r"GUEST_READ32\(\s*esp\s*\+\s*8u\s*\)\s*\)\s*;\s*"
       r"esp\s*\+=\s*12u\s*;\s*return\s*;")
NATIVE=r'''/* XPP-D54AC-NATIVE-GETSTATE-20261031: original Xbox exact 22-byte state.
 * Public original compat code copies 22 bytes, NOT sizeof(XBOX_INPUT_STATE),
 * and maps 360 buttons to Xbox's 8 analog-button bytes. Do not write 24.
 * Original guest: DWORD packet; WORD digital; 8 analog bytes;
 * 4 signed SHORT thumb axes (offsets 14,16,18,20).
 */
static uint32_t recomp_xinput_get_state(uint32_t handle,
                                        uint32_t state_address)
{
    uint32_t result=ERROR_DEVICE_NOT_CONNECTED;
    const uint32_t port=handle-1u;
    XINPUT_STATE native;
    ZeroMemory(&native,sizeof(native));
    if (handle>=1u && handle<=4u)
        result=(uint32_t)XInputGetState((DWORD)port,&native);
    if (result==ERROR_SUCCESS &&
        state_address>=0x00010000u &&
        state_address<=0x04000000u-22u)
    {
        const WORD native_buttons=native.Gamepad.wButtons;
        const uint32_t digital=(uint32_t)(native_buttons & 0x00FFu);
        const uint32_t a=(native_buttons & XINPUT_GAMEPAD_A) ? 255u : 0u;
        const uint32_t b=(native_buttons & XINPUT_GAMEPAD_B) ? 255u : 0u;
        const uint32_t x=(native_buttons & XINPUT_GAMEPAD_X) ? 255u : 0u;
        const uint32_t y=(native_buttons & XINPUT_GAMEPAD_Y) ? 255u : 0u;
        const uint32_t black=(native_buttons & XINPUT_GAMEPAD_RIGHT_SHOULDER) ? 255u : 0u;
        const uint32_t white=(native_buttons & XINPUT_GAMEPAD_LEFT_SHOULDER) ? 255u : 0u;
        const uint32_t ab_and_buttons=digital | (a<<16u) | (b<<24u);
        const uint32_t xy_bw=x | (y<<8u) | (black<<16u) | (white<<24u);
        const uint32_t triggers_lx=(uint32_t)native.Gamepad.bLeftTrigger |
            ((uint32_t)native.Gamepad.bRightTrigger<<8u) |
            ((uint32_t)(uint16_t)native.Gamepad.sThumbLX<<16u);
        const uint32_t ly_rx=(uint32_t)(uint16_t)native.Gamepad.sThumbLY |
            ((uint32_t)(uint16_t)native.Gamepad.sThumbRX<<16u);
        /* Five DWORDs + one WORD = EXACTLY 22 guest bytes, no 24B overwrite.
         * GUEST_WRITE16 uses the original little-endian guest accessor.
         */
        GUEST_WRITE32(state_address+0u,native.dwPacketNumber);
        GUEST_WRITE32(state_address+4u,ab_and_buttons);
        GUEST_WRITE32(state_address+8u,xy_bw);
        GUEST_WRITE32(state_address+12u,triggers_lx);
        GUEST_WRITE32(state_address+16u,ly_rx);
        GUEST_WRITE16(state_address+20u,(uint16_t)native.Gamepad.sThumbRY);
    }
    static unsigned trace_count=0u;
    if (++trace_count<=8u)
    {
        char line[196];
        sprintf(line,"XPP XINPUT state: handle=%u port=%u status=%08X out=%08X packet=%u buttons=%04X",
                (unsigned)handle,(unsigned)port,(unsigned)result,
                (unsigned)state_address,(unsigned)native.dwPacketNumber,
                (unsigned)native.Gamepad.wButtons);
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
    # "void sub_002D54AC(void)" is NOT a recursive guest call.
    entry=list(re.finditer(
        r"(?m)^[ \t]*void[ \t]+sub_002D54AC[ \t]*\([ \t]*void[ \t]*\)\s*\{",
        masked))
    if len(entry)!=1:
        raise ValueError("Original D54AC masked function declaration missing or ambiguous")
    body=masked[entry[0].end():]
    calls=sorted(set(SUBCALL.findall(body)))
    helpers=sorted(set(HELPERCALL.findall(body)))
    return calls,helpers

def parse_original(source,reader):
    if sha(source.encode("utf-8"))!=ORIGINAL_SHA:
        raise ValueError("Original XPP D54AC function SHA changed; no build")
    m=list(re.finditer(r"(?m)^[ \t]*(?:static\s+)?void\s+sub_002D54AC\s*\(\s*void\s*\)\s*\{",source))
    if len(m)!=1:
        raise ValueError("Original retail D54AC declaration not unique")
    prefix=source[:m[0].start()]
    if re.sub(r"/\*.*?\*/|//[^\n]*","",prefix,flags=re.S).strip():
        raise ValueError("Unexpected executable source prefix")
    canonical=prefix+"void sub_002D54AC(void)\n{"+source[m[0].end():]
    code=reader.mask_noncode(canonical)
    if (len(re.findall(r"\bRECOMP_TRACE_FUNC\(\s*0x002D54ACu\s*\);",code))!=1 or
        len(re.findall(SHAPE,code))!=1 or
        HELPER not in code):
        raise ValueError("Exact original XInputGetState EAX/ESP+12/ret ABI not found; inspect LOCAL_ONLY source")
    calls,helpers=original_body_dependencies(code)
    if calls or helpers!=[HELPER]:
        raise ValueError(
            "Original translated D54AC has unreviewed dependencies: "
            "direct_callees="+",".join(calls)+" helpers="+",".join(helpers))
    output=[]
    probes=0
    for line in canonical.splitlines():
        output.append(line.replace("__debugbreak()","PHASE4C_DEBUGBREAK()"))
        if re.fullmatch(r"\s*RECOMP_TRACE_FUNC\(\s*0x002D54ACu\s*\);\s*",line):
            probes+=1
            output.extend([
                "    PHASE4C_BUDGET_TICK(0x002D54ACu);",
                "    {",
                "        static unsigned entries=0u;",
                "        if (++entries<=8u)",
                "        {",
                "            char msg[128];",
                '            sprintf(msg,"XPP D54AC ENTRY n=%u esp=%08X eax=%08X",',
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
    proto="void sub_002D54AC(void);"
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
        parent.get("hardware_target")!="0x002D52D4" or
        parent.get("native_bridge")!=PARENT or
        parent.get("native_capability_buffer_bytes")!=28 or
        parent.get("native_struct_memcpy") is not False or
        parent.get("source_return")!="EAX/ESP_PLUS_12_RET8" or
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
    owner=parent.get("parent_input_owner")
    if (owner not in before or
        before[owner].count("#include <xtl.h>")!=1 or
        before[owner].count("/* "+PARENT+":")!=1):
        raise ValueError("Inherited D52D4 real native-input helper owner not unique")
    if (sum("XPP D52D4 ENTRY" in t for t in before.values())!=1 or
        sum("XPP D5272 ENTRY" in t for t in before.values())!=1 or
        sum("XPP 002D559B ENTRY" in t for t in before.values())!=1 or
        "K1S HALGETVECTOR44 ESI SLOT:" not in before["translated_044.cpp"] or
        "P6DQ-R51-MM173-FRAME-20261029-A" not in host):
        raise ValueError("Known-good native controller chain/K1S/host provenance missing")
    if any(MARKER in t for t in list(before.values())+[host]):
        raise ValueError("D54AC native state helper already staged")
    if any(DEFINITION.search(t) and any(int(m,16)==TARGET for m in DEFINITION.findall(t))
           for t in list(before.values())+[host]):
        raise ValueError("D54AC already defined; no duplicate guest function")
    base=load(a.emitter,"xpp_d52d4_local_reader")
    ranges,by_name=base.load_ranges(a.functions)
    funcs=base.load_generated(a.generated,by_name)
    rg=ranges.get(TARGET)
    item=funcs.get(TARGET)
    if not rg or rg["start"]!=TARGET or rg["end"]!=END:
        raise ValueError("Retail D54AC start/end mismatch")
    if not item or item["file"]!=ORIGINAL:
        raise ValueError("Exact original D54AC generated source not found")
    src=item["source"]
    a.private.parent.mkdir(parents=True,exist_ok=True)
    a.private.write_text(
        "USER-LOCAL ORIGINAL D54AC SOURCE (DO NOT COMMIT)\n\n"+src,
        encoding="utf-8")
    body=parse_original(src,base)
    n=nl(before[owner])
    if before[owner].count("#include <xtl.h>"+n)!=1:
        raise ValueError("Unique XDK include anchor required")
    extra=before[owner].replace(
        "#include <xtl.h>"+n,
        "#include <xtl.h>"+n+NATIVE.replace("\n",n)+n,1)
    extra=extra.rstrip("\r\n")+n+n+(
        "/* "+MARKER+" original retail XPP D54AC */"+n+body.replace("\n",n))
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
    if sum("XPP D54AC ENTRY" in z.decode("utf-8") for z in altered.values())!=1:
        raise ValueError("D54AC entry instrumentation missing/duplicate")
    # Check the two actual emitted tags, not a non-existent ';' variant.
    # Both are required exactly once, within the same native-input owner TU.
    native_tag="/* "+MARKER+":"
    guest_tag="/* "+MARKER+" original retail XPP D54AC */"
    marked=[name for name,blob in altered.items()
            if native_tag in blob.decode("utf-8")]
    guest_marked=[name for name,blob in altered.items()
                  if guest_tag in blob.decode("utf-8")]
    if (marked!=[owner] or guest_marked!=[owner] or
        altered[owner].decode("utf-8").count(native_tag)!=1 or
        altered[owner].decode("utf-8").count(guest_tag)!=1):
        raise ValueError("Native XInputGetState bridge and original guest body must "
                         "be unique in the inherited controller owner TrueTU")
    if a.out.resolve()==a.shards.resolve() or a.out_main.resolve()==a.parent_main.resolve():
        raise ValueError("Refusing to overwrite original known-good D52D4 stage")
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
        "hardware_target":"0x002D54AC","hardware_ticks":27107620,
        "original_function_sha256":ORIGINAL_SHA,
        "source_file":ORIGINAL,"source_return":"EAX/ESP_PLUS_12_RET8",
        "native_bridge":MARKER,
        "native_state_buffer_bytes":22,"native_struct_memcpy":False,
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
    print("[XPP-D54AC] SOURCE CLOSED: original XInputGetState EAX and RET8")
    print("[XPP-D54AC] NATIVE: real XInputGetState + EXACT 22-byte original Xbox state")
    print("[XPP-D54AC] Replaced original direct callsites=%d, changed TrueTUs=%s"%
          (calls,",".join(sorted(altered))))
    print("[XPP-D54AC] STAGE PASS: 64 inherited TUs, no XDK, no forced graphics")


def self_test():
    assert TARGET==0x002D54AC and END-TARGET==115
    assert PARENT=="XPP-D52D4-NATIVE-CAPABILITIES-20261031"
    assert ORIGINAL_SHA=="48e4ccc7ccc0ae3bfa852d584996f6f1ed034d0491f05433722054038f42a0e2"
    declaration="void sub_002D54AC(void)\n{\n"
    assert original_body_dependencies(declaration+
        " eax = recomp_xinput_get_state(1u,2u);\n}\n")==([],[HELPER])
    assert original_body_dependencies(declaration+" sub_002D54AC();\n}\n")==(["002D54AC"],[])
    assert NATIVE.count("XInputGetState((DWORD)port,&native)")==1
    assert NATIVE.count("GUEST_WRITE32(state_address+")==5
    assert NATIVE.count("GUEST_WRITE16(state_address+20u,")==1
    assert "state_address<=0x04000000u-22u" in NATIVE
    assert "GUEST_WRITE32(state_address+20u" not in NATIVE
    assert "memcpy(" not in NATIVE
    for button in ("XINPUT_GAMEPAD_A","XINPUT_GAMEPAD_B",
                   "XINPUT_GAMEPAD_X","XINPUT_GAMEPAD_Y",
                   "XINPUT_GAMEPAD_RIGHT_SHOULDER","XINPUT_GAMEPAD_LEFT_SHOULDER"):
        assert button in NATIVE
    assert "sThumbLX" in NATIVE and "sThumbLY" in NATIVE
    assert "sThumbRX" in NATIVE and "sThumbRY" in NATIVE
    assert re.search(SHAPE,"eax = recomp_xinput_get_state(GUEST_READ32(esp + 4u), GUEST_READ32(esp + 8u));\n esp += 12u; return;")
    native_tag="/* "+MARKER+":"
    guest_tag="/* "+MARKER+" original retail XPP D54AC */"
    assert NATIVE.count(native_tag)==1 and NATIVE.count(guest_tag)==0
    assert (NATIVE+"\n"+guest_tag).count(native_tag)==1
    for newline in ("\n","\r\n"):
        before=HEADER+newline+"void caller(void) { "+FENCE+" }"+newline
        after,count=rewrite(before)
        assert count==1 and FENCE not in after and CALL in after
        again,n=rewrite(after)
        assert n==0 and again==after
    print("[XPP-D54AC] SYNTHETIC PASS: original Xbox exact 22B state and protected guest ABI")

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

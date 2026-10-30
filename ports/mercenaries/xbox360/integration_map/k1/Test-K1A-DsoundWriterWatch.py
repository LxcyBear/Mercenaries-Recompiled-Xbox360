#!/usr/bin/env python3
"""Synthetic K1A writer owner and runtime-header regression, no game bytes."""
import importlib.util
import hashlib
import json
import tempfile
from pathlib import Path

path=Path(__file__).with_name("Stage-K1A-DsoundWriterWatch.py")
spec=importlib.util.spec_from_file_location("k1a_dswatch",path)
mod=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

BOOT="/* "+mod.K1A_MARK+" */\n"
BODY="""static inline void phase6ch_apu_write8(uint32_t address, uint8_t value)
{
    GUEST_WRITE8(address,value);
}
static void phase6ch_apu_write16(uint32_t address, uint16_t value)
{
    GUEST_WRITE16(address,value);
}
static __forceinline void phase6ch_apu_write32(uint32_t address, uint32_t value)
{
    GUEST_WRITE32(address,value);
}
"""

def rejected(fn,label):
    try:fn()
    except ValueError:return
    raise AssertionError("writer watch accepted bad "+label)

def make_shards(root:Path,helper_text:str)->None:
    root.mkdir()
    for i in range(64):
        (root/f"translated_{i:03d}.cpp").write_bytes(
            ("/* fake translated TU %d */\n"%i).encode())
    (root/"translated_runtime.h").write_bytes(helper_text.encode())
    (root/"another_runtime.h").write_bytes(b"/* fake extra header */\r\n")

def verify_owner(root:Path, owner:str, crlf:bool)->None:
    main=root/"clock.cpp"
    src_shards=root/"original"
    out=root/"staged"/"main.cpp"
    helper=BODY.replace("\n","\r\n") if crlf else BODY
    original_main=(BOOT+BODY if owner=="main.cpp" else BOOT+"/* base */\n")
    original_main=original_main.replace("\n","\r\n") if crlf else original_main
    main.write_bytes(original_main.encode())
    make_shards(src_shards,helper if owner=="translated_runtime.h" else "/* shared runtime */\n")
    snap={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
          for p in src_shards.iterdir()}
    before=main.read_bytes()
    doc=mod.stage(main,src_shards,out)
    assert doc["status"]=="STAGED_ONLY_NO_XDK_BUILD"
    assert doc["writer_owner"]==owner
    assert doc["generated_cpp_count"]==64
    assert doc["changed_cpp_count"]==0
    assert doc["generated_header_count"]==2
    assert doc["watch_widths"]==[1,2,4]
    assert doc["guest_write_semantics"]=="PRESERVED"
    assert doc["unknown_memory_fences"]=="PRESERVED"
    assert main.read_bytes()==before
    assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in src_shards.iterdir()}==snap
    staged=out.parent/"translated_shards"
    assert len(list(staged.glob("translated_*.cpp")))==64
    for f in src_shards.glob("translated_*.cpp"):
        assert (staged/f.name).read_bytes()==f.read_bytes()
    touched=out.read_bytes() if owner=="main.cpp" else (staged/"translated_runtime.h").read_bytes()
    assert touched.count(mod.MARK.encode())==3
    assert touched.count(b"K1A DSOBJECT WRITE:")==3
    assert b"(unsigned)eax" not in touched
    assert b"(unsigned)ebx" not in touched
    assert b"GUEST_READ32(0x00041D70u)" in touched
    assert b"GUEST_READ32(0x00041D74u)" in touched
    if crlf:
        assert touched.count(b"\r\n")==touched.count(b"\n")
    assert mod.stage(main,src_shards,out)==doc
    assert json.loads((out.parent/"k1a-dsound-writer-watch-manifest.json").read_text())==doc
    rejected(lambda:mod.stage(main,src_shards,main),"in-place main")
    if owner=="translated_runtime.h":
        header=staged/"translated_runtime.h"
        header.write_bytes(b"corrupted")
        rejected(lambda:mod.stage(main,src_shards,out),"staged header changed")
    else:
        out.write_bytes(b"corrupted")
        rejected(lambda:mod.stage(main,src_shards,out),"staged main changed")

def test():
    assert mod.signatures(BODY)==[1,1,1]
    assert mod.signatures("/* no helper definitions */")==[0,0,0]
    for source in (BOOT+BODY,(BOOT+BODY).replace("\n","\r\n")):
        patched=mod.patch(source)
        assert patched.count(mod.MARK)==3
        assert patched.count("K1A DSOBJECT WRITE:")==3
        for n,_,_ in mod.SPEC:
            assert patched.count(mod.MARK+" "+n)==1
        assert "(unsigned)eax" not in patched
        assert "GUEST_WRITE8(address,value);" in patched
        rejected(lambda:mod.patch(patched),"duplicate")
    rejected(lambda:mod.patch(BODY),"missing K1A identity")
    rejected(lambda:mod.patch(BOOT+BODY.replace(
        "void phase6ch_apu_write16","long phase6ch_apu_write16")),"wrong helper signature")
    rejected(lambda:mod.patch(BOOT+BODY+BODY),"duplicate helpers")
    with tempfile.TemporaryDirectory(prefix="k1a-writer-watch-") as temp:
        for owner in ("main.cpp","translated_runtime.h"):
            for crlf in (False,True):
                sub=Path(temp)/(owner+"-"+str(crlf))
                sub.mkdir()
                verify_owner(sub,owner,crlf)
        # Fail on ambiguous owner: two sets of definitions across main/header.
        sub=Path(temp)/"both"
        sub.mkdir()
        main=sub/"clock.cpp"
        main.write_text(BOOT+BODY)
        source=sub/"src"
        make_shards(source,BODY)
        rejected(lambda:mod.stage(main,source,sub/"out"/"main.cpp"),"ambiguous owner")
    print("[K1A-DSOBJECT] PASS: real-owner discovery in main OR translated_runtime.h")
    print("[K1A-DSOBJECT] PASS: fake 64 TrueTU + 2 headers, all SHA-guarded, LF/CRLF")
    print("[K1A-DSOBJECT] PASS: no guest-local registers, no in-place edits, no ambiguous owner")
    print("[K1A-DSOBJECT] Synthetic only; no Xbox XDK build or game bytes")

if __name__=="__main__":test()

#!/usr/bin/env python3
"""Synthetic writer-watch staging test; no retail XBE, no console tooling."""
from pathlib import Path
import importlib.util
import tempfile
import hashlib
import json
path=Path(__file__).with_name("Stage-K1A-DsoundWriterWatch.py")
spec=importlib.util.spec_from_file_location("k1a_dswatch",path)
mod=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

SOURCE='''/* P6K1A-BOOT-CLOCK128-304-305-20261029 */
static void phase6ch_apu_write8(uint32_t address, uint8_t value)
{
    GUEST_WRITE8(address,value);
}
static void phase6ch_apu_write16(uint32_t address, uint16_t value)
{
    GUEST_WRITE16(address,value);
}
static void phase6ch_apu_write32(uint32_t address, uint32_t value)
{
    GUEST_WRITE32(address,value);
}
'''

def rejected(fn,label):
    try:fn()
    except ValueError:return
    raise AssertionError("writer-watch accepted unsafe input: "+label)

def check():
    for text in (SOURCE,SOURCE.replace("\n","\r\n")):
        result=mod.patch(text)
        assert result.count(mod.MARK)==3
        assert result.count("K1A DSOBJECT WRITE:")==3
        assert result.count("GUEST_READ32(0x00041D70u)")==3
        assert result.count("GUEST_READ32(0x00041D74u)")==3
        assert result.count("GUEST_WRITE32(address,value);")==1
        assert result.count("GUEST_WRITE8(address,value);")==1
        assert result.count("GUEST_WRITE16(address,value);")==1
        assert result.count("unknown")==0
        assert result.find("DSOBJECT WRITE:")<result.find("GUEST_WRITE8(address,value);")
        assert result.count("\r\n")==result.count("\n") if "\r\n" in text else "\r" not in result
        rejected(lambda:mod.patch(result),"repeat stage")
    rejected(lambda:mod.patch(SOURCE.replace(mod.K1A_MARK,"not K1A")),"wrong baseline")
    rejected(lambda:mod.patch(SOURCE.replace(
        "static void phase6ch_apu_write16","void phase6ch_apu_write16")),"drifted helper definition")
    rejected(lambda:mod.patch(SOURCE+SOURCE),"multiple wrappers/identities")
    with tempfile.TemporaryDirectory(prefix="k1a-dsobject-") as temp:
        root=Path(temp)
        input=root/"baseline.cpp";out=root/"staged"/"main.cpp"
        input.write_bytes(SOURCE.replace("\n","\r\n").encode())
        before=input.read_bytes()
        doc=mod.stage(input,out)
        assert doc["status"]=="STAGED_ONLY_NO_XDK_BUILD"
        assert doc["watch_widths"]==[1,2,4]
        assert doc["guest_write_semantics"]=="PRESERVED"
        assert doc["unknown_memory_fences"]=="PRESERVED"
        assert before==input.read_bytes()
        assert doc["original_main_sha256"]==hashlib.sha256(before).hexdigest()
        assert doc["staged_main_sha256"]==hashlib.sha256(out.read_bytes()).hexdigest()
        assert out.read_bytes().count(b"\r\n")==out.read_bytes().count(b"\n")
        assert doc==mod.stage(input,out)
        manifest=json.loads((out.parent/"k1a-dsound-writer-watch-manifest.json").read_text())
        assert manifest==doc
        rejected(lambda:mod.stage(input,input),"in-place")
        out.write_bytes(b"corrupt")
        rejected(lambda:mod.stage(input,out),"staged drift")
    print("[K1A-DSOBJECT] PASS: 8/16/32 overlapping-write hooks and original write semantics")
    print("[K1A-DSOBJECT] PASS: Windows CRLF, K1A identity, SHA hashes, and in-place/drift rejection")
    print("[K1A-DSOBJECT] Synthetic only; no game material, runtime or XDK mutations")
if __name__=="__main__":check()

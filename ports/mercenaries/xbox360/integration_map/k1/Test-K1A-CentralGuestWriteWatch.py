#!/usr/bin/env python3
"""Synthetic source-only K1B regression, without XBE bytes or Xbox builds."""
from pathlib import Path
import importlib.util
import hashlib
import json
import tempfile

name=Path(__file__).with_name("Stage-K1A-CentralGuestWriteWatch.py")
spec=importlib.util.spec_from_file_location("k1b_central",name)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

def fixture(eol="\n"):
    content=f'''/* {m.BASE_MARK} */
/* {m.DSOBJECT_MARK} 8 */
/* {m.DSOBJECT_MARK} 16 */
/* {m.DSOBJECT_MARK} 32 */
void boot(){{ trace("{m.BOOT} | P6DQ-R76"); }}
void recomp_guest_write8(uint32_t address, uint8_t value)
{{
    phase6cv_shadow_note(address,1u,1);
    GUEST_WRITE8_UNMODIFIED(address,value);
}}
void recomp_guest_write16(uint32_t address, uint16_t value)
{{
    phase6cv_shadow_note(address,2u,1);
    GUEST_WRITE16_UNMODIFIED(address,value);
}}
void recomp_guest_write32(uint32_t address, uint32_t value)
{{
    uint32_t caller = 0u;
    if (s_traceCount != 0u)
    {{
        DWORD index = s_traceCount - 1u;
        if (index >= TRACE_CAPACITY) index = TRACE_CAPACITY - 1u;
        caller = s_trace[index];
    }}
    phase6cp_inherited_guest_write32(address,value);
}}
void recomp_guest_write64(uint32_t address, uint64_t value)
{{
    GUEST_WRITE64_UNMODIFIED(address,value);
}}
void recomp_guest_write128(
    uint32_t address,
    const uint32_t words[4])
{{
    GUEST_WRITE128_UNMODIFIED(address,words);
}}
static DWORD phase4c_current_caller(void)
{{
    return 0u;
}}
'''
    return content.replace("\n",eol)

def rejects(action,why):
    try: action()
    except ValueError: return
    raise AssertionError("K1B accepted drift: "+why)

def check():
    for eol in ("\n","\r\n"):
        original=fixture(eol)
        changed=m.patch(original)
        assert original.count(m.MARK)==0
        assert changed.count(m.MARK)==6
        assert changed.count("K1B CENTRAL WRITE:")==5
        assert changed.count(m.BOOT+" | "+m.MARK)==1
        for name,_,width in m.SPECS:
            assert changed.count(m.MARK+": "+name)==1,(name,width)
        for signature in ("GUEST_WRITE8_UNMODIFIED", "GUEST_WRITE16_UNMODIFIED",
                          "phase6cp_inherited_guest_write32",
                          "GUEST_WRITE64_UNMODIFIED",
                          "GUEST_WRITE128_UNMODIFIED"):
            assert changed.count(signature)==original.count(signature)
        assert changed.count("recomp_guest_read32(0x00041D70u)")==5
        assert changed.count("k1b_last_trace_va = s_trace[k1b_trace_index];")==5
        assert changed.count("(unsigned)k1b_last_trace_va,")==5
        assert changed.count("phase4c_current_caller()")==0
        assert changed.count("static DWORD phase4c_current_caller(void);")==0
        assert changed.count("s_execBudget")==5
        assert changed.count("\r\n")==changed.count("\n") if eol=="\r\n" else "\r" not in changed
        rejects(lambda:m.patch(changed),"duplicate watch")

    wrong=fixture().replace("void recomp_guest_write16","long recomp_guest_write16")
    rejects(lambda:m.patch(wrong),"16-bit writer definition gone")
    wrong=fixture().replace("uint64_t value","uint32_t value")
    rejects(lambda:m.patch(wrong),"64-bit writer width changed")
    wrong=fixture().replace("caller = s_trace[index];", "caller = unrelated_guess;")
    rejects(lambda:m.patch(wrong),"missing existing trace ring")
    wrong=fixture().replace("TRACE_CAPACITY", "X_CAP")
    rejects(lambda:m.patch(wrong),"missing existing trace cap")
    wrong=fixture().replace("const uint32_t words[4]","const uint32_t words[3]")
    rejects(lambda:m.patch(wrong),"128-bit writer changed")
    wrong=fixture().replace(m.BOOT, "some other old executable",1)
    rejects(lambda:m.patch(wrong),"missing console boot tag")
    wrong=fixture().replace(m.BASE_MARK,"older clock stage")
    rejects(lambda:m.patch(wrong),"missing K1A stage")
    wrong=fixture().replace(m.DSOBJECT_MARK,"older APU stage",1)
    rejects(lambda:m.patch(wrong),"missing three previous APU watches")
    wrong=fixture()+fixture()
    rejects(lambda:m.patch(wrong),"duplicate stage")

    with tempfile.TemporaryDirectory(prefix="k1b-central-watch-") as temp:
        root=Path(temp)
        source=root/"older"/"main.cpp"
        source.parent.mkdir()
        source.write_bytes(fixture("\r\n").encode("utf-8"))
        shards=root/"older"/"translated_shards"
        shards.mkdir()
        for n in range(64):
            (shards/f"translated_{n:03d}.cpp").write_text("/* fake TU */\n")
        (shards/"translated_runtime.h").write_text("/* fake shared header */\n")
        out=root/"new"/"main.cpp"
        before=source.read_bytes()
        shard_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in shards.iterdir()}
        result=m.stage(source,shards,out)
        assert result["status"]=="STAGED_ONLY_NO_XDK_BUILD"
        assert result["instrumented_guest_writer_widths"]==[1,2,4,8,16]
        assert result["guest_memory_writes_added"]==0
        assert result["hard_fence_policy"]=="UNCHANGED"
        assert before==source.read_bytes()
        assert shard_hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in shards.iterdir()}
        assert out.exists()
        assert b"PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF START | P6K1B" in out.read_bytes()
        assert m.stage(source,shards,out)==result
        assert json.loads((out.parent/"k1b-central-writer-manifest.json").read_text())==result
        rejects(lambda:m.stage(source,shards,source),"source overwrite")
        out.write_bytes(b"corrupted")
        rejects(lambda:m.stage(source,shards,out),"stage content drift")
        out.unlink()
        (shards/"translated_063.cpp").unlink()
        rejects(lambda:m.stage(source,shards,out),"missing original TrueTU")
    print("[K1B-WRITE] PASS: 5 central writer definitions + source-backed trace-ring witness (no phantom caller)")
    print("[K1B-WRITE] PASS: Linux LF/Windows CRLF, no changed writes, 64 unchanged TrueTU inputs")
    print("[K1B-WRITE] PASS: fail-closed on source drift, duplicate watches and staged SHA mismatch")
    print("[K1B-WRITE] No game bytes, no XDK build, no guest hard-fence changes")

if __name__=="__main__":
    check()

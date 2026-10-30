#!/usr/bin/env python3
"""K1C source-only 64-TrueTU fixture. No XDK, game assets, guest patching."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import importlib.util
import json

p=Path(__file__).with_name("Stage-K1C-ExactGuestWriteSite.py")
spec=importlib.util.spec_from_file_location("k1c",p)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

def rejected(fn,reason):
    try:fn()
    except ValueError: return
    raise AssertionError("accepted bad K1C stage "+reason)

def fixture(eol, tracker_late=True):
    comments="\n".join("/* "+m.K1B+" central writer */" for _ in range(5))
    tests="\n".join(
        f'''void recomp_guest_write{width}(uint32_t address, uint{width}_t value)
{{
    if (address == 0x41D70u) {{
        char line[360];
        sprintf(line, "{m.OLD_LABEL}",
                (unsigned)k1b_last_trace_va,
                (unsigned)s_execBudget, (unsigned)g_esp);
    }}
}}'''
        for width in (8,16,32,64)
    )
    write128=f'''void recomp_guest_write128(uint32_t address, const uint32_t words[4])
{{
    if (address == 0x41D70u) {{
        char line[360];
        sprintf(line, "{m.OLD_LABEL}",
                (unsigned)k1b_last_trace_va,
                (unsigned)s_execBudget, (unsigned)g_esp);
    }}
}}'''
    # Add one ring expression to each of the 5 real-writer fixtures.
    tests=tests.replace("sprintf(line,", "k1b_last_trace_va = s_trace[k1b_trace_index];\n        sprintf(line,")
    write128=write128.replace("sprintf(line,", "k1b_last_trace_va = s_trace[k1b_trace_index];\n        sprintf(line,")
    # Mirror the ACTUAL K1B main: tracker global follows early central
    # writer functions. The previous fixture only tested the opposite
    # order and therefore missed the real Windows staging failure.
    early_tracker="" if tracker_late else m.TRACKER+"\n"
    late_tracker=m.TRACKER+"\n" if tracker_late else ""
    text=(f'''/* {m.BOOT_OLD} */
{early_tracker}void recomp_guest_write8(uint32_t address, uint8_t value);
void recomp_guest_write32(uint32_t address, uint32_t value);
{comments}
{tests}
{write128}
{late_tracker}''')
    return text.replace("\n",eol)

with TemporaryDirectory(prefix="k1c-writer-site-") as tmp:
    root=Path(tmp)
    sources=root/"previous"
    sources.mkdir()
    shard_dir=sources/"translated_shards"
    shard_dir.mkdir()
    for n in range(64):
        (shard_dir/f"translated_{n:03d}.cpp").write_text("/* synthetic TrueTU */\n",encoding="utf-8")
    (shard_dir/"translated_runtime.h").write_text("/* synthetic runtime */\n")
    original_shards={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in shard_dir.iterdir()}
    for ending in ("\n","\r\n"):
        input_bytes=fixture(ending).encode("utf-8")
        main=sources/"main.cpp"
        main.write_bytes(input_bytes)
        output=root/("new-crlf" if ending=="\r\n" else "new-lf")/"main.cpp"
        patched=m.patch(fixture(ending))
        assert patched.count(m.NEW_LABEL)==5
        assert patched.count("(unsigned)k1c_read_guest_va(),")==5
        assert patched.count(m.HELPER_DECL)==1
        assert patched.count("static DWORD k1c_read_guest_va(void)"+ending+"{")==1
        assert patched.count("return s_phase6cpCurrentVa;")==1
        assert patched.count(m.TRACKER)==1
        assert patched.index(m.HELPER_DECL)<patched.index("void recomp_guest_write8(")
        assert patched.index(m.TRACKER)<patched.index("return s_phase6cpCurrentVa;")
        assert patched.index("void recomp_guest_write128")<patched.index(m.TRACKER)
        assert patched.count(m.BOOT_NEW)==1
        assert patched.count("k1b_last_trace_va = s_trace[k1b_trace_index];")==5
        assert patched.count(m.OLD_LABEL)==0
        assert patched.count(m.NEW_ARG.replace("\n",ending))==5
        assert patched.count("\r\n")==patched.count("\n") if ending=="\r\n" else "\r" not in patched
        result=m.stage(main,shard_dir,output)
        assert result["guest_memory_hard_fence"]=="UNCHANGED"
        assert result["translated_cpp_count"]==64
        assert result["extra_guest_memory_writes"]==0
        assert result["boot_marker"]==m.K1C
        assert result["guest_write_widths"]==[1,2,4,8,16]
        assert m.stage(main,shard_dir,output)==result
        assert json.loads((output.parent/"k1c-write-site-manifest.json").read_text())==result
        assert main.read_bytes()==input_bytes
        assert original_shards=={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in shard_dir.iterdir()}
        rejected(lambda:m.patch(patched),"duplicate K1C instrumentation")
        rejected(lambda:m.stage(main,shard_dir,main),"in-place main")
        output.write_text("DRIFT")
        rejected(lambda:m.stage(main,shard_dir,output),"existing output drift")
    source=fixture("\n")
    # Also accept the earlier-layout synthetic source without duplicating
    # or relocating its tracker global.
    early=m.patch(fixture("\n", tracker_late=False))
    assert early.count(m.HELPER_DECL)==1
    assert early.count("return s_phase6cpCurrentVa;")==1
    assert early.index(m.TRACKER)<early.index("void recomp_guest_write8(")
    rejected(lambda:m.patch(source.replace(m.TRACKER,"static DWORD otherVa = 0u;")),
             "missing guest VA tracker")
    rejected(lambda:m.patch(source.replace(m.OLD_LABEL,"other string",1)),
             "missing writer log")
    rejected(lambda:m.patch(source.replace(m.K1B,"older-stage",1)),
             "incomplete K1B stage")
    rejected(lambda:m.patch(source.replace("k1b_last_trace_va = s_trace[k1b_trace_index];",
                                          "missing trace ring",1)),"missing trace ring")
    (shard_dir/"translated_063.cpp").unlink()
    rejected(lambda:m.stage(sources/"main.cpp",shard_dir,root/"new-other"/"main.cpp"),
             "missing one of 64 TrueTUs")

print("[K1C-SITE] SYNTHETIC PASS: 5 central writers + late global tracker helper, LF/Windows CRLF")
print("[K1C-SITE] SYNTHETIC PASS: original pointer write, trace ring, 64 TrueTUs unchanged")
print("[K1C-SITE] SYNTHETIC PASS: source identity/drift/in-place/duplicate hard rejection")
print("[K1C-SITE] No Xbox build and no retail game bytes")

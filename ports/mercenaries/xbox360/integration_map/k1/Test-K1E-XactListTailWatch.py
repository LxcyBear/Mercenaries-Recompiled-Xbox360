#!/usr/bin/env python3
"""Synthetic 64-TU K1E read-only source staging tests; no game assets or XDK."""
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory

f=Path(__file__).with_name("Stage-K1E-XactListTailWatch.py")
spec=importlib.util.spec_from_file_location("k1e",f)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

def rejects(fn,reason):
    try:fn()
    except ValueError:return
    raise AssertionError("K1E accepted invalid source: "+reason)

def fixture(eol="\n"):
    body='''void sub_0027DC5B(void)
{
    uint32_t eax=0,ebx=0,ecx=0,edx=0,edi=0;
    uint32_t s_phase6dqXactInitEventCount=1;
    (void)s_phase6dqXactInitEventCount;
loc_0027DD06: ;
    PHASE4C_BUDGET_TICK(0x0027DD06u);
    edx = ebx + 0x74;
    eax = eax + 0x28;
loc_0027DD0C: ;
    PHASE4C_BUDGET_TICK(0x0027DD0Cu);
    GUEST_WRITE32(eax + 4, eax);
    GUEST_WRITE32(eax, eax);
    GUEST_WRITE32(eax, edx);
    ecx = GUEST_READ32(edx + 4);
    GUEST_WRITE32(eax + 4, ecx);
    GUEST_WRITE32(ecx, eax);
    ecx = GUEST_READ32(eax);
    GUEST_WRITE32(ecx + 4, eax);
    edi++;
}
void sub_0027F92A(void) { }
'''
    return body.replace("\n",eol)

for eol in ("\n","\r\n"):
    original=fixture(eol)
    altered=m.modify(original)
    assert altered.count(m.TAG)==1
    assert altered.count("K1E XACT LIST PRE")==1
    assert altered.count("tail_hits_41D70=%u head_hits_41D70=%u")==1
    assert altered.count("(unsigned)(ecx == 0x00041D70u)")==1
    assert altered.count("(unsigned)(edx + 4u == 0x00041D70u)")==1
    assert altered.count("GUEST_WRITE32(ecx + 4, eax);")==1
    assert altered.index("K1E XACT LIST PRE")<altered.index("    GUEST_WRITE32(ecx, eax);")
    assert altered.count("GUEST_WRITE32(")==original.count("GUEST_WRITE32(")
    assert altered.count("GUEST_READ32(")==original.count("GUEST_READ32(")
    assert altered.count("    GUEST_WRITE32(ecx, eax);")==1
    assert altered.count("    ecx = GUEST_READ32(edx + 4);")==1
    assert altered.count("static uint32_t k1e_list_edge_visits = 0u;")==1
    assert altered.count("\r\n")==altered.count("\n") if eol=="\r\n" else "\r" not in altered
    rejects(lambda:m.modify(altered),"duplicate K1E")
    if eol=="\r\n":
        rejects(lambda:m.modify(original.replace("\r\n","\r\r\n")),
                "Windows double-translated CRCRLF fixture")
    rejects(lambda:m.modify(original.replace("ecx = GUEST_READ32(edx + 4);",
                                              "ecx = GUEST_READ32(edx);")),
            "different tail load")
    rejects(lambda:m.modify(original.replace("GUEST_WRITE32(ecx, eax);",
                                              "GUEST_WRITE32(eax, ecx);")),
            "original link-store changed")
    rejects(lambda:m.modify(original.replace("loc_0027DD0C", "loc_0027DD0D")),
            "wrong guest VA")

with TemporaryDirectory(prefix="k1e-list-tail-test-") as temp:
    root=Path(temp)
    originals=root/"orig"
    originals.mkdir()
    staged=root/"staged"
    for i in range(64):
        (originals/f"translated_{i:03d}.cpp").write_text("/* empty TU */\n")
    target=originals/m.SOURCE_FILE
    # Windows text-mode writes translate LF -> CRLF. Writing an already
    # CRLF fixture with write_text creates CRCRLF and breaks exact
    # original-instruction matching. Stage inputs are byte-preserved.
    fixture_bytes=fixture("\r\n").encode("utf-8")
    target.write_bytes(fixture_bytes)
    assert target.read_bytes()==fixture_bytes
    assert b"\r\r\n" not in target.read_bytes()
    (originals/"translated_runtime.h").write_text("/* generated header */\n")
    hashes={x.name:hashlib.sha256(x.read_bytes()).hexdigest()
            for x in originals.iterdir()}
    record=m.stage(originals,staged)
    assert record["modified_shards"]==[m.SOURCE_FILE]
    assert (staged/m.SOURCE_FILE).read_bytes().count(b"\r\r\n")==0
    assert b"\r\n" in (staged/m.SOURCE_FILE).read_bytes()
    assert (staged/m.SOURCE_FILE).read_bytes().count(b"\r\n")==(
        (staged/m.SOURCE_FILE).read_bytes().count(b"\n")
    )
    assert record["unchanged_shards"]==63
    assert record["guest_store_statements_changed"]==0
    assert record["guest_read_statements_changed"]==0
    assert record["guest_register_writes_added"]==0
    assert record["unknown_memory_fences"]=="UNCHANGED"
    assert m.stage(originals,staged)==record
    assert json.loads((staged.parent/"k1e-xact-tail-manifest.json").read_text())==record
    assert hashes=={x.name:hashlib.sha256(x.read_bytes()).hexdigest()
                   for x in originals.iterdir()}
    for file in originals.iterdir():
        new=staged/file.name
        if file.name==m.SOURCE_FILE:
            assert new.read_bytes()!=file.read_bytes()
        else:
            assert new.read_bytes()==file.read_bytes()
    rejects(lambda:m.stage(originals,originals),"in-place source overwrite")
    (staged/"translated_007.cpp").write_text("DRIFT")
    rejects(lambda:m.stage(originals,staged),"existing staged drift")
    (staged/"translated_007.cpp").unlink()
    rejects(lambda:m.stage(originals,staged),"missing staged shard")

print("[K1E-XACT] SYNTHETIC PASS: source-window exact, original list-link stores kept")
print("[K1E-XACT] SYNTHETIC PASS: LF/CRLF, 64 shards, only one changed, headers unchanged")
print("[K1E-XACT] SYNTHETIC PASS: source overwrite, stale output and source drift rejected")
print("[K1E-XACT] No XDK build, no retail game bytes")

#!/usr/bin/env python3
"""Synthetic TRUE TU K1A-DSINDEX stage regression; no retail game data."""
from pathlib import Path
import importlib.util
import tempfile
import json
import hashlib
f=Path(__file__).with_name("Stage-K1A-DsoundIndexTrace.py")
spec=importlib.util.spec_from_file_location("k1a_dsidx",f)
module=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

FAKE=r'''/* mock translated shard, NOT Mercenaries code */
static void sub_002A6595(void)
{
    uint32_t ebp;
    ebx = ecx;
    edx = phase6ch_apu_read32(ebx + 4);
    eax = phase6ch_apu_read32(ebx);
    eax = eax - edx;
    phase6ch_apu_write32(ebp + -12, eax);
    eax = phase6ch_apu_read32(0x2BB240);
    phase6ch_apu_write32(ebp + -4, eax);
    eax = ecx;
loc_002A6607: ;
    ecx = phase6ch_apu_read32(ebp + -4);
    edx = phase6ch_apu_read32(ebp + -12);
    esi = ecx + edx * 8;
    phase6ch_apu_write32(ebp + -4, eax);
loc_002A6617: ;
    eax = eax + phase6ch_apu_read32(ebp + 8);
    PUSH32(esp, eax);
loc_002A6624: ;
    PHASE4C_BUDGET_TICK(0x002A6624u);
    phase6ch_apu_write32(esi + 4, phase6ch_apu_read32(esi + 4) & 0);
}
'''

def expect_rejected(action,why):
    try:action()
    except ValueError:return
    raise AssertionError("probe accepted unsafe input: "+why)

def test():
    changed=module.modify(FAKE)
    windows_fixture=FAKE.replace("\n","\r\n")
    changed_windows=module.modify(windows_fixture)
    assert changed_windows.count("\r\n")==changed_windows.count("\n"), "mixed EOL introduced"
    assert changed_windows.count(module.MARK)==1
    for tag in ("ENTRY:", "LEA:", "PRE173:", "POST173:"):
        assert changed_windows.count("K1A DSINDEX "+tag)==1
    expect_rejected(lambda: module.modify(windows_fixture.replace(
        "    esi = ecx + edx * 8;\r\n",
        "    esi = ecx + edx * 8;\n")), "mixed Windows line endings")
    assert changed.count(module.MARK)==1
    assert changed.count("K1A DSINDEX ENTRY:")==1
    assert changed.count("K1A DSINDEX LEA:")==1
    assert changed.count("K1A DSINDEX PRE173:")==1
    assert changed.count("K1A DSINDEX POST173:")==1
    assert changed.count("phase6ch_apu_write32(ebp + -4, eax);")==2
    assert changed.index("K1A DSINDEX POST173")<changed.index(
        "phase6ch_apu_write32(esi + 4, phase6ch_apu_read32(esi + 4) & 0)")
    expect_rejected(lambda:module.modify(changed),"duplicate instrumentation")
    expect_rejected(lambda:module.modify(FAKE.replace("esi = ecx + edx * 8;","esi = edx;")),"changed index expression")
    expect_rejected(lambda:module.modify(FAKE.replace("0x2BB240","0x2BB241")),"changed global table identity")
    with tempfile.TemporaryDirectory(prefix="k1a-dsidx-") as tmp:
        root=Path(tmp)
        base=root/"base"
        staged=root/"staged"
        base.mkdir()
        for i in range(64):
            data=FAKE if i==27 else "/* other true TU shard */\n"
            (base/f"translated_{i:03d}.cpp").write_text(data)
        # All translated TrueTUs depend on the generated shared header;
        # previous staging silently dropped it and XDK failed with C1083.
        (base/"translated_runtime.h").write_bytes(b"/* fake generated runtime header */\r\n")
        (base/"other_shared.h").write_bytes(b"/* fake auxiliary header */\n")
        header_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in base.glob("*.h")}
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in base.glob("translated_*.cpp")}
        # Explicitly emulate Windows text-mode newline translation even on
        # Linux CI, where Path.write_text otherwise preserves LF.
        owner=base/"translated_027.cpp"
        owner.write_bytes(windows_fixture.encode("utf-8"))
        before[owner.name]=hashlib.sha256(owner.read_bytes()).hexdigest()
        m=module.stage(base,staged)
        assert m["status"]=="STAGED_ONLY_NO_XDK_BUILD"
        assert m["original_shards"]==64
        assert m["unchanged_shards"]==63
        assert m["modified_shards"]==["translated_027.cpp"]
        assert len(list(staged.glob("translated_*.cpp")))==64
        assert m["header_count"]==2
        assert m["header_sha256"]==header_hashes
        assert set(m["auxiliary_headers"])==set(header_hashes)
        assert len(list(staged.glob("*.h")))==2
        for p in staged.glob("*.h"):
            assert hashlib.sha256(p.read_bytes()).hexdigest()==header_hashes[p.name]
        assert module.MARK in (staged/"translated_027.cpp").read_text()
        staged_data=(staged/"translated_027.cpp").read_bytes()
        assert staged_data.count(b"\r\n")==staged_data.count(b"\n"), "staging normalized CRLF"
        assert staged_data.count(b"\r\n")>0
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
               for p in base.glob("translated_*.cpp")}
        assert before==after,"original TrueTU inputs changed"
        for p in staged.glob("translated_*.cpp"):
            if p.name!="translated_027.cpp":
                assert hashlib.sha256(p.read_bytes()).hexdigest()==before[p.name]
        manifest=json.loads((root/"k1a-dsound-index-trace-manifest.json").read_text())
        assert manifest==m
        expect_rejected(lambda:module.stage(base,base),"in-place")
        reused=module.stage(base,staged)
        assert reused==m,"preflight stage reuse changed manifest"
        # Simulate the EXACT failed Xbox build: 64 staged .cpp files
        # present but all shared .h files missing. Legacy manifest has
        # no header metadata. Migration must repair only verified headers.
        for p in staged.glob("*.h"):
            p.unlink()
        old_manifest=dict(m)
        old_manifest.pop("header_sha256")
        old_manifest.pop("header_count")
        old_manifest.pop("auxiliary_headers")
        (root/"k1a-dsound-index-trace-manifest.json").write_text(
            json.dumps(old_manifest,indent=2)+"\n")
        repaired=module.stage(base,staged)
        assert repaired==m,"legacy stage migration did not restore identical manifest"
        for p in staged.glob("*.h"):
            assert hashlib.sha256(p.read_bytes()).hexdigest()==header_hashes[p.name]
        assert len(list(staged.glob("translated_*.cpp")))==64
        # Headers are checked just as strictly as the 64 source shards.
        (staged/"translated_runtime.h").write_bytes(b"/* corrupt */")
        expect_rejected(lambda:module.stage(base,staged),"stale translated_runtime.h")
        (staged/"translated_runtime.h").write_bytes(
            (base/"translated_runtime.h").read_bytes())
        (staged/"translated_010.cpp").write_text("/* corrupted synthetic shard */")
        expect_rejected(lambda:module.stage(base,staged),"stale copied shard")
        (staged/"translated_010.cpp").write_text("/* other true TU shard */\n")
        assert len(list(base.glob("translated_*.cpp")))==64
        assert set(p.name for p in base.glob("*.h"))==set(header_hashes)
    print("[K1A-DSINDEX] PASS: synthetic exact labels, entry/LEA/pre173/post173 probes")
    print("[K1A-DSINDEX] PASS: 63 unchanged shards, two header SHA identities, no in-place/duplicate")
    print("[K1A-DSINDEX] PASS: migrated legacy 64-cpp-only stage (missing translated_runtime.h)")
    print("[K1A-DSINDEX] No game bytes, XDK build or memory fences modified")
if __name__=="__main__":
    test()

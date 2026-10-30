#!/usr/bin/env python3
"""K1G synthetic source/64-TrueTU regression: no game files, no XDK."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent

def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

k1e = load("k1e_stage_for_k1g", HERE / "Stage-K1E-XactListTailWatch.py")
k1g = load("k1g_stage_test", HERE / "Stage-K1G-XactRegisterProvenance.py")

def rejects(call, label: str) -> None:
    try:
        call()
    except ValueError:
        return
    raise AssertionError("K1G accepted invalid source: " + label)

def fixture(nl: str) -> str:
    code = """void sub_0027DC5B(void);
void sub_0027DC5B(void)
{
    uint32_t ebp;
    ebx = ecx;
    ++s_phase6dqXactInitEntries;
    PUSH32(esp, 0); sub_0027D5C0();
loc_0027DC69: ;
    PHASE4C_BUDGET_TICK(0x0027DC69u);
    PUSH32(esp, 0); sub_0029FDF0();
loc_0027DC8A: ;
    PHASE4C_BUDGET_TICK(0x0027DC8Au);
    PUSH32(esp, 0); sub_0029E435();
loc_0027DCAC: ;
    PHASE4C_BUDGET_TICK(0x0027DCACu);
    PUSH32(esp, 0); sub_0028345A();
loc_0027DCBB: ;
    PHASE4C_BUDGET_TICK(0x0027DCBBu);
    PUSH32(esp, 0); sub_001787C0();
loc_0027DCE5: ;
    PHASE4C_BUDGET_TICK(0x0027DCE5u);
loc_0027DD06: ;
    PHASE4C_BUDGET_TICK(0x0027DD06u);
    edx = ebx + 0x74;
loc_0027DD0C: ;
    PHASE4C_BUDGET_TICK(0x0027DD0Cu);
    ecx = GUEST_READ32(edx + 4);
    GUEST_WRITE32(eax + 4, ecx);
    GUEST_WRITE32(ecx, eax);
}
"""
    return code.replace("\n", nl)

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

for nl in ("\n", "\r\n"):
    source = fixture(nl)
    k1e_text = k1e.modify(source)
    result = k1g.modify(k1e_text)
    assert result.count(k1g.TAG) == len(k1g.STAGES)
    assert result.count("K1G XACT ABI ") == len(k1g.STAGES)
    assert result.count("K1E XACT LIST PRE:") == 1
    assert result.count("GUEST_WRITE32(") == k1e_text.count("GUEST_WRITE32(")
    assert result.count("GUEST_READ32(") == k1e_text.count("GUEST_READ32(")
    assert result.index("K1G XACT ABI ENTRY:") < result.index("    ebx = ecx;")
    assert result.index("K1G XACT ABI POST_COPY:") > result.index("    ebx = ecx;")
    assert result.index("K1G XACT ABI BEFORE_LIST:") < result.index("loc_0027DD0C: ;")
    assert (result.count("\r") == 0 if nl == "\n"
            else result.count("\r\n") == result.count("\n"))
    rejects(lambda: k1g.modify(result), "duplicate instrumentation")
    rejects(lambda: k1g.modify(k1e_text.replace("    ebx = ecx;", "    ebx = eax;")),
            "guest EBX setup drift")
    rejects(lambda: k1g.modify(k1e_text.replace("loc_0027DCBB: ;", "loc_0027DCCC: ;")),
            "missing after-call boundary")
    rejects(lambda: k1g.modify(k1e_text + nl + k1e_text),
            "duplicate original function body")

with TemporaryDirectory(prefix="merc360-k1g-") as temp:
    root = Path(temp)
    originals = root / "originals"
    originals.mkdir()
    for i in range(64):
        (originals / f"translated_{i:03d}.cpp").write_bytes(b"/* TrueTU */\n")
    (originals / k1g.OWNER).write_bytes(fixture("\r\n").encode("utf-8"))
    (originals / "translated_runtime.h").write_bytes(b"/* header */\n")
    k1e_dir = root / "k1e" / "translated_shards"
    k1g_dir = root / "k1g" / "translated_shards"
    k1e_doc = k1e.stage(originals, k1e_dir)
    manifest = k1e_dir.parent / "k1e-xact-tail-manifest.json"
    baseline = {f.name: digest(f) for f in k1e_dir.iterdir()}
    k1g_doc = k1g.stage(k1e_dir, manifest, k1g_dir)
    assert k1g_doc["modified_shards"] == [k1g.OWNER]
    assert k1g_doc["unchanged_shards"] == 63
    assert k1g_doc["probe_stages"] == [name for name, _, _ in k1g.STAGES]
    assert k1g_doc["guest_reads_added"] == 0
    assert k1g_doc["guest_writes_added"] == 0
    assert k1g_doc["guest_register_writes_added"] == 0
    assert k1g_doc["memory_hard_fences"] == "UNCHANGED"
    assert k1g.stage(k1e_dir, manifest, k1g_dir) == k1g_doc
    assert json.loads((k1g_dir.parent / "k1g-register-provenance-manifest.json").read_text()) == k1g_doc
    assert {f.name: digest(f) for f in k1e_dir.iterdir()} == baseline
    for source in k1e_dir.iterdir():
        new = k1g_dir / source.name
        assert new.is_file()
        if source.name == k1g.OWNER:
            assert digest(new) != digest(source)
        else:
            assert new.read_bytes() == source.read_bytes()
    rejects(lambda: k1g.stage(k1e_dir, manifest, k1e_dir), "source overwrite")
    (k1g_dir / "translated_007.cpp").write_bytes(b"BAD")
    rejects(lambda: k1g.stage(k1e_dir, manifest, k1g_dir), "stale output")
    (k1g_dir / "translated_007.cpp").unlink()
    rejects(lambda: k1g.stage(k1e_dir, manifest, k1g_dir), "missing shard")
    assert k1e_doc["modified_shards"] == [k1g.OWNER]

print("[K1G] SYNTHETIC PASS: LF/CRLF, K1E source shape, 8 post-call register stages")
print("[K1G] SYNTHETIC PASS: 64 TrueTUs and all headers unchanged except owner")
print("[K1G] SYNTHETIC PASS: original list stores/read counts and K1E telemetry preserved")
print("[K1G] SYNTHETIC PASS: source overwrite, source drift and stale output fail closed")
print("[K1G] No retail game bytes or XDK build")

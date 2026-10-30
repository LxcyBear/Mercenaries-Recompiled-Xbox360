#!/usr/bin/env python3
"""K1J synthetic no-retail/no-XDK checks for two TrueTU register-edge probes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
module = importlib.util.spec_from_file_location(
    "k1j_stage", HERE / "Stage-K1J-DsoundReturnEbxWatch.py"
)
assert module and module.loader
k1j = importlib.util.module_from_spec(module)
module.loader.exec_module(k1j)

def reject(action, context):
    try:
        action()
    except ValueError:
        return
    raise AssertionError("expected K1J failure: " + context)

FDF0 = """void sub_0029FDF0(void);
void sub_0029FDF0(void)
{
    uint32_t ebp;
loc_0029FDF0: ;
    PHASE4C_BUDGET_TICK(0x0029FDF0u);
    PUSH32(esp, 0); sub_0029CDBE(); /* call 0x0029CDBE */
loc_0029FDFB: ;
    PHASE4C_BUDGET_TICK(0x0029FDFBu);
    PUSH32(esp, 0); sub_0029FD83(); /* call 0x0029FD83 */
loc_0029FE07: ;
    PHASE4C_BUDGET_TICK(0x0029FE07u);
    ecx = GUEST_READ32(eax);
loc_0029FE2F: ;
    PHASE4C_BUDGET_TICK(0x0029FE2Fu);
    POP32(esp, edi);
    return;
}
"""
FD83 = """void sub_0029FD83(void);
void sub_0029FD83(void)
{
loc_0029FD83: ;
    PHASE4C_BUDGET_TICK(0x0029FD83u);
    PUSH32(esp, 0); sub_002A41EE(); /* call 0x002A41EE */
    PUSH32(esp, 0); sub_0029CB9F(); /* call 0x0029CB9F */
    PUSH32(esp, 0); sub_0029CF0B(); /* call 0x0029CF0B */
    PUSH32(esp, 0); sub_0029FC4A(); /* call 0x0029FC4A */
    eax = esi;
    POP32(esp, esi);
    esp += 8; return; /* ret 4 */
}
"""
for nl in ("\n", "\r\n"):
    for name, original in [("translated_041.cpp", FDF0), ("translated_017.cpp", FD83)]:
        fixture = original.replace("\n", nl)
        result = k1j.modify(name, fixture)
        stages = k1j.OWNERS[name][1]
        assert result.count(k1j.TAG) == len(stages)
        assert result.count("K1J DSOUND ABI ") == len(stages)
        assert result.count("GUEST_READ32(") == fixture.count("GUEST_READ32(")
        assert result.count("GUEST_WRITE32(") == fixture.count("GUEST_WRITE32(")
        assert (result.count("\r\n") == result.count("\n") if nl == "\r\n"
                else "\r" not in result)
        reject(lambda: k1j.modify(name, result), "duplicate instrumentation")
        reject(lambda: k1j.modify(name, fixture.replace("PUSH32(esp, 0); sub_0029FC4A();", "PUSH32(esp, 0); sub_0029FD83();")),
               "missing FD83 FC4A anchor") if name == "translated_017.cpp" else None
        reject(lambda: k1j.modify(name, fixture.replace("PHASE4C_BUDGET_TICK(0x0029FE07u);", "PHASE4C_BUDGET_TICK(0x0029FE08u);")),
               "missing FDF0 label") if name == "translated_041.cpp" else None

with TemporaryDirectory(prefix="merc360-k1j-") as directory:
    root = Path(directory)
    source_dir = root / "k1g" / "translated_shards"
    source_dir.mkdir(parents=True)
    for i in range(64):
        (source_dir / f"translated_{i:03d}.cpp").write_text("// synthetic\n", encoding="utf-8")
    (source_dir / "translated_041.cpp").write_bytes(FDF0.replace("\n", "\r\n").encode("utf-8"))
    (source_dir / "translated_017.cpp").write_bytes(FD83.encode("utf-8"))
    (source_dir / "translated_029.cpp").write_bytes(
        b'/* K1G XACT ABI ENTRY: K1E XACT LIST PRE: */\n'
    )
    (source_dir / "translated_runtime.h").write_text("// synthetic header\n", encoding="utf-8")
    source_manifest = {
        "marker": k1j.SOURCE_MARKER,
        "status": "STAGED_ONLY_NO_XDK_BUILD",
        "staged_directory": str(source_dir.resolve()),
        "original_shards": 64,
        "unchanged_shards": 63,
        "modified_shards": ["translated_029.cpp"],
        "staged_owner_sha256": k1j.sha((source_dir / "translated_029.cpp").read_bytes()),
    }
    manifest_file = source_dir.parent / "k1g-register-provenance-manifest.json"
    manifest_file.write_text(json.dumps(source_manifest), encoding="utf-8")
    target = root / "k1j" / "translated_shards"
    inputs = {f.name: k1j.sha(f.read_bytes()) for f in source_dir.iterdir()}
    record = k1j.stage(source_dir, manifest_file, target)
    assert record["modified_from_k1g"] == ["translated_017.cpp", "translated_041.cpp"]
    assert record["unchanged_from_k1g"] == 62
    assert record["preserved_k1g_owner"] and record["preserved_k1e_witness"]
    assert len(record["probe_stages"]) == 10
    assert record["guest_register_writes_added"] == 0
    assert record["guest_memory_ops_added"] == 0
    assert record["unknown_memory_fences"] == "UNCHANGED"
    assert record == k1j.stage(source_dir, manifest_file, target)
    assert {f.name: k1j.sha(f.read_bytes()) for f in source_dir.iterdir()} == inputs
    for source_file in source_dir.iterdir():
        changed = target / source_file.name
        if source_file.name in k1j.OWNERS:
            assert changed.read_bytes() != source_file.read_bytes()
        else:
            assert changed.read_bytes() == source_file.read_bytes()
    reject(lambda: k1j.stage(source_dir, manifest_file, source_dir), "overwrite baseline")
    (target / "translated_013.cpp").write_text("BAD", encoding="utf-8")
    reject(lambda: k1j.stage(source_dir, manifest_file, target), "stale nonowner output")
    (target / "translated_013.cpp").unlink()
    reject(lambda: k1j.stage(source_dir, manifest_file, target), "missing TrueTU")
    source_manifest["marker"] = "CORRUPT"
    manifest_file.write_text(json.dumps(source_manifest), encoding="utf-8")
    reject(lambda: k1j.stage(source_dir, manifest_file, target), "manifest provenance drift")

print("[K1J] SYNTHETIC PASS: LF/CRLF, exactly 10 stage/call-edge probes")
print("[K1J] SYNTHETIC PASS: 64 TrueTUs/headers, only 2 new owner files modified")
print("[K1J] SYNTHETIC PASS: K1G/K1E telemetry remains in original owner")
print("[K1J] SYNTHETIC PASS: fail closed on stale output, manifest drift, source overwrite")
print("[K1J] No Xbox or XDK invocation")

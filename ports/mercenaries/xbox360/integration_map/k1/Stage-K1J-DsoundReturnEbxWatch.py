#!/usr/bin/env python3
"""K1J: K1G-preserving two-TrueTU DSOUND callee/return register forensic probes.

From the hardware-confirmed K1G staged set, add only host-side register
snapshots in sub_0029FDF0 (translated_041.cpp) and sub_0029FD83
(translated_017.cpp). Guest instructions, guest memory, ABI, and fences
remain untouched. Stage only; build/deploy guarded separately.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

TAG = "K1J-DSOUND-RETURN-EBX-20261030"
SOURCE_MARKER = "K1G-XACT-REGISTER-PROVENANCE-20261030"
OWNERS = {
    "translated_041.cpp": ("sub_0029FDF0", (
        ("FDF0_ENTRY", "    PHASE4C_BUDGET_TICK(0x0029FDF0u);", "after"),
        ("FDF0_AFTER_CDBE", "    PHASE4C_BUDGET_TICK(0x0029FDFBu);", "after"),
        ("FDF0_AFTER_FD83", "    PHASE4C_BUDGET_TICK(0x0029FE07u);", "after"),
        ("FDF0_RETURN", "    PHASE4C_BUDGET_TICK(0x0029FE2Fu);", "after"),
    )),
    "translated_017.cpp": ("sub_0029FD83", (
        ("FD83_ENTRY", "    PHASE4C_BUDGET_TICK(0x0029FD83u);", "after"),
        ("FD83_AFTER_A41EE", "    PUSH32(esp, 0); sub_002A41EE(); /* call 0x002A41EE */", "after"),
        ("FD83_AFTER_CB9F", "    PUSH32(esp, 0); sub_0029CB9F(); /* call 0x0029CB9F */", "after"),
        ("FD83_AFTER_CF0B", "    PUSH32(esp, 0); sub_0029CF0B(); /* call 0x0029CF0B */", "after"),
        ("FD83_AFTER_FC4A", "    PUSH32(esp, 0); sub_0029FC4A(); /* call 0x0029FC4A */", "after"),
        ("FD83_RETURN", "    eax = esi;\n    POP32(esp, esi);\n    esp += 8; return; /* ret 4 */", "before"),
    )),
}
ENTRY = re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+(sub_[0-9A-Fa-f]{8})[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
CLOSE = re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
READ_WRITE = re.compile(r"\bGUEST_(?:READ|WRITE)(?:8|16|32|64|128)\(")

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sample(name: str) -> str:
    return (
        f"    /* {TAG}: {name} */\n"
        "    {\n"
        f"        static uint32_t k1j_visits_{name} = 0u;\n"
        f"        ++k1j_visits_{name};\n"
        f"        if (k1j_visits_{name} <= 4u || k1j_visits_{name} == 32u)\n"
        "        {\n"
        "            char k1j_line[224];\n"
        "            sprintf(k1j_line,\n"
        f'                "K1J DSOUND ABI {name}: n=%u ebx=%08X ecx=%08X eax=%08X edx=%08X esi=%08X edi=%08X esp=%08X",\n'
        f"                (unsigned)k1j_visits_{name}, (unsigned)ebx,\n"
        "                (unsigned)ecx, (unsigned)eax, (unsigned)edx,\n"
        "                (unsigned)esi, (unsigned)edi, (unsigned)g_esp);\n"
        "            trace(k1j_line);\n"
        "        }\n"
        "    }\n"
    )

def modify(filename: str, source: str) -> str:
    if filename not in OWNERS:
        raise ValueError("unexpected K1J owner " + filename)
    if TAG in source:
        raise ValueError("K1J instrumentation already present")
    crlf = source.count("\r\n")
    if source.count("\r") != crlf or (crlf and crlf != source.count("\n")):
        raise ValueError("invalid source line endings")
    nl = "\r\n" if crlf else "\n"
    fn, points = OWNERS[filename]
    matches = [m for m in ENTRY.finditer(source) if m.group(1) == fn]
    if len(matches) != 1:
        raise ValueError("Expected exactly one function BODY for " + fn)
    m = matches[0]
    ending = CLOSE.search(source, m.end())
    if ending is None:
        raise ValueError("Missing top-level closing brace for " + fn)
    begin, end = m.start(), ending.end()
    body = source[begin:end]
    names = []
    for name, anchor, placement in points:
        target = anchor.replace("\n", nl)
        if body.count(target) != 1:
            raise ValueError("K1J source anchor not unique: " + name)
        marker = sample(name).rstrip("\n").replace("\n", nl)
        if placement == "before":
            body = body.replace(target, marker + nl + target, 1)
        else:
            body = body.replace(target, target + nl + marker, 1)
        names.append(name)
    if body.count(TAG) != len(points):
        raise ValueError("K1J forensic probe count mismatch")
    if READ_WRITE.findall(body) != READ_WRITE.findall(source[begin:end]):
        raise ValueError("K1J guest memory operation sequence changed")
    if source[:begin] != source[:begin] or source[end:] != source[end:]:
        raise RuntimeError("source prefix/suffix invariant broken")
    result = source[:begin] + body + source[end:]
    if result.count("K1G XACT ABI ") != source.count("K1G XACT ABI "):
        raise ValueError("K1J unexpectedly changed K1G original owner")
    return result

def stage(baseline: Path, manifest: Path, out: Path) -> dict:
    baseline, manifest, out = baseline.resolve(), manifest.resolve(), out.resolve()
    if baseline == out or baseline in out.parents or out in baseline.parents:
        raise ValueError("K1J output cannot overwrite K1G baseline")
    doc = json.loads(manifest.read_text(encoding="utf-8-sig"))
    files = sorted(baseline.glob("translated_*.cpp"))
    headers = sorted(baseline.glob("*.h"))
    source_files = [*files, *headers]
    if (
        doc.get("status") != "STAGED_ONLY_NO_XDK_BUILD"
        or doc.get("marker") != SOURCE_MARKER
        or doc.get("modified_shards") != ["translated_029.cpp"]
        or doc.get("original_shards") != 64
        or doc.get("unchanged_shards") != 63
        or Path(doc.get("staged_directory", "NONEXISTENT")).resolve() != baseline
        or len(files) != 64
        or not any(h.name == "translated_runtime.h" for h in headers)
        or sha((baseline / "translated_029.cpp").read_bytes()) != doc.get("staged_owner_sha256")
    ):
        raise ValueError("K1G manifest/source provenance mismatch")
    if b"K1E XACT LIST PRE:" not in (baseline / "translated_029.cpp").read_bytes():
        raise ValueError("K1E existing list write witness missing")
    updated = {}
    for name in OWNERS:
        old = (baseline / name).read_bytes()
        updated[name] = modify(name, old.decode("utf-8")).encode("utf-8")
        if sha(updated[name]) == sha(old):
            raise ValueError("K1J expected one modified body: " + name)
    names = {f.name for f in source_files}
    if out.exists() and any(out.iterdir()):
        if {f.name for f in out.iterdir()} != names:
            raise ValueError("existing K1J shard/header set drift")
        for f in source_files:
            expected = updated.get(f.name, f.read_bytes())
            if (out / f.name).read_bytes() != expected:
                raise ValueError("existing K1J stage drift: " + f.name)
        print("[K1J] REUSE PASS: 64 TrueTUs and all headers SHA verified")
    else:
        out.mkdir(parents=True, exist_ok=True)
        for f in source_files:
            target = out / f.name
            if f.name in OWNERS:
                target.write_bytes(updated[f.name])
            else:
                shutil.copy2(f, target)
    for f in source_files:
        old = f.read_bytes()
        new = (out / f.name).read_bytes()
        if f.name in OWNERS:
            if new != updated[f.name]:
                raise RuntimeError("modified K1J owner drift: " + f.name)
        elif new != old:
            raise RuntimeError("non-target K1G baseline changed: " + f.name)
    traces = [point[0] for fn, points in OWNERS.values() for point in points]
    record = {
        "status": "STAGED_ONLY_NO_XDK_BUILD",
        "marker": TAG,
        "baseline_directory": str(baseline),
        "staged_directory": str(out),
        "baseline_marker": SOURCE_MARKER,
        "translated_shards": 64,
        "modified_from_k1g": sorted(OWNERS),
        "unchanged_from_k1g": 62,
        "preserved_k1g_owner": True,
        "preserved_k1e_witness": True,
        "guest_memory_ops_added": 0,
        "guest_register_writes_added": 0,
        "unknown_memory_fences": "UNCHANGED",
        "probe_stages": traces,
        "changed_owner_hashes": {
            name: {"old_sha256": sha((baseline / name).read_bytes()),
                   "new_sha256": sha(updated[name])}
            for name in sorted(OWNERS)
        },
    }
    out_manifest = out.parent / "k1j-dsound-register-manifest.json"
    out_manifest.write_bytes((json.dumps(record, indent=2) + "\n").encode("utf-8"))
    return record

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--k1g-shards", required=True, type=Path)
    p.add_argument("--k1g-manifest", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    doc = stage(a.k1g_shards, a.k1g_manifest, a.out)
    print("[K1J] PASS: K1G/K1E existing runtime telemetry preserved")
    print("[K1J] PASS: only translated_017.cpp and translated_041.cpp modified")
    print("[K1J] PASS: 62 other TrueTUs + every header byte-for-byte unchanged")
    print("[K1J] PASS: no guest reads/writes/register assignments, memory fences unchanged")
    print("[K1J] STAGE ONLY: " + str(a.out))
    print("[K1J] manifest=" + str(a.out.parent / "k1j-dsound-register-manifest.json"))

if __name__ == "__main__":
    main()

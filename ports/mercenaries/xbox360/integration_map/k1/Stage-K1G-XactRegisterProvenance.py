#!/usr/bin/env python3
"""K1G: one-TU host-only register probes along the proven K1E XACT function.

K1E hardware: EBX=00000018 at the list-tail store, but K1F only proves
"ebx = ecx" at function entry. Nested translated calls may disturb shared
guest registers. Sample BEFORE copying ECX and after each nested-call
boundary. No new guest reads/writes, no pointer substitutions, no fence changes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

TAG = "K1G-XACT-REGISTER-PROVENANCE-20261030"
OWNER = "translated_029.cpp"
FUNCTION = "sub_0027DC5B"
ENTRY = re.compile(
    r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_0027DC5B"
    r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{"
)
CLOSE = re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
# Each anchor occurs once inside the original K1E instrumentation body.
# Labels are reached immediately AFTER their preceding translated guest call.
STAGES = (
    ("ENTRY", "    ebx = ecx;", "before"),
    ("POST_COPY", "    ++s_phase6dqXactInitEntries;", "before"),
    ("AFTER_D5C0", "loc_0027DC69: ;\n    PHASE4C_BUDGET_TICK(0x0027DC69u);", "after"),
    ("AFTER_29FDF0", "loc_0027DC8A: ;\n    PHASE4C_BUDGET_TICK(0x0027DC8Au);", "after"),
    ("AFTER_29E435", "loc_0027DCAC: ;\n    PHASE4C_BUDGET_TICK(0x0027DCACu);", "after"),
    ("AFTER_28345A", "loc_0027DCBB: ;\n    PHASE4C_BUDGET_TICK(0x0027DCBBu);", "after"),
    ("AFTER_1787C0", "loc_0027DCE5: ;\n    PHASE4C_BUDGET_TICK(0x0027DCE5u);", "after"),
    ("BEFORE_LIST", "loc_0027DD06: ;\n    PHASE4C_BUDGET_TICK(0x0027DD06u);", "after"),
)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def probe(name: str) -> str:
    # Local C++ block means goto labels cannot cross variable initialization.
    # All operands are pre-existing emulated registers, not guest memory accesses.
    return (
        "    /* " + TAG + ": " + name + " */\n"
        "    {\n"
        "        static uint32_t k1g_visits_" + name + " = 0u;\n"
        "        ++k1g_visits_" + name + ";\n"
        "        if (k1g_visits_" + name + " <= 4u || k1g_visits_" + name + " == 32u)\n"
        "        {\n"
        "            char k1g_line[256];\n"
        "            sprintf(k1g_line,\n"
        '                "K1G XACT ABI ' + name + ': n=%u ecx=%08X ebx=%08X eax=%08X edx=%08X esi=%08X edi=%08X esp=%08X",\n'
        "                (unsigned)k1g_visits_" + name + ", (unsigned)ecx,\n"
        "                (unsigned)ebx, (unsigned)eax, (unsigned)edx,\n"
        "                (unsigned)esi, (unsigned)edi, (unsigned)g_esp);\n"
        "            trace(k1g_line);\n"
        "        }\n"
        "    }\n"
    )

def modify(text: str) -> str:
    if TAG in text:
        raise ValueError("already instrumented with K1G")
    if text.count("K1E XACT LIST PRE:") != 1:
        raise ValueError("K1E pre-write probe not present exactly once")
    crlf = text.count("\r\n")
    if text.count("\r") != crlf or (crlf and crlf != text.count("\n")):
        raise ValueError("mixed/corrupt TrueTU line endings")
    nl = "\r\n" if crlf else "\n"
    match = list(ENTRY.finditer(text))
    if len(match) != 1:
        raise ValueError("expected exactly one XACT function definition")
    ending = CLOSE.search(text, match[0].end())
    if ending is None:
        raise ValueError("XACT body missing top-level closing brace")
    begin = match[0].start()
    end = ending.end()
    body = text[begin:end]
    if body.count("loc_0027DD0C: ;") != 1 or body.count("GUEST_WRITE32(ecx, eax);") != 1:
        raise ValueError("original K1D list-link site drift")
    for name, marker, position in STAGES:
        actual = marker.replace("\n", nl)
        if body.count(actual) != 1:
            raise ValueError("K1G expected exactly one " + name + " anchor")
        insert = probe(name).replace("\n", nl)
        if position == "before":
            body = body.replace(actual, insert + actual, 1)
        else:
            body = body.replace(actual, actual + nl + insert.rstrip("\r\n"), 1)
    if body.count(TAG) != len(STAGES) or body.count("K1E XACT LIST PRE:") != 1:
        raise ValueError("K1G probe/witness staging drift")
    if body.count("GUEST_WRITE32(ecx, eax);") != 1:
        raise ValueError("K1G changed original linked-list store count")
    return text[:begin] + body + text[end:]

def stage(k1e_dir: Path, k1e_manifest: Path, out: Path) -> dict:
    k1e_dir, k1e_manifest, out = (
        k1e_dir.resolve(), k1e_manifest.resolve(), out.resolve()
    )
    if k1e_dir == out or k1e_dir in out.parents or out in k1e_dir.parents:
        raise ValueError("K1G output must be independent of K1E stage")
    base = json.loads(k1e_manifest.read_text(encoding="utf-8-sig"))
    if (base.get("marker") != "K1E-XACT-TAIL-EDGE-20261030"
        or base.get("modified_shards") != [OWNER]
        or base.get("original_shards") != 64
        or base.get("unchanged_shards") != 63
        or Path(base.get("staged_directory", "")).resolve() != k1e_dir):
        raise ValueError("K1E manifest identity/staged directory mismatch")
    files = sorted(k1e_dir.glob("translated_*.cpp"))
    headers = sorted(k1e_dir.glob("*.h"))
    if len(files) != 64 or not any(h.name == "translated_runtime.h" for h in headers):
        raise ValueError("K1E TrueTU/header set incomplete")
    source_owner = k1e_dir / OWNER
    old = source_owner.read_bytes()
    if sha(old).lower() != base.get("staged_owner_sha256", "").lower():
        raise ValueError("K1E staged owner SHA mismatch")
    original_root = Path(base["source_directory"])
    originals = sorted(original_root.glob("translated_*.cpp"))
    if len(originals) != 64:
        raise ValueError("original 64 TrueTU source set missing")
    for file in files + headers:
        if file.name == OWNER:
            continue
        old_file = original_root / file.name
        if not old_file.is_file() or sha(file.read_bytes()) != sha(old_file.read_bytes()):
            raise ValueError("K1E non-target TrueTU/header provenance drift: " + file.name)
    updated = modify(old.decode("utf-8")).encode("utf-8")
    names = {p.name for p in files + headers}
    if out.exists() and any(out.iterdir()):
        if {p.name for p in out.iterdir()} != names:
            raise ValueError("existing K1G staging file set drift")
        for file in files + headers:
            expected = sha(updated) if file.name == OWNER else sha(file.read_bytes())
            if sha((out / file.name).read_bytes()) != expected:
                raise ValueError("existing K1G staged file SHA mismatch: " + file.name)
        print("[K1G] REUSE PASS: 64 staged TUs and headers verified")
    else:
        out.mkdir(parents=True, exist_ok=True)
        for file in files + headers:
            if file.name == OWNER:
                (out / file.name).write_bytes(updated)
            else:
                shutil.copy2(file, out / file.name)
    if any(sha(file.read_bytes()) != (sha(old) if file.name == OWNER else sha((out / file.name).read_bytes()))
           for file in files + headers):
        raise RuntimeError("K1G unexpectedly changed K1E inputs")
    record = {
        "status": "STAGED_ONLY_NO_XDK_BUILD",
        "marker": TAG,
        "source_directory": str(k1e_dir),
        "staged_directory": str(out),
        "original_shards": 64,
        "unchanged_shards": 63,
        "modified_shards": [OWNER],
        "old_owner_sha256": sha(old),
        "staged_owner_sha256": sha(updated),
        "probe_stages": [name for name, _, _ in STAGES],
        "guest_reads_added": 0,
        "guest_writes_added": 0,
        "guest_register_writes_added": 0,
        "memory_hard_fences": "UNCHANGED",
        "preserved_k1e_witness": True,
    }
    manifest = out.parent / "k1g-register-provenance-manifest.json"
    manifest.write_bytes((json.dumps(record, indent=2) + "\n").encode("utf-8"))
    return record

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k1e-shards", type=Path, required=True)
    ap.add_argument("--k1e-manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = stage(args.k1e_shards, args.k1e_manifest, args.out)
    print("[K1G] STAGING PASS: " + ", ".join(doc["probe_stages"]))
    print("[K1G] Only translated_029.cpp changed; K1E list witness preserved")
    print("[K1G] Guest reads/stores/register writes unchanged; hard fences unchanged")
    print("[K1G] NO XDK build yet; manifest=" +
          str(args.out.parent / "k1g-register-provenance-manifest.json"))

if __name__ == "__main__":
    main()

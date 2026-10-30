#!/usr/bin/env python3
"""K1F source-only follow-up to the K1E hardware list-tail witness.

The original XACTENG list insertion at guest VA 0027DD0C wrote to the
old tail 00041D70, with head 0000008C and EBX 00000018.
Extract original owner setup and lexical callers; do not mutate guest
source, repair a pointer, invoke XDK, or bypass unknown-memory fences.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

OWNER = "translated_029.cpp"
FUNC = "sub_0027DC5B"
LABEL = "loc_0027DD0C: ;"
ENTRY_RE = re.compile(
    r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_0027DC5B"
    r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{"
)
END_RE = re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
CALL_RE = re.compile(r"\bsub_0027DC5B\s*\(\s*\)")
EBX_RE = re.compile(r"\bebx\s*(?:\+=|-=|\*=|/=|=|\^=|\|=|&=|<<=|>>=)")

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def cut(lines: list[str], start: int, end: int) -> list[str]:
    return [f"{i+1:6d} {lines[i]}" for i in range(max(0, start), min(len(lines), end))]

def audit(originals: Path, manifest: Path) -> str:
    originals = originals.resolve()
    shards = sorted(originals.glob("translated_*.cpp"))
    if len(shards) != 64 or not (originals / "translated_runtime.h").is_file():
        raise ValueError("requires frozen 64 original TrueTUs and translated_runtime.h")
    doc = json.loads(manifest.read_text(encoding="utf-8-sig"))
    if (doc.get("marker") != "K1E-XACT-TAIL-EDGE-20261030"
        or doc.get("modified_shards") != [OWNER]
        or doc.get("original_shards") != 64
        or doc.get("unchanged_shards") != 63):
        raise ValueError("K1E manifest identity mismatch")
    owner = originals / OWNER
    if sha(owner).lower() != doc.get("old_owner_sha256", "").lower():
        raise ValueError("frozen original XACT owner SHA mismatch")
    staged = Path(doc["staged_directory"]).resolve() / OWNER
    if not staged.is_file() or sha(staged).lower() != doc.get("staged_owner_sha256", "").lower():
        raise ValueError("K1E staged XACT owner SHA mismatch")
    source = owner.read_bytes().decode("utf-8")
    matches = list(ENTRY_RE.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected one original {FUNC} implementation, got {len(matches)}")
    finish = END_RE.search(source, matches[0].end())
    if finish is None:
        raise ValueError("XACT original body missing top-level closing brace")
    body = source[matches[0].start():finish.end()]
    lines = source.splitlines()
    first = source[:matches[0].start()].count("\n")
    last = min(len(lines), source[:finish.end()].count("\n") + 1)
    labels = [i for i in range(first, last) if LABEL in lines[i]]
    if (len(labels) != 1 or
        body.count("PHASE4C_BUDGET_TICK(0x0027DD0Cu);") != 1 or
        body.count("ecx = GUEST_READ32(edx + 4);") != 1 or
        body.count("GUEST_WRITE32(ecx, eax);") != 1):
        raise ValueError("K1D-proven original linked-list instruction sequence drifted")
    anchor = labels[0]
    report = [
        "K1F SOURCE-ONLY XACT LIST-HEAD PROVENANCE",
        "K1E Xbox: guest VA 0027DD0C, EBX=00000018, head=0000008C,",
        "head+4=00000090, old tail=00041D70, inserted node=01B672D8",
        "K1C Xbox: WRITE32[00041D70]=01B672D8",
        "Later DSOUND: READ32 EFEE0EC4 at tick 27029593",
        "This proves a damaging list-link store, NOT where EBX=18 originated.",
        "No source changes, guessed list-head repairs, or memory-fence changes.",
        "Owner SHA256=" + sha(owner),
        "K1E staged SHA256=" + sha(staged),
        f"Function={FUNC} lines={first+1}..{last}, site={anchor+1}",
        "", "## Original function entry / register setup",
        *cut(lines, first, min(last, first + 85)),
        "", "## Source immediately before and after original list insertion",
        *cut(lines, max(first, anchor - 110), min(last, anchor + 40)),
        "", "## EBX assignments and mutations inside original function",
    ]
    changes = [i for i in range(first, last) if EBX_RE.search(lines[i])]
    report.append(f"EBX mutations={len(changes)}")
    for i in changes:
        report.extend([f"-- EBX at line {i+1} --", *cut(lines, max(first,i-4), min(last,i+6))])
    report.extend(["", "## Source arithmetic relevant to the low-memory head"])
    for i in range(first, last):
        if re.search(r"(?:ebx\s*\+\s*0x7[48]|edx\s*\+\s*4)", lines[i]):
            report.extend([f"-- list access at line {i+1} --", *cut(lines, max(first,i-3), min(last,i+5))])
    report.extend(["", "## Direct lexical callsites among original 64 TrueTUs"])
    callers = []
    for path in shards:
        caller_lines = path.read_bytes().decode("utf-8").splitlines()
        for i, line in enumerate(caller_lines):
            if CALL_RE.search(line) and "void sub_0027DC5B" not in line:
                callers.append(f"{path.name}:{i+1}")
                if len(callers) <= 20:
                    report.extend([f"-- caller {path.name}:{i+1} --", *cut(caller_lines, i-16, i+6)])
    report.extend([
        f"Direct lexical callsites={len(callers)} (first 20 shown)",
        "Indirect calls may not be visible to this source-only scanner.",
        "", "NEXT: establish source and live origin of EBX=18, and initialization of [0x90].",
        "Do not replace guest head/tail based only on this lexical report.",
    ])
    return "\n".join(report) + "\n"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original-shards", type=Path, required=True)
    ap.add_argument("--k1e-manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    files = [*sorted(a.original_shards.glob("translated_*.cpp")),
             *sorted(a.original_shards.glob("*.h")), a.k1e_manifest]
    identities = {p.resolve():sha(p) for p in files}
    if a.out.resolve() in identities or a.original_shards.resolve() in a.out.resolve().parents:
        raise ValueError("cannot write report over frozen TrueTU inputs")
    result = audit(a.original_shards, a.k1e_manifest)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(result.encode("utf-8"))
    if any(sha(p) != old for p,old in identities.items()):
        raise RuntimeError("original input modified during K1F read-only audit")
    print("[K1F] PASS: original XACT source and K1E witness identity verified")
    print("[K1F] PASS: 64 TrueTU inputs unchanged; NO XDK / game runtime changes")
    print("[K1F] Report=" + str(a.out))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""K1H: source-only proof search for DSOUND EBX preservation, no guest changes.

K1G hardware: EBX=01B5C320 after sub_0027D5C0 and 00000018 after
sub_0029FDF0. The register change crosses sub_0029FDF0, but the exact
internal instruction/return path responsible has NOT been proved.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = "sub_0029FDF0"
OWNER = "translated_029.cpp"
ENTRY = re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+(sub_[0-9A-Fa-f]{8})[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
CLOSE = re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
CALL = re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(")
EBX_CHANGE = re.compile(r"\bebx\s*(?:=|\+=|-=|\^=|\|=|&=|\*=|/=|<<=|>>=)|\bPOP32\s*\(\s*(?:g_)?esp\s*,\s*ebx\s*\)")
SAVES = re.compile(r"\b(?:PUSH32|POP32)\s*\([^;]*\bebx\b")
ENDS = re.compile(r"\breturn\s*;|\besp\s*=\s*ebp\s*;")

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def index(shards: list[Path]):
    """Index function bodies only (forward declarations are ignored)."""
    found = {}
    for shard in shards:
        src = shard.read_text(encoding="utf-8")
        for match in ENTRY.finditer(src):
            close = CLOSE.search(src, match.end())
            if close is None:
                raise ValueError(f"Unclosed function {match.group(1)} in {shard.name}")
            name = match.group(1)
            if name in found:
                raise ValueError(f"Duplicate function body: {name}")
            start = src.count("\n", 0, match.start()) + 1
            lines = src[match.start():close.end()].splitlines()
            found[name] = (shard.name, start, lines)
    return found

def details(name: str, definitions: dict, max_dump: int, follow: bool = False) -> list[str]:
    if name not in definitions:
        return [f"{name}: function body NOT FOUND in the 64 shards (manual/indirect router possible)"]
    filename, start, lines = definitions[name]
    scan = lines[1:]
    calls = []
    for offset, line in enumerate(scan, 1):
        for callee in CALL.findall(line):
            if callee != name:
                calls.append((start+offset, callee, line.strip()))
    mods = [(start+i, line) for i, line in enumerate(lines) if EBX_CHANGE.search(line)]
    preserves = [(start+i, line) for i, line in enumerate(lines) if SAVES.search(line)]
    returns = [(start+i, line) for i, line in enumerate(lines) if ENDS.search(line)]
    result = [f"## {name} owner={filename} lines={start}..{start+len(lines)-1}",
              f"Original guest source lines={len(lines)} EBX-change candidates={len(mods)} "
              f"EBX save/restore references={len(preserves)} return/leave references={len(returns)} "
              f"direct callsites={len(calls)}", ""]
    def excerpts(hits, title, limit=48):
        result.append(title)
        if not hits:
            result.append("  none lexical (not runtime proof)")
            return
        for line_no, line in hits[:limit]:
            result.append(f"  {line_no:7d} {line.strip()}")
        if len(hits) > limit:
            result.append(f"  ... {len(hits)-limit} additional hits omitted")
    excerpts(mods, "EBX assignments / POP32:")
    excerpts(preserves, "EBX PUSH32 / POP32 sites:")
    excerpts(returns, "Returns and leave-frame sites:")
    result.append("Direct nested calls:")
    if not calls:
        result.append("  none lexical; indirect routes remain possible")
    for n, callee, line in calls[:60]:
        result.append(f"  {n:7d} -> {callee}: {line}")
    if len(calls) > 60:
        result.append(f"  ... {len(calls)-60} additional calls omitted")
    result.append("Original code (numbered; never patched):")
    if len(lines) <= max_dump:
        positions = range(len(lines))
    else:
        first = max_dump // 2
        positions = list(range(first)) + list(range(len(lines)-(max_dump-first), len(lines)))
    last = -2
    for i in positions:
        if i != last+1:
            result.append("    ... middle source omitted; EBX/return/call indexes above remain complete ...")
        result.append(f"  {start+i:7d} {lines[i]}")
        last = i
    if follow:
        result.append("Direct callee names (unique ordered): " +
                      ", ".join(dict.fromkeys(callee for _,callee,_ in calls)))
    result.append("")
    return result

def audit(shards_dir: Path, k1e_manifest: Path, out: Path) -> str:
    original = shards_dir.resolve()
    files = sorted(original.glob("translated_*.cpp"))
    header = original / "translated_runtime.h"
    if len(files) != 64 or not header.is_file():
        raise ValueError("Require 64 frozen original TrueTUs and runtime header")
    doc = json.loads(k1e_manifest.read_text(encoding="utf-8-sig"))
    if (doc.get("marker") != "K1E-XACT-TAIL-EDGE-20261030"
        or doc.get("original_shards") != 64
        or doc.get("source_directory") is None
        or Path(doc["source_directory"]).resolve() != original
        or doc.get("modified_shards") != [OWNER]
        or sha(original / OWNER).lower() != doc.get("old_owner_sha256", "").lower()):
        raise ValueError("K1E provenance / original owner SHA mismatch")
    if out.resolve() in [*(p.resolve() for p in files), header.resolve(), k1e_manifest.resolve()]:
        raise ValueError("Report must not overwrite frozen input")
    if original in out.resolve().parents:
        raise ValueError("Report must not be written into frozen source directory")
    original_digests = {p:sha(p) for p in [*files, header, k1e_manifest]}
    funcs = index(files)
    if ROOT not in funcs:
        raise ValueError(f"{ROOT} not translated in frozen 64-TU source (no inferred source)")
    report = [
        "K1H READ-ONLY DSOUND CALLEE-SAVE SOURCE AUDIT",
        "K1G Xbox ENTRY XACT: ECX=01B5C320; POST_COPY EBX=01B5C320",
        "K1G Xbox AFTER_D5C0: EBX=01B5C320",
        "K1G Xbox AFTER_29FDF0: EBX=00000018, EAX=0, ECX=0, EDX=024908B8",
        "K1G Xbox BEFORE_LIST: EBX=00000018; K1E writes guest .text[00041D70]",
        "Downstream: READ32 EFEE0EC4, tick=27029593, display_calls=0",
        "INTERPRETATION: register change occurred across nested sub_0029FDF0 call.",
        "Not yet proven WHICH nested function/return path caused it.",
        "This is a lexical audit, not a register-restoration patch or runtime validation.",
        f"Original owner={original / OWNER}",
        f"Owner SHA256={sha(original / OWNER)}",
        f"Indexed function bodies={len(funcs)}", "",
    ]
    report.extend(details(ROOT, funcs, 350, follow=True))
    _, _, root_lines = funcs[ROOT]
    direct = list(dict.fromkeys(name for line in root_lines[1:]
                                for name in CALL.findall(line) if name != ROOT))
    report.extend([f"## Direct callees of {ROOT} ({len(direct)} unique) - clipped to 20", ""])
    for callee in direct[:20]:
        report.extend(details(callee, funcs, 70))
    report.extend([
        "NEXT: identify exact DSOUND child/return path clobbering call-preserved EBX.",
        "Do not edit original guest memory, force-restoration or alter hard-fenced faults.",
        "Source scanner is lexical: indirect calls and handwritten support must be audited separately.",
        "END K1H READ ONLY REPORT",
    ])
    if any(sha(p) != digest for p,digest in original_digests.items()):
        raise RuntimeError("Input modified during read-only audit")
    return "\n".join(report) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original-shards", required=True, type=Path)
    ap.add_argument("--k1e-manifest", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    report = audit(args.original_shards, args.k1e_manifest, args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print("[K1H] PASS: exact K1E original source identity; one sub_0029FDF0 owner")
    print("[K1H] PASS: direct-callee/EBX-save lexical audit, 64 source TUs unchanged")
    print("[K1H] NO XDK build, Xbox run, or guest-memory changes")
    print("[K1H] Report=" + str(args.out))

if __name__ == "__main__":
    main()

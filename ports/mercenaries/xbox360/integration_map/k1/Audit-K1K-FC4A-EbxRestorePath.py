#!/usr/bin/env python3
"""K1K source-only FC4A save/restore audit after K1J hardware boundary.

K1J hardware:
  FD83_AFTER_CF0B EBX=01B5C320
  FD83_AFTER_FC4A EBX=00000018
The precise sub_0029FC4A instruction / POP32 stack cause remains UNPROVEN.
This script prints the original unmodified 438-line function and all
EBX, stack, return, goto and nested-call boundaries with context.
No game bytes included; requires the user's locally generated frozen TrueTUs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "sub_0029FC4A"
OWNER = "translated_053.cpp"
XACT_OWNER = "translated_029.cpp"
ENTRY = re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_0029FC4A"
                   r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
CLOSE = re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
EBX_WRITE = re.compile(r"(?<!\w)ebx\s*(?:=|\+=|-=|\^=|\|=|&=|\*=|/=|<<=|>>=)"
                       r"|\bPOP32\s*\(\s*(?:g_)?esp\s*,\s*ebx\s*\)")
EBX_SAVE = re.compile(r"\b(?:PUSH32|POP32)\s*\([^;]*\bebx\b")
STACK = re.compile(r"\b(?:PUSH32|POP32)\s*\(|\b(?:g_)?esp\s*(?:=|\+=|-=)")
FRAME = re.compile(r"\b(?:return\s*;|goto\s+loc_[0-9A-Fa-f]+|PHASE6DJ_ICALL_SAFE)\b")
CALL = re.compile(r"\bsub_[0-9A-Fa-f]{8}\s*\(\s*\)")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(source: str) -> tuple[int, list[str]]:
    matches = list(ENTRY.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {TARGET} implementation, got {len(matches)}")
    start_match = matches[0]
    end_match = CLOSE.search(source, start_match.end())
    if end_match is None:
        raise ValueError("FC4A original function has no top-level close")
    start = source.count("\n", 0, start_match.start()) + 1
    lines = source[start_match.start():end_match.end()].splitlines()
    return start, lines


def matches_index(lines: list[str], pat: re.Pattern) -> list[int]:
    return [i for i, value in enumerate(lines) if pat.search(value)]


def audit(originals: Path, k1e_manifest: Path, k1i_report: Path, out: Path) -> str:
    originals = originals.resolve()
    out = out.resolve()
    srcs = sorted(originals.glob("translated_*.cpp"))
    heads = sorted(originals.glob("*.h"))
    if len(srcs) != 64 or not (originals / "translated_runtime.h").is_file():
        raise ValueError("Require complete 64 frozen source TrueTUs and header")
    doc = json.loads(k1e_manifest.read_text(encoding="utf-8-sig"))
    k1i = k1i_report.read_text(encoding="utf-8-sig")
    if (doc.get("marker") != "K1E-XACT-TAIL-EDGE-20261030"
        or doc.get("modified_shards") != [XACT_OWNER]
        or doc.get("original_shards") != 64
        or Path(doc.get("source_directory", ".")).resolve() != originals
        or sha(originals / XACT_OWNER).lower() != doc.get("old_owner_sha256","").lower()):
        raise ValueError("K1E original source provenance failed")
    k1i_gates = (
        "K1I READ-ONLY DSOUND NESTED EBX PROVENANCE",
        "Reachable named functions=29; missing bodies=0",
        "SUB_0029FDF0 -> SUB_0029FD83 -> SUB_0029FC4A",
        "owner=translated_053.cpp lines=17686..18123",
        "ebx = esi + 0x18;",
        "POP32(esp, ebx);",
    )
    if not all(g in k1i for g in k1i_gates):
        raise ValueError("K1I actual frozen FC4A proof report missing or different")
    if out in {p.resolve() for p in [*srcs,*heads,k1e_manifest,k1i_report]} or originals in out.parents:
        raise ValueError("Report output cannot overwrite any frozen source input")
    identities = {p:sha(p) for p in [*srcs,*heads,k1e_manifest,k1i_report]}
    source = (originals / OWNER).read_bytes().decode("utf-8")
    start, body = extract(source)
    if start != 17686 or len(body) != 438:
        raise ValueError(f"Expected K1I FC4A lines 17686..18123; got {start}..{start+len(body)-1}")
    required = {
        17996: "ebx = esi + 0x18;",
        18118: "POP32(esp, ebx);",
        17743: "PUSH32(esp, ebx);",
        17853: "ebx = r59_saved_ebx;",
        17888: "ebx = r59_saved_ebx;",
        17958: "ebx = r59_saved_ebx;",
        18025: "PUSH32(esp, ebx);",
    }
    for number, statement in required.items():
        if statement not in body[number-start]:
            raise ValueError(f"FC4A source anchor drift at {number}: {statement}")
    mutation = matches_index(body, EBX_WRITE)
    saves = matches_index(body, EBX_SAVE)
    stack = matches_index(body, STACK)
    returns = matches_index(body, FRAME)
    calls = matches_index(body, CALL)
    focus = sorted(set(mutation + saves + returns + calls +
                       [17996-start,18118-start,17743-start,18025-start]))
    report = [
        "K1K FC4A ORIGINAL EBX SAVE/RESTORE PATH - READ ONLY",
        "K1J Xbox FD83_AFTER_CF0B EBX=01B5C320; FD83_AFTER_FC4A EBX=00000018",
        "R59 FC4A trace previously restored EBX=8007000E after A19FC and FF54;",
        "Do not treat any observed working value as the correct restored value.",
        "K1I bounded call tree identified 29 functions (0 missing), and",
        "FC4A has explicit EBX=ESI+0x18, multiple saved_ebx restores, and POP32.",
        "A POP32(esp,ebx) may read a bad stack slot or may be bypassed.",
        "Lexical evidence cannot determine runtime branch or stack correctness.",
        f"Function={TARGET}; owner={OWNER}; original lines={start}..{start+len(body)-1}",
        f"Owner SHA256={sha(originals / OWNER)}",
        f"EBX mutation-like source lines={len(mutation)}",
        f"EBX PUSH/POP source lines={len(saves)}",
        f"Guest stack PUSH/POP/ESP mutation-like lines={len(stack)}",
        f"Return/goto/indirect dispatch source lines={len(returns)}",
        f"Direct-call source lines={len(calls)}",
        "",
        "## All key EBX / branch / return / call sites (with 5-line source windows)",
    ]
    last = -1
    for i in focus:
        lo, hi = max(0,i-4), min(len(body),i+6)
        if lo > last:
            report.append("  ...")
        for k in range(max(lo,last), hi):
            report.append(f"{start+k:7d} {body[k]}")
        last = max(last, hi)
    report.extend([
        "", "## All stack operations (full unmodified lexical index)",
        *[f"{start+i:7d} {body[i]}" for i in stack],
        "", "## Entire original FC4A body (never modified)",
        *[f"{start+i:7d} {line}" for i,line in enumerate(body)],
        "", "NEXT: correlate exact early-exit + POP32 paths with K1J hardware.",
        "Only if a stack/register bug is proven should we stage a semantically",
        "correct fix. No arbitrary EBX restore at XACT callsite, no guest fences relaxed.",
        "END K1K READ ONLY REPORT",
    ])
    if any(sha(path) != digest for path,digest in identities.items()):
        raise RuntimeError("K1K read-only audit unexpectedly changed original inputs")
    return "\n".join(report) + "\n"


def selftest() -> None:
    fixture = (
        "void sub_0029FC4A(void);\n"
        "void sub_0029FC4A(void)\n"
        "{\n"
        "    PUSH32(esp, ebx);\n"
        "    ebx = esi + 0x18;\n"
        "    POP32(esp, ebx);\n"
        "    return;\n"
        "}\n"
    )
    for nl in ("\n", "\r\n"):
        start, body = extract(fixture.replace("\n",nl))
        assert start == 2 and len(body) == 7
        assert len(matches_index(body, EBX_SAVE)) == 2
        assert len(matches_index(body, EBX_WRITE)) == 2
    try:
        extract(fixture.replace("void sub_0029FC4A(void)\n{","void sub_0029FC4B(void)\n{"))
    except ValueError:
        pass
    else:
        raise AssertionError("Missing original body accepted")
    print("[K1K] SYNTHETIC PASS: exact function body with forward declarations, LF/CRLF, EBX stack sites")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--original-shards", type=Path, required=True)
    p.add_argument("--k1e-manifest", type=Path, required=True)
    p.add_argument("--k1i-report", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    selftest()
    report = audit(args.original_shards, args.k1e_manifest, args.k1i_report,args.out)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(report.encode("utf-8"))
    print("[K1K] PASS: K1I FC4A source lines and K1E original owner SHA match")
    print("[K1K] PASS: full FC4A EBX/stack/return/child-call source audit; 64 TrueTU inputs unchanged")
    print("[K1K] NO XDK build, Xbox run or guest code changes")
    print("[K1K] Report="+str(args.out))


if __name__ == "__main__":
    main()

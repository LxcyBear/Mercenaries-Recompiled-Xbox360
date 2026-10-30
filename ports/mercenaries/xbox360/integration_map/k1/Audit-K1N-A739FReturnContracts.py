#!/usr/bin/env python3
"""K1N read-only original A739F child-call/ret-width audit.

K1M established A739F is a zero-stack-argument caller with its own
plain ret. R72 Xbox measured A19FC -> A739F guest ESP +4 and ESI
clobber, whereas A19FC -> A2A16 +4 is expected (one explicit arg).
Inspect child stack cleanup contracts before contemplating any repair.
This tool touches no TrueTU, XEX, guest CPU/memory, or hard fence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SOURCE_MARKER = "K1E-XACT-TAIL-EDGE-20261030"
OWNER_29_SHA = "4ab3cbe137476f77f598e28ed42392d009e84bd8b72e34ed2b27d2f17a13eb92"
PARENT = "SUB_002A739F"
CONTROL = "SUB_002A2A16"
# These are exact callsite contracts seen in the user-provided K1M
# frozen original function. Synthetic return-address pushes are not args.
CONTRACTS = (
    ("SUB_002A7322", 0, 1),
    ("SUB_002A70AA", 0, 1),
    ("SUB_002A6FDD", 0, 1),
    ("SUB_002A67E2", 0, 1),
    ("SUB_002A6B98", 0, 1),
    ("SUB_002A6EE9", 0, 1),
    ("SUB_002A6D1A", 1, 1),
    ("SUB_002A77BE", 1, 2),
)
FUNC_RE = re.compile(
    r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+(sub_[0-9a-fA-F]{8})"
    r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{"
)
END_RE = re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
CALL_RE = re.compile(r"\b(sub_[0-9A-Fa-f]{8})[ \t]*\([ \t]*\)")
RET_RE = re.compile(r"(?m)^\s*esp\s*\+=\s*(\d+)\s*;\s*return\s*;\s*/\*\s*ret(?:\s+(\d+))?\s*\*/")
POP_RE = re.compile(r"\bPOP32\s*\(")
PUSH_RE = re.compile(r"\bPUSH32\s*\(")
ESCAPE_RE = re.compile(r"\bPHASE6DJ_ICALL_SAFE\s*\(")


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bodies(files: list[Path]) -> dict[str, tuple[str, int, list[str]]]:
    output: dict[str, tuple[str, int, list[str]]] = {}
    for path in files:
        data = path.read_bytes().decode("utf-8")
        for m in FUNC_RE.finditer(data):
            name = m.group(1).upper()
            end = END_RE.search(data, m.end())
            if end is None:
                raise ValueError(f"Unterminated function {name} in {path.name}")
            if name in output:
                raise ValueError(f"Multiple original translated definitions of {name}")
            line_no = data.count("\n", 0, m.start()) + 1
            output[name] = (path.name, line_no, data[m.start():end.end()].splitlines())
    return output


def returns_in(body: list[str], firstline: int) -> list[tuple[int,int,str]]:
    output = []
    for j, line in enumerate(body):
        match = RET_RE.search(line)
        if match:
            output.append((firstline+j, int(match.group(1)), line.strip()))
    return output


def test() -> None:
    assert RETURNS_DEMO() == [(4, 4, "esp += 4; return; /* ret */")]
    assert [m.upper() for m in CALL_RE.findall(
        "PUSH32(esp, 0); sub_002A7322(); /* call */"
    )] == ["SUB_002A7322"]
    print("[K1N] SYNTHETIC PASS: plain ret / ret cleanup and direct call recognition")


def RETURNS_DEMO() -> list[tuple[int,int,str]]:
    return returns_in(["x", "y", "z", "esp += 4; return; /* ret */"], 1)


def audit(original_dir: Path, k1e_manifest: Path, k1m_report: Path, outfile: Path) -> str:
    original_dir = original_dir.resolve()
    outfile = outfile.resolve()
    cpp = sorted(original_dir.glob("translated_*.cpp"))
    header = original_dir / "translated_runtime.h"
    if len(cpp) != 64 or not header.is_file():
        raise ValueError("Need exact 64 frozen original TrueTU files and runtime header")
    manifest = json.loads(k1e_manifest.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("marker") != SOURCE_MARKER
        or manifest.get("modified_shards") != ["translated_029.cpp"]
        or manifest.get("original_shards") != 64
        or Path(manifest.get("source_directory", "MISSING")).resolve() != original_dir
        or manifest.get("old_owner_sha256","").lower() != checksum(original_dir / "translated_029.cpp").lower()
        or manifest.get("old_owner_sha256","").lower() != OWNER_29_SHA
    ):
        raise ValueError("K1E frozen TrueTU source provenance differs")
    text = k1m_report.read_text(encoding="utf-8-sig").replace("\r\n","\n")
    if "========== sub_002A739F ==========" not in text or "========== sub_002A2A16 ==========" not in text:
        raise ValueError("K1M complete A739F/A2A16 source evidence missing")
    if outfile in {f.resolve() for f in [*cpp, header, k1e_manifest, k1m_report]} or original_dir in outfile.parents:
        raise ValueError("K1N must not overwrite original source files")
    hashes={f:checksum(f) for f in [*cpp,header,k1e_manifest,k1m_report]}
    defs = bodies(cpp)
    for name,expected_owner in ((PARENT,"translated_009.cpp"),(CONTROL,"translated_042.cpp")):
        if name not in defs or defs[name][0] != expected_owner:
            raise ValueError(f"Missing exact K1M source function {name}")
        src="\n".join(defs[name][2]).strip()
        if src not in text:
            raise ValueError(f"K1M pasted source not identical to frozen original {name}")
    parent_fname,parent_start,parent_lines=defs[PARENT]
    found_calls: dict[str, list[tuple[int,int,str]]] = {}
    for i,line in enumerate(parent_lines):
        for callee in CALL_RE.findall(line):
            found_calls.setdefault(callee.upper(),[]).append((i,parent_start+i,line.strip()))
    wanted={name for name,_,_ in CONTRACTS}
    if set(found_calls)!=wanted:
        raise ValueError(f"K1M direct callee names differ: expected {wanted}; got {set(found_calls)}")
    for name,_,count in CONTRACTS:
        if len(found_calls[name])!=count:
            raise ValueError(f"K1M call count differs for {name}")
    lines=[
        "K1N READ-ONLY A739F NESTED RETURN CLEANUP CONTRACT AUDIT",
        "K1J Xbox: FC4A before A19FC EBX=01B5C320, after FC4A EBX=00000018.",
        "R72 Xbox: A19FC -> A739F ESP 008BF8B4 -> 008BF8B8 (unexpected +4).",
        "R72 control: A19FC -> A2A16 +4 (one stack argument, expected).",
        "A739F original: PUSH32 ESI, PUSH32 EDI; POP32 EDI/ESI, plain ret.",
        "K1M exact original A739F and A2A16 source matched frozen TrueTU.",
        "NOTE: return width is lexical, NOT live-branch/runtime proof.",
        "NOTE: a correct callee ret width does not prove nested ESP is balanced.",
        "NOTE: many child functions can have nested calls / indirect paths.",
        f"Frozen original source owner SHA256={checksum(original_dir/'translated_029.cpp')}",
        f"Indexed translated function bodies={len(defs)}",
        f"Original A739F owner={parent_fname}:{parent_start}",
        "", "## Direct A739F callsite stack-argument contracts and callee epilogues",
    ]
    suspects=[]
    for name,argc,count in CONTRACTS:
        if name not in defs:
            raise ValueError(f"Missing child translated body {name}")
        filename,first,body=defs[name]
        ret=returns_in(body,first)
        line_numbers=[x[1] for x in found_calls[name]]
        expected=argc*4
        widths=sorted({width-4 for _,width,_ in ret})
        # Internal emitted return increments include +4 synthetic return address.
        # For a no-arg plain ret, width=4, net arg cleanup=0.
        if not ret:
            status="NO_INLINE_RETURN_OR_MANUAL_CONTROL"
        elif len(widths)!=1:
            status="MULTIPLE_RET_WIDTHS_CHECK_BRANCH"
        elif widths[0]!=expected:
            status="CALLSITE_RET_WIDTH_MISMATCH_CANDIDATE"
            suspects.append(name)
        else:
            status="LEXICAL_RET_WIDTH_MATCH"
        lines.extend([
            f"### {name} | {filename}:{first}..{first+len(body)-1}",
            f"callsite_lines={line_numbers} count={count} args={argc} "
            f"expected_stack_arg_cleanup_bytes={expected}",
            f"emitted_guest_epilogue_total_esp_add={[w for _,w,_ in ret]} "
            f"synthetic_return_bytes=4",
            f"computed_argument_cleanup_bytes={widths}",
            f"nested_direct_calls={sum(len(CALL_RE.findall(s)) for s in body)} "
            f"indirect_calls={sum(bool(ESCAPE_RE.search(s)) for s in body)} "
            f"push_sites={sum(len(PUSH_RE.findall(s)) for s in body)} "
            f"pop_sites={sum(len(POP_RE.findall(s)) for s in body)}",
            f"status={status}",
        ])
        for index,lineno,statement in found_calls[name]:
            lines.append(f"  Parent at {lineno}:")
            for q in range(max(0,index-4),min(len(parent_lines),index+2)):
                lines.append(f"  {parent_start+q:6d} {parent_lines[q]}")
        for ln,width,statement in ret:
            lines.append(f"  Child return {ln}: {statement}")
        if not ret:
            lines.append("  WARNING: no standard translated return identified; inspect full source")
        lines.append("")
    lines.extend([
        "## Exact source for all A739F direct callees, original unmodified",
    ])
    for name,argc,count in CONTRACTS:
        filename,first,body=defs[name]
        lines.extend([
            f"### {name} ({filename}:{first}..{first+len(body)-1}; {len(body)} lines)"
        ])
        for i,statement in enumerate(body):
            lines.append(f"{first+i:7d} {statement}")
        lines.append("")
    lines.extend([
        "## Summary and next step",
        f"Number of lexical callsite/return mismatches={len(suspects)}",
        f"Mismatch candidates={'; '.join(suspects) if suspects else 'none'}",
        "A matching ret width is not a guarantee that nested calls preserve ESP.",
        "Use this to choose ONE source-proven runtime checkpoint around candidate",
        "A739F nested call boundaries before correcting guest ESP.",
        "Do not deploy the withdrawn K1L late FC4A repair.",
        "No XDK build, Xbox run, guest-memory modifications or fence changes.",
        "END K1N",
    ])
    if any(checksum(path)!=old for path,old in hashes.items()):
        raise RuntimeError("K1N original source inputs changed during read-only audit")
    return "\n".join(lines)+"\n"


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--original-shards", type=Path, required=True)
    p.add_argument("--k1e-manifest", type=Path, required=True)
    p.add_argument("--k1m-report", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args=p.parse_args()
    test()
    report=audit(args.original_shards,args.k1e_manifest,args.k1m_report,args.out)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(report,encoding="utf-8")
    print("[K1N] PASS: original K1M A739F/A2A16 and frozen K1E TrueTU provenance")
    print("[K1N] PASS: 8 unique nested callees, 9 direct callsites, ret-width/stack contracts")
    print("[K1N] 64 TrueTUs UNCHANGED; NO XDK build, Xbox run, or guest code changes")
    print("[K1N] Report="+str(args.out))

if __name__=="__main__":
    main()

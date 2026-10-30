#!/usr/bin/env python3
"""K1I: trace the K1G-proven DSOUND EBX-corruption call tree in frozen TrueTU source.

No source patches, EBX restoration, guest memory changes or XDK build.
Source-only recursive audit; lexical edges cannot prove live branch execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import deque
from pathlib import Path

ROOT = "sub_0029FDF0"
XACT_OWNER = "translated_029.cpp"
ENTRY_RE = re.compile(
    r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+(sub_[0-9A-Fa-f]{8})"
    r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{"
)
END_RE = re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
CALL_RE = re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(\s*\)")
EBX_RE = re.compile(
    r"\bebx\s*(?:=|\+=|-=|\^=|\|=|&=|\*=|/=|<<=|>>=)"
    r"|\b(?:POP32|POP16|POP8)\s*\(\s*(?:g_)?esp\s*,\s*ebx\s*\)"
)
SAVE_RE = re.compile(r"\b(?:PUSH32|POP32)\s*\([^;]*\bebx\b")
INDIRECT_RE = re.compile(r"\bPHASE6DJ_ICALL_SAFE\s*\(|/\* indirect call \*/")
EBX_18_RE = re.compile(r"\bebx\s*=\s*(?:0x0*18u?|\(?uint32_t\)?\s*0x0*18u?|\b24u?)\b", re.I)
CONST_18_RE = re.compile(r"\b0x0*18u?\b|\b24u?\b", re.I)
FENCE_RE = re.compile(r"hard.?fence|unknown.?memory", re.I)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_functions(files: list[Path]) -> dict[str, tuple[str, int, list[str]]]:
    definitions: dict[str, tuple[str, int, list[str]]] = {}
    for path in files:
        source = path.read_bytes().decode("utf-8")
        for m in ENTRY_RE.finditer(source):
            end = END_RE.search(source, m.end())
            if end is None:
                raise ValueError(f"Missing function ending: {path.name} {m.group(1)}")
            name = m.group(1).upper()
            if name in definitions:
                raise ValueError(f"Duplicate translated body {name}")
            line_number = source.count("\n", 0, m.start()) + 1
            body = source[m.start():end.end()].splitlines()
            definitions[name] = (path.name, line_number, body)
    return definitions


def calls_from(lines: list[str]) -> list[tuple[int, str, str]]:
    found = []
    for i, line in enumerate(lines[1:], 1):
        for callee in CALL_RE.findall(line):
            found.append((i, callee.upper(), line.strip()))
    return found


def walk(
    definitions: dict[str, tuple[str, int, list[str]]],
    root: str = ROOT,
    max_depth: int = 4,
    max_nodes: int = 350,
) -> tuple[dict[str, tuple[str, ...]], dict[str, list[tuple[int, str, str]]], bool]:
    root = root.upper()
    if root not in definitions:
        raise ValueError(f"Missing original translated root {root}")
    paths: dict[str, tuple[str, ...]] = {root: (root,)}
    queue: deque[tuple[str, int]] = deque([(root, 0)])
    edges = {}
    clipped = False
    while queue:
        current, depth = queue.popleft()
        lines = definitions[current][2]
        callsites = calls_from(lines)
        edges[current] = callsites
        if depth >= max_depth:
            continue
        for offset, callee, line in callsites:
            if callee in paths:
                continue
            if len(paths) >= max_nodes:
                clipped = True
                continue
            paths[callee] = paths[current] + (callee,)
            if callee in definitions:
                queue.append((callee, depth + 1))
    return paths, edges, clipped


def traits(
    func: tuple[str, int, list[str]],
) -> tuple[list[tuple[int,str]], list[tuple[int,str]], list[tuple[int,str]], list[tuple[int,str]], list[tuple[int,str]]]:
    _, start, body = func
    def matches(pattern: re.Pattern) -> list[tuple[int,str]]:
        return [(start + i, line.strip()) for i, line in enumerate(body)
                if pattern.search(line)]
    return (
        matches(EBX_RE),
        matches(SAVE_RE),
        matches(EBX_18_RE),
        matches(CONST_18_RE),
        matches(INDIRECT_RE),
    )


def short_hits(hits: list[tuple[int,str]], limit: int) -> list[str]:
    out = [f"      {line:7d} {text}" for line, text in hits[:limit]]
    if len(hits) > limit:
        out.append(f"      ... {len(hits)-limit} more matching source lines")
    if not hits:
        out.append("      none (lexical only)")
    return out


def audit(source_root: Path, k1e_manifest: Path, out: Path, max_depth: int) -> str:
    original = source_root.resolve()
    sources = sorted(original.glob("translated_*.cpp"))
    headers = sorted(original.glob("*.h"))
    files = [*sources, *headers, k1e_manifest]
    if len(sources) != 64 or not (original / "translated_runtime.h").is_file():
        raise ValueError("K1I requires 64 frozen original TrueTU C++ files and runtime header")
    manifest = json.loads(k1e_manifest.read_text(encoding="utf-8-sig"))
    owner = original / XACT_OWNER
    if (
        manifest.get("marker") != "K1E-XACT-TAIL-EDGE-20261030"
        or manifest.get("modified_shards") != [XACT_OWNER]
        or manifest.get("original_shards") != 64
        or manifest.get("unchanged_shards") != 63
        or Path(manifest.get("source_directory", "nonexistent")).resolve() != original
        or digest(owner).lower() != manifest.get("old_owner_sha256", "").lower()
    ):
        raise ValueError("K1I K1E manifest/original TrueTU provenance mismatch")
    staged = Path(manifest["staged_directory"]).resolve() / XACT_OWNER
    if not staged.is_file() or digest(staged).lower() != manifest.get("staged_owner_sha256","").lower():
        raise ValueError("K1I staged K1E owner SHA drift")
    input_ids = {f.resolve(): digest(f) for f in files}
    destination = out.resolve()
    if destination in input_ids or original in destination.parents:
        raise ValueError("K1I cannot overwrite original sources or manifest")

    definitions = parse_functions(sources)
    paths, edges, clipped = walk(definitions, max_depth=max_depth)
    rows = []
    missing = []
    for name, chain in paths.items():
        if name not in definitions:
            missing.append((name, chain))
            continue
        owner_name, start, body = definitions[name]
        changes, saves, literal18, mentions18, indirects = traits(definitions[name])
        rows.append((name, chain, owner_name, start, len(body), changes, saves, literal18, mentions18, indirects))

    lines: list[str] = [
        "K1I READ-ONLY DSOUND NESTED EBX PROVENANCE",
        "Hardware: XACT ECX/EBX=01B5C320 at entry; EBX=01B5C320 after 0027D5C0;",
        "EBX=00000018 after 0029FDF0, then K1E WRITE32[00041D70]=01B672D8.",
        "K1H: 0029FDF0, 0029CDBE, 0029FD83 contain no lexical EBX assignments.",
        "Crucial: EBX may change in direct or indirect grandchildren or host support.",
        "This report is SOURCE-ONLY; call-graph reachability != hardware path proof.",
        "Never infer register restoration from a lexical match alone.",
        f"Frozen owner SHA256={digest(owner)}",
        f"Source bodies indexed={len(definitions)}",
        f"Maximum recursive direct-call depth={max_depth}",
        f"Reachable named functions={len(paths)}; missing bodies={len(missing)}; "
        f"truncated by 350-node cap={clipped}",
        "", "## Direct-call graph (discovered BFS, first 220 nodes)",
    ]
    for name, chain in list(paths.items())[:220]:
        if name in definitions:
            changes, saves, set18, mentions18, indirects = traits(definitions[name])
            lines.append(
                f"{' -> '.join(chain)} | {definitions[name][0]} | "
                f"ebx_changes={len(changes)} saves={len(saves)} "
                f"set_18={len(set18)} const_18={len(mentions18)} "
                f"icalls={len(indirects)}"
            )
        else:
            lines.append(f"{' -> '.join(chain)} | BODY_MISSING_or_support")
    if len(paths) > 220:
        lines.append(f"... {len(paths)-220} additional nodes omitted from summary")
    lines.extend(["", "## Ranked direct-path EBX mutation candidates"])
    ranked = sorted(
        [row for row in rows if row[5] or row[7]],
        key=lambda row: (0 if row[7] else 1, len(row[1]), -len(row[5]), row[0])
    )
    if not ranked:
        lines.append("No lexical EBX mutations or assignments to 0x18 on bounded direct call paths.")
    for name, chain, filename, start, nlines, changes, saves, literal18, mentions18, indirects in ranked[:45]:
        lines.extend([
            f"### {' -> '.join(chain)}",
            f"owner={filename} lines={start}..{start+nlines-1} "
            f"EBX writes={len(changes)} EBX saves={len(saves)} "
            f"EBX=18 candidates={len(literal18)} indirects={len(indirects)}",
            "EBX modifications:",
            *short_hits(changes, 30),
            "EBX save/restore references:",
            *short_hits(saves, 20),
            "Literal 0x18 sites:",
            *short_hits(mentions18, 14),
        ])
    if len(ranked) > 45:
        lines.append(f"... {len(ranked)-45} additional candidate bodies omitted")
    lines.extend(["", "## Original sub_0029FD83 full, unmodified source"])
    if "SUB_0029FD83" not in definitions:
        raise ValueError("Original sub_0029FD83 body missing")
    _, start, body = definitions["SUB_0029FD83"]
    lines.extend(f"{start+i:7d} {text}" for i, text in enumerate(body))
    lines.extend(["", "## Important call boundaries and any indirect escape targets"])
    for name in (ROOT, "sub_0029CDBE", "sub_0029FD83",
                 "sub_002A41EE", "sub_0029CB9F", "sub_0029CF0B", "sub_0029FC4A"):
        upper = name.upper()
        if upper not in definitions:
            lines.append(f"{upper}: body not in frozen TrueTU pack")
            continue
        filename, start, code = definitions[upper]
        changes, saves, literal18, mentions18, indirects = traits(definitions[upper])
        lines.append(
            f"### {upper} {filename}:{start} ({len(code)} source lines): "
            f"EBX mutations {len(changes)}, saves {len(saves)}, "
            f"literal18 mentions {len(mentions18)}, ICALL {len(indirects)}"
        )
        for i, callee, statement in calls_from(code):
            lines.append(f"  direct call {start+i}: {callee}: {statement}")
        for no, statement in indirects:
            lines.append(f"  indirect dispatch {no}: {statement}")
        for no, statement in changes:
            lines.append(f"  EBX mutation {no}: {statement}")
    if missing:
        lines.extend(["", "## Unresolved direct names (manual/support/omitted)"])
        for name, chain in missing[:80]:
            lines.append(" -> ".join(chain))
    lines.extend([
        "", "NEXT: compare candidate EBX mutation paths against K1G hardware.",
        "If no unique path is proven, instrument post-call checkpoints within",
        "sub_0029FDF0 / sub_0029FD83 without changing guest CPU/memory semantics.",
        "No XDK invocation, no registers repaired, no guest memory fences weakened.",
        "END K1I",
    ])
    if any(digest(path) != before for path, before in input_ids.items()):
        raise RuntimeError("K1I original TrueTU files changed during audit")
    return "\n".join(lines) + "\n"


def test() -> None:
    def func(lines: list[str], source: str="translated_000.cpp"):
        return (source, 10, lines)
    sample = {
        "SUB_0029FDF0": func(["void sub_0029FDF0(void)", " {", "sub_0029FD83();", "}"]),
        "SUB_0029FD83": func(["void sub_0029FD83(void)", " {", "sub_0029FC4A();", "}"]),
        "SUB_0029FC4A": func(["void sub_0029FC4A(void)", " {", "ebx = 0x18;", "PUSH32(esp, ebx);", "}"]),
        "SUB_0029CDBE": func(["void sub_0029CDBE(void)", " {", "return;", "}"]),
    }
    paths, graph, clipped = walk(sample, max_depth=3)
    assert not clipped
    assert paths["SUB_0029FC4A"] == ("SUB_0029FDF0", "SUB_0029FD83", "SUB_0029FC4A")
    assert len(graph["SUB_0029FD83"]) == 1
    writes, saves, sets, mentions, indirects = traits(sample["SUB_0029FC4A"])
    assert len(writes) == 1 and len(saves) == 1 and len(sets) == 1
    assert len(mentions) == 1 and not indirects
    try:
        walk(sample, root="SUB_0029ABCD")
    except ValueError:
        pass
    else:
        raise AssertionError("Missing source root was accepted")
    print("[K1I] SYNTHETIC PASS: bounded direct-call graph and EBX/0x18 recognition")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--original-shards", type=Path, required=True)
    p.add_argument("--k1e-manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--depth", type=int, default=4)
    a = p.parse_args()
    if not 1 <= a.depth <= 5:
        raise ValueError("direct-call depth must be 1..5")
    test()
    report = audit(a.original_shards, a.k1e_manifest, a.out, a.depth)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(report.encode("utf-8"))
    print("[K1I] PASS: K1E original TrueTU and K1E staged owner SHA identities verified")
    print("[K1I] PASS: recursive direct DSOUND EBX source call-tree / indirect-site audit")
    print("[K1I] 64 original TrueTU inputs unchanged; NO XDK / Xbox test")
    print("[K1I] Report=" + str(a.out))


if __name__ == "__main__":
    main()

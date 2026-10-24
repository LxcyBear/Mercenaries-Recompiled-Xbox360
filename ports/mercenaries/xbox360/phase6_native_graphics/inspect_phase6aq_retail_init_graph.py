#!/usr/bin/env python3
"""Phase 6AQ-A: trace retail D3D initializer graph 0028FF80 -> 0028F9E0.

6AP recovered the original CreateDevice path:
  sub_0028CAA0 publishes device globals then calls phase4c_direct_frontier(0x0028FF80).
6AO proved sub_0028F9E0 is the sole writer of device+0x1A10.

This PC-only audit walks direct translated/frontier edges from 0x0028FF80,
finds paths to 0x0028F9E0, dumps every function on the shortest path, and flags
hardware-looking absolute guest accesses so the safe guest-object init can be
separated from original Xbox/NV2A work before any hardware patch.
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
from pathlib import Path

PHASE = "6AQ-A"
BASE_TAG = "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A"
ROOT = "sub_0028FF80"
TARGET = "sub_0028F9E0"
MAX_DEPTH = 8
MAX_VISITED = 512

DIRECT_RE = re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(\s*\)")
FRONTIER_RE = re.compile(r"phase4c_direct_frontier\(0x([0-9A-Fa-f]{8})u?\)")
ABS_ACCESS_RE = re.compile(
    r"GUEST_(?:S?READ(?:8|16|32|64|F32)|WRITE(?:8|16|32|64|F32))\(\s*(0x[0-9A-Fa-f]+)"
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AQ] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_functions(text: str, base):
    masked = base.mask_noncode(text)
    funcs = {}
    for m in base.FUNC_RE.finditer(masked):
        brace = masked.find("{", m.start(), m.end())
        if brace < 0:
            continue
        end = base.closing_brace(masked, brace)
        name = m.group(1)
        start_line = text.count("\n", 0, m.start()) + 1
        end_line = text.count("\n", 0, end) + 1
        funcs[name] = {
            "name": name,
            "start": m.start(),
            "end": end,
            "start_line": start_line,
            "end_line": end_line,
            "body": text[m.start():end],
        }
    return funcs


def edges_for(body: str):
    edges = []
    for m in DIRECT_RE.finditer(body):
        name = m.group(1)
        if name not in edges:
            edges.append(name)
    for m in FRONTIER_RE.finditer(body):
        name = "sub_" + m.group(1).upper()
        if name not in edges:
            edges.append(name)
    return edges


def hardware_flags(body: str):
    flags = []
    for i, line in enumerate(body.splitlines(), start=1):
        low = line.lower()
        reasons = []
        for m in ABS_ACCESS_RE.finditer(line):
            try:
                addr = int(m.group(1), 16)
            except ValueError:
                continue
            if addr >= 0x80000000:
                reasons.append(f"absolute_guest_{addr:08X}")
            if 0xFD000000 <= addr <= 0xFFFFFFFF:
                reasons.append(f"nv2a_mmio_like_{addr:08X}")
        if any(tok in low for tok in (
            "nv2a", "mmio", "pushbuffer", "push buffer", "vram",
            "0xfd", "0xfe", "0x80000000", "0x80000",
        )):
            reasons.append("hardware_token")
        if reasons:
            flags.append({
                "relative_line": i,
                "source": line.strip(),
                "reasons": sorted(set(reasons)),
            })
    return flags


def has_stack_writer(body: str):
    needles = (
        "GUEST_WRITE32(esi + 0x1A10",
        "GUEST_WRITE32(ecx + 0x1A10",
        "GUEST_WRITE32(eax + 0x1A10",
        "GUEST_WRITE32(edx + 0x1A10",
    )
    return any(n in body for n in needles)


def numbered(func):
    return [
        f"{func['start_line'] + i:07d}: {line}"
        for i, line in enumerate(func["body"].splitlines())
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    main_path = args.base_dir / "main_monolithic.cpp"
    manifest_path = args.base_dir / "phase6aj-manifest.json"
    if not main_path.exists() or not manifest_path.exists():
        raise SystemExit("[Phase6AQ] cached 6AJ baseline missing")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6AJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AQ] cached 6AJ identity mismatch")

    base = load(args.base_emitter, "phase6aq_base")
    text = main_path.read_text(encoding="utf-8", errors="replace")
    print("[Phase6AQ] Parsing translated functions...", flush=True)
    funcs = extract_functions(text, base)
    print(f"[Phase6AQ] Functions indexed    : {len(funcs)}", flush=True)

    if ROOT not in funcs:
        raise SystemExit(f"[Phase6AQ] root {ROOT} missing")
    if TARGET not in funcs:
        raise SystemExit(f"[Phase6AQ] target {TARGET} missing")

    graph = {}
    queue = collections.deque([(ROOT, 0)])
    parent = {ROOT: None}
    depth_map = {ROOT: 0}
    visit_order = []

    while queue:
        name, depth = queue.popleft()
        if name in graph:
            continue
        if name not in funcs:
            graph[name] = []
            continue
        visit_order.append(name)
        if len(visit_order) > MAX_VISITED:
            raise SystemExit("[Phase6AQ] graph visit cap exceeded")
        body = funcs[name]["body"]
        edges = [e for e in edges_for(body) if e in funcs]
        graph[name] = edges

        if depth < MAX_DEPTH:
            for child in edges:
                if child not in parent:
                    parent[child] = name
                    depth_map[child] = depth + 1
                    queue.append((child, depth + 1))

    path = []
    if TARGET in parent:
        cur = TARGET
        while cur is not None:
            path.append(cur)
            cur = parent[cur]
        path.reverse()

    # Find all visited functions that touch +1A10 or write it.
    related = []
    for name in visit_order:
        body = funcs[name]["body"]
        if "0x1A10" in body or "0x1a10" in body:
            related.append({
                "function": name,
                "depth": depth_map.get(name),
                "writer": has_stack_writer(body),
            })

    path_rows = []
    for name in path:
        f = funcs[name]
        path_rows.append({
            "function": name,
            "depth": depth_map.get(name),
            "range": [f["start_line"], f["end_line"]],
            "edges": graph.get(name, []),
            "hardware_flags": hardware_flags(f["body"]),
            "writes_1A10": has_stack_writer(f["body"]),
            "body": f["body"],
        })

    report = {
        "phase": PHASE,
        "baseline": BASE_TAG,
        "root": ROOT,
        "target": TARGET,
        "visited": len(visit_order),
        "target_reached": bool(path),
        "shortest_path": path,
        "path_length_edges": max(0, len(path) - 1),
        "related_1A10_functions": related,
        "path_functions": path_rows,
        "graph": graph,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "phase6aq-0028ff80-to-0028f9e0.json"
    txt_path = args.out_dir / "phase6aq-0028ff80-to-0028f9e0.txt"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    out = []
    out.append("Phase 6AQ-A retail D3D initializer graph")
    out.append(f"baseline={BASE_TAG}")
    out.append(f"root={ROOT} target={TARGET} visited={len(visit_order)} reached={int(bool(path))}")
    out.append("path=" + (" -> ".join(path) if path else "<not reached>"))
    out.append("")
    out.append("+1A10 RELATED FUNCTIONS")
    for row in related:
        out.append(
            f"{row['function']} depth={row['depth']} writer={int(row['writer'])}"
        )
    out.append("")
    out.append("SHORTEST PATH FUNCTIONS")
    for row in path_rows:
        out.append(
            f"===== {row['function']} depth={row['depth']} "
            f"range={row['range'][0]}..{row['range'][1]} "
            f"writes_1A10={int(row['writes_1A10'])} ====="
        )
        out.append("edges=" + (",".join(row["edges"]) or "<none>"))
        if row["hardware_flags"]:
            out.append("hardware_flags:")
            for h in row["hardware_flags"]:
                out.append(
                    f"  relL{h['relative_line']}: {','.join(h['reasons'])} :: {h['source']}"
                )
        else:
            out.append("hardware_flags=<none>")
        out.extend(numbered(funcs[row["function"]]))
        out.append("===== END =====")
        out.append("")
    txt_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    print("[Phase6AQ] RETAIL INIT GRAPH AUDIT: PASS")
    print(f"[Phase6AQ] visited             : {len(visit_order)}")
    print(f"[Phase6AQ] target reached      : {'YES' if path else 'NO'}")
    print(f"[Phase6AQ] shortest path       : {' -> '.join(path) if path else '<none>'}")
    print(f"[Phase6AQ] report              : {txt_path}")
    print("[Phase6AQ] NO BUILD BY DESIGN")
    print("[Phase6AQ] PATH SUMMARY BEGIN")
    if path:
        for row in path_rows:
            print(
                f"[Phase6AQ] | {row['function']} depth={row['depth']} "
                f"range={row['range'][0]}..{row['range'][1]} "
                f"writes_1A10={int(row['writes_1A10'])} "
                f"hardware_flags={len(row['hardware_flags'])}"
            )
            print(
                f"[Phase6AQ] |   edges={','.join(row['edges']) or '<none>'}"
            )
            for h in row["hardware_flags"][:20]:
                print(
                    f"[Phase6AQ] |   HW relL{h['relative_line']}: "
                    f"{','.join(h['reasons'])} :: {h['source']}"
                )
    else:
        print("[Phase6AQ] | target not reached within bounded direct/frontier graph")
    print("[Phase6AQ] PATH SUMMARY END")
    print("[Phase6AQ] PATH BODIES BEGIN")
    for row in path_rows:
        print(f"[Phase6AQ] BODY {row['function']} BEGIN")
        for line in numbered(funcs[row["function"]]):
            print(f"[Phase6AQ] | {line}")
        print(f"[Phase6AQ] BODY {row['function']} END")
    print("[Phase6AQ] PATH BODIES END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

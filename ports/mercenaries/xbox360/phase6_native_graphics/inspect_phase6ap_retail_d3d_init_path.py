#!/usr/bin/env python3
"""Phase 6AP-A: recover the retail D3D initializer path bypassed by 6AF.

6AO proved the only +0x1A10 writer is sub_0028F9E0 and that no ordinary
translated direct call to it is present in the current packed source. This
PC-only audit:
  1) dumps the full current sub_0028F9E0 body and its call/ICALL surface;
  2) finds every textual/literal reference to 0028F9E0 in the current source;
  3) scans cached Phase-6 monolithic sources for sub_0028CAA0 and records each
     distinct body so the pre-6AF retail CreateDevice implementation can be
     compared with the later native handoff;
  4) highlights any cached 0028CAA0 body that references/calls 0028F9E0.

No generated source is modified and no XEX is built.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

PHASE = "6AP-A"
BASE_TAG = "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A"
INIT_FUNC = "sub_0028F9E0"
CREATE_FUNC = "sub_0028CAA0"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AP] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_definition(text: str, base, signature: str):
    masked = base.mask_noncode(text)
    hits = []
    pos = 0
    while True:
        p = masked.find(signature, pos)
        if p < 0:
            break
        q = p + len(signature)
        while q < len(masked) and masked[q].isspace():
            q += 1
        if q < len(masked) and masked[q] == "{":
            end = base.closing_brace(masked, q)
            hits.append((p, end))
        pos = p + len(signature)
    if len(hits) != 1:
        return None
    p, end = hits[0]
    return text[p:end]


def line_number(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def numbered(body: str, base_line: int) -> list[str]:
    return [
        f"{base_line + i:07d}: {line}"
        for i, line in enumerate(body.splitlines())
    ]


def calls_in(body: str) -> dict:
    direct = []
    for m in re.finditer(r"\b(sub_[0-9A-Fa-f]{8})\s*\(\s*\)", body):
        name = m.group(1)
        if name not in direct:
            direct.append(name)
    icalls = []
    for line in body.splitlines():
        if "RECOMP_ICALL_SAFE" in line:
            s = line.strip()
            if s not in icalls:
                icalls.append(s)
    return {"direct": direct, "icalls": icalls}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--current-dir", type=Path, required=True)
    ap.add_argument("--phase6-build-root", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    current_main = args.current_dir / "main_monolithic.cpp"
    current_manifest = args.current_dir / "phase6aj-manifest.json"
    if not current_main.exists() or not current_manifest.exists():
        raise SystemExit("[Phase6AP] current 6AJ baseline missing")

    manifest = json.loads(current_manifest.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6AJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AP] current 6AJ identity mismatch")

    base = load(args.base_emitter, "phase6ap_base")
    current_text = current_main.read_text(encoding="utf-8", errors="replace")

    init_sig = f"static void {INIT_FUNC}(void)"
    init_body = extract_definition(current_text, base, init_sig)
    if init_body is None:
        raise SystemExit(f"[Phase6AP] could not uniquely extract {INIT_FUNC}")
    init_pos = current_text.find(init_body)
    init_line = line_number(current_text, init_pos)
    init_calls = calls_in(init_body)

    # Current-source refs outside the definition itself.
    current_refs = []
    needles = [INIT_FUNC, "0x0028F9E0", "0x28F9E0", "0028F9E0u", "0028F9E0"]
    for i, line in enumerate(current_text.splitlines(), start=1):
        if any(n.lower() in line.lower() for n in needles):
            in_def = init_line <= i < init_line + len(init_body.splitlines())
            current_refs.append({
                "line": i,
                "inside_definition": in_def,
                "source": line.strip(),
            })

    # Scan every cached Phase-6 monolithic-ish source for the retail CreateDevice body.
    candidates = []
    seen_files = set()
    patterns = ("main_monolithic.cpp", "main.cpp")
    paths = []
    for pattern in patterns:
        paths.extend(args.phase6_build_root.rglob(pattern))
    paths = sorted(set(paths))

    print(f"[Phase6AP] Cache sources       : {len(paths)} candidate cpp files", flush=True)

    for idx, path in enumerate(paths, start=1):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Sharded wrapper main.cpp often has only includes; skip cheaply.
        if CREATE_FUNC not in text:
            if idx % 25 == 0 or idx == len(paths):
                print(f"[Phase6AP] Cache progress      : {idx}/{len(paths)}", flush=True)
            continue

        body = extract_definition(text, base, f"static void {CREATE_FUNC}(void)")
        if body is None:
            if idx % 25 == 0 or idx == len(paths):
                print(f"[Phase6AP] Cache progress      : {idx}/{len(paths)}", flush=True)
            continue

        resolved = str(path.resolve())
        if resolved in seen_files:
            continue
        seen_files.add(resolved)

        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        body_calls = calls_in(body)
        references_init = (
            INIT_FUNC in body
            or "0x0028F9E0" in body
            or "0x28F9E0" in body
            or "0028F9E0" in body
        )
        bridge_markers = [
            m for m in (
                "phase6af",
                "CreateDevice handoff",
                "s_phase6afCreateDeviceBridgeCount",
                "phase6af_native_xenos_ready",
                "P6AF",
            )
            if m.lower() in body.lower()
        ]

        candidates.append({
            "path": resolved,
            "relative": str(path.relative_to(args.phase6_build_root)),
            "sha256": digest,
            "chars": len(body),
            "lines": len(body.splitlines()),
            "references_0028f9e0": references_init,
            "bridge_markers": bridge_markers,
            "calls": body_calls,
            "body": body,
            "base_line": line_number(text, text.find(body)),
        })

        if idx % 25 == 0 or idx == len(paths):
            print(f"[Phase6AP] Cache progress      : {idx}/{len(paths)}", flush=True)

    # Group distinct bodies; identical bodies across later phases are one semantic candidate.
    groups = {}
    for row in candidates:
        groups.setdefault(row["sha256"], []).append(row)

    distinct = []
    for digest, rows in groups.items():
        exemplar = rows[0]
        distinct.append({
            "sha256": digest,
            "occurrences": len(rows),
            "paths": [r["relative"] for r in rows],
            "chars": exemplar["chars"],
            "lines": exemplar["lines"],
            "references_0028f9e0": exemplar["references_0028f9e0"],
            "bridge_markers": exemplar["bridge_markers"],
            "calls": exemplar["calls"],
            "body": exemplar["body"],
            "base_line": exemplar["base_line"],
        })
    distinct.sort(key=lambda r: (bool(r["bridge_markers"]), -r["chars"], r["sha256"]))

    retail_like = [
        r for r in distinct
        if not r["bridge_markers"]
    ]
    bridge_like = [
        r for r in distinct
        if r["bridge_markers"]
    ]

    report = {
        "phase": PHASE,
        "baseline": BASE_TAG,
        "initializer": {
            "function": INIT_FUNC,
            "line": init_line,
            "calls": init_calls,
            "body": init_body,
        },
        "current_initializer_refs": current_refs,
        "create_device_cache_candidates": len(candidates),
        "create_device_distinct_bodies": len(distinct),
        "retail_like_bodies": len(retail_like),
        "bridge_like_bodies": len(bridge_like),
        "distinct_create_device_bodies": distinct,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "phase6ap-retail-d3d-init-path.json"
    txt_path = args.out_dir / "phase6ap-retail-d3d-init-path.txt"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    out = []
    out.append("Phase 6AP-A retail D3D initializer path audit")
    out.append(f"baseline={BASE_TAG}")
    out.append(
        f"initializer={INIT_FUNC} line={init_line} "
        f"direct_calls={len(init_calls['direct'])} icalls={len(init_calls['icalls'])}"
    )
    out.append(
        f"create_device_candidates={len(candidates)} "
        f"distinct_bodies={len(distinct)} retail_like={len(retail_like)} "
        f"bridge_like={len(bridge_like)}"
    )
    out.append("")
    out.append("CURRENT REFERENCES TO 0028F9E0")
    for row in current_refs:
        out.append(
            f"L{row['line']} inside_init={int(row['inside_definition'])} {row['source']}"
        )
    out.append("")
    out.append("FULL sub_0028F9E0")
    out.extend(numbered(init_body, init_line))
    out.append("")
    out.append("DISTINCT sub_0028CAA0 BODIES")
    for n, row in enumerate(distinct, start=1):
        out.append(
            f"===== BODY {n} sha={row['sha256'][:16]} occurrences={row['occurrences']} "
            f"retail_like={int(not bool(row['bridge_markers']))} "
            f"refs_0028F9E0={int(row['references_0028f9e0'])} "
            f"lines={row['lines']} ====="
        )
        out.append("paths=" + " | ".join(row["paths"][:12]))
        out.append("bridge_markers=" + (",".join(row["bridge_markers"]) or "<none>"))
        out.append("direct_calls=" + (",".join(row["calls"]["direct"]) or "<none>"))
        out.append("icalls=" + (" | ".join(row["calls"]["icalls"]) or "<none>"))
        out.extend(numbered(row["body"], row["base_line"]))
        out.append("===== END BODY =====")
        out.append("")
    txt_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    print("[Phase6AP] RETAIL D3D INIT PATH AUDIT: PASS")
    print(f"[Phase6AP] initializer           : {INIT_FUNC}")
    print(f"[Phase6AP] current refs          : {len(current_refs)}")
    print(f"[Phase6AP] cached 0028CAA0      : {len(candidates)}")
    print(f"[Phase6AP] distinct 0028CAA0    : {len(distinct)}")
    print(f"[Phase6AP] retail-like bodies   : {len(retail_like)}")
    print(f"[Phase6AP] bridge-like bodies   : {len(bridge_like)}")
    print(f"[Phase6AP] report               : {txt_path}")
    print("[Phase6AP] NO BUILD BY DESIGN")
    print("[Phase6AP] INIT CALL SURFACE BEGIN")
    for name in init_calls["direct"]:
        print(f"[Phase6AP] | direct {name}")
    for line in init_calls["icalls"]:
        print(f"[Phase6AP] | icall {line}")
    print("[Phase6AP] INIT CALL SURFACE END")
    print("[Phase6AP] CREATEDEVICE BODY SUMMARY BEGIN")
    for n, row in enumerate(distinct, start=1):
        print(
            f"[Phase6AP] | body={n} retail_like={int(not bool(row['bridge_markers']))} "
            f"refs_0028F9E0={int(row['references_0028f9e0'])} "
            f"lines={row['lines']} occurrences={row['occurrences']} "
            f"sha={row['sha256'][:16]}"
        )
        print(f"[Phase6AP] | paths={' | '.join(row['paths'][:8])}")
        print(f"[Phase6AP] | direct_calls={','.join(row['calls']['direct']) or '<none>'}")
        print(f"[Phase6AP] | bridge_markers={','.join(row['bridge_markers']) or '<none>'}")
    print("[Phase6AP] CREATEDEVICE BODY SUMMARY END")
    print("[Phase6AP] RETAIL-LIKE CREATEDEVICE BODIES BEGIN")
    for n, row in enumerate(distinct, start=1):
        if row["bridge_markers"]:
            continue
        print(f"[Phase6AP] BODY {n} BEGIN")
        for line in numbered(row["body"], row["base_line"]):
            print(f"[Phase6AP] | {line}")
        print(f"[Phase6AP] BODY {n} END")
    print("[Phase6AP] RETAIL-LIKE CREATEDEVICE BODIES END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

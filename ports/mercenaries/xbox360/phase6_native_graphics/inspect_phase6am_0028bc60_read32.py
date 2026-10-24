#!/usr/bin/env python3
"""Phase 6AM-A: resolve the 6AL hardware READ32 site to exact generated source.

Hardware 6AL-A proved the orange READ32 0x80000004 was issued while the
translated-function latch was 0x0028BC60 and __LINE__ was 1957. This inspector
reads the cached 6AL translated shards, finds sub_0028BC60, verifies that shard
line 1957 lies inside it, and prints the exact source neighborhood plus the
full function. No source is modified and no XEX is built.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

PHASE = "6AM-A"
BASE_TAG = "P6AL-READ32-SITE-PROBE-20261023-A"
TARGET_FUNC = "sub_0028BC60"
TARGET_VA = "0x0028BC60"
TARGET_LINE = 1957
TARGET_ADDRESS = "0x80000004"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AM] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def numbered(lines: list[str], start: int, end: int) -> list[str]:
    start = max(1, start)
    end = min(len(lines), end)
    return [f"{i:05d}: {lines[i - 1]}" for i in range(start, end + 1)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    manifest_path = args.base_dir / "phase6al-manifest.json"
    shard_dir = args.base_dir / "translated_shards"
    if not manifest_path.exists():
        raise SystemExit(f"[Phase6AM] missing 6AL manifest: {manifest_path}")
    if not shard_dir.is_dir():
        raise SystemExit(f"[Phase6AM] missing 6AL shard directory: {shard_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6AL" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AM] cached Phase 6AL-A baseline identity mismatch")

    al = manifest.get("phase6al_read32_site_probe") or {}
    if not al.get("probe_only") or al.get("guest_memory_semantics_changed"):
        raise SystemExit("[Phase6AM] Phase 6AL probe model drift")

    base = load(args.base_emitter, "phase6am_base")

    hits: list[Path] = []
    marker = f"static void {TARGET_FUNC}(void)"
    alt_marker = "const DWORD phase6al_function_va = 0x0028BC60u;"
    for path in sorted(shard_dir.glob("phase6al_*.inl")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if marker in text or alt_marker in text:
            hits.append(path)

    if len(hits) != 1:
        raise SystemExit(
            f"[Phase6AM] expected one shard containing {TARGET_FUNC}, found {len(hits)}"
        )

    shard = hits[0]
    text = shard.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if TARGET_LINE < 1 or TARGET_LINE > len(lines):
        raise SystemExit(
            f"[Phase6AM] hardware line {TARGET_LINE} outside {shard.name} "
            f"(lines={len(lines)})"
        )

    masked = base.mask_noncode(text)
    sig_pos = masked.find(marker)
    if sig_pos < 0:
        raise SystemExit(f"[Phase6AM] {TARGET_FUNC} definition missing in {shard.name}")
    brace = masked.find("{", sig_pos, sig_pos + len(marker) + 16)
    if brace < 0:
        raise SystemExit("[Phase6AM] target function opening brace missing")
    func_end = base.closing_brace(masked, brace)

    func_start_line = text.count("\n", 0, sig_pos) + 1
    func_end_line = text.count("\n", 0, func_end) + 1
    if not (func_start_line <= TARGET_LINE <= func_end_line):
        raise SystemExit(
            f"[Phase6AM] hardware line {TARGET_LINE} is not inside {TARGET_FUNC}: "
            f"{func_start_line}..{func_end_line}"
        )

    target_source = lines[TARGET_LINE - 1]
    window = numbered(lines, TARGET_LINE - 32, TARGET_LINE + 32)
    function_lines = numbered(lines, func_start_line, func_end_line)

    read32_lines = []
    suspicious_lines = []
    for i in range(func_start_line, func_end_line + 1):
        src = lines[i - 1]
        if "GUEST_READ32" in src:
            read32_lines.append({"line": i, "source": src})
        if any(token in src for token in (
            "80000000", "0x80000000", "eax + 4", "eax+4",
            "ecx + 4", "ecx+4", "+ 4)", "+ 4u)",
        )):
            suspicious_lines.append({"line": i, "source": src})

    exact_has_read = "GUEST_READ32" in target_source
    exact_has_plus4 = bool(re.search(r"\+\s*(?:4|0x4|4u|0x4u)\b", target_source))
    exact_regs = sorted(set(re.findall(r"\b(?:eax|ecx|edx|ebx|esi|edi|esp|ebp)\b", target_source)))

    report = {
        "phase": PHASE,
        "baseline": BASE_TAG,
        "hardware": {
            "fault": "READ32 0x80000004",
            "function": TARGET_VA,
            "line": TARGET_LINE,
        },
        "shard": shard.name,
        "shard_lines": len(lines),
        "function": TARGET_FUNC,
        "function_start_line": func_start_line,
        "function_end_line": func_end_line,
        "exact_source": target_source,
        "exact_has_guest_read32": exact_has_read,
        "exact_has_plus4": exact_has_plus4,
        "exact_register_tokens": exact_regs,
        "read32_lines": read32_lines,
        "suspicious_lines": suspicious_lines,
        "window": window,
        "function_source": function_lines,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = args.out_dir / "phase6am-0028bc60-read32-site.txt"
    json_path = args.out_dir / "phase6am-0028bc60-read32-site.json"

    txt = []
    txt.append(f"Phase {PHASE} exact READ32 source forensic")
    txt.append(f"baseline={BASE_TAG}")
    txt.append(f"hardware=READ32 0x80000004 func={TARGET_VA} line={TARGET_LINE}")
    txt.append(f"shard={shard.name}")
    txt.append(
        f"function={TARGET_FUNC} range={func_start_line}..{func_end_line} "
        f"read32_lines={len(read32_lines)}"
    )
    txt.append(f"exact={target_source}")
    txt.append("")
    txt.append("EXACT SITE WINDOW")
    txt.extend(window)
    txt.append("")
    txt.append("FULL TARGET FUNCTION")
    txt.extend(function_lines)
    txt.append("")
    txt.append("READ32 LINES")
    for row in read32_lines:
        txt.append(f"{row['line']:05d}: {row['source']}")
    txt_path.write_text("\n".join(txt) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("[Phase6AM] EXACT 0028BC60 READ32 SOURCE: PASS")
    print(f"[Phase6AM] Shard          : {shard.name}")
    print(
        f"[Phase6AM] Function range : {func_start_line}..{func_end_line} "
        f"(hardware line {TARGET_LINE})"
    )
    print(f"[Phase6AM] Exact source   : {target_source}")
    print(f"[Phase6AM] GUEST_READ32   : {'YES' if exact_has_read else 'NO'}")
    print(f"[Phase6AM] +4 expression  : {'YES' if exact_has_plus4 else 'NO'}")
    print(f"[Phase6AM] Registers      : {','.join(exact_regs) if exact_regs else '<none>'}")
    print(f"[Phase6AM] Report         : {txt_path}")
    print("[Phase6AM] NO BUILD BY DESIGN")
    print("[Phase6AM] EXACT SITE WINDOW BEGIN")
    for row in window:
        print(f"[Phase6AM] | {row}")
    print("[Phase6AM] EXACT SITE WINDOW END")
    print("[Phase6AM] TARGET FUNCTION BEGIN")
    for row in function_lines:
        print(f"[Phase6AM] | {row}")
    print("[Phase6AM] TARGET FUNCTION END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

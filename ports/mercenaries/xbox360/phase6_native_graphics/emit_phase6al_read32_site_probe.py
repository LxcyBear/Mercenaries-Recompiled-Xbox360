#!/usr/bin/env python3
"""Phase 6AL-A: exact translated READ32 call-site probe.

6AJ hardware proved sub_0028E700 reaches its return path before the orange
READ32 0x80000004 boundary. 6AK then proved the deferred boundary caller
(0x0023A3CE) does not directly mention/call sub_0028E700, so the last-traced
caller is not precise enough to identify the failing instruction.

This diagnostic build wraps translated GUEST_READ32 call sites only. If the
checked guest-memory helper latches a fault, the wrapper logs the exact
translated function VA + generated site id + address + live registers and
escapes immediately, before later translated instructions can overwrite useful
context. Guest memory routing, KSEG fences, D3D state, MMIO/VRAM behavior and
the actual read semantics remain unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A"
BUILD_TAG = "P6AL-READ32-SITE-PROBE-20261023-A"
COOKIE_OLD = "phase6aj_env_build_cookie"
COOKIE_NEW = "phase6al_env_build_cookie"
SHARD_TARGET_CHARS = 750000

TRACE_RE = re.compile(r"RECOMP_TRACE_FUNC\s*\(\s*0x([0-9A-Fa-f]{8})u?\s*\)")
READ32_RE = re.compile(r"\bGUEST_READ32\s*\(")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AL] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AL] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AL] runtime Policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AL] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return text[:line_start] + indent + 'trace("' + policy + '");' + text[line_end:]


def matching_paren(masked: str, open_index: int) -> int:
    depth = 0
    for i in range(open_index, len(masked)):
        ch = masked[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    raise SystemExit(f"[Phase6AL] unterminated GUEST_READ32 at offset {open_index}")


def translated_bounds(main_text: str) -> tuple[int, int]:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AL] optimize-off marker missing")
    start = off_pos + len(off_marker)
    end = main_text.find(on_marker, start)
    if end < 0:
        raise SystemExit("[Phase6AL] optimize-on marker missing")
    return start, end


def instrument_translated_read32(main_text: str, base) -> tuple[str, list[dict]]:
    """Instrument READ32s without rewriting individual expressions.

    Nested GUEST_READ32 calls make source-range replacement ambiguous. Instead,
    give every translated function a local phase6al_function_va and temporarily
    redefine GUEST_READ32 across the translated body. The preprocessor then
    handles nested expressions naturally.
    """
    body_start, body_end = translated_bounds(main_text)
    body = main_text[body_start:body_end]
    masked = base.mask_noncode(body)
    funcs = list(base.FUNC_RE.finditer(masked))
    if not funcs:
        raise SystemExit("[Phase6AL] translated body contains no functions")

    insertions: list[tuple[int, str]] = []
    rows: list[dict] = []
    total_reads = 0

    for match in funcs:
        brace = masked.find("{", match.start(), match.end())
        if brace < 0:
            raise SystemExit("[Phase6AL] translated function opening brace missing")
        func_end = base.closing_brace(masked, brace)
        func_source = body[match.start():func_end]
        func_masked = masked[match.start():func_end]
        read_count = len(READ32_RE.findall(func_masked))

        trace_match = TRACE_RE.search(func_masked)
        if trace_match:
            function_va = int(trace_match.group(1), 16)
        else:
            name = match.group(1)
            m = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
            if not m:
                raise SystemExit(
                    f"[Phase6AL] translated function has no recoverable VA: {name}"
                )
            function_va = int(m.group(1), 16)

        # Insert immediately after the opening brace. Every GUEST_READ32 in
        # this translated function can then reference the local VA, including
        # nested reads on the same source line.
        insertions.append(
            (
                brace + 1,
                f"\n    const DWORD phase6al_function_va = 0x{function_va:08X}u;"
            )
        )
        rows.append(
            {
                "function": f"0x{function_va:08X}",
                "literal_read32_count": read_count,
            }
        )
        total_reads += read_count

    if total_reads == 0:
        raise SystemExit("[Phase6AL] no translated GUEST_READ32 call sites found")

    pieces: list[str] = []
    cursor = 0
    for pos, payload in sorted(insertions):
        if pos < cursor:
            raise SystemExit("[Phase6AL] overlapping function-VA insertions")
        pieces.append(body[cursor:pos])
        pieces.append(payload)
        cursor = pos
    pieces.append(body[cursor:])
    body = "".join(pieces)

    # Limit the macro override strictly to translated code. The wrapper calls
    # recomp_guest_read32 directly, so there is no recursive macro expansion.
    prefix = (
        "#undef GUEST_READ32\n"
        "#define GUEST_READ32(addr) "
        "phase6al_read32_site(phase6al_function_va, (DWORD)__LINE__, "
        "(uint32_t)(addr))\n"
    )
    suffix = (
        "\n#undef GUEST_READ32\n"
        "#define GUEST_READ32(addr) recomp_guest_read32((uint32_t)(addr))\n"
    )
    body = prefix + body + suffix

    rows.insert(
        0,
        {
            "instrumented_read32_sites": total_reads,
            "instrumented_functions": len(insertions),
            "literal_read32_sites": total_reads,
            "macro_scope": "all translated GUEST_READ32 expansions",
            "site_identity": "translated function VA + compiler __LINE__",
        },
    )
    return main_text[:body_start] + body + main_text[body_end:], rows

def install_site_support(main_text: str) -> str:
    marker = '#pragma optimize("", off)\n'
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6AL] optimize-off insertion marker missing")

    block = r'''
static DWORD s_phase6alRead32Function = 0u;
static DWORD s_phase6alRead32Line = 0u;
static DWORD s_phase6alRead32Address = 0u;
static DWORD s_phase6alRead32Hits = 0u;

static uint32_t phase6al_read32_site(
    DWORD functionVa,
    DWORD sourceLine,
    uint32_t address)
{
    uint32_t value;

    s_phase6alRead32Function = functionVa;
    s_phase6alRead32Line = sourceLine;
    s_phase6alRead32Address = address;
    ++s_phase6alRead32Hits;

    /* Call the checked helper directly. Do not recurse through GUEST_READ32. */
    value = recomp_guest_read32(address);

    if (s_accessFault)
    {
        char line[256];
        sprintf(
            line,
            "P6AL READ32 FAULT SITE: func=%08X line=%u address=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
            (unsigned int)functionVa,
            (unsigned int)sourceLine,
            (unsigned int)address,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)ebx,
            (unsigned int)esi,
            (unsigned int)edi,
            (unsigned int)esp);
        trace(line);

        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            address,
            g_esp);
    }

    return value;
}

'''
    return main_text[:pos] + block + main_text[pos:]

def install_summary(main_text: str, site_count: int) -> str:
    marker = "P6AJ D3D SOURCE PROBE:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6AL] inherited 6AJ summary marker missing")
    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 4000:
        raise SystemExit("[Phase6AL] could not locate inherited 6AJ summary")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6AL READ32 SITE PROBE: calls=%u last_func=%08X last_line=%u last_address=%08X instrumented={site_count}",\n'
        f'{indent}    (unsigned int)s_phase6alRead32Hits,\n'
        f'{indent}    (unsigned int)s_phase6alRead32Function,\n'
        f'{indent}    (unsigned int)s_phase6alRead32Line,\n'
        f'{indent}    (unsigned int)s_phase6alRead32Address);\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + block + main_text[line_start:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    body_start, body_end = translated_bounds(main_text)
    body = main_text[body_start:body_end]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AL] translated body contains no functions")

    ends = []
    for match in matches:
        brace = masked.find("{", match.start(), match.end())
        if brace < 0:
            raise SystemExit("[Phase6AL] translated function opening brace missing")
        ends.append(base.closing_brace(masked, brace))

    cuts = []
    chunk_start = 0
    last_end = 0
    for end in ends:
        last_end = end
        if end - chunk_start >= SHARD_TARGET_CHARS:
            cuts.append(end)
            chunk_start = end
    if last_end < len(body):
        last_end = len(body)
    if not cuts or cuts[-1] != last_end:
        cuts.append(last_end)

    shard_dir = out_dir / "translated_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale in shard_dir.glob("*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cuts):
        if end <= start:
            continue
        name = f"phase6al_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append(
            {
                "name": name,
                "chars": len(payload),
                "lines": payload.count("\n") + 1,
            }
        )
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AL] shard writer did not consume translated body")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n' for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[body_end:]
    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8")
        for row in shards
    )
    if reconstructed != body:
        raise SystemExit("[Phase6AL] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6al_",
        "shard_count": len(shards),
        "shards": shards,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6aj-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AL] cached Phase 6AJ-A baseline missing: {path}")

    base = load(args.base_emitter, "phase6al_base")
    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AL] cached Phase 6AJ-A baseline identity mismatch")

    aj = manifest.get("phase6aj_d3d_orange_source_probe") or {}
    if (
        aj.get("probe_only") is not True
        or aj.get("guest_semantics_changed") is not False
        or aj.get("phase6ai_hardware", {}).get("next_boundary", {}).get("guest")
           != "0x80000004"
    ):
        raise SystemExit("[Phase6AL] inherited Phase 6AJ model drift")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6AJ D3D FAULT PROBE: step=%u a=%08X b=%08X c=%08X",
        "s_phase6ajD3DProbeStep = 10u;",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6AL] inherited marker missing: {marker}")

    main_text, sites = instrument_translated_read32(main_text, base)
    instrumented_read32_sites = int(sites[0]["instrumented_read32_sites"])
    main_text = install_site_support(main_text)
    main_text = install_summary(main_text, instrumented_read32_sites)

    policy = (
        "Policy: inherit 6AJ-A; wrap translated READ32 sites and escape on the "
        "first latched fault; preserve guest routing, KSEG, D3D, NV2A/MMIO/VRAM "
        "and ABI semantics"
    )
    if len(policy) > 240:
        raise SystemExit("[Phase6AL] startup policy trace exceeds safe length")
    main_text = replace_policy_line(main_text, policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = main_text.replace("PHASE 6AJ", "PHASE 6AL").replace(
        "Phase 6AJ", "Phase 6AL"
    )
    env_text = env_text.replace("PHASE 6AJ", "PHASE 6AL").replace(
        "Phase 6AJ", "Phase 6AL"
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "P6AL READ32 FAULT SITE:",
        "phase6al_read32_site(",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6AL] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    site_map_txt = args.out_dir / "phase6al-read32-site-map.txt"
    site_map_json = args.out_dir / "phase6al-read32-site-map.json"
    site_map_txt.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in sites) + "\n",
        encoding="utf-8",
    )
    site_map_json.write_text(json.dumps(sites, indent=2) + "\n", encoding="utf-8")

    manifest.update({"phase": "6AL", "build_tag": BUILD_TAG})
    manifest["phase6al_read32_site_probe"] = {
        "source_phase": "6AJ",
        "phase6aj_hardware": {
            "probe_step": 10,
            "fault": "READ32 0x80000004",
            "deferred_boundary_caller": "0x0023A3CE",
        },
        "phase6ak_forensic": {
            "result": "PASS",
            "root_mentions_in_0023a3ce": 0,
            "direct_calls_in_0023a3ce": 0,
            "interpretation": "deferred caller is not an exact direct-call source",
        },
        "probe_only": True,
        "guest_memory_semantics_changed": False,
        "boundary_timing_changed": True,
        "instrumented_read32_sites": instrumented_read32_sites,
        "site_map_txt": site_map_txt.name,
        "site_map_json": site_map_json.name,
        "source_layout": layout,
    }
    (args.out_dir / "phase6al-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print("[Phase6AL] EXACT READ32 SITE PROBE: READY")
    print(f"[Phase6AL] Instrumented translated READ32 sites: {instrumented_read32_sites}")
    print("[Phase6AL] Guest-memory/KSEG/D3D/MMIO/VRAM semantics unchanged")
    print("[Phase6AL] Boundary timing: immediate escape after first latched READ32 fault")
    print(f"[Phase6AL] Site map: {site_map_txt}")
    print("[Phase6AL] Hardware money line: P6AL READ32 FAULT SITE: func=... line=... address=...")
    print("[Phase6AL] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

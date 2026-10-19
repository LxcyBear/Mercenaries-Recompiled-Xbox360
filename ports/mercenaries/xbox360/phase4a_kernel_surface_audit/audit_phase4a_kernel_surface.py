#!/usr/bin/env python3
"""Phase 4A: exact Mercenaries guest-kernel/platform surface audit.

The translated game does not call xbox_resolve_ordinal() directly. Its real
runtime boundary is kernel_bridge.c: data exports are installed into guest
memory, callable exports are routed through bridge_for_ordinal(), and
kernel_thunk_dispatch() applies x86 callee stack cleanup. Audit that path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

_REPO_FROM_SCRIPT = Path(__file__).resolve().parents[4]
if str(_REPO_FROM_SCRIPT) not in sys.path:
    sys.path.insert(0, str(_REPO_FROM_SCRIPT))

from tools.xbe_parser.xbe_parser import XBEParser

EXPECTED_XBE_SHA256 = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
EXPECTED_TITLE_ID = 0x4C410015
EXPECTED_IMPORT_COUNT = 111

HOST_SURFACE_TOKENS = (
    "CreateFileW", "CreateFileA", "ReadFile", "WriteFile", "CloseHandle",
    "CreateThread", "ExitThread", "CreateEvent", "CreateEventW", "SetEvent",
    "ResetEvent", "CreateSemaphore", "CreateSemaphoreW", "ReleaseSemaphore",
    "CreateMutex", "CreateMutexW", "ReleaseMutex",
    "WaitForSingleObject", "WaitForSingleObjectEx",
    "WaitForMultipleObjects", "WaitForMultipleObjectsEx",
    "CreateTimerQueue", "CreateTimerQueueTimer", "DeleteTimerQueueTimer",
    "TrySubmitThreadpoolCallback",
    "VirtualAlloc", "VirtualFree", "VirtualProtect", "VirtualQuery",
    "HeapAlloc", "HeapFree", "GetProcessHeap",
    "GetFileAttributesW", "SetFilePointer", "SetFilePointerEx",
    "GetFileInformationByHandle", "GetDiskFreeSpaceEx", "FindFirstFile",
    "FindFirstFileW", "FindNextFile", "FindNextFileW", "FindClose",
    "InitializeCriticalSection", "DeleteCriticalSection",
    "EnterCriticalSection", "LeaveCriticalSection",
    "QueryPerformanceCounter", "QueryPerformanceFrequency",
    "GetSystemTimeAsFileTime", "GetLocalTime", "GetTickCount", "GetTickCount64",
    "Sleep", "WideCharToMultiByte", "MultiByteToWideChar",
    "GetLastError", "SetLastError", "ExitProcess", "DebugBreak",
)

# Logging/diagnostic helpers are a shared platform concern, not semantic
# dependencies of every guest kernel import that emits a trace message.
HOST_SURFACE_DIAGNOSTIC_HELPERS = {
    "xbox_log",
}

PHASE4B_PLATFORM_CALL = re.compile(r"\b(merc_platform_[A-Za-z0-9_]+)\s*\(")


def host_api_calls(masked_body: str) -> list[str]:
    """Return actual host API call expressions, not identifier substrings."""
    return [
        token
        for token in HOST_SURFACE_TOKENS
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(token) + r"\s*\(", masked_body)
    ]


def mask_noncode(text: str) -> str:
    out = list(text)
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            if j < 0:
                j = n
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n - 2 if j < 0 else j
            end = min(n, j + 2)
            for k in range(i, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end
            continue
        if text[i] in ('"', "'"):
            quote = text[i]
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    j += 1
                    break
                j += 1
            for k in range(i, min(j, n)):
                if out[k] != "\n":
                    out[k] = " "
            i = j
            continue
        i += 1
    return "".join(out)


def extract_braced_body(text: str, brace_pos: int) -> str | None:
    depth = 0
    i = brace_pos
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[brace_pos:i + 1]
        i += 1
    return None


def named_function_body(text: str, marker: str) -> str:
    masked = mask_noncode(text)
    start = masked.find(marker)
    if start < 0:
        raise SystemExit(f"[Phase4A] could not find {marker}")
    brace = masked.find("{", start)
    body = extract_braced_body(masked, brace)
    if body is None:
        raise SystemExit(f"[Phase4A] could not parse {marker}")
    return body


def resolver_map(thunks_text: str) -> dict[int, str]:
    body = named_function_body(thunks_text, "ULONG_PTR xbox_resolve_ordinal")
    result: dict[int, str] = {}
    for m in re.finditer(
        r"case\s+(\d+)\s*:\s*return\s*\(ULONG_PTR\)\s*([^;]+);", body
    ):
        result[int(m.group(1))] = m.group(2).strip()
    return result


def bridge_map(bridge_text: str) -> dict[int, str]:
    body = named_function_body(bridge_text, "static bridge_func_t bridge_for_ordinal")
    result: dict[int, str] = {}
    for m in re.finditer(r"case\s+(\d+)\s*:\s*return\s+(bridge_[A-Za-z0-9_]+)\s*;", body):
        result[int(m.group(1))] = m.group(2)
    for m in re.finditer(
        r"ordinal\s*==\s*(\d+)\s*\)\s*return\s+(bridge_[A-Za-z0-9_]+)\s*;", body
    ):
        result[int(m.group(1))] = m.group(2)
    return result


def data_ordinals(bridge_text: str) -> set[int]:
    body = named_function_body(bridge_text, "static uint32_t kernel_data_va_for_ordinal")
    result = {int(m.group(1)) for m in re.finditer(r"case\s+(\d+)\s*:", body)}
    result.update(
        int(m.group(1))
        for m in re.finditer(r"ordinal\s*==\s*(\d+)", body)
    )
    return result


def arg_bytes_map(bridge_text: str) -> dict[int, int]:
    body = named_function_body(bridge_text, "static int stdcall_args_for_ordinal")
    return {
        int(m.group(1)): int(m.group(2))
        for m in re.finditer(r"case\s+(\d+)\s*:\s*return\s+(\d+)\s*;", body)
    }


def find_function_body(
    symbol: str,
    sources: dict[Path, str],
    masked_sources: dict[Path, str],
):
    pat = re.compile(
        r"(?ms)^[^;{}]*\b" + re.escape(symbol) +
        r"\s*\([^;{}]*?\)\s*\{"
    )
    for path, raw in sources.items():
        masked = masked_sources[path]
        match = pat.search(masked)
        if not match:
            continue
        brace = masked.find("{", match.start(), match.end())
        masked_body = extract_braced_body(masked, brace)
        if masked_body is None:
            continue
        raw_body = raw[brace:brace + len(masked_body)]
        return path, raw_body, masked_body
    return None, None, None


def find_symbol_source(
    symbol: str,
    sources: dict[Path, str],
    masked_sources: dict[Path, str],
):
    token = re.compile(r"\b" + re.escape(symbol) + r"\b")
    for path in sources:
        if token.search(masked_sources[path]):
            return path
    return None


def runtime_surface_for_bridge(
    runtime_target: str,
    sources: dict[Path, str],
    masked_sources: dict[Path, str],
):
    """Inspect the callable path the translated guest actually enters.

    Follow bridge_* and xbox_* helpers conservatively so legacy resolver
    implementations that are bypassed by kernel_bridge.c do not inflate the
    Phase-4B host-surface count.
    """
    queue = [runtime_target]
    visited: set[str] = set()
    host_hits: set[str] = set()
    host_via: list[str] = []
    platform_hits: set[str] = set()
    root_path = None

    while queue:
        symbol = queue.pop(0)
        if symbol in visited:
            continue
        visited.add(symbol)

        path, raw_body, masked_body = find_function_body(
            symbol, sources, masked_sources
        )
        if raw_body is None:
            continue
        if root_path is None:
            root_path = path

        hits = host_api_calls(masked_body)
        if hits:
            host_hits.update(hits)
            if symbol != runtime_target:
                host_via.append(symbol)

        platform_hits.update(PHASE4B_PLATFORM_CALL.findall(masked_body))

        for match in re.finditer(
            r"\b((?:xbox|bridge)_[A-Za-z0-9_]+)\s*\(", masked_body
        ):
            callee = match.group(1)
            if (
                callee not in visited
                and callee not in HOST_SURFACE_DIAGNOSTIC_HELPERS
            ):
                queue.append(callee)

    return (
        root_path,
        sorted(host_hits),
        sorted(set(host_via)),
        sorted(platform_hits),
    )


def prototype_for(header: str, symbol: str) -> str | None:
    pos = header.find(symbol)
    if pos < 0:
        return None
    end = header.find(";", pos)
    if end < 0:
        return None
    start = max(header.rfind(";", 0, pos), header.rfind("\n\n", 0, pos))
    return re.sub(r"\s+", " ", header[start + 1:end + 1]).strip()


def split_params(signature: str) -> list[str]:
    left = signature.find("(")
    right = signature.rfind(")")
    if left < 0 or right < left:
        return []
    text = signature[left + 1:right].strip()
    if not text or text == "void":
        return []
    result: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            result.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        result.append("".join(current).strip())
    return result


def expected_cleanup(signature: str) -> int:
    if "__cdecl" in signature:
        return 0
    sizes = []
    for param in split_params(signature):
        by_value_64 = (
            re.search(
                r"\b(?:LARGE_INTEGER|LONGLONG|ULONGLONG|double|uint64_t|__int64)\b",
                param,
            )
            and "*" not in param
            and not re.search(r"\bP(?:LARGE_INTEGER|LONGLONG|ULONGLONG)\b", param)
        )
        sizes.append(8 if by_value_64 else 4)
    if "__fastcall" in signature:
        sizes = sizes[2:]
    return sum(sizes)


def semantic_review_hints(masked_body: str) -> list[str]:
    code = masked_body[1:-1]
    code = re.sub(r"\(void\)\s*[^;]+;", "", code)
    code = re.sub(r"\s+", " ", code).strip()
    if not code:
        return ["no_state_effect"]
    if re.fullmatch(r"return\s+[^;]+;", code):
        return ["constant_return_only"]
    return []


def scan_generated_refs(generated_dir: Path | None, imports) -> dict[int, int]:
    counts = {imp.ordinal: 0 for imp in imports}
    if generated_dir is None or not generated_dir.is_dir():
        return counts
    token_to_ordinal = {
        f"0X{imp.thunk_addr:08X}": imp.ordinal for imp in imports
    }
    literal = re.compile(r"0[xX][0-9A-Fa-f]{8}")
    for path in sorted(generated_dir.rglob("*")):
        if path.suffix.lower() not in {".c", ".cc", ".cpp", ".h", ".hpp"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in literal.finditer(text):
            ordinal = token_to_ordinal.get(match.group(0).upper())
            if ordinal is not None:
                counts[ordinal] += 1
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--xbe", type=Path, required=True)
    ap.add_argument("--json", dest="json_out", type=Path, required=True)
    ap.add_argument("--text", dest="text_out", type=Path, required=True)
    ap.add_argument("--generated-dir", type=Path)
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    xbe_path = args.xbe.resolve()
    if not xbe_path.is_file():
        raise SystemExit(f"[Phase4A] retail XBE not found: {xbe_path}")

    actual_sha = hashlib.sha256(xbe_path.read_bytes()).hexdigest().upper()
    if actual_sha != EXPECTED_XBE_SHA256:
        raise SystemExit(
            f"[Phase4A] unsupported default.xbe: expected {EXPECTED_XBE_SHA256}, got {actual_sha}"
        )

    xbe = XBEParser(str(xbe_path)).parse()
    if xbe.certificate.title_id != EXPECTED_TITLE_ID:
        raise SystemExit(f"[Phase4A] wrong title ID: 0x{xbe.certificate.title_id:08X}")
    if len(xbe.kernel_imports) != EXPECTED_IMPORT_COUNT:
        raise SystemExit(
            f"[Phase4A] expected {EXPECTED_IMPORT_COUNT} imports, found {len(xbe.kernel_imports)}"
        )

    thunks_path = repo / "src" / "kernel" / "kernel_thunks.c"
    bridge_path = repo / "src" / "kernel" / "kernel_bridge.c"
    header_path = repo / "src" / "kernel" / "kernel.h"
    for required in (thunks_path, bridge_path, header_path):
        if not required.is_file():
            raise SystemExit(f"[Phase4A] missing source: {required}")

    thunks_text = thunks_path.read_text(encoding="utf-8-sig")
    bridge_text = bridge_path.read_text(encoding="utf-8-sig")
    header_text = header_path.read_text(encoding="utf-8-sig")
    resolvers = resolver_map(thunks_text)
    bridges = bridge_map(bridge_text)
    data = data_ordinals(bridge_text)
    arg_bytes = arg_bytes_map(bridge_text)

    source_paths = sorted((repo / "src" / "kernel").glob("*.c"))
    source_paths += sorted((repo / "src" / "platform").glob("*.c"))
    sources = {
        p: p.read_text(encoding="utf-8-sig", errors="replace")
        for p in source_paths
    }
    # Symbol classification revisits the same source files for each imported
    # ordinal. Cache comment/string-masked views once instead of rebuilding
    # them hundreds of times.
    masked_sources = {p: mask_noncode(text) for p, text in sources.items()}

    generated_dir = args.generated_dir.resolve() if args.generated_dir else None
    static_refs = scan_generated_refs(generated_dir, xbe.kernel_imports)

    counts = {
        "imports": len(xbe.kernel_imports),
        "resolver_mappings": 0,
        "resolver_unmapped": 0,
        "source_callable": 0,
        "source_data": 0,
        "source_definition_missing": 0,
        "guest_bridge_explicit": 0,
        "guest_data_exports": 0,
        "guest_fallback": 0,
        "guest_arg_metadata_missing": 0,
        "guest_arg_metadata_mismatch": 0,
        "host_surface_flagged": 0,
        "platform_surface_bound": 0,
        "semantic_review_flagged": 0,
        "fallback_referenced_imports": 0,
        "fallback_static_refs": 0,
    }

    rows = []
    for slot, imp in enumerate(xbe.kernel_imports):
        expr = resolvers.get(imp.ordinal)
        symbol_match = re.search(r"\b(xbox_[A-Za-z0-9_]+)\b", expr or "")
        symbol = symbol_match.group(1) if symbol_match else None

        if expr is None:
            counts["resolver_unmapped"] += 1
        else:
            counts["resolver_mappings"] += 1

        if imp.ordinal in data:
            runtime_kind = "data"
            runtime_target = "guest-data"
            counts["guest_data_exports"] += 1
        elif imp.ordinal in bridges:
            runtime_kind = "bridge"
            runtime_target = bridges[imp.ordinal]
            counts["guest_bridge_explicit"] += 1
        else:
            runtime_kind = "fallback"
            runtime_target = "<return-0-fallback>"
            counts["guest_fallback"] += 1

        source = None
        host_hits: list[str] = []
        host_via: list[str] = []
        platform_hits: list[str] = []
        review_hints: list[str] = []
        expected_args = None
        signature = None

        if runtime_kind == "data":
            counts["source_data"] += 1
            if symbol:
                source_path = find_symbol_source(symbol, sources, masked_sources)
                if source_path:
                    source = str(source_path.relative_to(repo)).replace("\\", "/")
                else:
                    counts["source_definition_missing"] += 1
        elif runtime_kind == "bridge":
            source_path, host_hits, host_via, platform_hits = runtime_surface_for_bridge(
                runtime_target, sources, masked_sources
            )
            if source_path is not None:
                counts["source_callable"] += 1
                source = str(source_path.relative_to(repo)).replace("\\", "/")
                _, _, masked_body = find_function_body(
                    runtime_target, sources, masked_sources
                )
                if masked_body is not None:
                    review_hints = semantic_review_hints(masked_body)
                if host_hits:
                    counts["host_surface_flagged"] += 1
                if platform_hits:
                    counts["platform_surface_bound"] += 1
                if review_hints:
                    counts["semantic_review_flagged"] += 1
            else:
                counts["source_definition_missing"] += 1

            if symbol:
                signature = prototype_for(header_text, symbol)
                if signature:
                    expected_args = expected_cleanup(signature)
            elif imp.ordinal == 232:
                # NtUserIoApcDispatcher is bridge-only.
                expected_args = 12
        else:
            # Return-zero fallbacks never enter the legacy xbox_* resolver
            # implementation, so host APIs in that old source are irrelevant
            # to the translated guest runtime path.
            if symbol:
                signature = prototype_for(header_text, symbol)
                if signature:
                    expected_args = expected_cleanup(signature)
            elif imp.ordinal == 232:
                expected_args = 12

        actual_args = arg_bytes.get(imp.ordinal)
        abi_match = None
        if runtime_kind != "data":
            if actual_args is None:
                counts["guest_arg_metadata_missing"] += 1
            if expected_args is not None and actual_args is not None:
                abi_match = expected_args == actual_args
                if not abi_match:
                    counts["guest_arg_metadata_mismatch"] += 1

        refs = static_refs.get(imp.ordinal, 0)
        if runtime_kind == "fallback" and refs:
            counts["fallback_referenced_imports"] += 1
            counts["fallback_static_refs"] += refs

        rows.append({
            "slot": slot,
            "ordinal": imp.ordinal,
            "name": imp.name,
            "thunk_addr": f"0x{imp.thunk_addr:08X}",
            "resolver_expression": expr,
            "resolver_symbol": symbol,
            "runtime_kind": runtime_kind,
            "runtime_target": runtime_target,
            "source": source,
            "signature": signature,
            "guest_arg_bytes": actual_args,
            "expected_guest_arg_bytes": expected_args,
            "abi_match": abi_match,
            "static_generated_refs": refs,
            "host_surface_tokens": host_hits,
            "host_surface_via": host_via,
            "platform_surface_calls": platform_hits,
            "review_hints": review_hints,
        })

    report = {
        "phase": "4A",
        "title": xbe.certificate.title_name,
        "title_id": f"0x{xbe.certificate.title_id:08X}",
        "retail_xbe_sha256": actual_sha,
        "kernel_thunk_addr": f"0x{xbe.header.kernel_thunk_addr:08X}",
        "generated_dir": str(generated_dir) if generated_dir else None,
        "counts": counts,
        "imports": rows,
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.text_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "Merc360 Phase 4A - Mercenaries Guest Kernel Surface Audit",
        "=" * 72,
        f"Title:             {xbe.certificate.title_name}",
        f"Title ID:          0x{xbe.certificate.title_id:08X}",
        f"Retail XBE SHA256: {actual_sha}",
        f"Kernel thunk VA:   0x{xbe.header.kernel_thunk_addr:08X}",
        f"Generated refs:    {generated_dir if generated_dir and generated_dir.is_dir() else '<not scanned>'}",
        "",
        f"Imports:                    {counts['imports']}",
        f"General resolver mappings:  {counts['resolver_mappings']}",
        f"General resolver unmapped:  {counts['resolver_unmapped']}",
        f"Guest explicit bridges:     {counts['guest_bridge_explicit']}",
        f"Guest data exports:         {counts['guest_data_exports']}",
        f"Guest return-0 fallbacks:   {counts['guest_fallback']}",
        f"Arg metadata missing:       {counts['guest_arg_metadata_missing']}",
        f"Arg metadata mismatches:    {counts['guest_arg_metadata_mismatch']}",
        f"Host-surface flagged:       {counts['host_surface_flagged']}",
        f"Phase4B platform-bound:     {counts['platform_surface_bound']}",
        f"Semantic-review flagged:    {counts['semantic_review_flagged']}",
        f"Fallbacks statically used:  {counts['fallback_referenced_imports']}",
        f"Fallback static refs:       {counts['fallback_static_refs']}",
        "",
        "slot ord  thunk       runtime   args exp refs import -> runtime-target [source]",
        "-" * 118,
    ]
    for row in rows:
        args_text = "-" if row["guest_arg_bytes"] is None else str(row["guest_arg_bytes"])
        exp_text = "-" if row["expected_guest_arg_bytes"] is None else str(row["expected_guest_arg_bytes"])
        src = f" [{row['source']}]" if row["source"] else ""
        flags = []
        if row["abi_match"] is False:
            flags.append("ABI_MISMATCH")
        if row["host_surface_tokens"]:
            host_flag = "HOST=" + ",".join(row["host_surface_tokens"])
            if row["host_surface_via"]:
                host_flag += " via " + ",".join(row["host_surface_via"])
            flags.append(host_flag)
        if row["platform_surface_calls"]:
            flags.append("PLATFORM=" + ",".join(row["platform_surface_calls"]))
        if row["review_hints"]:
            flags.append("REVIEW=" + ",".join(row["review_hints"]))
        suffix = " {" + "; ".join(flags) + "}" if flags else ""
        lines.append(
            f"{row['slot']:>3} {row['ordinal']:>4} {row['thunk_addr']} "
            f"{row['runtime_kind']:<8} {args_text:>4} {exp_text:>3} "
            f"{row['static_generated_refs']:>4} {row['name']} -> "
            f"{row['runtime_target']}{src}{suffix}"
        )

    audit_ok = (
        counts["source_definition_missing"] == 0
        and counts["guest_arg_metadata_missing"] == 0
        and counts["guest_arg_metadata_mismatch"] == 0
    )
    lines += [
        "",
        "[Phase4A] AUDIT RESULT: " + ("PASS" if audit_ok else "FAIL"),
        f"[Phase4A] 4B TARGET: replace/review {counts['guest_fallback']} return-0 fallback imports, "
        f"prioritizing {counts['fallback_referenced_imports']} with generated-code references.",
    ]
    args.text_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("[Phase4A] MERCENARIES GUEST KERNEL SURFACE AUDIT")
    print(f"[Phase4A] Verified retail XBE: {actual_sha}")
    print(f"[Phase4A] Exact kernel imports: {counts['imports']}")
    print(
        f"[Phase4A] guest_bridge={counts['guest_bridge_explicit']} "
        f"data={counts['guest_data_exports']} fallback={counts['guest_fallback']}"
    )
    print(
        f"[Phase4A] arg_missing={counts['guest_arg_metadata_missing']} "
        f"arg_mismatch={counts['guest_arg_metadata_mismatch']} "
        f"host_surface={counts['host_surface_flagged']} "
        f"platform_bound={counts['platform_surface_bound']}"
    )
    if generated_dir and generated_dir.is_dir():
        print(
            f"[Phase4A] fallback_referenced={counts['fallback_referenced_imports']} "
            f"fallback_refs={counts['fallback_static_refs']}"
        )
    print(f"[Phase4A] Text report: {args.text_out}")
    print(f"[Phase4A] JSON report: {args.json_out}")
    print("[Phase4A] AUDIT RESULT: " + ("PASS" if audit_ok else "FAIL"))
    return 0 if audit_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

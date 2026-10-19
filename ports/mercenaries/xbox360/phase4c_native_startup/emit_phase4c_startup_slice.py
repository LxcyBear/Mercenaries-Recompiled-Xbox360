#!/usr/bin/env python3
"""Emit the first bounded real retail-derived Phase 4C startup XDK package.

Generated retail bodies remain local under build/. The repository contains only
the emitter and harness logic.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
DEFINE_RE = re.compile(r"(?m)^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\b")
FUNC_RE = re.compile(
    r"(?m)^\s*(?:static\s+)?(?:__forceinline\s+)?"
    r"void\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\(\s*void\s*\)\s*\{"
)
LOC_RE = re.compile(r"^(\s*)loc_([0-9A-Fa-f]{8})\s*:\s*;\s*$")

STANDARD_CALLS = {
    "if", "while", "for", "switch", "sizeof",
    "memcpy", "memmove", "memset", "memcmp",
    "sprintf", "_snprintf", "strlen", "strcmp",
    "sqrt", "sqrtf", "floor", "ceil", "fabs", "fabsf",
    "ldexp", "isnan", "isfinite",
}


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


def closing_brace(masked: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(masked)):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    raise ValueError(f"unterminated function at offset {open_index}")


def load_ranges(path: Path) -> tuple[dict[int, dict], dict[str, int]]:
    rows = json.loads(path.read_text(encoding="utf-8-sig"))
    by_va: dict[int, dict] = {}
    by_name: dict[str, int] = {}
    for row in rows:
        try:
            start = int(str(row["start"]), 0)
            end = int(str(row["end"]), 0)
        except (KeyError, TypeError, ValueError):
            continue
        name = str(row.get("name", f"sub_{start:08X}"))
        item = {**row, "start": start, "end": end, "name": name}
        by_va[start] = item
        by_name[name] = start
    return by_va, by_name


def load_generated(
    root: Path,
    by_name: dict[str, int],
) -> dict[int, dict]:
    result: dict[int, dict] = {}
    for path in sorted(root.glob("recomp_*.c")):
        if path.name in ("recomp_dispatch.c", "recomp_stubs_unresolved.c"):
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        masked = mask_noncode(raw)
        for match in FUNC_RE.finditer(masked):
            name = match.group(1)
            va = by_name.get(name)
            if va is None:
                continue
            open_index = masked.find("{", match.start(), match.end())
            end = closing_brace(masked, open_index)
            result[va] = {
                "name": name,
                "source": raw[match.start():end],
                "file": path.name,
            }
    return result


def localize_and_instrument(source: str, name: str) -> str:
    source, count = re.subn(
        rf"\bvoid\s+{re.escape(name)}\s*\(\s*void\s*\)",
        f"static void {name}(void)",
        source,
        count=1,
    )
    if count != 1:
        raise SystemExit(
            f"[Phase4C-B] could not localize translated definition {name}"
        )

    out: list[str] = []
    for line in source.splitlines():
        out.append(line)
        match = LOC_RE.match(line)
        if match:
            va = int(match.group(2), 16)
            out.append(
                f"{match.group(1)}    PHASE4C_BUDGET_TICK(0x{va:08X}u);"
            )
    return "\n".join(out) + "\n"


def support_symbols(text: str) -> set[str]:
    masked = mask_noncode(text)
    result = set(CALL_RE.findall(masked))
    result.update(DEFINE_RE.findall(masked))
    result.update(STANDARD_CALLS)
    return result


def build_env_source(phase2e_source: str) -> str:
    marker = "VOID __cdecl main()"
    index = phase2e_source.find(marker)
    if index < 0:
        raise SystemExit("[Phase4C-B] Phase-2E main marker not found")

    prefix = phase2e_source[:index]
    prefix = prefix.replace(
        "[Merc360:P2E]",
        "[Merc360:P4C-ENV]",
    )

    wrapper = r'''
static MercGuestMemory s_phase4c_memory;

extern "C" int phase4c_env_prepare(void)
{
    XbeBuffer xbe;
    int ok = 0;

    ZeroMemory(&xbe, sizeof(xbe));

    s_logFile = CreateFileA(
        "game:\\merc360-phase4c-startup-env.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 4C-B RETAIL ENVIRONMENT PREP START");
    trace("Expected user file: game:\\default.xbe");

    if (s_phase4c_memory.base)
        guest_memory_shutdown(&s_phase4c_memory);
    ZeroMemory(&s_phase4c_memory, sizeof(s_phase4c_memory));

    do
    {
        if (!guest_memory_init(&s_phase4c_memory))
        {
            trace("FATAL: could not allocate 64 MiB guest arena");
            break;
        }
        trace("PASS: 64 MiB guest arena allocated and cleared");

        if (!load_file("game:\\default.xbe", &xbe))
        {
            trace("FATAL: could not read game:\\default.xbe");
            break;
        }

        if (!verify_supported_xbe_hash(&xbe))
        {
            trace("PHASE 4C-B EXACT RETAIL VERIFICATION: FAIL");
            break;
        }
        trace("PHASE 4C-B EXACT RETAIL VERIFICATION: PASS");

        if (!load_supported_xbe(&xbe, &s_phase4c_memory))
        {
            trace("PHASE 4C-B VERIFIED XBE LOAD RESULT: FAIL");
            break;
        }
        trace("PHASE 4C-B VERIFIED XBE LOAD RESULT: PASS");

        if (!initialize_execution_environment(&s_phase4c_memory))
        {
            trace("PHASE 4C-B EXECUTION ENVIRONMENT RESULT: FAIL");
            break;
        }
        trace("PHASE 4C-B EXECUTION ENVIRONMENT RESULT: PASS");

        ok = 1;
    }
    while (0);

    unload_file(&xbe);

    if (!ok && s_phase4c_memory.base)
        guest_memory_shutdown(&s_phase4c_memory);

    return ok;
}

extern "C" BYTE* phase4c_env_guest_base(void)
{
    return s_phase4c_memory.base;
}

extern "C" DWORD phase4c_env_initial_esp(void)
{
    return MERC_STACK_TOP;
}

extern "C" DWORD phase4c_env_entry(void)
{
    return MERC_ENTRY_POINT;
}

extern "C" void phase4c_env_shutdown(void)
{
    if (s_phase4c_memory.base)
    {
        guest_memory_shutdown(&s_phase4c_memory);
        trace("Guest arena released");
    }

    trace("PHASE 4C-B RETAIL ENVIRONMENT PREP END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}
'''
    return prefix + wrapper


def boundary_support() -> str:
    return r'''
#include <setjmp.h>

#define PHASE4C_EXEC_BUDGET 200000u

enum Phase4CBoundaryKind
{
    PHASE4C_BOUNDARY_NONE = 0,
    PHASE4C_BOUNDARY_ICALL = 1,
    PHASE4C_BOUNDARY_ICALL_SAFE = 2,
    PHASE4C_BOUNDARY_ITAIL = 3,
    PHASE4C_BOUNDARY_ITAIL_SAFE = 4,
    PHASE4C_BOUNDARY_BUDGET = 5,
    PHASE4C_BOUNDARY_GUEST_FAULT = 6
};

static jmp_buf s_phase4cEscape;
static DWORD s_phase4cBoundaryKind = PHASE4C_BOUNDARY_NONE;
static DWORD s_phase4cBoundaryTarget = 0u;
static DWORD s_phase4cBoundaryEsp = 0u;
static DWORD s_phase4cBoundarySavedEsp = 0u;
static DWORD s_phase4cBoundaryCaller = 0u;
static DWORD s_phase4cBlockTicks = 0u;

static DWORD phase4c_current_caller(void)
{
    DWORD index;
    if (s_traceCount == 0u)
        return 0u;
    index = s_traceCount - 1u;
    if (index >= TRACE_CAPACITY)
        index = TRACE_CAPACITY - 1u;
    return s_trace[index];
}

static void phase4c_escape(
    DWORD kind,
    DWORD target,
    DWORD savedEsp)
{
    s_phase4cBoundaryKind = kind;
    s_phase4cBoundaryTarget = target;
    s_phase4cBoundaryEsp = g_esp;
    s_phase4cBoundarySavedEsp = savedEsp;
    s_phase4cBoundaryCaller = phase4c_current_caller();
    longjmp(s_phase4cEscape, 1);
}

static void phase4c_budget_tick(DWORD va)
{
    (void)va;
    ++s_phase4cBlockTicks;

    if (s_accessFault)
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0u,
            g_esp);

    if (s_phase4cBlockTicks > PHASE4C_EXEC_BUDGET)
        phase4c_escape(
            PHASE4C_BOUNDARY_BUDGET,
            va,
            g_esp);
}

#define PHASE4C_BUDGET_TICK(va) \
    do { phase4c_budget_tick((DWORD)(va)); } while (0)

typedef void (*recomp_func_t)(void);

#define RECOMP_ICALL(xbox_va) do { \
    phase4c_escape( \
        PHASE4C_BOUNDARY_ICALL, \
        (DWORD)(xbox_va), \
        g_esp + 4u); \
} while (0)

#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \
    phase4c_escape( \
        PHASE4C_BOUNDARY_ICALL_SAFE, \
        (DWORD)(xbox_va), \
        (DWORD)(saved_esp)); \
} while (0)

#define RECOMP_ITAIL(xbox_va) do { \
    phase4c_escape( \
        PHASE4C_BOUNDARY_ITAIL, \
        (DWORD)(xbox_va), \
        g_esp); \
} while (0)

#define RECOMP_ITAIL_SAFE(xbox_va, saved_esp) do { \
    phase4c_escape( \
        PHASE4C_BOUNDARY_ITAIL_SAFE, \
        (DWORD)(xbox_va), \
        (DWORD)(saved_esp)); \
} while (0)

/* The startup closure currently does not require live dispatch resolution.
 * These declarations make an accidental direct lookup call a link-time
 * failure rather than silently inventing behavior. */
recomp_func_t recomp_lookup(uint32_t xbox_va);
recomp_func_t recomp_lookup_manual(uint32_t xbox_va);
recomp_func_t recomp_lookup_kernel(uint32_t xbox_va);

/* MMX architectural state is shared just like the production runtime. */
uint64_t g_mm0 = 0ui64, g_mm1 = 0ui64, g_mm2 = 0ui64, g_mm3 = 0ui64;
uint64_t g_mm4 = 0ui64, g_mm5 = 0ui64, g_mm6 = 0ui64, g_mm7 = 0ui64;
#define mm0 g_mm0
#define mm1 g_mm1
#define mm2 g_mm2
#define mm3 g_mm3
#define mm4 g_mm4
#define mm5 g_mm5
#define mm6 g_mm6
#define mm7 g_mm7

static uint64_t xbox_ReadTimeStampCounter(void)
{
    LARGE_INTEGER counter;
    LARGE_INTEGER frequency;
    QueryPerformanceCounter(&counter);
    QueryPerformanceFrequency(&frequency);
    if (frequency.QuadPart == 0)
        return 0ui64;
    return (uint64_t)(
        ((unsigned __int64)counter.QuadPart * 733333333ui64) /
        (unsigned __int64)frequency.QuadPart);
}

#define RECOMP_RDTSC() do { \
    uint64_t _recomp_tsc = xbox_ReadTimeStampCounter(); \
    eax = (uint32_t)_recomp_tsc; \
    edx = (uint32_t)(_recomp_tsc >> 32); \
} while (0)
'''


def driver_source(root_name: str, root_va: int, member_count: int) -> str:
    return rf'''
extern "C" int phase4c_env_prepare(void);
extern "C" BYTE* phase4c_env_guest_base(void);
extern "C" DWORD phase4c_env_initial_esp(void);
extern "C" DWORD phase4c_env_entry(void);
extern "C" void phase4c_env_shutdown(void);

static const char* phase4c_boundary_name(DWORD kind)
{{
    switch (kind)
    {{
    case PHASE4C_BOUNDARY_ICALL: return "ICALL";
    case PHASE4C_BOUNDARY_ICALL_SAFE: return "ICALL_SAFE";
    case PHASE4C_BOUNDARY_ITAIL: return "ITAIL";
    case PHASE4C_BOUNDARY_ITAIL_SAFE: return "ITAIL_SAFE";
    case PHASE4C_BOUNDARY_BUDGET: return "BUDGET";
    case PHASE4C_BOUNDARY_GUEST_FAULT: return "GUEST_FAULT";
    default: return "NONE";
    }}
}}

static void phase4c_log_trace(void)
{{
    DWORD count = s_traceCount < TRACE_CAPACITY ? s_traceCount : TRACE_CAPACITY;
    DWORD start = count > 32u ? count - 32u : 0u;
    DWORD i;
    char line[160];

    for (i = start; i < count; ++i)
    {{
        sprintf(
            line,
            "trace[%u]=%08X",
            (unsigned int)i,
            (unsigned int)s_trace[i]);
        trace(line);
    }}
}}

static void phase4c_reset_architecture(void)
{{
    g_eax = g_ecx = g_edx = 0u;
    g_ebx = g_esi = g_edi = 0u;
    g_seh_ebp = 0u;
    g_eflags = 0u;

    g_fp_top = 0u;
    g_x87_control_word = 0x037Fu;
    g_x87_status_word = 0u;
    memset(g_fp_stack, 0, sizeof(g_fp_stack));
    memset(g_xmm0, 0, sizeof(g_xmm0));
    memset(g_xmm1, 0, sizeof(g_xmm1));
    memset(g_xmm2, 0, sizeof(g_xmm2));
    memset(g_xmm3, 0, sizeof(g_xmm3));
    memset(g_xmm4, 0, sizeof(g_xmm4));
    memset(g_xmm5, 0, sizeof(g_xmm5));
    memset(g_xmm6, 0, sizeof(g_xmm6));
    memset(g_xmm7, 0, sizeof(g_xmm7));

    g_mm0 = g_mm1 = g_mm2 = g_mm3 = 0ui64;
    g_mm4 = g_mm5 = g_mm6 = g_mm7 = 0ui64;

    s_traceCount = 0u;
    memset(s_trace, 0, sizeof(s_trace));
    s_accessFault = 0;
    s_phase4cBoundaryKind = PHASE4C_BOUNDARY_NONE;
    s_phase4cBoundaryTarget = 0u;
    s_phase4cBoundaryEsp = 0u;
    s_phase4cBoundarySavedEsp = 0u;
    s_phase4cBoundaryCaller = 0u;
    s_phase4cBlockTicks = 0u;
}}

VOID __cdecl main()
{{
    DWORD started;
    DWORD nextHeartbeat = 1000u;
    DWORD initialEsp;
    int escaped;
    int boundedPass = 0;
    char line[320];

    s_logFile = CreateFileA(
        "game:\\merc360-phase4c-startup.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 4C-B REAL TRANSLATED STARTUP BOUNDARY PROOF START");
    trace("BUILD TAG: P4C-STARTUP-20261019-A");
    trace("Policy: execute the real retail entry and stop at the first live dynamic/indirect boundary");
    sprintf(
        line,
        "Entry=%08X closure_members=%u",
        (unsigned int)0x{root_va:08X}u,
        (unsigned int){member_count}u);
    trace(line);

    if (!phase4c_env_prepare())
    {{
        trace("PHASE 4C-B ENVIRONMENT RESULT: FAIL");
        goto wait_for_exit;
    }}

    trace("PHASE 4C-B ENVIRONMENT RESULT: PASS");

    g_ram = phase4c_env_guest_base();
    if (!g_ram)
    {{
        trace("FAIL: environment returned null guest RAM");
        goto shutdown_env;
    }}

    if (phase4c_env_entry() != 0x{root_va:08X}u)
    {{
        trace("FAIL: environment entry VA does not match translated root");
        goto shutdown_env;
    }}

    phase4c_reset_architecture();

    initialEsp = phase4c_env_initial_esp();
    if (initialEsp < 4u)
    {{
        trace("FAIL: invalid initial guest ESP");
        goto shutdown_env;
    }}

    /*
     * Give the translated XBE entry one synthetic kernel-return slot. If the
     * entry returns before a dynamic boundary, this lets us distinguish a
     * clean translated RET from stack collapse.
     */
    g_esp = initialEsp - 4u;
    GUEST_WRITE32(g_esp, 0xC4C40000u);

    trace("PASS: exact retail XBE data + Phase-2E TIB/TLS/stack environment active");
    trace("PASS: entering real translated xbe_entry_point now");

    escaped = setjmp(s_phase4cEscape);
    if (escaped == 0)
    {{
        {root_name}();

        sprintf(
            line,
            "ENTRY RETURNED: eax=%08X esp=%08X ticks=%u trace=%u fault=%u",
            (unsigned int)g_eax,
            (unsigned int)g_esp,
            (unsigned int)s_phase4cBlockTicks,
            (unsigned int)s_traceCount,
            (unsigned int)s_accessFault);
        trace(line);

        boundedPass =
            !s_accessFault &&
            s_traceCount > 0u &&
            s_trace[0] == 0x{root_va:08X}u;
    }}
    else
    {{
        sprintf(
            line,
            "BOUNDARY: kind=%s caller=%08X target=%08X esp=%08X saved_esp=%08X ticks=%u trace=%u",
            phase4c_boundary_name(s_phase4cBoundaryKind),
            (unsigned int)s_phase4cBoundaryCaller,
            (unsigned int)s_phase4cBoundaryTarget,
            (unsigned int)s_phase4cBoundaryEsp,
            (unsigned int)s_phase4cBoundarySavedEsp,
            (unsigned int)s_phase4cBlockTicks,
            (unsigned int)s_traceCount);
        trace(line);

        sprintf(
            line,
            "BOUNDARY REGISTERS: eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X seh_ebp=%08X fault=%u",
            (unsigned int)g_eax,
            (unsigned int)g_ecx,
            (unsigned int)g_edx,
            (unsigned int)g_ebx,
            (unsigned int)g_esi,
            (unsigned int)g_edi,
            (unsigned int)g_seh_ebp,
            (unsigned int)s_accessFault);
        trace(line);

        boundedPass =
            s_phase4cBoundaryKind >= PHASE4C_BOUNDARY_ICALL &&
            s_phase4cBoundaryKind <= PHASE4C_BOUNDARY_ITAIL_SAFE &&
            !s_accessFault &&
            s_traceCount > 0u &&
            s_trace[0] == 0x{root_va:08X}u;
    }}

    phase4c_log_trace();

    if (boundedPass)
        trace("PHASE 4C-B BOUNDED REAL STARTUP RESULT: PASS");
    else
        trace("PHASE 4C-B BOUNDED REAL STARTUP RESULT: FAIL");

shutdown_env:
    phase4c_env_shutdown();
    g_ram = NULL;

wait_for_exit:
    trace("Press A to exit, or automatic exit after 10 seconds");
    started = GetTickCount();

    for (;;)
    {{
        XINPUT_STATE state;
        DWORD elapsed = GetTickCount() - started;

        if (elapsed >= 10000u)
            break;

        ZeroMemory(&state, sizeof(state));
        if (XInputGetState(0, &state) == ERROR_SUCCESS &&
            (state.Gamepad.wButtons & XINPUT_GAMEPAD_A) != 0)
            break;

        if (elapsed >= nextHeartbeat)
        {{
            trace("POST-TEST HEARTBEAT");
            nextHeartbeat += 1000u;
        }}

        Sleep(33);
    }}

    trace("PHASE 4C-B REAL TRANSLATED STARTUP BOUNDARY PROOF END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {{
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }}
}}
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--closure-report", type=Path, required=True)
    ap.add_argument("--phase3n-template", type=Path, required=True)
    ap.add_argument("--phase2e-source", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    report = json.loads(args.closure_report.read_text(encoding="utf-8-sig"))
    if report.get("phase") != "4C-A" or report.get("structural_pass") is not True:
        raise SystemExit("[Phase4C-B] Phase 4C-A report is not a structural PASS")

    closure = report["closure"]
    if closure.get("missing_direct_dependencies"):
        raise SystemExit("[Phase4C-B] closure still has missing direct dependencies")

    root_va = int(str(report["entry"]), 0)
    entry_resolution = report.get("entry_resolution", {})
    if entry_resolution.get("kind") != "exact_function":
        raise SystemExit(
            "[Phase4C-B] first execution gate currently requires an exact "
            "translated entry function"
        )

    by_va, by_name = load_ranges(args.functions)
    generated = load_generated(args.generated_root, by_name)

    member_vas = [
        int(str(row["address"]), 0)
        for row in closure["members"]
    ]
    missing_generated = [va for va in member_vas if va not in generated]
    if missing_generated:
        raise SystemExit(
            "[Phase4C-B] generated body missing for closure member(s): "
            + ", ".join(f"0x{va:08X}" for va in missing_generated)
        )

    root_row = by_va.get(root_va)
    if root_row is None:
        raise SystemExit("[Phase4C-B] root absent from function inventory")
    root_name = root_row["name"]

    bodies: list[str] = []
    forward_decls: list[str] = []
    closure_names = set()

    for va in member_vas:
        row = generated[va]
        name = row["name"]
        closure_names.add(name)
        forward_decls.append(f"static void {name}(void);")
        bodies.append(localize_and_instrument(row["source"], name))

    template = args.phase3n_template.read_text(encoding="utf-8")
    marker = "/*__P3NB_FORWARD_DECLS__*/"
    marker_index = template.find(marker)
    if marker_index < 0:
        raise SystemExit("[Phase4C-B] Phase-3N support donor marker missing")

    support = template[:marker_index]
    replacements = {
        "__P3NB_ROOT_VA__": f"0x{root_va:08X}u",
        "__P3NB_MEMBER_COUNT__": str(len(member_vas)),
        "__P3NB_DEPTH__": str(int(closure["max_direct_depth"])),
        "__P3NB_SCALE_COUNT__": str(len(member_vas)),
        "__P3NB_SCALE_GUEST_BYTES__": str(int(closure["guest_bytes"])),
        "__P3NB_SCALE_SOURCE_BYTES__": str(int(closure["source_bytes"])),
        "__P3NB_MEMBER_VAS__": ", ".join(
            f"0x{va:08X}u" for va in member_vas
        ),
    }
    for token, value in replacements.items():
        support = support.replace(token, value)

    unresolved_tokens = [
        token for token in (
            "__P3NB_ROOT_VA__",
            "__P3NB_MEMBER_COUNT__",
            "__P3NB_DEPTH__",
            "__P3NB_SCALE_COUNT__",
            "__P3NB_SCALE_GUEST_BYTES__",
            "__P3NB_SCALE_SOURCE_BYTES__",
            "__P3NB_MEMBER_VAS__",
        )
        if token in support
    ]
    if unresolved_tokens:
        raise SystemExit(
            "[Phase4C-B] unresolved Phase-3N donor token(s): "
            + ", ".join(unresolved_tokens)
        )

    support = support.replace("[Merc360:P3N]", "[Merc360:P4C]")

    boundary = boundary_support()

    supplied = support_symbols(support + boundary)
    supplied.update(closure_names)

    unknown: dict[str, list[str]] = {}
    for va in member_vas:
        row = generated[va]
        calls = set(CALL_RE.findall(mask_noncode(row["source"])))
        calls.discard(row["name"])
        missing = sorted(
            name for name in calls
            if name not in supplied and name not in STANDARD_CALLS
        )
        if missing:
            unknown[f"0x{va:08X} {row['name']}"] = missing

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "phase": "4C-B",
        "build_tag": "P4C-STARTUP-20261019-A",
        "entry": f"0x{root_va:08X}",
        "root_name": root_name,
        "closure_members": len(member_vas),
        "closure_depth": int(closure["max_direct_depth"]),
        "closure_guest_bytes": int(closure["guest_bytes"]),
        "closure_source_bytes": int(closure["source_bytes"]),
        "dynamic_boundary_bodies": int(closure["dynamic_boundary_count"]),
        "unknown_direct_helpers": unknown,
        "members": [f"0x{va:08X}" for va in member_vas],
    }
    (args.out_dir / "phase4c-b-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    if unknown:
        print("[Phase4C-B] unsupported direct helper calls found:")
        for owner, names in unknown.items():
            print(f"[Phase4C-B]   {owner}: {', '.join(names)}")
        raise SystemExit(
            "[Phase4C-B] refusing to emit a startup XEX with unresolved "
            "direct helper dependencies"
        )

    phase2e = args.phase2e_source.read_text(encoding="utf-8")
    env_source = build_env_source(phase2e)

    generated_main = (
        support
        + "\n"
        + boundary
        + "\n\n/* Phase 4C-B translated startup closure */\n"
        + "\n".join(forward_decls)
        + "\n\n#pragma optimize(\"\", off)\n"
        + "\n\n".join(bodies)
        + "\n#pragma optimize(\"\", on)\n"
        + driver_source(root_name, root_va, len(member_vas))
    )

    (args.out_dir / "main.cpp").write_text(generated_main, encoding="utf-8")
    (args.out_dir / "phase4c_env.cpp").write_text(env_source, encoding="utf-8")

    print("[Phase4C-B] STARTUP XDK PACKAGE READY")
    print(
        f"[Phase4C-B] Entry: {root_name} @ 0x{root_va:08X}; "
        f"closure={len(member_vas)} bodies; "
        f"dynamic-boundary bodies={closure['dynamic_boundary_count']}"
    )
    print(f"[Phase4C-B] main: {args.out_dir / 'main.cpp'}")
    print(f"[Phase4C-B] env:  {args.out_dir / 'phase4c_env.cpp'}")
    print(
        "[Phase4C-B] Runtime policy: execute real translated entry and "
        "escape at first live dynamic/indirect boundary."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

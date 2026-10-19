#!/usr/bin/env python3
"""Phase 4C-S: promote the next hardware-observed direct frontier.

Phase 4C-R executed the promoted 0x0022C5A4 function and real hardware continued
cleanly to DIRECT_FRONTIER 0x00230060 from translated caller 0x0022C5A4 with
fault=0 and a balanced boundary. This gate adds only 0x00230060 to the translated
pack while preserving every prior loader, kernel-data, kernel-header, and
kernel-call continuation invariant. The main/env build cookie is rotated for S.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path


THREAD_START = 0x0022B43F
THREAD_CTX1 = 0x002295D6
THREAD_CTX2 = 0x00000000
KERNEL_THREAD_TARGET = 0x800000FF
STARTUP_CALLBACK = 0x002295D6
CALLBACK_DIRECT_DEPTH = 1
CALLBACK_MEMBER_CAP = 64
MERC_KERNEL_THUNK_VA = 0x002DBCE0
MERC_KERNEL_IMPORT_COUNT = 111
XBOX_HARDWARE_INFO_TOKEN = 0x80000142
MERC_KERNEL_DATA_BASE = 0x0087E000
LIVE_DIRECT_FRONTIER_TARGET = 0x0022C47B
LIVE_DIRECT_FRONTIER_TARGET_2 = 0x0022F128
LIVE_DIRECT_FRONTIER_TARGET_3 = 0x0022C5A4
LIVE_DIRECT_FRONTIER_TARGET_4 = 0x00230060
KERNEL_HEADER_BASE = 0x80010000
KERNEL_HEADER_SIZE = 0x1000
KERNEL_HEADER_ELFANEW = 0x80


def load_base(path: Path):
    spec = importlib.util.spec_from_file_location("phase4c_b_emitter", path)
    if spec is None or spec.loader is None:
        raise SystemExit("[Phase4C-S] could not load Phase 4C-B emitter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pack_lookup_source(member_vas, generated):
    lines = [
        "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)",
        "{",
        "    switch (xbox_va) {",
    ]
    for va in member_vas:
        lines.append(
            f"    case 0x{va:08X}u: return {generated[va]['name']};"
        )
    lines += [
        "    default: return (recomp_func_t)0;",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


def instrument_first_fault_support(support):
    decl = "static int s_accessFault = 0;"
    expanded = """static int s_accessFault = 0;
static DWORD s_phase4cFaultAddress = 0u;
static DWORD s_phase4cFaultWidth = 0u;
static DWORD s_phase4cFaultWrite = 0u;
static int s_phase4cFaultEscapeArmed = 0;

static void phase4c_escape(
    DWORD kind,
    DWORD target,
    DWORD savedEsp);"""
    if decl not in support:
        raise SystemExit("[Phase4C-S] s_accessFault declaration marker changed")
    support = support.replace(decl, expanded, 1)

    marker = "uint8_t recomp_guest_read8(uint32_t address)"
    note = r"""static void phase4c_note_access_fault(
    DWORD address,
    DWORD width,
    DWORD isWrite)
{
    if (!s_accessFault)
    {
        char line[192];
        s_phase4cFaultAddress = address;
        s_phase4cFaultWidth = width;
        s_phase4cFaultWrite = isWrite;
        sprintf(
            line,
            "FAULT ACCESS IMMEDIATE: %s width=%u guest=%08X",
            isWrite ? "WRITE" : "READ",
            (unsigned int)width,
            (unsigned int)address);
        trace(line);
    }
    s_accessFault = 1;

    /*
     * Boundary kind 6 is PHASE4C_BOUNDARY_GUEST_FAULT. The enum and the
     * phase4c_escape definition are emitted later in this translation unit,
     * so use the stable numeric value here after a forward declaration.
     *
     * Do not longjmp before the driver has established setjmp; preparation
     * accesses still retain the old flag-only behavior.
     */
    if (s_phase4cFaultEscapeArmed)
        phase4c_escape(6u, address, g_esp);
}

"""
    if marker not in support:
        raise SystemExit("[Phase4C-S] guest accessor insertion marker changed")
    support = support.replace(marker, note + marker, 1)

    replacements = [
        (
            """uint8_t recomp_guest_read8(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 1u);

    if (!p)
    {
        s_accessFault = 1;""",
            """uint8_t recomp_guest_read8(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 1u);

    if (!p)
    {
        phase4c_note_access_fault((DWORD)address, 1u, 0u);""",
        ),
        (
            """uint16_t recomp_guest_read16(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 2u);

    if (!p)
    {
        s_accessFault = 1;""",
            """uint16_t recomp_guest_read16(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 2u);

    if (!p)
    {
        phase4c_note_access_fault((DWORD)address, 2u, 0u);""",
        ),
        (
            """uint32_t recomp_guest_read32(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 4u);

    if (!p)
    {
        s_accessFault = 1;""",
            """uint32_t recomp_guest_read32(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 4u);

    if (!p)
    {
        phase4c_note_access_fault((DWORD)address, 4u, 0u);""",
        ),
        (
            """uint64_t recomp_guest_read64(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 8u);
    uint64_t lo;
    uint64_t hi;

    if (!p)
    {
        s_accessFault = 1;""",
            """uint64_t recomp_guest_read64(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 8u);
    uint64_t lo;
    uint64_t hi;

    if (!p)
    {
        phase4c_note_access_fault((DWORD)address, 8u, 0u);""",
        ),
        (
            """void recomp_guest_write8(uint32_t address, uint8_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 1u);

    if (!p)
    {
        s_accessFault = 1;""",
            """void recomp_guest_write8(uint32_t address, uint8_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 1u);

    if (!p)
    {
        phase4c_note_access_fault((DWORD)address, 1u, 1u);""",
        ),
        (
            """void recomp_guest_write16(uint32_t address, uint16_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 2u);

    if (!p)
    {
        s_accessFault = 1;""",
            """void recomp_guest_write16(uint32_t address, uint16_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 2u);

    if (!p)
    {
        phase4c_note_access_fault((DWORD)address, 2u, 1u);""",
        ),
        (
            """void recomp_guest_write32(uint32_t address, uint32_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 4u);

    if (!p)
    {
        s_accessFault = 1;""",
            """void recomp_guest_write32(uint32_t address, uint32_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 4u);

    if (!p)
    {
        phase4c_note_access_fault((DWORD)address, 4u, 1u);""",
        ),
        (
            """void recomp_guest_write64(uint32_t address, uint64_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 8u);

    if (!p)
    {
        s_accessFault = 1;""",
            """void recomp_guest_write64(uint32_t address, uint64_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 8u);

    if (!p)
    {
        phase4c_note_access_fault((DWORD)address, 8u, 1u);""",
        ),
        (
            """static void recomp_guest_read128(uint32_t address, uint32_t words[4])
{
    BYTE* p = guest_ptr((DWORD)address, 16u);
    DWORD i;

    if (!p)
    {
        s_accessFault = 1;""",
            """static void recomp_guest_read128(uint32_t address, uint32_t words[4])
{
    BYTE* p = guest_ptr((DWORD)address, 16u);
    DWORD i;

    if (!p)
    {
        phase4c_note_access_fault((DWORD)address, 16u, 0u);""",
        ),
        (
            """static void recomp_guest_write128(
    uint32_t address,
    const uint32_t words[4])
{
    BYTE* p = guest_ptr((DWORD)address, 16u);
    DWORD i;

    if (!p)
    {
        s_accessFault = 1;""",
            """static void recomp_guest_write128(
    uint32_t address,
    const uint32_t words[4])
{
    BYTE* p = guest_ptr((DWORD)address, 16u);
    DWORD i;

    if (!p)
    {
        phase4c_note_access_fault((DWORD)address, 16u, 1u);""",
        ),
    ]

    for old, new in replacements:
        if old not in support:
            raise SystemExit(
                "[Phase4C-S] exact guest accessor body marker changed"
            )
        support = support.replace(old, new, 1)

    # Only the assignment inside phase4c_note_access_fault may remain.
    if support.count("s_accessFault = 1;") != 1:
        raise SystemExit(
            "[Phase4C-S] residual direct fault assignments remain"
        )

    return support

def instrument_kernel_header_page(support):
    decl = "static BYTE* g_ram = NULL;"
    expanded = """static BYTE s_phase4cKernelHeaderPage[0x1000u];
static BYTE* g_ram = NULL;"""
    if decl not in support:
        raise SystemExit("[Phase4C-S] guest RAM declaration marker changed")
    support = support.replace(decl, expanded, 1)

    old_ptr = """static BYTE* guest_ptr(DWORD address, DWORD width)
{
    DWORD offset;

    if (!g_ram || !guest_offset(address, width, &offset))
        return NULL;

    return g_ram + offset;
}"""
    new_ptr = """static BYTE* guest_ptr(DWORD address, DWORD width)
{
    DWORD offset;

    /*
     * xboxkrnl.exe occupies 0x80010000 on the original Xbox. Keep that page
     * separate from title RAM; Phase 4C-S supplies a minimal synthetic PE
     * header for startup code that introspects the kernel image.
     */
    if (address >= KERNEL_BASE && address < KERNEL_END)
    {
        DWORD kernelOffset = address - KERNEL_BASE;
        if (width == 0u ||
            kernelOffset >= 0x1000u ||
            width > 0x1000u - kernelOffset)
            return NULL;
        return s_phase4cKernelHeaderPage + kernelOffset;
    }

    if (!g_ram || !guest_offset(address, width, &offset))
        return NULL;

    return g_ram + offset;
}"""
    if old_ptr not in support:
        raise SystemExit("[Phase4C-S] guest_ptr body marker changed")
    support = support.replace(old_ptr, new_ptr, 1)
    return support


def bounded_callback_members(base, root_va, generated):
    name_to_va = {row["name"]: va for va, row in generated.items()}
    queue = [(root_va, 0)]
    seen = set()

    while queue:
        va, depth = queue.pop(0)
        if va in seen:
            continue
        if va not in generated:
            raise SystemExit(
                f"[Phase4C-S] callback dependency 0x{va:08X} "
                "is absent from generated tree"
            )
        seen.add(va)
        if len(seen) >= CALLBACK_MEMBER_CAP or depth >= CALLBACK_DIRECT_DEPTH:
            continue

        row = generated[va]
        calls = set(base.CALL_RE.findall(base.mask_noncode(row["source"])))
        deps = sorted(
            name_to_va[name]
            for name in calls
            if name in name_to_va and name_to_va[name] not in seen
        )
        for dep in deps:
            if len(seen) + len(queue) >= CALLBACK_MEMBER_CAP:
                break
            queue.append((dep, depth + 1))

    return sorted(seen)


def rewrite_direct_frontier(base, source, generated, packed_vas):
    name_to_va = {row["name"]: va for va, row in generated.items()}
    calls = set(base.CALL_RE.findall(base.mask_noncode(source)))
    frontier = []

    for name in sorted(calls):
        va = name_to_va.get(name)
        if va is None or va in packed_vas:
            continue
        pattern = r"\b" + re.escape(name) + r"\(\);"
        replacement = f"phase4c_direct_frontier(0x{va:08X}u);"
        source, count = re.subn(pattern, replacement, source)
        if count:
            frontier.append(va)

    return source, sorted(set(frontier))


def phase4c_s_boundary(base):
    text = base.boundary_support()

    old_enum = """    PHASE4C_BOUNDARY_DEBUGBREAK = 7,
    PHASE4C_BOUNDARY_HEAP_EXHAUSTED = 8
};"""
    new_enum = """    PHASE4C_BOUNDARY_DEBUGBREAK = 7,
    PHASE4C_BOUNDARY_HEAP_EXHAUSTED = 8,
    PHASE4C_BOUNDARY_THREAD_TARGET = 9,
    PHASE4C_BOUNDARY_KERNEL_FRAME = 10,
    PHASE4C_BOUNDARY_THREAD_RETURN = 11,
    PHASE4C_BOUNDARY_CALLBACK_RETURN = 12,
    PHASE4C_BOUNDARY_DIRECT_FRONTIER = 13
};"""
    if old_enum not in text:
        raise SystemExit("[Phase4C-S] boundary enum marker changed")
    text = text.replace(old_enum, new_enum)

    old_macro = r'''#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \
    phase4c_escape( \
        PHASE4C_BOUNDARY_ICALL_SAFE, \
        (DWORD)(xbox_va), \
        (DWORD)(saved_esp)); \
} while (0)'''

    new_macro = r'''#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \
    uint32_t _phase4c_target = (uint32_t)(xbox_va); \
    if (_phase4c_target == 0x800000FFu && !s_phase4cThreadEntered) { \
        phase4c_enter_first_title_thread((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000115u && s_phase4cThreadEntered) { \
        phase4c_enter_critical_section((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000126u && s_phase4cThreadEntered) { \
        phase4c_leave_critical_section((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x002295D6u && s_phase4cThreadEntered && !s_phase4cCallbackEntered) { \
        phase4c_enter_startup_callback((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x8000002Fu && s_phase4cCallbackEntered) { \
        phase4c_hal_register_shutdown_notification((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x8000006Bu && s_phase4cShutdownRegistrationHandled) { \
        phase4c_ke_initialize_dpc((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000071u && s_phase4cDpcInitialized) { \
        phase4c_ke_initialize_timer_ex((uint32_t)(saved_esp)); \
    } else { \
        phase4c_escape( \
            PHASE4C_BOUNDARY_ICALL_SAFE, \
            _phase4c_target, \
            (DWORD)(saved_esp)); \
    } \
} while (0)'''

    if old_macro not in text:
        raise SystemExit("[Phase4C-S] RECOMP_ICALL_SAFE marker changed")
    text = text.replace(old_macro, new_macro)

    text += r'''

static int s_phase4cThreadEntered;
static int s_phase4cCallbackEntered;
static int s_phase4cHardwareInfoThunkFixed;
static int s_phase4cKernelHeaderReady;
static int s_phase4cShutdownRegistrationHandled;
static uint32_t s_phase4cShutdownRegistrationVa;
static uint32_t s_phase4cShutdownRegisterRaw;
static int s_phase4cDpcInitialized;
static uint32_t s_phase4cDpcVa;
static uint32_t s_phase4cDpcRoutine;
static uint32_t s_phase4cDpcContext;
static int s_phase4cTimerInitialized;
static uint32_t s_phase4cTimerVa;
static uint32_t s_phase4cTimerTypeRaw;
static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va);

static void phase4c_enter_first_title_thread(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t handlePtr;
    uint32_t threadExtra;
    uint32_t kernelStack;
    uint32_t tlsSize;
    uint32_t threadIdPtr;
    uint32_t context1;
    uint32_t context2;
    uint32_t createSuspended;
    uint32_t debugStack;
    uint32_t startRoutine;
    recomp_func_t fn;
    char line[448];

    if (savedEsp != callEsp + 44u) {
        sprintf(
            line,
            "KERNEL FRAME MISMATCH: target=800000FF esp=%08X saved_esp=%08X delta=%u expected=44",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000FFu,
            savedEsp);
    }

    /* callEsp points at the translated synthetic CALL return slot. */
    handlePtr = GUEST_READ32(callEsp + 4u);
    threadExtra = GUEST_READ32(callEsp + 8u);
    kernelStack = GUEST_READ32(callEsp + 12u);
    tlsSize = GUEST_READ32(callEsp + 16u);
    threadIdPtr = GUEST_READ32(callEsp + 20u);
    context1 = GUEST_READ32(callEsp + 24u);
    context2 = GUEST_READ32(callEsp + 28u);
    createSuspended = GUEST_READ32(callEsp + 32u);
    debugStack = GUEST_READ32(callEsp + 36u);
    startRoutine = GUEST_READ32(callEsp + 40u);

    if (s_accessFault) {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000FFu,
            savedEsp);
    }

    sprintf(
        line,
        "PsCreateSystemThreadEx LIVE FRAME: handle_ptr=%08X extra=%u kstack=%u tls=%u tid_ptr=%08X ctx1=%08X ctx2=%08X suspended=%u debug=%u routine=%08X",
        (unsigned int)handlePtr,
        (unsigned int)threadExtra,
        (unsigned int)kernelStack,
        (unsigned int)tlsSize,
        (unsigned int)threadIdPtr,
        (unsigned int)context1,
        (unsigned int)context2,
        (unsigned int)createSuspended,
        (unsigned int)debugStack,
        (unsigned int)startRoutine);
    trace(line);

    if (startRoutine != 0x0022B43Fu ||
        context1 != 0x002295D6u ||
        context2 != 0x00000000u) {
        trace("FAIL: live title-thread handoff changed from Phase 4C-C hardware evidence");
        phase4c_escape(
            PHASE4C_BOUNDARY_THREAD_TARGET,
            startRoutine,
            savedEsp);
    }

    fn = phase4c_lookup_pack_func(startRoutine);
    if (!fn) {
        trace("FAIL: live StartRoutine is absent from the Phase 4C-S pack");
        phase4c_escape(
            PHASE4C_BOUNDARY_THREAD_TARGET,
            startRoutine,
            savedEsp);
    }

    if (handlePtr != 0u)
        GUEST_WRITE32(handlePtr, 0xBEEF0001u);
    if (threadIdPtr != 0u)
        GUEST_WRITE32(threadIdPtr, 1u);

    if (s_accessFault) {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            startRoutine,
            savedEsp);
    }

    trace("PASS: live ordinal-255 handoff matches Phase 4C-C; entering translated title thread");
    s_phase4cThreadEntered = 1;

    /*
     * Match the production bridge model:
     *   kernel_thunk_dispatch consumes the synthetic CALL return,
     *   bridge_PsCreateSystemThreadEx leaves the ten args in place while
     *   run_guest_thread_start pushes ctx2, ctx1, and a synthetic return.
     */
    g_esp += 4u;
    g_esp -= 4u; GUEST_WRITE32(g_esp, context2);
    g_esp -= 4u; GUEST_WRITE32(g_esp, context1);
    g_esp -= 4u; GUEST_WRITE32(g_esp, 0u);

    fn();

    /*
     * The first title thread should continue into another dynamic/kernel
     * boundary during this bounded gate. A direct return is diagnostic.
     */
    phase4c_escape(
        PHASE4C_BOUNDARY_THREAD_RETURN,
        startRoutine,
        savedEsp);
}
'''
    text += r'''

static void phase4c_enter_critical_section(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t criticalSection;
    char line[256];

    /*
     * Ordinal 277 is stdcall RtlEnterCriticalSection(PRTL_CRITICAL_SECTION).
     * Hardware 4C-E observed savedEsp-callEsp == 8:
     * one dword argument + the translated synthetic CALL return.
     */
    if (savedEsp != callEsp + 8u) {
        sprintf(
            line,
            "RtlEnterCriticalSection FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=8",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000115u,
            savedEsp);
    }

    criticalSection = GUEST_READ32(callEsp + 4u);
    if (s_accessFault) {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000115u,
            savedEsp);
    }

    sprintf(
        line,
        "RtlEnterCriticalSection LIVE FRAME: cs=%08X esp=%08X saved_esp=%08X",
        (unsigned int)criticalSection,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    /*
     * Match kernel_thunk_dispatch + bridge_RtlEnterCriticalSection:
     *   pop synthetic CALL return;
     *   consume the single stdcall argument;
     *   serialized guest execution means no host lock is taken;
     *   bridge leaves EAX as zero.
     */
    g_esp += 4u;
    g_eax = 0u;
    g_esp += 4u;

    if (g_esp != savedEsp) {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000115u,
            savedEsp);
    }

    trace("PASS: ordinal 277 RtlEnterCriticalSection matched maintained serialized-guest semantics");
}

static void phase4c_leave_critical_section(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t criticalSection;
    char line[256];

    if (savedEsp != callEsp + 8u) {
        sprintf(
            line,
            "RtlLeaveCriticalSection FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=8",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000126u,
            savedEsp);
    }

    criticalSection = GUEST_READ32(callEsp + 4u);
    if (s_accessFault) {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000126u,
            savedEsp);
    }

    sprintf(
        line,
        "RtlLeaveCriticalSection LIVE FRAME: cs=%08X esp=%08X saved_esp=%08X",
        (unsigned int)criticalSection,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    g_esp += 4u;
    g_eax = 0u;
    g_esp += 4u;

    if (g_esp != savedEsp) {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000126u,
            savedEsp);
    }

    trace("PASS: ordinal 294 RtlLeaveCriticalSection matched maintained serialized-guest semantics");
}

static void phase4c_hal_register_shutdown_notification(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t registrationVa;
    uint32_t registerRaw;
    uint32_t registerBoolean;
    char line[320];

    /*
     * Hardware Phase 4C-M observed:
     *   target   = 0x8000002F (ordinal 47)
     *   savedEsp - callEsp = 12
     *
     * Production ABI metadata defines 8 argument bytes:
     *   HalRegisterShutdownNotification(PVOID ShutdownRegistration,
     *                                   BOOLEAN Register)
     * plus the translated synthetic CALL return slot.
     */
    if (savedEsp != callEsp + 12u)
    {
        sprintf(
            line,
            "HalRegisterShutdownNotification FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=12",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x8000002Fu,
            savedEsp);
    }

    registrationVa = GUEST_READ32(callEsp + 4u);
    registerRaw = GUEST_READ32(callEsp + 8u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x8000002Fu,
            savedEsp);
    }

    registerBoolean = registerRaw & 0xFFu;

    sprintf(
        line,
        "HalRegisterShutdownNotification LIVE FRAME: registration=%08X register_raw=%08X register=%u esp=%08X saved_esp=%08X",
        (unsigned int)registrationVa,
        (unsigned int)registerRaw,
        (unsigned int)registerBoolean,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    /*
     * Production port semantics only log this registration. The shutdown
     * callback is never invoked by the recompiled runtime, so no guest-memory
     * mutation is required here.
     *
     * Match kernel_thunk_dispatch:
     *   pop synthetic return (4)
     *   bridge returns eax=0
     *   stdcall cleanup for two DWORD stack slots (8)
     */
    g_esp += 4u;
    g_eax = 0u;
    g_esp += 8u;

    if (g_esp != savedEsp)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x8000002Fu,
            savedEsp);
    }

    s_phase4cShutdownRegistrationVa = registrationVa;
    s_phase4cShutdownRegisterRaw = registerRaw;
    s_phase4cShutdownRegistrationHandled = 1;

    trace("PASS: ordinal 47 HalRegisterShutdownNotification matched production no-callback semantics");
}

static void phase4c_ke_initialize_dpc(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t dpcVa;
    uint32_t routineVa;
    uint32_t contextVa;
    DWORD i;
    char line[352];

    /*
     * Hardware Phase 4C-O observed target 0x8000006B (ordinal 107) with
     * savedEsp-callEsp == 16: three DWORD arguments plus synthetic return.
     */
    if (savedEsp != callEsp + 16u)
    {
        sprintf(
            line,
            "KeInitializeDpc FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=16",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x8000006Bu,
            savedEsp);
    }

    dpcVa = GUEST_READ32(callEsp + 4u);
    routineVa = GUEST_READ32(callEsp + 8u);
    contextVa = GUEST_READ32(callEsp + 12u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x8000006Bu,
            savedEsp);
    }

    sprintf(
        line,
        "KeInitializeDpc LIVE FRAME: dpc=%08X routine=%08X context=%08X esp=%08X saved_esp=%08X",
        (unsigned int)dpcVa,
        (unsigned int)routineVa,
        (unsigned int)contextVa,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    /*
     * Match production bridge_KeInitializeDpc exactly:
     * zero 32-byte Xbox KDPC, Type=0x13, DeferredRoutine at +12,
     * DeferredContext at +16.
     */
    for (i = 0u; i < 32u; i += 4u)
        GUEST_WRITE32(dpcVa + i, 0u);

    GUEST_WRITE16(dpcVa + 0u, 0x0013u);
    GUEST_WRITE32(dpcVa + 12u, routineVa);
    GUEST_WRITE32(dpcVa + 16u, contextVa);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x8000006Bu,
            savedEsp);
    }

    if (GUEST_READ16(dpcVa + 0u) != 0x0013u ||
        GUEST_READ32(dpcVa + 4u) != 0u ||
        GUEST_READ32(dpcVa + 8u) != 0u ||
        GUEST_READ32(dpcVa + 12u) != routineVa ||
        GUEST_READ32(dpcVa + 16u) != contextVa ||
        GUEST_READ32(dpcVa + 20u) != 0u ||
        GUEST_READ32(dpcVa + 24u) != 0u ||
        GUEST_READ32(dpcVa + 28u) != 0u ||
        s_accessFault)
    {
        trace("FAIL: KeInitializeDpc guest KDPC readback invariant failed");
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x8000006Bu,
            savedEsp);
    }

    /*
     * kernel_thunk_dispatch semantics:
     * pop synthetic return; bridge returns eax=0; stdcall cleans 12 args.
     */
    g_esp += 4u;
    g_eax = 0u;
    g_esp += 12u;

    if (g_esp != savedEsp)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x8000006Bu,
            savedEsp);
    }

    s_phase4cDpcVa = dpcVa;
    s_phase4cDpcRoutine = routineVa;
    s_phase4cDpcContext = contextVa;
    s_phase4cDpcInitialized = 1;

    trace("PASS: ordinal 107 KeInitializeDpc matched production guest-KDPC initialization semantics");
}

static void phase4c_ke_initialize_timer_ex(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t timerVa;
    uint32_t typeRaw;
    uint16_t expectedType;
    DWORD i;
    char line[352];

    if (savedEsp != callEsp + 12u)
    {
        sprintf(
            line,
            "KeInitializeTimerEx FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=12",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000071u,
            savedEsp);
    }

    timerVa = GUEST_READ32(callEsp + 4u);
    typeRaw = GUEST_READ32(callEsp + 8u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000071u,
            savedEsp);
    }

    sprintf(
        line,
        "KeInitializeTimerEx LIVE FRAME: timer=%08X type_raw=%08X type=%u esp=%08X saved_esp=%08X",
        (unsigned int)timerVa,
        (unsigned int)typeRaw,
        (unsigned int)(typeRaw & 1u),
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    /*
     * Production bridge_KeInitializeTimerEx guest-visible semantics:
     * zero the 40-byte Xbox KTIMER, then set DispatcherHeader.Type to
     * 0x08 + (TimerType & 1).
     */
    for (i = 0u; i < 40u; i += 4u)
        GUEST_WRITE32(timerVa + i, 0u);

    expectedType = (uint16_t)(0x08u + (typeRaw & 1u));
    GUEST_WRITE16(timerVa + 0u, expectedType);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000071u,
            savedEsp);
    }

    if (GUEST_READ16(timerVa + 0u) != expectedType ||
        GUEST_READ16(timerVa + 2u) != 0u ||
        GUEST_READ32(timerVa + 4u) != 0u ||
        GUEST_READ32(timerVa + 8u) != 0u ||
        GUEST_READ32(timerVa + 12u) != 0u ||
        GUEST_READ32(timerVa + 16u) != 0u ||
        GUEST_READ32(timerVa + 20u) != 0u ||
        GUEST_READ32(timerVa + 24u) != 0u ||
        GUEST_READ32(timerVa + 28u) != 0u ||
        GUEST_READ32(timerVa + 32u) != 0u ||
        GUEST_READ32(timerVa + 36u) != 0u ||
        s_accessFault)
    {
        trace("FAIL: KeInitializeTimerEx guest KTIMER readback invariant failed");
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000071u,
            savedEsp);
    }

    g_esp += 4u;
    g_eax = 0u;
    g_esp += 8u;

    if (g_esp != savedEsp)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000071u,
            savedEsp);
    }

    s_phase4cTimerVa = timerVa;
    s_phase4cTimerTypeRaw = typeRaw;
    s_phase4cTimerInitialized = 1;

    trace("PASS: ordinal 113 KeInitializeTimerEx matched production guest-KTIMER initialization semantics");
}

static void phase4c_direct_frontier(uint32_t target)
{
    char line[192];
    sprintf(
        line,
        "DIRECT FRONTIER: caller=%08X target=%08X esp=%08X",
        (unsigned int)phase4c_current_caller(),
        (unsigned int)target,
        (unsigned int)g_esp);
    trace(line);
    phase4c_escape(
        PHASE4C_BOUNDARY_DIRECT_FRONTIER,
        target,
        g_esp);
}

static void phase4c_enter_startup_callback(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t arg0;
    recomp_func_t fn;
    char line[256];

    if (savedEsp != callEsp + 8u) {
        sprintf(
            line,
            "Startup callback FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=8",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x002295D6u,
            savedEsp);
    }

    arg0 = GUEST_READ32(callEsp + 4u);
    if (s_accessFault) {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x002295D6u,
            savedEsp);
    }

    sprintf(
        line,
        "STARTUP CALLBACK LIVE FRAME: target=002295D6 arg0=%08X esp=%08X saved_esp=%08X",
        (unsigned int)arg0,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    fn = phase4c_lookup_pack_func(0x002295D6u);
    if (!fn) {
        trace("FAIL: hardware-confirmed startup callback is absent from Phase 4C-S pack");
        phase4c_escape(
            PHASE4C_BOUNDARY_THREAD_TARGET,
            0x002295D6u,
            savedEsp);
    }

    s_phase4cCallbackEntered = 1;
    trace("PASS: entering hardware-confirmed translated startup callback 002295D6");
    fn();

    phase4c_escape(
        PHASE4C_BOUNDARY_CALLBACK_RETURN,
        0x002295D6u,
        savedEsp);
}

static int phase4c_init_kernel_header_page(void)
{
    char line[256];

    memset(s_phase4cKernelHeaderPage, 0, sizeof(s_phase4cKernelHeaderPage));

    /* IMAGE_DOS_HEADER.e_magic = 'MZ'. */
    s_phase4cKernelHeaderPage[0x00] = 0x4Du;
    s_phase4cKernelHeaderPage[0x01] = 0x5Au;

    /* IMAGE_DOS_HEADER.e_lfanew = 0x80. */
    s_phase4cKernelHeaderPage[0x3C] = 0x80u;
    s_phase4cKernelHeaderPage[0x3D] = 0x00u;
    s_phase4cKernelHeaderPage[0x3E] = 0x00u;
    s_phase4cKernelHeaderPage[0x3F] = 0x00u;

    /* IMAGE_NT_HEADERS signature = 'PE\0\0'. */
    s_phase4cKernelHeaderPage[0x80] = 0x50u;
    s_phase4cKernelHeaderPage[0x81] = 0x45u;
    s_phase4cKernelHeaderPage[0x82] = 0x00u;
    s_phase4cKernelHeaderPage[0x83] = 0x00u;

    /* IMAGE_FILE_HEADER.Machine = IMAGE_FILE_MACHINE_I386. */
    s_phase4cKernelHeaderPage[0x84] = 0x4Cu;
    s_phase4cKernelHeaderPage[0x85] = 0x01u;

    /*
     * IMAGE_FILE_HEADER.NumberOfSections = 0. Startup/cache probing therefore
     * finds no INIT section and exits the scan without requiring kernel code.
     */
    s_phase4cKernelHeaderPage[0x86] = 0x00u;
    s_phase4cKernelHeaderPage[0x87] = 0x00u;

    if (GUEST_READ16(0x80010000u) != 0x5A4Du ||
        GUEST_READ32(0x8001003Cu) != 0x00000080u ||
        GUEST_READ32(0x80010080u) != 0x00004550u ||
        GUEST_READ16(0x80010084u) != 0x014Cu ||
        GUEST_READ16(0x80010086u) != 0u ||
        s_accessFault)
    {
        trace("FAIL: synthetic xboxkrnl PE-header readback invariant failed");
        return 0;
    }

    s_phase4cKernelHeaderReady = 1;
    sprintf(
        line,
        "KERNEL HEADER MODEL: base=80010000 e_lfanew=00000080 sections=0 size=4096");
    trace(line);
    trace("PASS: synthetic xboxkrnl PE header is readable through the fenced kernel-image page");
    return 1;
}

static uint32_t phase4c_startup_data_va_for_ordinal(DWORD ordinal)
{
    switch (ordinal)
    {
    case 156u: return 0x0087E020u; /* KeTickCount */
    case 322u: return 0x0087E000u; /* XboxHardwareInfo */
    case 324u: return 0x0087E010u; /* XboxKrnlVersion */
    default:   return 0u;
    }
}

static int phase4c_fix_startup_data_thunks(void)
{
    DWORD i;
    DWORD relocated = 0u;
    DWORD seen156 = 0u;
    DWORD seen322 = 0u;
    DWORD seen324 = 0u;
    DWORD sentinel;
    char line[320];

    for (i = 0u; i < 111u; ++i)
    {
        DWORD va = 0x002DBCE0u + i * 4u;
        DWORD value = GUEST_READ32(va);
        DWORD ordinal;
        DWORD dataVa;

        if (s_accessFault)
        {
            trace("FAIL: could not read retail kernel thunk table");
            return 0;
        }

        if ((value & 0x80000000u) == 0u)
            continue;

        ordinal = value & 0x7FFFFFFFu;
        dataVa = phase4c_startup_data_va_for_ordinal(ordinal);
        if (!dataVa)
            continue;

        GUEST_WRITE32(va, dataVa);
        if (s_accessFault)
        {
            trace("FAIL: could not write startup data-thunk relocation");
            return 0;
        }

        if (ordinal == 156u) ++seen156;
        if (ordinal == 322u) ++seen322;
        if (ordinal == 324u) ++seen324;
        ++relocated;

        sprintf(
            line,
            "DATA THUNK FIXUP: ordinal=%u slot=%08X old=%08X new=%08X",
            (unsigned int)ordinal,
            (unsigned int)va,
            (unsigned int)value,
            (unsigned int)dataVa);
        trace(line);
    }

    sentinel = GUEST_READ32(0x002DBCE0u + 111u * 4u);
    if (s_accessFault)
    {
        trace("FAIL: could not read retail kernel thunk terminator");
        return 0;
    }

    if (sentinel != 0u)
    {
        sprintf(
            line,
            "FAIL: expected zero thunk terminator after 111 imports, got %08X",
            (unsigned int)sentinel);
        trace(line);
        return 0;
    }

    if (seen156 != 1u || seen322 != 1u || seen324 != 1u || relocated != 3u)
    {
        sprintf(
            line,
            "FAIL: startup data-thunk counts KeTickCount=%u XboxHardwareInfo=%u XboxKrnlVersion=%u total=%u",
            (unsigned int)seen156,
            (unsigned int)seen322,
            (unsigned int)seen324,
            (unsigned int)relocated);
        trace(line);
        return 0;
    }

    if (GUEST_READ32(0x0087E000u) != 0u ||
        GUEST_READ8(0x0087E004u) != 0xA1u ||
        GUEST_READ8(0x0087E005u) != 0xB1u ||
        GUEST_READ16(0x0087E010u) != 1u ||
        GUEST_READ16(0x0087E012u) != 0u ||
        GUEST_READ16(0x0087E014u) != 5849u ||
        GUEST_READ16(0x0087E016u) != 0u ||
        s_accessFault)
    {
        trace("FAIL: startup kernel-data readback invariant failed");
        return 0;
    }

    s_phase4cHardwareInfoThunkFixed = 1;
    trace("PASS: startup data imports 156/322/324 point at initialized guest kernel data");
    return 1;
}

'''
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--entry-report", type=Path, required=True)
    ap.add_argument("--thread-report", type=Path, required=True)
    ap.add_argument("--phase3n-template", type=Path, required=True)
    ap.add_argument("--phase2e-source", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load_base(args.base_emitter)

    entry_report = json.loads(args.entry_report.read_text(encoding="utf-8-sig"))
    thread_report = json.loads(args.thread_report.read_text(encoding="utf-8-sig"))

    if (
        entry_report.get("phase") != "4C-A"
        or entry_report.get("structural_pass") is not True
    ):
        raise SystemExit("[Phase4C-S] Phase 4C-A report is not a PASS")

    if (
        thread_report.get("phase") != "4C-D"
        or thread_report.get("structural_pass") is not True
    ):
        raise SystemExit("[Phase4C-S] Phase 4C-D report is not a PASS")

    observed = thread_report.get("hardware_observed", {})
    expected_observed = {
        "start_routine": "0x0022B43F",
        "context1": "0x002295D6",
        "context2": "0x00000000",
        "ps_create_system_thread_ex_target": "0x800000FF",
        "frame_bytes": 44,
    }
    for key, value in expected_observed.items():
        if observed.get(key) != value:
            raise SystemExit(
                f"[Phase4C-S] hardware observation mismatch for {key}: "
                f"expected {value!r}, got {observed.get(key)!r}"
            )

    root_va = int(str(entry_report["entry"]), 0)
    if root_va != 0x0022964A:
        raise SystemExit(
            f"[Phase4C-S] unexpected XBE entry 0x{root_va:08X}"
        )

    thread_root = int(str(thread_report["closure"]["entry"]), 0)
    if thread_root != THREAD_START:
        raise SystemExit(
            f"[Phase4C-S] unexpected thread root 0x{thread_root:08X}"
        )

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)

    entry_members = {
        int(str(row["address"]), 0)
        for row in entry_report["closure"]["members"]
    }
    thread_members = {
        int(str(row["address"]), 0)
        for row in thread_report["closure"]["members"]
    }
    callback_members = set(
        bounded_callback_members(base, STARTUP_CALLBACK, generated)
    )
    promoted_direct_members = {LIVE_DIRECT_FRONTIER_TARGET, LIVE_DIRECT_FRONTIER_TARGET_2, LIVE_DIRECT_FRONTIER_TARGET_3, LIVE_DIRECT_FRONTIER_TARGET_4}
    member_vas = sorted(
        entry_members | thread_members | callback_members | promoted_direct_members
    )
    packed_vas = set(member_vas)

    missing_generated = [va for va in member_vas if va not in generated]
    if missing_generated:
        raise SystemExit(
            "[Phase4C-S] generated body missing for packed member(s): "
            + ", ".join(f"0x{va:08X}" for va in missing_generated)
        )

    root_row = by_va.get(root_va)
    if root_row is None:
        raise SystemExit("[Phase4C-S] XBE entry absent from function inventory")
    root_name = root_row["name"]

    bodies = []
    rendered_by_va = {}
    forward_decls = []
    translated_names = set()
    direct_frontier_targets = set()

    for va in member_vas:
        row = generated[va]
        name = row["name"]
        translated_names.add(name)
        forward_decls.append(f"static void {name}(void);")
        rendered = base.localize_and_instrument(row["source"], name)
        rendered, frontier = rewrite_direct_frontier(
            base, rendered, generated, packed_vas
        )
        direct_frontier_targets.update(frontier)
        rendered_by_va[va] = rendered
        bodies.append(rendered)

    pack_guest_bytes = 0
    for va in member_vas:
        raw_size = by_va.get(va, {}).get("size", 0)
        try:
            pack_guest_bytes += int(str(raw_size), 0)
        except (TypeError, ValueError):
            pass

    pack_source_bytes = sum(
        len(generated[va]["source"].encode("utf-8"))
        for va in member_vas
    )

    template = args.phase3n_template.read_text(encoding="utf-8")
    marker = "/*__P3NB_FORWARD_DECLS__*/"
    marker_index = template.find(marker)
    if marker_index < 0:
        raise SystemExit("[Phase4C-S] Phase-3N support donor marker missing")

    support = template[:marker_index]
    replacements = {
        "__P3NB_ROOT_VA__": f"0x{root_va:08X}u",
        "__P3NB_MEMBER_COUNT__": str(len(member_vas)),
        "__P3NB_DEPTH__": str(max(
            int(entry_report["closure"]["max_direct_depth"]),
            int(thread_report["closure"]["max_direct_depth"]),
        )),
        "__P3NB_SCALE_COUNT__": str(len(member_vas)),
        "__P3NB_SCALE_GUEST_BYTES__": str(pack_guest_bytes),
        "__P3NB_SCALE_SOURCE_BYTES__": str(pack_source_bytes),
        "__P3NB_MEMBER_VAS__": ", ".join(
            f"0x{va:08X}u" for va in member_vas
        ),
    }
    for token, value in replacements.items():
        support = support.replace(token, value)

    support = support.replace("[Merc360:P3N]", "[Merc360:P4C]")
    support = instrument_first_fault_support(support)
    support = instrument_kernel_header_page(support)

    boundary = phase4c_s_boundary(base)

    supplied = base.support_symbols(support + boundary)
    supplied.update(translated_names)
    supplied.update({
        "sub_0022B150",
        "sub_0022B178",
        "sub_0022DDA4",
        "sub_0022E51F",
        "phase4c_lookup_pack_func",
        "phase4c_enter_first_title_thread",
        "phase4c_enter_critical_section",
        "phase4c_leave_critical_section",
        "phase4c_enter_startup_callback",
        "phase4c_hal_register_shutdown_notification",
        "phase4c_ke_initialize_dpc",
        "phase4c_ke_initialize_timer_ex",
        "phase4c_direct_frontier",
        "phase4c_fix_startup_data_thunks",
        "phase4c_init_kernel_header_page",
    })

    unknown = {}
    for va in member_vas:
        row = generated[va]
        rendered = rendered_by_va[va]
        calls = set(base.CALL_RE.findall(base.mask_noncode(rendered)))
        calls.discard(row["name"])
        local_supplied = set(supplied)
        local_supplied.update(base.DEFINE_RE.findall(rendered))
        missing = sorted(
            name for name in calls
            if name not in local_supplied and name not in base.STANDARD_CALLS
        )
        if missing:
            unknown[f"0x{va:08X} {row['name']}"] = missing

    args.out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "phase": "4C-S",
        "build_tag": "P4C-DIRECT30060-20261019-A",
        "entry": f"0x{root_va:08X}",
        "thread_start": f"0x{THREAD_START:08X}",
        "thread_context1": f"0x{THREAD_CTX1:08X}",
        "thread_context2": f"0x{THREAD_CTX2:08X}",
        "startup_callback": f"0x{STARTUP_CALLBACK:08X}",
        "promoted_direct_frontier_target": f"0x{LIVE_DIRECT_FRONTIER_TARGET:08X}",
        "promoted_direct_frontier_target_2": f"0x{LIVE_DIRECT_FRONTIER_TARGET_2:08X}",
        "promoted_direct_frontier_target_3": f"0x{LIVE_DIRECT_FRONTIER_TARGET_3:08X}",
        "promoted_direct_frontier_target_4": f"0x{LIVE_DIRECT_FRONTIER_TARGET_4:08X}",
        "continued_kernel_call_113": {
            "target": "0x80000071",
            "ordinal": 113,
            "name": "KeInitializeTimerEx",
            "arg_bytes": 8,
            "frame_bytes": 12,
            "production_semantics": "zero 40-byte KTIMER; Type=0x08+(TimerType&1)",
        },
        "continued_kernel_call_107": {
            "target": "0x8000006B",
            "ordinal": 107,
            "name": "KeInitializeDpc",
            "arg_bytes": 12,
            "frame_bytes": 16,
            "production_semantics": "zero 32-byte KDPC; Type=0x13; routine +12; context +16",
        },
        "continued_kernel_call": {
            "target": "0x8000002F",
            "ordinal": 47,
            "name": "HalRegisterShutdownNotification",
            "arg_bytes": 8,
            "frame_bytes": 12,
            "production_semantics": "log registration; callback never invoked",
        },
        "kernel_header_model": {
            "base": "0x80010000",
            "size": 4096,
            "e_lfanew": "0x80",
            "number_of_sections": 0,
            "purpose": "bounded startup kernel-image introspection surface",
        },
        "promoted_direct_members": [
            f"0x{va:08X}" for va in sorted(promoted_direct_members)
        ],
        "diagnostic_goal": "execute_promoted_00230060_then_stop_next_boundary",
        "data_thunk_fixups": [
            {"ordinal": 156, "name": "KeTickCount", "guest_data_va": "0x0087E020"},
            {"ordinal": 322, "name": "XboxHardwareInfo", "guest_data_va": "0x0087E000"},
            {"ordinal": 324, "name": "XboxKrnlVersion", "guest_data_va": "0x0087E010"},
        ],
        "kernel_thunk_va": "0x002DBCE0",
        "import_count": 111,
        "callback_direct_depth": CALLBACK_DIRECT_DEPTH,
        "callback_members": len(callback_members),
        "callback_new_members": len(callback_members - entry_members - thread_members),
        "direct_frontier_targets": [f"0x{va:08X}" for va in sorted(direct_frontier_targets)],
        "continued_kernel_targets": [
            {"target": "0x80000115", "ordinal": 277, "name": "RtlEnterCriticalSection", "frame_bytes": 8},
            {"target": "0x80000126", "ordinal": 294, "name": "RtlLeaveCriticalSection", "frame_bytes": 8},
        ],
        "entry_members": len(entry_members),
        "thread_members": len(thread_members),
        "pack_members": len(member_vas),
        "new_members_over_entry": len(thread_members - entry_members),
        "pack_guest_bytes": pack_guest_bytes,
        "pack_source_bytes": pack_source_bytes,
        "unknown_direct_helpers": unknown,
        "members": [f"0x{va:08X}" for va in member_vas],
    }
    (args.out_dir / "phase4c-r-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    if unknown:
        print("[Phase4C-S] unsupported direct helper calls found:")
        for owner, names in unknown.items():
            print(f"[Phase4C-S]   {owner}: {', '.join(names)}")
        raise SystemExit(
            "[Phase4C-S] refusing to emit first-thread execution XEX with "
            "unresolved direct helper dependencies"
        )

    env_source = base.build_env_source(
        args.phase2e_source.read_text(encoding="utf-8")
    ).replace("PHASE 4C-B", "PHASE 4C-S")
    for stale_phase in (
        "PHASE 4C-N",
        "PHASE 4C-O",
        "PHASE 4C-P",
    ):
        env_source = env_source.replace(stale_phase, "PHASE 4C-S")
    env_source += """
extern "C" DWORD phase4c_env_build_cookie(void)
{
    return 0x50435331u; /* PCS1 */
}
"""
    for stale_phase in (
        "PHASE 4C-N",
        "PHASE 4C-O",
    ):
        env_source = env_source.replace(stale_phase, "PHASE 4C-S")

    driver = base.driver_source(root_name, root_va, len(member_vas))
    driver = driver.replace(
        "P4C-STARTUP-20261019-A",
        "P4C-DIRECT30060-20261019-A",
    )
    driver = driver.replace(
        "Policy: execute the real retail entry and stop at the first live dynamic/indirect boundary",
        "Policy: preserve proven startup path and execute promoted direct target 0022C5A4",
    )
    driver = driver.replace("PHASE 4C-B", "PHASE 4C-S")
    cookie_decl = 'extern "C" DWORD phase4c_env_entry(void);\n'
    if cookie_decl not in driver:
        raise SystemExit("[Phase4C-S] env-entry declaration marker changed")
    driver = driver.replace(
        cookie_decl,
        cookie_decl + 'extern "C" DWORD phase4c_env_build_cookie(void);\n',
        1,
    )
    env_pass_marker = """    trace("PHASE 4C-S ENVIRONMENT RESULT: PASS");

    g_ram = phase4c_env_guest_base();"""
    if env_pass_marker not in driver:
        raise SystemExit("[Phase4C-S] environment PASS marker changed")
    driver = driver.replace(
        env_pass_marker,
        """    if (phase4c_env_build_cookie() != 0x50435331u)
    {
        trace("FAIL: Phase 4C-S environment build cookie mismatch");
        goto shutdown_env;
    }
    trace("PASS: Phase 4C-S main/env build cookie matches");
    trace("PHASE 4C-S ENVIRONMENT RESULT: PASS");

    g_ram = phase4c_env_guest_base();""",
        1,
    )
    driver = driver.replace(
        "    s_accessFault = 0;\n",
        "    s_accessFault = 0;\n"
        "    s_phase4cFaultAddress = 0u;\n"
        "    s_phase4cFaultWidth = 0u;\n"
        "    s_phase4cFaultWrite = 0u;\n"
        "    s_phase4cFaultEscapeArmed = 0;\n",
        1,
    )
    driver = driver.replace(
        "    phase4c_reset_architecture();\n",
        "    phase4c_reset_architecture();\n\n"
        "    if (!phase4c_fix_startup_data_thunks())\n"
        "    {\n"
        "        trace(\"PHASE 4C-S STARTUP DATA-THUNK PREP RESULT: FAIL\");\n"
        "        goto shutdown_env;\n"
        "    }\n"
        "    trace(\"PHASE 4C-S STARTUP DATA-THUNK PREP RESULT: PASS\");\n"
        "    trace(\"PASS: hardware-observed direct target 0022C47B is packed for translated execution\");\n"
        "    if (!phase4c_init_kernel_header_page())\n"
        "    {\n"
        "        trace(\"PHASE 4C-S KERNEL HEADER PREP RESULT: FAIL\");\n"
        "        goto shutdown_env;\n"
        "    }\n"
        "    trace(\"PHASE 4C-S KERNEL HEADER PREP RESULT: PASS\");\n"
        "    trace(\"PASS: ordinal 47 HalRegisterShutdownNotification continuation armed\");\n"
        "    trace(\"PASS: hardware-observed direct target 0022F128 is packed for translated execution\");\n"
        "    trace(\"PASS: ordinal 107 KeInitializeDpc continuation armed\");\n"
        "    trace(\"PASS: ordinal 113 KeInitializeTimerEx continuation armed\");\n"
        "    trace(\"PASS: hardware-observed direct target 0022C5A4 is packed for translated execution\");\n",
        1,
    )
    driver = driver.replace(
        '    case PHASE4C_BOUNDARY_HEAP_EXHAUSTED: return "HEAP_EXHAUSTED";',
        '    case PHASE4C_BOUNDARY_HEAP_EXHAUSTED: return "HEAP_EXHAUSTED";\n'
        '    case PHASE4C_BOUNDARY_THREAD_TARGET: return "THREAD_TARGET";\n'
        '    case PHASE4C_BOUNDARY_KERNEL_FRAME: return "KERNEL_FRAME";\n'
        '    case PHASE4C_BOUNDARY_THREAD_RETURN: return "THREAD_RETURN";\n'
        '    case PHASE4C_BOUNDARY_CALLBACK_RETURN: return "CALLBACK_RETURN";\n'
        '    case PHASE4C_BOUNDARY_DIRECT_FRONTIER: return "DIRECT_FRONTIER";',
    )

    old_return_pass = f"""        boundedPass =
            !s_accessFault &&
            s_traceCount > 0u &&
            s_trace[0] == 0x{root_va:08X}u;"""
    if old_return_pass not in driver:
        raise SystemExit("[Phase4C-S] entry-return PASS marker changed")
    driver = driver.replace(
        old_return_pass,
        """        boundedPass = 0;
        trace("FAIL: startup path returned instead of reaching a post-thread boundary");"""
    )

    old_escape_pass = f"""        boundedPass =
            s_phase4cBoundaryKind >= PHASE4C_BOUNDARY_ICALL &&
            s_phase4cBoundaryKind <= PHASE4C_BOUNDARY_ITAIL_SAFE &&
            !s_accessFault &&
            s_traceCount > 0u &&
            s_trace[0] == 0x{root_va:08X}u;"""
    new_escape_pass = f"""        if (s_accessFault)
        {{
            sprintf(
                line,
                "FAULT ACCESS: %s width=%u guest=%08X translated_caller=%08X",
                s_phase4cFaultWrite ? "WRITE" : "READ",
                (unsigned int)s_phase4cFaultWidth,
                (unsigned int)s_phase4cFaultAddress,
                (unsigned int)s_phase4cBoundaryCaller);
            trace(line);
        }}

        boundedPass =
            s_phase4cHardwareInfoThunkFixed &&
            s_phase4cKernelHeaderReady &&
            s_phase4cShutdownRegistrationHandled &&
            s_phase4cDpcInitialized &&
            s_phase4cTimerInitialized &&
            s_phase4cCallbackEntered &&
            s_traceCount > 0u &&
            s_trace[0] == 0x{root_va:08X}u &&
            (
                (
                    s_phase4cBoundaryKind == PHASE4C_BOUNDARY_GUEST_FAULT &&
                    s_accessFault &&
                    s_phase4cFaultWidth != 0u &&
                    s_phase4cFaultAddress != 0x80000142u &&
                    s_phase4cFaultAddress != 0x80000148u &&
                    s_phase4cFaultAddress != 0x8001003Cu
                ) ||
                (
                    !s_accessFault &&
                    (
                        ((s_phase4cBoundaryKind >= PHASE4C_BOUNDARY_ICALL &&
                          s_phase4cBoundaryKind <= PHASE4C_BOUNDARY_ITAIL_SAFE) &&
                         s_phase4cBoundaryTarget != 0x8000002Fu &&
                         s_phase4cBoundaryTarget != 0x8000006Bu &&
                         s_phase4cBoundaryTarget != 0x80000071u) ||
                        (s_phase4cBoundaryKind == PHASE4C_BOUNDARY_DIRECT_FRONTIER &&
                         s_phase4cBoundaryTarget != 0x0022C47Bu &&
                         s_phase4cBoundaryTarget != 0x0022F128u &&
                         s_phase4cBoundaryTarget != 0x0022C5A4u &&
                         s_phase4cBoundaryTarget != 0x00230060u)
                    )
                )
            );"""
    if old_escape_pass not in driver:
        raise SystemExit("[Phase4C-S] boundary PASS marker changed")
    driver = driver.replace(old_escape_pass, new_escape_pass)

    result_marker = "PHASE 4C-S BOUNDED REAL STARTUP RESULT"
    if result_marker not in driver:
        raise SystemExit("[Phase4C-S] generated result label marker changed")
    driver = driver.replace(
        result_marker,
        "PHASE 4C-S PROMOTED 30060 RESULT",
        1,
    )
    arm_marker = f"""    if (escaped == 0)
    {{
        {root_name}();"""
    if arm_marker not in driver:
        raise SystemExit("[Phase4C-S] setjmp execution-arm marker changed")
    driver = driver.replace(
        arm_marker,
        f"""    if (escaped == 0)
    {{
        s_phase4cFaultEscapeArmed = 1;
        {root_name}();""",
        1,
    )

    escape_marker = """    else
    {
        sprintf("""
    if escape_marker not in driver:
        raise SystemExit("[Phase4C-S] setjmp escape marker changed")
    driver = driver.replace(
        escape_marker,
        """    else
    {
        s_phase4cFaultEscapeArmed = 0;
        sprintf(""",
        1,
    )

    generated_main = (
        support
        + "\n"
        + boundary
        + "\n\n/* Phase 4C-S: proven startup path + bounded startup callback frontier */\n"
        + "\n".join(forward_decls)
        + "\n\n"
        + pack_lookup_source(member_vas, generated)
        + "\n#pragma optimize(\"\", off)\n"
        + "\n\n".join(bodies)
        + "\n#pragma optimize(\"\", on)\n"
        + driver
    )

    (args.out_dir / "main.cpp").write_text(generated_main, encoding="utf-8")
    (args.out_dir / "phase4c_env.cpp").write_text(env_source, encoding="utf-8")

    print("[Phase4C-S] PROMOTED 30060 CONTINUATION PACKAGE READY")
    print(
        f"[Phase4C-S] Entry closure={len(entry_members)} bodies; "
        f"thread closure={len(thread_members)} bodies; "
        f"union={len(member_vas)} bodies"
    )
    print(
        f"[Phase4C-S] Callback depth-{CALLBACK_DIRECT_DEPTH} slice: "
        f"{len(callback_members)} bodies; "
        f"new beyond proven entry/thread pack="
        f"{len(callback_members - entry_members - thread_members)}"
    )
    print(
        f"[Phase4C-S] Static direct frontier targets: "
        f"{len(direct_frontier_targets)}"
    )
    print(
        "[Phase4C-S] Previously promoted hardware direct target: 0x0022C47B"
    )
    print(
        "[Phase4C-S] Newly promoted hardware direct target: 0x0022F128 "
        "(only this new frontier member is added)"
    )
    print(
        "[Phase4C-S] Continued hardware kernel target: "
        "0x8000002F ordinal 47 HalRegisterShutdownNotification"
    )
    print(
        "[Phase4C-S] Continued hardware kernel target: "
        "0x8000006B ordinal 107 KeInitializeDpc"
    )
    print(
        "[Phase4C-S] Continued hardware kernel target: "
        "0x80000071 ordinal 113 KeInitializeTimerEx"
    )
    print(
        "[Phase4C-S] Newly promoted hardware direct target: "
        "0x0022C5A4 (previously promoted)"
    )
    print(
        "[Phase4C-S] Newly promoted hardware direct target: "
        "0x00230060 (only this new frontier member is added)"
    )
    print(
        "[Phase4C-S] Hardware-observed handoff: "
        "StartRoutine=0x0022B43F ctx1=0x002295D6 ctx2=0x00000000"
    )
    print(f"[Phase4C-S] main: {args.out_dir / 'main.cpp'}")
    print(f"[Phase4C-S] env:  {args.out_dir / 'phase4c_env.cpp'}")
    print(
        "[Phase4C-S] Runtime policy: preserve the proven startup path, keep "
        "ordinal 113 continuation live, execute hardware-observed 0x00230060, "
        "and stop at the next dynamic/deeper-direct frontier or new guest fault."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

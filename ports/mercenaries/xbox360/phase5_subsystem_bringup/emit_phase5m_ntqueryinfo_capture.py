"""Phase 5M: capture live NtQueryInformationFile ordinal 211.

Phase 5L passed on real Xbox 360 hardware. The reviewed maintained
SetLastError root 0x0022B178 executed with value 0x00000490, startup continued
through the XBE image-section path, opened TitleMeta.xbx as tagged guest handle
0x48000002, and reached ICALL_SAFE target 0x800000D3 with fault=0 and a
54-entry translated trace.

0x800000D3 is original-Xbox kernel ordinal 211, NtQueryInformationFile.
The observed saved-ESP delta is 24 bytes, exactly five stdcall arguments plus
the translated synthetic return. Phase 5M captures the exact live handle,
IO_STATUS_BLOCK pointer, output buffer, length, and FILE_INFORMATION_CLASS,
then stops at an explicit FILE_INFORMATION boundary. No file-information
payload is fabricated until hardware identifies the requested class.
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
LIVE_DIRECT_FRONTIER_TARGET_5 = 0x0022F0FB
LIVE_DIRECT_FRONTIER_TARGET_6 = 0x0022D980
LIVE_DIRECT_FRONTIER_TARGET_7 = 0x00238C00
LIVE_DIRECT_FRONTIER_TARGET_8 = 0x0022D431
LIVE_DIRECT_FRONTIER_TARGET_9 = 0x0022CA2B
LIVE_DIRECT_FRONTIER_TARGET_10 = 0x0022C8EA
LIVE_DIRECT_FRONTIER_TARGET_11 = 0x0022CEEE
LIVE_DIRECT_FRONTIER_TARGET_12 = 0x0022C1C0
LIVE_DIRECT_FRONTIER_TARGET_13 = 0x002370B8
LIVE_DIRECT_FRONTIER_TARGET_14 = 0x0022BE8C
LIVE_DIRECT_FRONTIER_TARGET_15 = 0x0022F026
LIVE_DIRECT_FRONTIER_TARGET_16 = 0x0022B178
PROMOTED_CLOSURE_DEPTH = 0
PROMOTED_CLOSURE_CAP = 1
KERNEL_HEADER_BASE = 0x80010000
KERNEL_HEADER_SIZE = 0x1000
KERNEL_HEADER_ELFANEW = 0x80


def load_base(path: Path):
    spec = importlib.util.spec_from_file_location("phase4c_b_emitter", path)
    if spec is None or spec.loader is None:
        raise SystemExit("[Phase5M] could not load Phase 4C-B emitter")
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
        raise SystemExit("[Phase5M] s_accessFault declaration marker changed")
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
        raise SystemExit("[Phase5M] guest accessor insertion marker changed")
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
                "[Phase5M] exact guest accessor body marker changed"
            )
        support = support.replace(old, new, 1)

    # Only the assignment inside phase4c_note_access_fault may remain.
    if support.count("s_accessFault = 1;") != 1:
        raise SystemExit(
            "[Phase5M] residual direct fault assignments remain"
        )

    return support

def instrument_kernel_header_page(support):
    decl = "static BYTE* g_ram = NULL;"
    expanded = """static BYTE s_phase4cKernelHeaderPage[0x1000u];
#define PHASE4C_VM_PAGE_SHIFT 12u
#define PHASE4C_VM_PAGE_SIZE  0x1000u
#define PHASE4C_VM_PAGE_COUNT (RAM_SIZE / PHASE4C_VM_PAGE_SIZE)
#define PHASE4C_VM_PAGE_UNMANAGED 0u
#define PHASE4C_VM_PAGE_RESERVED  1u
#define PHASE4C_VM_PAGE_COMMITTED 2u
static BYTE s_phase4cVmPageState[PHASE4C_VM_PAGE_COUNT];
static DWORD s_phase4cVmPageProtect[PHASE4C_VM_PAGE_COUNT];
static BYTE* g_ram = NULL;"""
    if decl not in support:
        raise SystemExit("[Phase5M] guest RAM declaration marker changed")
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
     * separate from title RAM; Phase 5M supplies a minimal synthetic PE
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

    /*
     * Only pages explicitly owned by NtAllocateVirtualMemory reservations
     * acquire Phase-4C VM state. A reserved/uncommitted page behaves as
     * inaccessible until a later MEM_COMMIT transitions it to committed.
     */
    {
        DWORD firstPage = offset >> PHASE4C_VM_PAGE_SHIFT;
        DWORD lastPage =
            (offset + width - 1u) >> PHASE4C_VM_PAGE_SHIFT;
        DWORD page;
        for (page = firstPage; page <= lastPage; ++page)
        {
            if (s_phase4cVmPageState[page] ==
                PHASE4C_VM_PAGE_RESERVED)
                return NULL;
        }
    }

    return g_ram + offset;
}"""
    if old_ptr not in support:
        raise SystemExit("[Phase5M] guest_ptr body marker changed")
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
                f"[Phase5M] callback dependency 0x{va:08X} "
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


def bounded_promoted_members(base, root_va, generated, max_depth, member_cap):
    name_to_va = {row["name"]: va for va, row in generated.items()}
    queue = [(root_va, 0)]
    seen = set()

    while queue:
        va, depth = queue.pop(0)
        if va in seen:
            continue
        if va not in generated:
            raise SystemExit(
                f"[Phase5M] promoted dependency 0x{va:08X} "
                "is absent from generated tree"
            )
        seen.add(va)
        if len(seen) >= member_cap or depth >= max_depth:
            continue

        row = generated[va]
        calls = set(base.CALL_RE.findall(base.mask_noncode(row["source"])))
        deps = sorted(
            name_to_va[name]
            for name in calls
            if name in name_to_va and name_to_va[name] not in seen
        )
        for dep in deps:
            if len(seen) + len(queue) >= member_cap:
                break
            queue.append((dep, depth + 1))

    return sorted(seen)


def rewrite_direct_frontier(base, source, generated, packed_vas):
    """
    Fence every translated x86 direct CALL whose retail target is outside the
    current pack.

    The lifter emits:
        PUSH32(esp, 0); sub_XXXXXXXX(); /* call 0xXXXXXXXX */

    Older Phase-4C gates resolved the callee name through the generated-body
    table first. That incorrectly rejected valid direct targets represented by
    unresolved/mid-function stubs, because those names had no generated body
    and later appeared as "unknown helpers". The embedded retail target is the
    authoritative control-flow identity, so use it directly.
    """
    frontier = []

    direct_call_re = re.compile(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\);"
        r"(\s*/\*\s*call\s+0x([0-9A-Fa-f]{8})\s*\*/)"
    )

    def fence_match(match):
        va = int(match.group(3), 16)
        if va in packed_vas:
            return match.group(0)
        frontier.append(va)
        return (
            f"phase4c_direct_frontier(0x{va:08X}u);"
            f"{match.group(2)}"
        )

    source = direct_call_re.sub(fence_match, source)

    # Retain the generated-name fallback for older translated bodies that may
    # not carry the explicit /* call 0x... */ annotation.
    name_to_va = {row["name"]: va for va, row in generated.items()}
    calls = set(base.CALL_RE.findall(base.mask_noncode(source)))
    for name in sorted(calls):
        va = name_to_va.get(name)

        # Unresolved direct call stubs are intentionally named sub_XXXXXXXX by
        # the recompiler. They may not exist in the generated-body table, but
        # the symbol itself still carries the authoritative retail target.
        # Fence those targets instead of rejecting the entire hardware gate as
        # an "unknown helper".
        if va is None:
            unresolved = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
            if unresolved:
                va = int(unresolved.group(1), 16)

        if va is None or va in packed_vas:
            continue

        pattern = r"\b" + re.escape(name) + r"\(\);"
        replacement = f"phase4c_direct_frontier(0x{va:08X}u);"
        source, count = re.subn(pattern, replacement, source)
        if count:
            frontier.append(va)

    return source, sorted(set(frontier))


def phase5a_boundary(base):
    text = base.boundary_support()

    # Phase 5M state is consumed by the support-owned B178 body below. Declare
    # it before the donor body so the XDK compiler sees the symbols before
    # their first use.
    text = (
        "static uint32_t s_phase5mXboxLastError;\n"
        "static uint32_t s_phase5mSetLastErrorCount;\n"
        "static uint32_t s_phase5mNtQueryInformationFileCaptureCount;\n"
        "static uint32_t s_phase5mNtQueryInformationFileHandle;\n"
        "static uint32_t s_phase5mNtQueryInformationFileIoStatus;\n"
        "static uint32_t s_phase5mNtQueryInformationFileBuffer;\n"
        "static uint32_t s_phase5mNtQueryInformationFileLength;\n"
        "static uint32_t s_phase5mNtQueryInformationFileClass;\n\n"
        + text
    )

    # B178 is already a maintained helper in the Phase-4C support donor.
    # Instrument that one canonical body instead of emitting a duplicate body
    # from the translated pack. Keep the shared s_phase4cLastError state so
    # the paired GetLastError helper (B150) observes exactly what SetLastError
    # wrote.
    old_b178 = """static void sub_0022B178(void)
{
    s_phase4cLastError = GUEST_READ32(g_esp + 4u);
    g_esp += 8u;
}"""
    new_b178 = """static void sub_0022B178(void)
{
    char line[256];

    RECOMP_TRACE_FUNC(0x0022B178u);
    s_phase4cLastError = GUEST_READ32(g_esp + 4u);
    s_phase5mXboxLastError = s_phase4cLastError;
    ++s_phase5mSetLastErrorCount;

    sprintf(
        line,
        "PASS: Phase 5M maintained SetLastError value=%08X calls=%u new_esp=%08X",
        (unsigned int)s_phase4cLastError,
        (unsigned int)s_phase5mSetLastErrorCount,
        (unsigned int)(g_esp + 8u));
    trace(line);

    g_esp += 8u;
}"""
    if old_b178 not in text:
        raise SystemExit("[Phase5M] maintained support-owned B178 body marker changed")
    text = text.replace(old_b178, new_b178, 1)

    old_enum = """    PHASE4C_BOUNDARY_DEBUGBREAK = 7,
    PHASE4C_BOUNDARY_HEAP_EXHAUSTED = 8
};"""
    new_enum = """    PHASE4C_BOUNDARY_DEBUGBREAK = 7,
    PHASE4C_BOUNDARY_HEAP_EXHAUSTED = 8,
    PHASE4C_BOUNDARY_THREAD_TARGET = 9,
    PHASE4C_BOUNDARY_KERNEL_FRAME = 10,
    PHASE4C_BOUNDARY_THREAD_RETURN = 11,
    PHASE4C_BOUNDARY_CALLBACK_RETURN = 12,
    PHASE4C_BOUNDARY_DIRECT_FRONTIER = 13,
    PHASE4C_BOUNDARY_TIMER_DUE = 14,
    PHASE4C_BOUNDARY_STORAGE_OPEN = 15,
    PHASE4C_BOUNDARY_STORAGE_QUERY = 16,
    PHASE4C_BOUNDARY_STORAGE_IO = 17,
    PHASE4C_BOUNDARY_FILE_INFORMATION = 18
};"""
    if old_enum not in text:
        raise SystemExit("[Phase5M] boundary enum marker changed")
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
    } else if (_phase4c_target == 0x8000012Du && s_phase4cNvQueryHandled && !s_phase4cNtStatusMapped) { \
        phase4c_rtl_nt_status_to_dos_error((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000095u && s_phase4cTimerInitialized) { \
        phase4c_ke_set_timer((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000B8u) { \
        phase4c_nt_allocate_virtual_memory((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000123u) { \
        phase4c_initialize_critical_section((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000CAu) { \
        phase5b_nt_open_file((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000DAu) { \
        phase5c_query_volume_information((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000BBu) { \
        phase5c_nt_close((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000043u) { \
        phase5d_io_create_symbolic_link((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000045u) { \
        phase5d_io_delete_symbolic_link((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000BEu) { \
        phase5h_nt_create_file((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000DBu) { \
        phase5h_nt_read_file((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000121u) { \
        phase5i_rtl_init_ansi_string((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000117u) { \
        phase5k_rtl_equal_string((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000D3u) { \
        uint32_t _phase5m_call_esp = g_esp; \
        uint32_t _phase5m_ret; \
        uint32_t _phase5m_handle; \
        uint32_t _phase5m_iosb; \
        uint32_t _phase5m_info; \
        uint32_t _phase5m_len; \
        uint32_t _phase5m_class; \
        char _phase5m_line[512]; \
        if ((uint32_t)(saved_esp) != _phase5m_call_esp + 24u) { \
            sprintf( \
                _phase5m_line, \
                "NtQueryInformationFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=24", \
                (unsigned int)_phase5m_call_esp, \
                (unsigned int)(saved_esp), \
                (unsigned int)((uint32_t)(saved_esp) - _phase5m_call_esp)); \
            trace(_phase5m_line); \
            phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x800000D3u, (DWORD)(saved_esp)); \
        } \
        _phase5m_ret = GUEST_READ32(_phase5m_call_esp + 0u); \
        _phase5m_handle = GUEST_READ32(_phase5m_call_esp + 4u); \
        _phase5m_iosb = GUEST_READ32(_phase5m_call_esp + 8u); \
        _phase5m_info = GUEST_READ32(_phase5m_call_esp + 12u); \
        _phase5m_len = GUEST_READ32(_phase5m_call_esp + 16u); \
        _phase5m_class = GUEST_READ32(_phase5m_call_esp + 20u); \
        if (s_accessFault) { \
            phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, 0x800000D3u, (DWORD)(saved_esp)); \
        } \
        if (_phase5m_ret != 0u) { \
            sprintf(_phase5m_line, "NtQueryInformationFile RETURN SLOT MISMATCH: ret=%08X", (unsigned int)_phase5m_ret); \
            trace(_phase5m_line); \
            phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x800000D3u, (DWORD)(saved_esp)); \
        } \
        ++s_phase5mNtQueryInformationFileCaptureCount; \
        s_phase5mNtQueryInformationFileHandle = _phase5m_handle; \
        s_phase5mNtQueryInformationFileIoStatus = _phase5m_iosb; \
        s_phase5mNtQueryInformationFileBuffer = _phase5m_info; \
        s_phase5mNtQueryInformationFileLength = _phase5m_len; \
        s_phase5mNtQueryInformationFileClass = _phase5m_class; \
        sprintf( \
            _phase5m_line, \
            "NtQueryInformationFile CAPTURE FRAME: ret=%08X handle=%08X iosb=%08X info=%08X len=%u class=%u esp=%08X saved_esp=%08X", \
            (unsigned int)_phase5m_ret, \
            (unsigned int)_phase5m_handle, \
            (unsigned int)_phase5m_iosb, \
            (unsigned int)_phase5m_info, \
            (unsigned int)_phase5m_len, \
            (unsigned int)_phase5m_class, \
            (unsigned int)_phase5m_call_esp, \
            (unsigned int)(saved_esp)); \
        trace(_phase5m_line); \
        trace("PASS: Phase 5M captured ordinal 211 NtQueryInformationFile request"); \
        phase4c_escape(PHASE4C_BOUNDARY_FILE_INFORMATION, 0x800000D3u, (DWORD)(saved_esp)); \
    } else { \
        phase4c_escape( \
            PHASE4C_BOUNDARY_ICALL_SAFE, \
            _phase4c_target, \
            (DWORD)(saved_esp)); \
    } \
} while (0)'''

    if old_macro not in text:
        raise SystemExit("[Phase5M] RECOMP_ICALL_SAFE marker changed")
    text = text.replace(old_macro, new_macro)

    old_itail = r'''#define RECOMP_ITAIL(xbox_va) do { \
    phase4c_escape( \
        PHASE4C_BOUNDARY_ITAIL, \
        (DWORD)(xbox_va), \
        g_esp); \
} while (0)'''
    new_itail = r'''#define RECOMP_ITAIL(xbox_va) do { \
    uint32_t _phase4c_tail_target = (uint32_t)(xbox_va); \
    if (_phase4c_tail_target == 0x80000018u && !s_phase4cNvQueryHandled) { \
        phase4c_ex_query_nonvolatile_setting(); \
    } else { \
        phase4c_escape( \
            PHASE4C_BOUNDARY_ITAIL, \
            _phase4c_tail_target, \
            g_esp); \
    } \
} while (0)'''
    if old_itail not in text:
        raise SystemExit("[Phase5M] RECOMP_ITAIL marker changed")
    text = text.replace(old_itail, new_itail)

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
static int s_phase4cNvQueryHandled;
static uint32_t s_phase4cNvQueryIndex;
static uint32_t s_phase4cNvQueryValueVa;
static uint32_t s_phase4cNvQueryValueLength;
static int s_phase4cNtStatusMapped;
static uint32_t s_phase4cNtStatusInput;
static uint32_t s_phase4cNtStatusDosError;
static int s_phase4cTimerArmed;
static uint64_t s_phase4cTimerDue100ns;
static uint32_t s_phase4cTimerDpcVa;
static int s_phase4cTimerWasActive;
static uint32_t s_phase4cVmAllocCount;
static uint32_t s_phase4cVmAllocLastStatus;
static uint32_t s_phase4cVmAllocLastBase;
static uint32_t s_phase4cVmAllocLastSize;
static uint32_t s_phase4cCriticalSectionInitCount;
static uint32_t s_phase4cCriticalSectionInitLastVa;
static uint32_t s_phase5bNtOpenFileHandledCount;
static uint32_t s_phase5bNtOpenFileObjectAttributes;
static uint32_t s_phase5bNtOpenFilePathVa;
static uint32_t s_phase5bNtOpenFilePathLength;
static uint32_t s_phase5bNtOpenFileLastToken;
static uint32_t s_phase5bNtOpenFileLastStatus;
static uint32_t s_phase5cVolumeQueryCount;
static uint32_t s_phase5cVolumeLastClass;
static uint32_t s_phase5cCloseCount;
static uint32_t s_phase5dSymbolicLinkCreateCount;
static uint32_t s_phase5dSymbolicLinkDeleteCount;
static uint32_t s_phase5hNtCreateFileCallCount;
static uint32_t s_phase5hNtCreateFileSuccessCount;
static uint32_t s_phase5hNtReadFileCallCount;
static uint32_t s_phase5hNtReadFileSuccessCount;
static uint32_t s_phase5iRtlInitAnsiStringCount;
static uint32_t s_phase5iRtlInitAnsiStringLastLength;
static uint32_t s_phase5iRtlInitAnsiStringLastDestination;
static uint32_t s_phase5iRtlInitAnsiStringLastSource;
static uint32_t s_phase5kRtlEqualStringCount;
static uint32_t s_phase5kRtlEqualStringTrueCount;
static uint32_t s_phase5kRtlEqualStringLastString1;
static uint32_t s_phase5kRtlEqualStringLastString2;
static uint32_t s_phase5kRtlEqualStringLastCaseInsensitive;
static uint32_t s_phase5kRtlEqualStringLastResult;

#define PHASE5D_SYMLINK_CAP 32u
typedef struct Phase5DSymbolicLink
{
    uint32_t used;
    char link[64];
    char target[192];
} Phase5DSymbolicLink;
static Phase5DSymbolicLink s_phase5dSymbolicLinks[PHASE5D_SYMLINK_CAP];

#define PHASE5B_HANDLE_TAG 0x48000000u
#define PHASE5B_HANDLE_CAP 64u
static HANDLE s_phase5bHandles[PHASE5B_HANDLE_CAP];

#define PHASE4C_VM_RESERVATION_CAP 64u
typedef struct Phase4CVmReservation
{
    uint32_t base;
    uint32_t size;
    uint32_t protect;
    uint32_t inUse;
} Phase4CVmReservation;

static Phase4CVmReservation
    s_phase4cVmReservations[PHASE4C_VM_RESERVATION_CAP];
static uint32_t s_phase4cVmReservationCount;
static uint32_t s_phase4cVmPageNext = RAM_SIZE;

static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va);

static int phase5b_ascii_lower(int ch)
{
    if (ch >= 'A' && ch <= 'Z')
        return ch + ('a' - 'A');
    return ch;
}

static int phase5b_prefix_equal_ci(
    const char* path,
    const char* prefix,
    uint32_t* consumed)
{
    uint32_t i = 0u;
    if (!path || !prefix)
        return 0;

    while (prefix[i] != '\0')
    {
        if (path[i] == '\0' ||
            phase5b_ascii_lower((unsigned char)path[i]) !=
            phase5b_ascii_lower((unsigned char)prefix[i]))
            return 0;
        ++i;
    }

    if (consumed)
        *consumed = i;
    return 1;
}

static int phase5d_string_equal_ci(const char* a, const char* b)
{
    uint32_t i = 0u;
    if (!a || !b)
        return 0;

    while (a[i] != '\0' && b[i] != '\0')
    {
        if (phase5b_ascii_lower((unsigned char)a[i]) !=
            phase5b_ascii_lower((unsigned char)b[i]))
            return 0;
        ++i;
    }
    return a[i] == '\0' && b[i] == '\0';
}

static int phase5d_copy_guest_ansi_string(
    uint32_t stringVa,
    char* out,
    uint32_t capacity,
    uint32_t* outLength,
    uint32_t* outMaximumLength,
    uint32_t* outBufferVa)
{
    uint32_t length;
    uint32_t maximumLength;
    uint32_t bufferVa;
    uint32_t i;

    if (!stringVa || !out || capacity == 0u)
        return 0;

    length = (uint32_t)GUEST_READ16(stringVa + 0u);
    maximumLength = (uint32_t)GUEST_READ16(stringVa + 2u);
    bufferVa = GUEST_READ32(stringVa + 4u);

    if (s_accessFault || bufferVa == 0u || length >= capacity)
        return 0;

    for (i = 0u; i < length; ++i)
    {
        out[i] = (char)GUEST_READ8(bufferVa + i);
        if (s_accessFault)
            return 0;
    }
    out[length] = '\0';

    if (outLength) *outLength = length;
    if (outMaximumLength) *outMaximumLength = maximumLength;
    if (outBufferVa) *outBufferVa = bufferVa;
    return 1;
}

static int phase5d_find_symbolic_link(const char* link)
{
    uint32_t i;
    for (i = 0u; i < PHASE5D_SYMLINK_CAP; ++i)
    {
        if (s_phase5dSymbolicLinks[i].used &&
            phase5d_string_equal_ci(s_phase5dSymbolicLinks[i].link, link))
            return (int)i;
    }
    return -1;
}

static uint32_t phase5d_create_symbolic_link(
    const char* link,
    const char* target)
{
    uint32_t i;

    if (!link || !target || link[0] == '\0' || target[0] == '\0')
        return 0xC000000Du; /* STATUS_INVALID_PARAMETER */

    if (phase5d_find_symbolic_link(link) >= 0)
        return 0xC0000035u; /* STATUS_OBJECT_NAME_COLLISION */

    for (i = 0u; i < PHASE5D_SYMLINK_CAP; ++i)
    {
        if (!s_phase5dSymbolicLinks[i].used)
        {
            s_phase5dSymbolicLinks[i].used = 1u;
            strncpy(
                s_phase5dSymbolicLinks[i].link,
                link,
                sizeof(s_phase5dSymbolicLinks[i].link) - 1u);
            s_phase5dSymbolicLinks[i].link[
                sizeof(s_phase5dSymbolicLinks[i].link) - 1u] = '\0';
            strncpy(
                s_phase5dSymbolicLinks[i].target,
                target,
                sizeof(s_phase5dSymbolicLinks[i].target) - 1u);
            s_phase5dSymbolicLinks[i].target[
                sizeof(s_phase5dSymbolicLinks[i].target) - 1u] = '\0';
            return 0u;
        }
    }

    return 0xC000009Au; /* STATUS_INSUFFICIENT_RESOURCES */
}

static uint32_t phase5d_delete_symbolic_link(const char* link)
{
    int index = phase5d_find_symbolic_link(link);
    if (index < 0)
        return 0xC0000034u; /* STATUS_OBJECT_NAME_NOT_FOUND */

    ZeroMemory(
        &s_phase5dSymbolicLinks[index],
        sizeof(s_phase5dSymbolicLinks[index]));
    return 0u;
}

static int phase5d_expand_symbolic_path(
    const char* xboxPath,
    char* expanded,
    uint32_t capacity)
{
    char linkName[16];
    const char* remainder = NULL;
    int index;
    int written;

    if (!xboxPath || !expanded || capacity == 0u)
        return 0;

    /*
     * Retail file calls normally use X:\path after IoCreateSymbolicLink
     * created an object-manager alias named \\??\\X:. Expand that drive
     * spelling through the exact guest-created target.
     */
    if (((xboxPath[0] >= 'A' && xboxPath[0] <= 'Z') ||
         (xboxPath[0] >= 'a' && xboxPath[0] <= 'z')) &&
        xboxPath[1] == ':')
    {
        _snprintf(
            linkName,
            sizeof(linkName) - 1u,
            "\\??\\%c:",
            xboxPath[0]);
        linkName[sizeof(linkName) - 1u] = '\0';
        remainder = xboxPath + 2;
    }
    else
    {
        return 0;
    }

    index = phase5d_find_symbolic_link(linkName);
    if (index < 0)
        return 0;

    while (*remainder == '\\' || *remainder == '/')
        ++remainder;

    if (*remainder)
    {
        size_t targetLength = strlen(s_phase5dSymbolicLinks[index].target);
        const char* separator =
            (targetLength > 0u &&
             s_phase5dSymbolicLinks[index].target[targetLength - 1u] == '\\') ?
            "" : "\\";
        written = _snprintf(
            expanded,
            capacity - 1u,
            "%s%s%s",
            s_phase5dSymbolicLinks[index].target,
            separator,
            remainder);
    }
    else
    {
        written = _snprintf(
            expanded,
            capacity - 1u,
            "%s",
            s_phase5dSymbolicLinks[index].target);
    }

    expanded[capacity - 1u] = '\0';
    return written >= 0 && (uint32_t)written < capacity;
}

static int phase5b_translate_storage_path(
    const char* xboxPath,
    char* nativePath,
    uint32_t nativeCapacity,
    int* virtualRoot)
{
    static const char partition1[] = "\\Device\\Harddisk0\\partition1\\";
    static const char cdrom0[] = "\\Device\\CdRom0\\";
    uint32_t consumed = 0u;
    const char* remainder;
    int written;
    char expandedPath[260];

    if (!xboxPath || !nativePath || nativeCapacity == 0u)
        return 0;

    if (virtualRoot)
        *virtualRoot = 0;

    if (phase5d_expand_symbolic_path(
            xboxPath, expandedPath, sizeof(expandedPath)))
        xboxPath = expandedPath;

    if (phase5d_string_equal_ci(xboxPath, "\\Device\\CdRom0"))
    {
        written = _snprintf(
            nativePath,
            nativeCapacity - 1u,
            "game:\\");
    }
    else if (phase5b_prefix_equal_ci(xboxPath, partition1, &consumed))
    {
        remainder = xboxPath + consumed;
        if (remainder[0] == '\0')
        {
            written = _snprintf(
                nativePath,
                nativeCapacity - 1u,
                "game:\\merc360-partition1");
            if (virtualRoot)
                *virtualRoot = 1;
        }
        else
        {
            written = _snprintf(
                nativePath,
                nativeCapacity - 1u,
                "game:\\merc360-partition1\\%s",
                remainder);
        }
    }
    else if (phase5b_prefix_equal_ci(xboxPath, cdrom0, &consumed))
    {
        remainder = xboxPath + consumed;
        written = _snprintf(
            nativePath,
            nativeCapacity - 1u,
            "game:\\%s",
            remainder);
    }
    else if (
        (xboxPath[0] == 'D' || xboxPath[0] == 'd') &&
        xboxPath[1] == ':' &&
        (xboxPath[2] == '\\' || xboxPath[2] == '/') )
    {
        remainder = xboxPath + 3;
        written = _snprintf(
            nativePath,
            nativeCapacity - 1u,
            "game:\\%s",
            remainder);
    }
    else
    {
        nativePath[0] = '\0';
        return 0;
    }

    nativePath[nativeCapacity - 1u] = '\0';
    return written >= 0 && (uint32_t)written < nativeCapacity;
}

static uint32_t phase5b_native_handle_token(HANDLE handle)
{
    uint32_t i;
    if (!handle || handle == INVALID_HANDLE_VALUE)
        return 0u;

    for (i = 1u; i < PHASE5B_HANDLE_CAP; ++i)
    {
        if (s_phase5bHandles[i] == handle)
            return PHASE5B_HANDLE_TAG | i;
    }

    for (i = 1u; i < PHASE5B_HANDLE_CAP; ++i)
    {
        if (s_phase5bHandles[i] == NULL ||
            s_phase5bHandles[i] == INVALID_HANDLE_VALUE)
        {
            s_phase5bHandles[i] = handle;
            return PHASE5B_HANDLE_TAG | i;
        }
    }

    return 0u;
}

static HANDLE phase5c_read_native_handle(uint32_t token)
{
    uint32_t index;
    if ((token & 0xFF000000u) != PHASE5B_HANDLE_TAG)
        return NULL;
    index = token & 0x00FFFFFFu;
    if (index == 0u || index >= PHASE5B_HANDLE_CAP)
        return NULL;
    if (s_phase5bHandles[index] == NULL ||
        s_phase5bHandles[index] == INVALID_HANDLE_VALUE)
        return NULL;
    return s_phase5bHandles[index];
}

static HANDLE phase5c_take_native_handle(uint32_t token)
{
    uint32_t index;
    HANDLE handle = phase5c_read_native_handle(token);
    if (!handle)
        return NULL;
    index = token & 0x00FFFFFFu;
    s_phase5bHandles[index] = NULL;
    return handle;
}

static uint32_t phase5b_open_status_from_error(DWORD error)
{
    switch (error)
    {
    case ERROR_FILE_NOT_FOUND:
        return 0xC0000034u; /* STATUS_OBJECT_NAME_NOT_FOUND */
    case ERROR_PATH_NOT_FOUND:
        return 0xC000003Au; /* STATUS_OBJECT_PATH_NOT_FOUND */
    case ERROR_ACCESS_DENIED:
        return 0xC0000022u; /* STATUS_ACCESS_DENIED */
    case ERROR_INVALID_HANDLE:
        return 0xC0000008u; /* STATUS_INVALID_HANDLE */
    case ERROR_ALREADY_EXISTS:
    case ERROR_FILE_EXISTS:
        return 0xC0000035u; /* STATUS_OBJECT_NAME_COLLISION */
    default:
        return 0xC0000001u; /* STATUS_UNSUCCESSFUL */
    }
}

static DWORD phase5b_native_access(uint32_t access)
{
    DWORD nativeAccess = 0u;

    /* Xbox generic access bits. */
    if (access & 0x80000000u)
        nativeAccess |= GENERIC_READ;
    if (access & 0x40000000u)
        nativeAccess |= GENERIC_WRITE;
    if (access & 0x10000000u)
        nativeAccess |= GENERIC_READ | GENERIC_WRITE;

    /* Xbox file-data / attribute bits used by retail titles. */
    if (access & 0x00000001u)
        nativeAccess |= GENERIC_READ;
    if (access & (0x00000002u | 0x00000004u))
        nativeAccess |= GENERIC_WRITE;
    if (access & 0x00000080u)
        nativeAccess |= GENERIC_READ;
    if (access & 0x00000100u)
        nativeAccess |= GENERIC_WRITE;

    if (nativeAccess == 0u)
        nativeAccess = GENERIC_READ;
    return nativeAccess;
}

static DWORD phase5b_native_share(uint32_t share)
{
    DWORD nativeShare = 0u;
    if (share & 0x01u) nativeShare |= FILE_SHARE_READ;
    if (share & 0x02u) nativeShare |= FILE_SHARE_WRITE;
    return nativeShare;
}

static void phase5d_io_create_symbolic_link(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t linkVa;
    uint32_t targetVa;
    uint32_t linkLength = 0u;
    uint32_t linkMaximum = 0u;
    uint32_t linkBuffer = 0u;
    uint32_t targetLength = 0u;
    uint32_t targetMaximum = 0u;
    uint32_t targetBuffer = 0u;
    uint32_t status;
    char link[64];
    char target[192];
    char line[640];

    if (savedEsp != callEsp + 12u)
    {
        sprintf(
            line,
            "IoCreateSymbolicLink FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=12",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000043u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    linkVa = GUEST_READ32(callEsp + 4u);
    targetVa = GUEST_READ32(callEsp + 8u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000043u,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "IoCreateSymbolicLink LIVE FRAME: ret=%08X link_ptr=%08X target_ptr=%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)linkVa,
        (unsigned int)targetVa,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u ||
        !phase5d_copy_guest_ansi_string(
            linkVa, link, sizeof(link),
            &linkLength, &linkMaximum, &linkBuffer) ||
        !phase5d_copy_guest_ansi_string(
            targetVa, target, sizeof(target),
            &targetLength, &targetMaximum, &targetBuffer))
    {
        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x80000043u,
                savedEsp);
            return;
        }
        g_eax = 0xC000000Du;
        g_esp = savedEsp;
        trace("IoCreateSymbolicLink: invalid guest ANSI_STRING input");
        return;
    }

    sprintf(
        line,
        "IoCreateSymbolicLink OBJECTS: link_len=%u link_max=%u link_buf=%08X link=%s target_len=%u target_max=%u target_buf=%08X target=%s",
        (unsigned int)linkLength,
        (unsigned int)linkMaximum,
        (unsigned int)linkBuffer,
        link,
        (unsigned int)targetLength,
        (unsigned int)targetMaximum,
        (unsigned int)targetBuffer,
        target);
    trace(line);

    status = phase5d_create_symbolic_link(link, target);
    g_eax = status;
    g_esp = savedEsp;

    if (status == 0u)
        ++s_phase5dSymbolicLinkCreateCount;

    sprintf(
        line,
        "PASS: Phase 5M IoCreateSymbolicLink native continuation link=%s target=%s status=%08X creates=%u new_esp=%08X",
        link,
        target,
        (unsigned int)status,
        (unsigned int)s_phase5dSymbolicLinkCreateCount,
        (unsigned int)g_esp);
    trace(line);
}

static void phase5d_io_delete_symbolic_link(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t linkVa;
    uint32_t status;
    char link[64];
    char line[384];

    if (savedEsp != callEsp + 8u)
    {
        sprintf(
            line,
            "IoDeleteSymbolicLink FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=8",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000045u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    linkVa = GUEST_READ32(callEsp + 4u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000045u,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "IoDeleteSymbolicLink LIVE FRAME: ret=%08X link_ptr=%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)linkVa,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u ||
        !phase5d_copy_guest_ansi_string(
            linkVa, link, sizeof(link), NULL, NULL, NULL))
    {
        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x80000045u,
                savedEsp);
            return;
        }
        g_eax = 0xC000000Du;
        g_esp = savedEsp;
        return;
    }

    status = phase5d_delete_symbolic_link(link);
    if (status == 0u)
        ++s_phase5dSymbolicLinkDeleteCount;

    g_eax = status;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5M IoDeleteSymbolicLink native continuation link=%s status=%08X deletes=%u new_esp=%08X",
        link,
        (unsigned int)status,
        (unsigned int)s_phase5dSymbolicLinkDeleteCount,
        (unsigned int)g_esp);
    trace(line);
}

static void phase5c_query_volume_information(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t handleToken;
    uint32_t ioStatusVa;
    uint32_t infoVa;
    uint32_t length;
    uint32_t infoClass;
    HANDLE nativeHandle;
    ULARGE_INTEGER freeBytes;
    ULARGE_INTEGER totalBytes;
    ULARGE_INTEGER totalFreeBytes;
    unsigned __int64 clusterBytes;
    unsigned __int64 totalUnits;
    unsigned __int64 availableUnits;
    char line[640];

    if (savedEsp != callEsp + 24u)
    {
        sprintf(
            line,
            "NtQueryVolumeInformationFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=24",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000DAu,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    handleToken = GUEST_READ32(callEsp + 4u);
    ioStatusVa = GUEST_READ32(callEsp + 8u);
    infoVa = GUEST_READ32(callEsp + 12u);
    length = GUEST_READ32(callEsp + 16u);
    infoClass = GUEST_READ32(callEsp + 20u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000DAu,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "NtQueryVolumeInformationFile LIVE FRAME: ret=%08X handle=%08X iosb=%08X info=%08X len=%u class=%u esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)handleToken,
        (unsigned int)ioStatusVa,
        (unsigned int)infoVa,
        (unsigned int)length,
        (unsigned int)infoClass,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u || ioStatusVa == 0u || infoVa == 0u)
    {
        trace("KERNEL FRAME MISMATCH: ordinal 218 invalid return/iosb/info field");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000DAu,
            savedEsp);
        return;
    }

    nativeHandle = phase5c_read_native_handle(handleToken);
    if (!nativeHandle)
    {
        GUEST_WRITE32(ioStatusVa + 0u, 0xC0000008u);
        GUEST_WRITE32(ioStatusVa + 4u, 0u);
        g_eax = 0xC0000008u;
        g_esp = savedEsp;
        trace("NtQueryVolumeInformationFile: invalid tagged guest handle");
        return;
    }

    s_phase5cVolumeLastClass = infoClass;

    /*
     * XboxFileFsSizeInformation == 3 and is a 24-byte structure:
     *   LARGE_INTEGER TotalAllocationUnits
     *   LARGE_INTEGER AvailableAllocationUnits
     *   ULONG SectorsPerAllocationUnit
     *   ULONG BytesPerSector
     */
    if (infoClass != 3u || length < 24u)
    {
        sprintf(
            line,
            "STORAGE QUERY UNSUPPORTED: class=%u len=%u handle=%08X",
            (unsigned int)infoClass,
            (unsigned int)length,
            (unsigned int)handleToken);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_QUERY,
            0x800000DAu,
            savedEsp);
        return;
    }

    ZeroMemory(&freeBytes, sizeof(freeBytes));
    ZeroMemory(&totalBytes, sizeof(totalBytes));
    ZeroMemory(&totalFreeBytes, sizeof(totalFreeBytes));

    SetLastError(ERROR_SUCCESS);
    if (!GetDiskFreeSpaceExA(
            "game:\\",
            &freeBytes,
            &totalBytes,
            &totalFreeBytes))
    {
        sprintf(
            line,
            "STORAGE QUERY NATIVE FAILURE: GetDiskFreeSpaceExA(game:\\) error=%u",
            (unsigned int)GetLastError());
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_QUERY,
            0x800000DAu,
            savedEsp);
        return;
    }

    clusterBytes = 512ui64 * 32ui64; /* FATX-style 16 KiB allocation units */
    totalUnits = totalBytes.QuadPart / clusterBytes;
    availableUnits = freeBytes.QuadPart / clusterBytes;

    GUEST_WRITE32(infoVa + 0u, (uint32_t)totalUnits);
    GUEST_WRITE32(infoVa + 4u, (uint32_t)(totalUnits >> 32));
    GUEST_WRITE32(infoVa + 8u, (uint32_t)availableUnits);
    GUEST_WRITE32(infoVa + 12u, (uint32_t)(availableUnits >> 32));
    GUEST_WRITE32(infoVa + 16u, 32u);
    GUEST_WRITE32(infoVa + 20u, 512u);
    GUEST_WRITE32(ioStatusVa + 0u, 0u);
    GUEST_WRITE32(ioStatusVa + 4u, 24u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000DAu,
            savedEsp);
        return;
    }

    ++s_phase5cVolumeQueryCount;
    g_eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5M NtQueryVolumeInformationFile native continuation class=%u total_units=%I64u available_units=%I64u sectors_per_unit=32 bytes_per_sector=512 calls=%u new_esp=%08X",
        (unsigned int)infoClass,
        totalUnits,
        availableUnits,
        (unsigned int)s_phase5cVolumeQueryCount,
        (unsigned int)g_esp);
    trace(line);
}

static void phase5c_nt_close(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t handleToken;
    HANDLE nativeHandle;
    uint32_t status;
    char line[320];

    if (savedEsp != callEsp + 8u)
    {
        sprintf(
            line,
            "NtClose FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=8",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000BBu,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    handleToken = GUEST_READ32(callEsp + 4u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000BBu,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "NtClose LIVE FRAME: ret=%08X handle=%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)handleToken,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000BBu,
            savedEsp);
        return;
    }

    nativeHandle = phase5c_take_native_handle(handleToken);
    if (!nativeHandle)
    {
        status = 0xC0000008u; /* STATUS_INVALID_HANDLE */
    }
    else if (CloseHandle(nativeHandle))
    {
        status = 0u;
        ++s_phase5cCloseCount;
    }
    else
    {
        status = 0xC0000008u;
    }

    g_eax = status;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5M NtClose native continuation handle=%08X status=%08X closes=%u new_esp=%08X",
        (unsigned int)handleToken,
        (unsigned int)status,
        (unsigned int)s_phase5cCloseCount,
        (unsigned int)g_esp);
    trace(line);
}

static void phase5k_rtl_equal_string(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t string1Va;
    uint32_t string2Va;
    uint32_t caseInsensitive;
    uint32_t length1 = 0u;
    uint32_t length2 = 0u;
    uint32_t buffer1Va = 0u;
    uint32_t buffer2Va = 0u;
    uint32_t result = 0u;
    uint32_t i;
    char preview1[129];
    char preview2[129];
    char line[768];

    if (savedEsp != callEsp + 16u)
    {
        sprintf(
            line,
            "RtlEqualString FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=16",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000117u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    string1Va = GUEST_READ32(callEsp + 4u);
    string2Va = GUEST_READ32(callEsp + 8u);
    caseInsensitive = GUEST_READ32(callEsp + 12u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000117u,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "RtlEqualString LIVE FRAME: ret=%08X string1=%08X string2=%08X case_insensitive=%u esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)string1Va,
        (unsigned int)string2Va,
        (unsigned int)caseInsensitive,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000117u,
            savedEsp);
        return;
    }

    preview1[0] = '\0';
    preview2[0] = '\0';

    if (string1Va != 0u && string2Va != 0u)
    {
        length1 = (uint32_t)GUEST_READ16(string1Va + 0u);
        length2 = (uint32_t)GUEST_READ16(string2Va + 0u);
        buffer1Va = GUEST_READ32(string1Va + 4u);
        buffer2Va = GUEST_READ32(string2Va + 4u);

        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x80000117u,
                savedEsp);
            return;
        }

        if (length1 == length2)
        {
            if (length1 == 0u)
            {
                result = 1u;
            }
            else if (buffer1Va != 0u && buffer2Va != 0u)
            {
                result = 1u;
                for (i = 0u; i < length1; ++i)
                {
                    uint32_t c1 = (uint32_t)GUEST_READ8(buffer1Va + i);
                    uint32_t c2 = (uint32_t)GUEST_READ8(buffer2Va + i);

                    if (s_accessFault)
                    {
                        phase4c_escape(
                            PHASE4C_BOUNDARY_GUEST_FAULT,
                            0x80000117u,
                            savedEsp);
                        return;
                    }

                    if (caseInsensitive)
                    {
                        c1 = (uint32_t)phase5b_ascii_lower((int)c1);
                        c2 = (uint32_t)phase5b_ascii_lower((int)c2);
                    }

                    if (c1 != c2)
                    {
                        result = 0u;
                        break;
                    }
                }
            }
        }

        if (buffer1Va != 0u)
        {
            uint32_t previewLength1 = length1 < 128u ? length1 : 128u;
            for (i = 0u; i < previewLength1; ++i)
            {
                uint32_t ch = (uint32_t)GUEST_READ8(buffer1Va + i);
                if (s_accessFault)
                {
                    phase4c_escape(
                        PHASE4C_BOUNDARY_GUEST_FAULT,
                        0x80000117u,
                        savedEsp);
                    return;
                }
                preview1[i] =
                    (ch >= 0x20u && ch <= 0x7Eu) ? (char)ch : '.';
            }
            preview1[previewLength1] = '\0';
        }

        if (buffer2Va != 0u)
        {
            uint32_t previewLength2 = length2 < 128u ? length2 : 128u;
            for (i = 0u; i < previewLength2; ++i)
            {
                uint32_t ch = (uint32_t)GUEST_READ8(buffer2Va + i);
                if (s_accessFault)
                {
                    phase4c_escape(
                        PHASE4C_BOUNDARY_GUEST_FAULT,
                        0x80000117u,
                        savedEsp);
                    return;
                }
                preview2[i] =
                    (ch >= 0x20u && ch <= 0x7Eu) ? (char)ch : '.';
            }
            preview2[previewLength2] = '\0';
        }
    }

    s_phase5kRtlEqualStringLastString1 = string1Va;
    s_phase5kRtlEqualStringLastString2 = string2Va;
    s_phase5kRtlEqualStringLastCaseInsensitive = caseInsensitive;
    s_phase5kRtlEqualStringLastResult = result;
    ++s_phase5kRtlEqualStringCount;
    if (result)
        ++s_phase5kRtlEqualStringTrueCount;

    g_eax = result;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5M RtlEqualString continuation string1=%08X len1=%u preview1=%s string2=%08X len2=%u preview2=%s case_insensitive=%u result=%u calls=%u true_calls=%u new_esp=%08X",
        (unsigned int)string1Va,
        (unsigned int)length1,
        string1Va ? preview1 : "<null>",
        (unsigned int)string2Va,
        (unsigned int)length2,
        string2Va ? preview2 : "<null>",
        (unsigned int)caseInsensitive,
        (unsigned int)result,
        (unsigned int)s_phase5kRtlEqualStringCount,
        (unsigned int)s_phase5kRtlEqualStringTrueCount,
        (unsigned int)g_esp);
    trace(line);
}

static void phase5i_rtl_init_ansi_string(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t destinationVa;
    uint32_t sourceVa;
    uint32_t length = 0u;
    uint32_t i;
    char preview[129];
    char line[640];

    if (savedEsp != callEsp + 12u)
    {
        sprintf(
            line,
            "RtlInitAnsiString FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=12",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000121u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    destinationVa = GUEST_READ32(callEsp + 4u);
    sourceVa = GUEST_READ32(callEsp + 8u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000121u,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "RtlInitAnsiString LIVE FRAME: ret=%08X destination=%08X source=%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)destinationVa,
        (unsigned int)sourceVa,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000121u,
            savedEsp);
        return;
    }

    preview[0] = '\0';

    if (sourceVa != 0u)
    {
        for (length = 0u; length < 0xFFFEu; ++length)
        {
            uint32_t ch = (uint32_t)GUEST_READ8(sourceVa + length);
            if (s_accessFault)
            {
                phase4c_escape(
                    PHASE4C_BOUNDARY_GUEST_FAULT,
                    0x80000121u,
                    savedEsp);
                return;
            }

            if (length < 128u)
                preview[length] =
                    (ch >= 0x20u && ch <= 0x7Eu) ? (char)ch : '.';

            if (ch == 0u)
                break;
        }

        if (length == 0xFFFEu)
        {
            trace("RtlInitAnsiString: source exceeded maintained 0xFFFE-byte clamp");
        }

        i = length < 128u ? length : 128u;
        preview[i] = '\0';
    }

    if (destinationVa != 0u)
    {
        if (sourceVa != 0u)
        {
            GUEST_WRITE16(destinationVa + 0u, (uint16_t)length);
            GUEST_WRITE16(
                destinationVa + 2u,
                (uint16_t)(length < 0xFFFEu ? length + 1u : 0xFFFFu));
            GUEST_WRITE32(destinationVa + 4u, sourceVa);
        }
        else
        {
            GUEST_WRITE16(destinationVa + 0u, 0u);
            GUEST_WRITE16(destinationVa + 2u, 0u);
            GUEST_WRITE32(destinationVa + 4u, 0u);
        }
    }

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000121u,
            savedEsp);
        return;
    }

    s_phase5iRtlInitAnsiStringLastLength = length;
    s_phase5iRtlInitAnsiStringLastDestination = destinationVa;
    s_phase5iRtlInitAnsiStringLastSource = sourceVa;
    ++s_phase5iRtlInitAnsiStringCount;

    g_eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5M RtlInitAnsiString continuation destination=%08X source=%08X len=%u max=%u preview=%s calls=%u new_esp=%08X",
        (unsigned int)destinationVa,
        (unsigned int)sourceVa,
        (unsigned int)length,
        (unsigned int)(sourceVa ? (length < 0xFFFEu ? length + 1u : 0xFFFFu) : 0u),
        sourceVa ? preview : "<null>",
        (unsigned int)s_phase5iRtlInitAnsiStringCount,
        (unsigned int)g_esp);
    trace(line);
}

static DWORD phase5h_native_disposition(uint32_t disposition)
{
    switch (disposition)
    {
    case 0u: return CREATE_ALWAYS;     /* FILE_SUPERSEDE */
    case 1u: return OPEN_EXISTING;     /* FILE_OPEN */
    case 2u: return CREATE_NEW;        /* FILE_CREATE */
    case 3u: return OPEN_ALWAYS;       /* FILE_OPEN_IF */
    case 4u: return TRUNCATE_EXISTING; /* FILE_OVERWRITE */
    case 5u: return CREATE_ALWAYS;     /* FILE_OVERWRITE_IF */
    default: return 0u;
    }
}

static int phase5h_seek_absolute(HANDLE handle, uint32_t lowPart, uint32_t highPart)
{
    LONG high = (LONG)highPart;
    DWORD low;

    SetLastError(ERROR_SUCCESS);
    low = SetFilePointer(
        handle,
        (LONG)lowPart,
        &high,
        FILE_BEGIN);

    return !(
        low == 0xFFFFFFFFu &&
        GetLastError() != ERROR_SUCCESS);
}

static void phase5h_nt_create_file(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t handleVa;
    uint32_t access;
    uint32_t objectAttributesVa;
    uint32_t ioStatusVa;
    uint32_t allocationSizeVa;
    uint32_t fileAttributes;
    uint32_t share;
    uint32_t disposition;
    uint32_t options;
    uint32_t rootDirectory = 0u;
    uint32_t objectNameVa = 0u;
    uint32_t objectAttributes = 0u;
    uint32_t pathLength = 0u;
    uint32_t pathMaximumLength = 0u;
    uint32_t pathVa = 0u;
    uint32_t status = 0u;
    uint32_t token = 0u;
    uint32_t i;
    DWORD nativeDisposition;
    DWORD nativeFlags;
    DWORD nativeAttrs;
    DWORD error = ERROR_SUCCESS;
    HANDLE nativeHandle = INVALID_HANDLE_VALUE;
    int virtualRoot = 0;
    int isDirectory = 0;
    char path[260];
    char nativePath[260];
    char line[1024];

    if (savedEsp != callEsp + 40u)
    {
        sprintf(
            line,
            "NtCreateFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=40",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000BEu,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    handleVa = GUEST_READ32(callEsp + 4u);
    access = GUEST_READ32(callEsp + 8u);
    objectAttributesVa = GUEST_READ32(callEsp + 12u);
    ioStatusVa = GUEST_READ32(callEsp + 16u);
    allocationSizeVa = GUEST_READ32(callEsp + 20u);
    fileAttributes = GUEST_READ32(callEsp + 24u);
    share = GUEST_READ32(callEsp + 28u);
    disposition = GUEST_READ32(callEsp + 32u);
    options = GUEST_READ32(callEsp + 36u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000BEu,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "NtCreateFile LIVE FRAME: ret=%08X handle_ptr=%08X access=%08X oa=%08X iosb=%08X alloc=%08X attrs=%08X share=%08X disposition=%u options=%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)handleVa,
        (unsigned int)access,
        (unsigned int)objectAttributesVa,
        (unsigned int)ioStatusVa,
        (unsigned int)allocationSizeVa,
        (unsigned int)fileAttributes,
        (unsigned int)share,
        (unsigned int)disposition,
        (unsigned int)options,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u ||
        handleVa == 0u ||
        ioStatusVa == 0u ||
        objectAttributesVa == 0u)
    {
        trace("KERNEL FRAME MISMATCH: ordinal 190 invalid return/handle/iosb/object-attributes field");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000BEu,
            savedEsp);
        return;
    }

    rootDirectory = GUEST_READ32(objectAttributesVa + 0u);
    objectNameVa = GUEST_READ32(objectAttributesVa + 4u);
    objectAttributes = GUEST_READ32(objectAttributesVa + 8u);

    if (objectNameVa != 0u)
    {
        pathLength = GUEST_READ16(objectNameVa + 0u);
        pathMaximumLength = GUEST_READ16(objectNameVa + 2u);
        pathVa = GUEST_READ32(objectNameVa + 4u);
    }

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000BEu,
            savedEsp);
        return;
    }

    if (rootDirectory != 0u ||
        pathVa == 0u ||
        pathLength == 0u ||
        pathLength > 255u)
    {
        sprintf(
            line,
            "STORAGE IO UNSUPPORTED: NtCreateFile relative/invalid path root=%08X path_va=%08X len=%u",
            (unsigned int)rootDirectory,
            (unsigned int)pathVa,
            (unsigned int)pathLength);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_IO,
            0x800000BEu,
            savedEsp);
        return;
    }

    for (i = 0u; i < pathLength; ++i)
    {
        path[i] = (char)GUEST_READ8(pathVa + i);
        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x800000BEu,
                savedEsp);
            return;
        }
    }
    path[pathLength] = '\0';

    sprintf(
        line,
        "NtCreateFile OBJECT: root=%08X name=%08X attrs=%08X len=%u max=%u buffer=%08X path=%s",
        (unsigned int)rootDirectory,
        (unsigned int)objectNameVa,
        (unsigned int)objectAttributes,
        (unsigned int)pathLength,
        (unsigned int)pathMaximumLength,
        (unsigned int)pathVa,
        path);
    trace(line);

    if (!phase5b_translate_storage_path(
            path, nativePath, sizeof(nativePath), &virtualRoot))
    {
        sprintf(
            line,
            "STORAGE IO UNSUPPORTED: no Xenon path mapping for %s",
            path);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_IO,
            0x800000BEu,
            savedEsp);
        return;
    }

    nativeDisposition = phase5h_native_disposition(disposition);
    if (nativeDisposition == 0u)
    {
        status = 0xC000000Du; /* STATUS_INVALID_PARAMETER */
    }

    nativeAttrs = GetFileAttributesA(nativePath);
    isDirectory =
        virtualRoot ||
        ((options & 0x00000001u) != 0u) ||
        (nativeAttrs != 0xFFFFFFFFu &&
         (nativeAttrs & FILE_ATTRIBUTE_DIRECTORY) != 0u);

    if (status == 0u &&
        isDirectory &&
        (disposition == 2u || disposition == 3u) &&
        nativeAttrs == 0xFFFFFFFFu)
    {
        if (!CreateDirectoryA(nativePath, NULL) &&
            GetLastError() != ERROR_ALREADY_EXISTS)
        {
            error = GetLastError();
            status = phase5b_open_status_from_error(error);
        }
        nativeAttrs = GetFileAttributesA(nativePath);
    }

    if (status == 0u)
    {
        nativeFlags =
            isDirectory ?
            FILE_FLAG_BACKUP_SEMANTICS :
            FILE_ATTRIBUTE_NORMAL;

        if (!isDirectory && (fileAttributes & 0x00000001u))
            nativeFlags |= FILE_ATTRIBUTE_READONLY;

        SetLastError(ERROR_SUCCESS);
        nativeHandle = CreateFileA(
            nativePath,
            phase5b_native_access(access),
            phase5b_native_share(share),
            NULL,
            isDirectory ? OPEN_EXISTING : nativeDisposition,
            nativeFlags,
            NULL);

        if (nativeHandle == INVALID_HANDLE_VALUE)
        {
            error = GetLastError();
            status = phase5b_open_status_from_error(error);
        }
        else
        {
            token = phase5b_native_handle_token(nativeHandle);
            if (token == 0u)
            {
                CloseHandle(nativeHandle);
                nativeHandle = INVALID_HANDLE_VALUE;
                status = 0xC000009Au; /* STATUS_INSUFFICIENT_RESOURCES */
            }
        }
    }

    if (status == 0u)
    {
        GUEST_WRITE32(handleVa, token);
        GUEST_WRITE32(ioStatusVa + 0u, 0u);
        GUEST_WRITE32(
            ioStatusVa + 4u,
            disposition == 2u ? 2u : 1u);
        ++s_phase5hNtCreateFileSuccessCount;
    }
    else
    {
        GUEST_WRITE32(ioStatusVa + 0u, status);
        GUEST_WRITE32(ioStatusVa + 4u, 0u);
    }

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000BEu,
            savedEsp);
        return;
    }

    ++s_phase5hNtCreateFileCallCount;
    g_eax = status;
    g_esp = savedEsp;

    sprintf(
        line,
        "NtCreateFile NATIVE: xbox=%s native=%s status=%08X token=%08X error=%u disposition=%u options=%08X",
        path,
        nativePath,
        (unsigned int)status,
        (unsigned int)token,
        (unsigned int)error,
        (unsigned int)disposition,
        (unsigned int)options);
    trace(line);

    sprintf(
        line,
        "PASS: Phase 5M NtCreateFile native continuation status=%08X token=%08X calls=%u successes=%u new_esp=%08X",
        (unsigned int)status,
        (unsigned int)token,
        (unsigned int)s_phase5hNtCreateFileCallCount,
        (unsigned int)s_phase5hNtCreateFileSuccessCount,
        (unsigned int)g_esp);
    trace(line);
}

static void phase5h_nt_read_file(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t handleToken;
    uint32_t eventToken;
    uint32_t apcRoutine;
    uint32_t apcContext;
    uint32_t ioStatusVa;
    uint32_t bufferVa;
    uint32_t length;
    uint32_t offsetVa;
    uint32_t offsetLow = 0u;
    uint32_t offsetHigh = 0u;
    uint32_t status = 0u;
    DWORD bytesRead = 0u;
    DWORD error = ERROR_SUCCESS;
    HANDLE nativeHandle;
    BYTE* guestBuffer;
    char line[768];

    if (savedEsp != callEsp + 36u)
    {
        sprintf(
            line,
            "NtReadFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=36",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000DBu,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    handleToken = GUEST_READ32(callEsp + 4u);
    eventToken = GUEST_READ32(callEsp + 8u);
    apcRoutine = GUEST_READ32(callEsp + 12u);
    apcContext = GUEST_READ32(callEsp + 16u);
    ioStatusVa = GUEST_READ32(callEsp + 20u);
    bufferVa = GUEST_READ32(callEsp + 24u);
    length = GUEST_READ32(callEsp + 28u);
    offsetVa = GUEST_READ32(callEsp + 32u);

    if (offsetVa != 0u)
    {
        offsetLow = GUEST_READ32(offsetVa + 0u);
        offsetHigh = GUEST_READ32(offsetVa + 4u);
    }

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000DBu,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "NtReadFile LIVE FRAME: ret=%08X handle=%08X event=%08X apc=%08X context=%08X iosb=%08X buffer=%08X len=%u offset_ptr=%08X offset=%08X%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)handleToken,
        (unsigned int)eventToken,
        (unsigned int)apcRoutine,
        (unsigned int)apcContext,
        (unsigned int)ioStatusVa,
        (unsigned int)bufferVa,
        (unsigned int)length,
        (unsigned int)offsetVa,
        (unsigned int)offsetHigh,
        (unsigned int)offsetLow,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u || ioStatusVa == 0u ||
        (length != 0u && bufferVa == 0u))
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000DBu,
            savedEsp);
        return;
    }

    if (eventToken != 0u || apcRoutine != 0u || apcContext != 0u)
    {
        trace("STORAGE IO UNSUPPORTED: asynchronous NtReadFile event/APC form");
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_IO,
            0x800000DBu,
            savedEsp);
        return;
    }

    nativeHandle = phase5c_read_native_handle(handleToken);
    if (!nativeHandle)
    {
        status = 0xC0000008u; /* STATUS_INVALID_HANDLE */
    }

    guestBuffer = length ? guest_ptr((DWORD)bufferVa, (DWORD)length) : NULL;
    if (status == 0u && length != 0u && !guestBuffer)
    {
        s_accessFault = 1;
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            bufferVa,
            savedEsp);
        return;
    }

    if (status == 0u && offsetVa != 0u)
    {
        if (offsetHigh == 0xFFFFFFFFu && offsetLow == 0xFFFFFFFFu)
        {
            /* FILE_USE_FILE_POINTER_POSITION: keep current position. */
        }
        else if ((offsetHigh & 0x80000000u) != 0u)
        {
            trace("STORAGE IO UNSUPPORTED: NtReadFile negative/special byte offset");
            phase4c_escape(
                PHASE4C_BOUNDARY_STORAGE_IO,
                0x800000DBu,
                savedEsp);
            return;
        }
        else if (!phase5h_seek_absolute(
                     nativeHandle, offsetLow, offsetHigh))
        {
            error = GetLastError();
            status = 0xC0000001u; /* STATUS_UNSUCCESSFUL */
        }
    }

    if (status == 0u)
    {
        SetLastError(ERROR_SUCCESS);
        if (!ReadFile(
                nativeHandle,
                guestBuffer,
                length,
                &bytesRead,
                NULL))
        {
            error = GetLastError();
            if (error == ERROR_HANDLE_EOF)
                status = 0xC0000011u; /* STATUS_END_OF_FILE */
            else
                status = 0xC0000001u; /* STATUS_UNSUCCESSFUL */
        }
        else if (bytesRead == 0u && length > 0u)
        {
            status = 0xC0000011u; /* STATUS_END_OF_FILE */
        }
    }

    GUEST_WRITE32(ioStatusVa + 0u, status);
    GUEST_WRITE32(ioStatusVa + 4u, bytesRead);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000DBu,
            savedEsp);
        return;
    }

    ++s_phase5hNtReadFileCallCount;
    if (status == 0u)
        ++s_phase5hNtReadFileSuccessCount;

    g_eax = status;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5M NtReadFile native continuation handle=%08X status=%08X bytes=%u error=%u calls=%u successes=%u new_esp=%08X",
        (unsigned int)handleToken,
        (unsigned int)status,
        (unsigned int)bytesRead,
        (unsigned int)error,
        (unsigned int)s_phase5hNtReadFileCallCount,
        (unsigned int)s_phase5hNtReadFileSuccessCount,
        (unsigned int)g_esp);
    trace(line);
}

static void phase5b_nt_open_file(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t handleVa;
    uint32_t access;
    uint32_t objectAttributesVa;
    uint32_t ioStatusVa;
    uint32_t share;
    uint32_t options;
    uint32_t rootDirectory = 0u;
    uint32_t objectNameVa = 0u;
    uint32_t attributes = 0u;
    uint32_t pathVa = 0u;
    uint32_t pathLength = 0u;
    uint32_t pathMaximumLength = 0u;
    uint32_t copyLength = 0u;
    uint32_t status = 0u;
    uint32_t token = 0u;
    uint32_t i;
    DWORD nativeFlags;
    DWORD error = ERROR_SUCCESS;
    HANDLE nativeHandle = INVALID_HANDLE_VALUE;
    int virtualRoot = 0;
    char path[260];
    char nativePath[260];
    char line[896];

    if (savedEsp != callEsp + 28u)
    {
        sprintf(
            line,
            "NtOpenFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=28",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000CAu,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    handleVa = GUEST_READ32(callEsp + 4u);
    access = GUEST_READ32(callEsp + 8u);
    objectAttributesVa = GUEST_READ32(callEsp + 12u);
    ioStatusVa = GUEST_READ32(callEsp + 16u);
    share = GUEST_READ32(callEsp + 20u);
    options = GUEST_READ32(callEsp + 24u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000CAu,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "NtOpenFile LIVE FRAME: ret=%08X handle_ptr=%08X access=%08X oa=%08X iosb=%08X share=%08X options=%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)handleVa,
        (unsigned int)access,
        (unsigned int)objectAttributesVa,
        (unsigned int)ioStatusVa,
        (unsigned int)share,
        (unsigned int)options,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u || handleVa == 0u || ioStatusVa == 0u)
    {
        trace("KERNEL FRAME MISMATCH: ordinal 202 invalid return/handle/iosb field");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000CAu,
            savedEsp);
        return;
    }

    path[0] = '\0';
    nativePath[0] = '\0';

    if (objectAttributesVa != 0u)
    {
        rootDirectory = GUEST_READ32(objectAttributesVa + 0u);
        objectNameVa = GUEST_READ32(objectAttributesVa + 4u);
        attributes = GUEST_READ32(objectAttributesVa + 8u);

        if (objectNameVa != 0u)
        {
            pathLength = GUEST_READ16(objectNameVa + 0u);
            pathMaximumLength = GUEST_READ16(objectNameVa + 2u);
            pathVa = GUEST_READ32(objectNameVa + 4u);
        }
    }

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000CAu,
            savedEsp);
        return;
    }

    if (rootDirectory != 0u || pathVa == 0u || pathLength == 0u ||
        pathLength > 255u)
    {
        sprintf(
            line,
            "STORAGE UNSUPPORTED: NtOpenFile relative/invalid path root=%08X path_va=%08X len=%u",
            (unsigned int)rootDirectory,
            (unsigned int)pathVa,
            (unsigned int)pathLength);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_OPEN,
            0x800000CAu,
            savedEsp);
        return;
    }

    copyLength = pathLength;
    for (i = 0u; i < copyLength; ++i)
    {
        uint32_t ch = (uint32_t)GUEST_READ8(pathVa + i);
        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x800000CAu,
                savedEsp);
            return;
        }
        path[i] = (char)ch;
    }
    path[copyLength] = '\0';

    s_phase5bNtOpenFileObjectAttributes = objectAttributesVa;
    s_phase5bNtOpenFilePathVa = pathVa;
    s_phase5bNtOpenFilePathLength = pathLength;

    sprintf(
        line,
        "NtOpenFile OBJECT: root=%08X name=%08X attrs=%08X len=%u max=%u buffer=%08X path=%s",
        (unsigned int)rootDirectory,
        (unsigned int)objectNameVa,
        (unsigned int)attributes,
        (unsigned int)pathLength,
        (unsigned int)pathMaximumLength,
        (unsigned int)pathVa,
        path);
    trace(line);

    if (!phase5b_translate_storage_path(
            path, nativePath, sizeof(nativePath), &virtualRoot))
    {
        sprintf(
            line,
            "STORAGE UNSUPPORTED: no Xenon path mapping for %s",
            path);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_OPEN,
            0x800000CAu,
            savedEsp);
        return;
    }

    if (virtualRoot)
    {
        DWORD rootAttrs = GetFileAttributesA(nativePath);
        if (rootAttrs == 0xFFFFFFFFu)
        {
            if (!CreateDirectoryA(nativePath, NULL) &&
                GetLastError() != ERROR_ALREADY_EXISTS)
            {
                error = GetLastError();
                status = phase5b_open_status_from_error(error);
            }
        }
        else if ((rootAttrs & FILE_ATTRIBUTE_DIRECTORY) == 0u)
        {
            status = 0xC000003Au;
        }
    }

    if (status == 0u)
    {
        nativeFlags =
            (options & 0x00000001u) ?
            FILE_FLAG_BACKUP_SEMANTICS :
            FILE_ATTRIBUTE_NORMAL;

        SetLastError(ERROR_SUCCESS);
        nativeHandle = CreateFileA(
            nativePath,
            phase5b_native_access(access),
            phase5b_native_share(share),
            NULL,
            OPEN_EXISTING,
            nativeFlags,
            NULL);

        if (nativeHandle == INVALID_HANDLE_VALUE)
        {
            error = GetLastError();
            status = phase5b_open_status_from_error(error);
        }
        else
        {
            token = phase5b_native_handle_token(nativeHandle);
            if (token == 0u)
            {
                CloseHandle(nativeHandle);
                nativeHandle = INVALID_HANDLE_VALUE;
                status = 0xC000009Au; /* STATUS_INSUFFICIENT_RESOURCES */
            }
        }
    }

    if (status == 0u)
    {
        GUEST_WRITE32(handleVa, token);
        GUEST_WRITE32(ioStatusVa + 0u, 0u); /* STATUS_SUCCESS */
        GUEST_WRITE32(ioStatusVa + 4u, 1u); /* FILE_OPENED */
    }
    else
    {
        GUEST_WRITE32(ioStatusVa + 0u, status);
        GUEST_WRITE32(ioStatusVa + 4u, 0u);
    }

    if (s_accessFault)
    {
        if (nativeHandle != INVALID_HANDLE_VALUE && token == 0u)
            CloseHandle(nativeHandle);
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000CAu,
            savedEsp);
        return;
    }

    s_phase5bNtOpenFileLastToken = token;
    s_phase5bNtOpenFileLastStatus = status;

    sprintf(
        line,
        "NtOpenFile NATIVE: xbox=%s native=%s status=%08X token=%08X error=%u",
        path,
        nativePath,
        (unsigned int)status,
        (unsigned int)token,
        (unsigned int)error);
    trace(line);

    g_eax = status;
    g_esp = savedEsp;

    if (status == 0u)
    {
        ++s_phase5bNtOpenFileHandledCount;
        sprintf(
            line,
            "PASS: Phase 5M NtOpenFile native continuation status=%08X token=%08X calls=%u new_esp=%08X",
            (unsigned int)status,
            (unsigned int)token,
            (unsigned int)s_phase5bNtOpenFileHandledCount,
            (unsigned int)g_esp);
        trace(line);
    }
    else
    {
        sprintf(
            line,
            "FAIL: Phase 5M NtOpenFile native open failed status=%08X error=%u path=%s",
            (unsigned int)status,
            (unsigned int)error,
            nativePath);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_OPEN,
            0x800000CAu,
            savedEsp);
    }
}

static void phase4c_ex_query_nonvolatile_setting(void)
{
    const uint32_t frameEsp = g_esp;
    const uint32_t returnSlot = recomp_guest_read32(frameEsp + 0u);
    const uint32_t valueIndex = recomp_guest_read32(frameEsp + 4u);
    const uint32_t typeVa = recomp_guest_read32(frameEsp + 8u);
    const uint32_t valueVa = recomp_guest_read32(frameEsp + 12u);
    const uint32_t valueLength = recomp_guest_read32(frameEsp + 16u);
    const uint32_t resultLengthVa = recomp_guest_read32(frameEsp + 20u);
    uint32_t status = 0u;
    uint32_t i;
    char line[448];

    sprintf(
        line,
        "ExQueryNonVolatileSetting LIVE TAIL FRAME: ret=%08X index=%08X type_ptr=%08X value_ptr=%08X len=%u result_ptr=%08X esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)valueIndex,
        (unsigned int)typeVa,
        (unsigned int)valueVa,
        (unsigned int)valueLength,
        (unsigned int)resultLengthVa,
        (unsigned int)frameEsp);
    trace(line);

    /*
     * A direct translated x86 CALL pushes the recompiler's dummy return slot.
     * The retail tail JMP into xboxkrnl ordinal 24 reuses that slot; the
     * stdcall kernel return therefore consumes 4 + 20 bytes.
     */
    if (returnSlot != 0u)
    {
        trace("KERNEL FRAME MISMATCH: ordinal 24 tail frame dummy return is nonzero");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000018u,
            frameEsp);
        return;
    }

    if (valueVa == 0u)
    {
        status = 0xC000000Du; /* STATUS_INVALID_PARAMETER */
    }
    else
    {
        switch (valueIndex)
        {
        case 0x07u: /* XC_LANGUAGE */
            if (valueLength >= 4u)
            {
                recomp_guest_write32(valueVa, 1u); /* English */
                if (typeVa) recomp_guest_write32(typeVa, 4u);
                if (resultLengthVa) recomp_guest_write32(resultLengthVa, 4u);
            }
            break;

        case 0x08u: /* XC_VIDEO */
            if (valueLength >= 4u)
            {
                recomp_guest_write32(valueVa, 0u); /* retail NTSC 4:3 defaults */
                if (typeVa) recomp_guest_write32(typeVa, 4u);
                if (resultLengthVa) recomp_guest_write32(resultLengthVa, 4u);
            }
            break;

        case 0x103u: /* XC_FACTORY_AV_REGION */
            if (valueLength >= 4u)
            {
                recomp_guest_write32(valueVa, 0x00400100u); /* NTSC-M | 60 Hz */
                if (typeVa) recomp_guest_write32(typeVa, 4u);
                if (resultLengthVa) recomp_guest_write32(resultLengthVa, 4u);
            }
            break;

        case 0x09u: /* XC_AUDIO */
            if (valueLength >= 4u)
            {
                recomp_guest_write32(valueVa, 0x00010001u);
                if (typeVa) recomp_guest_write32(typeVa, 4u);
                if (resultLengthVa) recomp_guest_write32(resultLengthVa, 4u);
            }
            break;

        case 0x0Au: /* XC_PARENTAL_CONTROL */
        case 0x11u: /* XC_MISC */
            if (valueLength >= 4u)
            {
                recomp_guest_write32(valueVa, 0u);
                if (typeVa) recomp_guest_write32(typeVa, 4u);
                if (resultLengthVa) recomp_guest_write32(resultLengthVa, 4u);
            }
            break;

        case 0x12u: /* XC_DVD_REGION */
            if (valueLength >= 4u)
            {
                recomp_guest_write32(valueVa, 1u);
                if (typeVa) recomp_guest_write32(typeVa, 4u);
                if (resultLengthVa) recomp_guest_write32(resultLengthVa, 4u);
            }
            break;

        case 0xFFu: /* XC_MAX_OS: 24 ULONG user-settings block */
            if (typeVa) recomp_guest_write32(typeVa, 3u); /* REG_BINARY */
            if (resultLengthVa) recomp_guest_write32(resultLengthVa, 96u);
            if (valueLength < 96u)
            {
                status = 0xC0000023u; /* STATUS_BUFFER_TOO_SMALL */
            }
            else
            {
                for (i = 0u; i < 24u; ++i)
                    recomp_guest_write32(valueVa + i * 4u, 0u);
                recomp_guest_write32(valueVa + 12u * 4u, 1u);          /* language */
                recomp_guest_write32(valueVa + 13u * 4u, 0u);          /* video */
                recomp_guest_write32(valueVa + 14u * 4u, 0x00010001u); /* audio */
                recomp_guest_write32(valueVa + 23u * 4u, 1u);          /* DVD region */
            }
            break;

        case 0x00u: /* XC_TIMEZONE_BIAS */
            if (typeVa) recomp_guest_write32(typeVa, 4u);
            if (resultLengthVa) recomp_guest_write32(resultLengthVa, 4u);
            if (valueLength < 4u)
                status = 0xC0000023u;
            else
                recomp_guest_write32(valueVa, 0u);
            break;

        default:
            for (i = 0u; i < valueLength; ++i)
                recomp_guest_write8(valueVa + i, 0u);
            if (typeVa) recomp_guest_write32(typeVa, 4u);
            if (resultLengthVa) recomp_guest_write32(resultLengthVa, valueLength);
            break;
        }
    }

    g_eax = status;
    g_esp = frameEsp + 24u;
    s_phase4cNvQueryHandled = 1;
    s_phase4cNvQueryIndex = valueIndex;
    s_phase4cNvQueryValueVa = valueVa;
    s_phase4cNvQueryValueLength = valueLength;

    sprintf(
        line,
        "PASS: ordinal 24 ExQueryNonVolatileSetting matched guest EEPROM semantics status=%08X new_esp=%08X",
        (unsigned int)g_eax,
        (unsigned int)g_esp);
    trace(line);
}

static void phase4c_rtl_nt_status_to_dos_error(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t status;
    uint32_t dosError;
    char line[352];

    if (savedEsp != callEsp + 8u)
    {
        sprintf(
            line,
            "RtlNtStatusToDosError FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=8",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x8000012Du,
            savedEsp);
        return;
    }

    returnSlot = recomp_guest_read32(callEsp + 0u);
    status = recomp_guest_read32(callEsp + 4u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x8000012Du,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "RtlNtStatusToDosError LIVE FRAME: ret=%08X status=%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)status,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u)
    {
        trace("KERNEL FRAME MISMATCH: ordinal 301 dummy return is nonzero");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x8000012Du,
            savedEsp);
        return;
    }

    /* Match bridge_RtlNtStatusToDosError exactly. */
    switch (status)
    {
    case 0x00000000u: dosError = 0u; break;
    case 0xC0000034u: dosError = 2u; break;
    case 0xC000003Au: dosError = 3u; break;
    case 0xC0000022u: dosError = 5u; break;
    case 0xC0000008u: dosError = 6u; break;
    case 0xC0000017u: dosError = 8u; break;
    case 0xC000000Du: dosError = 87u; break;
    default:          dosError = 317u; break;
    }

    g_eax = dosError;
    g_esp = callEsp + 8u;

    if (g_esp != savedEsp)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x8000012Du,
            savedEsp);
        return;
    }

    s_phase4cNtStatusMapped = 1;
    s_phase4cNtStatusInput = status;
    s_phase4cNtStatusDosError = dosError;

    sprintf(
        line,
        "PASS: ordinal 301 RtlNtStatusToDosError matched runtime bridge semantics status=%08X dos_error=%u new_esp=%08X",
        (unsigned int)status,
        (unsigned int)dosError,
        (unsigned int)g_esp);
    trace(line);
}

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
        trace("FAIL: live StartRoutine is absent from the Phase 5M pack");
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

static void phase4c_initialize_critical_section(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t criticalSection;
    char line[320];

    /*
     * Ordinal 291 is stdcall
     * RtlInitializeCriticalSection(PRTL_CRITICAL_SECTION).
     * Hardware 4C-AA observed savedEsp-callEsp == 8:
     * one dword argument plus the translated synthetic CALL return.
     */
    if (savedEsp != callEsp + 8u)
    {
        sprintf(
            line,
            "RtlInitializeCriticalSection FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=8",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000123u,
            savedEsp);
        return;
    }

    criticalSection = GUEST_READ32(callEsp + 4u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000123u,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "RtlInitializeCriticalSection LIVE FRAME: cs=%08X esp=%08X saved_esp=%08X",
        (unsigned int)criticalSection,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    /*
     * Match bridge_RtlInitializeCriticalSection and kernel_rtl.c:
     * serialized guest execution intentionally takes no host lock and does not
     * reinterpret the guest critical-section storage as a native host object.
     * The bridge returns EAX=0 and stdcall consumes its one argument.
     */
    ++s_phase4cCriticalSectionInitCount;
    s_phase4cCriticalSectionInitLastVa = criticalSection;
    g_eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: ordinal 291 RtlInitializeCriticalSection matched maintained serialized-guest semantics cs=%08X calls=%u new_esp=%08X",
        (unsigned int)criticalSection,
        (unsigned int)s_phase4cCriticalSectionInitCount,
        (unsigned int)g_esp);
    trace(line);
}

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

static uint64_t phase4c_system_time_100ns(void)
{
    FILETIME value;
    GetSystemTimeAsFileTime(&value);
    return ((uint64_t)value.dwHighDateTime << 32) |
           (uint64_t)value.dwLowDateTime;
}

static void phase4c_ke_set_timer(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t timerVa;
    uint32_t dueLow;
    uint32_t dueHigh;
    uint32_t dpcVa;
    uint64_t dueBits;
    int64_t dueTime;
    uint64_t now;
    uint64_t absoluteDue;
    uint64_t relative;
    int wasActive;
    char line[512];

    if (savedEsp != callEsp + 20u)
    {
        sprintf(
            line,
            "KeSetTimer FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=20",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000095u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    timerVa = GUEST_READ32(callEsp + 4u);
    dueLow = GUEST_READ32(callEsp + 8u);
    dueHigh = GUEST_READ32(callEsp + 12u);
    dpcVa = GUEST_READ32(callEsp + 16u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000095u,
            savedEsp);
        return;
    }

    dueBits = (uint64_t)dueLow | ((uint64_t)dueHigh << 32);
    dueTime = (int64_t)dueBits;

    sprintf(
        line,
        "KeSetTimer LIVE FRAME: ret=%08X timer=%08X due=%08X%08X dpc=%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)timerVa,
        (unsigned int)dueHigh,
        (unsigned int)dueLow,
        (unsigned int)dpcVa,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u)
    {
        trace("KERNEL FRAME MISMATCH: ordinal 149 dummy return is nonzero");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000095u,
            savedEsp);
        return;
    }

    if (timerVa == 0u)
    {
        g_eax = 0u;
        g_esp = savedEsp;
        s_phase4cTimerWasActive = 0;
        s_phase4cTimerArmed = 0;
        trace("PASS: ordinal 149 KeSetTimer matched null-timer FALSE semantics");
        return;
    }

    now = phase4c_system_time_100ns();
    if (dueTime < 0)
    {
        relative = (uint64_t)(-(dueTime + 1)) + 1u;
        absoluteDue = now + relative;
    }
    else
    {
        absoluteDue = dueTime ? (uint64_t)dueTime : now;
    }

    wasActive = s_phase4cTimerArmed ? 1 : 0;

    /* Match bridge_set_guest_timer guest-visible KTIMER state. */
    GUEST_WRITE8(timerVa + 3u, 1u);
    GUEST_WRITE32(timerVa + 4u, 0u);
    GUEST_WRITE32(timerVa + 16u, (uint32_t)absoluteDue);
    GUEST_WRITE32(timerVa + 20u, (uint32_t)(absoluteDue >> 32));
    GUEST_WRITE32(timerVa + 32u, dpcVa);
    GUEST_WRITE32(timerVa + 36u, 0u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000095u,
            savedEsp);
        return;
    }

    s_phase4cTimerArmed = 1;
    s_phase4cTimerDue100ns = absoluteDue;
    s_phase4cTimerDpcVa = dpcVa;
    s_phase4cTimerWasActive = wasActive;

    g_eax = wasActive ? 1u : 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: ordinal 149 KeSetTimer matched guest-KTIMER semantics was_active=%u due_abs=%08X%08X dpc=%08X new_esp=%08X",
        (unsigned int)g_eax,
        (unsigned int)(absoluteDue >> 32),
        (unsigned int)absoluteDue,
        (unsigned int)dpcVa,
        (unsigned int)g_esp);
    trace(line);

    /*
     * The production bridge marks an already-expired timer pending and
     * delivers its guest DPC only at a safe point. Do not silently step past
     * that dependency in this bounded proof.
     */
    if (absoluteDue <= phase4c_system_time_100ns() && dpcVa != 0u)
    {
        trace("TIMER DUE BOUNDARY: ordinal 149 armed an already-due DPC");
        phase4c_escape(
            PHASE4C_BOUNDARY_TIMER_DUE,
            dpcVa,
            savedEsp);
    }
}

static uint32_t phase4c_page_round(uint32_t size)
{
    if (size == 0u || size > 0xFFFFF000u)
        return 0u;
    return (size + 0xFFFu) & ~0xFFFu;
}

static int phase4c_vm_page_range(
    uint32_t base,
    uint32_t size,
    uint32_t* firstPage,
    uint32_t* lastPage)
{
    uint32_t roundedBase;
    uint32_t end;

    if (size == 0u || base >= RAM_SIZE || size > RAM_SIZE - base)
        return 0;

    roundedBase = base & ~0xFFFu;
    end = base + size - 1u;
    if (firstPage)
        *firstPage = roundedBase >> PHASE4C_VM_PAGE_SHIFT;
    if (lastPage)
        *lastPage = end >> PHASE4C_VM_PAGE_SHIFT;
    return 1;
}

static int phase4c_vm_range_reserved(
    uint32_t base,
    uint32_t size)
{
    uint32_t index;
    uint64_t end = (uint64_t)base + (uint64_t)size;

    for (index = 0u;
         index < s_phase4cVmReservationCount;
         ++index)
    {
        const Phase4CVmReservation* reservation =
            &s_phase4cVmReservations[index];
        uint64_t reservationEnd;

        if (!reservation->inUse)
            continue;
        reservationEnd =
            (uint64_t)reservation->base +
            (uint64_t)reservation->size;
        if ((uint64_t)base >= (uint64_t)reservation->base &&
            end <= reservationEnd)
            return 1;
    }

    return 0;
}

static uint32_t phase4c_vm_reserve(
    uint32_t requested,
    uint32_t protect,
    int commitNow,
    uint32_t* allocationSize)
{
    uint32_t size = phase4c_page_round(requested);
    uint32_t base;
    uint32_t firstPage;
    uint32_t lastPage;
    uint32_t page;

    if (allocationSize)
        *allocationSize = 0u;

    if (size == 0u ||
        s_phase4cVmReservationCount >=
            PHASE4C_VM_RESERVATION_CAP)
        return 0u;

    /*
     * Match the production allocator's page-backed direction: ordinary
     * allocations grow upward from XBOX_HEAP_BASE while page-backed virtual
     * ranges grow downward from the top of installed RAM.
     *
     * The focused Phase-4C ordinary heap still ends at
     * PHASE4C_TITLE_HEAP_END, so never cross that lower bound.
     */
    if (size > s_phase4cVmPageNext - PHASE4C_TITLE_HEAP_END)
        return 0u;

    base = (s_phase4cVmPageNext - size) & ~0xFFFu;
    if (base < PHASE4C_TITLE_HEAP_END ||
        !phase4c_vm_page_range(
            base, size, &firstPage, &lastPage))
        return 0u;

    for (page = firstPage; page <= lastPage; ++page)
    {
        if (s_phase4cVmPageState[page] !=
            PHASE4C_VM_PAGE_UNMANAGED)
            return 0u;
    }

    s_phase4cVmReservations[s_phase4cVmReservationCount].base =
        base;
    s_phase4cVmReservations[s_phase4cVmReservationCount].size =
        size;
    s_phase4cVmReservations[s_phase4cVmReservationCount].protect =
        protect;
    s_phase4cVmReservations[s_phase4cVmReservationCount].inUse =
        1u;
    ++s_phase4cVmReservationCount;

    for (page = firstPage; page <= lastPage; ++page)
    {
        s_phase4cVmPageState[page] =
            commitNow ?
            PHASE4C_VM_PAGE_COMMITTED :
            PHASE4C_VM_PAGE_RESERVED;
        s_phase4cVmPageProtect[page] =
            commitNow ? protect : 0u;
    }

    if (commitNow)
        memset(g_ram + base, 0, size);

    s_phase4cVmPageNext = base;
    if (allocationSize)
        *allocationSize = size;
    return base;
}

static int phase4c_vm_commit(
    uint32_t base,
    uint32_t size,
    uint32_t protect)
{
    uint32_t firstPage;
    uint32_t lastPage;
    uint32_t page;

    if (!phase4c_vm_page_range(
            base, size, &firstPage, &lastPage))
        return 0;

    /*
     * A later MEM_COMMIT is expected to target the VA returned by reserve.
     * Retain production bridge permissiveness for valid unmanaged guest RAM,
     * but never let a commit cross the edge of a tracked reservation.
     */
    if (phase4c_vm_range_reserved(base, size))
    {
        for (page = firstPage; page <= lastPage; ++page)
        {
            if (s_phase4cVmPageState[page] ==
                PHASE4C_VM_PAGE_RESERVED)
            {
                memset(
                    g_ram + page * PHASE4C_VM_PAGE_SIZE,
                    0,
                    PHASE4C_VM_PAGE_SIZE);
            }
            s_phase4cVmPageState[page] =
                PHASE4C_VM_PAGE_COMMITTED;
            s_phase4cVmPageProtect[page] = protect;
        }
        return 1;
    }

    /*
     * Unmanaged pages are the pre-existing Phase-4C arena. The production
     * GuestMemoryCommit accepts any valid RAM page range, so keep that
     * behavior without zeroing already-live XBE/stack contents.
     */
    for (page = firstPage; page <= lastPage; ++page)
    {
        if (s_phase4cVmPageState[page] ==
            PHASE4C_VM_PAGE_RESERVED)
            return 0;
        s_phase4cVmPageState[page] =
            PHASE4C_VM_PAGE_COMMITTED;
        s_phase4cVmPageProtect[page] = protect;
    }
    return 1;
}

static void phase4c_nt_allocate_virtual_memory(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t basePtr;
    uint32_t zeroBits;
    uint32_t sizePtr;
    uint32_t allocType;
    uint32_t protect;
    uint32_t baseHint = 0u;
    uint32_t size = 0u;
    uint32_t allocationSize = 0u;
    uint32_t xboxVa = 0u;
    uint32_t status = 0u;
    char line[704];

    if (savedEsp != callEsp + 24u)
    {
        sprintf(
            line,
            "NtAllocateVirtualMemory FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=24",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000B8u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    basePtr = GUEST_READ32(callEsp + 4u);
    zeroBits = GUEST_READ32(callEsp + 8u);
    sizePtr = GUEST_READ32(callEsp + 12u);
    allocType = GUEST_READ32(callEsp + 16u);
    protect = GUEST_READ32(callEsp + 20u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000B8u,
            savedEsp);
        return;
    }

    if (basePtr != 0u)
        baseHint = GUEST_READ32(basePtr);
    if (sizePtr != 0u)
        size = GUEST_READ32(sizePtr);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000B8u,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "NtAllocateVirtualMemory LIVE FRAME: ret=%08X base_ptr=%08X base_hint=%08X zero_bits=%u size_ptr=%08X size=%u type=%08X protect=%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)basePtr,
        (unsigned int)baseHint,
        (unsigned int)zeroBits,
        (unsigned int)sizePtr,
        (unsigned int)size,
        (unsigned int)allocType,
        (unsigned int)protect,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u)
    {
        trace("KERNEL FRAME MISMATCH: ordinal 184 dummy return is nonzero");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000B8u,
            savedEsp);
        return;
    }

    ++s_phase4cVmAllocCount;

    if (basePtr == 0u || sizePtr == 0u || size == 0u)
    {
        status = 0xC000000Du; /* STATUS_INVALID_PARAMETER */
    }
    else if (baseHint != 0u &&
             (allocType & MEM_RESERVE) == 0u)
    {
        if ((allocType & MEM_COMMIT) == 0u ||
            !phase4c_vm_commit(baseHint, size, protect))
        {
            status = 0xC000000Du;
        }
        else
        {
            status = 0u;
            xboxVa = baseHint;
            allocationSize = size;
        }
    }
    else if ((allocType & MEM_RESERVE) != 0u)
    {
        xboxVa = phase4c_vm_reserve(
            size,
            protect,
            (allocType & MEM_COMMIT) != 0u,
            &allocationSize);
        if (xboxVa == 0u)
        {
            status = 0xC0000017u; /* STATUS_NO_MEMORY */
        }
        else
        {
            status = 0u;
            GUEST_WRITE32(basePtr, xboxVa);
            GUEST_WRITE32(sizePtr, allocationSize);
            if (s_accessFault)
            {
                phase4c_escape(
                    PHASE4C_BOUNDARY_GUEST_FAULT,
                    0x800000B8u,
                    savedEsp);
                return;
            }
        }
    }
    else
    {
        status = 0xC000000Du;
    }

    s_phase4cVmAllocLastStatus = status;
    s_phase4cVmAllocLastBase = xboxVa;
    s_phase4cVmAllocLastSize = allocationSize;

    g_eax = status;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: ordinal 184 NtAllocateVirtualMemory matched reserved/commit guest-VM semantics status=%08X base=%08X size=%u calls=%u page_next=%08X new_esp=%08X",
        (unsigned int)status,
        (unsigned int)xboxVa,
        (unsigned int)allocationSize,
        (unsigned int)s_phase4cVmAllocCount,
        (unsigned int)s_phase4cVmPageNext,
        (unsigned int)g_esp);
    trace(line);
}

/*
 * Exact maintained Mercenaries CRT memmove ABI used by the production port.
 * The translated CALL has already pushed the recompiler's dummy return slot.
 * CRT memmove is cdecl, so this helper consumes only that return slot; the
 * caller remains responsible for its 12 argument bytes.
 */
void recomp_crt_memmove(void)
{
    const uint32_t frameEsp = g_esp;
    const uint32_t returnSlot = GUEST_READ32(frameEsp + 0u);
    const uint32_t destination = GUEST_READ32(frameEsp + 4u);
    const uint32_t source = GUEST_READ32(frameEsp + 8u);
    const uint32_t length = GUEST_READ32(frameEsp + 12u);
    BYTE* dst = NULL;
    BYTE* src = NULL;
    char line[448];

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x00238C00u,
            frameEsp);
        return;
    }

    sprintf(
        line,
        "CRT memmove LIVE FRAME: ret=%08X dest=%08X src=%08X len=%u esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)destination,
        (unsigned int)source,
        (unsigned int)length,
        (unsigned int)frameEsp);
    trace(line);

    if (returnSlot != 0u)
    {
        trace("CRT memmove FRAME MISMATCH: translated dummy return is nonzero");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x00238C00u,
            frameEsp);
        return;
    }

    if (length != 0u)
    {
        dst = guest_ptr(destination, length);
        src = guest_ptr(source, length);
        if (!dst || !src)
        {
            trace("CRT memmove GUEST RANGE FAILURE");
            if (!dst)
                phase4c_note_access_fault(destination, length, 1u);
            else
                phase4c_note_access_fault(source, length, 0u);
            if (!s_phase4cFaultEscapeArmed)
            {
                phase4c_escape(
                    PHASE4C_BOUNDARY_GUEST_FAULT,
                    !dst ? destination : source,
                    frameEsp);
            }
            return;
        }

        memmove(dst, src, length);
    }

    g_eax = destination;
    g_esp = frameEsp + 4u;

    sprintf(
        line,
        "PASS: recomp_crt_memmove matched maintained cdecl semantics dest=%08X src=%08X len=%u new_esp=%08X",
        (unsigned int)destination,
        (unsigned int)source,
        (unsigned int)length,
        (unsigned int)g_esp);
    trace(line);
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
        trace("FAIL: hardware-confirmed startup callback is absent from Phase 5M pack");
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
        raise SystemExit("[Phase5M] Phase 4C-A report is not a PASS")

    if (
        thread_report.get("phase") != "4C-D"
        or thread_report.get("structural_pass") is not True
    ):
        raise SystemExit("[Phase5M] Phase 4C-D report is not a PASS")

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
                f"[Phase5M] hardware observation mismatch for {key}: "
                f"expected {value!r}, got {observed.get(key)!r}"
            )

    root_va = int(str(entry_report["entry"]), 0)
    if root_va != 0x0022964A:
        raise SystemExit(
            f"[Phase5M] unexpected XBE entry 0x{root_va:08X}"
        )

    thread_root = int(str(thread_report["closure"]["entry"]), 0)
    if thread_root != THREAD_START:
        raise SystemExit(
            f"[Phase5M] unexpected thread root 0x{thread_root:08X}"
        )

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)

    manual_b178_row = by_va.get(LIVE_DIRECT_FRONTIER_TARGET_16)
    if manual_b178_row is None:
        raise SystemExit(
            "[Phase5M] maintained manual target 0x0022B178 is absent from the function inventory"
        )
    if manual_b178_row["name"] != "sub_0022B178":
        raise SystemExit(
            "[Phase5M] maintained manual target 0x0022B178 name changed: "
            + str(manual_b178_row["name"])
        )

    # Recompile.ps1 deliberately passes --manual-function 0x0022B178.
    # The Phase-4C boundary/support layer already owns the maintained
    # SetLastError implementation for this address. Keep only metadata in the
    # generated map so closure/lookup logic can name the root; phase5a_boundary
    # instruments the single support-owned body below. Never emit a second
    # translated/manual definition into the body pack.
    generated[LIVE_DIRECT_FRONTIER_TARGET_16] = {
        "name": "sub_0022B178",
        "file": "<maintained-manual:recomp_manual.c>",
        "source": """void sub_0022B178(void)
{
    /* support-owned maintained SetLastError; emitted by phase5a_boundary */
}""",
        "emit_mode": "support-owned",
    }

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
    previous_promoted_closure_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_5,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    prior_safe_root_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_6,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    prior_root_38c00_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_7,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )

    prior_root_d431_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_8,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )

    prior_root_ca2b_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_9,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )

    prior_root_c8ea_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_10,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )

    prior_root_ceee_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_11,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )

    prior_root_c1c0_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_12,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )

    prior_root_370b8_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_13,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )

    prior_root_be8c_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_14,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )

    prior_root_f026_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_15,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )

    # 5L promotes only the exact hardware-observed post-section-scan root.
    # Distinguish a normal function start from a mid-function/split target
    # before packaging.
    if LIVE_DIRECT_FRONTIER_TARGET_16 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_16 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5M] target 0x0022B178 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5L requires a split/mid-function promotion."
            )
        raise SystemExit(
            "[Phase5M] target 0x0022B178 is absent from the function inventory"
        )

    if generated[LIVE_DIRECT_FRONTIER_TARGET_16].get("file") != "<maintained-manual:recomp_manual.c>":
        raise SystemExit(
            "[Phase5M] target 0x0022B178 must use the reviewed maintained manual body"
        )

    promoted_closure_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_16,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    promoted_direct_members = {
        LIVE_DIRECT_FRONTIER_TARGET,
        LIVE_DIRECT_FRONTIER_TARGET_2,
        LIVE_DIRECT_FRONTIER_TARGET_3,
        LIVE_DIRECT_FRONTIER_TARGET_4,
    } | previous_promoted_closure_members | prior_safe_root_members | prior_root_38c00_members | prior_root_d431_members | prior_root_ca2b_members | prior_root_c8ea_members | prior_root_ceee_members | prior_root_c1c0_members | prior_root_370b8_members | prior_root_be8c_members | prior_root_f026_members | promoted_closure_members
    member_vas = sorted(
        entry_members | thread_members | callback_members | promoted_direct_members
    )
    packed_vas = set(member_vas)

    missing_generated = [va for va in member_vas if va not in generated]
    if missing_generated:
        raise SystemExit(
            "[Phase5M] generated body missing for packed member(s): "
            + ", ".join(f"0x{va:08X}" for va in missing_generated)
        )

    root_row = by_va.get(root_va)
    if root_row is None:
        raise SystemExit("[Phase5M] XBE entry absent from function inventory")
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

        if va == LIVE_DIRECT_FRONTIER_TARGET_16:
            if row.get("emit_mode") != "support-owned":
                raise SystemExit(
                    "[Phase5M] B178 must remain support-owned during body emission"
                )
            # phase5a_boundary() already emitted the one canonical maintained
            # body before the pack lookup and translated bodies.
            rendered_by_va[va] = ""
            continue

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
        raise SystemExit("[Phase5M] Phase-3N support donor marker missing")

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

    support = support.replace("[Merc360:P3N]", "[Merc360:P5]")
    support = instrument_first_fault_support(support)
    support = instrument_kernel_header_page(support)

    boundary = phase5a_boundary(base)

    supplied = base.support_symbols(support + boundary)
    supplied.update(translated_names)
    supplied.update({
        "sub_0022B150",
        "sub_0022B178",
        "sub_0022DDA4",
        "sub_0022E51F",
        "phase4c_lookup_pack_func",
        "phase4c_enter_first_title_thread",
        "phase5d_io_create_symbolic_link",
        "phase5d_io_delete_symbolic_link",
        "phase5k_rtl_equal_string",
        "phase5i_rtl_init_ansi_string",
        "phase5h_nt_create_file",
        "phase5h_nt_read_file",
        "phase5c_query_volume_information",
        "phase5c_nt_close",
        "phase5b_nt_open_file",
        "phase4c_initialize_critical_section",
        "phase4c_enter_critical_section",
        "phase4c_leave_critical_section",
        "phase4c_enter_startup_callback",
        "phase4c_hal_register_shutdown_notification",
        "phase4c_ke_initialize_dpc",
        "phase4c_ke_initialize_timer_ex",
        "phase4c_ex_query_nonvolatile_setting",
        "phase4c_rtl_nt_status_to_dos_error",
        "phase4c_ke_set_timer",
        "phase4c_system_time_100ns",
        "phase4c_page_round",
        "phase4c_vm_page_range",
        "phase4c_vm_range_reserved",
        "phase4c_vm_reserve",
        "phase4c_vm_commit",
        "phase4c_nt_allocate_virtual_memory",
        "recomp_crt_memmove",
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
        "phase": "5L",
        "build_tag": "P5M-NTQUERYINFO211-CAPTURE-20261020-A",
        "entry": f"0x{root_va:08X}",
        "thread_start": f"0x{THREAD_START:08X}",
        "thread_context1": f"0x{THREAD_CTX1:08X}",
        "thread_context2": f"0x{THREAD_CTX2:08X}",
        "startup_callback": f"0x{STARTUP_CALLBACK:08X}",
        "promoted_direct_frontier_target": f"0x{LIVE_DIRECT_FRONTIER_TARGET:08X}",
        "promoted_direct_frontier_target_2": f"0x{LIVE_DIRECT_FRONTIER_TARGET_2:08X}",
        "promoted_direct_frontier_target_3": f"0x{LIVE_DIRECT_FRONTIER_TARGET_3:08X}",
        "promoted_direct_frontier_target_4": f"0x{LIVE_DIRECT_FRONTIER_TARGET_4:08X}",
        "promoted_direct_frontier_target_5": f"0x{LIVE_DIRECT_FRONTIER_TARGET_5:08X}",
        "promoted_closure_5_members": [
            f"0x{va:08X}" for va in sorted(previous_promoted_closure_members)
        ],
        "promoted_direct_frontier_target_6": f"0x{LIVE_DIRECT_FRONTIER_TARGET_6:08X}",
        "promoted_closure_6_members": [
            f"0x{va:08X}" for va in sorted(prior_safe_root_members)
        ],
        "promoted_direct_frontier_target_7": f"0x{LIVE_DIRECT_FRONTIER_TARGET_7:08X}",
        "promoted_closure_7_members": [
            f"0x{va:08X}" for va in sorted(prior_root_38c00_members)
        ],
        "promoted_direct_frontier_target_8": f"0x{LIVE_DIRECT_FRONTIER_TARGET_8:08X}",
        "promoted_closure_8_members": [
            f"0x{va:08X}" for va in sorted(prior_root_d431_members)
        ],
        "promoted_direct_frontier_target_9": f"0x{LIVE_DIRECT_FRONTIER_TARGET_9:08X}",
        "promoted_closure_9_members": [
            f"0x{va:08X}" for va in sorted(prior_root_ca2b_members)
        ],
        "promoted_direct_frontier_target_10": f"0x{LIVE_DIRECT_FRONTIER_TARGET_10:08X}",
        "promoted_closure_10_members": [
            f"0x{va:08X}" for va in sorted(prior_root_c8ea_members)
        ],
        "promoted_direct_frontier_target_11": f"0x{LIVE_DIRECT_FRONTIER_TARGET_11:08X}",
        "promoted_closure_11_members": [
            f"0x{va:08X}" for va in sorted(prior_root_ceee_members)
        ],
        "promoted_direct_frontier_target_12": f"0x{LIVE_DIRECT_FRONTIER_TARGET_12:08X}",
        "promoted_closure_12_members": [
            f"0x{va:08X}" for va in sorted(prior_root_c1c0_members)
        ],
        "promoted_direct_frontier_target_13": f"0x{LIVE_DIRECT_FRONTIER_TARGET_13:08X}",
        "promoted_closure_13_members": [
            f"0x{va:08X}" for va in sorted(prior_root_370b8_members)
        ],
        "promoted_direct_frontier_target_14": f"0x{LIVE_DIRECT_FRONTIER_TARGET_14:08X}",
        "promoted_closure_14_members": [
            f"0x{va:08X}" for va in sorted(prior_root_be8c_members)
        ],
        "promoted_direct_frontier_target_15": f"0x{LIVE_DIRECT_FRONTIER_TARGET_15:08X}",
        "promoted_closure_15_members": [
            f"0x{va:08X}" for va in sorted(prior_root_f026_members)
        ],
        "promoted_direct_frontier_target_16": f"0x{LIVE_DIRECT_FRONTIER_TARGET_16:08X}",
        "promoted_direct_frontier_target_16_mode": "manual-maintained",
        "manual_maintained_root_16": {
            "address": "0x0022B178",
            "name": "sub_0022B178",
            "production_source": "ports/mercenaries/src/recomp_manual.c",
            "semantic_name": "SetLastError",
            "abi": "stdcall one uint32 argument; preserve EAX; g_esp += 8",
            "state_policy": "stable runtime last-error value instead of flattened Xbox FS-backed TIB",
        },
        "promoted_closure_depth": PROMOTED_CLOSURE_DEPTH,
        "promoted_closure_cap": PROMOTED_CLOSURE_CAP,
        "promoted_closure_members": [
            f"0x{va:08X}" for va in sorted(promoted_closure_members)
        ],
        "phase5_nt_query_information_file_capture": {
            "target": "0x800000D3",
            "ordinal": 211,
            "name": "NtQueryInformationFile",
            "arg_bytes": 20,
            "frame_bytes": 24,
            "mode": "capture-only",
            "policy": "capture exact hardware handle/IO_STATUS_BLOCK/buffer/length/class before implementing a class payload",
        },
        "phase5_rtl_equal_string": {
            "target": "0x80000117",
            "ordinal": 279,
            "name": "RtlEqualString",
            "arg_bytes": 12,
            "frame_bytes": 16,
            "mode": "maintained-native-continuation",
            "guest_layout": "ANSI_STRING operands: Length u16, MaximumLength u16, Buffer u32 guest VA",
            "comparison_policy": "exact byte-length equality with optional ASCII case folding",
            "preview_policy": "bounded printable preview of first 128 bytes per operand",
        },
        "phase5_rtl_init_ansi_string": {
            "target": "0x80000121",
            "ordinal": 289,
            "name": "RtlInitAnsiString",
            "arg_bytes": 8,
            "frame_bytes": 12,
            "mode": "maintained-native-continuation",
            "guest_layout": "ANSI_STRING: Length u16, MaximumLength u16, Buffer u32 guest VA",
            "source_policy": "bounded guest C-string scan with maintained 0xFFFE clamp",
        },
        "phase5_nt_create_file": {
            "target": "0x800000BE",
            "ordinal": 190,
            "name": "NtCreateFile",
            "arg_bytes": 36,
            "frame_bytes": 40,
            "mode": "native-continuation",
            "path_policy": "reuse guest symbolic-link expansion and native Xenon storage mapping",
            "handle_policy": "stable tagged 32-bit guest token backed by native Xenon HANDLE table",
            "create_dispositions": "0..5 mapped to CreateFileA semantics",
        },
        "phase5_nt_read_file": {
            "target": "0x800000DB",
            "ordinal": 219,
            "name": "NtReadFile",
            "arg_bytes": 32,
            "frame_bytes": 36,
            "mode": "synchronous-native-continuation",
            "async_policy": "event/APC forms remain fenced",
        },
        "phase5_symbolic_link": {
            "target": "0x80000043",
            "ordinal": 67,
            "name": "IoCreateSymbolicLink",
            "arg_bytes": 8,
            "frame_bytes": 12,
            "semantics": "decode guest ANSI_STRING link/target, collision-check, record mapping, resume",
            "path_integration": "guest-created \\??\\X: aliases are expanded before storage path translation",
        },
        "phase5_symbolic_link_delete": {
            "target": "0x80000045",
            "ordinal": 69,
            "name": "IoDeleteSymbolicLink",
            "arg_bytes": 4,
            "frame_bytes": 8,
            "semantics": "remove recorded guest symbolic-link mapping",
        },
        "phase5_volume_query": {
            "target": "0x800000DA",
            "ordinal": 218,
            "name": "NtQueryVolumeInformationFile",
            "arg_bytes": 20,
            "frame_bytes": 24,
            "supported_class": 3,
            "supported_class_name": "XboxFileFsSizeInformation",
            "native_primitive": "GetDiskFreeSpaceExA(game:\\)",
            "guest_geometry": "512-byte sectors, 32 sectors per allocation unit",
            "handle_policy": "resolve tagged 32-bit guest token to native Xenon HANDLE",
        },
        "phase5_handle_close": {
            "target": "0x800000BB",
            "ordinal": 187,
            "name": "NtClose",
            "arg_bytes": 4,
            "frame_bytes": 8,
            "native_primitive": "CloseHandle",
            "handle_policy": "take tagged guest token and release native Xenon HANDLE",
        },
        "phase5_storage_boundary": {
            "target": "0x800000CA",
            "ordinal": 202,
            "name": "NtOpenFile",
            "arg_bytes": 24,
            "frame_bytes": 28,
            "mode": "native-continuation",
            "captures": [
                "handle pointer",
                "desired access",
                "OBJECT_ATTRIBUTES root/name/attributes",
                "ANSI_STRING length/maximum/buffer/path",
                "IO_STATUS_BLOCK pointer",
                "share access",
                "open options",
            ],
            "native_mapping": "\\Device\\Harddisk0\\partition1\\ -> game:\\merc360-partition1",
            "native_primitive": "CreateFileA / OPEN_EXISTING / FILE_FLAG_BACKUP_SEMANTICS for directory opens",
            "handle_policy": "stable tagged 32-bit guest token backed by native Xenon HANDLE table",
            "next_gate": "continue real boot path and capture the next live storage/runtime dependency",
        },
        "continued_kernel_call_291": {
            "target": "0x80000123",
            "ordinal": 291,
            "name": "RtlInitializeCriticalSection",
            "arg_bytes": 4,
            "frame_bytes": 8,
            "production_semantics": "serialized guest no-op; EAX=0; stdcall cleanup; no host lock mapping",
        },
        "continued_kernel_call_184": {
            "target": "0x800000B8",
            "ordinal": 184,
            "name": "NtAllocateVirtualMemory",
            "arg_bytes": 20,
            "frame_bytes": 24,
            "supported_modes": [
                "MEM_RESERVE with explicit reserved/uncommitted guest-page state",
                "MEM_RESERVE|MEM_COMMIT with page-rounded page-backed guest allocation",
                "MEM_COMMIT into a previously reserved guest range",
                "MEM_COMMIT inside an existing valid guest range",
            ],
            "page_allocator": "top of 64 MiB guest RAM downward; ordinary Phase-4C heap remains below",
            "production_semantics": "guest pointer/size writeback, persistent reservation state, commit zero-fill, protection metadata, NTSTATUS result",
        },
        "continued_support_helper_memmove": {
            "name": "recomp_crt_memmove",
            "retail_entry": "0x00238C00",
            "calling_convention": "cdecl",
            "arg_bytes": 12,
            "callee_cleanup_bytes": 4,
            "semantics": "overlap-safe guest memmove; EAX=destination; preserve caller registers",
            "oracle": "tools/recomp/test_crt_memmove_native.py",
        },
        "continued_kernel_call_149": {
            "target": "0x80000095",
            "ordinal": 149,
            "name": "KeSetTimer",
            "arg_bytes": 16,
            "frame_bytes": 20,
            "production_semantics": "guest KTIMER arming, absolute deadline, DPC pointer, prior-active return",
        },
        "continued_kernel_call_301": {
            "target": "0x8000012D",
            "ordinal": 301,
            "name": "RtlNtStatusToDosError",
            "arg_bytes": 4,
            "frame_bytes": 8,
            "production_semantics": "bridge_RtlNtStatusToDosError exact common-status mapping",
        },
        "continued_kernel_call_24": {
            "target": "0x80000018",
            "ordinal": 24,
            "name": "ExQueryNonVolatileSetting",
            "arg_bytes": 20,
            "frame_bytes": 24,
            "production_semantics": "guest EEPROM/XConfig defaults; stdcall tail return",
        },
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
        "diagnostic_goal": "capture_live_NtQueryInformationFile_ordinal_211_frame_and_class",
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
    (args.out_dir / "phase5m-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    if unknown:
        print("[Phase5M] NON-DIRECT unresolved helper dependencies remain:")
        for owner, names in unknown.items():
            print(f"[Phase5M]   {owner}: {', '.join(names)}")
        print(
            "[Phase5M] Direct sub_XXXXXXXX callees have already been converted "
            "to DIRECT_FRONTIER boundaries; entries listed above are true support "
            "dependencies and are not safe to guess."
        )
        print(
            "[Phase5M] EMIT RESULT: BLOCKED_BY_SUPPORT_DEPENDENCY"
        )
        return 3

    env_source = base.build_env_source(
        args.phase2e_source.read_text(encoding="utf-8")
    ).replace("PHASE 4C-B", "PHASE 5L")
    env_source = env_source.replace("[Merc360:P4C-ENV]", "[Merc360:P5-ENV]")
    for stale_phase in (
        "PHASE 4C-N",
        "PHASE 4C-O",
        "PHASE 4C-P",
        "PHASE 4C-R",
        "PHASE 4C-S",
        "PHASE 4C-T",
        "PHASE 4C-U",
        "PHASE 4C-V",
        "PHASE 4C-W",
        "PHASE 4C-X",
        "PHASE 4C-Y",
        "PHASE 4C-Z",
        "PHASE 4C-AA",
        "PHASE 4C-AB",
        "PHASE 4C-AC",
        "PHASE 4C-AD",
        "PHASE 4C-AE",
        "PHASE 4C-AF",
    ):
        env_source = env_source.replace(stale_phase, "PHASE 5L")
    env_source += """
extern "C" DWORD phase5m_env_build_cookie(void)
{
    return 0x50354D31u; /* P5M1 */
}
"""
    for stale_phase in (
        "PHASE 4C-N",
        "PHASE 4C-O",
        "PHASE 4C-R",
        "PHASE 4C-S",
        "PHASE 4C-T",
        "PHASE 4C-U",
        "PHASE 4C-V",
        "PHASE 4C-W",
        "PHASE 4C-X",
        "PHASE 4C-Y",
        "PHASE 4C-Z",
        "PHASE 4C-AA",
        "PHASE 4C-AB",
        "PHASE 4C-AC",
        "PHASE 4C-AD",
        "PHASE 4C-AE",
        "PHASE 4C-AF",
    ):
        env_source = env_source.replace(stale_phase, "PHASE 5L")

    driver = base.driver_source(root_name, root_va, len(member_vas))
    driver = driver.replace(
        "P4C-STARTUP-20261019-A",
        "P5M-NTQUERYINFO211-CAPTURE-20261020-A",
    )
    driver = driver.replace(
        "Policy: execute the real retail entry and stop at the first live dynamic/indirect boundary",
        "Policy: preserve Phase 5L state and capture live ordinal 211 NtQueryInformationFile",
    )
    driver = driver.replace("PHASE 4C-B", "PHASE 5L")
    cookie_decl = 'extern "C" DWORD phase4c_env_entry(void);\n'
    if cookie_decl not in driver:
        raise SystemExit("[Phase5M] env-entry declaration marker changed")
    driver = driver.replace(
        cookie_decl,
        cookie_decl + 'extern "C" DWORD phase5m_env_build_cookie(void);\n',
        1,
    )
    env_pass_marker = """    trace("PHASE 5L ENVIRONMENT RESULT: PASS");

    g_ram = phase4c_env_guest_base();"""
    if env_pass_marker not in driver:
        raise SystemExit("[Phase5M] environment PASS marker changed")
    driver = driver.replace(
        env_pass_marker,
        """    if (phase5m_env_build_cookie() != 0x50354D31u)
    {
        trace("FAIL: Phase 5M environment build cookie mismatch");
        goto shutdown_env;
    }
    trace("PASS: Phase 5M main/env build cookie matches");
    trace("PHASE 5L ENVIRONMENT RESULT: PASS");

    g_ram = phase4c_env_guest_base();""",
        1,
    )
    driver = driver.replace(
        "    s_accessFault = 0;\n",
        "    s_accessFault = 0;\n"
        "    s_phase4cFaultAddress = 0u;\n"
        "    s_phase4cFaultWidth = 0u;\n"
        "    s_phase4cFaultWrite = 0u;\n"
        "    s_phase4cFaultEscapeArmed = 0;\n"
        "    s_phase5bNtOpenFileHandledCount = 0u;\n"
        "    s_phase5bNtOpenFileObjectAttributes = 0u;\n"
        "    s_phase5bNtOpenFilePathVa = 0u;\n"
        "    s_phase5bNtOpenFilePathLength = 0u;\n"
        "    s_phase5bNtOpenFileLastToken = 0u;\n"
        "    s_phase5bNtOpenFileLastStatus = 0u;\n"
        "    s_phase5cVolumeQueryCount = 0u;\n"
        "    s_phase5cVolumeLastClass = 0u;\n"
        "    s_phase5cCloseCount = 0u;\n"
        "    s_phase5dSymbolicLinkCreateCount = 0u;\n"
        "    s_phase5dSymbolicLinkDeleteCount = 0u;\n"
        "    s_phase5hNtCreateFileCallCount = 0u;\n"
        "    s_phase5hNtCreateFileSuccessCount = 0u;\n"
        "    s_phase5hNtReadFileCallCount = 0u;\n"
        "    s_phase5hNtReadFileSuccessCount = 0u;\n"
        "    s_phase5iRtlInitAnsiStringCount = 0u;\n"
        "    s_phase5iRtlInitAnsiStringLastLength = 0u;\n"
        "    s_phase5iRtlInitAnsiStringLastDestination = 0u;\n"
        "    s_phase5iRtlInitAnsiStringLastSource = 0u;\n"
        "    s_phase5kRtlEqualStringCount = 0u;\n"
        "    s_phase5kRtlEqualStringTrueCount = 0u;\n"
        "    s_phase5kRtlEqualStringLastString1 = 0u;\n"
        "    s_phase5kRtlEqualStringLastString2 = 0u;\n"
        "    s_phase5kRtlEqualStringLastCaseInsensitive = 0u;\n"
        "    s_phase5kRtlEqualStringLastResult = 0u;\n"
        "    s_phase5mXboxLastError = 0u;\n"
        "    s_phase5mSetLastErrorCount = 0u;\n"
        "    s_phase5mNtQueryInformationFileCaptureCount = 0u;\n"
        "    s_phase5mNtQueryInformationFileHandle = 0u;\n"
        "    s_phase5mNtQueryInformationFileIoStatus = 0u;\n"
        "    s_phase5mNtQueryInformationFileBuffer = 0u;\n"
        "    s_phase5mNtQueryInformationFileLength = 0u;\n"
        "    s_phase5mNtQueryInformationFileClass = 0u;\n"
        "    ZeroMemory(s_phase5dSymbolicLinks, sizeof(s_phase5dSymbolicLinks));\n"
        "    ZeroMemory(s_phase5bHandles, sizeof(s_phase5bHandles));\n",
        1,
    )
    driver = driver.replace(
        "    phase4c_reset_architecture();\n",
        "    phase4c_reset_architecture();\n\n"
        "    if (!phase4c_fix_startup_data_thunks())\n"
        "    {\n"
        "        trace(\"PHASE 5L STARTUP DATA-THUNK PREP RESULT: FAIL\");\n"
        "        goto shutdown_env;\n"
        "    }\n"
        "    trace(\"PHASE 5L STARTUP DATA-THUNK PREP RESULT: PASS\");\n"
        "    trace(\"PASS: hardware-observed direct target 0022C47B is packed for translated execution\");\n"
        "    if (!phase4c_init_kernel_header_page())\n"
        "    {\n"
        "        trace(\"PHASE 5L KERNEL HEADER PREP RESULT: FAIL\");\n"
        "        goto shutdown_env;\n"
        "    }\n"
        "    trace(\"PHASE 5L KERNEL HEADER PREP RESULT: PASS\");\n"
        "    trace(\"PASS: ordinal 47 HalRegisterShutdownNotification continuation armed\");\n"
        "    trace(\"PASS: hardware-observed direct target 0022F128 is packed for translated execution\");\n"
        "    trace(\"PASS: ordinal 107 KeInitializeDpc continuation armed\");\n"
        "    trace(\"PASS: ordinal 113 KeInitializeTimerEx continuation armed\");\n"
        "    trace(\"PASS: hardware-observed direct target 0022C5A4 is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed direct target 00230060 is packed for translated execution\");\n"
        "    trace(\"PASS: ordinal 24 ExQueryNonVolatileSetting tail continuation armed\");\n"
        "    trace(\"PASS: ordinal 301 RtlNtStatusToDosError continuation armed\");\n"
        "    trace(\"PASS: bounded direct closure rooted at 0022F0FB is packed for translated execution\");\n"
        "    trace(\"PASS: ordinal 149 KeSetTimer continuation armed\");\n"
        "    trace(\"PASS: bounded direct closure rooted at 0022D980 is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed direct root 00238C00 is packed for translated execution\");\n"
        "    trace(\"PASS: maintained recomp_crt_memmove cdecl support armed\");\n"
        "    trace(\"PASS: ordinal 184 NtAllocateVirtualMemory reserved/commit page-state continuation armed\");\n"
        "    trace(\"PASS: ordinal 291 RtlInitializeCriticalSection continuation armed\");\n"
        "    trace(\"PASS: hardware-observed direct root 0022D431 is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed direct root 0022CA2B is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed direct root 0022C8EA is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed direct root 0022CEEE is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed post-mount direct root 0022C1C0 is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed next retail direct root 002370B8 is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed next retail direct root 0022BE8C is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed post-storage direct root 0022F026 is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed root 0022B178 uses maintained manual SetLastError execution\");\n"
        "    trace(\"PASS: Phase 5M ordinal 202 NtOpenFile native continuation armed\");\n"
        "    trace(\"PASS: Phase 5M ordinal 218 NtQueryVolumeInformationFile native continuation armed\");\n"
        "    trace(\"PASS: Phase 5M ordinal 187 NtClose native continuation armed\");\n"
        "    trace(\"PASS: Phase 5M ordinal 67 IoCreateSymbolicLink native continuation armed\");\n"
        "    trace(\"PASS: Phase 5M ordinal 69 IoDeleteSymbolicLink native continuation armed\");\n"
        "    trace(\"PASS: Phase 5M ordinal 190 NtCreateFile native continuation armed\");\n"
        "    trace(\"PASS: Phase 5M ordinal 219 NtReadFile synchronous continuation armed\");\n"
        "    trace(\"PASS: Phase 5M ordinal 289 RtlInitAnsiString continuation armed\");\n"
        "    trace(\"PASS: Phase 5M ordinal 279 RtlEqualString continuation armed\");\n"
        "    trace(\"PASS: Phase 5M ordinal 211 NtQueryInformationFile capture armed\");\n",
        1,
    )
    driver = driver.replace(
        '    case PHASE4C_BOUNDARY_HEAP_EXHAUSTED: return "HEAP_EXHAUSTED";',
        '    case PHASE4C_BOUNDARY_HEAP_EXHAUSTED: return "HEAP_EXHAUSTED";\n'
        '    case PHASE4C_BOUNDARY_THREAD_TARGET: return "THREAD_TARGET";\n'
        '    case PHASE4C_BOUNDARY_KERNEL_FRAME: return "KERNEL_FRAME";\n'
        '    case PHASE4C_BOUNDARY_THREAD_RETURN: return "THREAD_RETURN";\n'
        '    case PHASE4C_BOUNDARY_CALLBACK_RETURN: return "CALLBACK_RETURN";\n'
        '    case PHASE4C_BOUNDARY_DIRECT_FRONTIER: return "DIRECT_FRONTIER";\n'
        '    case PHASE4C_BOUNDARY_TIMER_DUE: return "TIMER_DUE";\n'
        '    case PHASE4C_BOUNDARY_STORAGE_OPEN: return "STORAGE_OPEN";\n'
        '    case PHASE4C_BOUNDARY_STORAGE_QUERY: return "STORAGE_QUERY";\n'
        '    case PHASE4C_BOUNDARY_STORAGE_IO: return "STORAGE_IO";\n'
        '    case PHASE4C_BOUNDARY_FILE_INFORMATION: return "FILE_INFORMATION";',
    )

    old_return_pass = f"""        boundedPass =
            !s_accessFault &&
            s_traceCount > 0u &&
            s_trace[0] == 0x{root_va:08X}u;"""
    if old_return_pass not in driver:
        raise SystemExit("[Phase5M] entry-return PASS marker changed")
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
            s_phase4cNvQueryHandled &&
            s_phase4cNtStatusMapped &&
            s_phase4cTimerArmed &&
            s_phase4cVmAllocCount > 0u &&
            s_phase4cCriticalSectionInitCount > 0u &&
            s_phase5bNtOpenFileHandledCount > 0u &&
            s_phase5cVolumeQueryCount > 0u &&
            s_phase5dSymbolicLinkCreateCount > 0u &&
            s_phase5hNtCreateFileCallCount > 0u &&
            s_phase5iRtlInitAnsiStringCount > 0u &&
            s_phase5kRtlEqualStringCount > 0u &&
            s_phase5mSetLastErrorCount > 0u &&
            s_phase5mNtQueryInformationFileCaptureCount > 0u &&
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
                         s_phase4cBoundaryTarget != 0x80000071u &&
                         s_phase4cBoundaryTarget != 0x80000018u &&
                         s_phase4cBoundaryTarget != 0x8000012Du &&
                         s_phase4cBoundaryTarget != 0x80000095u &&
                         s_phase4cBoundaryTarget != 0x800000B8u &&
                         s_phase4cBoundaryTarget != 0x80000123u &&
                         s_phase4cBoundaryTarget != 0x800000CAu &&
                         s_phase4cBoundaryTarget != 0x800000DAu &&
                         s_phase4cBoundaryTarget != 0x800000BBu &&
                         s_phase4cBoundaryTarget != 0x80000043u &&
                         s_phase4cBoundaryTarget != 0x80000045u &&
                         s_phase4cBoundaryTarget != 0x800000BEu &&
                         s_phase4cBoundaryTarget != 0x800000DBu &&
                         s_phase4cBoundaryTarget != 0x80000121u &&
                         s_phase4cBoundaryTarget != 0x80000117u &&
                         s_phase4cBoundaryTarget != 0x800000D3u) ||
                        (s_phase4cBoundaryKind == PHASE4C_BOUNDARY_DIRECT_FRONTIER &&
                         s_phase4cBoundaryTarget != 0x0022C47Bu &&
                         s_phase4cBoundaryTarget != 0x0022F128u &&
                         s_phase4cBoundaryTarget != 0x0022C5A4u &&
                         s_phase4cBoundaryTarget != 0x00230060u &&
                         s_phase4cBoundaryTarget != 0x0022F0FBu &&
                         s_phase4cBoundaryTarget != 0x0022D980u &&
                         s_phase4cBoundaryTarget != 0x00238C00u &&
                         s_phase4cBoundaryTarget != 0x0022D431u &&
                         s_phase4cBoundaryTarget != 0x0022CA2Bu &&
                         s_phase4cBoundaryTarget != 0x0022C8EAu &&
                         s_phase4cBoundaryTarget != 0x0022CEEEu &&
                         s_phase4cBoundaryTarget != 0x0022C1C0u &&
                         s_phase4cBoundaryTarget != 0x002370B8u &&
                         s_phase4cBoundaryTarget != 0x0022BE8Cu &&
                         s_phase4cBoundaryTarget != 0x0022F026u &&
                         s_phase4cBoundaryTarget != 0x0022B178u) ||
                        (s_phase4cBoundaryKind == PHASE4C_BOUNDARY_TIMER_DUE &&
                         s_phase4cBoundaryTarget != 0u) ||
                        (s_phase4cBoundaryKind == PHASE4C_BOUNDARY_FILE_INFORMATION &&
                         s_phase4cBoundaryTarget == 0x800000D3u)
                    )
                )
            );"""
    if old_escape_pass not in driver:
        raise SystemExit("[Phase5M] boundary PASS marker changed")
    driver = driver.replace(old_escape_pass, new_escape_pass)

    result_marker = "PHASE 5L BOUNDED REAL STARTUP RESULT"
    if result_marker not in driver:
        raise SystemExit("[Phase5M] generated result label marker changed")
    driver = driver.replace(
        result_marker,
        "PHASE 5L DIRECTB178 RESULT",
        1,
    )
    arm_marker = f"""    if (escaped == 0)
    {{
        {root_name}();"""
    if arm_marker not in driver:
        raise SystemExit("[Phase5M] setjmp execution-arm marker changed")
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
        raise SystemExit("[Phase5M] setjmp escape marker changed")
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
        + "\n\n/* Phase 5M: native symbolic-link mount continuation + next live subsystem frontier */\n"
        + "\n".join(forward_decls)
        + "\n\n"
        + pack_lookup_source(member_vas, generated)
        + "\n#pragma optimize(\"\", off)\n"
        + "\n\n".join(bodies)
        + "\n#pragma optimize(\"\", on)\n"
        + driver
    )

    b178_definition = "static void sub_0022B178(void)"
    phase5m_state_decl = "static uint32_t s_phase5mXboxLastError;"
    phase5m_count_decl = "static uint32_t s_phase5mSetLastErrorCount;"
    if generated_main.count(b178_definition) != 1:
        raise SystemExit(
            "[Phase5M] generated main must contain exactly one support-owned "
            "sub_0022B178 definition"
        )
    if generated_main.count(phase5m_state_decl) != 1 or generated_main.count(phase5m_count_decl) != 1:
        raise SystemExit(
            "[Phase5M] generated main must contain exactly one declaration "
            "for each Phase 5M SetLastError state variable"
        )
    b178_index = generated_main.index(b178_definition)
    if generated_main.index(phase5m_state_decl) > b178_index or generated_main.index(phase5m_count_decl) > b178_index:
        raise SystemExit(
            "[Phase5M] SetLastError state declarations must precede the "
            "support-owned B178 body"
        )
    if "s_phase4cLastError = GUEST_READ32(g_esp + 4u);" not in generated_main:
        raise SystemExit(
            "[Phase5M] generated main lost shared SetLastError runtime state"
        )
    if "PASS: Phase 5M maintained SetLastError value=" not in generated_main:
        raise SystemExit(
            "[Phase5M] generated main lost maintained SetLastError instrumentation"
        )
    if "NtQueryInformationFile CAPTURE FRAME:" not in generated_main:
        raise SystemExit(
            "[Phase5M] generated main lost ordinal-211 capture instrumentation"
        )
    if "PHASE4C_BOUNDARY_FILE_INFORMATION" not in generated_main:
        raise SystemExit(
            "[Phase5M] generated main lost FILE_INFORMATION boundary"
        )

    (args.out_dir / "main.cpp").write_text(generated_main, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_source, encoding="utf-8")

    print("[Phase5M] NTQUERYINFO211 CAPTURE PACKAGE READY")
    print(
        f"[Phase5M] Entry closure={len(entry_members)} bodies; "
        f"thread closure={len(thread_members)} bodies; "
        f"union={len(member_vas)} bodies"
    )
    print(
        f"[Phase5M] Callback depth-{CALLBACK_DIRECT_DEPTH} slice: "
        f"{len(callback_members)} bodies; "
        f"new beyond proven entry/thread pack="
        f"{len(callback_members - entry_members - thread_members)}"
    )
    print(
        f"[Phase5M] Static direct frontier targets: "
        f"{len(direct_frontier_targets)}"
    )
    print(
        "[Phase5M] Previously promoted hardware direct target: 0x0022C47B"
    )
    print(
        "[Phase5M] Newly promoted hardware direct target: 0x0022F128 "
        "(only this new frontier member is added)"
    )
    print(
        "[Phase5M] Continued hardware kernel target: "
        "0x8000002F ordinal 47 HalRegisterShutdownNotification"
    )
    print(
        "[Phase5M] Continued hardware kernel target: "
        "0x8000006B ordinal 107 KeInitializeDpc"
    )
    print(
        "[Phase5M] Continued hardware kernel target: "
        "0x80000071 ordinal 113 KeInitializeTimerEx"
    )
    print(
        "[Phase5M] Newly continued hardware kernel tail target: "
        "0x80000018 ordinal 24 ExQueryNonVolatileSetting"
    )
    print(
        "[Phase5M] Newly continued hardware kernel target: "
        "0x8000012D ordinal 301 RtlNtStatusToDosError"
    )
    print(
        f"[Phase5M] Previous promoted direct closure root: 0x{LIVE_DIRECT_FRONTIER_TARGET_5:08X}; "
        f"members={len(previous_promoted_closure_members)}"
    )
    print(
        f"[Phase5M] Prior safe-root target: 0x{LIVE_DIRECT_FRONTIER_TARGET_6:08X}; "
        f"members={len(prior_safe_root_members)}"
    )
    print(
        f"[Phase5M] New maintained-manual hardware root: 0x{LIVE_DIRECT_FRONTIER_TARGET_16:08X}; "
        f"depth={PROMOTED_CLOSURE_DEPTH}; members={len(promoted_closure_members)}"
    )
    print(
        "[Phase5M] New post-storage root members: "
        + ", ".join(f"0x{va:08X}" for va in sorted(promoted_closure_members))
    )
    print(
        "[Phase5M] Newly continued hardware kernel target: "
        "0x80000095 ordinal 149 KeSetTimer"
    )
    print(
        "[Phase5M] Newly promoted hardware direct target: "
        "0x0022C5A4 (previously promoted)"
    )
    print(
        "[Phase5M] Newly promoted hardware direct target: "
        "0x00230060 (only this new frontier member is added)"
    )
    print(
        "[Phase5M] Hardware-observed handoff: "
        "StartRoutine=0x0022B43F ctx1=0x002295D6 ctx2=0x00000000"
    )
    print(f"[Phase5M] main: {args.out_dir / 'main.cpp'}")
    print(f"[Phase5M] env:  {args.out_dir / 'phase5_env.cpp'}")
    print(
        "[Phase5M] Runtime policy: preserve the proven startup path, keep "
        "the complete hardware-proven title-storage/XBE-section-scan path live, preserve reviewed SetLastError execution, capture ordinal 211 NtQueryInformationFile, and stop before fabricating a file-information payload."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

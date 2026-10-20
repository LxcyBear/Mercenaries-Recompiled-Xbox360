r"""Phase 5BB: advance beyond the persistent-cache second-boot frontier.

Phase 5AP passed as a two-launch hardware proof. On pass 2, the 512 KiB
Partition0 backing reloaded, the sector 0x800 write was identical (changed=0),
retail skipped the first-boot cache IOCTL/reboot branch, opened Partition5 with
a trailing slash, queried volume information, created \\??\\Z:, and reached
a new fault-free direct frontier 0x0022F0D6 from caller 0x0022BD2D.

P5BB preserves the complete 5BA path, including the hardware-proven packed
guest ICALL 0x0022C452 -> 0x0023D550. Phase 5BA executed that target and
continued through translated code 0x00238533 -> 0x00238507 -> 0x002384E0 ->
0x0022B5EF before reaching a new fault-free direct frontier at 0x0022DDA4.
P5BB validates that exact target against the refreshed Phase-3N inventory,
promotes a bounded depth-2/cap-16 translated closure, requires actual root
entry, and excludes the old 0x0022DDA4 frontier from PASS.
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
LIVE_DIRECT_FRONTIER_TARGET_17 = 0x00239B78
LIVE_DIRECT_FRONTIER_TARGET_18 = 0x0023DDDD
LIVE_DIRECT_FRONTIER_TARGET_19 = 0x0023DD7B
LIVE_DIRECT_FRONTIER_TARGET_20 = 0x0023DDA0
LIVE_DIRECT_FRONTIER_TARGET_21 = 0x0023DD56
LIVE_DIRECT_FRONTIER_TARGET_22 = 0x0023F8CB
LIVE_DIRECT_FRONTIER_TARGET_23 = 0x0022BDA5
LIVE_DIRECT_FRONTIER_TARGET_24 = 0x0022F08D
LIVE_DIRECT_FRONTIER_TARGET_25 = 0x0022F0CC
LIVE_DIRECT_FRONTIER_TARGET_26 = 0x0022F0AE
LIVE_DIRECT_FRONTIER_TARGET_27 = 0x0022A604
LIVE_DIRECT_FRONTIER_TARGET_28 = 0x0022A3B9
LIVE_DIRECT_FRONTIER_TARGET_29 = 0x0022C5C6
LIVE_DIRECT_FRONTIER_TARGET_30 = 0x0022F0D6
LIVE_DIRECT_FRONTIER_TARGET_31 = 0x0022BBC8
LIVE_DIRECT_FRONTIER_TARGET_32 = 0x0023E600
LIVE_INDIRECT_FRONTIER_TARGET_33 = 0x0023D550
LIVE_DIRECT_FRONTIER_TARGET_34 = 0x0022DDA4
P5BB_DIRECT34_CLOSURE_DEPTH = 2
P5BB_DIRECT34_CLOSURE_CAP = 16
P5BB_ICALL_FRONTIER_CLOSURE_DEPTH = 2
P5BB_ICALL_FRONTIER_CLOSURE_CAP = 16
P5BB_LIVE_FRONTIER_CLOSURE_DEPTH = 2
P5BB_LIVE_FRONTIER_CLOSURE_CAP = 16
P5BB_FRONTIER_CLOSURE_DEPTH = 2
P5BB_FRONTIER_CLOSURE_CAP = 16
P5BB_NEXT_FRONTIER_CLOSURE_DEPTH = 2
P5BB_NEXT_FRONTIER_CLOSURE_CAP = 16
P5AN_FRONTIER_CLOSURE_DEPTH = 2
P5AN_FRONTIER_CLOSURE_CAP = 16
PROMOTED_CLOSURE_DEPTH = 0
PROMOTED_CLOSURE_CAP = 1
KERNEL_HEADER_BASE = 0x80010000
KERNEL_HEADER_SIZE = 0x1000
KERNEL_HEADER_ELFANEW = 0x80


def load_base(path: Path):
    spec = importlib.util.spec_from_file_location("phase4c_b_emitter", path)
    if spec is None or spec.loader is None:
        raise SystemExit("[Phase5BB] could not load Phase 4C-B emitter")
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
        raise SystemExit("[Phase5BB] s_accessFault declaration marker changed")
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
        raise SystemExit("[Phase5BB] guest accessor insertion marker changed")
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
                "[Phase5BB] exact guest accessor body marker changed"
            )
        support = support.replace(old, new, 1)

    # Only the assignment inside phase4c_note_access_fault may remain.
    if support.count("s_accessFault = 1;") != 1:
        raise SystemExit(
            "[Phase5BB] residual direct fault assignments remain"
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
        raise SystemExit("[Phase5BB] guest RAM declaration marker changed")
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
     * separate from title RAM; Phase 5BB supplies a minimal synthetic PE
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
        raise SystemExit("[Phase5BB] guest_ptr body marker changed")
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
                f"[Phase5BB] callback dependency 0x{va:08X} "
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
                f"[Phase5BB] promoted dependency 0x{va:08X} "
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

    # Phase 5BB state is consumed by the support-owned B178 body below. Declare
    # it before the donor body so the XDK compiler sees the symbols before
    # their first use.
    text = (
        "static uint32_t s_phase5ahXboxLastError;\n"
        "static uint32_t s_phase5ahSetLastErrorCount;\n"
        "static uint32_t s_phase5ahNtQueryInformationFileCallCount;\n"
        "static uint32_t s_phase5ahNtQueryInformationFileSuccessCount;\n"
        "static uint32_t s_phase5ahNtQueryInformationFileLastClass;\n"
        "static uint32_t s_phase5bbNtOpenSymbolicLinkCallCount;\n"
        "static uint32_t s_phase5bbNtOpenSymbolicLinkSuccessCount;\n"
        "static uint32_t s_phase5bbNtOpenSymbolicLinkDDriveSuccessCount;\n"
        "static uint32_t s_phase5bbNtOpenSymbolicLinkLastToken;\n"
        "static uint32_t s_phase5bbNtQuerySymbolicLinkCallCount;\n"
        "static uint32_t s_phase5bbNtQuerySymbolicLinkSuccessCount;\n"
        "static uint32_t s_phase5bbNtQuerySymbolicLinkLastLength;\n"
        "static uint32_t s_phase5bbNtQuerySymbolicLinkSavedEspRepairCount;\n"
        "static uint32_t s_phase5bbNtQuerySymbolicLinkSavedEspRepairExtra;\n"
        "static uint32_t s_phase5bbSymbolicLinkCloseCount;\n"
        "static int s_phase5bbRoot22DDA4Entered;\n"
        "static uint32_t s_phase5bbManualHeapAllocCount;\n"
        "static uint32_t s_phase5bbManualHeapFreeCount;\n"
        "static uint32_t s_phase5bbManualHeapReallocCount;\n"
        "static uint32_t s_phase5bbManualHeapLastHeap;\n"
        "static uint32_t s_phase5bbManualHeapLastFlags;\n"
        "static uint32_t s_phase5bbManualHeapLastSize;\n"
        "static uint32_t s_phase5bbManualHeapLastResult;\n"
        "static void phase5bb_nt_open_symbolic_link_object(uint32_t savedEsp);\n"
        "static void phase5bb_nt_query_symbolic_link_object(uint32_t savedEsp);\n\n"
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
    s_phase5ahXboxLastError = s_phase4cLastError;
    ++s_phase5ahSetLastErrorCount;

    sprintf(
        line,
        "PASS: Phase 5BB maintained SetLastError value=%08X calls=%u new_esp=%08X",
        (unsigned int)s_phase4cLastError,
        (unsigned int)s_phase5ahSetLastErrorCount,
        (unsigned int)(g_esp + 8u));
    trace(line);

    g_esp += 8u;
}"""
    if old_b178 not in text:
        raise SystemExit("[Phase5BB] maintained support-owned B178 body marker changed")
    text = text.replace(old_b178, new_b178, 1)

    # DDA4/E51F are already support-owned manual Xbox CRT heap helpers in the
    # Phase-4C donor. Phase 5BA hardware reached DDA4 directly. Instrument
    # those canonical bodies and add the adjacent production-manual realloc
    # sibling E713 over the same deterministic title-heap block table.
    old_manual_heap = """static void sub_0022DDA4(void)
{
    uint32_t flags = GUEST_READ32(g_esp + 8u);
    uint32_t size = GUEST_READ32(g_esp + 12u);

    g_eax = phase4c_heap_allocate(flags, size);
    g_esp += 16u;
}

static void sub_0022E51F(void)
{
    uint32_t allocation = GUEST_READ32(g_esp + 12u);

    g_eax = phase4c_heap_free(allocation);
    g_esp += 16u;
}"""

    new_manual_heap = """static uint32_t phase5bb_heap_reallocate(
    uint32_t flags,
    uint32_t address,
    uint32_t requested)
{
    uint32_t capacity;
    uint32_t index;

    if (address == 0u)
        return phase4c_heap_allocate(flags, requested);

    phase4c_heap_init();
    capacity = phase4c_heap_align(requested);
    if (capacity == 0u)
        return 0u;

    for (index = 0u; index < s_phase4cHeapCount; ++index)
    {
        Phase4CHeapBlock* block = &s_phase4cHeap[index];
        uint32_t oldRequested;

        if (!block->inUse || block->address != address)
            continue;

        oldRequested = block->requested;

        if (capacity <= block->capacity)
        {
            if ((flags & PHASE4C_HEAP_ZERO_MEMORY) != 0u &&
                requested > oldRequested)
            {
                memset(
                    g_ram + address + oldRequested,
                    0,
                    requested - oldRequested);
            }
            block->requested = requested;
            return address;
        }

        if (index + 1u < s_phase4cHeapCount)
        {
            Phase4CHeapBlock* next = &s_phase4cHeap[index + 1u];
            if (!next->inUse &&
                block->address + block->capacity == next->address &&
                block->capacity + next->capacity >= capacity)
            {
                uint32_t needed = capacity - block->capacity;

                if (next->capacity == needed)
                {
                    block->capacity = capacity;
                    phase4c_heap_remove(index + 1u);
                }
                else
                {
                    block->capacity = capacity;
                    next = &s_phase4cHeap[index + 1u];
                    next->address += needed;
                    next->capacity -= needed;
                }

                block = &s_phase4cHeap[index];
                if ((flags & PHASE4C_HEAP_ZERO_MEMORY) != 0u &&
                    requested > oldRequested)
                {
                    memset(
                        g_ram + address + oldRequested,
                        0,
                        requested - oldRequested);
                }
                block->requested = requested;
                return address;
            }
        }

        if ((flags & 0x00000010u) == 0u)
        {
            uint32_t replacement = phase4c_heap_allocate(flags, requested);
            uint32_t copyBytes =
                oldRequested < requested ? oldRequested : requested;

            if (replacement != 0u)
            {
                if (copyBytes != 0u)
                    memmove(g_ram + replacement, g_ram + address, copyBytes);
                phase4c_heap_free(address);
            }
            return replacement;
        }

        return 0u;
    }

    return 0u;
}

static void sub_0022DDA4(void)
{
    uint32_t returnSlot = GUEST_READ32(g_esp + 0u);
    uint32_t heap = GUEST_READ32(g_esp + 4u);
    uint32_t flags = GUEST_READ32(g_esp + 8u);
    uint32_t size = GUEST_READ32(g_esp + 12u);
    uint32_t result;
    char line[448];

    RECOMP_TRACE_FUNC(0x0022DDA4u);
    s_phase5bbRoot22DDA4Entered = 1;

    if (s_accessFault)
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x0022DDA4u,
            g_esp);

    result = phase4c_heap_allocate(flags, size);
    ++s_phase5bbManualHeapAllocCount;
    s_phase5bbManualHeapLastHeap = heap;
    s_phase5bbManualHeapLastFlags = flags;
    s_phase5bbManualHeapLastSize = size;
    s_phase5bbManualHeapLastResult = result;

    sprintf(
        line,
        "PASS: Phase 5BB maintained RtlAllocateHeap ret=%08X heap=%08X flags=%08X size=%u result=%08X calls=%u new_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)heap,
        (unsigned int)flags,
        (unsigned int)size,
        (unsigned int)result,
        (unsigned int)s_phase5bbManualHeapAllocCount,
        (unsigned int)(g_esp + 16u));
    trace(line);

    g_eax = result;
    g_esp += 16u;
}

static void sub_0022E51F(void)
{
    uint32_t returnSlot = GUEST_READ32(g_esp + 0u);
    uint32_t heap = GUEST_READ32(g_esp + 4u);
    uint32_t flags = GUEST_READ32(g_esp + 8u);
    uint32_t allocation = GUEST_READ32(g_esp + 12u);
    uint32_t result;
    char line[448];

    RECOMP_TRACE_FUNC(0x0022E51Fu);

    if (s_accessFault)
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x0022E51Fu,
            g_esp);

    result = phase4c_heap_free(allocation);
    ++s_phase5bbManualHeapFreeCount;
    s_phase5bbManualHeapLastHeap = heap;
    s_phase5bbManualHeapLastFlags = flags;
    s_phase5bbManualHeapLastSize = 0u;
    s_phase5bbManualHeapLastResult = result;

    sprintf(
        line,
        "PASS: Phase 5BB maintained RtlFreeHeap ret=%08X heap=%08X flags=%08X allocation=%08X result=%u calls=%u new_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)heap,
        (unsigned int)flags,
        (unsigned int)allocation,
        (unsigned int)result,
        (unsigned int)s_phase5bbManualHeapFreeCount,
        (unsigned int)(g_esp + 16u));
    trace(line);

    g_eax = result;
    g_esp += 16u;
}

static void sub_0022E713(void)
{
    uint32_t returnSlot = GUEST_READ32(g_esp + 0u);
    uint32_t heap = GUEST_READ32(g_esp + 4u);
    uint32_t flags = GUEST_READ32(g_esp + 8u);
    uint32_t allocation = GUEST_READ32(g_esp + 12u);
    uint32_t size = GUEST_READ32(g_esp + 16u);
    uint32_t result;
    char line[480];

    RECOMP_TRACE_FUNC(0x0022E713u);

    if (s_accessFault)
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x0022E713u,
            g_esp);

    result = phase5bb_heap_reallocate(flags, allocation, size);
    ++s_phase5bbManualHeapReallocCount;
    s_phase5bbManualHeapLastHeap = heap;
    s_phase5bbManualHeapLastFlags = flags;
    s_phase5bbManualHeapLastSize = size;
    s_phase5bbManualHeapLastResult = result;

    sprintf(
        line,
        "PASS: Phase 5BB maintained RtlReAllocateHeap ret=%08X heap=%08X flags=%08X allocation=%08X size=%u result=%08X calls=%u new_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)heap,
        (unsigned int)flags,
        (unsigned int)allocation,
        (unsigned int)size,
        (unsigned int)result,
        (unsigned int)s_phase5bbManualHeapReallocCount,
        (unsigned int)(g_esp + 20u));
    trace(line);

    g_eax = result;
    g_esp += 20u;
}"""

    if old_manual_heap not in text:
        raise SystemExit("[Phase5BB] maintained manual heap donor bodies changed")
    text = text.replace(old_manual_heap, new_manual_heap, 1)

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
        raise SystemExit("[Phase5BB] boundary enum marker changed")
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
    } else if (_phase4c_target == 0x8000012Du) { \
        phase4c_rtl_nt_status_to_dos_error((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000095u && s_phase4cTimerInitialized) { \
        phase4c_ke_set_timer((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000031u) { \
        phase5bb_hal_return_to_firmware_trap((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000A5u) { \
        phase5bb_mm_allocate_contiguous((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000A6u) { \
        phase5bb_mm_allocate_contiguous_ex((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000A7u) { \
        phase5bb_mm_allocate_system((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000ABu) { \
        phase5bb_mm_free_contiguous((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000ACu) { \
        phase5bb_mm_free_system((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000ADu) { \
        phase5bb_mm_get_physical_address((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000AFu) { \
        phase5bb_mm_lock_unlock_buffer_pages((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000B0u) { \
        phase5bb_mm_lock_unlock_physical_page((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000B1u) { \
        phase5bb_mm_map_io_space((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000B2u) { \
        phase5bb_mm_persist_contiguous((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000B3u) { \
        phase5bb_mm_query_address_protect((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000B4u) { \
        phase5bb_mm_query_allocation_size((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000B5u) { \
        phase5bb_mm_query_statistics((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000B6u) { \
        phase5bb_mm_set_address_protect((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000B7u) { \
        phase5bb_mm_unmap_io_space((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000B8u) { \
        phase4c_nt_allocate_virtual_memory((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000C7u) { \
        phase5bb_nt_free_virtual_memory((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000123u) { \
        phase4c_initialize_critical_section((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000C4u) { \
        phase5bb_nt_device_io_control_file((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000CAu) { \
        phase5b_nt_open_file((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000CBu) { \
        phase5bb_nt_open_symbolic_link_object((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000D7u) { \
        phase5bb_nt_query_symbolic_link_object((uint32_t)(saved_esp)); \
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
    } else if (_phase4c_target == 0x800000ECu) { \
        phase5ah_nt_write_file((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000121u) { \
        phase5i_rtl_init_ansi_string((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000117u) { \
        phase5k_rtl_equal_string((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x800000D3u) { \
        phase5ah_nt_query_information_file((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000147u) { \
        phase5ah_xe_load_section((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x80000148u) { \
        phase5ah_xe_unload_section((uint32_t)(saved_esp)); \
    } else if (_phase4c_target == 0x0023D550u) { \
        recomp_func_t _phase5bb_icall_fn = phase4c_lookup_pack_func(_phase4c_target); \
        if (!_phase5bb_icall_fn) { \
            trace("FAIL: Phase 5BB packed ICALL target 0023D550 missing from translated pack"); \
            phase4c_escape( \
                PHASE4C_BOUNDARY_ICALL_SAFE, \
                _phase4c_target, \
                (DWORD)(saved_esp)); \
        } \
        ++s_phase5bbPackedIcall23D550Count; \
        s_phase5bbPackedIcall23D550LastSavedEsp = (uint32_t)(saved_esp); \
        trace("PASS: Phase 5BB ICALL_SAFE 0022C452 -> 0023D550 entering packed translated target"); \
        _phase5bb_icall_fn(); \
    } else { \
        phase4c_escape( \
            PHASE4C_BOUNDARY_ICALL_SAFE, \
            _phase4c_target, \
            (DWORD)(saved_esp)); \
    } \
} while (0)'''

    if old_macro not in text:
        raise SystemExit("[Phase5BB] RECOMP_ICALL_SAFE marker changed")
    text = text.replace(old_macro, new_macro)

    old_itail = r'''#define RECOMP_ITAIL(xbox_va) do { \
    phase4c_escape( \
        PHASE4C_BOUNDARY_ITAIL, \
        (DWORD)(xbox_va), \
        g_esp); \
} while (0)'''
    new_itail = r'''#define RECOMP_ITAIL(xbox_va) do { \
    uint32_t _phase4c_tail_target = (uint32_t)(xbox_va); \
    if (_phase4c_tail_target == 0x80000018u) { \
        phase4c_ex_query_nonvolatile_setting(); \
    } else { \
        phase4c_escape( \
            PHASE4C_BOUNDARY_ITAIL, \
            _phase4c_tail_target, \
            g_esp); \
    } \
} while (0)'''
    if old_itail not in text:
        raise SystemExit("[Phase5BB] RECOMP_ITAIL marker changed")
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
static uint32_t s_phase5bbNvQueryCount;
static uint32_t s_phase4cNvQueryIndex;
static uint32_t s_phase4cNvQueryValueVa;
static uint32_t s_phase4cNvQueryValueLength;
static int s_phase4cNtStatusMapped;
static uint32_t s_phase4cNtStatusInput;
static uint32_t s_phase4cNtStatusDosError;
static uint32_t s_phase5ahNtStatusMapCount;
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
static uint32_t s_phase5ahPartition0OpenSuccessCount;
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
static uint32_t s_phase5bbNtCreateFileObDosDevicesCount;
static uint32_t s_phase5bbNtCreateFileObDosDevicesMappedCount;
static uint32_t s_phase5bbNtCreateFileObDosDevicesSuccessCount;
static uint32_t s_phase5bbNtOpenFileObDosDevicesCount;
static uint32_t s_phase5bbNtOpenFileObDosDevicesMappedCount;
static uint32_t s_phase5hNtReadFileCallCount;
static uint32_t s_phase5hNtReadFileSuccessCount;
static uint32_t s_phase5ahNtWriteFileCallCount;
static uint32_t s_phase5ahNtWriteFileSuccessCount;
static uint32_t s_phase5ahNtWriteFileLastBytes;
static uint32_t s_phase5ahNtWriteFileLastStatus;
static uint32_t s_phase5ahNtWriteFileSavedEspRepairCount;
static uint32_t s_phase5ahNtWriteFileSavedEspRepairSuccessCount;
static uint32_t s_phase5ahNtWriteFileSavedEspRepairLastBytes;
static uint32_t s_phase5ahNtWriteFileSavedEspRepairLastResumeEsp;
static uint32_t s_phase5ahNtWriteFileSavedEspRepairLastImageIndex;
static uint32_t s_phase5ahNtWriteFileXsImageSuccessCount;
static int s_phase5ahRoot22BDA5Entered;
static int s_phase5ahRoot22F08DEntered;
static int s_phase5ahRoot22F0CCEntered;
static int s_phase5ahRoot22F0AEEntered;
static int s_phase5ahRoot22A604Entered;
static int s_phase5ahRoot22A3B9Entered;
static int s_phase5bbRoot22C5C6Entered;
static int s_phase5bbRoot22F0D6Entered;
static int s_phase5bbRoot22BBC8Entered;
static int s_phase5bbRoot23E600Entered;
static int s_phase5bbRoot23D550Entered;
static uint32_t s_phase5bbPackedIcall23D550Count;
static uint32_t s_phase5bbPackedIcall23D550LastSavedEsp;
static uint32_t s_phase5ahXeLoadSectionCallCount;
static uint32_t s_phase5ahXeLoadSectionSuccessCount;
static uint32_t s_phase5ahXeLoadSectionLastSectionVa;
static uint32_t s_phase5ahXeLoadSectionLastIndex;
static uint32_t s_phase5ahXeLoadSectionLastRefCount;
static uint32_t s_phase5ahXeUnloadSectionCallCount;
static uint32_t s_phase5ahXeUnloadSectionSuccessCount;
static uint32_t s_phase5ahXeUnloadSectionLastSectionVa;
static uint32_t s_phase5ahXeUnloadSectionLastIndex;
static uint32_t s_phase5ahXeUnloadSectionLastRefCount;
static uint32_t s_phase5iRtlInitAnsiStringCount;
static uint32_t s_phase5iRtlInitAnsiStringLastLength;
static uint32_t s_phase5iRtlInitAnsiStringLastDestination;
static uint32_t s_phase5iRtlInitAnsiStringLastSource;
static uint32_t s_phase5bbRtlInitAnsiSavedEspRepairCount;
static uint32_t s_phase5bbRtlInitAnsiSavedEspRepairExtra;
static uint32_t s_phase5bbRtlInitAnsiSavedEspRepairLastResumeEsp;
static uint32_t s_phase5kRtlEqualStringCount;
static uint32_t s_phase5kRtlEqualStringTrueCount;
static uint32_t s_phase5kRtlEqualStringLastString1;
static uint32_t s_phase5kRtlEqualStringLastString2;
static uint32_t s_phase5kRtlEqualStringLastCaseInsensitive;
static uint32_t s_phase5kRtlEqualStringLastResult;
static uint32_t s_phase5bbMmCallCount;
static uint32_t s_phase5bbMmAllocSuccessCount;
static uint32_t s_phase5bbMmFreeCount;
static uint32_t s_phase5bbMmLastOrdinal;
static uint32_t s_phase5bbMmLastBase;
static uint32_t s_phase5bbMmLastSize;
static uint32_t s_phase5bbMmPersistCount;
static uint32_t s_phase5bbMmIoMapCount;
static uint32_t s_phase5bbMmIoUnmapCount;
static uint32_t s_phase5bbNtFreeVirtualCount;
static uint32_t s_phase5bbNtFreeVirtualSuccessCount;
#define PHASE5AQ_PARTITION0_CONFIG_SIZE 0x00080000u
static BYTE s_phase5bbPartition0Config[PHASE5AQ_PARTITION0_CONFIG_SIZE];
static uint32_t s_phase5bbPartition0RawReadCount;
static uint32_t s_phase5bbPartition0RawReadBytes;
static uint32_t s_phase5bbPartition0RawWriteCount;
static uint32_t s_phase5bbPartition0RawWriteBytes;
static uint32_t s_phase5bbPartition0BackingLoaded;
static uint32_t s_phase5bbPartition0BackingLoadBytes;
static uint32_t s_phase5bbPartition0BackingFlushCount;
static uint32_t s_phase5bbPartition0BackingFlushBytes;
static uint32_t s_phase5bbPartition0ChangedWriteCount;
static uint32_t s_phase5bbPartition0UnchangedWriteCount;
static uint32_t s_phase5bbPartition0BackingReady;
static const char s_phase5bbPartition0BackingPath[] =
    "game:\\merc360-partition0\\partition0-config.bin";
static int phase5bb_partition0_backing_load(void);
static int phase5bb_partition0_backing_flush(void);
static uint32_t s_phase5bbCacheRootOpenCount;
static uint32_t s_phase5bbNtDeviceIoControlCallCount;
static uint32_t s_phase5bbNtDeviceIoControlSuccessCount;
static uint32_t s_phase5bbNtDeviceIoControlGeometryCount;
static uint32_t s_phase5bbNtDeviceIoControlPartitionInfoCount;
static uint32_t s_phase5bbNtDeviceIoControlUnknownCount;
static uint32_t s_phase5bbNtDeviceIoControlLastCode;
static uint32_t s_phase5bbNtDeviceIoControlLastStatus;
static uint32_t s_phase5bbHalReturnTrapCount;
static uint32_t s_phase5bbHalReturnRoutine;
static uint32_t s_phase5bbHalReturnLaunchPage;
static uint32_t s_phase5bbDiskIdentityDataReady;
static uint32_t s_phase5bbDiskIdentitySeen40;
static uint32_t s_phase5bbDiskIdentitySeen41;
static uint32_t s_phase5bbDiskIdentitySeen42;
static uint32_t s_phase5bbXeImageFileNameReady;
static uint32_t s_phase5bbXeImageFileNameSeen326;

#define PHASE5AN_AUDIO_FALLBACK_CAP 16u
typedef struct Phase5ANAudioFallbackAllocation
{
    uint32_t inUse;
    uint32_t base;
    uint32_t size;
    uint32_t attributes;
} Phase5ANAudioFallbackAllocation;

static Phase5ANAudioFallbackAllocation
    s_phase5bbAudioFallback[PHASE5AN_AUDIO_FALLBACK_CAP];
static uint32_t s_phase5bbAudioFallbackAttemptCount;
static uint32_t s_phase5bbAudioFallbackSuccessCount;
static uint32_t s_phase5bbAudioFallbackFreeCount;
static uint32_t s_phase5bbAudioAllocFailureTestCount;
static uint32_t s_phase5bbCachePrepareCallCount;
static uint32_t s_phase5bbCachePrepareReadyCount;

#define PHASE5D_SYMLINK_CAP 32u
typedef struct Phase5DSymbolicLink
{
    uint32_t used;
    char link[64];
    char target[192];
} Phase5DSymbolicLink;
static Phase5DSymbolicLink s_phase5dSymbolicLinks[PHASE5D_SYMLINK_CAP];

#define PHASE5AU_SYMLINK_HANDLE_TAG 0x53000000u
#define PHASE5AU_SYMLINK_HANDLE_CAP 32u
typedef struct Phase5BBSymbolicLinkHandle
{
    uint32_t used;
    char link[64];
    char target[192];
    uint32_t targetMaximumLength;
} Phase5BBSymbolicLinkHandle;
static Phase5BBSymbolicLinkHandle
    s_phase5bbSymbolicLinkHandles[PHASE5AU_SYMLINK_HANDLE_CAP];

#define PHASE5B_HANDLE_TAG 0x48000000u
#define PHASE5B_HANDLE_CAP 64u
#define PHASE5B_HANDLE_PATH_CAP 260u
static HANDLE s_phase5bHandles[PHASE5B_HANDLE_CAP];
static char s_phase5bHandlePaths[PHASE5B_HANDLE_CAP][PHASE5B_HANDLE_PATH_CAP];

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
    static const char partition0Root[] = "\\Device\\Harddisk0\\partition0";
    static const char partition1[] = "\\Device\\Harddisk0\\partition1\\";
    static const char partition3Root[] = "\\Device\\Harddisk0\\partition3";
    static const char partition3[] = "\\Device\\Harddisk0\\partition3\\";
    static const char partition4Root[] = "\\Device\\Harddisk0\\partition4";
    static const char partition4[] = "\\Device\\Harddisk0\\partition4\\";
    static const char partition5Root[] = "\\Device\\Harddisk0\\partition5";
    static const char partition5[] = "\\Device\\Harddisk0\\partition5\\";
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
    else if (phase5d_string_equal_ci(xboxPath, partition0Root))
    {
        written = _snprintf(
            nativePath,
            nativeCapacity - 1u,
            "game:\\merc360-partition0");
        if (virtualRoot)
            *virtualRoot = 1;
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
    else if (phase5d_string_equal_ci(xboxPath, partition3Root))
    {
        written = _snprintf(
            nativePath,
            nativeCapacity - 1u,
            "game:\\merc360-partition3");
        if (virtualRoot) *virtualRoot = 1;
    }
    else if (phase5b_prefix_equal_ci(xboxPath, partition3, &consumed))
    {
        remainder = xboxPath + consumed;
        written = _snprintf(
            nativePath,
            nativeCapacity - 1u,
            remainder[0] ? "game:\\merc360-partition3\\%s" : "game:\\merc360-partition3",
            remainder);
        if (virtualRoot && remainder[0] == '\0') *virtualRoot = 1;
    }
    else if (phase5d_string_equal_ci(xboxPath, partition4Root))
    {
        written = _snprintf(
            nativePath,
            nativeCapacity - 1u,
            "game:\\merc360-partition4");
        if (virtualRoot) *virtualRoot = 1;
    }
    else if (phase5b_prefix_equal_ci(xboxPath, partition4, &consumed))
    {
        remainder = xboxPath + consumed;
        written = _snprintf(
            nativePath,
            nativeCapacity - 1u,
            remainder[0] ? "game:\\merc360-partition4\\%s" : "game:\\merc360-partition4",
            remainder);
        if (virtualRoot && remainder[0] == '\0') *virtualRoot = 1;
    }
    else if (phase5d_string_equal_ci(xboxPath, partition5Root))
    {
        written = _snprintf(
            nativePath,
            nativeCapacity - 1u,
            "game:\\merc360-partition5");
        if (virtualRoot) *virtualRoot = 1;
    }
    else if (phase5b_prefix_equal_ci(xboxPath, partition5, &consumed))
    {
        remainder = xboxPath + consumed;
        written = _snprintf(
            nativePath,
            nativeCapacity - 1u,
            remainder[0] ? "game:\\merc360-partition5\\%s" : "game:\\merc360-partition5",
            remainder);
        if (virtualRoot && remainder[0] == '\0') *virtualRoot = 1;
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

static void phase5b_set_handle_path(uint32_t token, const char* nativePath)
{
    uint32_t index;
    if ((token & 0xFF000000u) != PHASE5B_HANDLE_TAG)
        return;
    index = token & 0x00FFFFFFu;
    if (index == 0u || index >= PHASE5B_HANDLE_CAP)
        return;

    s_phase5bHandlePaths[index][0] = '\0';
    if (!nativePath)
        return;

    _snprintf(
        s_phase5bHandlePaths[index],
        PHASE5B_HANDLE_PATH_CAP - 1u,
        "%s",
        nativePath);
    s_phase5bHandlePaths[index][PHASE5B_HANDLE_PATH_CAP - 1u] = '\0';
}

static const char* phase5b_read_handle_path(uint32_t token)
{
    uint32_t index;
    if ((token & 0xFF000000u) != PHASE5B_HANDLE_TAG)
        return NULL;
    index = token & 0x00FFFFFFu;
    if (index == 0u || index >= PHASE5B_HANDLE_CAP)
        return NULL;
    if (s_phase5bHandlePaths[index][0] == '\0')
        return NULL;
    return s_phase5bHandlePaths[index];
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
    s_phase5bHandlePaths[index][0] = '\0';
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


static uint32_t phase5bb_allocate_symbolic_link_handle(
    const char* link,
    const char* target,
    uint32_t targetMaximumLength)
{
    uint32_t i;

    if (!link || !target)
        return 0u;

    for (i = 1u; i < PHASE5AU_SYMLINK_HANDLE_CAP; ++i)
    {
        if (!s_phase5bbSymbolicLinkHandles[i].used)
        {
            s_phase5bbSymbolicLinkHandles[i].used = 1u;
            _snprintf(
                s_phase5bbSymbolicLinkHandles[i].link,
                sizeof(s_phase5bbSymbolicLinkHandles[i].link) - 1u,
                "%s",
                link);
            s_phase5bbSymbolicLinkHandles[i].link[
                sizeof(s_phase5bbSymbolicLinkHandles[i].link) - 1u] = '\0';
            _snprintf(
                s_phase5bbSymbolicLinkHandles[i].target,
                sizeof(s_phase5bbSymbolicLinkHandles[i].target) - 1u,
                "%s",
                target);
            s_phase5bbSymbolicLinkHandles[i].target[
                sizeof(s_phase5bbSymbolicLinkHandles[i].target) - 1u] = '\0';
            s_phase5bbSymbolicLinkHandles[i].targetMaximumLength =
                targetMaximumLength;
            return PHASE5AU_SYMLINK_HANDLE_TAG | i;
        }
    }

    return 0u;
}

static Phase5BBSymbolicLinkHandle* phase5bb_read_symbolic_link_handle(
    uint32_t token)
{
    uint32_t index;

    if ((token & 0xFF000000u) != PHASE5AU_SYMLINK_HANDLE_TAG)
        return NULL;

    index = token & 0x00FFFFFFu;
    if (index == 0u || index >= PHASE5AU_SYMLINK_HANDLE_CAP)
        return NULL;
    if (!s_phase5bbSymbolicLinkHandles[index].used)
        return NULL;

    return &s_phase5bbSymbolicLinkHandles[index];
}

static int phase5bb_close_symbolic_link_handle(uint32_t token)
{
    uint32_t index;

    if ((token & 0xFF000000u) != PHASE5AU_SYMLINK_HANDLE_TAG)
        return 0;

    index = token & 0x00FFFFFFu;
    if (index == 0u ||
        index >= PHASE5AU_SYMLINK_HANDLE_CAP ||
        !s_phase5bbSymbolicLinkHandles[index].used)
        return -1;

    ZeroMemory(
        &s_phase5bbSymbolicLinkHandles[index],
        sizeof(s_phase5bbSymbolicLinkHandles[index]));
    ++s_phase5bbSymbolicLinkCloseCount;
    return 1;
}

static void phase5bb_nt_open_symbolic_link_object(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t handlePtr;
    uint32_t objectAttributesVa;
    uint32_t rootDirectory = 0u;
    uint32_t objectNameVa = 0u;
    uint32_t attributes = 0u;
    uint32_t pathLength = 0u;
    uint32_t pathMaximumLength = 0u;
    uint32_t pathBufferVa = 0u;
    uint32_t status = 0u;
    uint32_t token = 0u;
    uint32_t targetMaximumLength = 0u;
    int linkIndex = -1;
    char path[64];
    char line[896];

    path[0] = '\0';
    ++s_phase5bbNtOpenSymbolicLinkCallCount;

    if (savedEsp != callEsp + 12u)
    {
        sprintf(
            line,
            "NtOpenSymbolicLinkObject FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=12",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000CBu,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    handlePtr = GUEST_READ32(callEsp + 4u);
    objectAttributesVa = GUEST_READ32(callEsp + 8u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000CBu,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "NtOpenSymbolicLinkObject LIVE FRAME: ret=%08X handle_ptr=%08X oa=%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)handlePtr,
        (unsigned int)objectAttributesVa,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u || handlePtr == 0u || objectAttributesVa == 0u)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000CBu,
            savedEsp);
        return;
    }

    rootDirectory = GUEST_READ32(objectAttributesVa + 0u);
    objectNameVa = GUEST_READ32(objectAttributesVa + 4u);
    attributes = GUEST_READ32(objectAttributesVa + 8u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000CBu,
            savedEsp);
        return;
    }

    if (rootDirectory != 0u ||
        !phase5d_copy_guest_ansi_string(
            objectNameVa,
            path,
            sizeof(path),
            &pathLength,
            &pathMaximumLength,
            &pathBufferVa))
    {
        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x800000CBu,
                savedEsp);
            return;
        }
        status = 0xC000000Du;
    }
    else
    {
        linkIndex = phase5d_find_symbolic_link(path);
        if (linkIndex < 0)
        {
            status = 0xC0000034u;
        }
        else
        {
            targetMaximumLength =
                (uint32_t)strlen(s_phase5dSymbolicLinks[linkIndex].target) + 1u;
            token = phase5bb_allocate_symbolic_link_handle(
                s_phase5dSymbolicLinks[linkIndex].link,
                s_phase5dSymbolicLinks[linkIndex].target,
                targetMaximumLength);
            if (token == 0u)
                status = 0xC000009Au;
        }
    }

    sprintf(
        line,
        "NtOpenSymbolicLinkObject OBJECT: root=%08X name=%08X attrs=%08X len=%u max=%u buffer=%08X path=%s",
        (unsigned int)rootDirectory,
        (unsigned int)objectNameVa,
        (unsigned int)attributes,
        (unsigned int)pathLength,
        (unsigned int)pathMaximumLength,
        (unsigned int)pathBufferVa,
        path[0] ? path : "<empty>");
    trace(line);

    if (status == 0u)
    {
        GUEST_WRITE32(handlePtr, token);
        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                handlePtr,
                savedEsp);
            return;
        }

        ++s_phase5bbNtOpenSymbolicLinkSuccessCount;
        s_phase5bbNtOpenSymbolicLinkLastToken = token;

        if (phase5d_string_equal_ci(path, "\\??\\D:") &&
            linkIndex >= 0 &&
            phase5d_string_equal_ci(
                s_phase5dSymbolicLinks[linkIndex].target,
                "\\Device\\CdRom0"))
        {
            ++s_phase5bbNtOpenSymbolicLinkDDriveSuccessCount;
        }
    }

    g_eax = status;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5BB NtOpenSymbolicLinkObject guest-object continuation path=%s target=%s status=%08X token=%08X calls=%u successes=%u ddrive=%u new_esp=%08X",
        path[0] ? path : "<empty>",
        (linkIndex >= 0) ? s_phase5dSymbolicLinks[linkIndex].target : "<missing>",
        (unsigned int)status,
        (unsigned int)token,
        (unsigned int)s_phase5bbNtOpenSymbolicLinkCallCount,
        (unsigned int)s_phase5bbNtOpenSymbolicLinkSuccessCount,
        (unsigned int)s_phase5bbNtOpenSymbolicLinkDDriveSuccessCount,
        (unsigned int)g_esp);
    trace(line);
}

static void phase5bb_nt_query_symbolic_link_object(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    const uint32_t caller = phase4c_current_caller();
    uint32_t frameBytes = savedEsp - callEsp;
    uint32_t resumeEsp = savedEsp;
    uint32_t returnSlot;
    uint32_t handleToken;
    uint32_t targetStringVa;
    uint32_t returnedLengthVa;
    uint32_t targetLength;
    uint32_t targetMaximumLength;
    uint32_t targetBufferVa;
    uint32_t linkLength = 0u;
    uint32_t status = 0u;
    uint32_t extraSlot = 0u;
    uint32_t i;
    Phase5BBSymbolicLinkHandle* linkHandle;
    char line[1024];

    ++s_phase5bbNtQuerySymbolicLinkCallCount;

    /*
     * Xbox ordinal 215 is a three-argument stdcall (12 argument bytes, 16
     * guest bytes including our synthetic return slot). Phase 5AU hardware
     * proved translated caller 0x0022B7B2 presents the otherwise-valid frame
     * with savedEsp one dword too high: callEsp=008BEC64,
     * savedEsp=008BEC78 (20 bytes). Mirror the established NtWriteFile
     * callsite repair policy: fix only this exact observed caller/frame after
     * validating the standard ordinal-215 arguments, and resume at savedEsp-4.
     */
    if (frameBytes == 20u && caller == 0x0022B7B2u)
    {
        uint32_t probeReturn = GUEST_READ32(callEsp + 0u);
        uint32_t probeHandle = GUEST_READ32(callEsp + 4u);
        uint32_t probeTargetString = GUEST_READ32(callEsp + 8u);
        uint32_t probeReturnedLength = GUEST_READ32(callEsp + 12u);
        uint32_t probeExtra = GUEST_READ32(callEsp + 16u);
        uint32_t probeLength = 0u;
        uint32_t probeMaximumLength = 0u;
        uint32_t probeBuffer = 0u;
        Phase5BBSymbolicLinkHandle* probeHandleObject =
            phase5bb_read_symbolic_link_handle(probeHandle);

        if (probeTargetString != 0u)
        {
            probeLength = (uint32_t)GUEST_READ16(probeTargetString + 0u);
            probeMaximumLength = (uint32_t)GUEST_READ16(probeTargetString + 2u);
            probeBuffer = GUEST_READ32(probeTargetString + 4u);
        }

        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x800000D7u,
                savedEsp);
            return;
        }

        sprintf(
            line,
            "NtQuerySymbolicLinkObject SAVEDESP REPAIR PROBE: caller=%08X ret=%08X handle=%08X target_string=%08X returned_length=%08X extra=%08X len=%u max=%u buffer=%08X esp=%08X saved_esp=%08X",
            (unsigned int)caller,
            (unsigned int)probeReturn,
            (unsigned int)probeHandle,
            (unsigned int)probeTargetString,
            (unsigned int)probeReturnedLength,
            (unsigned int)probeExtra,
            (unsigned int)probeLength,
            (unsigned int)probeMaximumLength,
            (unsigned int)probeBuffer,
            (unsigned int)callEsp,
            (unsigned int)savedEsp);
        trace(line);

        if (probeReturn == 0u &&
            probeHandleObject != NULL &&
            probeTargetString != 0u &&
            probeBuffer != 0u &&
            probeMaximumLength != 0u &&
            probeMaximumLength <= 1024u &&
            probeLength <= probeMaximumLength)
        {
            resumeEsp = savedEsp - 4u;
            frameBytes = 16u;
            extraSlot = probeExtra;
            ++s_phase5bbNtQuerySymbolicLinkSavedEspRepairCount;
            s_phase5bbNtQuerySymbolicLinkSavedEspRepairExtra = probeExtra;

            sprintf(
                line,
                "PASS: Phase 5BB NtQuerySymbolicLinkObject caller 0022B7B2 saved-ESP repair extra=%08X %08X->%08X restores 16-byte ordinal-215 frame",
                (unsigned int)probeExtra,
                (unsigned int)savedEsp,
                (unsigned int)resumeEsp);
            trace(line);
        }
    }

    if (frameBytes != 16u)
    {
        sprintf(
            line,
            "NtQuerySymbolicLinkObject FRAME MISMATCH: caller=%08X esp=%08X saved_esp=%08X delta=%u expected=16",
            (unsigned int)caller,
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000D7u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    handleToken = GUEST_READ32(callEsp + 4u);
    targetStringVa = GUEST_READ32(callEsp + 8u);
    returnedLengthVa = GUEST_READ32(callEsp + 12u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000D7u,
            resumeEsp);
        return;
    }

    sprintf(
        line,
        "NtQuerySymbolicLinkObject LIVE FRAME: caller=%08X ret=%08X handle=%08X target_string=%08X returned_length=%08X extra=%08X esp=%08X saved_esp=%08X resume_esp=%08X",
        (unsigned int)caller,
        (unsigned int)returnSlot,
        (unsigned int)handleToken,
        (unsigned int)targetStringVa,
        (unsigned int)returnedLengthVa,
        (unsigned int)extraSlot,
        (unsigned int)callEsp,
        (unsigned int)savedEsp,
        (unsigned int)resumeEsp);
    trace(line);

    if (returnSlot != 0u || targetStringVa == 0u)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000D7u,
            resumeEsp);
        return;
    }

    targetLength = (uint32_t)GUEST_READ16(targetStringVa + 0u);
    targetMaximumLength = (uint32_t)GUEST_READ16(targetStringVa + 2u);
    targetBufferVa = GUEST_READ32(targetStringVa + 4u);
    linkHandle = phase5bb_read_symbolic_link_handle(handleToken);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000D7u,
            resumeEsp);
        return;
    }

    if (!linkHandle)
    {
        status = 0xC0000008u; /* STATUS_INVALID_HANDLE */
    }
    else
    {
        linkLength = (uint32_t)strlen(linkHandle->target);

        if (returnedLengthVa != 0u)
            GUEST_WRITE32(returnedLengthVa, linkHandle->targetMaximumLength);

        if (targetBufferVa == 0u)
        {
            status = 0xC000000Du; /* STATUS_INVALID_PARAMETER */
        }
        else if (linkLength > targetMaximumLength)
        {
            status = 0xC0000023u; /* STATUS_BUFFER_TOO_SMALL */
        }
        else
        {
            for (i = 0u; i < linkLength; ++i)
                GUEST_WRITE8(targetBufferVa + i, (uint8_t)linkHandle->target[i]);
            GUEST_WRITE16(targetStringVa + 0u, (uint16_t)linkLength);
        }
    }

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000D7u,
            resumeEsp);
        return;
    }

    if (status == 0u)
    {
        ++s_phase5bbNtQuerySymbolicLinkSuccessCount;
        s_phase5bbNtQuerySymbolicLinkLastLength = linkLength;
    }

    g_eax = status;
    g_esp = resumeEsp;

    sprintf(
        line,
        "PASS: Phase 5BB NtQuerySymbolicLinkObject guest-object continuation handle=%08X link=%s target=%s status=%08X input_len=%u max=%u returned_len=%u calls=%u successes=%u repairs=%u new_esp=%08X",
        (unsigned int)handleToken,
        linkHandle ? linkHandle->link : "<invalid>",
        linkHandle ? linkHandle->target : "<invalid>",
        (unsigned int)status,
        (unsigned int)targetLength,
        (unsigned int)targetMaximumLength,
        (unsigned int)(linkHandle ? linkHandle->targetMaximumLength : 0u),
        (unsigned int)s_phase5bbNtQuerySymbolicLinkCallCount,
        (unsigned int)s_phase5bbNtQuerySymbolicLinkSuccessCount,
        (unsigned int)s_phase5bbNtQuerySymbolicLinkSavedEspRepairCount,
        (unsigned int)g_esp);
    trace(line);
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
        "PASS: Phase 5BB IoCreateSymbolicLink native continuation link=%s target=%s status=%08X creates=%u new_esp=%08X",
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
        "PASS: Phase 5BB IoDeleteSymbolicLink native continuation link=%s status=%08X deletes=%u new_esp=%08X",
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
        "PASS: Phase 5BB NtQueryVolumeInformationFile native continuation class=%u total_units=%I64u available_units=%I64u sectors_per_unit=32 bytes_per_sector=512 calls=%u new_esp=%08X",
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

    {
        int symbolicClose = phase5bb_close_symbolic_link_handle(handleToken);
        if (symbolicClose > 0)
        {
            status = 0u;
            ++s_phase5cCloseCount;
        }
        else if (symbolicClose < 0)
        {
            status = 0xC0000008u; /* STATUS_INVALID_HANDLE */
        }
        else
        {
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
        }
    }

    g_eax = status;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5BB NtClose native continuation handle=%08X status=%08X closes=%u new_esp=%08X",
        (unsigned int)handleToken,
        (unsigned int)status,
        (unsigned int)s_phase5cCloseCount,
        (unsigned int)g_esp);
    trace(line);
}

static uint64_t phase5ah_filetime_value(const FILETIME* value)
{
    return ((uint64_t)value->dwHighDateTime << 32) |
           (uint64_t)value->dwLowDateTime;
}

static void phase5ah_write_guest_u64(uint32_t address, uint64_t value)
{
    GUEST_WRITE32(address + 0u, (uint32_t)value);
    GUEST_WRITE32(address + 4u, (uint32_t)(value >> 32));
}

static void phase5ah_nt_query_information_file(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t handleToken;
    uint32_t ioStatusVa;
    uint32_t infoVa;
    uint32_t length;
    uint32_t infoClass;
    uint32_t status = 0u;
    uint32_t attributes = 0u;
    DWORD error = ERROR_SUCCESS;
    HANDLE nativeHandle;
    const char* nativePath;
    WIN32_FILE_ATTRIBUTE_DATA data;
    uint64_t creationTime = 0ui64;
    uint64_t lastAccessTime = 0ui64;
    uint64_t lastWriteTime = 0ui64;
    uint64_t changeTime = 0ui64;
    uint64_t endOfFile = 0ui64;
    uint64_t allocationSize = 0ui64;
    char line[1024];

    if (savedEsp != callEsp + 24u)
    {
        sprintf(
            line,
            "NtQueryInformationFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=24",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000D3u,
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
            0x800000D3u,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "NtQueryInformationFile LIVE FRAME: ret=%08X handle=%08X iosb=%08X info=%08X len=%u class=%u esp=%08X saved_esp=%08X",
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
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000D3u,
            savedEsp);
        return;
    }

    ++s_phase5ahNtQueryInformationFileCallCount;
    s_phase5ahNtQueryInformationFileLastClass = infoClass;

    if (infoClass != 34u)
    {
        sprintf(
            line,
            "FILE INFORMATION UNSUPPORTED: NtQueryInformationFile class=%u len=%u handle=%08X",
            (unsigned int)infoClass,
            (unsigned int)length,
            (unsigned int)handleToken);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_FILE_INFORMATION,
            0x800000D3u,
            savedEsp);
        return;
    }

    if (length < 56u)
    {
        status = 0xC0000004u; /* STATUS_INFO_LENGTH_MISMATCH */
        GUEST_WRITE32(ioStatusVa + 0u, status);
        GUEST_WRITE32(ioStatusVa + 4u, 0u);
        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x800000D3u,
                savedEsp);
            return;
        }

        g_eax = status;
        g_esp = savedEsp;
        trace("PASS: Phase 5BB NtQueryInformationFile class 34 length-mismatch semantics");
        return;
    }

    nativeHandle = phase5c_read_native_handle(handleToken);
    nativePath = phase5b_read_handle_path(handleToken);
    if (!nativeHandle || !nativePath)
    {
        status = 0xC0000008u; /* STATUS_INVALID_HANDLE */
    }
    else
    {
        ZeroMemory(&data, sizeof(data));
        SetLastError(ERROR_SUCCESS);
        if (!GetFileAttributesExA(
                nativePath,
                GetFileExInfoStandard,
                &data))
        {
            error = GetLastError();
            status = phase5b_open_status_from_error(error);
        }
        else
        {
            creationTime = phase5ah_filetime_value(&data.ftCreationTime);
            lastAccessTime = phase5ah_filetime_value(&data.ftLastAccessTime);
            lastWriteTime = phase5ah_filetime_value(&data.ftLastWriteTime);
            changeTime = lastWriteTime;
            endOfFile =
                ((uint64_t)data.nFileSizeHigh << 32) |
                (uint64_t)data.nFileSizeLow;
            if (endOfFile == 0ui64)
            {
                allocationSize = 0ui64;
            }
            else if (endOfFile <= 0xFFFFFFFFFFFFC000ui64)
            {
                allocationSize =
                    (endOfFile + 0x3FFFui64) & ~0x3FFFui64;
            }
            else
            {
                allocationSize = endOfFile;
            }
            attributes = data.dwFileAttributes;
            if (attributes == 0u)
                attributes = FILE_ATTRIBUTE_NORMAL;
        }
    }

    if (status == 0u)
    {
        phase5ah_write_guest_u64(infoVa + 0u, creationTime);
        phase5ah_write_guest_u64(infoVa + 8u, lastAccessTime);
        phase5ah_write_guest_u64(infoVa + 16u, lastWriteTime);
        phase5ah_write_guest_u64(infoVa + 24u, changeTime);
        phase5ah_write_guest_u64(infoVa + 32u, allocationSize);
        phase5ah_write_guest_u64(infoVa + 40u, endOfFile);
        GUEST_WRITE32(infoVa + 48u, attributes);
        GUEST_WRITE32(infoVa + 52u, 0u);
        GUEST_WRITE32(ioStatusVa + 0u, 0u);
        GUEST_WRITE32(ioStatusVa + 4u, 56u);
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
            0x800000D3u,
            savedEsp);
        return;
    }

    if (status == 0u)
        ++s_phase5ahNtQueryInformationFileSuccessCount;

    g_eax = status;
    g_esp = savedEsp;

    sprintf(
        line,
        "NtQueryInformationFile NATIVE: class=%u path=%s status=%08X error=%u eof=%I64u allocation=%I64u attrs=%08X",
        (unsigned int)infoClass,
        nativePath ? nativePath : "<none>",
        (unsigned int)status,
        (unsigned int)error,
        endOfFile,
        allocationSize,
        (unsigned int)attributes);
    trace(line);

    sprintf(
        line,
        "PASS: Phase 5BB NtQueryInformationFile class 34 native continuation status=%08X calls=%u successes=%u new_esp=%08X",
        (unsigned int)status,
        (unsigned int)s_phase5ahNtQueryInformationFileCallCount,
        (unsigned int)s_phase5ahNtQueryInformationFileSuccessCount,
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
        "PASS: Phase 5BB RtlEqualString continuation string1=%08X len1=%u preview1=%s string2=%08X len2=%u preview2=%s case_insensitive=%u result=%u calls=%u true_calls=%u new_esp=%08X",
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
    const uint32_t caller = phase4c_current_caller();
    uint32_t frameBytes = savedEsp - callEsp;
    uint32_t resumeEsp = savedEsp;
    uint32_t returnSlot;
    uint32_t destinationVa;
    uint32_t sourceVa;
    uint32_t length = 0u;
    uint32_t i;
    char preview[129];
    char line[768];

    /*
     * Xbox ordinal 289 is RtlInitAnsiString(destination, source): two stdcall
     * arguments, or 12 guest bytes including our synthetic return slot.
     * Phase 5AX hardware proved translated caller 0x0022A7A4 presents a
     * 16-byte saved-ESP delta. Repair only that exact caller/frame after
     * validating the canonical arguments; resume at savedEsp-4.
     */
    if (frameBytes == 16u && caller == 0x0022A7A4u)
    {
        uint32_t probeReturn = GUEST_READ32(callEsp + 0u);
        uint32_t probeDestination = GUEST_READ32(callEsp + 4u);
        uint32_t probeSource = GUEST_READ32(callEsp + 8u);
        uint32_t probeExtra = GUEST_READ32(callEsp + 12u);
        BYTE* probeDestinationPtr =
            probeDestination ? guest_ptr((DWORD)probeDestination, 8u) : NULL;
        BYTE* probeSourcePtr =
            probeSource ? guest_ptr((DWORD)probeSource, 1u) : (BYTE*)1;

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
            "RtlInitAnsiString SAVEDESP REPAIR PROBE: caller=%08X ret=%08X destination=%08X source=%08X extra=%08X esp=%08X saved_esp=%08X",
            (unsigned int)caller,
            (unsigned int)probeReturn,
            (unsigned int)probeDestination,
            (unsigned int)probeSource,
            (unsigned int)probeExtra,
            (unsigned int)callEsp,
            (unsigned int)savedEsp);
        trace(line);

        if (probeReturn != 0u ||
            probeDestination == 0u ||
            probeDestinationPtr == NULL ||
            probeSourcePtr == NULL)
        {
            trace("RtlInitAnsiString SAVEDESP REPAIR REJECTED: caller 0022A7A4 did not match canonical ordinal-289 arguments");
            phase4c_escape(
                PHASE4C_BOUNDARY_KERNEL_FRAME,
                0x80000121u,
                savedEsp);
            return;
        }

        resumeEsp = savedEsp - 4u;
        frameBytes = 12u;
        ++s_phase5bbRtlInitAnsiSavedEspRepairCount;
        s_phase5bbRtlInitAnsiSavedEspRepairExtra = probeExtra;
        s_phase5bbRtlInitAnsiSavedEspRepairLastResumeEsp = resumeEsp;

        sprintf(
            line,
            "PASS: Phase 5BB RtlInitAnsiString caller 0022A7A4 saved-ESP repair extra=%08X %08X->%08X restores 12-byte ordinal-289 frame",
            (unsigned int)probeExtra,
            (unsigned int)savedEsp,
            (unsigned int)resumeEsp);
        trace(line);
    }

    if (frameBytes != 12u)
    {
        sprintf(
            line,
            "RtlInitAnsiString FRAME MISMATCH: caller=%08X esp=%08X saved_esp=%08X delta=%u expected=12",
            (unsigned int)caller,
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
            resumeEsp);
        return;
    }

    sprintf(
        line,
        "RtlInitAnsiString LIVE FRAME: caller=%08X ret=%08X destination=%08X source=%08X esp=%08X saved_esp=%08X resume_esp=%08X",
        (unsigned int)caller,
        (unsigned int)returnSlot,
        (unsigned int)destinationVa,
        (unsigned int)sourceVa,
        (unsigned int)callEsp,
        (unsigned int)savedEsp,
        (unsigned int)resumeEsp);
    trace(line);

    if (returnSlot != 0u)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000121u,
            resumeEsp);
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
                    resumeEsp);
                return;
            }

            if (length < 128u)
                preview[length] =
                    (ch >= 0x20u && ch <= 0x7Eu) ? (char)ch : '.';

            if (ch == 0u)
                break;
        }

        if (length == 0xFFFEu)
            trace("RtlInitAnsiString: source exceeded maintained 0xFFFE-byte clamp");

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
            resumeEsp);
        return;
    }

    s_phase5iRtlInitAnsiStringLastLength = length;
    s_phase5iRtlInitAnsiStringLastDestination = destinationVa;
    s_phase5iRtlInitAnsiStringLastSource = sourceVa;
    ++s_phase5iRtlInitAnsiStringCount;

    g_eax = 0u;
    g_esp = resumeEsp;

    sprintf(
        line,
        "PASS: Phase 5BB RtlInitAnsiString continuation caller=%08X destination=%08X source=%08X len=%u max=%u preview=%s calls=%u repairs=%u new_esp=%08X",
        (unsigned int)caller,
        (unsigned int)destinationVa,
        (unsigned int)sourceVa,
        (unsigned int)length,
        (unsigned int)(sourceVa ? (length < 0xFFFEu ? length + 1u : 0xFFFFu) : 0u),
        sourceVa ? preview : "<null>",
        (unsigned int)s_phase5iRtlInitAnsiStringCount,
        (unsigned int)s_phase5bbRtlInitAnsiSavedEspRepairCount,
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

    if ((rootDirectory != 0u && rootDirectory != 0xFFFFFFFDu) ||
        pathVa == 0u ||
        pathLength == 0u ||
        pathLength > 255u)
    {
        sprintf(
            line,
            "STORAGE IO UNSUPPORTED: NtCreateFile unsupported-root/invalid path root=%08X path_va=%08X len=%u",
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

    if (rootDirectory == 0xFFFFFFFDu)
    {
        ++s_phase5bbNtCreateFileObDosDevicesCount;
        sprintf(
            line,
            "NtCreateFile OBDOSDEVICES: root=FFFFFFFD path=%s calls=%u",
            path,
            (unsigned int)s_phase5bbNtCreateFileObDosDevicesCount);
        trace(line);
    }

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

    if (rootDirectory == 0xFFFFFFFDu)
    {
        ++s_phase5bbNtCreateFileObDosDevicesMappedCount;
        sprintf(
            line,
            "PASS: Phase 5BB NtCreateFile ObDosDevices path expansion xbox=%s native=%s mappings=%u",
            path,
            nativePath,
            (unsigned int)s_phase5bbNtCreateFileObDosDevicesMappedCount);
        trace(line);
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
            else
            {
                phase5b_set_handle_path(token, nativePath);
            }
        }
    }

    if (status == 0u && rootDirectory == 0xFFFFFFFDu)
        ++s_phase5bbNtCreateFileObDosDevicesSuccessCount;

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
        "PASS: Phase 5BB NtCreateFile native continuation status=%08X token=%08X calls=%u successes=%u new_esp=%08X",
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
    const char* handlePath;
    int partition0Config = 0;
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
    handlePath = phase5b_read_handle_path(handleToken);
    if (!nativeHandle)
    {
        status = 0xC0000008u; /* STATUS_INVALID_HANDLE */
    }
    partition0Config =
        status == 0u &&
        handlePath != NULL &&
        phase5d_string_equal_ci(handlePath, "game:\\merc360-partition0");

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

    if (status == 0u && partition0Config)
    {
        unsigned __int64 rawOffset =
            ((unsigned __int64)offsetHigh << 32) | offsetLow;
        uint32_t available = 0u;
        uint32_t transfer = 0u;

        if (offsetVa == 0u)
            rawOffset = 0u;

        if (rawOffset >= PHASE5AQ_PARTITION0_CONFIG_SIZE)
        {
            status = 0xC0000011u; /* STATUS_END_OF_FILE */
        }
        else
        {
            available =
                PHASE5AQ_PARTITION0_CONFIG_SIZE - (uint32_t)rawOffset;
            transfer = length < available ? length : available;
            if (transfer != 0u)
                memcpy(
                    guestBuffer,
                    s_phase5bbPartition0Config + (uint32_t)rawOffset,
                    transfer);
            bytesRead = transfer;
            if (length != 0u && transfer == 0u)
                status = 0xC0000011u;
            else
            {
                ++s_phase5bbPartition0RawReadCount;
                s_phase5bbPartition0RawReadBytes += transfer;
                sprintf(
                    line,
                    "PASS: Phase 5BB Partition0 config raw read offset=%08X%08X requested=%u bytes=%u reads=%u total_bytes=%u",
                    (unsigned int)offsetHigh,
                    (unsigned int)offsetLow,
                    (unsigned int)length,
                    (unsigned int)bytesRead,
                    (unsigned int)s_phase5bbPartition0RawReadCount,
                    (unsigned int)s_phase5bbPartition0RawReadBytes);
                trace(line);
            }
        }
    }

    if (status == 0u && !partition0Config && offsetVa != 0u)
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

    if (status == 0u && !partition0Config)
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
        "PASS: Phase 5BB NtReadFile native continuation handle=%08X status=%08X bytes=%u error=%u calls=%u successes=%u new_esp=%08X",
        (unsigned int)handleToken,
        (unsigned int)status,
        (unsigned int)bytesRead,
        (unsigned int)error,
        (unsigned int)s_phase5hNtReadFileCallCount,
        (unsigned int)s_phase5hNtReadFileSuccessCount,
        (unsigned int)g_esp);
    trace(line);
}

static uint32_t phase5ah_write_status_from_error(DWORD error)
{
    switch (error)
    {
    case ERROR_ACCESS_DENIED:
        return 0xC0000022u; /* STATUS_ACCESS_DENIED */
    case ERROR_INVALID_HANDLE:
        return 0xC0000008u; /* STATUS_INVALID_HANDLE */
    case 112u: /* ERROR_DISK_FULL */
    case 39u:  /* ERROR_HANDLE_DISK_FULL */
        return 0xC000007Fu; /* STATUS_DISK_FULL */
    default:
        return 0xC0000001u; /* STATUS_UNSUCCESSFUL */
    }
}

static int phase5ah_seek_end(HANDLE handle)
{
    LONG high = 0;
    DWORD low;

    SetLastError(ERROR_SUCCESS);
    low = SetFilePointer(handle, 0, &high, FILE_END);
    return !(
        low == 0xFFFFFFFFu &&
        GetLastError() != ERROR_SUCCESS);
}

static int phase5ah_path_ends_with_ci(
    const char* path,
    const char* suffix)
{
    size_t pathLength;
    size_t suffixLength;
    size_t i;

    if (!path || !suffix)
        return 0;

    pathLength = strlen(path);
    suffixLength = strlen(suffix);
    if (suffixLength > pathLength)
        return 0;

    path += pathLength - suffixLength;
    for (i = 0u; i < suffixLength; ++i)
    {
        if (phase5b_ascii_lower((unsigned char)path[i]) !=
            phase5b_ascii_lower((unsigned char)suffix[i]))
            return 0;
    }
    return 1;
}

static void phase5ah_nt_write_file(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    const uint32_t caller = phase4c_current_caller();
    uint32_t frameBytes = savedEsp - callEsp;
    uint32_t resumeEsp = savedEsp;
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
    uint32_t repairedSavedEsp = 0u;
    DWORD bytesWritten = 0u;
    DWORD error = ERROR_SUCCESS;
    HANDLE nativeHandle;
    BYTE* guestBuffer;
    const char* handlePath;
    int partition0Config = 0;
    char line[1024];

    /*
     * Standard NtWriteFile@32 occupies 36 guest bytes including our synthetic
     * return slot. Phase 5Z proved caller 0x0022F0CC has all eight arguments,
     * including ByteOffset at +0x20, but its translated RECOMP_ICALL_SAFE
     * savedEsp is one dword short. Repair only that exact observed call site.
     */
    if (frameBytes == 32u && caller == 0x0022F0CCu)
    {
        uint32_t probeReturn = GUEST_READ32(callEsp + 0u);
        uint32_t probeHandle = GUEST_READ32(callEsp + 4u);
        uint32_t probeEvent = GUEST_READ32(callEsp + 8u);
        uint32_t probeApc = GUEST_READ32(callEsp + 12u);
        uint32_t probeContext = GUEST_READ32(callEsp + 16u);
        uint32_t probeIosb = GUEST_READ32(callEsp + 20u);
        uint32_t probeBuffer = GUEST_READ32(callEsp + 24u);
        uint32_t probeLength = GUEST_READ32(callEsp + 28u);
        uint32_t probeOffset = GUEST_READ32(callEsp + 32u);
        const char* probePath = phase5b_read_handle_path(probeHandle);
        uint32_t imageIndex = 0xFFFFFFFFu;
        const char* imageName = "<unsupported>";
        int imageFrameMatched = 0;

        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x800000ECu,
                savedEsp);
            return;
        }

        sprintf(
            line,
            "NtWriteFile SAVEDESP REPAIR PROBE: caller=%08X ret=%08X handle=%08X event=%08X apc=%08X context=%08X iosb=%08X buffer=%08X len=%u offset_ptr=%08X path=%s last_section_index=%u esp=%08X saved_esp=%08X",
            (unsigned int)caller,
            (unsigned int)probeReturn,
            (unsigned int)probeHandle,
            (unsigned int)probeEvent,
            (unsigned int)probeApc,
            (unsigned int)probeContext,
            (unsigned int)probeIosb,
            (unsigned int)probeBuffer,
            (unsigned int)probeLength,
            (unsigned int)probeOffset,
            probePath ? probePath : "<none>",
            (unsigned int)s_phase5ahXeLoadSectionLastIndex,
            (unsigned int)callEsp,
            (unsigned int)savedEsp);
        trace(line);

        if (probeReturn == 0u &&
            probeEvent == 0u &&
            probeApc == 0u &&
            probeContext == 0u &&
            probeIosb != 0u &&
            probeHandle != 0u &&
            probeOffset == 0u &&
            probePath != NULL &&
            s_phase5ahXeLoadSectionSuccessCount > 0u)
        {
            if (s_phase5ahXeLoadSectionLastIndex == 11u &&
                s_phase5ahXeLoadSectionLastSectionVa == 0x000105D8u &&
                probeBuffer == 0x00874D40u &&
                probeLength == 0x00002800u &&
                phase5ah_path_ends_with_ci(probePath, "\\TitleImage.xbx"))
            {
                imageFrameMatched = 1;
                imageIndex = 11u;
                imageName = "$$XTIMAGE";
            }
            else if (s_phase5ahXeLoadSectionLastIndex == 12u &&
                     s_phase5ahXeLoadSectionLastSectionVa == 0x00010610u &&
                     probeBuffer == 0x00877540u &&
                     probeLength == 0x00001000u &&
                     phase5ah_path_ends_with_ci(probePath, "\\SaveImage.xbx"))
            {
                imageFrameMatched = 1;
                imageIndex = 12u;
                imageName = "$$XSIMAGE";
            }
        }

        if (!imageFrameMatched)
        {
            trace("NtWriteFile SAVEDESP REPAIR REJECTED: caller 0022F0CC did not match a proven loaded image-section/file pair");
            phase4c_escape(
                PHASE4C_BOUNDARY_KERNEL_FRAME,
                0x800000ECu,
                savedEsp);
            return;
        }

        repairedSavedEsp = savedEsp + 4u;
        resumeEsp = repairedSavedEsp;
        frameBytes = 36u;
        ++s_phase5ahNtWriteFileSavedEspRepairCount;
        s_phase5ahNtWriteFileSavedEspRepairLastImageIndex = imageIndex;

        sprintf(
            line,
            "PASS: Phase 5BB NtWriteFile caller 0022F0CC saved-ESP repair image=%s index=%u %08X->%08X restores full 36-byte stdcall frame",
            imageName,
            (unsigned int)imageIndex,
            (unsigned int)savedEsp,
            (unsigned int)resumeEsp);
        trace(line);
    }

    if (frameBytes != 36u)
    {
        sprintf(
            line,
            "NtWriteFile FRAME MISMATCH: caller=%08X esp=%08X saved_esp=%08X delta=%u expected=36",
            (unsigned int)caller,
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000ECu,
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
            0x800000ECu,
            resumeEsp);
        return;
    }

    sprintf(
        line,
        "NtWriteFile LIVE FRAME: caller=%08X ret=%08X handle=%08X event=%08X apc=%08X context=%08X iosb=%08X buffer=%08X len=%u offset_ptr=%08X offset=%08X%08X esp=%08X saved_esp=%08X resume_esp=%08X",
        (unsigned int)caller,
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
        (unsigned int)savedEsp,
        (unsigned int)resumeEsp);
    trace(line);

    if (returnSlot != 0u || ioStatusVa == 0u ||
        (length != 0u && bufferVa == 0u))
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000ECu,
            resumeEsp);
        return;
    }

    if (eventToken != 0u || apcRoutine != 0u || apcContext != 0u)
    {
        trace("STORAGE IO UNSUPPORTED: asynchronous NtWriteFile event/APC form");
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_IO,
            0x800000ECu,
            resumeEsp);
        return;
    }

    nativeHandle = phase5c_read_native_handle(handleToken);
    handlePath = phase5b_read_handle_path(handleToken);
    if (!nativeHandle)
    {
        status = 0xC0000008u; /* STATUS_INVALID_HANDLE */
    }
    partition0Config =
        status == 0u &&
        handlePath != NULL &&
        phase5d_string_equal_ci(handlePath, "game:\\merc360-partition0");

    guestBuffer = length ? guest_ptr((DWORD)bufferVa, (DWORD)length) : NULL;
    if (status == 0u && length != 0u && !guestBuffer)
    {
        s_accessFault = 1;
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            bufferVa,
            resumeEsp);
        return;
    }

    if (status == 0u && partition0Config)
    {
        unsigned __int64 rawOffset =
            ((unsigned __int64)offsetHigh << 32) | offsetLow;

        if (offsetVa == 0u)
            rawOffset = 0u;

        if ((offsetHigh & 0x80000000u) != 0u ||
            rawOffset > PHASE5AQ_PARTITION0_CONFIG_SIZE ||
            length > PHASE5AQ_PARTITION0_CONFIG_SIZE - (uint32_t)rawOffset)
        {
            status = 0xC000007Fu; /* STATUS_DISK_FULL / bounded device overflow */
        }
        else
        {
            int changed = 0;
            if (length != 0u)
            {
                changed =
                    memcmp(
                        s_phase5bbPartition0Config + (uint32_t)rawOffset,
                        guestBuffer,
                        length) != 0;
                memcpy(
                    s_phase5bbPartition0Config + (uint32_t)rawOffset,
                    guestBuffer,
                    length);
            }

            if (changed)
                ++s_phase5bbPartition0ChangedWriteCount;
            else
                ++s_phase5bbPartition0UnchangedWriteCount;

            if (!phase5bb_partition0_backing_flush())
            {
                status = 0xC0000001u; /* STATUS_UNSUCCESSFUL */
            }
            else
            {
                bytesWritten = length;
                ++s_phase5bbPartition0RawWriteCount;
                s_phase5bbPartition0RawWriteBytes += bytesWritten;
                sprintf(
                    line,
                    "PASS: Phase 5BB Partition0 config raw write offset=%08X%08X requested=%u bytes=%u changed=%u writes=%u changed_writes=%u unchanged_writes=%u total_bytes=%u",
                    (unsigned int)offsetHigh,
                    (unsigned int)offsetLow,
                    (unsigned int)length,
                    (unsigned int)bytesWritten,
                    (unsigned int)(changed ? 1u : 0u),
                    (unsigned int)s_phase5bbPartition0RawWriteCount,
                    (unsigned int)s_phase5bbPartition0ChangedWriteCount,
                    (unsigned int)s_phase5bbPartition0UnchangedWriteCount,
                    (unsigned int)s_phase5bbPartition0RawWriteBytes);
                trace(line);
            }
        }
    }

    if (status == 0u && !partition0Config && offsetVa != 0u)
    {
        if (offsetHigh == 0xFFFFFFFFu && offsetLow == 0xFFFFFFFFu)
        {
            /* FILE_USE_FILE_POINTER_POSITION: keep current position. */
        }
        else if (offsetHigh == 0xFFFFFFFFu && offsetLow == 0xFFFFFFFEu)
        {
            /* FILE_WRITE_TO_END_OF_FILE. */
            if (!phase5ah_seek_end(nativeHandle))
            {
                error = GetLastError();
                status = phase5ah_write_status_from_error(error);
            }
        }
        else if ((offsetHigh & 0x80000000u) != 0u)
        {
            trace("STORAGE IO UNSUPPORTED: NtWriteFile negative/special byte offset");
            phase4c_escape(
                PHASE4C_BOUNDARY_STORAGE_IO,
                0x800000ECu,
                resumeEsp);
            return;
        }
        else if (!phase5h_seek_absolute(
                     nativeHandle, offsetLow, offsetHigh))
        {
            error = GetLastError();
            status = phase5ah_write_status_from_error(error);
        }
    }

    if (status == 0u && !partition0Config && length != 0u)
    {
        SetLastError(ERROR_SUCCESS);
        if (!WriteFile(
                nativeHandle,
                guestBuffer,
                length,
                &bytesWritten,
                NULL))
        {
            error = GetLastError();
            status = phase5ah_write_status_from_error(error);
        }
        else if (bytesWritten != length)
        {
            status = 0xC0000001u; /* STATUS_UNSUCCESSFUL */
        }
    }

    GUEST_WRITE32(ioStatusVa + 0u, status);
    GUEST_WRITE32(ioStatusVa + 4u, bytesWritten);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000ECu,
            resumeEsp);
        return;
    }

    ++s_phase5ahNtWriteFileCallCount;
    if (status == 0u)
        ++s_phase5ahNtWriteFileSuccessCount;
    s_phase5ahNtWriteFileLastBytes = bytesWritten;
    s_phase5ahNtWriteFileLastStatus = status;

    if (repairedSavedEsp != 0u)
    {
        if (status == 0u)
        {
            ++s_phase5ahNtWriteFileSavedEspRepairSuccessCount;
            if (s_phase5ahNtWriteFileSavedEspRepairLastImageIndex == 12u &&
                bytesWritten == 0x00001000u)
                ++s_phase5ahNtWriteFileXsImageSuccessCount;
        }
        s_phase5ahNtWriteFileSavedEspRepairLastBytes = bytesWritten;
        s_phase5ahNtWriteFileSavedEspRepairLastResumeEsp = resumeEsp;
    }

    g_eax = status;
    g_esp = resumeEsp;

    sprintf(
        line,
        "PASS: Phase 5BB NtWriteFile native continuation caller=%08X handle=%08X status=%08X bytes=%u requested=%u error=%u repairs=%u repair_successes=%u new_esp=%08X",
        (unsigned int)caller,
        (unsigned int)handleToken,
        (unsigned int)status,
        (unsigned int)bytesWritten,
        (unsigned int)length,
        (unsigned int)error,
        (unsigned int)s_phase5ahNtWriteFileSavedEspRepairCount,
        (unsigned int)s_phase5ahNtWriteFileSavedEspRepairSuccessCount,
        (unsigned int)g_esp);
    trace(line);
}

static int phase5ah_copy_guest_cstr(
    uint32_t stringVa,
    char* out,
    uint32_t capacity)
{
    uint32_t i;

    if (!stringVa || !out || capacity < 2u)
        return 0;

    for (i = 0u; i + 1u < capacity; ++i)
    {
        uint32_t value = (uint32_t)GUEST_READ8(stringVa + i);
        if (s_accessFault)
            return 0;
        out[i] = (char)value;
        if (value == 0u)
            return 1;
    }

    out[capacity - 1u] = '\0';
    return 1;
}

static void phase5ah_xe_load_section(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t sectionVa;
    uint32_t sectionCount;
    uint32_t sectionTableVa;
    uint32_t tableBytes;
    uint32_t delta;
    uint32_t index;
    uint32_t flags;
    uint32_t virtualAddress;
    uint32_t virtualSize;
    uint32_t fileAddress;
    uint32_t fileSize;
    uint32_t nameVa;
    uint32_t oldRefCount;
    uint32_t newRefCount;
    uint32_t headRefVa;
    uint32_t tailRefVa;
    uint32_t headRefCount = 0u;
    uint32_t tailRefCount = 0u;
    char sectionName[64];
    char line[896];

    if (savedEsp != callEsp + 8u)
    {
        sprintf(
            line,
            "XeLoadSection FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=8",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000147u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    sectionVa = GUEST_READ32(callEsp + 4u);
    sectionCount = GUEST_READ32(0x0001011Cu);
    sectionTableVa = GUEST_READ32(0x00010120u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000147u,
            savedEsp);
        return;
    }

    sprintf(
        line,
        "XeLoadSection LIVE FRAME: ret=%08X section=%08X section_table=%08X section_count=%u esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)sectionVa,
        (unsigned int)sectionTableVa,
        (unsigned int)sectionCount,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u ||
        sectionVa == 0u ||
        sectionCount == 0u ||
        sectionCount > 64u ||
        sectionTableVa == 0u)
    {
        trace("XELOADSECTION UNSUPPORTED: invalid call/header contract");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000147u,
            savedEsp);
        return;
    }

    tableBytes = sectionCount * 0x38u;
    if (sectionVa < sectionTableVa ||
        sectionVa >= sectionTableVa + tableBytes)
    {
        trace("XELOADSECTION UNSUPPORTED: section pointer is outside the XBE section table");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000147u,
            savedEsp);
        return;
    }

    delta = sectionVa - sectionTableVa;
    if ((delta % 0x38u) != 0u)
    {
        trace("XELOADSECTION UNSUPPORTED: section pointer is not aligned to an XBE section header");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000147u,
            savedEsp);
        return;
    }

    index = delta / 0x38u;
    if (index >= sectionCount)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000147u,
            savedEsp);
        return;
    }

    flags = GUEST_READ32(sectionVa + 0x00u);
    virtualAddress = GUEST_READ32(sectionVa + 0x04u);
    virtualSize = GUEST_READ32(sectionVa + 0x08u);
    fileAddress = GUEST_READ32(sectionVa + 0x0Cu);
    fileSize = GUEST_READ32(sectionVa + 0x10u);
    nameVa = GUEST_READ32(sectionVa + 0x14u);
    oldRefCount = GUEST_READ32(sectionVa + 0x18u);
    headRefVa = GUEST_READ32(sectionVa + 0x1Cu);
    tailRefVa = GUEST_READ32(sectionVa + 0x20u);

    if (s_accessFault ||
        virtualAddress < 0x00010000u ||
        virtualAddress >= RAM_SIZE ||
        virtualSize > RAM_SIZE - virtualAddress ||
        fileSize > virtualSize)
    {
        trace("XELOADSECTION UNSUPPORTED: malformed XBE section metadata");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000147u,
            savedEsp);
        return;
    }

    if (!phase5ah_copy_guest_cstr(nameVa, sectionName, sizeof(sectionName)))
    {
        trace("XELOADSECTION UNSUPPORTED: section name is unreadable");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000147u,
            savedEsp);
        return;
    }

    if ((oldRefCount & 0x80000000u) != 0u ||
        oldRefCount == 0x7FFFFFFFu)
    {
        trace("XELOADSECTION UNSUPPORTED: invalid section reference count");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000147u,
            savedEsp);
        return;
    }

    newRefCount = oldRefCount + 1u;

    if (oldRefCount == 0u)
    {
        if (headRefVa != 0u)
        {
            headRefCount = (uint32_t)GUEST_READ16(headRefVa);
            if (s_accessFault || headRefCount == 0xFFFFu)
            {
                phase4c_escape(
                    PHASE4C_BOUNDARY_GUEST_FAULT,
                    headRefVa,
                    savedEsp);
                return;
            }
            GUEST_WRITE16(headRefVa, (uint16_t)(headRefCount + 1u));
        }

        if (tailRefVa != 0u)
        {
            tailRefCount = (uint32_t)GUEST_READ16(tailRefVa);
            if (s_accessFault || tailRefCount == 0xFFFFu)
            {
                phase4c_escape(
                    PHASE4C_BOUNDARY_GUEST_FAULT,
                    tailRefVa,
                    savedEsp);
                return;
            }
            if (tailRefVa != headRefVa)
                GUEST_WRITE16(tailRefVa, (uint16_t)(tailRefCount + 1u));
        }
    }

    GUEST_WRITE32(sectionVa + 0x18u, newRefCount);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            sectionVa + 0x18u,
            savedEsp);
        return;
    }

    ++s_phase5ahXeLoadSectionCallCount;
    ++s_phase5ahXeLoadSectionSuccessCount;
    s_phase5ahXeLoadSectionLastSectionVa = sectionVa;
    s_phase5ahXeLoadSectionLastIndex = index;
    s_phase5ahXeLoadSectionLastRefCount = newRefCount;

    g_eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5BB XeLoadSection native continuation index=%u name=%s section=%08X flags=%08X va=%08X vsize=%u file=%08X fsize=%u refs=%u->%u head_ref=%08X tail_ref=%08X calls=%u new_esp=%08X",
        (unsigned int)index,
        sectionName,
        (unsigned int)sectionVa,
        (unsigned int)flags,
        (unsigned int)virtualAddress,
        (unsigned int)virtualSize,
        (unsigned int)fileAddress,
        (unsigned int)fileSize,
        (unsigned int)oldRefCount,
        (unsigned int)newRefCount,
        (unsigned int)headRefVa,
        (unsigned int)tailRefVa,
        (unsigned int)s_phase5ahXeLoadSectionCallCount,
        (unsigned int)g_esp);
    trace(line);
}


static void phase5ah_xe_unload_section(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t sectionVa;
    uint32_t sectionCount;
    uint32_t sectionTableVa;
    uint32_t tableBytes;
    uint32_t delta;
    uint32_t index;
    uint32_t flags;
    uint32_t virtualAddress;
    uint32_t virtualSize;
    uint32_t fileAddress;
    uint32_t fileSize;
    uint32_t nameVa;
    uint32_t oldRefCount;
    uint32_t newRefCount;
    uint32_t headRefVa;
    uint32_t tailRefVa;
    uint32_t headRefCount = 0u;
    uint32_t tailRefCount = 0u;
    char sectionName[64];
    char line[896];

    if (savedEsp != callEsp + 8u)
    {
        sprintf(
            line,
            "XeUnloadSection FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=8",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000148u, savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    sectionVa = GUEST_READ32(callEsp + 4u);
    sectionCount = GUEST_READ32(0x0001011Cu);
    sectionTableVa = GUEST_READ32(0x00010120u);

    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, 0x80000148u, savedEsp);
        return;
    }

    sprintf(
        line,
        "XeUnloadSection LIVE FRAME: ret=%08X section=%08X section_table=%08X section_count=%u esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)sectionVa,
        (unsigned int)sectionTableVa,
        (unsigned int)sectionCount,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u || sectionVa == 0u ||
        sectionCount == 0u || sectionCount > 64u || sectionTableVa == 0u)
    {
        trace("XEUNLOADSECTION UNSUPPORTED: invalid call/header contract");
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000148u, savedEsp);
        return;
    }

    tableBytes = sectionCount * 0x38u;
    if (sectionVa < sectionTableVa || sectionVa >= sectionTableVa + tableBytes)
    {
        trace("XEUNLOADSECTION UNSUPPORTED: section pointer is outside the XBE section table");
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000148u, savedEsp);
        return;
    }

    delta = sectionVa - sectionTableVa;
    if ((delta % 0x38u) != 0u)
    {
        trace("XEUNLOADSECTION UNSUPPORTED: section pointer is not aligned to an XBE section header");
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000148u, savedEsp);
        return;
    }

    index = delta / 0x38u;
    if (index >= sectionCount)
    {
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000148u, savedEsp);
        return;
    }

    flags = GUEST_READ32(sectionVa + 0x00u);
    virtualAddress = GUEST_READ32(sectionVa + 0x04u);
    virtualSize = GUEST_READ32(sectionVa + 0x08u);
    fileAddress = GUEST_READ32(sectionVa + 0x0Cu);
    fileSize = GUEST_READ32(sectionVa + 0x10u);
    nameVa = GUEST_READ32(sectionVa + 0x14u);
    oldRefCount = GUEST_READ32(sectionVa + 0x18u);
    headRefVa = GUEST_READ32(sectionVa + 0x1Cu);
    tailRefVa = GUEST_READ32(sectionVa + 0x20u);

    if (s_accessFault ||
        virtualAddress < 0x00010000u ||
        virtualAddress >= RAM_SIZE ||
        virtualSize > RAM_SIZE - virtualAddress ||
        fileSize > virtualSize)
    {
        trace("XEUNLOADSECTION UNSUPPORTED: malformed XBE section metadata");
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000148u, savedEsp);
        return;
    }

    if (!phase5ah_copy_guest_cstr(nameVa, sectionName, sizeof(sectionName)))
    {
        trace("XEUNLOADSECTION UNSUPPORTED: section name is unreadable");
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000148u, savedEsp);
        return;
    }

    if ((oldRefCount & 0x80000000u) != 0u || oldRefCount == 0u)
    {
        trace("XEUNLOADSECTION UNSUPPORTED: section reference count is not positive");
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000148u, savedEsp);
        return;
    }

    newRefCount = oldRefCount - 1u;

    if (oldRefCount == 1u)
    {
        if (headRefVa != 0u)
        {
            headRefCount = (uint32_t)GUEST_READ16(headRefVa);
            if (s_accessFault || headRefCount == 0u)
            {
                trace("XEUNLOADSECTION UNSUPPORTED: shared head-page reference count underflow");
                phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000148u, savedEsp);
                return;
            }
        }

        if (tailRefVa != 0u && tailRefVa != headRefVa)
        {
            tailRefCount = (uint32_t)GUEST_READ16(tailRefVa);
            if (s_accessFault || tailRefCount == 0u)
            {
                trace("XEUNLOADSECTION UNSUPPORTED: shared tail-page reference count underflow");
                phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000148u, savedEsp);
                return;
            }
        }

        if (headRefVa != 0u)
            GUEST_WRITE16(headRefVa, (uint16_t)(headRefCount - 1u));
        if (tailRefVa != 0u && tailRefVa != headRefVa)
            GUEST_WRITE16(tailRefVa, (uint16_t)(tailRefCount - 1u));
    }

    GUEST_WRITE32(sectionVa + 0x18u, newRefCount);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, sectionVa + 0x18u, savedEsp);
        return;
    }

    ++s_phase5ahXeUnloadSectionCallCount;
    ++s_phase5ahXeUnloadSectionSuccessCount;
    s_phase5ahXeUnloadSectionLastSectionVa = sectionVa;
    s_phase5ahXeUnloadSectionLastIndex = index;
    s_phase5ahXeUnloadSectionLastRefCount = newRefCount;

    g_eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5BB XeUnloadSection native bookkeeping continuation index=%u name=%s section=%08X flags=%08X va=%08X vsize=%u file=%08X fsize=%u refs=%u->%u head_ref=%08X tail_ref=%08X calls=%u resident_bytes=1 new_esp=%08X",
        (unsigned int)index,
        sectionName,
        (unsigned int)sectionVa,
        (unsigned int)flags,
        (unsigned int)virtualAddress,
        (unsigned int)virtualSize,
        (unsigned int)fileAddress,
        (unsigned int)fileSize,
        (unsigned int)oldRefCount,
        (unsigned int)newRefCount,
        (unsigned int)headRefVa,
        (unsigned int)tailRefVa,
        (unsigned int)s_phase5ahXeUnloadSectionCallCount,
        (unsigned int)g_esp);
    trace(line);
}



static int phase5bb_partition0_backing_load(void)
{
    HANDLE file;
    DWORD bytesRead = 0u;
    DWORD error = ERROR_SUCCESS;
    char line[512];

    memset(s_phase5bbPartition0Config, 0, sizeof(s_phase5bbPartition0Config));
    s_phase5bbPartition0BackingLoaded = 0u;
    s_phase5bbPartition0BackingLoadBytes = 0u;
    s_phase5bbPartition0BackingReady = 0u;

    SetLastError(ERROR_SUCCESS);
    if (!CreateDirectoryA("game:\\merc360-partition0", NULL))
    {
        error = GetLastError();
        if (error != ERROR_ALREADY_EXISTS)
        {
            sprintf(
                line,
                "PARTITION0 BACKING FAIL: CreateDirectory path=game:\\merc360-partition0 error=%u",
                (unsigned int)error);
            trace(line);
            return 0;
        }
    }

    SetLastError(ERROR_SUCCESS);
    file = CreateFileA(
        s_phase5bbPartition0BackingPath,
        GENERIC_READ,
        FILE_SHARE_READ,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    if (file == INVALID_HANDLE_VALUE)
    {
        error = GetLastError();
        if (error != ERROR_FILE_NOT_FOUND && error != ERROR_PATH_NOT_FOUND)
        {
            sprintf(
                line,
                "PARTITION0 BACKING FAIL: open-read path=%s error=%u",
                s_phase5bbPartition0BackingPath,
                (unsigned int)error);
            trace(line);
            return 0;
        }

        s_phase5bbPartition0BackingReady = 1u;
        sprintf(
            line,
            "PASS: Phase 5BB Partition0 backing NEW path=%s size=%u",
            s_phase5bbPartition0BackingPath,
            (unsigned int)PHASE5AQ_PARTITION0_CONFIG_SIZE);
        trace(line);
        return 1;
    }

    if (!ReadFile(
            file,
            s_phase5bbPartition0Config,
            PHASE5AQ_PARTITION0_CONFIG_SIZE,
            &bytesRead,
            NULL))
    {
        error = GetLastError();
        CloseHandle(file);
        sprintf(
            line,
            "PARTITION0 BACKING FAIL: read path=%s error=%u",
            s_phase5bbPartition0BackingPath,
            (unsigned int)error);
        trace(line);
        return 0;
    }

    CloseHandle(file);

    if (bytesRead < PHASE5AQ_PARTITION0_CONFIG_SIZE)
    {
        memset(
            s_phase5bbPartition0Config + bytesRead,
            0,
            PHASE5AQ_PARTITION0_CONFIG_SIZE - bytesRead);
    }

    s_phase5bbPartition0BackingLoaded = 1u;
    s_phase5bbPartition0BackingLoadBytes = bytesRead;
    s_phase5bbPartition0BackingReady = 1u;

    sprintf(
        line,
        "PASS: Phase 5BB Partition0 backing LOADED path=%s bytes=%u padded=%u",
        s_phase5bbPartition0BackingPath,
        (unsigned int)bytesRead,
        (unsigned int)(PHASE5AQ_PARTITION0_CONFIG_SIZE - bytesRead));
    trace(line);
    return 1;
}

static int phase5bb_partition0_backing_flush(void)
{
    HANDLE file;
    DWORD bytesWritten = 0u;
    DWORD error = ERROR_SUCCESS;
    char line[512];

    SetLastError(ERROR_SUCCESS);
    file = CreateFileA(
        s_phase5bbPartition0BackingPath,
        GENERIC_WRITE,
        0u,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    if (file == INVALID_HANDLE_VALUE)
    {
        error = GetLastError();
        sprintf(
            line,
            "PARTITION0 BACKING FAIL: open-write path=%s error=%u",
            s_phase5bbPartition0BackingPath,
            (unsigned int)error);
        trace(line);
        return 0;
    }

    if (!WriteFile(
            file,
            s_phase5bbPartition0Config,
            PHASE5AQ_PARTITION0_CONFIG_SIZE,
            &bytesWritten,
            NULL) ||
        bytesWritten != PHASE5AQ_PARTITION0_CONFIG_SIZE)
    {
        error = GetLastError();
        CloseHandle(file);
        sprintf(
            line,
            "PARTITION0 BACKING FAIL: write path=%s bytes=%u expected=%u error=%u",
            s_phase5bbPartition0BackingPath,
            (unsigned int)bytesWritten,
            (unsigned int)PHASE5AQ_PARTITION0_CONFIG_SIZE,
            (unsigned int)error);
        trace(line);
        return 0;
    }

    CloseHandle(file);
    ++s_phase5bbPartition0BackingFlushCount;
    s_phase5bbPartition0BackingFlushBytes += bytesWritten;
    s_phase5bbPartition0BackingReady = 1u;

    sprintf(
        line,
        "PASS: Phase 5BB Partition0 backing FLUSHED path=%s bytes=%u flushes=%u total_bytes=%u",
        s_phase5bbPartition0BackingPath,
        (unsigned int)bytesWritten,
        (unsigned int)s_phase5bbPartition0BackingFlushCount,
        (unsigned int)s_phase5bbPartition0BackingFlushBytes);
    trace(line);
    return 1;
}

static int phase5bb_is_cache_native_path(const char* nativePath)
{
    return nativePath != NULL &&
        (phase5d_string_equal_ci(nativePath, "game:\\merc360-partition3") ||
         phase5d_string_equal_ci(nativePath, "game:\\merc360-partition4") ||
         phase5d_string_equal_ci(nativePath, "game:\\merc360-partition5"));
}

static void phase5bb_nt_device_io_control_file(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    const uint32_t cacheSize = 0x000FF000u;
    const uint32_t bytesPerSector = 512u;
    const uint32_t ioctlGeometry = 0x00070000u;
    const uint32_t ioctlPartitionInfo = 0x00074004u;
    uint32_t frameBytes;
    uint32_t argBase;
    uint32_t candidateOffset;
    uint32_t candidateCount = 0u;
    uint32_t candidateBase = 0u;
    uint32_t returnSlot;
    uint32_t handleToken;
    uint32_t eventToken;
    uint32_t apcRoutine;
    uint32_t apcContext;
    uint32_t ioStatusVa;
    uint32_t controlCode;
    uint32_t inputBufferVa;
    uint32_t inputLength;
    uint32_t outputBufferVa;
    uint32_t outputLength;
    uint32_t status = 0u;
    uint32_t information = 0u;
    uint32_t raw[13];
    uint32_t rawCount = 0u;
    uint32_t i;
    HANDLE nativeHandle;
    const char* handlePath;
    char line[1024];

    frameBytes = savedEsp - callEsp;
    if (frameBytes != 44u && frameBytes != 52u)
    {
        sprintf(
            line,
            "NtDeviceIoControlFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=44-or-52",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)frameBytes);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000C4u,
            savedEsp);
        return;
    }

    rawCount = frameBytes / 4u;
    for (i = 0u; i < rawCount; ++i)
        raw[i] = GUEST_READ32(callEsp + i * 4u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000C4u,
            savedEsp);
        return;
    }

    if (frameBytes == 52u)
    {
        sprintf(
            line,
            "NtDeviceIoControlFile FRAME52 RAW0: d0=%08X d1=%08X d2=%08X d3=%08X d4=%08X d5=%08X d6=%08X",
            (unsigned int)raw[0],
            (unsigned int)raw[1],
            (unsigned int)raw[2],
            (unsigned int)raw[3],
            (unsigned int)raw[4],
            (unsigned int)raw[5],
            (unsigned int)raw[6]);
        trace(line);
        sprintf(
            line,
            "NtDeviceIoControlFile FRAME52 RAW1: d7=%08X d8=%08X d9=%08X d10=%08X d11=%08X d12=%08X",
            (unsigned int)raw[7],
            (unsigned int)raw[8],
            (unsigned int)raw[9],
            (unsigned int)raw[10],
            (unsigned int)raw[11],
            (unsigned int)raw[12]);
        trace(line);

        /*
         * Hardware P5AO-A observed eight caller-owned bytes around the
         * canonical 44-byte NtDeviceIoControlFile frame. Do not guess which
         * side owns them: locate the one 44-byte window whose return slot,
         * tracked cache handle and known cache IOCTL are simultaneously valid.
         */
        for (candidateOffset = 0u; candidateOffset <= 8u; candidateOffset += 4u)
        {
            uint32_t candidateReturn =
                GUEST_READ32(callEsp + candidateOffset + 0u);
            uint32_t candidateHandle =
                GUEST_READ32(callEsp + candidateOffset + 4u);
            uint32_t candidateIoStatus =
                GUEST_READ32(callEsp + candidateOffset + 20u);
            uint32_t candidateCode =
                GUEST_READ32(callEsp + candidateOffset + 24u);
            const char* candidatePath =
                phase5b_read_handle_path(candidateHandle);

            if (!s_accessFault &&
                candidateReturn == 0u &&
                candidateIoStatus != 0u &&
                phase5bb_is_cache_native_path(candidatePath) &&
                (candidateCode == ioctlGeometry ||
                 candidateCode == ioctlPartitionInfo))
            {
                ++candidateCount;
                candidateBase = callEsp + candidateOffset;
            }
        }

        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x800000C4u,
                savedEsp);
            return;
        }

        if (candidateCount != 1u)
        {
            sprintf(
                line,
                "NtDeviceIoControlFile FRAME52 AMBIGUOUS: candidates=%u esp=%08X saved_esp=%08X",
                (unsigned int)candidateCount,
                (unsigned int)callEsp,
                (unsigned int)savedEsp);
            trace(line);
            phase4c_escape(
                PHASE4C_BOUNDARY_KERNEL_FRAME,
                0x800000C4u,
                savedEsp);
            return;
        }

        argBase = candidateBase;
    }
    else
    {
        argBase = callEsp;
    }

    returnSlot = GUEST_READ32(argBase + 0u);
    handleToken = GUEST_READ32(argBase + 4u);
    eventToken = GUEST_READ32(argBase + 8u);
    apcRoutine = GUEST_READ32(argBase + 12u);
    apcContext = GUEST_READ32(argBase + 16u);
    ioStatusVa = GUEST_READ32(argBase + 20u);
    controlCode = GUEST_READ32(argBase + 24u);
    inputBufferVa = GUEST_READ32(argBase + 28u);
    inputLength = GUEST_READ32(argBase + 32u);
    outputBufferVa = GUEST_READ32(argBase + 36u);
    outputLength = GUEST_READ32(argBase + 40u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000C4u,
            savedEsp);
        return;
    }

    ++s_phase5bbNtDeviceIoControlCallCount;
    s_phase5bbNtDeviceIoControlLastCode = controlCode;

    sprintf(
        line,
        "NtDeviceIoControlFile LIVE FRAME: frame=%u arg_offset=%u ret=%08X handle=%08X event=%08X apc=%08X context=%08X iosb=%08X code=%08X input=%08X input_len=%u output=%08X output_len=%u esp=%08X saved_esp=%08X",
        (unsigned int)frameBytes,
        (unsigned int)(argBase - callEsp),
        (unsigned int)returnSlot,
        (unsigned int)handleToken,
        (unsigned int)eventToken,
        (unsigned int)apcRoutine,
        (unsigned int)apcContext,
        (unsigned int)ioStatusVa,
        (unsigned int)controlCode,
        (unsigned int)inputBufferVa,
        (unsigned int)inputLength,
        (unsigned int)outputBufferVa,
        (unsigned int)outputLength,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u || ioStatusVa == 0u)
    {
        trace("KERNEL FRAME MISMATCH: ordinal 196 invalid return/iosb field");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000C4u,
            savedEsp);
        return;
    }

    if (eventToken != 0u || apcRoutine != 0u || apcContext != 0u)
    {
        trace("STORAGE IO UNSUPPORTED: asynchronous NtDeviceIoControlFile event/APC form");
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_IO,
            0x800000C4u,
            savedEsp);
        return;
    }

    nativeHandle = phase5c_read_native_handle(handleToken);
    handlePath = phase5b_read_handle_path(handleToken);

    if (!nativeHandle)
    {
        status = 0xC0000008u; /* STATUS_INVALID_HANDLE */
    }
    else if (!phase5bb_is_cache_native_path(handlePath))
    {
        sprintf(
            line,
            "STORAGE IO UNSUPPORTED: NtDeviceIoControlFile non-cache handle token=%08X path=%s code=%08X",
            (unsigned int)handleToken,
            handlePath ? handlePath : "<unknown>",
            (unsigned int)controlCode);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_IO,
            0x800000C4u,
            savedEsp);
        return;
    }
    else if (controlCode == ioctlGeometry)
    {
        if (outputBufferVa == 0u || outputLength < 8u)
        {
            status = 0xC0000023u; /* STATUS_BUFFER_TOO_SMALL */
        }
        else
        {
            GUEST_WRITE32(outputBufferVa + 0u, cacheSize / bytesPerSector);
            GUEST_WRITE32(outputBufferVa + 4u, bytesPerSector);
            information = 8u;
            ++s_phase5bbNtDeviceIoControlGeometryCount;
        }
    }
    else if (controlCode == ioctlPartitionInfo)
    {
        if (outputBufferVa == 0u || outputLength < 16u)
        {
            status = 0xC0000023u; /* STATUS_BUFFER_TOO_SMALL */
        }
        else
        {
            GUEST_WRITE32(outputBufferVa + 0u, 0u);
            GUEST_WRITE32(outputBufferVa + 4u, 0u);
            GUEST_WRITE32(outputBufferVa + 8u, cacheSize);
            GUEST_WRITE32(outputBufferVa + 12u, 0u);
            information = 16u;
            ++s_phase5bbNtDeviceIoControlPartitionInfoCount;
        }
    }
    else
    {
        ++s_phase5bbNtDeviceIoControlUnknownCount;
        sprintf(
            line,
            "STORAGE IO UNSUPPORTED: NtDeviceIoControlFile unknown code=%08X path=%s input=%08X/%u output=%08X/%u calls=%u",
            (unsigned int)controlCode,
            handlePath ? handlePath : "<unknown>",
            (unsigned int)inputBufferVa,
            (unsigned int)inputLength,
            (unsigned int)outputBufferVa,
            (unsigned int)outputLength,
            (unsigned int)s_phase5bbNtDeviceIoControlCallCount);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_IO,
            0x800000C4u,
            savedEsp);
        return;
    }

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            outputBufferVa,
            savedEsp);
        return;
    }

    GUEST_WRITE32(ioStatusVa + 0u, status);
    GUEST_WRITE32(ioStatusVa + 4u, information);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            ioStatusVa,
            savedEsp);
        return;
    }

    s_phase5bbNtDeviceIoControlLastStatus = status;
    if (status == 0u)
        ++s_phase5bbNtDeviceIoControlSuccessCount;

    g_eax = status;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 5BB NtDeviceIoControlFile cache continuation path=%s frame=%u arg_offset=%u code=%08X status=%08X information=%u calls=%u successes=%u geometry=%u partition_info=%u new_esp=%08X",
        handlePath ? handlePath : "<unknown>",
        (unsigned int)frameBytes,
        (unsigned int)(argBase - callEsp),
        (unsigned int)controlCode,
        (unsigned int)status,
        (unsigned int)information,
        (unsigned int)s_phase5bbNtDeviceIoControlCallCount,
        (unsigned int)s_phase5bbNtDeviceIoControlSuccessCount,
        (unsigned int)s_phase5bbNtDeviceIoControlGeometryCount,
        (unsigned int)s_phase5bbNtDeviceIoControlPartitionInfoCount,
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

    if ((rootDirectory != 0u && rootDirectory != 0xFFFFFFFDu) ||
        pathVa == 0u || pathLength == 0u ||
        pathLength > 255u)
    {
        sprintf(
            line,
            "STORAGE UNSUPPORTED: NtOpenFile unsupported-root/invalid path root=%08X path_va=%08X len=%u",
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

    if (rootDirectory == 0xFFFFFFFDu)
    {
        ++s_phase5bbNtOpenFileObDosDevicesCount;
        sprintf(
            line,
            "NtOpenFile OBDOSDEVICES: root=FFFFFFFD path=%s calls=%u",
            path,
            (unsigned int)s_phase5bbNtOpenFileObDosDevicesCount);
        trace(line);
    }

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

    if (rootDirectory == 0xFFFFFFFDu)
    {
        ++s_phase5bbNtOpenFileObDosDevicesMappedCount;
        sprintf(
            line,
            "PASS: Phase 5BB NtOpenFile ObDosDevices path expansion xbox=%s native=%s mappings=%u",
            path,
            nativePath,
            (unsigned int)s_phase5bbNtOpenFileObDosDevicesMappedCount);
        trace(line);
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
            (virtualRoot || (options & 0x00000001u)) ?
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
            else
            {
                phase5b_set_handle_path(token, nativePath);
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
        if (phase5d_string_equal_ci(path, "\\Device\\Harddisk0\\partition3") ||
            phase5b_prefix_equal_ci(path, "\\Device\\Harddisk0\\partition3\\", NULL) ||
            phase5d_string_equal_ci(path, "\\Device\\Harddisk0\\partition4") ||
            phase5b_prefix_equal_ci(path, "\\Device\\Harddisk0\\partition4\\", NULL) ||
            phase5d_string_equal_ci(path, "\\Device\\Harddisk0\\partition5") ||
            phase5b_prefix_equal_ci(path, "\\Device\\Harddisk0\\partition5\\", NULL))
        {
            ++s_phase5bbCacheRootOpenCount;
            sprintf(
                line,
                "PASS: Phase 5BB cache partition native open xbox=%s native=%s opens=%u",
                path,
                nativePath,
                (unsigned int)s_phase5bbCacheRootOpenCount);
            trace(line);
        }
        if (phase5d_string_equal_ci(
                path, "\\Device\\Harddisk0\\partition0"))
        {
            ++s_phase5ahPartition0OpenSuccessCount;
            sprintf(
                line,
                "PASS: Phase 5BB Partition0 root NtOpenFile native continuation token=%08X native=%s opens=%u new_esp=%08X",
                (unsigned int)token,
                nativePath,
                (unsigned int)s_phase5ahPartition0OpenSuccessCount,
                (unsigned int)g_esp);
            trace(line);
        }
        sprintf(
            line,
            "PASS: Phase 5BB NtOpenFile native continuation status=%08X token=%08X calls=%u new_esp=%08X",
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
            "FAIL: Phase 5BB NtOpenFile native open failed status=%08X error=%u path=%s",
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
    ++s_phase5bbNvQueryCount;
    s_phase4cNvQueryIndex = valueIndex;
    s_phase4cNvQueryValueVa = valueVa;
    s_phase4cNvQueryValueLength = valueLength;

    sprintf(
        line,
        "PASS: Phase 5BB ordinal 24 ExQueryNonVolatileSetting repeatable guest EEPROM semantics status=%08X calls=%u new_esp=%08X",
        (unsigned int)g_eax,
        (unsigned int)s_phase5bbNvQueryCount,
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

    /* Match src/kernel/kernel_rtl.c xbox_RtlNtStatusToDosError. */
    switch (status)
    {
    case 0x00000000u: dosError = 0u; break;    /* ERROR_SUCCESS */
    case 0xC000000Du: dosError = 87u; break;   /* ERROR_INVALID_PARAMETER */
    case 0xC0000017u: dosError = 8u; break;    /* ERROR_NOT_ENOUGH_MEMORY */
    case 0xC000009Au: dosError = 1450u; break; /* ERROR_NO_SYSTEM_RESOURCES */
    case 0xC0000022u: dosError = 5u; break;    /* ERROR_ACCESS_DENIED */
    case 0xC0000034u: dosError = 2u; break;    /* ERROR_FILE_NOT_FOUND */
    case 0xC000003Au: dosError = 3u; break;    /* ERROR_PATH_NOT_FOUND */
    case 0xC0000035u: dosError = 183u; break;  /* ERROR_ALREADY_EXISTS */
    case 0xC000000Fu: dosError = 2u; break;    /* ERROR_FILE_NOT_FOUND */
    case 0xC0000011u: dosError = 38u; break;   /* ERROR_HANDLE_EOF */
    case 0xC0000008u: dosError = 6u; break;    /* ERROR_INVALID_HANDLE */
    case 0xC0000002u: dosError = 120u; break;  /* ERROR_CALL_NOT_IMPLEMENTED */
    case 0xC0000001u: dosError = 31u; break;   /* ERROR_GEN_FAILURE */
    case 0x00000103u: dosError = 997u; break;  /* ERROR_IO_PENDING */
    case 0x80000005u: dosError = 234u; break;  /* ERROR_MORE_DATA */
    case 0x80000006u: dosError = 18u; break;   /* ERROR_NO_MORE_FILES */
    case 0xC00000BBu: dosError = 50u; break;   /* ERROR_NOT_SUPPORTED */
    case 0xC0000120u: dosError = 1223u; break; /* ERROR_CANCELLED */
    case 0xC0000021u: dosError = 1455u; break; /* ERROR_COMMITMENT_LIMIT */
    default:          dosError = 317u; break;   /* ERROR_MR_MID_NOT_FOUND */
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
    ++s_phase5ahNtStatusMapCount;

    sprintf(
        line,
        "PASS: Phase 5BB ordinal 301 RtlNtStatusToDosError repeatable mapping status=%08X dos_error=%u calls=%u new_esp=%08X",
        (unsigned int)status,
        (unsigned int)dosError,
        (unsigned int)s_phase5ahNtStatusMapCount,
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
        trace("FAIL: live StartRoutine is absent from the Phase 5BB pack");
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


/* Phase 5BB guest-safe memory-manager cluster. */
static int phase5bb_find_reservation(uint32_t base)
{
    uint32_t i;
    for (i = 0u; i < s_phase4cVmReservationCount; ++i)
        if (s_phase4cVmReservations[i].inUse &&
            s_phase4cVmReservations[i].base == base)
            return (int)i;
    return -1;
}

static uint32_t phase5bb_alloc_guest_pages(
    uint32_t requested, uint32_t alignment, uint32_t protect, uint32_t* actualSize)
{
    uint32_t size = phase4c_page_round(requested);
    uint32_t base, firstPage, lastPage, page;
    if (actualSize) *actualSize = 0u;
    if (alignment < 0x1000u || (alignment & (alignment - 1u)) != 0u)
        alignment = 0x1000u;
    if (size == 0u ||
        s_phase4cVmReservationCount >= PHASE4C_VM_RESERVATION_CAP ||
        s_phase4cVmPageNext <= PHASE4C_TITLE_HEAP_END ||
        size > s_phase4cVmPageNext - PHASE4C_TITLE_HEAP_END)
        return 0u;
    base = (s_phase4cVmPageNext - size) & ~(alignment - 1u);
    if (base < PHASE4C_TITLE_HEAP_END ||
        !phase4c_vm_page_range(base, size, &firstPage, &lastPage))
        return 0u;
    for (page = firstPage; page <= lastPage; ++page)
        if (s_phase4cVmPageState[page] != PHASE4C_VM_PAGE_UNMANAGED)
            return 0u;
    s_phase4cVmReservations[s_phase4cVmReservationCount].base = base;
    s_phase4cVmReservations[s_phase4cVmReservationCount].size = size;
    s_phase4cVmReservations[s_phase4cVmReservationCount].protect = protect;
    s_phase4cVmReservations[s_phase4cVmReservationCount].inUse = 1u;
    ++s_phase4cVmReservationCount;
    for (page = firstPage; page <= lastPage; ++page) {
        s_phase4cVmPageState[page] = PHASE4C_VM_PAGE_COMMITTED;
        s_phase4cVmPageProtect[page] = protect;
    }
    memset(g_ram + base, 0, size);
    s_phase4cVmPageNext = base;
    if (actualSize) *actualSize = size;
    return base;
}

static uint32_t phase5bb_release_guest_pages(uint32_t base)
{
    int index = phase5bb_find_reservation(base);
    uint32_t firstPage, lastPage, page, size;
    if (index < 0) return 0u;
    size = s_phase4cVmReservations[index].size;
    if (!phase4c_vm_page_range(base, size, &firstPage, &lastPage)) return 0u;
    for (page = firstPage; page <= lastPage; ++page) {
        s_phase4cVmPageState[page] = PHASE4C_VM_PAGE_UNMANAGED;
        s_phase4cVmPageProtect[page] = 0u;
    }
    memset(g_ram + base, 0, size);
    s_phase4cVmReservations[index].inUse = 0u;
    return size;
}


/*
 * Generated audio-wrapper support shims exposed by the depth-2 cache closure.
 * Preserve the retail allocator/free paths: the test hook never forces a
 * failure, the fallback runs only after the normal allocator returned NULL,
 * and free claims only pointers allocated by this fallback table.
 */
int recomp_test_audio_alloc_failure(uint32_t attributes)
{
    char line[256];
    ++s_phase5bbAudioAllocFailureTestCount;
    sprintf(
        line,
        "PASS: Phase 5BB audio alloc failure-test hook attributes=%08X calls=%u forced_failure=0",
        (unsigned int)attributes,
        (unsigned int)s_phase5bbAudioAllocFailureTestCount);
    trace(line);
    return 0;
}

uint32_t recomp_audio_pool_fallback(uint32_t size, uint32_t attributes)
{
    uint32_t i;
    uint32_t actual = 0u;
    uint32_t base = 0u;
    char line[384];

    ++s_phase5bbAudioFallbackAttemptCount;

    if (size == 0u)
    {
        trace("PASS: Phase 5BB audio fallback ignored zero-byte allocation");
        return 0u;
    }

    for (i = 0u; i < PHASE5AN_AUDIO_FALLBACK_CAP; ++i)
        if (!s_phase5bbAudioFallback[i].inUse)
            break;

    if (i >= PHASE5AN_AUDIO_FALLBACK_CAP)
    {
        trace("Phase 5BB audio fallback table exhausted");
        return 0u;
    }

    base = phase5bb_alloc_guest_pages(
        size,
        0x1000u,
        0x4u,
        &actual);
    if (base == 0u)
    {
        sprintf(
            line,
            "Phase 5BB audio fallback allocation failed size=%u attributes=%08X attempts=%u",
            (unsigned int)size,
            (unsigned int)attributes,
            (unsigned int)s_phase5bbAudioFallbackAttemptCount);
        trace(line);
        return 0u;
    }

    s_phase5bbAudioFallback[i].inUse = 1u;
    s_phase5bbAudioFallback[i].base = base;
    s_phase5bbAudioFallback[i].size = actual;
    s_phase5bbAudioFallback[i].attributes = attributes;
    ++s_phase5bbAudioFallbackSuccessCount;

    sprintf(
        line,
        "PASS: Phase 5BB audio pool fallback size=%u rounded=%u attributes=%08X base=%08X slot=%u successes=%u",
        (unsigned int)size,
        (unsigned int)actual,
        (unsigned int)attributes,
        (unsigned int)base,
        (unsigned int)i,
        (unsigned int)s_phase5bbAudioFallbackSuccessCount);
    trace(line);
    return base;
}

int recomp_audio_pool_free(uint32_t ptr)
{
    uint32_t i;
    uint32_t freed;
    char line[320];

    if (ptr == 0u)
        return 0;

    for (i = 0u; i < PHASE5AN_AUDIO_FALLBACK_CAP; ++i)
    {
        if (!s_phase5bbAudioFallback[i].inUse ||
            s_phase5bbAudioFallback[i].base != ptr)
            continue;

        freed = phase5bb_release_guest_pages(ptr);
        if (freed == 0u)
        {
            sprintf(
                line,
                "Phase 5BB audio fallback free failed ptr=%08X slot=%u",
                (unsigned int)ptr,
                (unsigned int)i);
            trace(line);
            return 0;
        }

        s_phase5bbAudioFallback[i].inUse = 0u;
        s_phase5bbAudioFallback[i].base = 0u;
        s_phase5bbAudioFallback[i].size = 0u;
        s_phase5bbAudioFallback[i].attributes = 0u;
        ++s_phase5bbAudioFallbackFreeCount;

        sprintf(
            line,
            "PASS: Phase 5BB audio pool fallback free ptr=%08X bytes=%u slot=%u frees=%u",
            (unsigned int)ptr,
            (unsigned int)freed,
            (unsigned int)i,
            (unsigned int)s_phase5bbAudioFallbackFreeCount);
        trace(line);
        return 1;
    }

    return 0;
}

/*
 * Cache preparation is deliberately prep-only. The helper is called before
 * sub_0022C5C6's guest prologue, so returning nonzero would bypass the retail
 * function without reproducing its guest epilogue. Ensure the isolated cache
 * roots exist, then return 0 so the translated retail body runs normally.
 */
int recomp_prepare_empty_cache_volume(void)
{
    static const char* roots[3] = {
        "game:\\merc360-partition3",
        "game:\\merc360-partition4",
        "game:\\merc360-partition5",
    };
    uint32_t i;
    uint32_t ready = 0u;
    char line[384];

    ++s_phase5bbCachePrepareCallCount;

    for (i = 0u; i < 3u; ++i)
    {
        SetLastError(ERROR_SUCCESS);
        if (CreateDirectoryA(roots[i], NULL))
        {
            ++ready;
            continue;
        }

        if (GetLastError() == ERROR_ALREADY_EXISTS)
        {
            ++ready;
            continue;
        }

        sprintf(
            line,
            "Phase 5BB cache prep root failure path=%s error=%u",
            roots[i],
            (unsigned int)GetLastError());
        trace(line);
    }

    s_phase5bbCachePrepareReadyCount = ready;
    sprintf(
        line,
        "PASS: Phase 5BB cache prep helper calls=%u roots_ready=%u policy=continue-retail-body",
        (unsigned int)s_phase5bbCachePrepareCallCount,
        (unsigned int)ready);
    trace(line);

    /* Do not short-circuit sub_0022C5C6; preserve its guest stack/epilogue. */
    return 0;
}

static void phase5bb_mm_allocate_contiguous(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,size,actual=0u,va; char line[384];
    if(savedEsp!=c+8u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A5u,savedEsp);
    ret=GUEST_READ32(c); size=GUEST_READ32(c+4u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000A5u,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A5u,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=165u;
    va=phase5bb_alloc_guest_pages(size,0x1000u,0x4u,&actual);
    if(va) ++s_phase5bbMmAllocSuccessCount;
    s_phase5bbMmLastBase=va; s_phase5bbMmLastSize=actual; g_eax=va; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 165 MmAllocateContiguousMemory size=%u rounded=%u base=%08X calls=%u alloc_success=%u new_esp=%08X",
            (unsigned)size,(unsigned)actual,(unsigned)va,(unsigned)s_phase5bbMmCallCount,
            (unsigned)s_phase5bbMmAllocSuccessCount,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,size,low,high,align,prot,actual=0u,va; char line[512];
    if(savedEsp!=c+24u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A6u,savedEsp);
    ret=GUEST_READ32(c); size=GUEST_READ32(c+4u); low=GUEST_READ32(c+8u);
    high=GUEST_READ32(c+12u); align=GUEST_READ32(c+16u); prot=GUEST_READ32(c+20u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000A6u,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A6u,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=166u;
    va=phase5bb_alloc_guest_pages(size,align,prot?prot:0x4u,&actual);
    if(va) ++s_phase5bbMmAllocSuccessCount;
    s_phase5bbMmLastBase=va; s_phase5bbMmLastSize=actual; g_eax=va; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 166 MmAllocateContiguousMemoryEx size=%u low=%08X high=%08X align=%u protect=%08X base=%08X rounded=%u new_esp=%08X",
            (unsigned)size,(unsigned)low,(unsigned)high,(unsigned)align,(unsigned)prot,
            (unsigned)va,(unsigned)actual,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_allocate_system(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,size,prot,actual=0u,va; char line[384];
    if(savedEsp!=c+12u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A7u,savedEsp);
    ret=GUEST_READ32(c); size=GUEST_READ32(c+4u); prot=GUEST_READ32(c+8u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000A7u,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A7u,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=167u;
    va=phase5bb_alloc_guest_pages(size,0x1000u,prot?prot:0x4u,&actual);
    if(va) ++s_phase5bbMmAllocSuccessCount;
    s_phase5bbMmLastBase=va; s_phase5bbMmLastSize=actual; g_eax=va; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 167 MmAllocateSystemMemory size=%u protect=%08X base=%08X rounded=%u new_esp=%08X",
            (unsigned)size,(unsigned)prot,(unsigned)va,(unsigned)actual,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_free_contiguous(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,base,freed; char line[320];
    if(savedEsp!=c+8u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000ABu,savedEsp);
    ret=GUEST_READ32(c); base=GUEST_READ32(c+4u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000ABu,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000ABu,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=171u;
    freed=phase5bb_release_guest_pages(base); if(freed) ++s_phase5bbMmFreeCount;
    g_eax=0u; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 171 MmFreeContiguousMemory base=%08X freed=%u frees=%u new_esp=%08X",
            (unsigned)base,(unsigned)freed,(unsigned)s_phase5bbMmFreeCount,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_free_system(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,base,requested,freed; char line[352];
    if(savedEsp!=c+12u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000ACu,savedEsp);
    ret=GUEST_READ32(c); base=GUEST_READ32(c+4u); requested=GUEST_READ32(c+8u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000ACu,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000ACu,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=172u;
    freed=phase5bb_release_guest_pages(base); if(freed) ++s_phase5bbMmFreeCount;
    g_eax=(freed+0xFFFu)>>12; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 172 MmFreeSystemMemory base=%08X requested=%u freed=%u pages=%u new_esp=%08X",
            (unsigned)base,(unsigned)requested,(unsigned)freed,(unsigned)g_eax,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_get_physical_address(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,base; char line[288];
    if(savedEsp!=c+8u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000ADu,savedEsp);
    ret=GUEST_READ32(c); base=GUEST_READ32(c+4u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000ADu,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000ADu,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=173u; g_eax=base; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 173 MmGetPhysicalAddress identity base=%08X physical=%08X new_esp=%08X",
            (unsigned)base,(unsigned)g_eax,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_lock_unlock_buffer_pages(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,base,size,unlock; char line[352];
    if(savedEsp!=c+16u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000AFu,savedEsp);
    ret=GUEST_READ32(c); base=GUEST_READ32(c+4u); size=GUEST_READ32(c+8u); unlock=GUEST_READ32(c+12u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000AFu,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000AFu,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=175u; g_eax=0u; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 175 MmLockUnlockBufferPages no-op base=%08X size=%u unlock=%u new_esp=%08X",
            (unsigned)base,(unsigned)size,(unsigned)unlock,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_query_allocation_size(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,base,size=0u; int index; char line[320];
    if(savedEsp!=c+8u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B4u,savedEsp);
    ret=GUEST_READ32(c); base=GUEST_READ32(c+4u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000B4u,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B4u,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=180u;
    index=phase5bb_find_reservation(base); if(index>=0) size=s_phase4cVmReservations[index].size;
    g_eax=size; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 180 MmQueryAllocationSize base=%08X size=%u new_esp=%08X",
            (unsigned)base,(unsigned)size,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_query_statistics(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,stats,page,committed=0u,reserved=0u,available; char line[384];
    if(savedEsp!=c+8u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B5u,savedEsp);
    ret=GUEST_READ32(c); stats=GUEST_READ32(c+4u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000B5u,savedEsp);
    if(ret!=0u || stats==0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B5u,savedEsp);
    for(page=0u;page<PHASE4C_VM_PAGE_COUNT;++page){
        if(s_phase4cVmPageState[page]==PHASE4C_VM_PAGE_COMMITTED) ++committed;
        else if(s_phase4cVmPageState[page]==PHASE4C_VM_PAGE_RESERVED) ++reserved;
    }
    available=(s_phase4cVmPageNext>PHASE4C_TITLE_HEAP_END)?
        ((s_phase4cVmPageNext-PHASE4C_TITLE_HEAP_END)>>12):0u;
    GUEST_WRITE32(stats+0u,36u); GUEST_WRITE32(stats+4u,16384u);
    GUEST_WRITE32(stats+8u,available); GUEST_WRITE32(stats+12u,committed<<12);
    GUEST_WRITE32(stats+16u,reserved<<12); GUEST_WRITE32(stats+20u,0u);
    GUEST_WRITE32(stats+24u,0u); GUEST_WRITE32(stats+28u,0u); GUEST_WRITE32(stats+32u,0u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000B5u,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=181u; g_eax=0u; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 181 MmQueryStatistics total_pages=16384 available=%u committed=%u reserved=%u new_esp=%08X",
            (unsigned)available,(unsigned)committed,(unsigned)reserved,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_set_address_protect(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,base,size,prot,first,last,page; char line[384];
    if(savedEsp!=c+16u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B6u,savedEsp);
    ret=GUEST_READ32(c); base=GUEST_READ32(c+4u); size=GUEST_READ32(c+8u); prot=GUEST_READ32(c+12u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000B6u,savedEsp);
    if(ret!=0u || !phase4c_vm_page_range(base,size,&first,&last))
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B6u,savedEsp);
    for(page=first;page<=last;++page)
        if(s_phase4cVmPageState[page]!=PHASE4C_VM_PAGE_RESERVED)
            s_phase4cVmPageProtect[page]=prot;
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=182u; g_eax=0u; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 182 MmSetAddressProtect base=%08X size=%u protect=%08X pages=%u new_esp=%08X",
            (unsigned)base,(unsigned)size,(unsigned)prot,(unsigned)(last-first+1u),(unsigned)g_esp); trace(line);
}


static void phase5bb_mm_lock_unlock_physical_page(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,physical,unlock; char line[352];
    if(savedEsp!=c+12u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B0u,savedEsp);
    ret=GUEST_READ32(c); physical=GUEST_READ32(c+4u); unlock=GUEST_READ32(c+8u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000B0u,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B0u,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=176u; g_eax=0u; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 176 MmLockUnlockPhysicalPage no-op physical=%08X unlock=%u new_esp=%08X",
            (unsigned)physical,(unsigned)unlock,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_map_io_space(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,physical,size,prot,actual=0u,va; char line[448];
    if(savedEsp!=c+16u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B1u,savedEsp);
    ret=GUEST_READ32(c); physical=GUEST_READ32(c+4u); size=GUEST_READ32(c+8u); prot=GUEST_READ32(c+12u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000B1u,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B1u,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=177u;
    va=phase5bb_alloc_guest_pages(size,0x1000u,prot?prot:0x4u,&actual);
    if(va) { ++s_phase5bbMmAllocSuccessCount; ++s_phase5bbMmIoMapCount; }
    s_phase5bbMmLastBase=va; s_phase5bbMmLastSize=actual; g_eax=va; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 177 MmMapIoSpace dummy mapping physical=%08X size=%u protect=%08X base=%08X rounded=%u maps=%u new_esp=%08X",
            (unsigned)physical,(unsigned)size,(unsigned)prot,(unsigned)va,(unsigned)actual,
            (unsigned)s_phase5bbMmIoMapCount,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_persist_contiguous(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,base,size,persist; char line[384];
    if(savedEsp!=c+16u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B2u,savedEsp);
    ret=GUEST_READ32(c); base=GUEST_READ32(c+4u); size=GUEST_READ32(c+8u); persist=GUEST_READ32(c+12u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000B2u,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B2u,savedEsp);
    ++s_phase5bbMmCallCount; ++s_phase5bbMmPersistCount; s_phase5bbMmLastOrdinal=178u;
    s_phase5bbMmLastBase=base; s_phase5bbMmLastSize=size; g_eax=0u; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 178 MmPersistContiguousMemory production no-op base=%08X size=%u persist=%u calls=%u new_esp=%08X",
            (unsigned)base,(unsigned)size,(unsigned)persist,(unsigned)s_phase5bbMmPersistCount,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_query_address_protect(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,base,page,prot=1u; char line[352];
    if(savedEsp!=c+8u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B3u,savedEsp);
    ret=GUEST_READ32(c); base=GUEST_READ32(c+4u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000B3u,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B3u,savedEsp);
    if(base<RAM_SIZE) {
        page=base>>PHASE4C_VM_PAGE_SHIFT;
        if(s_phase4cVmPageState[page]==PHASE4C_VM_PAGE_RESERVED) prot=1u;
        else if(s_phase4cVmPageState[page]==PHASE4C_VM_PAGE_COMMITTED)
            prot=s_phase4cVmPageProtect[page]?s_phase4cVmPageProtect[page]:4u;
        else prot=4u;
    }
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=179u; g_eax=prot; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 179 MmQueryAddressProtect base=%08X protect=%08X new_esp=%08X",
            (unsigned)base,(unsigned)prot,(unsigned)g_esp); trace(line);
}

static void phase5bb_mm_unmap_io_space(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,base,size,freed; char line[384];
    if(savedEsp!=c+12u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B7u,savedEsp);
    ret=GUEST_READ32(c); base=GUEST_READ32(c+4u); size=GUEST_READ32(c+8u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000B7u,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000B7u,savedEsp);
    ++s_phase5bbMmCallCount; s_phase5bbMmLastOrdinal=183u;
    freed=phase5bb_release_guest_pages(base); if(freed) { ++s_phase5bbMmFreeCount; ++s_phase5bbMmIoUnmapCount; }
    g_eax=0u; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 183 MmUnmapIoSpace base=%08X requested=%u freed=%u unmaps=%u new_esp=%08X",
            (unsigned)base,(unsigned)size,(unsigned)freed,(unsigned)s_phase5bbMmIoUnmapCount,(unsigned)g_esp); trace(line);
}

static void phase5bb_nt_free_virtual_memory(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,basePtr,sizePtr,freeType,base=0u,size=0u,status=0xC000000Du;
    uint32_t first=0u,last=0u,page,freed=0u; char line[512];
    if(savedEsp!=c+16u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000C7u,savedEsp);
    ret=GUEST_READ32(c); basePtr=GUEST_READ32(c+4u); sizePtr=GUEST_READ32(c+8u); freeType=GUEST_READ32(c+12u);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000C7u,savedEsp);
    if(ret!=0u) phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000C7u,savedEsp);
    if(basePtr) base=GUEST_READ32(basePtr);
    if(sizePtr) size=GUEST_READ32(sizePtr);
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000C7u,savedEsp);
    ++s_phase5bbNtFreeVirtualCount;
    if(basePtr && base) {
        if((freeType & 0x00008000u)!=0u) {
            freed=phase5bb_release_guest_pages(base);
            if(freed) {
                GUEST_WRITE32(basePtr,0u);
                if(sizePtr) GUEST_WRITE32(sizePtr,0u);
                status=0u;
            }
        } else if((freeType & 0x00004000u)!=0u && size!=0u &&
                  phase4c_vm_range_reserved(base,size) &&
                  phase4c_vm_page_range(base,size,&first,&last)) {
            for(page=first;page<=last;++page) {
                memset(g_ram + page*PHASE4C_VM_PAGE_SIZE,0,PHASE4C_VM_PAGE_SIZE);
                s_phase4cVmPageState[page]=PHASE4C_VM_PAGE_RESERVED;
                s_phase4cVmPageProtect[page]=0u;
            }
            status=0u;
        }
    }
    if(s_accessFault) phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000C7u,savedEsp);
    if(status==0u) ++s_phase5bbNtFreeVirtualSuccessCount;
    g_eax=status; g_esp=savedEsp;
    sprintf(line,"PASS: Phase 5BB ordinal 199 NtFreeVirtualMemory status=%08X base_ptr=%08X base=%08X size=%u type=%08X freed=%u calls=%u successes=%u new_esp=%08X",
            (unsigned)status,(unsigned)basePtr,(unsigned)base,(unsigned)size,(unsigned)freeType,
            (unsigned)freed,(unsigned)s_phase5bbNtFreeVirtualCount,(unsigned)s_phase5bbNtFreeVirtualSuccessCount,
            (unsigned)g_esp); trace(line);
}


static void phase5bb_hal_return_to_firmware_trap(uint32_t savedEsp)
{
    uint32_t c = g_esp;
    uint32_t ret;
    uint32_t routine;
    uint32_t launchPage = 0u;
    uint32_t launchType = 0u;
    uint32_t titleId = 0u;
    uint32_t flags = 0u;
    uint32_t i;
    char path[193];
    char line[640];

    if (savedEsp != c + 8u)
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x80000031u,savedEsp);

    ret = GUEST_READ32(c + 0u);
    routine = GUEST_READ32(c + 4u);
    launchPage = GUEST_READ32(0x0087E030u);
    if (s_accessFault)
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x80000031u,savedEsp);
    if (ret != 0u)
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x80000031u,savedEsp);

    path[0] = '\0';
    if (launchPage != 0u && launchPage <= RAM_SIZE - 0x1000u)
    {
        launchType = GUEST_READ32(launchPage + 0u);
        titleId = GUEST_READ32(launchPage + 4u);
        for (i = 0u; i < sizeof(path) - 1u; ++i)
        {
            uint8_t ch = GUEST_READ8(launchPage + 8u + i);
            if (s_accessFault)
                phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x80000031u,savedEsp);
            if (ch == 0u) break;
            path[i] = (ch >= 32u && ch <= 126u) ? (char)ch : '.';
        }
        path[i] = '\0';
        flags = GUEST_READ32(launchPage + 528u);
        if (s_accessFault)
            phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x80000031u,savedEsp);
    }

    ++s_phase5bbHalReturnTrapCount;
    s_phase5bbHalReturnRoutine = routine;
    s_phase5bbHalReturnLaunchPage = launchPage;

    sprintf(
        line,
        "HAL RETURN TRAP: ordinal=49 routine=%u launch_page=%08X launch_type=%08X title_id=%08X flags=%08X path=%s traps=%u",
        (unsigned int)routine,
        (unsigned int)launchPage,
        (unsigned int)launchType,
        (unsigned int)titleId,
        (unsigned int)flags,
        path[0] ? path : "<empty>",
        (unsigned int)s_phase5bbHalReturnTrapCount);
    trace(line);
    trace("HAL RETURN TRAP: non-returning firmware action intentionally not executed by diagnostic harness");

    phase4c_escape(
        PHASE4C_BOUNDARY_ICALL_SAFE,
        0x80000031u,
        savedEsp);
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
        trace("FAIL: hardware-confirmed startup callback is absent from Phase 5BB pack");
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


static int phase5bb_init_disk_identity_data(void)
{
    static const char model[] = "MERC360 VIRTUAL HDD";
    static const char serial[] = "MERC3600000000001";
    BYTE* modelBuf;
    BYTE* serialBuf;
    uint32_t modelLen = (uint32_t)(sizeof(model) - 1u);
    uint32_t serialLen = (uint32_t)(sizeof(serial) - 1u);

    /* Production-layout-compatible slots inside the existing 4 KiB page. */
    const uint32_t modelStringVa = 0x0087E420u;
    const uint32_t modelBufferVa = 0x0087E430u;
    const uint32_t serialStringVa = 0x0087E460u;
    const uint32_t serialBufferVa = 0x0087E470u;
    const uint32_t cachePartsVa = 0x0087E4A0u;

    modelBuf = guest_ptr(modelBufferVa, modelLen + 1u);
    serialBuf = guest_ptr(serialBufferVa, serialLen + 1u);
    if (!modelBuf || !serialBuf)
        return 0;

    memcpy(modelBuf, model, modelLen + 1u);
    memcpy(serialBuf, serial, serialLen + 1u);

    GUEST_WRITE16(modelStringVa + 0u, modelLen);
    GUEST_WRITE16(modelStringVa + 2u, modelLen + 1u);
    GUEST_WRITE32(modelStringVa + 4u, modelBufferVa);

    GUEST_WRITE16(serialStringVa + 0u, serialLen);
    GUEST_WRITE16(serialStringVa + 2u, serialLen + 1u);
    GUEST_WRITE32(serialStringVa + 4u, serialBufferVa);

    /* Retail HDD has three game-cache partitions exposed as X:, Y:, Z:. */
    GUEST_WRITE32(cachePartsVa, 3u);

    if (s_accessFault ||
        GUEST_READ32(cachePartsVa) != 3u ||
        GUEST_READ16(modelStringVa + 0u) != modelLen ||
        GUEST_READ32(modelStringVa + 4u) != modelBufferVa ||
        GUEST_READ16(serialStringVa + 0u) != serialLen ||
        GUEST_READ32(serialStringVa + 4u) != serialBufferVa ||
        memcmp(modelBuf, model, modelLen + 1u) != 0 ||
        memcmp(serialBuf, serial, serialLen + 1u) != 0)
    {
        trace("FAIL: Phase 5BB disk-identity kernel-data initialization invariant");
        return 0;
    }

    s_phase5bbDiskIdentityDataReady = 1u;
    trace("PASS: Phase 5BB disk identity data initialized cache_partitions=3 model=MERC360 VIRTUAL HDD serial=MERC3600000000001");
    return 1;
}


static int phase5bb_init_xe_image_file_name(void)
{
    static const char imagePath[] = "\\Device\\CdRom0\\default.xbe";
    const uint32_t stringVa = 0x0087E040u;
    const uint32_t bufferVa = 0x0087E050u;
    const uint32_t imageLen = (uint32_t)(sizeof(imagePath) - 1u);
    BYTE* buffer = guest_ptr(bufferVa, imageLen + 1u);

    if (!buffer)
        return 0;

    memcpy(buffer, imagePath, imageLen + 1u);
    GUEST_WRITE16(stringVa + 0u, imageLen);
    GUEST_WRITE16(stringVa + 2u, imageLen + 1u);
    GUEST_WRITE32(stringVa + 4u, bufferVa);

    if (s_accessFault ||
        imageLen != 26u ||
        GUEST_READ16(stringVa + 0u) != imageLen ||
        GUEST_READ16(stringVa + 2u) != imageLen + 1u ||
        GUEST_READ32(stringVa + 4u) != bufferVa ||
        memcmp(buffer, imagePath, imageLen + 1u) != 0)
    {
        trace("FAIL: Phase 5BB XeImageFileName guest kernel-data initialization invariant");
        return 0;
    }

    s_phase5bbXeImageFileNameReady = 1u;
    trace("PASS: Phase 5BB XeImageFileName initialized ordinal=326 string_va=0087E040 buffer_va=0087E050 len=26 path=\\Device\\CdRom0\\default.xbe");
    return 1;
}

static uint32_t phase4c_startup_data_va_for_ordinal(DWORD ordinal)
{
    switch (ordinal)
    {
    case 40u:  return 0x0087E4A0u; /* HalDiskCachePartitionCount */
    case 41u:  return 0x0087E420u; /* HalDiskModelNumber STRING */
    case 42u:  return 0x0087E460u; /* HalDiskSerialNumber STRING */
    case 156u: return 0x0087E020u; /* KeTickCount */
    case 164u: return 0x0087E030u; /* LaunchDataPage pointer export */
    case 322u: return 0x0087E000u; /* XboxHardwareInfo */
    case 324u: return 0x0087E010u; /* XboxKrnlVersion */
    case 326u: return 0x0087E040u; /* XeImageFileName ANSI_STRING */
    default:   return 0u;
    }
}

static int phase4c_fix_startup_data_thunks(void)
{
    DWORD i;

    if (!phase5bb_init_disk_identity_data())
        return 0;
    if (!phase5bb_init_xe_image_file_name())
        return 0;
    DWORD relocated = 0u;
    DWORD seen40 = 0u;
    DWORD seen41 = 0u;
    DWORD seen42 = 0u;
    DWORD seen156 = 0u;
    DWORD seen164 = 0u;
    DWORD seen322 = 0u;
    DWORD seen324 = 0u;
    DWORD seen326 = 0u;
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

        if (ordinal == 40u) ++seen40;
        if (ordinal == 41u) ++seen41;
        if (ordinal == 42u) ++seen42;
        if (ordinal == 156u) ++seen156;
        if (ordinal == 164u) ++seen164;
        if (ordinal == 322u) ++seen322;
        if (ordinal == 324u) ++seen324;
        if (ordinal == 326u) ++seen326;
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

    if (seen40 != 1u || seen41 > 1u || seen42 > 1u ||
        seen156 != 1u || seen164 != 1u || seen322 != 1u || seen324 != 1u ||
        seen326 != 1u || relocated != (6u + seen41 + seen42))
    {
        sprintf(
            line,
            "FAIL: startup data-thunk counts HalDiskCachePartitionCount=%u HalDiskModelNumber=%u HalDiskSerialNumber=%u KeTickCount=%u LaunchDataPage=%u XboxHardwareInfo=%u XboxKrnlVersion=%u XeImageFileName=%u total=%u",
            (unsigned int)seen40,
            (unsigned int)seen41,
            (unsigned int)seen42,
            (unsigned int)seen156,
            (unsigned int)seen164,
            (unsigned int)seen322,
            (unsigned int)seen324,
            (unsigned int)seen326,
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
        GUEST_READ32(0x0087E030u) != 0u ||
        GUEST_READ16(0x0087E040u) != 26u ||
        GUEST_READ16(0x0087E042u) != 27u ||
        GUEST_READ32(0x0087E044u) != 0x0087E050u ||
        GUEST_READ32(0x0087E4A0u) != 3u ||
        (seen41 && (GUEST_READ16(0x0087E420u) != 19u ||
                    GUEST_READ32(0x0087E424u) != 0x0087E430u)) ||
        (seen42 && (GUEST_READ16(0x0087E460u) != 17u ||
                    GUEST_READ32(0x0087E464u) != 0x0087E470u)) ||
        s_accessFault)
    {
        trace("FAIL: startup kernel-data readback invariant failed");
        return 0;
    }

    s_phase5bbDiskIdentitySeen40 = seen40;
    s_phase5bbDiskIdentitySeen41 = seen41;
    s_phase5bbDiskIdentitySeen42 = seen42;
    s_phase5bbXeImageFileNameSeen326 = seen326;
    s_phase4cHardwareInfoThunkFixed = 1;
    sprintf(
        line,
        "PASS: startup data imports 40/41/42(optional)/156/164/322/324/326 relocated; disk_cache_parts=3 seen40=%u seen41=%u seen42=%u seen326=%u LaunchDataPage=NULL XeImageFileName=\\Device\\CdRom0\\default.xbe",
        (unsigned int)seen40,
        (unsigned int)seen41,
        (unsigned int)seen42,
        (unsigned int)seen326);
    trace(line);
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
        raise SystemExit("[Phase5BB] Phase 4C-A report is not a PASS")

    if (
        thread_report.get("phase") != "4C-D"
        or thread_report.get("structural_pass") is not True
    ):
        raise SystemExit("[Phase5BB] Phase 4C-D report is not a PASS")

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
                f"[Phase5BB] hardware observation mismatch for {key}: "
                f"expected {value!r}, got {observed.get(key)!r}"
            )

    root_va = int(str(entry_report["entry"]), 0)
    if root_va != 0x0022964A:
        raise SystemExit(
            f"[Phase5BB] unexpected XBE entry 0x{root_va:08X}"
        )

    thread_root = int(str(thread_report["closure"]["entry"]), 0)
    if thread_root != THREAD_START:
        raise SystemExit(
            f"[Phase5BB] unexpected thread root 0x{thread_root:08X}"
        )

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)

    manual_b178_row = by_va.get(LIVE_DIRECT_FRONTIER_TARGET_16)
    if manual_b178_row is None:
        raise SystemExit(
            "[Phase5BB] maintained manual target 0x0022B178 is absent from the function inventory"
        )
    if manual_b178_row["name"] != "sub_0022B178":
        raise SystemExit(
            "[Phase5BB] maintained manual target 0x0022B178 name changed: "
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

    manual_heap_targets = {
        0x0022DDA4: "sub_0022DDA4",
        0x0022E51F: "sub_0022E51F",
        0x0022E713: "sub_0022E713",
    }
    for manual_va, manual_name in manual_heap_targets.items():
        manual_row = by_va.get(manual_va)
        if manual_row is None:
            raise SystemExit(
                f"[Phase5BB] maintained manual heap target 0x{manual_va:08X} "
                "is absent from the function inventory"
            )
        if manual_row["name"] != manual_name:
            raise SystemExit(
                f"[Phase5BB] maintained manual heap target 0x{manual_va:08X} "
                f"name changed: {manual_row['name']}"
            )
        generated[manual_va] = {
            "name": manual_name,
            "file": "<maintained-manual:recomp_manual.c>",
            "source": f"""void {manual_name}(void)
{{
    /* support-owned maintained Xbox CRT heap helper; emitted by phase5a_boundary */
}}""",
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
                "[Phase5BB] target 0x0022B178 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5L requires a split/mid-function promotion."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0022B178 is absent from the function inventory"
        )

    if generated[LIVE_DIRECT_FRONTIER_TARGET_16].get("file") != "<maintained-manual:recomp_manual.c>":
        raise SystemExit(
            "[Phase5BB] target 0x0022B178 must use the reviewed maintained manual body"
        )

    prior_root_b178_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_16,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )

    # 5O promotes only the exact hardware-observed root 0x00239B78.
    # Fail closed if the frontier is a split/mid-function target or if the
    # frozen Stage-3 translation set has no body for it.
    if LIVE_DIRECT_FRONTIER_TARGET_17 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_17 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x00239B78 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5O requires an explicit split/mid-function promotion."
            )
        raise SystemExit(
            "[Phase5BB] target 0x00239B78 is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_17 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_17]
        raise SystemExit(
            "[Phase5BB] target 0x00239B78 is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    prior_root_239b78_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_17,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if prior_root_239b78_members != {LIVE_DIRECT_FRONTIER_TARGET_17}:
        raise SystemExit(
            "[Phase5BB] retained root 0x00239B78 must contain exactly one member"
        )

    # 5P promotes only the exact hardware-observed root 0x0023DDDD.
    if LIVE_DIRECT_FRONTIER_TARGET_18 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_18 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0023DDDD is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5P requires an explicit split/mid-function promotion."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0023DDDD is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_18 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_18]
        raise SystemExit(
            "[Phase5BB] target 0x0023DDDD is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    prior_root_23dddd_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_18,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if prior_root_23dddd_members != {LIVE_DIRECT_FRONTIER_TARGET_18}:
        raise SystemExit(
            "[Phase5BB] retained root 0x0023DDDD must contain exactly one member"
        )

    # 5Q promotes only the exact hardware-observed root 0x0023DD7B.
    if LIVE_DIRECT_FRONTIER_TARGET_19 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_19 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0023DD7B is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5Q requires an explicit split/mid-function promotion."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0023DD7B is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_19 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_19]
        raise SystemExit(
            "[Phase5BB] target 0x0023DD7B is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    prior_root_23dd7b_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_19,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if prior_root_23dd7b_members != {LIVE_DIRECT_FRONTIER_TARGET_19}:
        raise SystemExit(
            "[Phase5BB] retained root 0x0023DD7B must contain exactly one member"
        )

    # 5R promotes only the exact hardware-observed root 0x0023DDA0.
    if LIVE_DIRECT_FRONTIER_TARGET_20 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_20 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0023DDA0 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5R requires an explicit split/mid-function promotion."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0023DDA0 is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_20 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_20]
        raise SystemExit(
            "[Phase5BB] target 0x0023DDA0 is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    prior_root_23dda0_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_20,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if prior_root_23dda0_members != {LIVE_DIRECT_FRONTIER_TARGET_20}:
        raise SystemExit(
            "[Phase5BB] retained root 0x0023DDA0 must contain exactly one member"
        )

    # 5S promotes only the exact hardware-observed root 0x0023DD56.
    if LIVE_DIRECT_FRONTIER_TARGET_21 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_21 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0023DD56 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5S requires an explicit split/mid-function promotion."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0023DD56 is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_21 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_21]
        raise SystemExit(
            "[Phase5BB] target 0x0023DD56 is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    prior_root_23dd56_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_21,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if prior_root_23dd56_members != {LIVE_DIRECT_FRONTIER_TARGET_21}:
        raise SystemExit(
            "[Phase5BB] retained root 0x0023DD56 must contain exactly one member"
        )

    # 5T promotes only the exact hardware-observed root 0x0023F8CB.
    if LIVE_DIRECT_FRONTIER_TARGET_22 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_22 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0023F8CB is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5T requires an explicit split/mid-function promotion."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0023F8CB is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_22 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_22]
        raise SystemExit(
            "[Phase5BB] target 0x0023F8CB is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    prior_root_23f8cb_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_22,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if prior_root_23f8cb_members != {LIVE_DIRECT_FRONTIER_TARGET_22}:
        raise SystemExit(
            "[Phase5BB] retained root 0x0023F8CB must contain exactly one member"
        )

    # 5V promotes only the exact hardware-observed root 0x0022BDA5.
    if LIVE_DIRECT_FRONTIER_TARGET_23 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_23 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0022BDA5 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5V requires an explicit split/mid-function continuation."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0022BDA5 is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_23 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_23]
        raise SystemExit(
            "[Phase5BB] target 0x0022BDA5 is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    prior_root_22bda5_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_23,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if prior_root_22bda5_members != {LIVE_DIRECT_FRONTIER_TARGET_23}:
        raise SystemExit(
            "[Phase5BB] retained root 0x0022BDA5 must contain exactly one member"
        )

    # 5W promotes only the exact hardware-observed root 0x0022F08D.
    if LIVE_DIRECT_FRONTIER_TARGET_24 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_24 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0022F08D is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5W requires an explicit split/mid-function continuation."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0022F08D is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_24 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_24]
        raise SystemExit(
            "[Phase5BB] target 0x0022F08D is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    prior_root_22f08d_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_24,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if prior_root_22f08d_members != {LIVE_DIRECT_FRONTIER_TARGET_24}:
        raise SystemExit(
            "[Phase5BB] retained root 0x0022F08D must contain exactly one member"
        )

    # 5Y promotes only the exact hardware-observed post-XeLoadSection root.
    if LIVE_DIRECT_FRONTIER_TARGET_25 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_25 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0022F0CC is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5Y requires an explicit split/mid-function continuation."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0022F0CC is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_25 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_25]
        raise SystemExit(
            "[Phase5BB] target 0x0022F0CC is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    prior_root_22f0cc_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_25,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if prior_root_22f0cc_members != {LIVE_DIRECT_FRONTIER_TARGET_25}:
        raise SystemExit(
            "[Phase5BB] retained root 0x0022F0CC must contain exactly one member"
        )

    # Retain the previously promoted post-image-write root.
    if LIVE_DIRECT_FRONTIER_TARGET_26 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_26 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] retained target 0x0022F0AE is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}"
            )
        raise SystemExit(
            "[Phase5BB] retained target 0x0022F0AE is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_26 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_26]
        raise SystemExit(
            "[Phase5BB] retained target 0x0022F0AE is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    prior_root_22f0ae_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_26,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if prior_root_22f0ae_members != {LIVE_DIRECT_FRONTIER_TARGET_26}:
        raise SystemExit(
            "[Phase5BB] retained root 0x0022F0AE must contain exactly one member"
        )

    # Retain the previously promoted persistent-state root.
    if LIVE_DIRECT_FRONTIER_TARGET_27 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_27 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] retained target 0x0022A604 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}"
            )
        raise SystemExit(
            "[Phase5BB] retained target 0x0022A604 is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_27 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_27]
        raise SystemExit(
            "[Phase5BB] retained target 0x0022A604 is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    prior_root_22a604_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_27,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if prior_root_22a604_members != {LIVE_DIRECT_FRONTIER_TARGET_27}:
        raise SystemExit(
            "[Phase5BB] retained root 0x0022A604 must contain exactly one member"
        )

    # Promote only the exact new hardware-observed frontier.
    if LIVE_DIRECT_FRONTIER_TARGET_28 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_28 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0022A3B9 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5AF requires an explicit split/mid-function continuation."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0022A3B9 is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_28 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_28]
        raise SystemExit(
            "[Phase5BB] target 0x0022A3B9 is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    promoted_closure_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_28,
            generated,
            PROMOTED_CLOSURE_DEPTH,
            PROMOTED_CLOSURE_CAP,
        )
    )
    if promoted_closure_members != {LIVE_DIRECT_FRONTIER_TARGET_28}:
        raise SystemExit(
            "[Phase5BB] target 0x0022A3B9 promotion must contain exactly one root"
        )

    # Batch the new cache-setup translated frontier instead of adding only one body.
    if LIVE_DIRECT_FRONTIER_TARGET_29 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_29 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0022C5C6 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}"
            )
        raise SystemExit(
            "[Phase5BB] target 0x0022C5C6 is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_29 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_29]
        raise SystemExit(
            "[Phase5BB] target 0x0022C5C6 is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    phase5bb_cache_frontier_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_29,
            generated,
            P5AN_FRONTIER_CLOSURE_DEPTH,
            P5AN_FRONTIER_CLOSURE_CAP,
        )
    )
    if LIVE_DIRECT_FRONTIER_TARGET_29 not in phase5bb_cache_frontier_members:
        raise SystemExit(
            "[Phase5BB] cache frontier closure lost root 0x0022C5C6"
        )

    # Batch the hardware-observed post-persistence frontier.
    if LIVE_DIRECT_FRONTIER_TARGET_30 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_30 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0022F0D6 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}"
            )
        raise SystemExit(
            "[Phase5BB] target 0x0022F0D6 is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_30 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_30]
        raise SystemExit(
            "[Phase5BB] target 0x0022F0D6 is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    phase5bb_post_persist_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_30,
            generated,
            P5BB_FRONTIER_CLOSURE_DEPTH,
            P5BB_FRONTIER_CLOSURE_CAP,
        )
    )
    if LIVE_DIRECT_FRONTIER_TARGET_30 not in phase5bb_post_persist_members:
        raise SystemExit(
            "[Phase5BB] post-persistence closure lost root 0x0022F0D6"
        )

    # Phase 5AR hardware PASS exposed the next clean direct frontier:
    # caller 0x00230060 -> target 0x0022BBC8, after the second repeatable
    # ExQueryNonVolatileSetting call completed successfully.
    if LIVE_DIRECT_FRONTIER_TARGET_31 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_31 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0022BBC8 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}"
            )
        raise SystemExit(
            "[Phase5BB] target 0x0022BBC8 is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_31 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_31]
        raise SystemExit(
            "[Phase5BB] target 0x0022BBC8 is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    phase5bb_next_frontier_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_31,
            generated,
            P5BB_NEXT_FRONTIER_CLOSURE_DEPTH,
            P5BB_NEXT_FRONTIER_CLOSURE_CAP,
        )
    )
    if LIVE_DIRECT_FRONTIER_TARGET_31 not in phase5bb_next_frontier_members:
        raise SystemExit(
            "[Phase5BB] next-frontier closure lost root 0x0022BBC8"
        )

    # Phase 5AW hardware PASS exposed the next clean direct frontier:
    # caller 0x00239D6C -> target 0x0023E600, after ordinal 326
    # XeImageFileName was successfully relocated and consumed.
    if LIVE_DIRECT_FRONTIER_TARGET_32 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_32 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0023E600 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5AX requires an explicit split/mid-function promotion."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0023E600 is absent from the function inventory"
        )

    if LIVE_DIRECT_FRONTIER_TARGET_32 not in generated:
        row = by_va[LIVE_DIRECT_FRONTIER_TARGET_32]
        raise SystemExit(
            "[Phase5BB] target 0x0023E600 is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    phase5bb_live_frontier_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_32,
            generated,
            P5BB_LIVE_FRONTIER_CLOSURE_DEPTH,
            P5BB_LIVE_FRONTIER_CLOSURE_CAP,
        )
    )
    if LIVE_DIRECT_FRONTIER_TARGET_32 not in phase5bb_live_frontier_members:
        raise SystemExit(
            "[Phase5BB] live frontier closure lost root 0x0023E600"
        )

    # Phase 5AZ hardware PASS exposed a new fault-free guest-code ICALL:
    # caller 0x0022C452 -> target 0x0023D550.
    if LIVE_INDIRECT_FRONTIER_TARGET_33 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_INDIRECT_FRONTIER_TARGET_33 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0023D550 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5BA requires an explicit split/mid-function promotion."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0023D550 is absent from the function inventory"
        )

    if LIVE_INDIRECT_FRONTIER_TARGET_33 not in generated:
        row = by_va[LIVE_INDIRECT_FRONTIER_TARGET_33]
        raise SystemExit(
            "[Phase5BB] target 0x0023D550 is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )

    phase5bb_icall_frontier_members = set(
        bounded_promoted_members(
            base,
            LIVE_INDIRECT_FRONTIER_TARGET_33,
            generated,
            P5BB_ICALL_FRONTIER_CLOSURE_DEPTH,
            P5BB_ICALL_FRONTIER_CLOSURE_CAP,
        )
    )
    if LIVE_INDIRECT_FRONTIER_TARGET_33 not in phase5bb_icall_frontier_members:
        raise SystemExit(
            "[Phase5BB] ICALL frontier closure lost root 0x0023D550"
        )

    # Phase 5BA hardware PASS exposed a new fault-free direct frontier:
    # caller 0x0022B5EF -> target 0x0022DDA4.
    if LIVE_DIRECT_FRONTIER_TARGET_34 not in by_va:
        containing = [
            row for row in by_va.values()
            if int(row["start"]) < LIVE_DIRECT_FRONTIER_TARGET_34 < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                "[Phase5BB] target 0x0022DDA4 is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "5BB requires an explicit split/mid-function review."
            )
        raise SystemExit(
            "[Phase5BB] target 0x0022DDA4 is absent from the refreshed function inventory; "
            "do not seed blindly -- inspect the hardware-proven direct target first"
        )

    if generated[LIVE_DIRECT_FRONTIER_TARGET_34].get("emit_mode") != "support-owned":
        raise SystemExit(
            "[Phase5BB] target 0x0022DDA4 must use the reviewed maintained manual RtlAllocateHeap body"
        )

    phase5bb_direct34_members = set(
        bounded_promoted_members(
            base,
            LIVE_DIRECT_FRONTIER_TARGET_34,
            generated,
            P5BB_DIRECT34_CLOSURE_DEPTH,
            P5BB_DIRECT34_CLOSURE_CAP,
        )
    )
    phase5bb_direct34_members.update(manual_heap_targets.keys())
    if LIVE_DIRECT_FRONTIER_TARGET_34 not in phase5bb_direct34_members:
        raise SystemExit(
            "[Phase5BB] direct frontier closure lost root 0x0022DDA4"
        )
    if len(phase5bb_direct34_members) > P5BB_DIRECT34_CLOSURE_CAP:
        raise SystemExit(
            "[Phase5BB] maintained heap family exceeds direct34 closure cap"
        )

    promoted_direct_members = {
        LIVE_DIRECT_FRONTIER_TARGET,
        LIVE_DIRECT_FRONTIER_TARGET_2,
        LIVE_DIRECT_FRONTIER_TARGET_3,
        LIVE_DIRECT_FRONTIER_TARGET_4,
    } | previous_promoted_closure_members | prior_safe_root_members | prior_root_38c00_members | prior_root_d431_members | prior_root_ca2b_members | prior_root_c8ea_members | prior_root_ceee_members | prior_root_c1c0_members | prior_root_370b8_members | prior_root_be8c_members | prior_root_f026_members | prior_root_b178_members | prior_root_239b78_members | prior_root_23dddd_members | prior_root_23dd7b_members | prior_root_23dda0_members | prior_root_23dd56_members | prior_root_23f8cb_members | prior_root_22bda5_members | prior_root_22f08d_members | prior_root_22f0cc_members | prior_root_22f0ae_members | prior_root_22a604_members | promoted_closure_members | phase5bb_cache_frontier_members | phase5bb_post_persist_members | phase5bb_next_frontier_members | phase5bb_live_frontier_members | phase5bb_icall_frontier_members | phase5bb_direct34_members
    member_vas = sorted(
        entry_members | thread_members | callback_members | promoted_direct_members
    )
    packed_vas = set(member_vas)

    missing_generated = [va for va in member_vas if va not in generated]
    if missing_generated:
        raise SystemExit(
            "[Phase5BB] generated body missing for packed member(s): "
            + ", ".join(f"0x{va:08X}" for va in missing_generated)
        )

    root_row = by_va.get(root_va)
    if root_row is None:
        raise SystemExit("[Phase5BB] XBE entry absent from function inventory")
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

        if va in {
            LIVE_DIRECT_FRONTIER_TARGET_16,
            0x0022DDA4,
            0x0022E51F,
            0x0022E713,
        }:
            if row.get("emit_mode") != "support-owned":
                raise SystemExit(
                    f"[Phase5BB] manual support target 0x{va:08X} must remain support-owned during body emission"
                )
            rendered_by_va[va] = ""
            continue

        forward_decls.append(f"static void {name}(void);")
        rendered = base.localize_and_instrument(row["source"], name)
        if va == LIVE_DIRECT_FRONTIER_TARGET_23:
            name_pos = rendered.find(name)
            brace_pos = rendered.find("{", name_pos)
            if name_pos < 0 or brace_pos < 0:
                raise SystemExit(
                    "[Phase5BB] could not instrument retained root 0x0022BDA5"
                )
            rendered = (
                rendered[:brace_pos + 1]
                + "\n    s_phase5ahRoot22BDA5Entered = 1;"
                + rendered[brace_pos + 1:]
            )
        if va == LIVE_DIRECT_FRONTIER_TARGET_24:
            name_pos = rendered.find(name)
            brace_pos = rendered.find("{", name_pos)
            if name_pos < 0 or brace_pos < 0:
                raise SystemExit(
                    "[Phase5BB] could not instrument retained root 0x0022F08D"
                )
            rendered = (
                rendered[:brace_pos + 1]
                + "\n    s_phase5ahRoot22F08DEntered = 1;"
                + rendered[brace_pos + 1:]
            )
        if va == LIVE_DIRECT_FRONTIER_TARGET_25:
            name_pos = rendered.find(name)
            brace_pos = rendered.find("{", name_pos)
            if name_pos < 0 or brace_pos < 0:
                raise SystemExit(
                    "[Phase5BB] could not instrument retained root 0x0022F0CC"
                )
            rendered = (
                rendered[:brace_pos + 1]
                + "\n    s_phase5ahRoot22F0CCEntered = 1;"
                + rendered[brace_pos + 1:]
            )
        if va == LIVE_DIRECT_FRONTIER_TARGET_26:
            name_pos = rendered.find(name)
            brace_pos = rendered.find("{", name_pos)
            if name_pos < 0 or brace_pos < 0:
                raise SystemExit(
                    "[Phase5BB] could not instrument retained root 0x0022F0AE"
                )
            rendered = (
                rendered[:brace_pos + 1]
                + "\n    s_phase5ahRoot22F0AEEntered = 1;"
                + rendered[brace_pos + 1:]
            )
        if va == LIVE_DIRECT_FRONTIER_TARGET_27:
            name_pos = rendered.find(name)
            brace_pos = rendered.find("{", name_pos)
            if name_pos < 0 or brace_pos < 0:
                raise SystemExit(
                    "[Phase5BB] could not instrument retained root 0x0022A604"
                )
            rendered = (
                rendered[:brace_pos + 1]
                + "\n    s_phase5ahRoot22A604Entered = 1;"
                + rendered[brace_pos + 1:]
            )
        if va == LIVE_DIRECT_FRONTIER_TARGET_28:
            name_pos = rendered.find(name)
            brace_pos = rendered.find("{", name_pos)
            if name_pos < 0 or brace_pos < 0:
                raise SystemExit(
                    "[Phase5BB] could not instrument promoted root 0x0022A3B9"
                )
            rendered = (
                rendered[:brace_pos + 1]
                + "\n    s_phase5ahRoot22A3B9Entered = 1;"
                + rendered[brace_pos + 1:]
            )
        if va == LIVE_DIRECT_FRONTIER_TARGET_29:
            name_pos = rendered.find(name)
            brace_pos = rendered.find("{", name_pos)
            if name_pos < 0 or brace_pos < 0:
                raise SystemExit(
                    "[Phase5BB] could not instrument promoted cache root 0x0022C5C6"
                )
            rendered = (
                rendered[:brace_pos + 1]
                + "\n    s_phase5bbRoot22C5C6Entered = 1;"
                + rendered[brace_pos + 1:]
            )
        if va == LIVE_DIRECT_FRONTIER_TARGET_30:
            name_pos = rendered.find(name)
            brace_pos = rendered.find("{", name_pos)
            if name_pos < 0 or brace_pos < 0:
                raise SystemExit(
                    "[Phase5BB] could not instrument post-persistence root 0x0022F0D6"
                )
            rendered = (
                rendered[:brace_pos + 1]
                + "\n    s_phase5bbRoot22F0D6Entered = 1;"
                + rendered[brace_pos + 1:]
            )
        if va == LIVE_DIRECT_FRONTIER_TARGET_31:
            name_pos = rendered.find(name)
            brace_pos = rendered.find("{", name_pos)
            if name_pos < 0 or brace_pos < 0:
                raise SystemExit(
                    "[Phase5BB] could not instrument next frontier root 0x0022BBC8"
                )
            rendered = (
                rendered[:brace_pos + 1]
                + "\n    s_phase5bbRoot22BBC8Entered = 1;"
                + rendered[brace_pos + 1:]
            )
        if va == LIVE_DIRECT_FRONTIER_TARGET_32:
            name_pos = rendered.find(name)
            brace_pos = rendered.find("{", name_pos)
            if name_pos < 0 or brace_pos < 0:
                raise SystemExit(
                    "[Phase5BB] could not instrument live frontier root 0x0023E600"
                )
            rendered = (
                rendered[:brace_pos + 1]
                + "\n    s_phase5bbRoot23E600Entered = 1;"
                + rendered[brace_pos + 1:]
            )
        if va == LIVE_INDIRECT_FRONTIER_TARGET_33:
            name_pos = rendered.find(name)
            brace_pos = rendered.find("{", name_pos)
            if name_pos < 0 or brace_pos < 0:
                raise SystemExit(
                    "[Phase5BB] could not instrument ICALL frontier root 0x0023D550"
                )
            rendered = (
                rendered[:brace_pos + 1]
                + "\n    s_phase5bbRoot23D550Entered = 1;"
                + rendered[brace_pos + 1:]
            )
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
        raise SystemExit("[Phase5BB] Phase-3N support donor marker missing")

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
        "phase5ah_nt_query_information_file",
        "phase5ah_xe_load_section",
        "phase5ah_copy_guest_cstr",
        "phase5ah_filetime_value",
        "phase5ah_write_guest_u64",
        "phase5k_rtl_equal_string",
        "phase5i_rtl_init_ansi_string",
        "phase5h_nt_create_file",
        "phase5h_nt_read_file",
        "phase5ah_nt_write_file",
        "phase5ah_write_status_from_error",
        "phase5ah_seek_end",
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
        "phase5bb_find_reservation",
        "phase5bb_alloc_guest_pages",
        "phase5bb_release_guest_pages",
        "phase5bb_mm_allocate_contiguous",
        "phase5bb_mm_allocate_contiguous_ex",
        "phase5bb_mm_allocate_system",
        "phase5bb_mm_free_contiguous",
        "phase5bb_mm_free_system",
        "phase5bb_mm_get_physical_address",
        "phase5bb_mm_lock_unlock_buffer_pages",
        "phase5bb_mm_query_allocation_size",
        "phase5bb_mm_query_statistics",
        "phase5bb_mm_set_address_protect",
        "phase5bb_mm_lock_unlock_physical_page",
        "phase5bb_mm_map_io_space",
        "phase5bb_mm_persist_contiguous",
        "phase5bb_mm_query_address_protect",
        "phase5bb_mm_unmap_io_space",
        "phase5bb_nt_free_virtual_memory",
        "recomp_test_audio_alloc_failure",
        "recomp_audio_pool_fallback",
        "recomp_audio_pool_free",
        "recomp_prepare_empty_cache_volume",
        "phase5bb_hal_return_to_firmware_trap",
        "recomp_crt_memmove",
        "phase4c_direct_frontier",
        "phase4c_fix_startup_data_thunks",
        "phase4c_init_kernel_header_page",
    })

    unknown = {}
    unknown_contexts = {}
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
            owner = f"0x{va:08X} {row['name']}"
            unknown[owner] = missing
            source_lines = rendered.splitlines()
            owner_contexts = []
            for helper in missing:
                call_pattern = re.compile(
                    rf"\b{re.escape(helper)}\s*\("
                )
                matched = False
                for line_index, source_line in enumerate(source_lines):
                    if not call_pattern.search(source_line):
                        continue
                    matched = True
                    first = max(0, line_index - 5)
                    last = min(len(source_lines), line_index + 6)
                    owner_contexts.append({
                        "helper": helper,
                        "call_line": line_index + 1,
                        "first_line": first + 1,
                        "last_line": last,
                        "context": "\n".join(
                            f"{n + 1:04d}: {source_lines[n]}"
                            for n in range(first, last)
                        ),
                    })
                if not matched:
                    owner_contexts.append({
                        "helper": helper,
                        "call_line": 0,
                        "first_line": 0,
                        "last_line": 0,
                        "context": "<call not found in rendered source>",
                    })
            unknown_contexts[owner] = owner_contexts

    args.out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "phase": "5BB",
        "build_tag": "P5BB-FRONTIER22DDA4-20261020-A",
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
        "promoted_closure_16_members": [
            f"0x{va:08X}" for va in sorted(prior_root_b178_members)
        ],
        "promoted_direct_frontier_target_17": f"0x{LIVE_DIRECT_FRONTIER_TARGET_17:08X}",
        "promoted_closure_17_members": [
            f"0x{va:08X}" for va in sorted(prior_root_239b78_members)
        ],
        "promoted_direct_frontier_target_18": f"0x{LIVE_DIRECT_FRONTIER_TARGET_18:08X}",
        "promoted_closure_18_members": [
            f"0x{va:08X}" for va in sorted(prior_root_23dddd_members)
        ],
        "promoted_direct_frontier_target_19": f"0x{LIVE_DIRECT_FRONTIER_TARGET_19:08X}",
        "promoted_closure_19_members": [
            f"0x{va:08X}" for va in sorted(prior_root_23dd7b_members)
        ],
        "promoted_direct_frontier_target_20": f"0x{LIVE_DIRECT_FRONTIER_TARGET_20:08X}",
        "promoted_closure_20_members": [
            f"0x{va:08X}" for va in sorted(prior_root_23dda0_members)
        ],
        "promoted_direct_frontier_target_21": f"0x{LIVE_DIRECT_FRONTIER_TARGET_21:08X}",
        "promoted_closure_21_members": [
            f"0x{va:08X}" for va in sorted(prior_root_23dd56_members)
        ],
        "promoted_direct_frontier_target_22": f"0x{LIVE_DIRECT_FRONTIER_TARGET_22:08X}",
        "promoted_closure_22_members": [
            f"0x{va:08X}" for va in sorted(prior_root_23f8cb_members)
        ],
        "promoted_direct_frontier_target_23": f"0x{LIVE_DIRECT_FRONTIER_TARGET_23:08X}",
        "promoted_closure_23_members": [
            f"0x{va:08X}" for va in sorted(prior_root_22bda5_members)
        ],
        "promoted_direct_frontier_target_24": f"0x{LIVE_DIRECT_FRONTIER_TARGET_24:08X}",
        "promoted_closure_24_members": [
            f"0x{va:08X}" for va in sorted(prior_root_22f08d_members)
        ],
        "promoted_direct_frontier_target_25": f"0x{LIVE_DIRECT_FRONTIER_TARGET_25:08X}",
        "promoted_closure_25_members": [
            f"0x{va:08X}" for va in sorted(prior_root_22f0cc_members)
        ],
        "promoted_direct_frontier_target_26": f"0x{LIVE_DIRECT_FRONTIER_TARGET_26:08X}",
        "promoted_closure_26_members": [
            f"0x{va:08X}" for va in sorted(prior_root_22f0ae_members)
        ],
        "promoted_direct_frontier_target_27": f"0x{LIVE_DIRECT_FRONTIER_TARGET_27:08X}",
        "promoted_closure_27_members": [
            f"0x{va:08X}" for va in sorted(prior_root_22a604_members)
        ],
        "promoted_direct_frontier_target_28": f"0x{LIVE_DIRECT_FRONTIER_TARGET_28:08X}",
        "promoted_closure_28_members": [
            f"0x{va:08X}" for va in sorted(promoted_closure_members)
        ],
        "promoted_direct_frontier_target_29": f"0x{LIVE_DIRECT_FRONTIER_TARGET_29:08X}",
        "promoted_closure_29_depth": P5AN_FRONTIER_CLOSURE_DEPTH,
        "promoted_closure_29_cap": P5AN_FRONTIER_CLOSURE_CAP,
        "promoted_closure_29_members": [
            f"0x{va:08X}" for va in sorted(phase5bb_cache_frontier_members)
        ],
        "promoted_direct_frontier_target_30": f"0x{LIVE_DIRECT_FRONTIER_TARGET_30:08X}",
        "promoted_closure_30_depth": P5BB_FRONTIER_CLOSURE_DEPTH,
        "promoted_closure_30_cap": P5BB_FRONTIER_CLOSURE_CAP,
        "promoted_closure_30_members": [
            f"0x{va:08X}" for va in sorted(phase5bb_post_persist_members)
        ],
        "promoted_direct_frontier_target_31": f"0x{LIVE_DIRECT_FRONTIER_TARGET_31:08X}",
        "promoted_closure_31_depth": P5BB_NEXT_FRONTIER_CLOSURE_DEPTH,
        "promoted_closure_31_cap": P5BB_NEXT_FRONTIER_CLOSURE_CAP,
        "promoted_closure_31_members": [
            f"0x{va:08X}" for va in sorted(phase5bb_next_frontier_members)
        ],
        "promoted_direct_frontier_target_32": f"0x{LIVE_DIRECT_FRONTIER_TARGET_32:08X}",
        "promoted_closure_32_depth": P5BB_LIVE_FRONTIER_CLOSURE_DEPTH,
        "promoted_closure_32_cap": P5BB_LIVE_FRONTIER_CLOSURE_CAP,
        "promoted_closure_32_members": [
            f"0x{va:08X}" for va in sorted(phase5bb_live_frontier_members)
        ],
        "promoted_indirect_frontier_target_33": f"0x{LIVE_INDIRECT_FRONTIER_TARGET_33:08X}",
        "promoted_closure_33_depth": P5BB_ICALL_FRONTIER_CLOSURE_DEPTH,
        "promoted_closure_33_cap": P5BB_ICALL_FRONTIER_CLOSURE_CAP,
        "promoted_closure_33_members": [
            f"0x{va:08X}" for va in sorted(phase5bb_icall_frontier_members)
        ],
        "promoted_direct_frontier_target_34": f"0x{LIVE_DIRECT_FRONTIER_TARGET_34:08X}",
        "promoted_closure_34_depth": P5BB_DIRECT34_CLOSURE_DEPTH,
        "promoted_closure_34_cap": P5BB_DIRECT34_CLOSURE_CAP,
        "promoted_closure_34_members": [
            f"0x{va:08X}" for va in sorted(phase5bb_direct34_members)
        ],
        "promoted_closure_depth": PROMOTED_CLOSURE_DEPTH,
        "promoted_closure_cap": PROMOTED_CLOSURE_CAP,
        "promoted_closure_members": [
            f"0x{va:08X}" for va in sorted(promoted_closure_members)
        ],
        "phase5_nt_query_information_file": {
            "target": "0x800000D3",
            "ordinal": 211,
            "name": "NtQueryInformationFile",
            "arg_bytes": 20,
            "frame_bytes": 24,
            "mode": "native-class34-continuation",
            "supported_class": 34,
            "supported_class_name": "FileNetworkOpenInformation",
            "required_length": 56,
            "guest_layout": "CreationTime/LastAccessTime/LastWriteTime/ChangeTime/AllocationSize/EndOfFile as six u64 values, FileAttributes u32, reserved u32",
            "metadata_source": "GetFileAttributesExA on Xenon path associated with tagged guest handle",
            "allocation_policy": "round EndOfFile upward to the proven 16 KiB FATX-style allocation unit",
            "change_time_policy": "mirror native last-write time because XAM WIN32_FILE_ATTRIBUTE_DATA exposes no distinct change time",
            "unobserved_classes": "fenced at FILE_INFORMATION boundary",
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
            "mode": "maintained-native-continuation-plus-proven-caller-savedesp-repair",
            "guest_layout": "ANSI_STRING: Length u16, MaximumLength u16, Buffer u32 guest VA",
            "source_policy": "bounded guest C-string scan with maintained 0xFFFE clamp",
            "caller_0022A7A4_repair": {
                "observed_phase": "5AX",
                "caller": "0x0022A7A4",
                "observed_frame_bytes": 16,
                "abi_frame_bytes": 12,
                "resume_adjustment": -4,
                "validation": "zero synthetic return; non-null bounded 8-byte destination; source is NULL or guest-readable",
                "policy": "repair only exact hardware-observed caller/frame; retain canonical two-argument ordinal-289 ABI"
            }
        },
        "phase5_nt_create_file": {
            "target": "0x800000BE",
            "ordinal": 190,
            "name": "NtCreateFile",
            "arg_bytes": 36,
            "frame_bytes": 40,
            "mode": "native-continuation-plus-obdosdevices-root",
            "path_policy": "reuse guest symbolic-link expansion and native Xenon storage mapping",
            "handle_policy": "stable tagged 32-bit guest token backed by native Xenon HANDLE table",
            "create_dispositions": "0..5 mapped to CreateFileA semantics",
            "obdosdevices_root": "0xFFFFFFFD",
            "obdosdevices_policy": "treat 0xFFFFFFFD as Xbox ObDosDevices pseudo-root, not a relative file handle; resolve X:\\path through guest-created \\??\\X: symbolic links",
            "observed_phase": "5AY",
            "observed_caller": "0x0022A7A4",
            "observed_path": "t:\\$u\\contentmeta.xbx"
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
        "phase5_nt_write_file": {
            "target": "0x800000EC",
            "ordinal": 236,
            "name": "NtWriteFile",
            "arg_bytes": 32,
            "frame_bytes": 36,
            "mode": "synchronous-native-continuation-plus-proven-image-section-savedesp-repair",
            "native_primitive": "WriteFile",
            "handle_policy": "resolve tagged guest token to native Xenon HANDLE and require the proven image filename suffix for compact caller 0x0022F0CC",
            "offset_policy": "absolute offsets + FILE_USE_FILE_POINTER_POSITION + FILE_WRITE_TO_END_OF_FILE; compact image-section repair requires ByteOffset=NULL",
            "async_policy": "event/APC forms remain fenced",
            "iosb_policy": "write NTSTATUS and transferred-byte count to guest IO_STATUS_BLOCK",
            "hardware_frame_36": "proven native write path from 0x0023F8CB",
            "caller_0022F0CC": "all eight standard arguments present; translated savedEsp is one dword short",
            "caller_0022F0CC_xtimage": "$XTIMAGE section index 11, header 0x000105D8, VA 0x00874D40, length 0x2800, TitleImage.xbx",
            "caller_0022F0CC_xsimage": "$XSIMAGE section index 12, header 0x00010610, VA 0x00877540, length 0x1000, SaveImage.xbx",
            "caller_0022F0CC_repair": "require a successful matching XeLoadSection, exact buffer/length/path pair and NULL ByteOffset; resumeEsp=savedEsp+4",
        },
        "phase5_xe_load_section": {
            "target": "0x80000147",
            "ordinal": 327,
            "name": "XeLoadSection",
            "arg_bytes": 4,
            "frame_bytes": 8,
            "mode": "native-bookkeeping-continuation",
            "section_header_bytes": 56,
            "section_table_source": "retail XBE header NumSections/Sections at 0x11C/0x120",
            "image_policy": "Phase-2E already preloads all XBE section bytes into guest RAM",
            "reference_policy": "increment SectionReferenceCount; on 0->1 increment distinct shared head/tail page counters",
        },
        "phase5_xe_unload_section": {
            "target": "0x80000148",
            "ordinal": 328,
            "name": "XeUnloadSection",
            "arg_bytes": 4,
            "frame_bytes": 8,
            "mode": "native-bookkeeping-continuation",
            "section_header_bytes": 56,
            "reference_policy": "decrement SectionReferenceCount; on 1->0 decrement distinct shared head/tail page reference counters",
            "resident_byte_policy": "do not clear guest section bytes because Phase-2E preloads all XBE sections and XeLoadSection is bookkeeping-only",
            "state_policy": "armed but not mandatory on persistent-file boots",
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
            "partition0_mapping": "\\Device\\Harddisk0\\partition0 -> game:\\merc360-partition0",
            "partition0_scope": "exact root only; child paths remain fenced until observed",
            "partition0_open_policy": "create sandbox directory on demand; force FILE_FLAG_BACKUP_SEMANTICS for virtual roots",
            "native_primitive": "CreateFileA / OPEN_EXISTING / FILE_FLAG_BACKUP_SEMANTICS for directory opens",
            "handle_policy": "stable tagged 32-bit guest token backed by native Xenon HANDLE table",
            "obdosdevices_root": "0xFFFFFFFD",
            "obdosdevices_policy": "same Xbox DOS-device pseudo-root acceptance as NtCreateFile; drive aliases expand through guest symbolic-link table",
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
            "dispatch": "repeatable; no one-shot state guard",
            "production_semantics": "src/kernel/kernel_rtl.c xbox_RtlNtStatusToDosError table",
            "hardware_gate": "second call must map STATUS_UNSUCCESSFUL 0xC0000001 to ERROR_GEN_FAILURE 31",
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
        "diagnostic_goal": "relocate_hardware_observed_ordinal326_XeImageFileName_then_continue_beyond_00239C23_80000146",
        "phase5bb_xe_image_file_name": {
            "observed_caller": "0x00239C23",
            "old_fault_token": "0x80000146",
            "ordinal": 326,
            "name": "XeImageFileName",
            "guest_string_va": "0x0087E040",
            "guest_buffer_va": "0x0087E050",
            "length": 26,
            "maximum_length": 27,
            "path": "\\Device\\CdRom0\\default.xbe",
            "policy": "relocate retail kernel thunk ordinal 326 to an 8-byte guest ANSI_STRING; old 0x80000146 fault cannot count as progress"
        },
        "phase5bb_support_shims": {
            "recomp_prepare_empty_cache_volume": {
                "signature": "int(void)",
                "policy": "ensure Partition3/4/5 roots exist; return 0 so retail translated body executes"
            },
            "recomp_test_audio_alloc_failure": {
                "signature": "int(uint32_t attributes)",
                "policy": "diagnostic hook only; never force failure"
            },
            "recomp_audio_pool_fallback": {
                "signature": "uint32_t(uint32_t size, uint32_t attributes)",
                "policy": "page-backed guest fallback only after retail allocator returned NULL; tracked ownership"
            },
            "recomp_audio_pool_free": {
                "signature": "int(uint32_t ptr)",
                "policy": "consume only tracked fallback pointers; otherwise preserve retail free path"
            }
        },
        "phase5bb_partition0_persistence": {
            "backing_path": "game:\\merc360-partition0\\partition0-config.bin",
            "backing_size": 524288,
            "load_policy": "load existing backing, zero-pad short file, otherwise start zeroed",
            "write_policy": "compare range, update in-memory device, flush complete 512 KiB backing before reporting NtWriteFile success",
            "two_pass_hardware_test": True,
            "first_pass_expected": "changed write then HalReturnToFirmware routine 2 may prime persistent cache metadata",
            "second_pass_expected": "reload backing without rebuild; persistent sector should be visible before retail cache setup"
        },
        "phase5bb_cache_device_io": {
            "ordinal": 196,
            "name": "NtDeviceIoControlFile",
            "token": "0x800000C4",
            "canonical_frame_bytes": 44,
            "hardware_frame_bytes": 52,
            "accepted_frame_bytes": [44, 52],
            "hardware_extra_bytes": 8,
            "frame_policy": "locate exactly one canonical 44-byte argument window in 52-byte hardware frame using tracked cache handle + known IOCTL",
            "synchronous_only": True,
            "cache_size": 1044480,
            "bytes_per_sector": 512,
            "supported_controls": {
                "0x00070000": {
                    "name": "IOCTL_DISK_GET_DRIVE_GEOMETRY",
                    "output_bytes": 8,
                    "payload": "sector_count, bytes_per_sector"
                },
                "0x00074004": {
                    "name": "IOCTL_DISK_GET_PARTITION_INFO",
                    "output_bytes": 16,
                    "payload": "starting_offset_64, partition_length_64"
                }
            },
            "unknown_policy": "fence at STORAGE_IO and log full live frame"
        },
        "phase5bb_post_persistence_frontier": {
            "observed_caller": "0x0022BD2D",
            "root": "0x0022F0D6",
            "closure_depth": P5BB_FRONTIER_CLOSURE_DEPTH,
            "closure_cap": P5BB_FRONTIER_CLOSURE_CAP,
            "required_prior_state": "persistent Partition0 loaded; sector 0x800 rewrite unchanged; Z cache mount reached",
            "pass_policy": "root must execute and old 0x0022F0D6 frontier cannot count as progress"
        },
        "phase5bb_next_frontier": {
            "observed_caller": "0x00230060",
            "root": "0x0022BBC8",
            "closure_depth": P5BB_NEXT_FRONTIER_CLOSURE_DEPTH,
            "closure_cap": P5BB_NEXT_FRONTIER_CLOSURE_CAP,
            "required_prior_state": "Phase 5AR hardware PASS; repeatable ordinal 24 calls >= 2; post-persistence 0x0022F0D6 root executed",
            "pass_policy": "0x0022BBC8 root must execute and old 0x0022BBC8 direct frontier cannot count as progress"
        },
        "phase5bb_live_frontier": {
            "observed_phase": "5AW",
            "observed_caller": "0x00239D6C",
            "root": "0x0023E600",
            "observed_fault": 0,
            "closure_depth": P5BB_LIVE_FRONTIER_CLOSURE_DEPTH,
            "closure_cap": P5BB_LIVE_FRONTIER_CLOSURE_CAP,
            "required_prior_state": "XeImageFileName ordinal 326 relocated exactly once; symbolic-link query and close succeeded; persisted cache path active",
            "pass_policy": "0x0023E600 root must execute and old 0x0023E600 direct frontier cannot count as progress"
        },
        "phase5bb_indirect_frontier": {
            "observed_phase": "5AZ",
            "boundary_kind": "ICALL_SAFE",
            "observed_caller": "0x0022C452",
            "root": "0x0023D550",
            "observed_fault": 0,
            "observed_esp": "0x008BFF40",
            "observed_saved_esp": "0x008BFF44",
            "closure_depth": P5BB_ICALL_FRONTIER_CLOSURE_DEPTH,
            "closure_cap": P5BB_ICALL_FRONTIER_CLOSURE_CAP,
            "dispatch_policy": "only exact guest ICALL target 0x0023D550 is allowed to resolve through the translated pack in this phase",
            "required_prior_state": "ObDosDevices contentmeta path mapping executed; STATUS_OBJECT_PATH_NOT_FOUND converted to DOS error 3; SetLastError(3) completed",
            "pass_policy": "0x0023D550 root must execute, packed ICALL count must be nonzero, and old 0x0023D550 boundary cannot count as progress"
        },
        "phase5bb_direct_frontier_34": {
            "observed_phase": "5BA",
            "boundary_kind": "DIRECT_FRONTIER",
            "observed_caller": "0x0022B5EF",
            "root": "0x0022DDA4",
            "observed_fault": 0,
            "observed_esp": "0x008BFF14",
            "closure_depth": P5BB_DIRECT34_CLOSURE_DEPTH,
            "closure_cap": P5BB_DIRECT34_CLOSURE_CAP,
            "required_prior_state": "packed ICALL 0x0023D550 executed; trace reached 0x00238533, 0x00238507, 0x002384E0, 0x0022B5EF",
            "pass_policy": "0x0022DDA4 root must execute, maintained allocation call count must be nonzero, and old 0x0022DDA4 direct frontier cannot count as progress"
        },
        "phase5bb_manual_heap": {
            "mode": "support-owned maintained Xbox CRT heap family",
            "allocate": "0x0022DDA4",
            "free": "0x0022E51F",
            "reallocate": "0x0022E713",
            "arena_start": "0x008C1000",
            "arena_end": "0x009C0000",
            "alignment": 16,
            "zero_memory_flag": "0x00000008",
            "realloc_in_place_only_flag": "0x00000010",
            "source_policy": "reuse Phase-4C deterministic title-heap allocator/free and add coherent realloc over the same block table",
            "pack_policy": "all three reviewed Recompile.ps1 manual functions are support-owned and packed together"
        },
        "phase5bb_symbolic_link_object": {
            "open_target": "0x800000CB",
            "open_ordinal": 203,
            "open_name": "NtOpenSymbolicLinkObject",
            "open_arg_bytes": 8,
            "open_frame_bytes": 12,
            "observed_open_caller": "0x0022B7B2",
            "observed_open_path": "\\??\\D:",
            "observed_open_target": "\\Device\\CdRom0",
            "query_target": "0x800000D7",
            "query_ordinal": 215,
            "query_name": "NtQuerySymbolicLinkObject",
            "query_arg_bytes": 12,
            "query_frame_bytes": 16,
            "handle_tag": "0x53000000",
            "mode": "guest symbolic-link object table",
            "open_policy": "open only links already created by IoCreateSymbolicLink; return OBJECT_NAME_NOT_FOUND for unknown names",
            "query_policy": "return the exact target snapshot associated with the opened link handle using Xbox ANSI_STRING length semantics",
            "close_policy": "NtClose recognizes and releases symbolic-link object tokens without calling host CloseHandle",
            "query_saved_esp_repair": {
                "caller": "0x0022B7B2",
                "target": "0x800000D7",
                "observed_frame_bytes": 20,
                "abi_frame_bytes": 16,
                "resume_adjustment": -4,
                "validation": "return slot zero, valid 0x53 symbolic-link handle, non-null bounded ANSI_STRING buffer",
                "policy": "repair only the exact hardware-observed caller/frame; retain ordinal 215 three-argument Xbox ABI"
            }
        },
        "phase5bb_cache_storage": {
            "partition0_size": 524288,
            "partition0_mode": "bounded in-memory read/write config device",
            "observed_write_offset": "0x00000800",
            "observed_write_length": 512,
            "cache_partition_mappings": {
                "3": "game:\\merc360-partition3",
                "4": "game:\\merc360-partition4",
                "5": "game:\\merc360-partition5"
            },
            "translated_frontier": "0x0022C5C6",
            "closure_depth": P5AN_FRONTIER_CLOSURE_DEPTH,
            "closure_cap": P5AN_FRONTIER_CLOSURE_CAP
        },
        "phase5bb_disk_identity": {
            "cache_partition_count": 3,
            "cache_partition_export_va": "0x0087E4A0",
            "model_string_va": "0x0087E420",
            "model_buffer_va": "0x0087E430",
            "serial_string_va": "0x0087E460",
            "serial_buffer_va": "0x0087E470",
            "model": "MERC360 VIRTUAL HDD",
            "serial": "MERC3600000000001",
            "privacy": "synthetic guest identity; no host disk identity exposed"
        },
        "phase5bb_memory_cluster": {
            "enabled_ordinals": [165,166,167,171,172,173,175,176,177,178,179,180,181,182,183,184,199],
            "fenced_ordinals": [168],
            "policy": "batch production-backed guest-safe allocation/persistence/protection/map-unmap/free semantics; keep RAMIN claim fenced"
        },
        "phase5bb_partition0_config": {
            "size": 524288,
            "backing": "zero-initialized in-memory fixed-structure config area",
            "read_scope": "all bounded synchronous reads within 0x00000000-0x0007FFFF",
            "observed_probe_offset": "0x00000800",
            "observed_probe_length": 512,
            "hal_return_policy": "trap and log routine/LaunchDataPage; never execute firmware return in diagnostic harness"
        },
        "data_thunk_fixups": [
            {"ordinal": 40, "name": "HalDiskCachePartitionCount", "guest_data_va": "0x0087E4A0", "initial_value": 3},
            {"ordinal": 41, "name": "HalDiskModelNumber", "guest_data_va": "0x0087E420", "optional_import": True},
            {"ordinal": 42, "name": "HalDiskSerialNumber", "guest_data_va": "0x0087E460", "optional_import": True},
            {"ordinal": 156, "name": "KeTickCount", "guest_data_va": "0x0087E020"},
            {"ordinal": 164, "name": "LaunchDataPage", "guest_data_va": "0x0087E030", "initial_value": "NULL"},
            {"ordinal": 322, "name": "XboxHardwareInfo", "guest_data_va": "0x0087E000"},
            {"ordinal": 324, "name": "XboxKrnlVersion", "guest_data_va": "0x0087E010"},
            {"ordinal": 326, "name": "XeImageFileName", "guest_data_va": "0x0087E040", "buffer_va": "0x0087E050", "value": "\\Device\\CdRom0\\default.xbe"},
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
        "unknown_direct_helper_contexts": unknown_contexts,
        "members": [f"0x{va:08X}" for va in member_vas],
    }
    (args.out_dir / "phase5bb-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    if unknown:
        print("[Phase5BB] NON-DIRECT unresolved helper dependencies remain:")
        for owner, names in unknown.items():
            print(f"[Phase5BB]   {owner}: {', '.join(names)}")
            for item in unknown_contexts.get(owner, []):
                print(
                    f"[Phase5BB]     CALL CONTEXT helper={item['helper']} "
                    f"lines={item['first_line']}-{item['last_line']}"
                )
                for context_line in item["context"].splitlines():
                    print(f"[Phase5BB]       {context_line}")
        print(
            "[Phase5BB] Direct sub_XXXXXXXX callees have already been converted "
            "to DIRECT_FRONTIER boundaries; entries listed above are true support "
            "dependencies and are not safe to guess."
        )
        print(
            "[Phase5BB] EMIT RESULT: BLOCKED_BY_SUPPORT_DEPENDENCY"
        )
        return 3

    env_source = base.build_env_source(
        args.phase2e_source.read_text(encoding="utf-8")
    ).replace("PHASE 4C-B", "PHASE 5BB")
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
        env_source = env_source.replace(stale_phase, "PHASE 5BB")
    env_source += """
extern "C" DWORD phase5bb_env_build_cookie(void)
{
    return 0x50354242u; /* P5BB */
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
        env_source = env_source.replace(stale_phase, "PHASE 5BB")

    driver = base.driver_source(root_name, root_va, len(member_vas))
    driver = driver.replace(
        "P4C-STARTUP-20261019-A",
        "P5BB-FRONTIER22DDA4-20261020-A",
    )
    driver = driver.replace(
        "Policy: execute the real retail entry and stop at the first live dynamic/indirect boundary",
        "Policy: retain P5AM disk-data proof, add bounded Partition0 writeback, map cache Partition3/4/5, and execute a depth-2 closure rooted at 0022C5C6",
    )
    driver = driver.replace("PHASE 4C-B", "PHASE 5BB")
    cookie_decl = 'extern "C" DWORD phase4c_env_entry(void);\n'
    if cookie_decl not in driver:
        raise SystemExit("[Phase5BB] env-entry declaration marker changed")
    driver = driver.replace(
        cookie_decl,
        cookie_decl + 'extern "C" DWORD phase5bb_env_build_cookie(void);\n',
        1,
    )
    env_pass_marker = """    trace("PHASE 5BB ENVIRONMENT RESULT: PASS");

    g_ram = phase4c_env_guest_base();"""
    if env_pass_marker not in driver:
        raise SystemExit("[Phase5BB] environment PASS marker changed")
    driver = driver.replace(
        env_pass_marker,
        """    if (phase5bb_env_build_cookie() != 0x50354242u)
    {
        trace("FAIL: Phase 5BB environment build cookie mismatch");
        goto shutdown_env;
    }
    trace("PASS: Phase 5BB main/env build cookie matches");
    trace("PHASE 5BB ENVIRONMENT RESULT: PASS");

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
        "    s_phase5ahPartition0OpenSuccessCount = 0u;\n"
        "    s_phase5ahNtStatusMapCount = 0u;\n"        "    s_phase5bbMmCallCount = 0u;\n"
        "    s_phase5bbMmAllocSuccessCount = 0u;\n"
        "    s_phase5bbMmFreeCount = 0u;\n"
        "    s_phase5bbMmLastOrdinal = 0u;\n"
        "    s_phase5bbMmLastBase = 0u;\n"
        "    s_phase5bbMmLastSize = 0u;\n"        "    s_phase5bbMmPersistCount = 0u;\n"
        "    s_phase5bbMmIoMapCount = 0u;\n"
        "    s_phase5bbMmIoUnmapCount = 0u;\n"
        "    s_phase5bbNtFreeVirtualCount = 0u;\n"
        "    s_phase5bbNtFreeVirtualSuccessCount = 0u;\n"        "    s_phase5bbPartition0BackingLoaded = 0u;\n"
        "    s_phase5bbPartition0BackingLoadBytes = 0u;\n"
        "    s_phase5bbPartition0BackingFlushCount = 0u;\n"
        "    s_phase5bbPartition0BackingFlushBytes = 0u;\n"
        "    s_phase5bbPartition0ChangedWriteCount = 0u;\n"
        "    s_phase5bbPartition0UnchangedWriteCount = 0u;\n"
        "    s_phase5bbPartition0BackingReady = 0u;\n"
        "    s_phase5bbPartition0RawReadCount = 0u;\n"
        "    s_phase5bbPartition0RawReadBytes = 0u;\n"        "    s_phase5bbPartition0RawWriteCount = 0u;\n"
        "    s_phase5bbPartition0RawWriteBytes = 0u;\n"
        "    s_phase5bbCacheRootOpenCount = 0u;\n"        "    s_phase5bbNtDeviceIoControlCallCount = 0u;\n"
        "    s_phase5bbNtDeviceIoControlSuccessCount = 0u;\n"
        "    s_phase5bbNtDeviceIoControlGeometryCount = 0u;\n"
        "    s_phase5bbNtDeviceIoControlPartitionInfoCount = 0u;\n"
        "    s_phase5bbNtDeviceIoControlUnknownCount = 0u;\n"
        "    s_phase5bbNtDeviceIoControlLastCode = 0u;\n"
        "    s_phase5bbNtDeviceIoControlLastStatus = 0u;\n"
        "    s_phase5bbHalReturnTrapCount = 0u;\n"
        "    s_phase5bbHalReturnRoutine = 0u;\n"
        "    s_phase5bbHalReturnLaunchPage = 0u;\n"        "    s_phase5bbDiskIdentityDataReady = 0u;\n"
        "    s_phase5bbDiskIdentitySeen40 = 0u;\n"
        "    s_phase5bbDiskIdentitySeen41 = 0u;\n"
        "    s_phase5bbDiskIdentitySeen42 = 0u;\n"        "    s_phase5bbXeImageFileNameReady = 0u;\n"
        "    s_phase5bbXeImageFileNameSeen326 = 0u;\n"        "    ZeroMemory(s_phase5bbAudioFallback, sizeof(s_phase5bbAudioFallback));\n"
        "    s_phase5bbAudioFallbackAttemptCount = 0u;\n"
        "    s_phase5bbAudioFallbackSuccessCount = 0u;\n"
        "    s_phase5bbAudioFallbackFreeCount = 0u;\n"
        "    s_phase5bbAudioAllocFailureTestCount = 0u;\n"
        "    s_phase5bbCachePrepareCallCount = 0u;\n"
        "    s_phase5bbCachePrepareReadyCount = 0u;\n"
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
        "    s_phase5hNtCreateFileSuccessCount = 0u;\n"        "    s_phase5bbNtCreateFileObDosDevicesCount = 0u;\n"
        "    s_phase5bbNtCreateFileObDosDevicesMappedCount = 0u;\n"
        "    s_phase5bbNtCreateFileObDosDevicesSuccessCount = 0u;\n"
        "    s_phase5bbNtOpenFileObDosDevicesCount = 0u;\n"
        "    s_phase5bbNtOpenFileObDosDevicesMappedCount = 0u;\n"
        "    s_phase5hNtReadFileCallCount = 0u;\n"
        "    s_phase5hNtReadFileSuccessCount = 0u;\n"
        "    s_phase5ahNtWriteFileCallCount = 0u;\n"
        "    s_phase5ahNtWriteFileSuccessCount = 0u;\n"
        "    s_phase5ahNtWriteFileLastBytes = 0u;\n"
        "    s_phase5ahNtWriteFileLastStatus = 0u;\n"
        "    s_phase5ahNtWriteFileSavedEspRepairCount = 0u;\n"
        "    s_phase5ahNtWriteFileSavedEspRepairSuccessCount = 0u;\n"
        "    s_phase5ahNtWriteFileSavedEspRepairLastBytes = 0u;\n"
        "    s_phase5ahNtWriteFileSavedEspRepairLastResumeEsp = 0u;\n"
        "    s_phase5ahNtWriteFileSavedEspRepairLastImageIndex = 0xFFFFFFFFu;\n"
        "    s_phase5ahNtWriteFileXsImageSuccessCount = 0u;\n"
        "    s_phase5ahRoot22BDA5Entered = 0;\n"
        "    s_phase5ahRoot22F08DEntered = 0;\n"
        "    s_phase5ahRoot22F0CCEntered = 0;\n"
        "    s_phase5ahRoot22F0AEEntered = 0;\n"
        "    s_phase5ahRoot22A604Entered = 0;\n"
        "    s_phase5ahRoot22A3B9Entered = 0;\n"        "    s_phase5bbRoot22C5C6Entered = 0;\n"        "    s_phase5bbRoot22F0D6Entered = 0;\n"        "    s_phase5bbRoot22BBC8Entered = 0;\n"        "    s_phase5bbRoot23E600Entered = 0;\n"        "    s_phase5bbRoot23D550Entered = 0;\n"
        "    s_phase5bbPackedIcall23D550Count = 0u;\n"
        "    s_phase5bbPackedIcall23D550LastSavedEsp = 0u;\n"        "    s_phase5bbRoot22DDA4Entered = 0;\n"        "    s_phase5bbManualHeapAllocCount = 0u;\n"
        "    s_phase5bbManualHeapFreeCount = 0u;\n"
        "    s_phase5bbManualHeapReallocCount = 0u;\n"
        "    s_phase5bbManualHeapLastHeap = 0u;\n"
        "    s_phase5bbManualHeapLastFlags = 0u;\n"
        "    s_phase5bbManualHeapLastSize = 0u;\n"
        "    s_phase5bbManualHeapLastResult = 0u;\n"        "    s_phase5bbNtOpenSymbolicLinkCallCount = 0u;\n"
        "    s_phase5bbNtOpenSymbolicLinkSuccessCount = 0u;\n"
        "    s_phase5bbNtOpenSymbolicLinkDDriveSuccessCount = 0u;\n"
        "    s_phase5bbNtOpenSymbolicLinkLastToken = 0u;\n"
        "    s_phase5bbNtQuerySymbolicLinkCallCount = 0u;\n"
        "    s_phase5bbNtQuerySymbolicLinkSuccessCount = 0u;\n"
        "    s_phase5bbNtQuerySymbolicLinkLastLength = 0u;\n"
        "    s_phase5bbNtQuerySymbolicLinkSavedEspRepairCount = 0u;\n"
        "    s_phase5bbNtQuerySymbolicLinkSavedEspRepairExtra = 0u;\n"
        "    s_phase5bbSymbolicLinkCloseCount = 0u;\n"
        "    s_phase5ahXeLoadSectionCallCount = 0u;\n"
        "    s_phase5ahXeLoadSectionSuccessCount = 0u;\n"
        "    s_phase5ahXeLoadSectionLastSectionVa = 0u;\n"
        "    s_phase5ahXeLoadSectionLastIndex = 0u;\n"
        "    s_phase5ahXeLoadSectionLastRefCount = 0u;\n"
        "    s_phase5ahXeUnloadSectionCallCount = 0u;\n"
        "    s_phase5ahXeUnloadSectionSuccessCount = 0u;\n"
        "    s_phase5ahXeUnloadSectionLastSectionVa = 0u;\n"
        "    s_phase5ahXeUnloadSectionLastIndex = 0u;\n"
        "    s_phase5ahXeUnloadSectionLastRefCount = 0u;\n"
        "    s_phase5iRtlInitAnsiStringCount = 0u;\n"
        "    s_phase5iRtlInitAnsiStringLastLength = 0u;\n"
        "    s_phase5iRtlInitAnsiStringLastDestination = 0u;\n"
        "    s_phase5iRtlInitAnsiStringLastSource = 0u;\n"        "    s_phase5bbRtlInitAnsiSavedEspRepairCount = 0u;\n"
        "    s_phase5bbRtlInitAnsiSavedEspRepairExtra = 0u;\n"
        "    s_phase5bbRtlInitAnsiSavedEspRepairLastResumeEsp = 0u;\n"
        "    s_phase5kRtlEqualStringCount = 0u;\n"
        "    s_phase5kRtlEqualStringTrueCount = 0u;\n"
        "    s_phase5kRtlEqualStringLastString1 = 0u;\n"
        "    s_phase5kRtlEqualStringLastString2 = 0u;\n"
        "    s_phase5kRtlEqualStringLastCaseInsensitive = 0u;\n"
        "    s_phase5kRtlEqualStringLastResult = 0u;\n"
        "    s_phase5ahXboxLastError = 0u;\n"
        "    s_phase5ahSetLastErrorCount = 0u;\n"
        "    s_phase5ahNtQueryInformationFileCallCount = 0u;\n"
        "    s_phase5ahNtQueryInformationFileSuccessCount = 0u;\n"
        "    s_phase5ahNtQueryInformationFileLastClass = 0u;\n"
        "    ZeroMemory(s_phase5dSymbolicLinks, sizeof(s_phase5dSymbolicLinks));\n"
        "    ZeroMemory(s_phase5bbSymbolicLinkHandles, sizeof(s_phase5bbSymbolicLinkHandles));\n"
        "    ZeroMemory(s_phase5bHandles, sizeof(s_phase5bHandles));\n"
        "    ZeroMemory(s_phase5bHandlePaths, sizeof(s_phase5bHandlePaths));\n",
        1,
    )
    driver = driver.replace(
        "    phase4c_reset_architecture();\n",
        "    phase4c_reset_architecture();\n\n"
        "    if (!phase5bb_partition0_backing_load())\n"
        "    {\n"
        "        trace(\"FAIL: Phase 5BB Partition0 backing initialization failed\");\n"
        "        goto shutdown_env;\n"
        "    }\n"
        "    trace(\"PASS: Phase 5BB Partition0 backing initialization complete\");\n"
        "    if (!phase4c_fix_startup_data_thunks())\n"
        "    {\n"
        "        trace(\"PHASE 5BB STARTUP DATA-THUNK PREP RESULT: FAIL\");\n"
        "        goto shutdown_env;\n"
        "    }\n"
        "    trace(\"PHASE 5BB STARTUP DATA-THUNK PREP RESULT: PASS\");\n"
        "    trace(\"PASS: hardware-observed direct target 0022C47B is packed for translated execution\");\n"
        "    if (!phase4c_init_kernel_header_page())\n"
        "    {\n"
        "        trace(\"PHASE 5BB KERNEL HEADER PREP RESULT: FAIL\");\n"
        "        goto shutdown_env;\n"
        "    }\n"
        "    trace(\"PHASE 5BB KERNEL HEADER PREP RESULT: PASS\");\n"
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
        "    trace(\"PASS: hardware-observed post-TitleMeta direct root 00239B78 is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed next post-TitleMeta direct root 0023DDDD is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed next post-TitleMeta direct root 0023DD7B is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed next post-TitleMeta direct root 0023DDA0 is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed next post-TitleMeta direct root 0023DD56 is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed next post-TitleMeta direct root 0023F8CB is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed post-write direct root 0022BDA5 is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed TitleImage-path direct root 0022F08D is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed post-XeLoadSection direct root 0022F0CC is packed for translated execution\");\n"
        "    trace(\"PASS: hardware-observed post-TitleImage-write direct root 0022F0AE is packed for translated execution\");\n"        "    trace(\"PASS: hardware-observed persistent-state direct root 0022A604 is packed for translated execution\");\n"        "    trace(\"PASS: hardware-observed next direct root 0022A3B9 is packed for translated execution\");\n"        "    trace(\"PASS: Phase 5BB cache-setup root 0022C5C6 plus bounded depth-2 closure is packed\");\n"        "    trace(\"PASS: Phase 5BB post-persistence root 0022F0D6 plus bounded depth-2/cap-16 closure is packed\");\n"        "    trace(\"PASS: Phase 5BB next frontier root 0022BBC8 plus bounded depth-2/cap-16 closure is packed\");\n"        "    trace(\"PASS: Phase 5BB live frontier root 0023E600 plus bounded depth-2/cap-16 closure is packed\");\n"        "    trace(\"PASS: Phase 5BB ICALL frontier root 0023D550 plus bounded depth-2/cap-16 closure is packed and dispatch armed\");\n"        "    trace(\"PASS: Phase 5BB direct frontier root 0022DDA4 plus bounded depth-2/cap-16 closure is packed\");\n"        "    trace(\"PASS: Phase 5BB maintained Xbox CRT heap family DDA4/E51F/E713 is support-owned and packed\");\n"        "    trace(\"PASS: Phase 5BB ordinals 203/215 NtOpenSymbolicLinkObject + NtQuerySymbolicLinkObject guest-object continuations armed\");\n"
        "    trace(\"PASS: Phase 5BB Partition0 config read/write device semantics armed\");\n"        "    trace(\"PASS: Phase 5BB Partition0 persistent backing armed at game:\\\\merc360-partition0\\\\partition0-config.bin\");\n"
        "    trace(\"PASS: Phase 5BB cache partition mappings armed for Partition3/4/5\");\n"        "    trace(\"PASS: Phase 5BB exact cache-root mappings armed for Partition3/4/5 (slash optional)\");\n"
        "    trace(\"PASS: Phase 5BB guest-safe Mm cluster armed: ordinals 165/166/167/171/172/173/175/176/177/178/179/180/181/182/183/184/199\");\n"
        "    trace(\"PASS: Phase 5BB hardware-sensitive Mm ordinal 168 remains fenced\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 196 NtDeviceIoControlFile cache continuation armed for IOCTL 00070000/00074004\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 202 NtOpenFile native continuation armed\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 218 NtQueryVolumeInformationFile native continuation armed\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 187 NtClose native continuation armed\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 67 IoCreateSymbolicLink native continuation armed\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 69 IoDeleteSymbolicLink native continuation armed\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 190 NtCreateFile native continuation armed\");\n"        "    trace(\"PASS: Phase 5BB Xbox ObDosDevices root FFFFFFFD support armed for NtCreateFile/NtOpenFile\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 219 NtReadFile synchronous continuation armed\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 236 NtWriteFile 36-byte native continuation armed\");\n"
        "    trace(\"PASS: Phase 5BB caller 0022F0CC NtWriteFile saved-ESP repair armed for proven $XTIMAGE/$XSIMAGE image-section frames\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 289 RtlInitAnsiString continuation armed\");\n"        "    trace(\"PASS: Phase 5BB caller 0022A7A4 RtlInitAnsiString saved-ESP repair armed\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 279 RtlEqualString continuation armed\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 211 NtQueryInformationFile class-34 native continuation armed\");\n"
        "    trace(\"PASS: Phase 5BB ordinal 327 XeLoadSection native bookkeeping continuation armed\");\n"        "    trace(\"PASS: Phase 5BB ordinal 328 XeUnloadSection native bookkeeping continuation armed\");\n",
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
        raise SystemExit("[Phase5BB] entry-return PASS marker changed")
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
            s_phase5bbNvQueryCount >= 2u &&
            s_phase4cNtStatusMapped &&

            s_phase4cTimerArmed &&
            s_phase4cVmAllocCount > 0u &&
            s_phase4cCriticalSectionInitCount > 0u &&
            s_phase5bNtOpenFileHandledCount > 0u &&
            s_phase5ahPartition0OpenSuccessCount > 0u &&
            s_phase5bbPartition0RawReadCount > 0u &&
            s_phase5hNtReadFileSuccessCount > 0u &&
            s_phase5bbPartition0BackingReady > 0u &&
            (
                (s_phase5bbPartition0RawWriteCount > 0u &&
                 s_phase5ahNtWriteFileSuccessCount > 0u &&
                 s_phase5bbPartition0BackingFlushCount > 0u) ||
                s_phase5bbPartition0BackingLoaded > 0u
            ) &&
            s_phase5bbDiskIdentityDataReady > 0u &&
            s_phase5bbDiskIdentitySeen40 == 1u &&
            s_phase5bbXeImageFileNameReady > 0u &&
            s_phase5bbXeImageFileNameSeen326 == 1u &&
            s_phase5bbPartition0BackingLoaded > 0u &&
            s_phase5bbPartition0UnchangedWriteCount > 0u &&
            s_phase5bbRoot22F0D6Entered &&
            s_phase5bbRoot22BBC8Entered &&
            s_phase5bbRoot23E600Entered &&
            s_phase5bbRoot23D550Entered &&
            s_phase5bbPackedIcall23D550Count > 0u &&
            s_phase5bbRoot22DDA4Entered &&
            s_phase5bbManualHeapAllocCount > 0u &&
            s_phase5bbNtOpenSymbolicLinkSuccessCount > 0u &&
            s_phase5bbNtOpenSymbolicLinkDDriveSuccessCount > 0u &&
            s_phase5bbNtQuerySymbolicLinkCallCount > 0u &&
            s_phase5bbNtQuerySymbolicLinkSuccessCount > 0u &&
            s_phase5bbNtQuerySymbolicLinkSavedEspRepairCount > 0u &&
            s_phase5bbCacheRootOpenCount > 0u &&
            s_phase5cVolumeQueryCount > 0u &&
            s_phase5dSymbolicLinkCreateCount > 0u &&
            s_phase5hNtCreateFileCallCount > 0u &&
            s_phase5bbNtCreateFileObDosDevicesMappedCount > 0u &&
            s_phase5ahRoot22A3B9Entered &&
            s_phase5iRtlInitAnsiStringCount > 0u &&
            s_phase5bbRtlInitAnsiSavedEspRepairCount > 0u &&
            s_phase5kRtlEqualStringCount > 0u &&
            s_phase5ahSetLastErrorCount > 0u &&
            s_phase5ahNtQueryInformationFileCallCount > 0u &&
            s_phase5ahNtQueryInformationFileSuccessCount > 0u &&
            s_phase5ahNtQueryInformationFileLastClass == 34u &&
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
                    s_phase4cFaultAddress != 0x8001003Cu &&
                    s_phase4cFaultAddress != 0x800000A4u &&
                    s_phase4cFaultAddress != 0x80000028u &&
                    s_phase4cFaultAddress != 0x80000146u
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
                         s_phase4cBoundaryTarget != 0x800000C4u &&
                         s_phase4cBoundaryTarget != 0x800000CAu &&
                         s_phase4cBoundaryTarget != 0x800000CBu &&
                         s_phase4cBoundaryTarget != 0x800000D7u &&
                         s_phase4cBoundaryTarget != 0x800000DAu &&
                         s_phase4cBoundaryTarget != 0x800000BBu &&
                         s_phase4cBoundaryTarget != 0x80000043u &&
                         s_phase4cBoundaryTarget != 0x80000045u &&
                         s_phase4cBoundaryTarget != 0x800000BEu &&
                         s_phase4cBoundaryTarget != 0x800000DBu &&
                         s_phase4cBoundaryTarget != 0x800000ECu &&
                         s_phase4cBoundaryTarget != 0x80000121u &&
                         s_phase4cBoundaryTarget != 0x80000117u &&
                         s_phase4cBoundaryTarget != 0x800000D3u &&
                         s_phase4cBoundaryTarget != 0x80000147u &&
                         s_phase4cBoundaryTarget != 0x80000148u) ||
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
                         s_phase4cBoundaryTarget != 0x0022B178u &&
                         s_phase4cBoundaryTarget != 0x00239B78u &&
                         s_phase4cBoundaryTarget != 0x0023DDDDu &&
                         s_phase4cBoundaryTarget != 0x0023DD7Bu &&
                         s_phase4cBoundaryTarget != 0x0023DDA0u &&
                         s_phase4cBoundaryTarget != 0x0023DD56u &&
                         s_phase4cBoundaryTarget != 0x0023F8CBu &&
                         s_phase4cBoundaryTarget != 0x0022BDA5u &&
                         s_phase4cBoundaryTarget != 0x0022F08Du &&
                         s_phase4cBoundaryTarget != 0x0022F0CCu &&
                         s_phase4cBoundaryTarget != 0x0022F0AEu &&
                         s_phase4cBoundaryTarget != 0x0022A604u &&
                         s_phase4cBoundaryTarget != 0x0022A3B9u &&
                         s_phase4cBoundaryTarget != 0x0022C5C6u &&
                         s_phase4cBoundaryTarget != 0x0022F0D6u &&
                         s_phase4cBoundaryTarget != 0x0022BBC8u &&
                         s_phase4cBoundaryTarget != 0x0023E600u &&
                         s_phase4cBoundaryTarget != 0x0023D550u &&
                         s_phase4cBoundaryTarget != 0x0022DDA4u) ||
                        (s_phase4cBoundaryKind == PHASE4C_BOUNDARY_TIMER_DUE &&
                         s_phase4cBoundaryTarget != 0u)
                    )
                )
            );"""
    if old_escape_pass not in driver:
        raise SystemExit("[Phase5BB] boundary PASS marker changed")
    driver = driver.replace(old_escape_pass, new_escape_pass)

    result_marker = "PHASE 5BB BOUNDED REAL STARTUP RESULT"
    if result_marker not in driver:
        raise SystemExit("[Phase5BB] generated result label marker changed")
    driver = driver.replace(
        result_marker,
        "PHASE 5BB POST-PERSIST CLOSURE RESULT",
    )
    arm_marker = f"""    if (escaped == 0)
    {{
        {root_name}();"""
    if arm_marker not in driver:
        raise SystemExit("[Phase5BB] setjmp execution-arm marker changed")
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
        raise SystemExit("[Phase5BB] setjmp escape marker changed")
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
        + "\n\n/* Phase 5BB: persistent Partition0 + cache-reboot handshake */\n"
        + "\n".join(forward_decls)
        + "\n\n"
        + pack_lookup_source(member_vas, generated)
        + "\n#pragma optimize(\"\", off)\n"
        + "\n\n".join(bodies)
        + "\n#pragma optimize(\"\", on)\n"
        + driver
    )

    b178_definition = "static void sub_0022B178(void)"
    phase5ah_state_decl = "static uint32_t s_phase5ahXboxLastError;"
    phase5ah_count_decl = "static uint32_t s_phase5ahSetLastErrorCount;"
    if generated_main.count(b178_definition) != 1:
        raise SystemExit(
            "[Phase5BB] generated main must contain exactly one support-owned "
            "sub_0022B178 definition"
        )
    if generated_main.count(phase5ah_state_decl) != 1 or generated_main.count(phase5ah_count_decl) != 1:
        raise SystemExit(
            "[Phase5BB] generated main must contain exactly one declaration "
            "for each Phase 5BB SetLastError state variable"
        )
    b178_index = generated_main.index(b178_definition)
    if generated_main.index(phase5ah_state_decl) > b178_index or generated_main.index(phase5ah_count_decl) > b178_index:
        raise SystemExit(
            "[Phase5BB] SetLastError state declarations must precede the "
            "support-owned B178 body"
        )
    if "s_phase4cLastError = GUEST_READ32(g_esp + 4u);" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost shared SetLastError runtime state"
        )
    if "PASS: Phase 5BB maintained SetLastError value=" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost maintained SetLastError instrumentation"
        )
    if "XeLoadSection LIVE FRAME:" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-327 live-frame instrumentation"
        )
    if "PASS: Phase 5BB XeLoadSection native continuation" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-327 native continuation"
        )
    if "XeUnloadSection LIVE FRAME:" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-328 live-frame instrumentation"
        )
    if "PASS: Phase 5BB XeUnloadSection native bookkeeping continuation" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-328 bookkeeping continuation"
        )
    if "s_phase5ahXeUnloadSectionSuccessCount" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-328 proof state"
        )
    for marker in (
        "NtCreateFile OBDOSDEVICES:",
        "PASS: Phase 5BB NtCreateFile ObDosDevices path expansion",
        "NtOpenFile OBDOSDEVICES:",
        "PASS: Phase 5BB NtOpenFile ObDosDevices path expansion",
        "s_phase5bbNtCreateFileObDosDevicesMappedCount > 0u",
        "PASS: Phase 5BB Xbox ObDosDevices root FFFFFFFD support armed for NtCreateFile/NtOpenFile",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost ObDosDevices marker: {marker}"
            )

    if "NtWriteFile SAVEDESP REPAIR PROBE:" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost caller-specific saved-ESP repair probe"
        )
    if "PASS: Phase 5BB NtWriteFile caller 0022F0CC saved-ESP repair image=" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost image-section saved-ESP repair marker"
        )
    if "s_phase5ahNtWriteFileXsImageSuccessCount" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost $XSIMAGE write proof state"
        )
    if "phase5ah_path_ends_with_ci" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost compact-write file-path guard"
        )
    if "NtWriteFile LIVE FRAME:" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-236 live-frame instrumentation"
        )
    if "PASS: Phase 5BB NtWriteFile native continuation" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-236 native continuation"
        )
    if "WriteFile(" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost native WriteFile primitive"
        )
    if "NtQueryInformationFile NATIVE:" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-211 native continuation"
        )
    if "GetFileAttributesExA" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost native class-34 metadata source"
        )
    if "s_phase5bHandlePaths" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost tagged-handle path bookkeeping"
        )
    if "PHASE4C_BOUNDARY_FILE_INFORMATION" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost FILE_INFORMATION boundary"
        )
    for marker in (
        "RtlInitAnsiString SAVEDESP REPAIR PROBE:",
        "PASS: Phase 5BB RtlInitAnsiString caller 0022A7A4 saved-ESP repair",
        "s_phase5bbRtlInitAnsiSavedEspRepairCount > 0u",
        "PASS: Phase 5BB caller 0022A7A4 RtlInitAnsiString saved-ESP repair armed",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost RtlInitAnsiString repair marker: {marker}"
            )

    if "sub_00239B78" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained root sub_00239B78"
        )
    retained_18_name = generated[LIVE_DIRECT_FRONTIER_TARGET_18]["name"]
    if retained_18_name not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained root "
            + retained_18_name
        )
    retained_19_name = generated[LIVE_DIRECT_FRONTIER_TARGET_19]["name"]
    if retained_19_name not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained root "
            + retained_19_name
        )
    retained_20_name = generated[LIVE_DIRECT_FRONTIER_TARGET_20]["name"]
    if retained_20_name not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained root "
            + retained_20_name
        )
    retained_21_name = generated[LIVE_DIRECT_FRONTIER_TARGET_21]["name"]
    if retained_21_name not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained root "
            + retained_21_name
        )
    retained_22_name = generated[LIVE_DIRECT_FRONTIER_TARGET_22]["name"]
    if retained_22_name not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained root "
            + retained_22_name
        )
    retained_23_name = generated[LIVE_DIRECT_FRONTIER_TARGET_23]["name"]
    if retained_23_name not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained root "
            + retained_23_name
        )
    retained_24_name = generated[LIVE_DIRECT_FRONTIER_TARGET_24]["name"]
    if retained_24_name not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained root "
            + retained_24_name
        )
    retained_25_name = generated[LIVE_DIRECT_FRONTIER_TARGET_25]["name"]
    if retained_25_name not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained root "
            + retained_25_name
        )
    retained_26_name = generated[LIVE_DIRECT_FRONTIER_TARGET_26]["name"]
    if retained_26_name not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained root "
            + retained_26_name
        )
    retained_27_name = generated[LIVE_DIRECT_FRONTIER_TARGET_27]["name"]
    if retained_27_name not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained root "
            + retained_27_name
        )
    promoted_28_name = generated[LIVE_DIRECT_FRONTIER_TARGET_28]["name"]
    if promoted_28_name not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost promoted root "
            + promoted_28_name
        )
    if "s_phase5ahRoot22BDA5Entered = 1;" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained 0x0022BDA5 instrumentation"
        )
    if "s_phase5ahRoot22F08DEntered = 1;" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained 0x0022F08D instrumentation"
        )
    if "s_phase5ahRoot22F0CCEntered = 1;" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained 0x0022F0CC instrumentation"
        )
    if "s_phase5ahRoot22F0AEEntered = 1;" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained 0x0022F0AE instrumentation"
        )
    if "s_phase5ahRoot22A604Entered = 1;" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost retained 0x0022A604 instrumentation"
        )
    if "s_phase5ahRoot22A3B9Entered = 1;" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost 0x0022A3B9 execution proof instrumentation"
        )
    if "s_phase5ahRoot22A3B9Entered &&" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost 0x0022A3B9 PASS gate"
        )
    if "_phase4c_target == 0x8000012Du)" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost repeatable ordinal-301 dispatch"
        )
    # P5AL deliberately removes the P5AH/P5AK "second ordinal-301 must
    # execute" PASS gate. A successful Partition0 raw read should avoid the
    # STATUS_UNSUCCESSFUL -> RtlNtStatusToDosError recovery path entirely.
    # Keep the repeatable ordinal-301 implementation/mapping available as a
    # retained regression path, but prove P5AL with the config-device read.
    if "s_phase5bbPartition0RawReadCount > 0u" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost Partition0 raw-read hardware gate"
        )
    if "s_phase5hNtReadFileSuccessCount > 0u" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost successful NtReadFile hardware gate"
        )
    if "case 40u:  return 0x0087E4A0u; /* HalDiskCachePartitionCount */" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-40 data-thunk mapping"
        )
    if "case 41u:  return 0x0087E420u; /* HalDiskModelNumber STRING */" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-41 data-thunk mapping"
        )
    if "case 42u:  return 0x0087E460u; /* HalDiskSerialNumber STRING */" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-42 data-thunk mapping"
        )
    if "s_phase5bbDiskIdentitySeen40 == 1u" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost ordinal-40 hardware PASS gate"
        )
    if "s_phase4cFaultAddress != 0x80000028u" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main still accepts raw ordinal-40 token fault"
        )
    if "PASS: Phase 5BB disk identity data initialized cache_partitions=3" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost disk-identity initialization proof"
        )
    if "case 0xC0000001u: dosError = 31u;" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost STATUS_UNSUCCESSFUL -> ERROR_GEN_FAILURE mapping"
        )
    if "s_phase5bbNvQueryCount >= 2u" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost repeatable ordinal-24 hardware gate"
        )
    if "PASS: Phase 5BB ordinal 24 ExQueryNonVolatileSetting repeatable guest EEPROM semantics" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost repeatable ordinal-24 instrumentation"
        )
    if "PASS: Phase 5BB ordinal 301 RtlNtStatusToDosError repeatable mapping" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost repeatable ordinal-301 instrumentation"
        )

    for marker in (
        "int recomp_test_audio_alloc_failure(uint32_t attributes)",
        "uint32_t recomp_audio_pool_fallback(uint32_t size, uint32_t attributes)",
        "int recomp_audio_pool_free(uint32_t ptr)",
        "int recomp_prepare_empty_cache_volume(void)",
        "PASS: Phase 5BB cache prep helper",
        "PASS: Phase 5BB audio pool fallback",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost support shim marker: {marker}"
            )

    for marker in (
        "static int phase5bb_partition0_backing_load(void);",
        "static int phase5bb_partition0_backing_flush(void);",
        "static int phase5bb_partition0_backing_load(void)",
        "static int phase5bb_partition0_backing_flush(void)",
        "partition0-config.bin",
        "Partition0 backing NEW",
        "Partition0 backing LOADED",
        "Partition0 backing FLUSHED",
        "changed_writes=%u",
        "s_phase5bbPartition0BackingReady > 0u",
        "phase4c_reset_architecture();\n\n    if (!phase5bb_partition0_backing_load())",
        "PASS: Phase 5BB Partition0 backing initialization complete",
        "static void phase5bb_nt_device_io_control_file(uint32_t savedEsp)",
        "_phase4c_target == 0x800000C4u",
        "NtDeviceIoControlFile LIVE FRAME:",
        "NtDeviceIoControlFile FRAME52 RAW0:",
        "NtDeviceIoControlFile FRAME52 RAW1:",
        "NtDeviceIoControlFile FRAME52 AMBIGUOUS:",
        "expected=44-or-52",
        "arg_offset=%u",
        "code=%08X",
        "0x00070000u",
        "0x00074004u",
        "s_phase5bbPartition0BackingLoaded > 0u",
        "s_phase5bbPartition0UnchangedWriteCount > 0u",
        "s_phase4cBoundaryTarget != 0x800000C4u",
        "PASS: Phase 5BB NtDeviceIoControlFile cache continuation",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost ordinal-196 marker: {marker}"
            )

    if "PASS: Phase 5BB Partition0 config raw write offset=" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost Partition0 config raw-write continuation"
        )
    if "s_phase5bbPartition0RawWriteCount > 0u" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost Partition0 raw-write PASS gate"
        )
    if "s_phase5bbRoot22C5C6Entered" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main lost promoted cache-root instrumentation"
        )
    for marker in (
        "_phase4c_target == 0x800000CBu",
        "_phase4c_target == 0x800000D7u",
        "phase5bb_nt_open_symbolic_link_object",
        "phase5bb_nt_query_symbolic_link_object",
        "PHASE5AU_SYMLINK_HANDLE_TAG 0x53000000u",
        "PASS: Phase 5BB NtOpenSymbolicLinkObject guest-object continuation",
        "PASS: Phase 5BB NtQuerySymbolicLinkObject guest-object continuation",
        "s_phase5bbNtOpenSymbolicLinkDDriveSuccessCount > 0u",
        "s_phase5bbNtQuerySymbolicLinkCallCount > 0u",
        "s_phase5bbNtQuerySymbolicLinkSuccessCount > 0u",
        "s_phase5bbNtQuerySymbolicLinkSavedEspRepairCount > 0u",
        "NtQuerySymbolicLinkObject SAVEDESP REPAIR PROBE:",
        "PASS: Phase 5BB NtQuerySymbolicLinkObject caller 0022B7B2 saved-ESP repair",
        "s_phase4cBoundaryTarget != 0x800000CBu",
        "s_phase4cBoundaryTarget != 0x800000D7u",
        "PASS: Phase 5BB ordinals 203/215 NtOpenSymbolicLinkObject + NtQuerySymbolicLinkObject guest-object continuations armed",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost symbolic-link-object marker: {marker}"
            )

    for marker in (
        "case 0x0022BBC8u: return sub_0022BBC8;",
        "s_phase5bbRoot22BBC8Entered = 1;",
        "s_phase5bbRoot22BBC8Entered",
        "s_phase5bbNvQueryCount >= 2u",
        "s_phase4cBoundaryTarget != 0x0022BBC8u",
        "PASS: Phase 5BB next frontier root 0022BBC8 plus bounded depth-2/cap-16 closure is packed",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost next-frontier marker: {marker}"
            )

    for marker in (
        "case 0x0023E600u: return sub_0023E600;",
        "s_phase5bbRoot23E600Entered = 1;",
        "s_phase5bbRoot23E600Entered",
        "s_phase4cBoundaryTarget != 0x0023E600u",
        "PASS: Phase 5BB live frontier root 0023E600 plus bounded depth-2/cap-16 closure is packed",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost live-frontier marker: {marker}"
            )

    for marker in (
        "case 0x0023D550u: return sub_0023D550;",
        "_phase4c_target == 0x0023D550u",
        "PASS: Phase 5BB ICALL_SAFE 0022C452 -> 0023D550 entering packed translated target",
        "s_phase5bbRoot23D550Entered = 1;",
        "s_phase5bbRoot23D550Entered",
        "s_phase5bbPackedIcall23D550Count > 0u",
        "s_phase4cBoundaryTarget != 0x0023D550u",
        "PASS: Phase 5BB ICALL frontier root 0023D550 plus bounded depth-2/cap-16 closure is packed and dispatch armed",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost ICALL-frontier marker: {marker}"
            )

    for marker in (
        "case 0x0022DDA4u: return sub_0022DDA4;",
        "case 0x0022E51Fu: return sub_0022E51F;",
        "case 0x0022E713u: return sub_0022E713;",
        "s_phase5bbRoot22DDA4Entered = 1;",
        "s_phase5bbRoot22DDA4Entered",
        "s_phase5bbManualHeapAllocCount > 0u",
        "PASS: Phase 5BB maintained RtlAllocateHeap",
        "PASS: Phase 5BB maintained RtlFreeHeap",
        "PASS: Phase 5BB maintained RtlReAllocateHeap",
        "s_phase4cBoundaryTarget != 0x0022DDA4u",
        "PASS: Phase 5BB direct frontier root 0022DDA4 plus bounded depth-2/cap-16 closure is packed",
        "PASS: Phase 5BB maintained Xbox CRT heap family DDA4/E51F/E713 is support-owned and packed",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost direct34-frontier marker: {marker}"
            )

    for marker in (
        "case 0x0022F0D6u: return sub_0022F0D6;",
        "s_phase5bbRoot22F0D6Entered = 1;",
        "s_phase5bbPartition0BackingLoaded > 0u",
        "s_phase5bbPartition0UnchangedWriteCount > 0u",
        "s_phase5bbRoot22F0D6Entered",
        "s_phase4cBoundaryTarget != 0x0022F0D6u",
        "PASS: Phase 5BB post-persistence root 0022F0D6 plus bounded depth-2/cap-16 closure is packed",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost post-persistence frontier marker: {marker}"
            )
    for marker in (
        'partition3Root[] = "\\\\Device\\\\Harddisk0\\\\partition3"',
        'partition4Root[] = "\\\\Device\\\\Harddisk0\\\\partition4"',
        'partition5Root[] = "\\\\Device\\\\Harddisk0\\\\partition5"',
        "s_phase5bbCacheRootOpenCount > 0u",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost exact cache-root marker: {marker}"
            )
    if "s_phase4cBoundaryTarget != 0x0022C5C6u" not in generated_main:
        raise SystemExit(
            "[Phase5BB] generated main still accepts old 0x0022C5C6 frontier"
        )
    # generated_main is C/C++ source text, so path separators appear
    # escaped as two backslashes in the string literal. Use raw Python
    # markers here; manifest/runtime path checks intentionally use one slash.
    for marker in (
        r"game:\\merc360-partition3",
        r"game:\\merc360-partition4",
        r"game:\\merc360-partition5",
    ):
        if marker not in generated_main:
            raise SystemExit(
                f"[Phase5BB] generated main lost cache mapping {marker}"
            )

    (args.out_dir / "main.cpp").write_text(generated_main, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_source, encoding="utf-8")

    print("[Phase5BB] POST-PERSIST CLOSURE PACKAGE READY")
    print(
        f"[Phase5BB] Entry closure={len(entry_members)} bodies; "
        f"thread closure={len(thread_members)} bodies; "
        f"union={len(member_vas)} bodies"
    )
    print(
        f"[Phase5BB] Callback depth-{CALLBACK_DIRECT_DEPTH} slice: "
        f"{len(callback_members)} bodies; "
        f"new beyond proven entry/thread pack="
        f"{len(callback_members - entry_members - thread_members)}"
    )
    print(
        f"[Phase5BB] Static direct frontier targets: "
        f"{len(direct_frontier_targets)}"
    )
    print(
        "[Phase5BB] Previously promoted hardware direct target: 0x0022C47B"
    )
    print(
        "[Phase5BB] Newly promoted hardware direct target: 0x0022F128 "
        "(only this new frontier member is added)"
    )
    print(
        "[Phase5BB] Continued hardware kernel target: "
        "0x8000002F ordinal 47 HalRegisterShutdownNotification"
    )
    print(
        "[Phase5BB] Continued hardware kernel target: "
        "0x8000006B ordinal 107 KeInitializeDpc"
    )
    print(
        "[Phase5BB] Continued hardware kernel target: "
        "0x80000071 ordinal 113 KeInitializeTimerEx"
    )
    print(
        "[Phase5BB] Newly continued hardware kernel tail target: "
        "0x80000018 ordinal 24 ExQueryNonVolatileSetting"
    )
    print(
        "[Phase5BB] Newly continued hardware kernel target: "
        "0x8000012D ordinal 301 RtlNtStatusToDosError"
    )
    print(
        f"[Phase5BB] Previous promoted direct closure root: 0x{LIVE_DIRECT_FRONTIER_TARGET_5:08X}; "
        f"members={len(previous_promoted_closure_members)}"
    )
    print(
        f"[Phase5BB] Prior safe-root target: 0x{LIVE_DIRECT_FRONTIER_TARGET_6:08X}; "
        f"members={len(prior_safe_root_members)}"
    )
    print(
        f"[Phase5BB] New maintained-manual hardware root: 0x{LIVE_DIRECT_FRONTIER_TARGET_16:08X}; "
        f"depth={PROMOTED_CLOSURE_DEPTH}; members={len(promoted_closure_members)}"
    )
    print(
        "[Phase5BB] New post-storage root members: "
        + ", ".join(f"0x{va:08X}" for va in sorted(promoted_closure_members))
    )
    print(
        "[Phase5BB] Newly continued hardware kernel target: "
        "0x80000095 ordinal 149 KeSetTimer"
    )
    print(
        "[Phase5BB] Newly promoted hardware direct target: "
        "0x0022C5A4 (previously promoted)"
    )
    print(
        "[Phase5BB] Newly promoted hardware direct target: "
        "0x00230060 (only this new frontier member is added)"
    )
    print(
        f"[Phase5BB] Batched cache frontier root: 0x{LIVE_DIRECT_FRONTIER_TARGET_29:08X}; "
        f"depth={P5AN_FRONTIER_CLOSURE_DEPTH}; members={len(phase5bb_cache_frontier_members)}"
    )
    print(
        "[Phase5BB] Cache frontier members: "
        + ", ".join(f"0x{va:08X}" for va in sorted(phase5bb_cache_frontier_members))
    )
    print(
        f"[Phase5BB] Post-persistence frontier root: 0x{LIVE_DIRECT_FRONTIER_TARGET_30:08X}; "
        f"depth={P5BB_FRONTIER_CLOSURE_DEPTH}; members={len(phase5bb_post_persist_members)}"
    )
    print(
        f"[Phase5BB] Live hardware frontier root: 0x{LIVE_DIRECT_FRONTIER_TARGET_32:08X}; "
        f"caller=0x00239D6C depth={P5BB_LIVE_FRONTIER_CLOSURE_DEPTH}; "
        f"members={len(phase5bb_live_frontier_members)}"
    )
    print(
        "[Phase5BB] Live frontier members: "
        + ", ".join(f"0x{va:08X}" for va in sorted(phase5bb_live_frontier_members))
    )
    print(
        f"[Phase5BB] ICALL hardware frontier root: 0x{LIVE_INDIRECT_FRONTIER_TARGET_33:08X}; "
        f"caller=0x0022C452 depth={P5BB_ICALL_FRONTIER_CLOSURE_DEPTH}; "
        f"members={len(phase5bb_icall_frontier_members)}"
    )
    print(
        "[Phase5BB] ICALL frontier members: "
        + ", ".join(f"0x{va:08X}" for va in sorted(phase5bb_icall_frontier_members))
    )
    print(
        f"[Phase5BB] Direct hardware frontier root: 0x{LIVE_DIRECT_FRONTIER_TARGET_34:08X}; "
        f"caller=0x0022B5EF depth={P5BB_DIRECT34_CLOSURE_DEPTH}; "
        f"members={len(phase5bb_direct34_members)}"
    )
    print(
        "[Phase5BB] Direct frontier members: "
        + ", ".join(f"0x{va:08X}" for va in sorted(phase5bb_direct34_members))
    )
    print(
        "[Phase5BB] Post-persistence frontier members: "
        + ", ".join(f"0x{va:08X}" for va in sorted(phase5bb_post_persist_members))
    )
    print(
        "[Phase5BB] Hardware-observed handoff: "
        "StartRoutine=0x0022B43F ctx1=0x002295D6 ctx2=0x00000000"
    )
    print(f"[Phase5BB] main: {args.out_dir / 'main.cpp'}")
    print(f"[Phase5BB] env:  {args.out_dir / 'phase5_env.cpp'}")
    print(
        "[Phase5BB] Runtime policy: preserve the proven startup path, keep "
        "the complete hardware-proven title-storage/XBE-section-scan path live, preserve reviewed SetLastError execution, service ordinal 211 class 34 natively, retain the complete post-TitleMeta direct-root chain through 0x0023F8CB and the native ordinal-236 NtWriteFile bridge, retain the full 77-body translated pack and exact Partition0 sandbox, make ordinal 301 repeatable with the production status table, require Partition0 raw read/write success, map cache Partition3/4/5, execute the bounded 0x0022C5C6 cache closure, require the persisted second-boot path, execute the bounded 0x0022F0D6 post-persistence closure, execute the bounded 0x0023E600 live frontier, repair only the proven caller 0x0022A7A4 ordinal-289 saved-ESP mismatch, honor Xbox ObDosDevices root 0xFFFFFFFD for DOS-drive file opens, enter the exact hardware-observed guest ICALL target 0x0023D550 through its bounded translated closure, execute the new direct frontier root 0x0022DDA4, and continue to the next real runtime boundary."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

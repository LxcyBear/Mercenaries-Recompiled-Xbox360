/*
 * Mercenaries Xbox 360 - Phase 3J dependency-closed translated cluster.
 *
 * The root and all members are selected automatically from the supported
 * retail call graph. No member VA is hand-picked in this source.
 *
 * Phase 3J-A deliberately requires a small, branchless/loop-free, statically
 * closed cluster so every selected dependency is actually exercised. Phase 3K
 * widens the control-flow/flags surface after this closure gate passes.
 */

#include <xtl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef unsigned char      uint8_t;
typedef signed char        int8_t;
typedef unsigned short     uint16_t;
typedef signed short       int16_t;
typedef unsigned int       uint32_t;
typedef signed int         int32_t;
typedef unsigned __int64   uint64_t;
typedef __int64            int64_t;

#define RAM_SIZE           0x04000000u
#define RAM_MASK           0x03FFFFFFu
#define MIRROR_END         0x74000000u
#define KSEG_BASE          0x80000000u
#define KSEG_END           0xC0000000u
#define FENCE_BASE         0x80000000u
#define FENCE_END          0x80001000u
#define KERNEL_BASE        0x80010000u
#define KERNEL_END         0x80011000u

#define ROOT_VA            __P3J_ROOT_VA__
#define CLUSTER_MEMBERS    __P3J_MEMBER_COUNT__
#define CLUSTER_DEPTH      __P3J_DEPTH__

#define ROOT_STACK         0x008B4000u
#define ARG_COUNT          48u

#define SAFE_EAX_BASE      0x00100000u
#define SAFE_ECX_BASE      0x00110000u
#define SAFE_EDX_BASE      0x00120000u
#define SAFE_EBX_BASE      0x00130000u
#define SAFE_ESI_BASE      0x00140000u
#define SAFE_EDI_BASE      0x00150000u

#define CANARY_BASE        0x03EF0000u
#define CANARY_COUNT       8u

#define TRACE_CAPACITY     256u

static BYTE* g_ram = NULL;
static HANDLE s_logFile = INVALID_HANDLE_VALUE;
static int s_accessFault = 0;

uint32_t g_eax = 0u;
uint32_t g_ecx = 0u;
uint32_t g_edx = 0u;
uint32_t g_esp = 0u;
uint32_t g_ebx = 0u;
uint32_t g_esi = 0u;
uint32_t g_edi = 0u;
uint32_t g_seh_ebp = 0u;
uint32_t g_eflags = 0u;
volatile uint32_t g_recomp_14fa2b_entry = 0u;

#define eax g_eax
#define ecx g_ecx
#define edx g_edx
#define esp g_esp
#define ebx g_ebx
#define esi g_esi
#define edi g_edi

#define LO8(r)   ((uint8_t)((r) & 0xFFu))
#define HI8(r)   ((uint8_t)(((r) >> 8) & 0xFFu))
#define LO16(r)  ((uint16_t)((r) & 0xFFFFu))
#define SET_LO8(r, v)  ((r) = ((r) & 0xFFFFFF00u) | ((uint32_t)(uint8_t)(v)))
#define SET_HI8(r, v)  ((r) = ((r) & 0xFFFF00FFu) | (((uint32_t)(uint8_t)(v)) << 8))
#define SET_LO16(r, v) ((r) = ((r) & 0xFFFF0000u) | ((uint32_t)(uint16_t)(v)))
#define SX8(v)  ((uint32_t)(int32_t)(int8_t)(v))
#define SX16(v) ((uint32_t)(int32_t)(int16_t)(v))
#define ZX8(v)  ((uint32_t)(uint8_t)(v))
#define ZX16(v) ((uint32_t)(uint16_t)(v))

#define CMP_EQ(a, b)  ((uint32_t)(a) == (uint32_t)(b))
#define CMP_NE(a, b)  ((uint32_t)(a) != (uint32_t)(b))
#define CMP_B(a, b)   ((uint32_t)(a) <  (uint32_t)(b))
#define CMP_AE(a, b)  ((uint32_t)(a) >= (uint32_t)(b))
#define CMP_BE(a, b)  ((uint32_t)(a) <= (uint32_t)(b))
#define CMP_A(a, b)   ((uint32_t)(a) >  (uint32_t)(b))
#define CMP_L(a, b)   ((int32_t)(a) <  (int32_t)(b))
#define CMP_GE(a, b)  ((int32_t)(a) >= (int32_t)(b))
#define CMP_LE(a, b)  ((int32_t)(a) <= (int32_t)(b))
#define CMP_G(a, b)   ((int32_t)(a) >  (int32_t)(b))

#define TEST_Z(a, b)  (((uint32_t)(a) & (uint32_t)(b)) == 0u)
#define TEST_NZ(a, b) (((uint32_t)(a) & (uint32_t)(b)) != 0u)
#define TEST_S(a, b)  (sizeof(a) == 1 ? \
    ((((uint8_t)(a) & (uint8_t)(b)) & 0x80u) != 0u) : \
    (sizeof(a) == 2 ? \
        ((((uint16_t)(a) & (uint16_t)(b)) & 0x8000u) != 0u) : \
        ((((uint32_t)(a) & (uint32_t)(b)) & 0x80000000u) != 0u)))

static int EVEN_PARITY8(uint8_t value)
{
    value ^= (uint8_t)(value >> 4);
    return (int)((0x9669u >> (value & 0xFu)) & 1u);
}

static uint32_t bswap32_local(uint32_t value)
{
    return ((value & 0x000000FFu) << 24) |
           ((value & 0x0000FF00u) << 8) |
           ((value & 0x00FF0000u) >> 8) |
           ((value & 0xFF000000u) >> 24);
}

#define BSWAP32(v) bswap32_local((uint32_t)(v))

static DWORD s_trace[TRACE_CAPACITY];
static DWORD s_traceCount = 0u;

static const DWORD s_clusterVas[CLUSTER_MEMBERS] = {
    /*__P3J_MEMBER_VAS__*/
};

static void trace_func(DWORD va)
{
    if (s_traceCount < TRACE_CAPACITY)
        s_trace[s_traceCount] = va;
    ++s_traceCount;
}

#define RECOMP_TRACE_FUNC(va) do { trace_func((DWORD)(va)); } while (0)

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P3J] ");
    OutputDebugStringA(line);
    OutputDebugStringA("\r\n");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        WriteFile(s_logFile, line, length, &written, NULL);
        WriteFile(s_logFile, "\r\n", 2, &written, NULL);
        FlushFileBuffers(s_logFile);
    }
}

static int check(int condition, const char* passText, const char* failText)
{
    if (condition)
    {
        trace(passText);
        return 1;
    }

    trace(failText);
    return 0;
}

static int guest_offset(DWORD address, DWORD width, DWORD* out)
{
    DWORD offset;

    if (!out || width == 0u)
        return 0;

    if (address < MIRROR_END)
    {
        offset = address & RAM_MASK;
    }
    else if (address >= KSEG_BASE && address < KSEG_END)
    {
        if ((address >= FENCE_BASE && address < FENCE_END) ||
            (address >= KERNEL_BASE && address < KERNEL_END))
            return 0;

        offset = address & RAM_MASK;
    }
    else
    {
        return 0;
    }

    if (offset >= RAM_SIZE || width > RAM_SIZE - offset)
        return 0;

    *out = offset;
    return 1;
}

static BYTE* guest_ptr(DWORD address, DWORD width)
{
    DWORD offset;

    if (!g_ram || !guest_offset(address, width, &offset))
        return NULL;

    return g_ram + offset;
}

uint8_t recomp_guest_read8(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 1u);

    if (!p)
    {
        s_accessFault = 1;
        return 0u;
    }

    return p[0];
}

uint16_t recomp_guest_read16(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 2u);

    if (!p)
    {
        s_accessFault = 1;
        return 0u;
    }

    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

uint32_t recomp_guest_read32(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 4u);

    if (!p)
    {
        s_accessFault = 1;
        return 0u;
    }

    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

uint64_t recomp_guest_read64(uint32_t address)
{
    BYTE* p = guest_ptr((DWORD)address, 8u);
    uint64_t lo;
    uint64_t hi;

    if (!p)
    {
        s_accessFault = 1;
        return 0ui64;
    }

    lo = (uint64_t)(
        ((uint32_t)p[0]) |
        ((uint32_t)p[1] << 8) |
        ((uint32_t)p[2] << 16) |
        ((uint32_t)p[3] << 24));

    hi = (uint64_t)(
        ((uint32_t)p[4]) |
        ((uint32_t)p[5] << 8) |
        ((uint32_t)p[6] << 16) |
        ((uint32_t)p[7] << 24));

    return lo | (hi << 32);
}

void recomp_guest_write8(uint32_t address, uint8_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 1u);

    if (!p)
    {
        s_accessFault = 1;
        return;
    }

    p[0] = (BYTE)value;
}

void recomp_guest_write16(uint32_t address, uint16_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 2u);

    if (!p)
    {
        s_accessFault = 1;
        return;
    }

    p[0] = (BYTE)value;
    p[1] = (BYTE)(value >> 8);
}

void recomp_guest_write32(uint32_t address, uint32_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 4u);

    if (!p)
    {
        s_accessFault = 1;
        return;
    }

    p[0] = (BYTE)value;
    p[1] = (BYTE)(value >> 8);
    p[2] = (BYTE)(value >> 16);
    p[3] = (BYTE)(value >> 24);
}

void recomp_guest_write64(uint32_t address, uint64_t value)
{
    BYTE* p = guest_ptr((DWORD)address, 8u);

    if (!p)
    {
        s_accessFault = 1;
        return;
    }

    p[0] = (BYTE)value;
    p[1] = (BYTE)(value >> 8);
    p[2] = (BYTE)(value >> 16);
    p[3] = (BYTE)(value >> 24);
    p[4] = (BYTE)(value >> 32);
    p[5] = (BYTE)(value >> 40);
    p[6] = (BYTE)(value >> 48);
    p[7] = (BYTE)(value >> 56);
}

#define GUEST_READ8(addr)   recomp_guest_read8((uint32_t)(addr))
#define GUEST_READ16(addr)  recomp_guest_read16((uint32_t)(addr))
#define GUEST_READ32(addr)  recomp_guest_read32((uint32_t)(addr))
#define GUEST_READ64(addr)  recomp_guest_read64((uint32_t)(addr))
#define GUEST_SREAD8(addr)  ((int8_t)GUEST_READ8(addr))
#define GUEST_SREAD16(addr) ((int16_t)GUEST_READ16(addr))
#define GUEST_SREAD32(addr) ((int32_t)GUEST_READ32(addr))
#define GUEST_SREAD64(addr) ((int64_t)GUEST_READ64(addr))

#define GUEST_WRITE8(addr, value)   recomp_guest_write8((uint32_t)(addr), (uint8_t)(value))
#define GUEST_WRITE16(addr, value)  recomp_guest_write16((uint32_t)(addr), (uint16_t)(value))
#define GUEST_WRITE32(addr, value)  recomp_guest_write32((uint32_t)(addr), (uint32_t)(value))
#define GUEST_WRITE64(addr, value)  recomp_guest_write64((uint32_t)(addr), (uint64_t)(value))

#define RECOMP_READ8(addr)      GUEST_READ8(addr)
#define RECOMP_READ16(addr)     GUEST_READ16(addr)
#define RECOMP_READ32(addr)     GUEST_READ32(addr)
#define RECOMP_READ64(addr)     GUEST_READ64(addr)
#define RECOMP_WRITE8(addr, v)  GUEST_WRITE8((addr), (v))
#define RECOMP_WRITE16(addr, v) GUEST_WRITE16((addr), (v))
#define RECOMP_WRITE32(addr, v) GUEST_WRITE32((addr), (v))
#define RECOMP_WRITE64(addr, v) GUEST_WRITE64((addr), (v))

#define PUSH32(sp, val) do { \
    uint32_t _phase3j_push_value = (uint32_t)(val); \
    (sp) -= 4u; \
    GUEST_WRITE32((sp), _phase3j_push_value); \
} while (0)

#define POP32(sp, dst) do { \
    (dst) = GUEST_READ32(sp); \
    (sp) += 4u; \
} while (0)

/* All selected translated symbols are declared before any body so arbitrary
 * dependency order does not become a native C compiler constraint. */
/*__P3J_FORWARD_DECLS__*/

/* Dependency-first, mechanically translated retail bodies. */
/*__P3J_CLUSTER_BODIES__*/

static unsigned __int64 hash_guest_ram(void)
{
    const unsigned __int64 kOffset = 14695981039346656037ui64;
    const unsigned __int64 kPrime = 1099511628211ui64;
    const DWORD* words = (const DWORD*)g_ram;
    const DWORD count = RAM_SIZE / sizeof(DWORD);
    unsigned __int64 hash = kOffset;
    DWORD i;

    for (i = 0u; i < count; ++i)
    {
        hash ^= (unsigned __int64)words[i];
        hash *= kPrime;
    }

    return hash;
}

static DWORD canary_value(DWORD caseIndex, DWORD index)
{
    return 0x3A4A0000u ^ (caseIndex << 12) ^ (index * 0x01010101u);
}

static void reset_trace(void)
{
    s_traceCount = 0u;
    memset(s_trace, 0, sizeof(s_trace));
}

static void seed_pointer_region(DWORD base, DWORD caseIndex)
{
    DWORD i;

    /*
     * Zero-filled object regions are deliberate. If translated code follows a
     * pointer loaded from a field, zero remains a mapped guest address rather
     * than becoming a random host-invalid value. A few low fields point back
     * into mapped deterministic pools to exercise nonzero pointer loads too.
     */
    for (i = 0u; i < 0x400u; ++i)
        GUEST_WRITE8(base + i, 0u);

    GUEST_WRITE32(base + 0x00u, base);
    GUEST_WRITE32(base + 0x04u, base + 0x80u);
    GUEST_WRITE32(base + 0x08u, 0u);
    GUEST_WRITE32(base + 0x0Cu, caseIndex);
    GUEST_WRITE32(base + 0x10u, base + 0x100u);
    GUEST_WRITE32(base + 0x14u, 0u);
    GUEST_WRITE32(base + 0x18u, base + 0x180u);
    GUEST_WRITE32(base + 0x1Cu, 0u);
}

static void seed_case(DWORD caseIndex)
{
    DWORD i;
    DWORD safeArgs[6];

    memset(g_ram, 0, RAM_SIZE);

    seed_pointer_region(SAFE_EAX_BASE + caseIndex * 0x1000u, caseIndex);
    seed_pointer_region(SAFE_ECX_BASE + caseIndex * 0x1000u, caseIndex);
    seed_pointer_region(SAFE_EDX_BASE + caseIndex * 0x1000u, caseIndex);
    seed_pointer_region(SAFE_EBX_BASE + caseIndex * 0x1000u, caseIndex);
    seed_pointer_region(SAFE_ESI_BASE + caseIndex * 0x1000u, caseIndex);
    seed_pointer_region(SAFE_EDI_BASE + caseIndex * 0x1000u, caseIndex);

    safeArgs[0] = SAFE_EAX_BASE + caseIndex * 0x1000u;
    safeArgs[1] = SAFE_ECX_BASE + caseIndex * 0x1000u;
    safeArgs[2] = SAFE_EDX_BASE + caseIndex * 0x1000u;
    safeArgs[3] = SAFE_EBX_BASE + caseIndex * 0x1000u;
    safeArgs[4] = SAFE_ESI_BASE + caseIndex * 0x1000u;
    safeArgs[5] = SAFE_EDI_BASE + caseIndex * 0x1000u;

    g_eax = safeArgs[0];
    g_ecx = safeArgs[1];
    g_edx = safeArgs[2];
    g_ebx = safeArgs[3];
    g_esi = safeArgs[4];
    g_edi = safeArgs[5];
    g_seh_ebp = 0x00160000u + caseIndex * 0x1000u;
    g_eflags = 0u;

    g_esp = ROOT_STACK;
    GUEST_WRITE32(g_esp, 0x3A4A0000u ^ caseIndex);

    for (i = 1u; i <= ARG_COUNT; ++i)
    {
        DWORD value = safeArgs[(i - 1u) % 6u];

        if ((i & 7u) == 0u)
            value = caseIndex;
        else if ((i & 7u) == 4u)
            value = 0u;

        GUEST_WRITE32(g_esp + i * 4u, value);
    }

    for (i = 0u; i < CANARY_COUNT; ++i)
        GUEST_WRITE32(CANARY_BASE + i * 4u, canary_value(caseIndex, i));

    s_accessFault = 0;
    reset_trace();
}

static int canaries_ok(DWORD caseIndex)
{
    DWORD i;

    for (i = 0u; i < CANARY_COUNT; ++i)
    {
        if (GUEST_READ32(CANARY_BASE + i * 4u) !=
            canary_value(caseIndex, i))
            return 0;
    }

    return 1;
}

static DWORD trace_occurrences(DWORD va)
{
    DWORD i;
    DWORD count = 0u;
    DWORD limit = s_traceCount < TRACE_CAPACITY
        ? s_traceCount : TRACE_CAPACITY;

    for (i = 0u; i < limit; ++i)
    {
        if (s_trace[i] == va)
            ++count;
    }

    return count;
}

static DWORD covered_member_count(void)
{
    DWORD i;
    DWORD count = 0u;

    for (i = 0u; i < CLUSTER_MEMBERS; ++i)
    {
        if (trace_occurrences(s_clusterVas[i]) > 0u)
            ++count;
    }

    return count;
}

typedef struct RunResult
{
    DWORD eax;
    DWORD ecx;
    DWORD edx;
    DWORD esp;
    DWORD ebx;
    DWORD esi;
    DWORD edi;
    DWORD sehEbp;
    DWORD eflags;

    int accessFault;
    int canaryOk;

    DWORD traceCount;
    DWORD trace[TRACE_CAPACITY];
    DWORD coveredMembers;

    unsigned __int64 memoryHash;
} RunResult;

static void capture_result(DWORD caseIndex, RunResult* result)
{
    DWORD i;

    result->eax = g_eax;
    result->ecx = g_ecx;
    result->edx = g_edx;
    result->esp = g_esp;
    result->ebx = g_ebx;
    result->esi = g_esi;
    result->edi = g_edi;
    result->sehEbp = g_seh_ebp;
    result->eflags = g_eflags;

    result->accessFault = s_accessFault;
    result->canaryOk = canaries_ok(caseIndex);

    result->traceCount = s_traceCount;
    result->coveredMembers = covered_member_count();

    for (i = 0u; i < TRACE_CAPACITY; ++i)
        result->trace[i] = s_trace[i];

    result->memoryHash = hash_guest_ram();
}

static int traces_match(const RunResult* a, const RunResult* b)
{
    DWORD i;
    DWORD limit;

    if (a->traceCount != b->traceCount)
        return 0;

    limit = a->traceCount < TRACE_CAPACITY
        ? a->traceCount : TRACE_CAPACITY;

    for (i = 0u; i < limit; ++i)
    {
        if (a->trace[i] != b->trace[i])
            return 0;
    }

    return 1;
}

static int architecture_matches(const RunResult* a, const RunResult* b)
{
    return
        a->eax == b->eax &&
        a->ecx == b->ecx &&
        a->edx == b->edx &&
        a->esp == b->esp &&
        a->ebx == b->ebx &&
        a->esi == b->esi &&
        a->edi == b->edi &&
        a->sehEbp == b->sehEbp &&
        a->eflags == b->eflags &&
        a->accessFault == b->accessFault &&
        a->canaryOk == b->canaryOk &&
        a->coveredMembers == b->coveredMembers &&
        a->memoryHash == b->memoryHash;
}

static int run_once(DWORD caseIndex, RunResult* result)
{
    seed_case(caseIndex);
    __P3J_ROOT_NAME__();
    capture_result(caseIndex, result);
    return 1;
}

static int run_case(DWORD caseIndex)
{
    RunResult a;
    RunResult b;
    char line[384];
    int ok = 1;

    run_once(caseIndex, &a);
    run_once(caseIndex, &b);

    sprintf(
        line,
        "CASE %u A eax=%08X ecx=%08X esp=%08X trace=%u coverage=%u/%u hash=%08X%08X",
        (unsigned int)caseIndex,
        (unsigned int)a.eax,
        (unsigned int)a.ecx,
        (unsigned int)a.esp,
        (unsigned int)a.traceCount,
        (unsigned int)a.coveredMembers,
        (unsigned int)CLUSTER_MEMBERS,
        (unsigned int)(a.memoryHash >> 32),
        (unsigned int)a.memoryHash);
    trace(line);

    sprintf(
        line,
        "CASE %u B eax=%08X ecx=%08X esp=%08X trace=%u coverage=%u/%u hash=%08X%08X",
        (unsigned int)caseIndex,
        (unsigned int)b.eax,
        (unsigned int)b.ecx,
        (unsigned int)b.esp,
        (unsigned int)b.traceCount,
        (unsigned int)b.coveredMembers,
        (unsigned int)CLUSTER_MEMBERS,
        (unsigned int)(b.memoryHash >> 32),
        (unsigned int)b.memoryHash);
    trace(line);

    ok &= check(
        a.accessFault == 0 && b.accessFault == 0,
        "PASS: both dependency-closed cluster runs complete without guest-memory faults",
        "FAIL: dependency-closed cluster triggered guest-memory fault");

    ok &= check(
        a.canaryOk && b.canaryOk,
        "PASS: unrelated high-RAM canaries survive both cluster runs",
        "FAIL: dependency-closed cluster corrupted high-RAM canary");

    ok &= check(
        a.traceCount > 0u &&
        b.traceCount > 0u &&
        a.trace[0] == ROOT_VA &&
        b.trace[0] == ROOT_VA,
        "PASS: translated trace begins at the automatically selected real root",
        "FAIL: cluster trace does not begin at selected root");

    ok &= check(
        a.coveredMembers == CLUSTER_MEMBERS &&
        b.coveredMembers == CLUSTER_MEMBERS,
        "PASS: every statically closed cluster member executes on both runs",
        "FAIL: one or more selected dependency members were not executed");

    ok &= check(
        a.esp == ROOT_STACK + 4u &&
        b.esp == ROOT_STACK + 4u,
        "PASS: complete dependency cluster returns to harness with exact root RET stack state",
        "FAIL: final guest ESP does not match one root return slot");

    ok &= check(
        traces_match(&a, &b),
        "PASS: complete translated cluster trace is deterministic",
        "FAIL: translated cluster traces diverge across repeated runs");

    ok &= check(
        architecture_matches(&a, &b),
        "PASS: repeated cluster runs match architecture and complete 64 MiB guest RAM",
        "FAIL: repeated cluster architecture/full-RAM state diverges");

    return ok;
}

static int run_fixture(void)
{
    int ok = 1;

    ok &= run_case(0u);
    ok &= run_case(1u);
    ok &= run_case(2u);

    return ok;
}

VOID __cdecl main()
{
    int result = 0;
    DWORD started;
    DWORD nextHeartbeat = 1000u;
    char line[256];

    s_logFile = CreateFileA(
        "game:\\merc360-phase3j-closed-cluster.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 3J DEPENDENCY-CLOSED TRANSLATED CLUSTER START");
    trace("BUILD TAG: P3J-CLOSURE-20261018-A");

    sprintf(
        line,
        "Root VA: %08X, members=%u, depth=%u",
        (unsigned int)ROOT_VA,
        (unsigned int)CLUSTER_MEMBERS,
        (unsigned int)CLUSTER_DEPTH);
    trace(line);

    g_ram = (BYTE*)malloc(RAM_SIZE);

    if (!g_ram)
    {
        trace("FATAL: could not allocate 64 MiB guest RAM");
        goto wait_for_exit;
    }

    result = run_fixture();

    if (result)
        trace("PHASE 3J DEPENDENCY-CLOSED TRANSLATED CLUSTER RESULT: PASS");
    else
        trace("PHASE 3J DEPENDENCY-CLOSED TRANSLATED CLUSTER RESULT: FAIL");

    free(g_ram);
    g_ram = NULL;
    trace("Guest RAM released");

wait_for_exit:
    trace("Press A to exit, or automatic exit after 10 seconds");
    started = GetTickCount();

    for (;;)
    {
        XINPUT_STATE state;
        DWORD elapsed = GetTickCount() - started;

        if (elapsed >= 10000u)
        {
            trace("10-second post-test timeout - exiting");
            break;
        }

        ZeroMemory(&state, sizeof(state));

        if (XInputGetState(0, &state) == ERROR_SUCCESS &&
            (state.Gamepad.wButtons & XINPUT_GAMEPAD_A) != 0)
        {
            trace("Controller A detected - exiting");
            break;
        }

        if (elapsed >= nextHeartbeat)
        {
            trace("POST-TEST HEARTBEAT");
            nextHeartbeat += 1000u;
        }

        Sleep(33);
    }

    trace("PHASE 3J DEPENDENCY-CLOSED TRANSLATED CLUSTER END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

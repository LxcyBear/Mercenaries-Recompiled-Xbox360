/*
 * Mercenaries Xbox 360 - Phase 3G first bounded translated normal CALL chain.
 *
 * The prep workflow selects a tiny real x86 CALL edge from the user's verified
 * retail XBE, lifts both functions with explicit guest memory, and injects:
 *   - renamed translated callee implementation
 *   - translated reference caller with only the CALL push rewritten
 *   - unmodified translated real caller
 *
 * Retail-derived generated bodies remain local under gitignored build/.
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

#define CALLER_VA          __PHASE3G_CALLER_VA__
#define CALLEE_VA          __PHASE3G_CALLEE_VA__
#define CALLER_INITIAL_ESP 0x008BFE00u

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

static uint32_t bswap32_local(uint32_t value)
{
    return ((value & 0x000000FFu) << 24) |
           ((value & 0x0000FF00u) << 8) |
           ((value & 0x00FF0000u) >> 8) |
           ((value & 0xFF000000u) >> 24);
}

#define BSWAP32(v) bswap32_local((uint32_t)(v))

#define TRACE_CAPACITY 8u
static DWORD s_trace[TRACE_CAPACITY];
static DWORD s_traceCount = 0u;

static DWORD s_calleeProbeCount = 0u;
static DWORD s_calleeEntryEsp = 0u;
static DWORD s_calleeEntryTop = 0u;

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

    OutputDebugStringA("[Merc360:P3G] ");
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
    uint32_t _phase3g_push_value = (uint32_t)(val); \
    (sp) -= 4u; \
    GUEST_WRITE32((sp), _phase3g_push_value); \
} while (0)

#define POP32(sp, dst) do { \
    (dst) = GUEST_READ32(sp); \
    (sp) += 4u; \
} while (0)

/* The real translated callee body, renamed locally by the prep selector. */
/*__PHASE3G_CALLEE_IMPL__*/

static void __PHASE3G_CALLEE_NAME__(void)
{
    ++s_calleeProbeCount;
    s_calleeEntryEsp = g_esp;
    s_calleeEntryTop = GUEST_READ32(g_esp);
    phase3g_callee_impl();
}

/*
 * Independent reference for the one operation Phase 3G is isolating:
 * x86 CALL's synthetic return-address push.
 *
 * This intentionally does NOT use PUSH32. It writes the same dummy translated
 * return value directly through the explicit guest-memory ABI, updates ESP,
 * then enters the same translated callee wrapper.
 */
static void phase3g_reference_call(void)
{
    uint32_t newEsp = g_esp - 4u;
    GUEST_WRITE32(newEsp, 0u);
    g_esp = newEsp;
    __PHASE3G_CALLEE_NAME__();
}

/* Exact translated caller with only its direct CALL line reference-rewritten. */
/*__PHASE3G_REFERENCE_CALLER__*/

/* Exact unmodified translated retail caller. */
/*__PHASE3G_REAL_CALLER__*/

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
    unsigned __int64 memoryHash;
    int accessFault;
    DWORD traceCount;
    DWORD trace[TRACE_CAPACITY];
    DWORD probeCount;
    DWORD calleeEntryEsp;
    DWORD calleeEntryTop;
} RunResult;

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

static void reset_observers(void)
{
    s_accessFault = 0;
    s_traceCount = 0u;
    memset(s_trace, 0, sizeof(s_trace));
    s_calleeProbeCount = 0u;
    s_calleeEntryEsp = 0u;
    s_calleeEntryTop = 0xFFFFFFFFu;
}

static void seed_guest_state(DWORD caseIndex)
{
    DWORD i;

    memset(g_ram, 0, RAM_SIZE);

    /*
     * Keep guest pointers in low mapped RAM and the surrounding memory zeroed.
     * The cases move them slightly while preserving alignment and safety.
     */
    g_eax = 0x00030000u + caseIndex * 0x100u;
    g_ecx = 0x00040000u + caseIndex * 0x100u;
    g_edx = 0x00050000u + caseIndex * 0x100u;
    g_ebx = 0x00060000u + caseIndex * 0x100u;
    g_esi = 0x00070000u + caseIndex * 0x100u;
    g_edi = 0x00080000u + caseIndex * 0x100u;
    g_seh_ebp = 0x00090000u + caseIndex * 0x100u;

    g_esp = CALLER_INITIAL_ESP;

    /*
     * Caller return address and a small deterministic argument area. Zero/small
     * values remain safe whether interpreted as integers or guest pointers.
     */
    GUEST_WRITE32(g_esp, 0xC011CA11u ^ caseIndex);
    for (i = 1u; i <= 16u; ++i)
        GUEST_WRITE32(g_esp + i * 4u, (caseIndex + i) & 3u);

    /*
     * This location is where translated CALL must create its dummy return
     * address. Seed nonzero data first so the test proves it was overwritten.
     */
    GUEST_WRITE32(g_esp - 4u, 0xA5A50000u | caseIndex);

    reset_observers();
}

static void capture_result(RunResult* result)
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
    result->memoryHash = hash_guest_ram();
    result->accessFault = s_accessFault;
    result->traceCount = s_traceCount;
    result->probeCount = s_calleeProbeCount;
    result->calleeEntryEsp = s_calleeEntryEsp;
    result->calleeEntryTop = s_calleeEntryTop;

    for (i = 0u; i < TRACE_CAPACITY; ++i)
        result->trace[i] = s_trace[i];
}

static int architectural_results_match(
    const RunResult* reference,
    const RunResult* real)
{
    return
        reference->eax == real->eax &&
        reference->ecx == real->ecx &&
        reference->edx == real->edx &&
        reference->esp == real->esp &&
        reference->ebx == real->ebx &&
        reference->esi == real->esi &&
        reference->edi == real->edi &&
        reference->sehEbp == real->sehEbp &&
        reference->memoryHash == real->memoryHash &&
        reference->accessFault == real->accessFault;
}

static int run_one_case(DWORD caseIndex)
{
    RunResult reference;
    RunResult real;
    char line[320];
    int ok = 1;

    seed_guest_state(caseIndex);
    phase3g_reference_caller();
    capture_result(&reference);

    seed_guest_state(caseIndex);
    __PHASE3G_CALLER_NAME__();
    capture_result(&real);

    sprintf(
        line,
        "CASE %u ref  eax=%08X ecx=%08X esp=%08X entryEsp=%08X top=%08X hash=%08X%08X",
        (unsigned int)caseIndex,
        (unsigned int)reference.eax,
        (unsigned int)reference.ecx,
        (unsigned int)reference.esp,
        (unsigned int)reference.calleeEntryEsp,
        (unsigned int)reference.calleeEntryTop,
        (unsigned int)(reference.memoryHash >> 32),
        (unsigned int)reference.memoryHash);
    trace(line);

    sprintf(
        line,
        "CASE %u real eax=%08X ecx=%08X esp=%08X entryEsp=%08X top=%08X hash=%08X%08X",
        (unsigned int)caseIndex,
        (unsigned int)real.eax,
        (unsigned int)real.ecx,
        (unsigned int)real.esp,
        (unsigned int)real.calleeEntryEsp,
        (unsigned int)real.calleeEntryTop,
        (unsigned int)(real.memoryHash >> 32),
        (unsigned int)real.memoryHash);
    trace(line);

    ok &= check(
        reference.accessFault == 0 && real.accessFault == 0,
        "PASS: reference and generated CALL paths complete without guest-memory faults",
        "FAIL: reference or generated CALL path triggered guest-memory fault");

    ok &= check(
        reference.probeCount == 1u && real.probeCount == 1u,
        "PASS: translated callee entered exactly once on both paths",
        "FAIL: translated callee entry count differs");

    ok &= check(
        reference.calleeEntryEsp == CALLER_INITIAL_ESP - 4u &&
        real.calleeEntryEsp == CALLER_INITIAL_ESP - 4u,
        "PASS: callee sees caller ESP minus one 4-byte synthetic return slot",
        "FAIL: callee entry ESP does not match x86 CALL stack semantics");

    ok &= check(
        reference.calleeEntryTop == 0u &&
        real.calleeEntryTop == 0u,
        "PASS: synthetic translated return-address slot contains zero",
        "FAIL: synthetic translated return-address slot is not zero");

    ok &= check(
        reference.esp == CALLER_INITIAL_ESP + 4u &&
        real.esp == CALLER_INITIAL_ESP + 4u,
        "PASS: callee RET restores caller ESP and caller RET consumes its own return slot",
        "FAIL: final guest ESP does not match normal CALL plus caller RET");

    ok &= check(
        reference.traceCount == 2u &&
        reference.trace[0] == CALLER_VA &&
        reference.trace[1] == CALLEE_VA &&
        real.traceCount == 2u &&
        real.trace[0] == CALLER_VA &&
        real.trace[1] == CALLEE_VA,
        "PASS: translated trace is caller then callee on both paths",
        "FAIL: translated direct-CALL trace sequence is unexpected");

    ok &= check(
        architectural_results_match(&reference, &real),
        "PASS: generated PUSH32 CALL matches independent explicit-stack reference",
        "FAIL: generated direct CALL differs from independent explicit-stack reference");

    if (reference.memoryHash == real.memoryHash)
        trace("PASS: full 64 MiB guest-RAM hashes match");
    else
    {
        trace("FAIL: full 64 MiB guest-RAM hashes differ");
        ok = 0;
    }

    return ok;
}

static int run_fixture(void)
{
    int ok = 1;

    ok &= run_one_case(0u);
    ok &= run_one_case(1u);
    ok &= run_one_case(2u);

    return ok;
}

VOID __cdecl main()
{
    int result = 0;
    DWORD started;
    DWORD nextHeartbeat = 1000u;

    s_logFile = CreateFileA(
        "game:\\merc360-phase3g-direct-call.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 3G TRANSLATED NORMAL-CALL CHAIN START");
    trace("BUILD TAG: P3G-CALL-20261018-A");
    trace("Caller VA: __PHASE3G_CALLER_VA_TEXT__");
    trace("Callee VA: __PHASE3G_CALLEE_VA_TEXT__");
    trace("Reference: manual guest return-slot write versus generated PUSH32(esp, 0)");

    g_ram = (BYTE*)malloc(RAM_SIZE);

    if (!g_ram)
    {
        trace("FATAL: could not allocate 64 MiB guest RAM");
        goto wait_for_exit;
    }

    result = run_fixture();

    if (result)
        trace("PHASE 3G TRANSLATED NORMAL-CALL RESULT: PASS");
    else
        trace("PHASE 3G TRANSLATED NORMAL-CALL RESULT: FAIL");

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

    trace("PHASE 3G TRANSLATED NORMAL-CALL CHAIN END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

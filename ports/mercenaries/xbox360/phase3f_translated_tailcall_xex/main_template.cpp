/*
 * Mercenaries Xbox 360 - Phase 3F first bounded translated tail-call chain.
 *
 * Prepare-Phase3F.ps1 locally lifts the user's verified retail functions:
 *   0x00034AD0 - reviewed wrapper: ECX += 0x78; tail-call 0x00034AE0
 *   0x00034AE0 - translated callee
 *
 * Retail-derived function bodies are injected into a gitignored local copy.
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

#define RAM_SIZE          0x04000000u
#define RAM_MASK          0x03FFFFFFu
#define MIRROR_END        0x74000000u
#define KSEG_BASE         0x80000000u
#define KSEG_END          0xC0000000u
#define FENCE_BASE        0x80000000u
#define FENCE_END         0x80001000u
#define KERNEL_BASE       0x80010000u
#define KERNEL_END        0x80011000u

#define WRAPPER_VA        0x00034AD0u
#define CALLEE_VA         0x00034AE0u
#define WRAPPER_ECX_DELTA 0x00000078u
#define OBJECT_BASE       0x00040000u
#define STACK_TOP         0x008BFFF0u

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

    OutputDebugStringA("[Merc360:P3F] ");
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
#define GUEST_WRITE8(addr, value)  recomp_guest_write8((uint32_t)(addr), (uint8_t)(value))
#define GUEST_WRITE16(addr, value) recomp_guest_write16((uint32_t)(addr), (uint16_t)(value))
#define GUEST_WRITE32(addr, value) recomp_guest_write32((uint32_t)(addr), (uint32_t)(value))
#define GUEST_WRITE64(addr, value) recomp_guest_write64((uint32_t)(addr), (uint64_t)(value))

#define PUSH32(sp, val) do { \
    uint32_t _pv = (uint32_t)(val); \
    (sp) -= 4u; \
    GUEST_WRITE32((sp), _pv); \
} while (0)

#define POP32(sp, dst) do { \
    (dst) = GUEST_READ32(sp); \
    (sp) += 4u; \
} while (0)

/*
 * The callee is injected first so the generated wrapper's direct C call has a
 * declaration/definition available under the old XDK C++ compiler.
 */
/*__PHASE3F_CALLEE__*/

/*__PHASE3F_WRAPPER__*/

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
} RunResult;

static unsigned __int64 hash_guest_ram(void)
{
    const unsigned __int64 kOffset = 14695981039346656037ui64;
    const unsigned __int64 kPrime = 1099511628211ui64;
    unsigned __int64 hash = kOffset;
    DWORD i;

    for (i = 0u; i < RAM_SIZE; ++i)
    {
        hash ^= (unsigned __int64)g_ram[i];
        hash *= kPrime;
    }

    return hash;
}

static void seed_guest_state(DWORD caseIndex, int wrapperRun)
{
    DWORD i;
    DWORD effectiveObject = OBJECT_BASE + WRAPPER_ECX_DELTA;

    memset(g_ram, 0, RAM_SIZE);

    /*
     * Seed the effective object and nearby bytes identically for direct-callee
     * and wrapper runs. The wrapper begins 0x78 bytes earlier, then adjusts ECX
     * before its tail jump.
     */
    for (i = 0u; i < 0x400u; ++i)
    {
        BYTE value = (BYTE)((i * 37u + caseIndex * 53u + 0x21u) & 0xFFu);
        GUEST_WRITE8(effectiveObject + i, value);
    }

    /*
     * Add a second deterministic area so accidental writes through unrelated
     * register state also affect the whole-RAM hash.
     */
    for (i = 0u; i < 0x100u; ++i)
    {
        BYTE value = (BYTE)((i * 11u + caseIndex * 29u + 0x80u) & 0xFFu);
        GUEST_WRITE8(0x00052000u + i, value);
    }

    g_eax = 0xA1000000u | caseIndex;
    g_ecx = wrapperRun ? OBJECT_BASE : effectiveObject;
    g_edx = 0xD2000100u + caseIndex;
    g_ebx = 0xB3000200u + caseIndex;
    g_esi = 0x51000300u + caseIndex;
    g_edi = 0xD1000400u + caseIndex;
    g_seh_ebp = 0x0EB00000u + caseIndex;

    g_esp = STACK_TOP - 4u;
    GUEST_WRITE32(g_esp, 0xC0DEF00Du ^ caseIndex);

    s_accessFault = 0;
    s_traceCount = 0u;
    memset(s_trace, 0, sizeof(s_trace));
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

    for (i = 0u; i < TRACE_CAPACITY; ++i)
        result->trace[i] = s_trace[i];
}

static int results_match(const RunResult* direct, const RunResult* wrapper)
{
    if (direct->eax != wrapper->eax ||
        direct->ecx != wrapper->ecx ||
        direct->edx != wrapper->edx ||
        direct->esp != wrapper->esp ||
        direct->ebx != wrapper->ebx ||
        direct->esi != wrapper->esi ||
        direct->edi != wrapper->edi ||
        direct->sehEbp != wrapper->sehEbp ||
        direct->memoryHash != wrapper->memoryHash ||
        direct->accessFault != wrapper->accessFault)
        return 0;

    return 1;
}

static int run_one_case(DWORD caseIndex)
{
    RunResult direct;
    RunResult wrapper;
    char line[256];
    int ok = 1;

    seed_guest_state(caseIndex, 0);
    sub_00034AE0();
    capture_result(&direct);

    seed_guest_state(caseIndex, 1);
    sub_00034AD0();
    capture_result(&wrapper);

    sprintf(
        line,
        "CASE %u direct eax=%08X ecx=%08X esp=%08X hash=%08X%08X",
        (unsigned int)caseIndex,
        (unsigned int)direct.eax,
        (unsigned int)direct.ecx,
        (unsigned int)direct.esp,
        (unsigned int)(direct.memoryHash >> 32),
        (unsigned int)direct.memoryHash);
    trace(line);

    sprintf(
        line,
        "CASE %u wrapper eax=%08X ecx=%08X esp=%08X hash=%08X%08X",
        (unsigned int)caseIndex,
        (unsigned int)wrapper.eax,
        (unsigned int)wrapper.ecx,
        (unsigned int)wrapper.esp,
        (unsigned int)(wrapper.memoryHash >> 32),
        (unsigned int)wrapper.memoryHash);
    trace(line);

    ok &= check(
        direct.accessFault == 0 && wrapper.accessFault == 0,
        "PASS: direct and wrapper paths completed without guest-memory faults",
        "FAIL: direct or wrapper path triggered guest-memory fault");

    ok &= check(
        direct.esp == STACK_TOP && wrapper.esp == STACK_TOP,
        "PASS: direct and tail-call paths consume exactly one guest return slot",
        "FAIL: direct/tail-call guest ESP cleanup differs");

    ok &= check(
        direct.traceCount == 1u &&
        direct.trace[0] == CALLEE_VA,
        "PASS: direct reference executes only translated callee",
        "FAIL: direct reference trace sequence unexpected");

    ok &= check(
        wrapper.traceCount == 2u &&
        wrapper.trace[0] == WRAPPER_VA &&
        wrapper.trace[1] == CALLEE_VA,
        "PASS: wrapper trace is translated caller then translated callee",
        "FAIL: translated tail-call trace sequence unexpected");

    ok &= check(
        results_match(&direct, &wrapper),
        "PASS: tail-call chain matches direct-callee architectural result",
        "FAIL: wrapper/callee chain differs from direct-callee result");

    if (direct.memoryHash == wrapper.memoryHash)
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
        "game:\\merc360-phase3f-tailcall.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 3F TRANSLATED TAIL-CALL CHAIN START");
    trace("BUILD TAG: P3F-TAILCALL-20261018-A");
    trace("Wrapper VA: 0x00034AD0");
    trace("Callee VA:  0x00034AE0");
    trace("Reference: direct callee at ECX+0x78 versus translated wrapper tail-call");

    g_ram = (BYTE*)malloc(RAM_SIZE);

    if (!g_ram)
    {
        trace("FATAL: could not allocate 64 MiB guest RAM");
        goto wait_for_exit;
    }

    result = run_fixture();

    if (result)
        trace("PHASE 3F TRANSLATED TAIL-CALL RESULT: PASS");
    else
        trace("PHASE 3F TRANSLATED TAIL-CALL RESULT: FAIL");

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

    trace("PHASE 3F TRANSLATED TAIL-CALL CHAIN END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

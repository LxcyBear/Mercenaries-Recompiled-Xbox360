/*
 * Mercenaries Xbox 360 - Phase 3F translated tail-call chain, candidate B.
 *
 * Prepare-Phase3F.ps1 locally lifts from the user's verified retail XBE:
 *   0x001EF850 - translated wrapper / tail caller
 *   0x0021AB90 - reviewed scalar transform setter, ret 4
 *
 * It also derives a local reference-prefix copy of 0x001EF850 that executes
 * the real translated wrapper up to, but not through, its tail-call boundary.
 * No retail-derived generated function body is committed to this repository.
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

#define WRAPPER_VA        0x001EF850u
#define CALLEE_VA         0x0021AB90u
#define OBJECT_BASE       0x00060000u
#define WRAPPER_ECX_DELTA 0x00000028u
#define STORE_OFFSET      0x000000DCu
#define EFFECTIVE_OBJECT  (OBJECT_BASE + WRAPPER_ECX_DELTA)
#define STORE_ADDRESS     (EFFECTIVE_OBJECT + STORE_OFFSET)
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
float g_xmm0[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
volatile uint32_t g_recomp_14fa2b_entry = 0u;

#define eax g_eax
#define ecx g_ecx
#define edx g_edx
#define esp g_esp
#define ebx g_ebx
#define esi g_esi
#define edi g_edi
#define xmm0 g_xmm0[0]

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

float recomp_guest_readf32(uint32_t address)
{
    uint32_t bits = recomp_guest_read32(address);
    float value = 0.0f;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

double recomp_guest_readf64(uint32_t address)
{
    uint64_t bits = recomp_guest_read64(address);
    double value = 0.0;
    memcpy(&value, &bits, sizeof(value));
    return value;
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

void recomp_guest_writef32(uint32_t address, float value)
{
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    recomp_guest_write32(address, bits);
}

void recomp_guest_writef64(uint32_t address, double value)
{
    uint64_t bits;
    memcpy(&bits, &value, sizeof(bits));
    recomp_guest_write64(address, bits);
}

#define GUEST_READ8(addr)   recomp_guest_read8((uint32_t)(addr))
#define GUEST_READ16(addr)  recomp_guest_read16((uint32_t)(addr))
#define GUEST_READ32(addr)  recomp_guest_read32((uint32_t)(addr))
#define GUEST_READ64(addr)  recomp_guest_read64((uint32_t)(addr))
#define GUEST_SREAD8(addr)  ((int8_t)GUEST_READ8(addr))
#define GUEST_SREAD16(addr) ((int16_t)GUEST_READ16(addr))
#define GUEST_SREAD32(addr) ((int32_t)GUEST_READ32(addr))
#define GUEST_SREAD64(addr) ((int64_t)GUEST_READ64(addr))
#define GUEST_READF32(addr) recomp_guest_readf32((uint32_t)(addr))
#define GUEST_READF64(addr) recomp_guest_readf64((uint32_t)(addr))
#define GUEST_WRITE8(addr, value)   recomp_guest_write8((uint32_t)(addr), (uint8_t)(value))
#define GUEST_WRITE16(addr, value)  recomp_guest_write16((uint32_t)(addr), (uint16_t)(value))
#define GUEST_WRITE32(addr, value)  recomp_guest_write32((uint32_t)(addr), (uint32_t)(value))
#define GUEST_WRITE64(addr, value)  recomp_guest_write64((uint32_t)(addr), (uint64_t)(value))
#define GUEST_WRITEF32(addr, value) recomp_guest_writef32((uint32_t)(addr), (float)(value))
#define GUEST_WRITEF64(addr, value) recomp_guest_writef64((uint32_t)(addr), (double)(value))

static void recomp_xmm_loadss(float dst[4], uint32_t address)
{
    uint32_t bits = GUEST_READ32(address);
    memcpy(&dst[0], &bits, sizeof(bits));
    dst[1] = 0.0f;
    dst[2] = 0.0f;
    dst[3] = 0.0f;
}

#define RECOMP_READ8(addr)         GUEST_READ8(addr)
#define RECOMP_READ16(addr)        GUEST_READ16(addr)
#define RECOMP_READ32(addr)        GUEST_READ32(addr)
#define RECOMP_READ64(addr)        GUEST_READ64(addr)
#define RECOMP_WRITE8(addr, v)     GUEST_WRITE8((addr), (v))
#define RECOMP_WRITE16(addr, v)    GUEST_WRITE16((addr), (v))
#define RECOMP_WRITE32(addr, v)    GUEST_WRITE32((addr), (v))
#define RECOMP_WRITE64(addr, v)    GUEST_WRITE64((addr), (v))

#define PUSH32(sp, val) do { \
    uint32_t _pv = (uint32_t)(val); \
    (sp) -= 4u; \
    GUEST_WRITE32((sp), _pv); \
} while (0)

#define POP32(sp, dst) do { \
    (dst) = GUEST_READ32(sp); \
    (sp) += 4u; \
} while (0)

/* Callee must precede the generated wrapper's direct C tail invocation. */
/*__PHASE3F_CALLEE__*/

/* Unmodified translated retail wrapper. */
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
    DWORD xmm0Bits[4];
    DWORD storedBits;
    unsigned __int64 memoryHash;
    int accessFault;
    DWORD traceCount;
    DWORD trace[TRACE_CAPACITY];
} RunResult;

static unsigned __int64 hash_guest_ram(void)
{
    const unsigned __int64 kOffset = 14695981039346656037ui64;
    const unsigned __int64 kPrime = 1099511628211ui64;
    const DWORD* words = (const DWORD*)g_ram;
    const DWORD count = RAM_SIZE / sizeof(DWORD);
    unsigned __int64 hash = kOffset;
    DWORD i;

    /*
     * Comparison-only digest. Host DWORD order is irrelevant because both runs
     * execute on the same Xenon host; using dwords makes the full-arena check
     * much cheaper than a byte-at-a-time pass.
     */
    for (i = 0u; i < count; ++i)
    {
        hash ^= (unsigned __int64)words[i];
        hash *= kPrime;
    }

    return hash;
}

static void reset_trace(void)
{
    s_traceCount = 0u;
    memset(s_trace, 0, sizeof(s_trace));
}

static DWORD test_argument_bits(DWORD caseIndex)
{
    if (caseIndex == 0u)
        return 0x3F800000u;       /* 1.0f */
    if (caseIndex == 1u)
        return 0xC0200000u;       /* -2.5f */
    return 0x3EAAAAABu;           /* approx 1/3 */
}

static void seed_guest_state(DWORD caseIndex, int wrapperRun)
{
    DWORD i;
    DWORD argumentBits = test_argument_bits(caseIndex);
    uint32_t xmmSeed[4];

    memset(g_ram, 0, RAM_SIZE);

    for (i = 0u; i < 0x500u; ++i)
    {
        BYTE value = (BYTE)((i * 37u + caseIndex * 53u + 0x21u) & 0xFFu);
        GUEST_WRITE8(OBJECT_BASE + i, value);
    }

    for (i = 0u; i < 0x100u; ++i)
    {
        BYTE value = (BYTE)((i * 11u + caseIndex * 29u + 0x80u) & 0xFFu);
        GUEST_WRITE8(0x00072000u + i, value);
    }

    g_eax = 0xA1000000u | caseIndex;
    g_ecx = wrapperRun ? OBJECT_BASE : EFFECTIVE_OBJECT;
    g_edx = 0xD2000100u + caseIndex;
    g_ebx = 0xB3000200u + caseIndex;
    g_esi = 0x51000300u + caseIndex;
    g_edi = 0xD1000400u + caseIndex;
    g_seh_ebp = 0x0EB00000u + caseIndex;

    /*
     * XMM0 is already live when the real wrapper is entered. Lane 0 carries
     * the scalar setter value; the upper lanes are sentinels so Phase 3F also
     * proves the tail chain preserves the same SIMD architectural state as the
     * direct-callee reference.
     */
    xmmSeed[0] = argumentBits;
    xmmSeed[1] = 0x11110000u + caseIndex;
    xmmSeed[2] = 0x22220000u + caseIndex;
    xmmSeed[3] = 0x33330000u + caseIndex;
    memcpy(g_xmm0, xmmSeed, sizeof(xmmSeed));

    /*
     * 0x0021AB90 ends with ret 4. The scalar value is live in XMM0, while this
     * four-byte guest argument remains part of the original x86 stack contract
     * and must still be cleaned by RET 4.
     */
    g_esp = STACK_TOP - 8u;
    GUEST_WRITE32(g_esp, 0xC0DEF00Du ^ caseIndex);
    GUEST_WRITE32(g_esp + 4u, argumentBits);

    s_accessFault = 0;
    reset_trace();
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
    memcpy(result->xmm0Bits, g_xmm0, sizeof(result->xmm0Bits));
    result->storedBits = GUEST_READ32(STORE_ADDRESS);
    result->memoryHash = hash_guest_ram();
    result->accessFault = s_accessFault;
    result->traceCount = s_traceCount;

    for (i = 0u; i < TRACE_CAPACITY; ++i)
        result->trace[i] = s_trace[i];
}

static int architectural_results_match(
    const RunResult* reference,
    const RunResult* wrapper)
{
    return
        reference->eax == wrapper->eax &&
        reference->ecx == wrapper->ecx &&
        reference->edx == wrapper->edx &&
        reference->esp == wrapper->esp &&
        reference->ebx == wrapper->ebx &&
        reference->esi == wrapper->esi &&
        reference->edi == wrapper->edi &&
        reference->sehEbp == wrapper->sehEbp &&
        reference->xmm0Bits[0] == wrapper->xmm0Bits[0] &&
        reference->xmm0Bits[1] == wrapper->xmm0Bits[1] &&
        reference->xmm0Bits[2] == wrapper->xmm0Bits[2] &&
        reference->xmm0Bits[3] == wrapper->xmm0Bits[3] &&
        reference->storedBits == wrapper->storedBits &&
        reference->memoryHash == wrapper->memoryHash &&
        reference->accessFault == wrapper->accessFault;
}

static int run_one_case(DWORD caseIndex)
{
    RunResult reference;
    RunResult wrapper;
    DWORD expectedBits = test_argument_bits(caseIndex);
    char line[288];
    int ok = 1;

    /*
     * Differential reference:
     * enter the exact translated callee with the ECX value that the real
     * wrapper should produce. XMM0 and the guest stack are otherwise seeded
     * identically.
     */
    seed_guest_state(caseIndex, 0);
    sub_0021AB90();
    capture_result(&reference);

    /*
     * Real translated chain:
     * start ECX at OBJECT_BASE, execute translated 0x001EF850, let it perform
     * ECX += 0x28 and tail-call translated 0x0021AB90 with no synthetic push.
     */
    seed_guest_state(caseIndex, 1);
    sub_001EF850();
    capture_result(&wrapper);

    sprintf(
        line,
        "CASE %u reference ecx=%08X esp=%08X xmm0=%08X store=%08X hash=%08X%08X",
        (unsigned int)caseIndex,
        (unsigned int)reference.ecx,
        (unsigned int)reference.esp,
        (unsigned int)reference.xmm0Bits[0],
        (unsigned int)reference.storedBits,
        (unsigned int)(reference.memoryHash >> 32),
        (unsigned int)reference.memoryHash);
    trace(line);

    sprintf(
        line,
        "CASE %u wrapper   ecx=%08X esp=%08X xmm0=%08X store=%08X hash=%08X%08X",
        (unsigned int)caseIndex,
        (unsigned int)wrapper.ecx,
        (unsigned int)wrapper.esp,
        (unsigned int)wrapper.xmm0Bits[0],
        (unsigned int)wrapper.storedBits,
        (unsigned int)(wrapper.memoryHash >> 32),
        (unsigned int)wrapper.memoryHash);
    trace(line);

    ok &= check(
        reference.accessFault == 0 && wrapper.accessFault == 0,
        "PASS: direct and real tail-call paths complete without guest-memory faults",
        "FAIL: direct or real tail-call path triggered guest-memory fault");

    ok &= check(
        reference.esp == STACK_TOP && wrapper.esp == STACK_TOP,
        "PASS: ret 4 consumes one return slot plus one argument on both paths",
        "FAIL: guest ESP cleanup differs from the expected ret-4 result");

    ok &= check(
        reference.traceCount == 1u &&
        reference.trace[0] == CALLEE_VA,
        "PASS: differential reference executes only translated callee",
        "FAIL: differential reference translated trace is unexpected");

    ok &= check(
        wrapper.traceCount == 2u &&
        wrapper.trace[0] == WRAPPER_VA &&
        wrapper.trace[1] == CALLEE_VA,
        "PASS: real translated trace is wrapper then tail-called callee",
        "FAIL: real translated tail-call trace sequence is unexpected");

    ok &= check(
        reference.ecx == EFFECTIVE_OBJECT &&
        wrapper.ecx == EFFECTIVE_OBJECT,
        "PASS: wrapper ECX += 0x28 matches direct-callee effective object",
        "FAIL: wrapper ECX adjustment does not match direct-callee reference");

    ok &= check(
        reference.storedBits == expectedBits &&
        wrapper.storedBits == expectedBits,
        "PASS: scalar XMM0 value stored exactly at effective this+0xDC",
        "FAIL: scalar setter did not store the expected XMM0 bits");

    ok &= check(
        architectural_results_match(&reference, &wrapper),
        "PASS: real tail-call chain matches direct-callee architectural result",
        "FAIL: real tail-call chain differs from direct-callee result");

    ok &= check(
        reference.xmm0Bits[0] == wrapper.xmm0Bits[0] &&
        reference.xmm0Bits[1] == wrapper.xmm0Bits[1] &&
        reference.xmm0Bits[2] == wrapper.xmm0Bits[2] &&
        reference.xmm0Bits[3] == wrapper.xmm0Bits[3],
        "PASS: all four XMM0 lanes match the differential reference",
        "FAIL: XMM0 architectural state differs between reference and tail-call path");

    if (reference.memoryHash == wrapper.memoryHash)
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
    trace("BUILD TAG: P3F-TAILCALL-20261018-B");
    trace("Candidate B wrapper VA: 0x001EF850");
    trace("Candidate B callee VA:  0x0021AB90");
    trace("Reference: direct translated callee at ECX=BASE+0x28 versus real wrapper tail-call");

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

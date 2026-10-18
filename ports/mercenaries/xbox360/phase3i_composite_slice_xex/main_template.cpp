/*
 * Mercenaries Xbox 360 - Phase 3I composite translated execution slice.
 *
 * One persistent 64 MiB guest arena executes five translated stages:
 *   1) 0x00050010 -> direct CALL -> 0x0004CFF0
 *   2) 0x001EF850 -> tail JMP -> 0x0021AB90 (MOVSS)
 *   3) 0x0008DE60 -> resolved RECOMP_ICALL_SAFE -> 0x0004CFF0
 *   4) 0x0008DE60 -> unresolved RECOMP_ICALL_SAFE failure path
 *   5) 0x00050010 -> direct CALL -> 0x0004CFF0 again
 *
 * The whole slice runs twice from identical initial state. Stage-by-stage
 * complete 64 MiB hashes, translated traces, architecture, XMM state and
 * persistent canaries must match.
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

#define DIRECT_CALLER_VA   0x00050010u
#define SHARED_TARGET_VA   0x0004CFF0u
#define TAIL_WRAPPER_VA    0x001EF850u
#define TAIL_CALLEE_VA     0x0021AB90u
#define ICALL_CALLER_VA    0x0008DE60u

#define DIRECT1_STACK      0x008B8000u
#define TAIL_STACK_TOP     0x008B9000u
#define ICALL_STACK        0x008BA000u
#define DIRECT2_STACK      0x008BC000u

#define TAIL_OBJECT_BASE   0x00140000u
#define TAIL_OBJECT_STRIDE 0x00001000u
#define TAIL_ECX_DELTA     0x00000028u
#define TAIL_STORE_OFFSET  0x000000DCu

#define CANARY_BASE        0x01000000u
#define MARKER_BASE        0x01000100u
#define STAGE_COUNT        5u

#define TRACE_CAPACITY     64u
#define ICALL_TRACE_SIZE   16u

enum DispatchMode
{
    DISPATCH_RESOLVED = 0,
    DISPATCH_UNRESOLVED = 1
};

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
#define xmm0v g_xmm0

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

static DWORD s_trace[TRACE_CAPACITY];
static DWORD s_traceCount = 0u;

volatile uint32_t g_icall_trace[ICALL_TRACE_SIZE];
volatile uint32_t g_icall_trace_idx = 0u;
volatile uint64_t g_icall_count = 0ui64;

static int s_dispatchMode = DISPATCH_RESOLVED;
static DWORD s_manualLookupCount = 0u;
static DWORD s_generatedLookupCount = 0u;
static DWORD s_kernelLookupCount = 0u;
static DWORD s_lastLookupVa = 0u;

static DWORD s_targetProbeCount = 0u;
static DWORD s_targetEntryEsp = 0u;
static DWORD s_targetEntryTop = 0xFFFFFFFFu;

static DWORD s_icallSavedEsp = 0u;
static DWORD s_icallPostEsp = 0u;
static DWORD s_icallPostEax = 0xFFFFFFFFu;

static DWORD s_discoveredPointerSlot = 0u;
static DWORD s_discoverySlotProbeCount = 0u;

static const char* s_runLabel = "?";

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

    OutputDebugStringA("[Merc360:P3I] ");
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

#define RECOMP_READ8(addr)      GUEST_READ8(addr)
#define RECOMP_READ16(addr)     GUEST_READ16(addr)
#define RECOMP_READ32(addr)     GUEST_READ32(addr)
#define RECOMP_READ64(addr)     GUEST_READ64(addr)
#define RECOMP_WRITE8(addr, v)  GUEST_WRITE8((addr), (v))
#define RECOMP_WRITE16(addr, v) GUEST_WRITE16((addr), (v))
#define RECOMP_WRITE32(addr, v) GUEST_WRITE32((addr), (v))
#define RECOMP_WRITE64(addr, v) GUEST_WRITE64((addr), (v))

#define PUSH32(sp, val) do { \
    uint32_t _phase3i_push_value = (uint32_t)(val); \
    (sp) -= 4u; \
    GUEST_WRITE32((sp), _phase3i_push_value); \
} while (0)

#define POP32(sp, dst) do { \
    (dst) = GUEST_READ32(sp); \
    (sp) += 4u; \
} while (0)

typedef void (*recomp_func_t)(void);

static void __P3I_SHARED_TARGET_NAME__(void);

recomp_func_t recomp_lookup_manual(uint32_t xbox_va)
{
    ++s_manualLookupCount;
    s_lastLookupVa = xbox_va;
    return NULL;
}

recomp_func_t recomp_lookup(uint32_t xbox_va)
{
    ++s_generatedLookupCount;
    s_lastLookupVa = xbox_va;

    if (s_dispatchMode == DISPATCH_RESOLVED &&
        xbox_va == SHARED_TARGET_VA)
        return (recomp_func_t)__P3I_SHARED_TARGET_NAME__;

    return NULL;
}

recomp_func_t recomp_lookup_kernel(uint32_t xbox_va)
{
    ++s_kernelLookupCount;
    s_lastLookupVa = xbox_va;
    return NULL;
}

#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \
    uint32_t _va = (uint32_t)(xbox_va); \
    const uint32_t _saved_esp_local = (uint32_t)(saved_esp); \
    const uint32_t _callee_saved_ebx = g_ebx; \
    const uint32_t _callee_saved_esi = g_esi; \
    const uint32_t _callee_saved_edi = g_edi; \
    s_icallSavedEsp = _saved_esp_local; \
    g_icall_trace[g_icall_trace_idx & (ICALL_TRACE_SIZE - 1u)] = _va; \
    ++g_icall_trace_idx; \
    ++g_icall_count; \
    if (_va >= 0x00400000u && _va < 0xFE000000u) { \
        g_esp = _saved_esp_local; eax = 0; \
        s_icallPostEsp = g_esp; s_icallPostEax = g_eax; break; \
    } \
    recomp_func_t _fn = recomp_lookup_manual(_va); \
    if (!_fn) _fn = recomp_lookup(_va); \
    if (!_fn) _fn = recomp_lookup_kernel(_va); \
    if (_fn) { \
        _fn(); \
        g_ebx = _callee_saved_ebx; \
        g_esi = _callee_saved_esi; \
        g_edi = _callee_saved_edi; \
    } \
    else { \
        g_esp = _saved_esp_local; eax = 0; \
    } \
    s_icallPostEsp = g_esp; \
    s_icallPostEax = g_eax; \
} while (0)

/* Shared real translated target body, renamed locally so direct and ICALL paths
 * both enter the same observable wrapper symbol. */
/*__P3I_SHARED_TARGET_IMPL__*/

static void __P3I_SHARED_TARGET_NAME__(void)
{
    ++s_targetProbeCount;
    s_targetEntryEsp = g_esp;
    s_targetEntryTop = GUEST_READ32(g_esp);
    phase3i_shared_target_impl();
}

/* Tail-call callee must precede the generated wrapper's C invocation. */
/*__P3I_TAIL_CALLEE__*/

/* Real translated tail-call wrapper. */
/*__P3I_TAIL_WRAPPER__*/

/* Optional one bounded ordinary helper used by the ICALL caller. */
/*__P3I_ICALL_HELPER__*/

static void phase3i_discovery_icall_slot(uint32_t slot_address, uint32_t saved_esp)
{
    s_discoveredPointerSlot = slot_address;
    ++s_discoverySlotProbeCount;

    /* Mimic the safe unresolved ICALL result after observing the real slot. */
    g_esp = saved_esp;
    g_eax = 0u;
}

/* Exact translated ICALL caller with only the ICALL operation replaced by the
 * pointer-slot observer above. */
/*__P3I_DISCOVERY_CALLER__*/

/* Real translated direct-CALL caller. */
/*__P3I_DIRECT_CALLER__*/

/* Real unchanged translated ICALL caller. */
/*__P3I_ICALL_CALLER__*/

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

static void reset_trace(void)
{
    s_traceCount = 0u;
    memset(s_trace, 0, sizeof(s_trace));
}

static void reset_target_probe(void)
{
    s_targetProbeCount = 0u;
    s_targetEntryEsp = 0u;
    s_targetEntryTop = 0xFFFFFFFFu;
}

static void reset_icall_observers(void)
{
    DWORD i;

    g_icall_trace_idx = 0u;
    g_icall_count = 0ui64;
    for (i = 0u; i < ICALL_TRACE_SIZE; ++i)
        g_icall_trace[i] = 0u;

    s_manualLookupCount = 0u;
    s_generatedLookupCount = 0u;
    s_kernelLookupCount = 0u;
    s_lastLookupVa = 0u;

    s_icallSavedEsp = 0u;
    s_icallPostEsp = 0u;
    s_icallPostEax = 0xFFFFFFFFu;
}

static DWORD tail_argument_bits(DWORD caseIndex)
{
    if (caseIndex == 0u)
        return 0x3F800000u; /* 1.0f */
    if (caseIndex == 1u)
        return 0xC0200000u; /* -2.5f */
    return 0x3EAAAAABu;     /* approx 1/3 */
}

static DWORD canary_value(DWORD caseIndex, DWORD index)
{
    return 0xC0A10000u ^ (caseIndex << 8) ^ (index * 0x11111111u);
}

static DWORD stage_marker_value(DWORD caseIndex, DWORD stageIndex)
{
    return 0x31000000u | (caseIndex << 8) | stageIndex;
}

static void seed_full_arena(DWORD caseIndex)
{
    DWORD i;

    memset(g_ram, 0, RAM_SIZE);

    for (i = 0u; i < 0x400u; ++i)
    {
        BYTE value = (BYTE)((i * 37u + caseIndex * 53u + 0x21u) & 0xFFu);
        GUEST_WRITE8(0x00100000u + i, value);
    }

    for (i = 0u; i < 4u; ++i)
        GUEST_WRITE32(CANARY_BASE + i * 4u, canary_value(caseIndex, i));

    for (i = 0u; i < STAGE_COUNT; ++i)
        GUEST_WRITE32(MARKER_BASE + i * 4u, 0u);

    memset(g_xmm0, 0, sizeof(g_xmm0));
    s_accessFault = 0;
}

static int canaries_ok(DWORD caseIndex)
{
    DWORD i;

    for (i = 0u; i < 4u; ++i)
    {
        if (GUEST_READ32(CANARY_BASE + i * 4u) !=
            canary_value(caseIndex, i))
            return 0;
    }

    return 1;
}

static void mark_stage(DWORD caseIndex, DWORD stageIndex)
{
    GUEST_WRITE32(
        MARKER_BASE + stageIndex * 4u,
        stage_marker_value(caseIndex, stageIndex));
}

static int markers_ok(DWORD caseIndex, DWORD throughStage)
{
    DWORD i;

    for (i = 0u; i <= throughStage; ++i)
    {
        if (GUEST_READ32(MARKER_BASE + i * 4u) !=
            stage_marker_value(caseIndex, i))
            return 0;
    }

    return 1;
}

static void seed_direct_stage(DWORD caseIndex, int secondPass)
{
    DWORD i;
    DWORD stack = secondPass ? DIRECT2_STACK : DIRECT1_STACK;
    DWORD bias = secondPass ? 0x80u : 0u;

    g_eax = 0x00030000u + caseIndex * 0x100u + bias;
    g_ecx = 0x00040000u + caseIndex * 0x100u + bias;
    g_edx = 0x00050000u + caseIndex * 0x100u + bias;
    g_ebx = 0x00060000u + caseIndex * 0x100u + bias;
    g_esi = 0x00070000u + caseIndex * 0x100u + bias;
    g_edi = 0x00080000u + caseIndex * 0x100u + bias;
    g_seh_ebp = 0x00090000u + caseIndex * 0x100u + bias;

    g_esp = stack;
    GUEST_WRITE32(g_esp, 0xD1EC7000u ^ caseIndex ^ bias);
    GUEST_WRITE32(g_esp - 4u, 0xA5A50000u | caseIndex | bias);

    for (i = 1u; i <= 16u; ++i)
        GUEST_WRITE32(g_esp + i * 4u, (caseIndex + i + bias) & 3u);

    reset_target_probe();
}

static void seed_tail_stage(DWORD caseIndex)
{
    DWORD i;
    DWORD argumentBits = tail_argument_bits(caseIndex);
    DWORD objectBase = TAIL_OBJECT_BASE + caseIndex * TAIL_OBJECT_STRIDE;
    uint32_t xmmSeed[4];

    for (i = 0u; i < 0x500u; ++i)
    {
        BYTE value = (BYTE)((i * 19u + caseIndex * 41u + 0x31u) & 0xFFu);
        GUEST_WRITE8(objectBase + i, value);
    }

    g_eax = 0xA1000000u | caseIndex;
    g_ecx = objectBase;
    g_edx = 0xD2000100u + caseIndex;
    g_ebx = 0xB3000200u + caseIndex;
    g_esi = 0x51000300u + caseIndex;
    g_edi = 0xD1000400u + caseIndex;
    g_seh_ebp = 0x0EB00000u + caseIndex;

    xmmSeed[0] = 0xDEAD0000u + caseIndex;
    xmmSeed[1] = 0x11110000u + caseIndex;
    xmmSeed[2] = 0x22220000u + caseIndex;
    xmmSeed[3] = 0x33330000u + caseIndex;
    memcpy(g_xmm0, xmmSeed, sizeof(xmmSeed));

    g_esp = TAIL_STACK_TOP - 8u;
    GUEST_WRITE32(g_esp, 0xC0DEF00Du ^ caseIndex);
    GUEST_WRITE32(g_esp + 4u, argumentBits);
}

static void seed_icall_stage(DWORD caseIndex)
{
    DWORD i;

    g_eax = 0x00030000u + caseIndex * 0x100u;
    g_ecx = 0x00040000u + caseIndex * 0x100u;
    g_edx = 0x00050000u + caseIndex * 0x100u;
    g_ebx = 0x00060000u + caseIndex * 0x100u;
    g_esi = 0x00070000u + caseIndex * 0x100u;
    g_edi = 0x00080000u + caseIndex * 0x100u;
    g_seh_ebp = 0x00090000u + caseIndex * 0x100u;

    g_esp = ICALL_STACK;
    GUEST_WRITE32(g_esp, 0x1CA11000u ^ caseIndex);
    GUEST_WRITE32(g_esp - 4u, 0xA5A51000u | caseIndex);

    for (i = 1u; i <= 16u; ++i)
        GUEST_WRITE32(g_esp + i * 4u, (caseIndex + i) & 3u);
}

static DWORD trace_occurrences_range(DWORD start, DWORD end, DWORD va)
{
    DWORD i;
    DWORD count = 0u;
    DWORD cappedEnd = end < TRACE_CAPACITY ? end : TRACE_CAPACITY;

    for (i = start; i < cappedEnd; ++i)
    {
        if (s_trace[i] == va)
            ++count;
    }

    return count;
}

static int discover_pointer_slot(DWORD caseIndex, DWORD* outSlot)
{
    DWORD slotA;
    DWORD slotB;
    DWORD pass;

    if (!outSlot)
        return 0;

    for (pass = 0u; pass < 2u; ++pass)
    {
        seed_full_arena(caseIndex);
        reset_trace();
        seed_icall_stage(caseIndex);

        s_discoveredPointerSlot = 0u;
        s_discoverySlotProbeCount = 0u;
        phase3i_discovery_caller();

        if (s_accessFault != 0 ||
            s_discoverySlotProbeCount != 1u ||
            s_discoveredPointerSlot == 0u ||
            !guest_ptr(s_discoveredPointerSlot, 4u))
            return 0;

        if (pass == 0u)
            slotA = s_discoveredPointerSlot;
        else
            slotB = s_discoveredPointerSlot;
    }

    if (slotA != slotB)
        return 0;

    *outSlot = slotA;
    return 1;
}

typedef struct SliceResult
{
    unsigned __int64 checkpoint[STAGE_COUNT];

    DWORD eax;
    DWORD ecx;
    DWORD edx;
    DWORD esp;
    DWORD ebx;
    DWORD esi;
    DWORD edi;
    DWORD sehEbp;
    DWORD xmm0Bits[4];

    DWORD pointerSlot;
    int accessFault;
    int canaryOk;

    DWORD traceCount;
    DWORD trace[TRACE_CAPACITY];
} SliceResult;

static int run_direct_stage(
    DWORD caseIndex,
    int secondPass,
    DWORD stageIndex,
    unsigned __int64* checkpoint)
{
    DWORD before = s_traceCount;
    DWORD stack = secondPass ? DIRECT2_STACK : DIRECT1_STACK;
    int ok = 1;

    seed_direct_stage(caseIndex, secondPass);
    __P3I_DIRECT_CALLER_NAME__();

    ok &= check(
        s_accessFault == 0,
        "PASS: direct-CALL stage has no guest-memory fault",
        "FAIL: direct-CALL stage triggered guest-memory fault");

    ok &= check(
        s_targetProbeCount == 1u &&
        s_targetEntryEsp == stack - 4u &&
        s_targetEntryTop == 0u,
        "PASS: direct-CALL target sees one zero synthetic return slot",
        "FAIL: direct-CALL target entry stack is incorrect");

    ok &= check(
        g_esp == stack + 4u,
        "PASS: direct-CALL stage restores callee stack then returns caller",
        "FAIL: direct-CALL stage final ESP is incorrect");

    ok &= check(
        s_traceCount == before + 2u &&
        before + 1u < TRACE_CAPACITY &&
        s_trace[before] == DIRECT_CALLER_VA &&
        s_trace[before + 1u] == SHARED_TARGET_VA,
        "PASS: direct-CALL stage trace is caller then shared target",
        "FAIL: direct-CALL stage trace is unexpected");

    ok &= check(
        canaries_ok(caseIndex),
        "PASS: persistent canaries survive direct-CALL stage",
        "FAIL: persistent canary changed during direct-CALL stage");

    mark_stage(caseIndex, stageIndex);
    ok &= check(
        markers_ok(caseIndex, stageIndex),
        "PASS: cumulative stage markers remain intact",
        "FAIL: cumulative stage marker corruption detected");

    *checkpoint = hash_guest_ram();
    return ok;
}

static int run_tail_stage(
    DWORD caseIndex,
    DWORD stageIndex,
    unsigned __int64* checkpoint)
{
    DWORD before = s_traceCount;
    DWORD objectBase = TAIL_OBJECT_BASE + caseIndex * TAIL_OBJECT_STRIDE;
    DWORD effectiveObject = objectBase + TAIL_ECX_DELTA;
    DWORD storeAddress = effectiveObject + TAIL_STORE_OFFSET;
    DWORD expectedBits = tail_argument_bits(caseIndex);
    DWORD xmmBits[4];
    int ok = 1;

    seed_tail_stage(caseIndex);
    __P3I_TAIL_WRAPPER_NAME__();
    memcpy(xmmBits, g_xmm0, sizeof(xmmBits));

    ok &= check(
        s_accessFault == 0,
        "PASS: tail-call/MOVSS stage has no guest-memory fault",
        "FAIL: tail-call/MOVSS stage triggered guest-memory fault");

    ok &= check(
        g_esp == TAIL_STACK_TOP &&
        g_ecx == effectiveObject,
        "PASS: tail wrapper ECX delta and ret-4 stack cleanup are exact",
        "FAIL: tail wrapper ECX or ret-4 stack state is incorrect");

    ok &= check(
        GUEST_READ32(storeAddress) == expectedBits &&
        xmmBits[0] == expectedBits &&
        xmmBits[1] == 0u &&
        xmmBits[2] == 0u &&
        xmmBits[3] == 0u,
        "PASS: tail-called MOVSS loads/stores exact scalar and zeroes upper lanes",
        "FAIL: tail-called MOVSS state differs from proven contract");

    ok &= check(
        s_traceCount == before + 2u &&
        before + 1u < TRACE_CAPACITY &&
        s_trace[before] == TAIL_WRAPPER_VA &&
        s_trace[before + 1u] == TAIL_CALLEE_VA,
        "PASS: tail-call stage trace is wrapper then translated callee",
        "FAIL: tail-call stage trace is unexpected");

    ok &= check(
        canaries_ok(caseIndex),
        "PASS: persistent canaries survive tail-call/MOVSS stage",
        "FAIL: persistent canary changed during tail-call/MOVSS stage");

    mark_stage(caseIndex, stageIndex);
    ok &= check(
        markers_ok(caseIndex, stageIndex),
        "PASS: cumulative stage markers remain intact",
        "FAIL: cumulative stage marker corruption detected");

    *checkpoint = hash_guest_ram();
    return ok;
}

static int run_icall_stage(
    DWORD caseIndex,
    DWORD pointerSlot,
    int resolved,
    DWORD stageIndex,
    unsigned __int64* checkpoint)
{
    DWORD before = s_traceCount;
    DWORD after;
    int ok = 1;

    seed_icall_stage(caseIndex);
    GUEST_WRITE32(pointerSlot, SHARED_TARGET_VA);

    s_dispatchMode = resolved ? DISPATCH_RESOLVED : DISPATCH_UNRESOLVED;
    reset_icall_observers();
    reset_target_probe();

    __P3I_ICALL_CALLER_NAME__();
    after = s_traceCount;

    ok &= check(
        s_accessFault == 0,
        "PASS: ICALL stage has no guest-memory fault",
        "FAIL: ICALL stage triggered guest-memory fault");

    ok &= check(
        GUEST_READ32(pointerSlot) == SHARED_TARGET_VA &&
        g_icall_trace_idx == 1u &&
        g_icall_count == 1ui64 &&
        g_icall_trace[0] == SHARED_TARGET_VA,
        "PASS: unchanged ICALL caller reads nonzero code VA from discovered slot",
        "FAIL: ICALL caller did not consume the seeded real guest pointer slot");

    ok &= check(
        before < TRACE_CAPACITY &&
        s_trace[before] == ICALL_CALLER_VA,
        "PASS: ICALL stage begins at real translated caller",
        "FAIL: ICALL stage trace does not begin at translated caller");

    if (resolved)
    {
        ok &= check(
            s_manualLookupCount == 1u &&
            s_generatedLookupCount == 1u &&
            s_kernelLookupCount == 0u &&
            s_lastLookupVa == SHARED_TARGET_VA,
            "PASS: resolved ICALL uses manual miss then generated hit",
            "FAIL: resolved ICALL lookup chain is unexpected");

        ok &= check(
            s_targetProbeCount == 1u &&
            s_targetEntryTop == 0u &&
            s_targetEntryEsp == s_icallSavedEsp - 4u &&
            s_icallPostEsp == s_icallSavedEsp,
            "PASS: resolved ICALL target stack and return state are exact",
            "FAIL: resolved ICALL target/stack state is incorrect");

        ok &= check(
            trace_occurrences_range(before, after, SHARED_TARGET_VA) == 1u,
            "PASS: resolved ICALL stage enters shared translated target exactly once",
            "FAIL: resolved ICALL target trace count is unexpected");
    }
    else
    {
        ok &= check(
            s_manualLookupCount == 1u &&
            s_generatedLookupCount == 1u &&
            s_kernelLookupCount == 1u &&
            s_lastLookupVa == SHARED_TARGET_VA,
            "PASS: unresolved ICALL exhausts manual/generated/kernel lookup chain",
            "FAIL: unresolved ICALL lookup chain is unexpected");

        ok &= check(
            s_targetProbeCount == 0u &&
            s_icallPostEsp == s_icallSavedEsp &&
            s_icallPostEax == 0u,
            "PASS: unresolved ICALL restores saved ESP, returns EAX=0, enters no target",
            "FAIL: unresolved ICALL safe-failure state is incorrect");

        ok &= check(
            trace_occurrences_range(before, after, SHARED_TARGET_VA) == 0u,
            "PASS: unresolved ICALL stage never enters shared translated target",
            "FAIL: unresolved ICALL unexpectedly entered translated target");
    }

    ok &= check(
        g_esp == ICALL_STACK + 4u,
        "PASS: ICALL caller continues after dispatch and returns with exact ESP",
        "FAIL: ICALL caller final ESP is incorrect");

    ok &= check(
        canaries_ok(caseIndex),
        "PASS: persistent canaries survive ICALL stage",
        "FAIL: persistent canary changed during ICALL stage");

    mark_stage(caseIndex, stageIndex);
    ok &= check(
        markers_ok(caseIndex, stageIndex),
        "PASS: cumulative stage markers remain intact",
        "FAIL: cumulative stage marker corruption detected");

    *checkpoint = hash_guest_ram();
    return ok;
}

static int run_composite(
    DWORD caseIndex,
    DWORD pointerSlot,
    const char* runLabel,
    SliceResult* result)
{
    DWORD i;
    int ok = 1;

    memset(result, 0, sizeof(*result));
    s_runLabel = runLabel;

    seed_full_arena(caseIndex);
    reset_trace();
    reset_icall_observers();
    reset_target_probe();

    ok &= run_direct_stage(
        caseIndex, 0, 0u, &result->checkpoint[0]);

    ok &= run_tail_stage(
        caseIndex, 1u, &result->checkpoint[1]);

    ok &= run_icall_stage(
        caseIndex, pointerSlot, 1, 2u, &result->checkpoint[2]);

    ok &= run_icall_stage(
        caseIndex, pointerSlot, 0, 3u, &result->checkpoint[3]);

    ok &= run_direct_stage(
        caseIndex, 1, 4u, &result->checkpoint[4]);

    result->eax = g_eax;
    result->ecx = g_ecx;
    result->edx = g_edx;
    result->esp = g_esp;
    result->ebx = g_ebx;
    result->esi = g_esi;
    result->edi = g_edi;
    result->sehEbp = g_seh_ebp;
    memcpy(result->xmm0Bits, g_xmm0, sizeof(result->xmm0Bits));

    result->pointerSlot = pointerSlot;
    result->accessFault = s_accessFault;
    result->canaryOk = canaries_ok(caseIndex);

    result->traceCount = s_traceCount;
    for (i = 0u; i < TRACE_CAPACITY; ++i)
        result->trace[i] = s_trace[i];

    return ok;
}

static int slice_results_match(const SliceResult* a, const SliceResult* b)
{
    DWORD i;
    DWORD limit;

    if (a->eax != b->eax ||
        a->ecx != b->ecx ||
        a->edx != b->edx ||
        a->esp != b->esp ||
        a->ebx != b->ebx ||
        a->esi != b->esi ||
        a->edi != b->edi ||
        a->sehEbp != b->sehEbp ||
        a->pointerSlot != b->pointerSlot ||
        a->accessFault != b->accessFault ||
        a->canaryOk != b->canaryOk ||
        a->traceCount != b->traceCount)
        return 0;

    for (i = 0u; i < 4u; ++i)
    {
        if (a->xmm0Bits[i] != b->xmm0Bits[i])
            return 0;
    }

    for (i = 0u; i < STAGE_COUNT; ++i)
    {
        if (a->checkpoint[i] != b->checkpoint[i])
            return 0;
    }

    limit = a->traceCount < TRACE_CAPACITY
        ? a->traceCount : TRACE_CAPACITY;

    for (i = 0u; i < limit; ++i)
    {
        if (a->trace[i] != b->trace[i])
            return 0;
    }

    return 1;
}

static int run_case(DWORD caseIndex)
{
    DWORD pointerSlot = 0u;
    SliceResult runA;
    SliceResult runB;
    char line[360];
    DWORD i;
    int ok = 1;

    ok &= check(
        discover_pointer_slot(caseIndex, &pointerSlot),
        "PASS: real ICALL guest pointer slot is deterministic across discovery runs",
        "FAIL: ICALL guest pointer-slot discovery is unstable or invalid");

    if (!ok)
        return 0;

    sprintf(
        line,
        "CASE %u discovered real ICALL pointer slot=%08X",
        (unsigned int)caseIndex,
        (unsigned int)pointerSlot);
    trace(line);

    ok &= run_composite(caseIndex, pointerSlot, "A", &runA);
    ok &= run_composite(caseIndex, pointerSlot, "B", &runB);

    for (i = 0u; i < STAGE_COUNT; ++i)
    {
        sprintf(
            line,
            "CASE %u checkpoint %u A=%08X%08X B=%08X%08X",
            (unsigned int)caseIndex,
            (unsigned int)(i + 1u),
            (unsigned int)(runA.checkpoint[i] >> 32),
            (unsigned int)runA.checkpoint[i],
            (unsigned int)(runB.checkpoint[i] >> 32),
            (unsigned int)runB.checkpoint[i]);
        trace(line);
    }

    ok &= check(
        runA.accessFault == 0 &&
        runB.accessFault == 0 &&
        runA.canaryOk &&
        runB.canaryOk,
        "PASS: both composite runs finish fault-free with persistent canaries intact",
        "FAIL: composite run fault/canary state is incorrect");

    ok &= check(
        slice_results_match(&runA, &runB),
        "PASS: complete five-stage translated slice is deterministic across repeated runs",
        "FAIL: repeated five-stage translated slices diverge");

    ok &= check(
        runA.pointerSlot != 0u &&
        runA.pointerSlot == runB.pointerSlot,
        "PASS: both composite runs use the same real nonzero guest function-pointer slot",
        "FAIL: composite ICALL pointer-slot state diverged");

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

    s_logFile = CreateFileA(
        "game:\\merc360-phase3i-composite-slice.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 3I COMPOSITE TRANSLATED SLICE START");
    trace("BUILD TAG: P3I-SLICE-20261018-A");
    trace("Stages: direct CALL -> tail/MOVSS -> resolved ICALL -> unresolved ICALL -> direct CALL");
    trace("Real VAs: 00050010/0004CFF0, 001EF850/0021AB90, 0008DE60");

    g_ram = (BYTE*)malloc(RAM_SIZE);

    if (!g_ram)
    {
        trace("FATAL: could not allocate 64 MiB guest RAM");
        goto wait_for_exit;
    }

    result = run_fixture();

    if (result)
        trace("PHASE 3I COMPOSITE TRANSLATED SLICE RESULT: PASS");
    else
        trace("PHASE 3I COMPOSITE TRANSLATED SLICE RESULT: FAIL");

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

    trace("PHASE 3I COMPOSITE TRANSLATED SLICE END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

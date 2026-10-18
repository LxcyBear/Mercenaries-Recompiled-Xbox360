/*
 * Mercenaries Xbox 360 - Phase 3H translated indirect-call dispatch.
 *
 * Local prep selects one real mechanically translated RECOMP_ICALL_SAFE site
 * and injects the exact retail-derived caller plus the already hardware-proven
 * translated target 0x0004CFF0. Generated retail C remains under build/.
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

#define RAM_SIZE               0x04000000u
#define RAM_MASK               0x03FFFFFFu
#define MIRROR_END             0x74000000u
#define KSEG_BASE              0x80000000u
#define KSEG_END               0xC0000000u
#define FENCE_BASE             0x80000000u
#define FENCE_END              0x80001000u
#define KERNEL_BASE            0x80010000u
#define KERNEL_END             0x80011000u

#define CALLER_VA              __PHASE3H_CALLER_VA__
#define DISPATCH_TARGET_VA     __PHASE3H_TARGET_VA__
#define RANGE_REJECT_VA        0x00400000u
#define CALLER_INITIAL_ESP     0x008BFC00u
#define ICALL_TARGET_SLOT_BASE 0x000A0000u

#define ICALL_TRACE_SIZE 16u

enum Phase3HMode
{
    PHASE3H_RESOLVED = 0,
    PHASE3H_UNRESOLVED = 1,
    PHASE3H_RANGE_REJECT = 2
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

volatile uint32_t g_icall_trace[ICALL_TRACE_SIZE];
volatile uint32_t g_icall_trace_idx = 0u;
volatile uint64_t g_icall_count = 0ui64;

static int s_dispatchMode = PHASE3H_RESOLVED;
/*
 * Exact guest VA computed by the selected translated caller under the current
 * deterministic seed. Discovery runs first; resolved lookup then maps this
 * observed guest key to the already-proven translated target 0x0004CFF0.
 */
static uint32_t s_resolvedGuestVa = 0u;
static uint32_t s_discoveredPointerSlot = 0u;
static DWORD s_discoverySlotProbeCount = 0u;

static DWORD s_manualLookupCount = 0u;
static DWORD s_generatedLookupCount = 0u;
static DWORD s_kernelLookupCount = 0u;
static DWORD s_lastLookupVa = 0u;

static DWORD s_targetProbeCount = 0u;
static DWORD s_targetEntryEsp = 0u;
static DWORD s_targetEntryTop = 0xFFFFFFFFu;
static DWORD s_targetClobberIssued = 0u;

static DWORD s_icallSavedEsp = 0u;
static DWORD s_icallPostEsp = 0u;
static DWORD s_icallPostEax = 0u;

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

    OutputDebugStringA("[Merc360:P3H] ");
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
    uint32_t _phase3h_push_value = (uint32_t)(val); \
    (sp) -= 4u; \
    GUEST_WRITE32((sp), _phase3h_push_value); \
} while (0)

#define POP32(sp, dst) do { \
    (dst) = GUEST_READ32(sp); \
    (sp) += 4u; \
} while (0)

typedef void (*recomp_func_t)(void);

static void __PHASE3H_TARGET_NAME__(void);

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

    if (s_dispatchMode == PHASE3H_RESOLVED &&
        xbox_va == s_resolvedGuestVa)
        return (recomp_func_t)__PHASE3H_TARGET_NAME__;

    return NULL;
}

recomp_func_t recomp_lookup_kernel(uint32_t xbox_va)
{
    ++s_kernelLookupCount;
    s_lastLookupVa = xbox_va;
    return NULL;
}

/*
 * Keep this macro behavior aligned with the maintained generic runtime:
 * trace/count the target, reject garbage middle-range VAs, try
 * manual/generated/kernel lookup, restore EBX/ESI/EDI after a resolved call,
 * and restore saved_esp + EAX=0 when resolution fails.
 */
#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \
    uint32_t _va = (uint32_t)(xbox_va); \
    const uint32_t _saved_esp_local = (uint32_t)(saved_esp); \
    const uint32_t _callee_saved_ebx = g_ebx; \
    const uint32_t _callee_saved_esi = g_esi; \
    const uint32_t _callee_saved_edi = g_edi; \
    s_icallSavedEsp = _saved_esp_local; \
    g_icall_trace[g_icall_trace_idx & (ICALL_TRACE_SIZE-1)] = _va; \
    g_icall_trace_idx++; \
    g_icall_count++; \
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
    else { g_esp = _saved_esp_local; eax = 0; } \
    s_icallPostEsp = g_esp; s_icallPostEax = g_eax; \
} while(0)

/* Optional one bounded real direct translated helper used by the caller. */
/*__PHASE3H_DIRECT_HELPER__*/

/* Real translated dispatch target body, renamed locally by prep. */
/*__PHASE3H_TARGET_IMPL__*/

static void __PHASE3H_TARGET_NAME__(void)
{
    ++s_targetProbeCount;
    s_targetEntryEsp = g_esp;
    s_targetEntryTop = GUEST_READ32(g_esp);

    phase3h_target_impl();

    /*
     * Deliberately violate the callee-saved register convention after the
     * translated body returns. RECOMP_ICALL_SAFE must repair all three.
     */
    g_ebx = 0xBADC0DE1u;
    g_esi = 0xBADC0DE2u;
    g_edi = 0xBADC0DE3u;
    s_targetClobberIssued = 1u;
}

static void phase3h_reference_icall(uint32_t xbox_va, uint32_t saved_esp)
{
    uint32_t newEsp;
    uint32_t savedEbx = g_ebx;
    uint32_t savedEsi = g_esi;
    uint32_t savedEdi = g_edi;

    s_icallSavedEsp = saved_esp;
    g_icall_trace[g_icall_trace_idx & (ICALL_TRACE_SIZE - 1u)] = xbox_va;
    ++g_icall_trace_idx;
    ++g_icall_count;

    /*
     * The generated line being replaced includes PUSH32(esp, 0), so reproduce
     * that stack effect independently without using PUSH32.
     */
    newEsp = g_esp - 4u;
    GUEST_WRITE32(newEsp, 0u);
    g_esp = newEsp;

    if (xbox_va >= 0x00400000u && xbox_va < 0xFE000000u)
    {
        g_esp = saved_esp;
        g_eax = 0u;
        s_icallPostEsp = g_esp;
        s_icallPostEax = g_eax;
        return;
    }

    if (s_dispatchMode == PHASE3H_RESOLVED &&
        xbox_va == s_resolvedGuestVa)
    {
        __PHASE3H_TARGET_NAME__();
        g_ebx = savedEbx;
        g_esi = savedEsi;
        g_edi = savedEdi;
        s_icallPostEsp = g_esp;
        s_icallPostEax = g_eax;
        return;
    }

    g_esp = saved_esp;
    g_eax = 0u;
    s_icallPostEsp = g_esp;
    s_icallPostEax = g_eax;
}

static void phase3h_discovery_icall_slot(uint32_t slot_address, uint32_t saved_esp)
{
    s_discoveredPointerSlot = slot_address;
    ++s_discoverySlotProbeCount;

    /*
     * Preserve the exact unresolved ICALL behavior after observing the slot.
     * The discovery caller therefore continues exactly as the translated caller
     * would after a failed indirect dispatch.
     */
    phase3h_reference_icall(GUEST_READ32(slot_address), saved_esp);
}

/* Exact translated caller with ICALL rewritten only to expose pointer-slot address. */
/*__PHASE3H_DISCOVERY_CALLER__*/

/* Exact translated caller with only ICALL rewritten for differential reference. */
/*__PHASE3H_REFERENCE_CALLER__*/

/* Exact unmodified translated caller containing RECOMP_ICALL_SAFE. */
/*__PHASE3H_REAL_CALLER__*/

typedef struct RunResult
{
    DWORD eax;
    DWORD ecx;
    DWORD edx;
    DWORD esp;
    DWORD ebx;
    DWORD esi;
    DWORD edi;
    unsigned __int64 memoryHash;
    int accessFault;

    DWORD traceCount;
    DWORD trace[TRACE_CAPACITY];

    DWORD icallTraceIdx;
    unsigned __int64 icallCount;
    DWORD icallTarget;

    DWORD manualLookups;
    DWORD generatedLookups;
    DWORD kernelLookups;
    DWORD lastLookupVa;

    DWORD targetProbeCount;
    DWORD targetEntryEsp;
    DWORD targetEntryTop;
    DWORD targetClobberIssued;

    DWORD icallSavedEsp;
    DWORD icallPostEsp;
    DWORD icallPostEax;
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
    DWORD i;

    s_accessFault = 0;

    s_traceCount = 0u;
    memset(s_trace, 0, sizeof(s_trace));

    g_icall_trace_idx = 0u;
    g_icall_count = 0ui64;
    for (i = 0u; i < ICALL_TRACE_SIZE; ++i)
        g_icall_trace[i] = 0u;

    s_manualLookupCount = 0u;
    s_generatedLookupCount = 0u;
    s_kernelLookupCount = 0u;
    s_lastLookupVa = 0u;

    s_targetProbeCount = 0u;
    s_targetEntryEsp = 0u;
    s_targetEntryTop = 0xFFFFFFFFu;
    s_targetClobberIssued = 0u;

    s_icallSavedEsp = 0u;
    s_icallPostEsp = 0u;
    s_icallPostEax = 0xFFFFFFFFu;

    s_discoveredPointerSlot = 0u;
    s_discoverySlotProbeCount = 0u;
}

static void seed_guest_state(DWORD caseIndex, int mode)
{
    DWORD i;

    memset(g_ram, 0, RAM_SIZE);

    g_eax = 0x00030000u + caseIndex * 0x100u;
    g_ecx = 0x00040000u + caseIndex * 0x100u;
    g_edx = 0x00050000u + caseIndex * 0x100u;
    g_ebx = 0x00060000u + caseIndex * 0x100u;
    g_esi = 0x00070000u + caseIndex * 0x100u;
    g_edi = 0x00080000u + caseIndex * 0x100u;
    g_seh_ebp = 0x00090000u + caseIndex * 0x100u;

    g_esp = CALLER_INITIAL_ESP;
    GUEST_WRITE32(g_esp, 0xC011CA11u ^ caseIndex);

    for (i = 1u; i <= 16u; ++i)
        GUEST_WRITE32(g_esp + i * 4u, (caseIndex + i) & 3u);

    GUEST_WRITE32(g_esp - 4u, 0xA5A50000u | caseIndex);

    s_dispatchMode = mode;

    /*
     * Do not force the call operand. The exact translated caller is allowed to
     * compute its real deterministic guest target from this seeded state.
     */
    /*__PHASE3H_TARGET_SEED__*/

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
    result->memoryHash = hash_guest_ram();
    result->accessFault = s_accessFault;

    result->traceCount = s_traceCount;
    for (i = 0u; i < TRACE_CAPACITY; ++i)
        result->trace[i] = s_trace[i];

    result->icallTraceIdx = g_icall_trace_idx;
    result->icallCount = g_icall_count;
    result->icallTarget = g_icall_trace[0];

    result->manualLookups = s_manualLookupCount;
    result->generatedLookups = s_generatedLookupCount;
    result->kernelLookups = s_kernelLookupCount;
    result->lastLookupVa = s_lastLookupVa;

    result->targetProbeCount = s_targetProbeCount;
    result->targetEntryEsp = s_targetEntryEsp;
    result->targetEntryTop = s_targetEntryTop;
    result->targetClobberIssued = s_targetClobberIssued;

    result->icallSavedEsp = s_icallSavedEsp;
    result->icallPostEsp = s_icallPostEsp;
    result->icallPostEax = s_icallPostEax;
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
        reference->memoryHash == real->memoryHash &&
        reference->accessFault == real->accessFault &&
        reference->traceCount == real->traceCount &&
        reference->icallTraceIdx == real->icallTraceIdx &&
        reference->icallCount == real->icallCount &&
        reference->icallTarget == real->icallTarget &&
        reference->targetProbeCount == real->targetProbeCount &&
        reference->targetEntryEsp == real->targetEntryEsp &&
        reference->targetEntryTop == real->targetEntryTop &&
        reference->targetClobberIssued == real->targetClobberIssued &&
        reference->icallSavedEsp == real->icallSavedEsp &&
        reference->icallPostEsp == real->icallPostEsp &&
        reference->icallPostEax == real->icallPostEax;
}

static DWORD trace_occurrences(const RunResult* result, DWORD va)
{
    DWORD i;
    DWORD count = 0u;
    DWORD limit = result->traceCount < TRACE_CAPACITY
        ? result->traceCount : TRACE_CAPACITY;

    for (i = 0u; i < limit; ++i)
    {
        if (result->trace[i] == va)
            ++count;
    }

    return count;
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

static const char* mode_name(int mode)
{
    if (mode == PHASE3H_RESOLVED)
        return "RESOLVED";
    if (mode == PHASE3H_UNRESOLVED)
        return "UNRESOLVED";
    return "RANGE_REJECT";
}

static int discover_case_pointer_slot(DWORD caseIndex, DWORD* outSlot)
{
    RunResult discovery;
    char line[300];

    if (!outSlot)
        return 0;

    /*
     * Execute an exact translated copy where only the ICALL operation is
     * replaced by a slot-observer helper. All instructions that compute the
     * function-pointer slot address remain mechanically translated and intact.
     */
    seed_guest_state(caseIndex, PHASE3H_UNRESOLVED);
    s_resolvedGuestVa = 0u;
    phase3h_discovery_caller();
    capture_result(&discovery);

    if (discovery.accessFault != 0 ||
        s_discoverySlotProbeCount != 1u ||
        s_discoveredPointerSlot == 0u)
    {
        trace("FAIL: pointer-slot discovery did not produce one clean nonzero guest slot");
        return 0;
    }

    if (!guest_ptr(s_discoveredPointerSlot, 4u))
    {
        trace("FAIL: discovered function-pointer slot is outside mapped guest RAM");
        return 0;
    }

    *outSlot = s_discoveredPointerSlot;

    sprintf(
        line,
        "CASE %u DISCOVERY guest pointer slot=%08X initial=%08X",
        (unsigned int)caseIndex,
        (unsigned int)*outSlot,
        (unsigned int)GUEST_READ32(*outSlot));
    trace(line);

    return 1;
}

static int run_one_case(
    DWORD caseIndex,
    int mode,
    DWORD pointerSlot,
    DWORD expectedTarget)
{
    RunResult reference;
    RunResult real;
    DWORD expectedEbx;
    DWORD expectedEsi;
    DWORD expectedEdi;
    char line[384];
    int ok = 1;

    seed_guest_state(caseIndex, mode);
    GUEST_WRITE32(pointerSlot, expectedTarget);
    s_resolvedGuestVa = expectedTarget;
    expectedEbx = g_ebx;
    expectedEsi = g_esi;
    expectedEdi = g_edi;
    phase3h_reference_caller();
    capture_result(&reference);

    seed_guest_state(caseIndex, mode);
    GUEST_WRITE32(pointerSlot, expectedTarget);
    s_resolvedGuestVa = expectedTarget;
    __PHASE3H_CALLER_NAME__();
    capture_result(&real);

    sprintf(
        line,
        "CASE %u %s ref  eax=%08X esp=%08X icall=%08X probe=%u hash=%08X%08X",
        (unsigned int)caseIndex,
        mode_name(mode),
        (unsigned int)reference.eax,
        (unsigned int)reference.esp,
        (unsigned int)reference.icallTarget,
        (unsigned int)reference.targetProbeCount,
        (unsigned int)(reference.memoryHash >> 32),
        (unsigned int)reference.memoryHash);
    trace(line);

    sprintf(
        line,
        "CASE %u %s real eax=%08X esp=%08X icall=%08X probe=%u lookups=%u/%u/%u hash=%08X%08X",
        (unsigned int)caseIndex,
        mode_name(mode),
        (unsigned int)real.eax,
        (unsigned int)real.esp,
        (unsigned int)real.icallTarget,
        (unsigned int)real.targetProbeCount,
        (unsigned int)real.manualLookups,
        (unsigned int)real.generatedLookups,
        (unsigned int)real.kernelLookups,
        (unsigned int)(real.memoryHash >> 32),
        (unsigned int)real.memoryHash);
    trace(line);

    ok &= check(
        reference.accessFault == 0 && real.accessFault == 0,
        "PASS: reference and real ICALL paths complete without guest-memory faults",
        "FAIL: reference or real ICALL path triggered guest-memory fault");

    ok &= check(
        pointerSlot != 0u &&
        expectedTarget == DISPATCH_TARGET_VA &&
        expectedTarget != 0u,
        "PASS: nonzero translated code VA is assigned to the discovered real guest pointer slot",
        "FAIL: guest function-pointer slot setup is incorrect");

    ok &= check(
        reference.icallTraceIdx == 1u &&
        real.icallTraceIdx == 1u &&
        reference.icallCount == 1ui64 &&
        real.icallCount == 1ui64 &&
        reference.icallTarget == expectedTarget &&
        real.icallTarget == expectedTarget,
        "PASS: unchanged translated caller reads nonzero code VA from its real guest pointer slot",
        "FAIL: translated caller did not consume the seeded real guest function-pointer slot");

    if (mode == PHASE3H_RESOLVED)
    {
        ok &= check(
            reference.targetProbeCount == 1u &&
            real.targetProbeCount == 1u,
            "PASS: translated dispatch target entered exactly once",
            "FAIL: resolved target entry count is unexpected");

        ok &= check(
            reference.icallSavedEsp == real.icallSavedEsp &&
            reference.icallPostEsp == reference.icallSavedEsp &&
            real.icallPostEsp == real.icallSavedEsp,
            "PASS: resolved ICALL returns to the saved pre-call ESP",
            "FAIL: resolved ICALL post-dispatch ESP is incorrect");

        ok &= check(
            reference.targetEntryEsp == reference.icallSavedEsp - 4u &&
            real.targetEntryEsp == real.icallSavedEsp - 4u &&
            reference.targetEntryTop == 0u &&
            real.targetEntryTop == 0u,
            "PASS: resolved ICALL target sees one zero-valued synthetic return slot",
            "FAIL: resolved ICALL target stack entry is incorrect");

        ok &= check(
            real.manualLookups == 1u &&
            real.generatedLookups == 1u &&
            real.kernelLookups == 0u &&
            real.lastLookupVa == expectedTarget,
            "PASS: real dispatcher resolves nonzero guest code VA through generated lookup",
            "FAIL: resolved lookup chain is unexpected");

        ok &= check(
            real.targetClobberIssued == 1u &&
            real.ebx == expectedEbx &&
            real.esi == expectedEsi &&
            real.edi == expectedEdi,
            "PASS: RECOMP_ICALL_SAFE restores EBX/ESI/EDI after target clobber",
            "FAIL: callee-saved registers were not restored after resolved ICALL");

        ok &= check(
            traces_match(&reference, &real) &&
            real.traceCount >= 2u &&
            real.trace[0] == CALLER_VA &&
            trace_occurrences(&real, DISPATCH_TARGET_VA) == 1u,
            "PASS: resolved translated trace matches reference and enters indirect target once",
            "FAIL: resolved translated trace sequence is unexpected");
    }
    else
    {
        ok &= check(
            reference.targetProbeCount == 0u &&
            real.targetProbeCount == 0u,
            "PASS: unresolved ICALL does not enter translated dispatch target",
            "FAIL: unresolved ICALL unexpectedly entered dispatch target");

        ok &= check(
            reference.icallPostEax == 0u &&
            real.icallPostEax == 0u &&
            reference.icallPostEsp == reference.icallSavedEsp &&
            real.icallPostEsp == real.icallSavedEsp,
            "PASS: unresolved ICALL immediately restores saved ESP and forces EAX=0",
            "FAIL: unresolved ICALL immediate safe-failure contract is incorrect");

        ok &= check(
            traces_match(&reference, &real) &&
            real.traceCount >= 1u &&
            real.trace[0] == CALLER_VA &&
            trace_occurrences(&real, DISPATCH_TARGET_VA) == 0u,
            "PASS: unresolved translated trace matches reference and never enters target",
            "FAIL: unresolved translated trace is unexpected");

        ok &= check(
            real.manualLookups == 1u &&
            real.generatedLookups == 1u &&
            real.kernelLookups == 1u &&
            real.lastLookupVa == expectedTarget,
            "PASS: unresolved ICALL exhausts manual/generated/kernel lookup chain",
            "FAIL: unresolved lookup chain is unexpected");
    }

    ok &= check(
        reference.esp == CALLER_INITIAL_ESP + 4u &&
        real.esp == CALLER_INITIAL_ESP + 4u,
        "PASS: ICALL stack handling plus caller RET produces exact final ESP",
        "FAIL: final guest ESP differs from expected caller return state");

    ok &= check(
        architectural_results_match(&reference, &real),
        "PASS: real RECOMP_ICALL_SAFE matches independent dispatch reference",
        "FAIL: real RECOMP_ICALL_SAFE differs from independent reference");

    if (reference.memoryHash == real.memoryHash)
        trace("PASS: full 64 MiB guest-RAM hashes match");
    else
    {
        trace("FAIL: full 64 MiB guest-RAM hashes differ");
        ok = 0;
    }

    return ok;
}

static int run_range_guard_case(DWORD caseIndex)
{
    RunResult reference;
    RunResult real;
    DWORD savedEsp;
    int ok = 1;

    /*
     * The selected real caller is intentionally not rewritten to fabricate a
     * garbage target. Test the production range guard independently with the
     * exact same macro and explicit-stack reference.
     */
    seed_guest_state(caseIndex, PHASE3H_RANGE_REJECT);
    s_resolvedGuestVa = 0u;
    savedEsp = g_esp;
    phase3h_reference_icall(RANGE_REJECT_VA, savedEsp);
    capture_result(&reference);

    seed_guest_state(caseIndex, PHASE3H_RANGE_REJECT);
    s_resolvedGuestVa = 0u;
    savedEsp = g_esp;
    PUSH32(g_esp, 0u);
    RECOMP_ICALL_SAFE(RANGE_REJECT_VA, savedEsp);
    capture_result(&real);

    ok &= check(
        reference.accessFault == 0 && real.accessFault == 0,
        "PASS: direct range-guard reference and real macro complete without faults",
        "FAIL: direct range-guard path triggered guest-memory fault");

    ok &= check(
        reference.icallTarget == RANGE_REJECT_VA &&
        real.icallTarget == RANGE_REJECT_VA &&
        reference.icallTraceIdx == 1u &&
        real.icallTraceIdx == 1u,
        "PASS: range guard records exactly the rejected guest VA",
        "FAIL: range-guard ICALL trace is unexpected");

    ok &= check(
        real.manualLookups == 0u &&
        real.generatedLookups == 0u &&
        real.kernelLookups == 0u,
        "PASS: middle-range garbage VA is rejected before any lookup",
        "FAIL: range-rejected VA unexpectedly entered lookup chain");

    ok &= check(
        reference.icallPostEsp == savedEsp &&
        real.icallPostEsp == savedEsp &&
        reference.icallPostEax == 0u &&
        real.icallPostEax == 0u &&
        reference.esp == savedEsp &&
        real.esp == savedEsp,
        "PASS: range reject restores saved ESP and forces EAX=0 immediately",
        "FAIL: range-reject safe-failure state is incorrect");

    ok &= check(
        reference.targetProbeCount == 0u &&
        real.targetProbeCount == 0u,
        "PASS: range-rejected VA never enters translated target",
        "FAIL: range-rejected VA unexpectedly entered translated target");

    ok &= check(
        architectural_results_match(&reference, &real),
        "PASS: real range guard matches independent explicit-stack reference",
        "FAIL: real range guard differs from independent reference");

    if (reference.memoryHash == real.memoryHash)
        trace("PASS: range-guard full 64 MiB guest-RAM hashes match");
    else
    {
        trace("FAIL: range-guard full 64 MiB guest-RAM hashes differ");
        ok = 0;
    }

    return ok;
}

static int run_fixture(void)
{
    int ok = 1;
    DWORD caseIndex;
    DWORD pointerSlot = 0u;

    for (caseIndex = 0u; caseIndex < 3u; ++caseIndex)
    {
        if (!discover_case_pointer_slot(caseIndex, &pointerSlot))
        {
            ok = 0;
            continue;
        }

        ok &= run_one_case(
            caseIndex, PHASE3H_RESOLVED, pointerSlot, DISPATCH_TARGET_VA);
        ok &= run_one_case(
            caseIndex, PHASE3H_UNRESOLVED, pointerSlot, DISPATCH_TARGET_VA);
        ok &= run_range_guard_case(caseIndex);
    }

    return ok;
}

VOID __cdecl main()
{
    int result = 0;
    DWORD started;
    DWORD nextHeartbeat = 1000u;

    s_logFile = CreateFileA(
        "game:\\merc360-phase3h-icall.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 3H TRANSLATED INDIRECT-CALL DISPATCH START");
    trace("BUILD TAG: P3H-ICALL-20261018-B");
    trace("Caller VA: __PHASE3H_CALLER_VA_TEXT__");
    trace("Dispatch target VA: __PHASE3H_TARGET_VA_TEXT__");
    trace("Modes: discover real guest pointer slot / seed 0x0004CFF0 / resolved / unresolved + direct range guard");

    g_ram = (BYTE*)malloc(RAM_SIZE);

    if (!g_ram)
    {
        trace("FATAL: could not allocate 64 MiB guest RAM");
        goto wait_for_exit;
    }

    result = run_fixture();

    if (result)
        trace("PHASE 3H TRANSLATED INDIRECT-CALL RESULT: PASS");
    else
        trace("PHASE 3H TRANSLATED INDIRECT-CALL RESULT: FAIL");

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

    trace("PHASE 3H TRANSLATED INDIRECT-CALL DISPATCH END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

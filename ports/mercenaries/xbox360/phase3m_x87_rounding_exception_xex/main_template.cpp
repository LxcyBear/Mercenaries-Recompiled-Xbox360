/*
 * Mercenaries Xbox 360 - Phase 3M wider control/flags + mixed FP cluster.
 *
 * The root and all members are selected automatically from the supported
 * retail call graph. No member VA is hand-picked in this source.
 *
 * Phase 3M-A requires a bounded dependency-closed cluster that composes real
 * conditional/flag control flow with supported x87 or XMM/SSE architectural
 * state. Backward guest loops and dynamic ICALL/ITAIL remain outside this
 * first mixed-state gate.
 */

#include <xtl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

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

#define ROOT_VA            __P3M_ROOT_VA__
#define CLUSTER_MEMBERS    __P3M_MEMBER_COUNT__
#define CLUSTER_DEPTH      __P3M_DEPTH__

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
#define PROFILE_COUNT      16u
#define EXEC_BUDGET        4096u

static DWORD s_execBudget = 0u;
static int s_budgetExceeded = 0;
static DWORD s_backedgeCount = 0u;
static DWORD s_lastBackedgeFrom = 0u;
static DWORD s_lastBackedgeTo = 0u;
static DWORD s_x87RoundCount = 0u;
static DWORD s_x87InvalidCount = 0u;

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
double g_fp_stack[8] = { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 };
uint32_t g_fp_top = 0u;
uint16_t g_x87_control_word = 0x037Fu;
uint16_t g_x87_status_word = 0u;

float g_xmm0[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
float g_xmm1[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
float g_xmm2[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
float g_xmm3[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
float g_xmm4[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
float g_xmm5[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
float g_xmm6[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
float g_xmm7[4] = { 0.0f, 0.0f, 0.0f, 0.0f };

volatile uint32_t g_recomp_14fa2b_entry = 0u;

#define eax g_eax
#define ecx g_ecx
#define edx g_edx
#define esp g_esp
#define ebx g_ebx
#define esi g_esi
#define edi g_edi

#define xmm0 g_xmm0[0]
#define xmm1 g_xmm1[0]
#define xmm2 g_xmm2[0]
#define xmm3 g_xmm3[0]
#define xmm4 g_xmm4[0]
#define xmm5 g_xmm5[0]
#define xmm6 g_xmm6[0]
#define xmm7 g_xmm7[0]
#define xmm0v g_xmm0
#define xmm1v g_xmm1
#define xmm2v g_xmm2
#define xmm3v g_xmm3
#define xmm4v g_xmm4
#define xmm5v g_xmm5
#define xmm6v g_xmm6
#define xmm7v g_xmm7

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

static int recomp_isnan(double value)
{
    uint64_t bits;
    uint64_t exponent;
    uint64_t mantissa;

    memcpy(&bits, &value, sizeof(bits));
    exponent = (bits >> 52) & 0x7FFui64;
    mantissa = bits & 0x000FFFFFFFFFFFFFui64;
    return exponent == 0x7FFui64 && mantissa != 0ui64;
}

#ifdef isnan
#undef isnan
#endif
#define isnan(v) recomp_isnan((double)(v))

static int recomp_isfinite(double value)
{
    uint64_t bits;
    memcpy(&bits, &value, sizeof(bits));
    return ((bits >> 52) & 0x7FFui64) != 0x7FFui64;
}

static double phase3m_trunc(double value)
{
    if (!recomp_isfinite(value))
        return value;
    return value < 0.0 ? ceil(value) : floor(value);
}

static double phase3m_nearest_even(double value)
{
    double lower;
    double fraction;
    int64_t lowerInt;

    if (!recomp_isfinite(value))
        return value;

    lower = floor(value);
    fraction = value - lower;

    if (fraction < 0.5)
        return lower;
    if (fraction > 0.5)
        return lower + 1.0;

    /* Exact .5 ties are below 2^53, so this parity cast is safe. */
    lowerInt = (int64_t)lower;
    return (lowerInt & 1i64) == 0i64 ? lower : lower + 1.0;
}

static double x87_round_integral(double value)
{
    double rounded;
    ++s_x87RoundCount;

    switch ((g_x87_control_word >> 10) & 3u)
    {
    case 1u:
        rounded = floor(value);
        break;
    case 2u:
        rounded = ceil(value);
        break;
    case 3u:
        rounded = phase3m_trunc(value);
        break;
    default:
        rounded = phase3m_nearest_even(value);
        break;
    }

    if (recomp_isfinite(value) && rounded != value)
        g_x87_status_word |= 0x0020u; /* PE */

    return rounded;
}

static int16_t X87_FIST16(double value)
{
    double rounded = x87_round_integral(value);
    if (!recomp_isfinite(rounded) ||
        rounded < -32768.0 || rounded >= 32768.0)
    {
        g_x87_status_word |= 0x0001u; /* IE */
        ++s_x87InvalidCount;
        return (int16_t)0x8000u;
    }
    return (int16_t)rounded;
}

static int32_t X87_FIST32(double value)
{
    double rounded = x87_round_integral(value);
    if (!recomp_isfinite(rounded) ||
        rounded < -2147483648.0 || rounded >= 2147483648.0)
    {
        g_x87_status_word |= 0x0001u; /* IE */
        ++s_x87InvalidCount;
        return (int32_t)0x80000000u;
    }
    return (int32_t)rounded;
}

static int64_t X87_FIST64(double value)
{
    double rounded = x87_round_integral(value);
    if (!recomp_isfinite(rounded) ||
        rounded < -9223372036854775808.0 ||
        rounded >= 9223372036854775808.0)
    {
        g_x87_status_word |= 0x0001u; /* IE */
        ++s_x87InvalidCount;
        return (int64_t)0x8000000000000000ui64;
    }
    return (int64_t)rounded;
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
    /*__P3M_MEMBER_VAS__*/
};

static void trace_func(DWORD va)
{
    if (s_traceCount < TRACE_CAPACITY)
        s_trace[s_traceCount] = va;
    ++s_traceCount;
}

#define RECOMP_TRACE_FUNC(va) do { trace_func((DWORD)(va)); } while (0)

#define RECOMP_TRACE_BACKEDGE(fromVa, toVa) do { \
    ++s_backedgeCount; \
    s_lastBackedgeFrom = (DWORD)(fromVa); \
    s_lastBackedgeTo = (DWORD)(toVa); \
} while (0)

#define RECOMP_BUDGET_TICK(va) do { \
    (void)(va); \
    ++s_execBudget; \
    if (s_execBudget > EXEC_BUDGET) { \
        s_budgetExceeded = 1; \
        return; \
    } \
} while (0)

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P3M] ");
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

#define GUEST_READF32(addr) recomp_guest_readf32((uint32_t)(addr))
#define GUEST_READF64(addr) recomp_guest_readf64((uint32_t)(addr))
#define GUEST_WRITEF32(addr, value) recomp_guest_writef32((uint32_t)(addr), (float)(value))
#define GUEST_WRITEF64(addr, value) recomp_guest_writef64((uint32_t)(addr), (double)(value))

static void recomp_guest_read128(uint32_t address, uint32_t words[4])
{
    BYTE* p = guest_ptr((DWORD)address, 16u);
    DWORD i;

    if (!p)
    {
        s_accessFault = 1;
        words[0] = words[1] = words[2] = words[3] = 0u;
        return;
    }

    for (i = 0u; i < 4u; ++i)
    {
        const BYTE* q = p + i * 4u;
        words[i] = ((uint32_t)q[0]) |
                   ((uint32_t)q[1] << 8) |
                   ((uint32_t)q[2] << 16) |
                   ((uint32_t)q[3] << 24);
    }
}

static void recomp_guest_write128(
    uint32_t address,
    const uint32_t words[4])
{
    BYTE* p = guest_ptr((DWORD)address, 16u);
    DWORD i;

    if (!p)
    {
        s_accessFault = 1;
        return;
    }

    for (i = 0u; i < 4u; ++i)
    {
        uint32_t value = words[i];
        BYTE* q = p + i * 4u;
        q[0] = (BYTE)value;
        q[1] = (BYTE)(value >> 8);
        q[2] = (BYTE)(value >> 16);
        q[3] = (BYTE)(value >> 24);
    }
}

static uint32_t recomp_xmm_lane_bits(
    const float src[4],
    unsigned lane)
{
    uint32_t value;
    memcpy(&value, &src[lane], 4);
    return value;
}

static void recomp_xmm_set_lane_bits(
    float dst[4],
    unsigned lane,
    uint32_t value)
{
    memcpy(&dst[lane], &value, 4);
}

static void recomp_xmm_load(float dst[4], uint32_t addr)
{
    uint32_t words[4];
    unsigned i;

    recomp_guest_read128(addr, words);
    for (i = 0u; i < 4u; ++i)
        recomp_xmm_set_lane_bits(dst, i, words[i]);
}

static void recomp_xmm_store(uint32_t addr, const float src[4])
{
    uint32_t words[4];
    unsigned i;

    for (i = 0u; i < 4u; ++i)
        words[i] = recomp_xmm_lane_bits(src, i);
    recomp_guest_write128(addr, words);
}

static void recomp_xmm_copy(float dst[4], const float src[4])
{
    memcpy(dst, src, 16);
}

static void recomp_xmm_zero(float dst[4])
{
    memset(dst, 0, 16);
}

static void recomp_xmm_loadss(float dst[4], uint32_t addr)
{
    recomp_xmm_set_lane_bits(dst, 0u, GUEST_READ32(addr));
    dst[1] = dst[2] = dst[3] = 0.0f;
}

static void recomp_xmm_loadsd(float dst[4], uint32_t addr)
{
    uint64_t bits = GUEST_READ64(addr);

    recomp_xmm_set_lane_bits(dst, 0u, (uint32_t)bits);
    recomp_xmm_set_lane_bits(dst, 1u, (uint32_t)(bits >> 32));
    dst[2] = dst[3] = 0.0f;
}

static void recomp_xmm_copysd(float dst[4], const float src[4])
{
    memcpy(&dst[0], &src[0], 8);
}

static void recomp_xmm_storesd(uint32_t addr, const float src[4])
{
    uint64_t bits =
        (uint64_t)recomp_xmm_lane_bits(src, 0u) |
        ((uint64_t)recomp_xmm_lane_bits(src, 1u) << 32);

    GUEST_WRITE64(addr, bits);
}

static void recomp_xmm_movlps_load(float dst[4], uint32_t addr)
{
    uint64_t bits = GUEST_READ64(addr);
    recomp_xmm_set_lane_bits(dst, 0u, (uint32_t)bits);
    recomp_xmm_set_lane_bits(dst, 1u, (uint32_t)(bits >> 32));
}

static void recomp_xmm_movlps_store(uint32_t addr, const float src[4])
{
    uint64_t bits =
        (uint64_t)recomp_xmm_lane_bits(src, 0u) |
        ((uint64_t)recomp_xmm_lane_bits(src, 1u) << 32);
    GUEST_WRITE64(addr, bits);
}

static void recomp_xmm_movhps_load(float dst[4], uint32_t addr)
{
    uint64_t bits = GUEST_READ64(addr);
    recomp_xmm_set_lane_bits(dst, 2u, (uint32_t)bits);
    recomp_xmm_set_lane_bits(dst, 3u, (uint32_t)(bits >> 32));
}

static void recomp_xmm_movhps_store(uint32_t addr, const float src[4])
{
    uint64_t bits =
        (uint64_t)recomp_xmm_lane_bits(src, 2u) |
        ((uint64_t)recomp_xmm_lane_bits(src, 3u) << 32);
    GUEST_WRITE64(addr, bits);
}

static void recomp_xmm_movlhps(float dst[4], const float src[4])
{
    float s0 = src[0];
    float s1 = src[1];
    dst[2] = s0;
    dst[3] = s1;
}

static void recomp_xmm_movhlps(float dst[4], const float src[4])
{
    float s2 = src[2];
    float s3 = src[3];
    dst[0] = s2;
    dst[1] = s3;
}

static void recomp_xmm_set_u32(float dst[4], uint32_t value)
{
    memcpy(&dst[0], &value, 4);
    dst[1] = dst[2] = dst[3] = 0.0f;
}

static uint32_t recomp_xmm_get_u32(const float src[4])
{
    uint32_t value;
    memcpy(&value, &src[0], 4);
    return value;
}

static void recomp_xmm_movq_copy(float dst[4], const float src[4])
{
    memcpy(&dst[0], &src[0], 8);
    dst[2] = dst[3] = 0.0f;
}

static void recomp_xmm_movq_load(float dst[4], uint32_t addr)
{
    recomp_xmm_loadsd(dst, addr);
}

static float recomp_xmm_min_sse(float a, float b)
{
    return (isnan(a) || isnan(b) || a == b) ? b : (a < b ? a : b);
}

static float recomp_xmm_max_sse(float a, float b)
{
    return (isnan(a) || isnan(b) || a == b) ? b : (a > b ? a : b);
}

#define RECOMP_XMM_BINARY_RR(dst, src, op) do { \
    unsigned _xmm_i; \
    for (_xmm_i = 0u; _xmm_i < 4u; ++_xmm_i) \
        (dst)[_xmm_i] = (dst)[_xmm_i] op (src)[_xmm_i]; \
} while (0)

#define RECOMP_XMM_BINARY_RM(dst, addr, op) do { \
    float _xmm_src[4]; \
    recomp_xmm_load(_xmm_src, (uint32_t)(addr)); \
    RECOMP_XMM_BINARY_RR((dst), _xmm_src, op); \
} while (0)

static void recomp_xmm_minps(float dst[4], const float src[4])
{
    unsigned i;
    for (i = 0u; i < 4u; ++i)
        dst[i] = recomp_xmm_min_sse(dst[i], src[i]);
}

static void recomp_xmm_maxps(float dst[4], const float src[4])
{
    unsigned i;
    for (i = 0u; i < 4u; ++i)
        dst[i] = recomp_xmm_max_sse(dst[i], src[i]);
}

static void recomp_xmm_minps_mem(float dst[4], uint32_t addr)
{
    float src[4];
    recomp_xmm_load(src, addr);
    recomp_xmm_minps(dst, src);
}

static void recomp_xmm_maxps_mem(float dst[4], uint32_t addr)
{
    float src[4];
    recomp_xmm_load(src, addr);
    recomp_xmm_maxps(dst, src);
}

static void recomp_xmm_bitwise(
    float dst[4],
    const float src[4],
    unsigned operation)
{
    unsigned i;

    for (i = 0u; i < 4u; ++i)
    {
        uint32_t a = recomp_xmm_lane_bits(dst, i);
        uint32_t b = recomp_xmm_lane_bits(src, i);
        uint32_t value =
            operation == 0u ? (a ^ b) :
            operation == 1u ? (a & b) :
            operation == 2u ? (a | b) : ((~a) & b);

        recomp_xmm_set_lane_bits(dst, i, value);
    }
}

static void recomp_xmm_bitwise_mem(
    float dst[4],
    uint32_t addr,
    unsigned operation)
{
    float src[4];
    recomp_xmm_load(src, addr);
    recomp_xmm_bitwise(dst, src, operation);
}

static void recomp_xmm_shufps(
    float dst[4],
    const float src[4],
    uint8_t control)
{
    float a[4];
    float b[4];
    float out[4];

    recomp_xmm_copy(a, dst);
    recomp_xmm_copy(b, src);

    out[0] = a[(control >> 0) & 3u];
    out[1] = a[(control >> 2) & 3u];
    out[2] = b[(control >> 4) & 3u];
    out[3] = b[(control >> 6) & 3u];

    recomp_xmm_copy(dst, out);
}

static void recomp_xmm_shufps_mem(
    float dst[4],
    uint32_t addr,
    uint8_t control)
{
    float src[4];
    recomp_xmm_load(src, addr);
    recomp_xmm_shufps(dst, src, control);
}

static void recomp_xmm_unpcklps(float dst[4], const float src[4])
{
    float a0 = dst[0];
    float a1 = dst[1];
    float b0 = src[0];
    float b1 = src[1];

    dst[0] = a0;
    dst[1] = b0;
    dst[2] = a1;
    dst[3] = b1;
}

static void recomp_xmm_unpckhps(float dst[4], const float src[4])
{
    float a2 = dst[2];
    float a3 = dst[3];
    float b2 = src[2];
    float b3 = src[3];

    dst[0] = a2;
    dst[1] = b2;
    dst[2] = a3;
    dst[3] = b3;
}

static void recomp_xmm_unpcklps_mem(float dst[4], uint32_t addr)
{
    float src[4];
    recomp_xmm_load(src, addr);
    recomp_xmm_unpcklps(dst, src);
}

static void recomp_xmm_unpckhps_mem(float dst[4], uint32_t addr)
{
    float src[4];
    recomp_xmm_load(src, addr);
    recomp_xmm_unpckhps(dst, src);
}

static void recomp_xmm_unary_ps(
    float dst[4],
    const float src[4],
    unsigned operation)
{
    float input[4];
    unsigned i;

    recomp_xmm_copy(input, src);

    for (i = 0u; i < 4u; ++i)
    {
        dst[i] =
            operation == 0u ? sqrtf(input[i]) :
            operation == 1u ? 1.0f / sqrtf(input[i]) :
                              1.0f / input[i];
    }
}

static void recomp_xmm_unary_ps_mem(
    float dst[4],
    uint32_t addr,
    unsigned operation)
{
    float src[4];
    recomp_xmm_load(src, addr);
    recomp_xmm_unary_ps(dst, src, operation);
}

static void recomp_xmm_cmp_ps(
    float dst[4],
    const float src[4],
    unsigned predicate)
{
    float a[4];
    float b[4];
    unsigned i;

    recomp_xmm_copy(a, dst);
    recomp_xmm_copy(b, src);

    for (i = 0u; i < 4u; ++i)
    {
        int unordered = isnan(a[i]) || isnan(b[i]);
        int result =
            predicate == 0u ? (unordered || a[i] != b[i]) :
            predicate == 1u ? (!unordered && a[i] == b[i]) :
            predicate == 2u ? (!unordered && a[i] < b[i]) :
                              (!unordered && a[i] <= b[i]);

        recomp_xmm_set_lane_bits(
            dst, i, result ? 0xFFFFFFFFu : 0u);
    }
}

static void recomp_xmm_cmp_ps_mem(
    float dst[4],
    uint32_t addr,
    unsigned predicate)
{
    float src[4];
    recomp_xmm_load(src, addr);
    recomp_xmm_cmp_ps(dst, src, predicate);
}

static uint32_t recomp_xmm_movmskps(const float src[4])
{
    uint32_t mask = 0u;
    unsigned i;

    for (i = 0u; i < 4u; ++i)
        mask |=
            ((recomp_xmm_lane_bits(src, i) >> 31) & 1u) << i;

    return mask;
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
    uint32_t _phase3m_push_value = (uint32_t)(val); \
    (sp) -= 4u; \
    GUEST_WRITE32((sp), _phase3m_push_value); \
} while (0)

#define POP32(sp, dst) do { \
    (dst) = GUEST_READ32(sp); \
    (sp) += 4u; \
} while (0)

/* All selected translated symbols are declared before any body so arbitrary
 * dependency order does not become a native C compiler constraint. */
/*__P3M_FORWARD_DECLS__*/

/*
 * Dependency-first, mechanically translated retail bodies with Phase 3M budget/x87 proof instrumentation.
 *
 * The Xbox 360 XDK compiler can ICE in its optimizer on wider generated
 * mixed-control/SSE functions. Keep optimization disabled only for the
 * mechanically translated cluster; the surrounding harness remains under
 * the project defaults. This does not alter guest-visible translated logic.
 */
#pragma optimize("", off)
/*__P3M_CLUSTER_BODIES__*/
#pragma optimize("", on)

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

static DWORD canary_value(DWORD profileIndex, DWORD index)
{
    return 0x3A4A0000u ^ (profileIndex << 12) ^ (index * 0x01010101u);
}

static void reset_trace(void)
{
    s_traceCount = 0u;
    memset(s_trace, 0, sizeof(s_trace));
}

static DWORD profile_value(
    DWORD profileIndex,
    DWORD base,
    DWORD slot)
{
    DWORD offset = ((slot * 0x20u) & 0x3E0u);

    switch (profileIndex % PROFILE_COUNT)
    {
    case 0u:
        return 0u;
    case 1u:
        return (slot & 1u) ? 1u : 0u;
    case 2u:
        return (slot & 1u) ? 0u : 1u;
    case 3u:
        return base + offset;
    case 4u:
        return (slot % 3u) ? (base + offset) : 0u;
    case 5u:
        return (slot & 3u) + 1u;
    case 6u:
        return (slot & 1u)
            ? (0x84010000u + offset)
            : 0u;
    case 7u:
        return (slot & 1u)
            ? 0u
            : (0x84010000u + offset);
    case 8u:
        return 0x00010000u + offset;
    case 9u:
        return 0x03F00000u + offset;
    case 10u:
        return (slot & 1u) ? 2u : 3u;
    case 11u:
        return (slot & 3u) == 0u
            ? base
            : ((slot & 3u) == 1u
                ? 1u
                : ((slot & 3u) == 2u
                    ? 0x84010000u + offset
                    : 0u));
    case 12u:
        return (slot & 1u) ? 0x3F800000u : 0u; /* +1.0f */
    case 13u:
        return (slot & 1u) ? 0xBF800000u : 0u; /* -1.0f, safe KSEG */
    case 14u:
        return (slot & 1u) ? 0x40000000u : 0x3F000000u; /* 2.0f / 0.5f */
    default:
        return (slot & 3u) == 0u
            ? 0x3F800000u
            : ((slot & 3u) == 1u
                ? 0xBF800000u
                : ((slot & 3u) == 2u
                    ? 0x40000000u
                    : 0x3F000000u));
    }
}

static void seed_pointer_region(
    DWORD base,
    DWORD profileIndex)
{
    DWORD i;

    /*
     * Every profile uses values that are also valid guest addresses when a
     * field is unexpectedly consumed as a pointer. This lets the suite drive
     * zero/nonzero/equality/signed branch conditions without introducing
     * random host-invalid addresses.
     */
    for (i = 0u; i < 0x400u; ++i)
        GUEST_WRITE8(base + i, 0u);

    for (i = 0u; i < 0x100u / 4u; ++i)
        GUEST_WRITE32(
            base + i * 4u,
            profile_value(profileIndex, base, i));

    /* Profile 0 preserves the original conservative seed exactly. */
    if ((profileIndex % PROFILE_COUNT) == 0u)
    {
        GUEST_WRITE32(base + 0x00u, base);
        GUEST_WRITE32(base + 0x04u, base + 0x80u);
        GUEST_WRITE32(base + 0x08u, 0u);
        GUEST_WRITE32(base + 0x0Cu, profileIndex);
        GUEST_WRITE32(base + 0x10u, base + 0x100u);
        GUEST_WRITE32(base + 0x14u, 0u);
        GUEST_WRITE32(base + 0x18u, base + 0x180u);
        GUEST_WRITE32(base + 0x1Cu, 0u);
    }
}

static void seed_case(DWORD profileIndex)
{
    DWORD i;
    DWORD safeArgs[6];

    memset(g_ram, 0, RAM_SIZE);

    seed_pointer_region(
        SAFE_EAX_BASE + profileIndex * 0x1000u, profileIndex);
    seed_pointer_region(
        SAFE_ECX_BASE + profileIndex * 0x1000u, profileIndex);
    seed_pointer_region(
        SAFE_EDX_BASE + profileIndex * 0x1000u, profileIndex);
    seed_pointer_region(
        SAFE_EBX_BASE + profileIndex * 0x1000u, profileIndex);
    seed_pointer_region(
        SAFE_ESI_BASE + profileIndex * 0x1000u, profileIndex);
    seed_pointer_region(
        SAFE_EDI_BASE + profileIndex * 0x1000u, profileIndex);

    safeArgs[0] = SAFE_EAX_BASE + profileIndex * 0x1000u;
    safeArgs[1] = SAFE_ECX_BASE + profileIndex * 0x1000u;
    safeArgs[2] = SAFE_EDX_BASE + profileIndex * 0x1000u;
    safeArgs[3] = SAFE_EBX_BASE + profileIndex * 0x1000u;
    safeArgs[4] = SAFE_ESI_BASE + profileIndex * 0x1000u;
    safeArgs[5] = SAFE_EDI_BASE + profileIndex * 0x1000u;

    g_eax = safeArgs[0];
    g_ecx = safeArgs[1];
    g_edx = safeArgs[2];
    g_ebx = safeArgs[3];
    g_esi = safeArgs[4];
    g_edi = safeArgs[5];
    g_seh_ebp = 0x00160000u + profileIndex * 0x1000u;
    g_eflags = 0u;

    g_fp_top = 0u;
    g_x87_control_word =
        (uint16_t)((0x037Fu & ~0x0C00u) |
        ((profileIndex & 3u) << 10));
    g_x87_status_word = 0u;
    for (i = 0u; i < 8u; ++i)
    {
        g_fp_stack[i] =
            ((double)((int)(profileIndex % PROFILE_COUNT) - 8) * 0.5) +
            ((double)i * 0.25);
    }

    /* Exceptional architectural seeds stay out of generic pointer memory. */
    if ((profileIndex % PROFILE_COUNT) == 12u)
    {
        uint64_t bits = 0x7FF8000000000000ui64; /* quiet NaN */
        memcpy(&g_fp_stack[0], &bits, sizeof(bits));
    }
    else if ((profileIndex % PROFILE_COUNT) == 13u)
    {
        uint64_t bits = 0x7FF0000000000000ui64; /* +infinity */
        memcpy(&g_fp_stack[0], &bits, sizeof(bits));
    }
    else if ((profileIndex % PROFILE_COUNT) == 14u)
    {
        uint64_t bits = 0xFFF0000000000000ui64; /* -infinity */
        memcpy(&g_fp_stack[0], &bits, sizeof(bits));
    }
    else if ((profileIndex % PROFILE_COUNT) == 15u)
    {
        g_fp_stack[0] = 2147483648.5; /* FIST32 overflow boundary */
    }

    {
        float* xmmRegs[8] = {
            g_xmm0, g_xmm1, g_xmm2, g_xmm3,
            g_xmm4, g_xmm5, g_xmm6, g_xmm7
        };
        DWORD xr;
        DWORD lane;

        for (xr = 0u; xr < 8u; ++xr)
        {
            for (lane = 0u; lane < 4u; ++lane)
            {
                int signedSeed =
                    (int)(profileIndex % PROFILE_COUNT) - 8 +
                    (int)xr - (int)lane;
                xmmRegs[xr][lane] =
                    (float)signedSeed * 0.25f;
            }
        }
    }

    g_esp = ROOT_STACK;
    GUEST_WRITE32(g_esp, 0x3A4A0000u ^ profileIndex);

    for (i = 1u; i <= ARG_COUNT; ++i)
    {
        DWORD value;

        if ((profileIndex % PROFILE_COUNT) == 0u)
        {
            value = safeArgs[(i - 1u) % 6u];

            if ((i & 7u) == 0u)
                value = profileIndex;
            else if ((i & 7u) == 4u)
                value = 0u;
        }
        else
        {
            value = profile_value(
                profileIndex,
                safeArgs[(i - 1u) % 6u],
                i);

            /*
             * Keep a regular stream of unquestionably mapped nonzero pointers
             * in the argument area in case a branch-selected path dereferences
             * an argument rather than treating it as a scalar.
             */
            if ((i % 6u) == 0u)
                value = safeArgs[(i - 1u) % 6u];
        }

        GUEST_WRITE32(g_esp + i * 4u, value);
    }

    for (i = 0u; i < CANARY_COUNT; ++i)
        GUEST_WRITE32(
            CANARY_BASE + i * 4u,
            canary_value(profileIndex, i));

    s_accessFault = 0;
    s_execBudget = 0u;
    s_budgetExceeded = 0;
    s_backedgeCount = 0u;
    s_lastBackedgeFrom = 0u;
    s_lastBackedgeTo = 0u;
    s_x87RoundCount = 0u;
    s_x87InvalidCount = 0u;
    reset_trace();
}

static int canaries_ok(DWORD profileIndex)
{
    DWORD i;

    for (i = 0u; i < CANARY_COUNT; ++i)
    {
        if (GUEST_READ32(CANARY_BASE + i * 4u) !=
            canary_value(profileIndex, i))
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

static DWORD coverage_mask(void)
{
    DWORD i;
    DWORD mask = 0u;

    for (i = 0u; i < CLUSTER_MEMBERS; ++i)
    {
        if (trace_occurrences(s_clusterVas[i]) > 0u)
            mask |= (1u << i);
    }

    return mask;
}

static DWORD covered_member_count_from_mask(DWORD mask)
{
    DWORD i;
    DWORD count = 0u;

    for (i = 0u; i < CLUSTER_MEMBERS; ++i)
    {
        if ((mask & (1u << i)) != 0u)
            ++count;
    }

    return count;
}

static void log_member_table(void)
{
    DWORD i;
    char line[160];

    trace("Selected dependency-closed member VAs:");
    for (i = 0u; i < CLUSTER_MEMBERS; ++i)
    {
        sprintf(
            line,
            "  member[%u]=%08X%s",
            (unsigned int)i,
            (unsigned int)s_clusterVas[i],
            s_clusterVas[i] == ROOT_VA ? " ROOT" : "");
        trace(line);
    }
}

static void log_run_trace(
    DWORD profileIndex,
    const char* label,
    const DWORD* values,
    DWORD count)
{
    DWORD i;
    DWORD limit = count < TRACE_CAPACITY ? count : TRACE_CAPACITY;
    char line[192];

    for (i = 0u; i < limit; ++i)
    {
        sprintf(
            line,
            "PROFILE %u %s trace[%u]=%08X",
            (unsigned int)profileIndex,
            label,
            (unsigned int)i,
            (unsigned int)values[i]);
        trace(line);
    }
}

static void log_missing_members(DWORD mask)
{
    DWORD i;
    char line[160];

    for (i = 0u; i < CLUSTER_MEMBERS; ++i)
    {
        if ((mask & (1u << i)) == 0u)
        {
            sprintf(
                line,
                "MISSING member[%u]=%08X",
                (unsigned int)i,
                (unsigned int)s_clusterVas[i]);
            trace(line);
        }
    }
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
    int budgetExceeded;
    DWORD execBudget;
    DWORD backedgeCount;
    DWORD lastBackedgeFrom;
    DWORD lastBackedgeTo;
    DWORD x87RoundCount;
    DWORD x87InvalidCount;

    DWORD traceCount;
    DWORD trace[TRACE_CAPACITY];
    DWORD coverageMask;
    DWORD coveredMembers;

    DWORD fpTop;
    uint16_t x87ControlWord;
    uint16_t x87StatusWord;
    uint64_t fpStackBits[8];
    DWORD xmmBits[8][4];

    unsigned __int64 fpStateHash;
    unsigned __int64 memoryHash;
} RunResult;

static unsigned __int64 hash_fp_state(void)
{
    const unsigned __int64 kOffset = 14695981039346656037ui64;
    const unsigned __int64 kPrime = 1099511628211ui64;
    float* xmmRegs[8] = {
        g_xmm0, g_xmm1, g_xmm2, g_xmm3,
        g_xmm4, g_xmm5, g_xmm6, g_xmm7
    };
    unsigned __int64 hash = kOffset;
    DWORD i;
    DWORD lane;

    hash ^= (unsigned __int64)g_fp_top;
    hash *= kPrime;
    hash ^= (unsigned __int64)g_x87_control_word;
    hash *= kPrime;
    hash ^= (unsigned __int64)g_x87_status_word;
    hash *= kPrime;

    for (i = 0u; i < 8u; ++i)
    {
        uint64_t bits;
        memcpy(&bits, &g_fp_stack[i], sizeof(bits));
        hash ^= bits;
        hash *= kPrime;
    }

    for (i = 0u; i < 8u; ++i)
    {
        for (lane = 0u; lane < 4u; ++lane)
        {
            uint32_t bits;
            memcpy(&bits, &xmmRegs[i][lane], sizeof(bits));
            hash ^= (unsigned __int64)bits;
            hash *= kPrime;
        }
    }

    return hash;
}

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
    result->budgetExceeded = s_budgetExceeded;
    result->execBudget = s_execBudget;
    result->backedgeCount = s_backedgeCount;
    result->lastBackedgeFrom = s_lastBackedgeFrom;
    result->lastBackedgeTo = s_lastBackedgeTo;
    result->x87RoundCount = s_x87RoundCount;
    result->x87InvalidCount = s_x87InvalidCount;

    result->fpTop = g_fp_top;
    result->x87ControlWord = g_x87_control_word;
    result->x87StatusWord = g_x87_status_word;
    for (i = 0u; i < 8u; ++i)
        memcpy(
            &result->fpStackBits[i],
            &g_fp_stack[i],
            sizeof(result->fpStackBits[i]));

    {
        float* xmmRegs[8] = {
            g_xmm0, g_xmm1, g_xmm2, g_xmm3,
            g_xmm4, g_xmm5, g_xmm6, g_xmm7
        };
        DWORD xr;
        DWORD lane;

        for (xr = 0u; xr < 8u; ++xr)
        {
            for (lane = 0u; lane < 4u; ++lane)
            {
                memcpy(
                    &result->xmmBits[xr][lane],
                    &xmmRegs[xr][lane],
                    sizeof(result->xmmBits[xr][lane]));
            }
        }
    }

    result->fpStateHash = hash_fp_state();

    result->traceCount = s_traceCount;
    result->coverageMask = coverage_mask();
    result->coveredMembers =
        covered_member_count_from_mask(result->coverageMask);

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
        a->budgetExceeded == b->budgetExceeded &&
        a->execBudget == b->execBudget &&
        a->backedgeCount == b->backedgeCount &&
        a->lastBackedgeFrom == b->lastBackedgeFrom &&
        a->lastBackedgeTo == b->lastBackedgeTo &&
        a->x87RoundCount == b->x87RoundCount &&
        a->x87InvalidCount == b->x87InvalidCount &&
        a->coverageMask == b->coverageMask &&
        a->coveredMembers == b->coveredMembers &&
        a->fpTop == b->fpTop &&
        a->x87ControlWord == b->x87ControlWord &&
        a->x87StatusWord == b->x87StatusWord &&
        memcmp(a->fpStackBits, b->fpStackBits, sizeof(a->fpStackBits)) == 0 &&
        memcmp(a->xmmBits, b->xmmBits, sizeof(a->xmmBits)) == 0 &&
        a->fpStateHash == b->fpStateHash &&
        a->memoryHash == b->memoryHash;
}

static int run_once(DWORD caseIndex, RunResult* result)
{
    seed_case(caseIndex);
    __P3M_ROOT_NAME__();
    capture_result(caseIndex, result);
    return 1;
}

static int run_case(
    DWORD profileIndex,
    DWORD* suiteCoverage,
    DWORD* suiteBackedges,
    DWORD* suiteRounding)
{
    RunResult a;
    RunResult b;
    char line[384];
    int ok = 1;

    run_once(profileIndex, &a);
    run_once(profileIndex, &b);

    sprintf(
        line,
        "PROFILE %u A eax=%08X ecx=%08X esp=%08X trace=%u coverage=%u/%u mask=%08X backedges=%u budget=%u/%u x87round=%u invalid=%u fp=%08X%08X ram=%08X%08X",
        (unsigned int)profileIndex,
        (unsigned int)a.eax,
        (unsigned int)a.ecx,
        (unsigned int)a.esp,
        (unsigned int)a.traceCount,
        (unsigned int)a.coveredMembers,
        (unsigned int)CLUSTER_MEMBERS,
        (unsigned int)a.coverageMask,
        (unsigned int)a.backedgeCount,
        (unsigned int)a.execBudget,
        (unsigned int)EXEC_BUDGET,
        (unsigned int)a.x87RoundCount,
        (unsigned int)a.x87InvalidCount,
        (unsigned int)(a.fpStateHash >> 32),
        (unsigned int)a.fpStateHash,
        (unsigned int)(a.memoryHash >> 32),
        (unsigned int)a.memoryHash);
    trace(line);

    sprintf(
        line,
        "PROFILE %u B eax=%08X ecx=%08X esp=%08X trace=%u coverage=%u/%u mask=%08X backedges=%u budget=%u/%u fp=%08X%08X ram=%08X%08X",
        (unsigned int)profileIndex,
        (unsigned int)b.eax,
        (unsigned int)b.ecx,
        (unsigned int)b.esp,
        (unsigned int)b.traceCount,
        (unsigned int)b.coveredMembers,
        (unsigned int)CLUSTER_MEMBERS,
        (unsigned int)b.coverageMask,
        (unsigned int)b.backedgeCount,
        (unsigned int)b.execBudget,
        (unsigned int)EXEC_BUDGET,
        (unsigned int)b.x87RoundCount,
        (unsigned int)b.x87InvalidCount,
        (unsigned int)(b.fpStateHash >> 32),
        (unsigned int)b.fpStateHash,
        (unsigned int)(b.memoryHash >> 32),
        (unsigned int)b.memoryHash);
    trace(line);

    log_run_trace(profileIndex, "A", a.trace, a.traceCount);

    ok &= check(
        a.accessFault == 0 && b.accessFault == 0,
        "PASS: both profile runs complete without guest-memory faults",
        "FAIL: profile triggered guest-memory fault");

    ok &= check(
        !a.budgetExceeded && !b.budgetExceeded,
        "PASS: both profile runs stay within the translated execution budget",
        "FAIL: translated execution budget exhausted");

    ok &= check(
        a.backedgeCount == b.backedgeCount,
        "PASS: backward-edge execution count is deterministic across A/B",
        "FAIL: backward-edge execution count diverges across A/B");

    ok &= check(
        a.canaryOk && b.canaryOk,
        "PASS: unrelated high-RAM canaries survive both profile runs",
        "FAIL: profile corrupted high-RAM canary");

    ok &= check(
        a.traceCount > 0u &&
        b.traceCount > 0u &&
        a.trace[0] == ROOT_VA &&
        b.trace[0] == ROOT_VA,
        "PASS: translated trace begins at the automatically selected real root",
        "FAIL: cluster trace does not begin at selected root");

    ok &= check(
        a.coverageMask == b.coverageMask,
        "PASS: profile member coverage is deterministic across A/B",
        "FAIL: profile member coverage diverges across A/B");

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
        "PASS: repeated cluster runs match integer/x87/XMM architecture and complete 64 MiB guest RAM",
        "FAIL: repeated cluster integer/FP/full-RAM state diverges");

    if (suiteCoverage)
        *suiteCoverage |= a.coverageMask;
    if (suiteBackedges)
        *suiteBackedges += a.backedgeCount;
    if (suiteRounding)
        *suiteRounding += a.x87RoundCount;

    return ok;
}

static int run_x87_helper_fixture(void)
{
    static const int32_t expectPos[4] = { 2, 1, 2, 1 };
    static const int32_t expectNeg[4] = { -2, -2, -1, -1 };
    DWORD mode;
    int ok = 1;
    char line[192];

    trace("x87 helper preflight: four rounding modes + invalid conversions");

    for (mode = 0u; mode < 4u; ++mode)
    {
        int32_t pos;
        int32_t neg;

        g_x87_control_word =
            (uint16_t)((0x037Fu & ~0x0C00u) | (mode << 10));
        g_x87_status_word = 0u;
        s_x87RoundCount = 0u;
        s_x87InvalidCount = 0u;

        pos = X87_FIST32(1.5);
        neg = X87_FIST32(-1.5);

        sprintf(
            line,
            "x87 RC=%u +1.5=%d -1.5=%d status=%04X",
            (unsigned int)mode,
            (int)pos,
            (int)neg,
            (unsigned int)g_x87_status_word);
        trace(line);

        ok &= check(
            pos == expectPos[mode] &&
            neg == expectNeg[mode] &&
            (g_x87_status_word & 0x0020u) != 0u &&
            (g_x87_status_word & 0x0001u) == 0u,
            "PASS: x87 rounding-control conversion matches expected result",
            "FAIL: x87 rounding-control conversion mismatch");
    }

    {
        uint64_t bits = 0x7FF8000000000000ui64;
        double qnan;
        int32_t value;
        memcpy(&qnan, &bits, sizeof(qnan));
        g_x87_control_word = 0x037Fu;
        g_x87_status_word = 0u;
        s_x87InvalidCount = 0u;
        value = X87_FIST32(qnan);
        ok &= check(
            value == (int32_t)0x80000000u &&
            (g_x87_status_word & 0x0001u) != 0u &&
            (g_x87_status_word & 0x0020u) == 0u &&
            s_x87InvalidCount == 1u,
            "PASS: NaN FIST32 returns integer-indefinite and sets IE without PE",
            "FAIL: NaN FIST32 exceptional state mismatch");
    }

    {
        uint64_t bits = 0x7FF0000000000000ui64;
        double pinf;
        int32_t value;
        memcpy(&pinf, &bits, sizeof(pinf));
        g_x87_status_word = 0u;
        s_x87InvalidCount = 0u;
        value = X87_FIST32(pinf);
        ok &= check(
            value == (int32_t)0x80000000u &&
            (g_x87_status_word & 0x0001u) != 0u &&
            s_x87InvalidCount == 1u,
            "PASS: infinity FIST32 returns integer-indefinite and sets IE",
            "FAIL: infinity FIST32 exceptional state mismatch");
    }

    {
        int32_t value;
        g_x87_status_word = 0u;
        s_x87InvalidCount = 0u;
        value = X87_FIST32(2147483648.0);
        ok &= check(
            value == (int32_t)0x80000000u &&
            (g_x87_status_word & 0x0001u) != 0u &&
            s_x87InvalidCount == 1u,
            "PASS: out-of-range FIST32 returns integer-indefinite and sets IE",
            "FAIL: out-of-range FIST32 exceptional state mismatch");
    }

    return ok;
}

static int run_fixture(void)
{
    DWORD profileIndex;
    DWORD suiteCoverage = 0u;
    DWORD suiteBackedges = 0u;
    DWORD suiteRounding = 0u;
    DWORD covered;
    DWORD fullMask = (1u << CLUSTER_MEMBERS) - 1u;
    char line[256];
    int ok = 1;

    log_member_table();

    for (profileIndex = 0u;
         profileIndex < PROFILE_COUNT;
         ++profileIndex)
    {
        ok &= run_case(
            profileIndex, &suiteCoverage, &suiteBackedges, &suiteRounding);
    }

    covered = covered_member_count_from_mask(suiteCoverage);

    sprintf(
        line,
        "SUITE COVERAGE: %u/%u mask=%08X expected=%08X",
        (unsigned int)covered,
        (unsigned int)CLUSTER_MEMBERS,
        (unsigned int)suiteCoverage,
        (unsigned int)fullMask);
    trace(line);

    if (suiteCoverage != fullMask)
        log_missing_members(suiteCoverage);

    ok &= check(
        suiteCoverage == fullMask,
        "PASS: deterministic profile suite executes every statically closed cluster member",
        "FAIL: deterministic profile suite did not execute every selected cluster member");

    sprintf(
        line,
        "SUITE BACKEDGES (optional): %u",
        (unsigned int)suiteBackedges);
    trace(line);

    sprintf(
        line,
        "SUITE X87 ROUNDING CALLS: %u",
        (unsigned int)suiteRounding);
    trace(line);

    ok &= check(
        suiteRounding > 0u,
        "PASS: deterministic profile suite executes real x87 rounding/conversion",
        "FAIL: selected x87 rounding/conversion surface was never executed");

    return ok;
}

VOID __cdecl main()
{
    int result = 0;
    DWORD started;
    DWORD nextHeartbeat = 1000u;
    char line[256];

    s_logFile = CreateFileA(
        "game:\\merc360-phase3m-x87-rounding.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 3L BOUNDED BACKWARD-CONTROL CLUSTER START");
    trace("BUILD TAG: P3M-X87ROUND-20261019-A");
    trace("Coverage policy: x87 helper reference checks + deterministic retail rounding execution + full mixed-state/RAM equality");

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

    result = run_x87_helper_fixture();
    result &= run_fixture();

    if (result)
        trace("PHASE 3L BOUNDED BACKWARD-CONTROL CLUSTER RESULT: PASS");
    else
        trace("PHASE 3L BOUNDED BACKWARD-CONTROL CLUSTER RESULT: FAIL");

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

    trace("PHASE 3L BOUNDED BACKWARD-CONTROL CLUSTER END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

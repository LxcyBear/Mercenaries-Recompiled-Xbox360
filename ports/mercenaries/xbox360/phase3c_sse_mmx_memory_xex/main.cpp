/*
 * Mercenaries Xbox 360 - Phase 3C SSE/XMM + MMX guest-memory ABI.
 *
 * SELF-CONTAINED XDK TEST. No translated Mercenaries function executes here.
 */

#include <xtl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RAM_SIZE        0x04000000u
#define RAM_MASK        0x03FFFFFFu
#define MIRROR_END      0x74000000u
#define KSEG_BASE       0x80000000u
#define KSEG_END        0xC0000000u
#define FENCE_BASE      0x80000000u
#define FENCE_END       0x80001000u
#define KERNEL_BASE     0x80010000u
#define KERNEL_END      0x80011000u

static BYTE* g_ram = NULL;
static HANDLE s_logFile = INVALID_HANDLE_VALUE;
static int s_fault = 0;

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P3C] ");
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

static DWORD read32(DWORD address)
{
    BYTE* p = guest_ptr(address, 4u);

    if (!p)
    {
        s_fault = 1;
        return 0u;
    }

    return ((DWORD)p[0]) |
           ((DWORD)p[1] << 8) |
           ((DWORD)p[2] << 16) |
           ((DWORD)p[3] << 24);
}

static unsigned __int64 read64(DWORD address)
{
    BYTE* p = guest_ptr(address, 8u);
    unsigned __int64 lo;
    unsigned __int64 hi;

    if (!p)
    {
        s_fault = 1;
        return 0ui64;
    }

    lo = (unsigned __int64)(
        ((DWORD)p[0]) |
        ((DWORD)p[1] << 8) |
        ((DWORD)p[2] << 16) |
        ((DWORD)p[3] << 24));

    hi = (unsigned __int64)(
        ((DWORD)p[4]) |
        ((DWORD)p[5] << 8) |
        ((DWORD)p[6] << 16) |
        ((DWORD)p[7] << 24));

    return lo | (hi << 32);
}

static void write32(DWORD address, DWORD value)
{
    BYTE* p = guest_ptr(address, 4u);

    if (!p)
    {
        s_fault = 1;
        return;
    }

    p[0] = (BYTE)value;
    p[1] = (BYTE)(value >> 8);
    p[2] = (BYTE)(value >> 16);
    p[3] = (BYTE)(value >> 24);
}

static void write64(DWORD address, unsigned __int64 value)
{
    BYTE* p = guest_ptr(address, 8u);

    if (!p)
    {
        s_fault = 1;
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

#define GUEST_READ32(a) read32((DWORD)(a))
#define GUEST_READ64(a) read64((DWORD)(a))
#define GUEST_WRITE32(a,v) write32((DWORD)(a),(DWORD)(v))
#define GUEST_WRITE64(a,v) write64((DWORD)(a),(unsigned __int64)(v))

static void recomp_guest_read128(DWORD address, DWORD words[4])
{
    BYTE* p = guest_ptr(address, 16u);
    DWORD i;

    if (!p)
    {
        s_fault = 1;
        words[0] = words[1] = words[2] = words[3] = 0u;
        return;
    }

    for (i = 0; i < 4u; ++i)
    {
        const BYTE* q = p + i * 4u;
        words[i] = ((DWORD)q[0]) |
                   ((DWORD)q[1] << 8) |
                   ((DWORD)q[2] << 16) |
                   ((DWORD)q[3] << 24);
    }
}

static void recomp_guest_write128(DWORD address, const DWORD words[4])
{
    BYTE* p = guest_ptr(address, 16u);
    DWORD i;

    if (!p)
    {
        s_fault = 1;
        return;
    }

    for (i = 0; i < 4u; ++i)
    {
        DWORD value = words[i];
        BYTE* q = p + i * 4u;
        q[0] = (BYTE)value;
        q[1] = (BYTE)(value >> 8);
        q[2] = (BYTE)(value >> 16);
        q[3] = (BYTE)(value >> 24);
    }
}

static DWORD lane_bits(const float src[4], DWORD lane)
{
    DWORD value;
    memcpy(&value, &src[lane], 4);
    return value;
}

static void set_lane_bits(float dst[4], DWORD lane, DWORD value)
{
    memcpy(&dst[lane], &value, 4);
}

static void recomp_xmm_load(float dst[4], DWORD addr)
{
    DWORD words[4];
    DWORD i;

    recomp_guest_read128(addr, words);

    for (i = 0; i < 4u; ++i)
        set_lane_bits(dst, i, words[i]);
}

static void recomp_xmm_store(DWORD addr, const float src[4])
{
    DWORD words[4];
    DWORD i;

    for (i = 0; i < 4u; ++i)
        words[i] = lane_bits(src, i);

    recomp_guest_write128(addr, words);
}

static void recomp_xmm_loadss(float dst[4], DWORD addr)
{
    set_lane_bits(dst, 0u, GUEST_READ32(addr));
    dst[1] = dst[2] = dst[3] = 0.0f;
}

static void recomp_xmm_loadsd(float dst[4], DWORD addr)
{
    unsigned __int64 bits = GUEST_READ64(addr);

    set_lane_bits(dst, 0u, (DWORD)bits);
    set_lane_bits(dst, 1u, (DWORD)(bits >> 32));
    dst[2] = dst[3] = 0.0f;
}

static void recomp_xmm_storesd(DWORD addr, const float src[4])
{
    unsigned __int64 bits =
        (unsigned __int64)lane_bits(src, 0u) |
        ((unsigned __int64)lane_bits(src, 1u) << 32);

    GUEST_WRITE64(addr, bits);
}

static void recomp_xmm_movlps_load(float dst[4], DWORD addr)
{
    unsigned __int64 bits = GUEST_READ64(addr);

    set_lane_bits(dst, 0u, (DWORD)bits);
    set_lane_bits(dst, 1u, (DWORD)(bits >> 32));
}

static void recomp_xmm_movlps_store(DWORD addr, const float src[4])
{
    unsigned __int64 bits =
        (unsigned __int64)lane_bits(src, 0u) |
        ((unsigned __int64)lane_bits(src, 1u) << 32);

    GUEST_WRITE64(addr, bits);
}

static void recomp_xmm_movhps_load(float dst[4], DWORD addr)
{
    unsigned __int64 bits = GUEST_READ64(addr);

    set_lane_bits(dst, 2u, (DWORD)bits);
    set_lane_bits(dst, 3u, (DWORD)(bits >> 32));
}

static void recomp_xmm_movhps_store(DWORD addr, const float src[4])
{
    unsigned __int64 bits =
        (unsigned __int64)lane_bits(src, 2u) |
        ((unsigned __int64)lane_bits(src, 3u) << 32);

    GUEST_WRITE64(addr, bits);
}

static void set_float_lane(float dst[4], DWORD lane, float value)
{
    dst[lane] = value;
}

static int run_fixture(void)
{
    int ok = 1;
    DWORD base = 0x00018001u;
    DWORD i;
    DWORD native = 0x01020304u;
    const BYTE* nativeBytes = (const BYTE*)&native;

    float xmm[4];
    float xmm2[4];
    float src[4];

    unsigned __int64 mm0;
    unsigned __int64 mask;

    ok &= check(nativeBytes[0] == 0x01u,
                "PASS: Xenon host is big-endian",
                "FAIL: Xenon host-order probe");

    /* Full unaligned 128-bit load must reconstruct four x86 float lanes. */
    GUEST_WRITE32(base + 0u, 0x3F800000u);  /* 1.0 */
    GUEST_WRITE32(base + 4u, 0xC0000000u);  /* -2.0 */
    GUEST_WRITE32(base + 8u, 0x40600000u);  /* 3.5 */
    GUEST_WRITE32(base + 12u, 0xC0880000u); /* -4.25 */

    recomp_xmm_load(xmm, base);

    ok &= check(xmm[0] == 1.0f &&
                xmm[1] == -2.0f &&
                xmm[2] == 3.5f &&
                xmm[3] == -4.25f,
                "PASS: unaligned 128-bit XMM load reconstructs four float lanes",
                "FAIL: 128-bit XMM lane reconstruction");

    /* Full store must emit little-endian guest dwords in lane order. */
    set_float_lane(src, 0u, 5.0f);
    set_float_lane(src, 1u, 6.5f);
    set_float_lane(src, 2u, -7.25f);
    set_float_lane(src, 3u, 8.0f);

    recomp_xmm_store(base + 0x31u, src);

    ok &= check(GUEST_READ32(base + 0x31u) == 0x40A00000u &&
                GUEST_READ32(base + 0x35u) == 0x40D00000u &&
                GUEST_READ32(base + 0x39u) == 0xC0E80000u &&
                GUEST_READ32(base + 0x3Du) == 0x41000000u,
                "PASS: 128-bit XMM store preserves lane bits and order",
                "FAIL: 128-bit XMM store lane bits");

    /* MOVSS memory load must set low lane and zero upper lanes. */
    xmm[0] = xmm[1] = xmm[2] = xmm[3] = 99.0f;
    GUEST_WRITE32(base + 0x51u, 0x3F200000u); /* 0.625 */
    recomp_xmm_loadss(xmm, base + 0x51u);

    ok &= check(xmm[0] == 0.625f &&
                xmm[1] == 0.0f &&
                xmm[2] == 0.0f &&
                xmm[3] == 0.0f,
                "PASS: MOVSS-style load uses explicit low lane and zeroes upper lanes",
                "FAIL: MOVSS-style load");

    /* MOVSD/MOVQ must preserve the raw low 64-bit payload, not native-double bytes. */
    GUEST_WRITE64(base + 0x59u, 0x1122334455667788ui64);
    recomp_xmm_loadsd(xmm, base + 0x59u);

    ok &= check(lane_bits(xmm, 0u) == 0x55667788u &&
                lane_bits(xmm, 1u) == 0x11223344u &&
                lane_bits(xmm, 2u) == 0u &&
                lane_bits(xmm, 3u) == 0u,
                "PASS: MOVSD-style load preserves raw low 64-bit payload",
                "FAIL: MOVSD raw payload");

    recomp_xmm_storesd(base + 0x69u, xmm);

    ok &= check(GUEST_READ64(base + 0x69u) == 0x1122334455667788ui64,
                "PASS: MOVSD-style store preserves raw low 64-bit payload",
                "FAIL: MOVSD store raw payload");

    /* MOVLPS/MOVHPS replace exactly their two lanes and preserve the others. */
    set_lane_bits(xmm, 0u, 0xAAAAAAAAu);
    set_lane_bits(xmm, 1u, 0xBBBBBBBBu);
    set_lane_bits(xmm, 2u, 0xCCCCCCCCu);
    set_lane_bits(xmm, 3u, 0xDDDDDDDDu);

    GUEST_WRITE64(base + 0x79u, 0x0102030405060708ui64);
    recomp_xmm_movlps_load(xmm, base + 0x79u);

    ok &= check(lane_bits(xmm, 0u) == 0x05060708u &&
                lane_bits(xmm, 1u) == 0x01020304u &&
                lane_bits(xmm, 2u) == 0xCCCCCCCCu &&
                lane_bits(xmm, 3u) == 0xDDDDDDDDu,
                "PASS: MOVLPS-style load replaces low lanes only",
                "FAIL: MOVLPS lane preservation");

    GUEST_WRITE64(base + 0x81u, 0xA1A2A3A4B1B2B3B4ui64);
    recomp_xmm_movhps_load(xmm, base + 0x81u);

    ok &= check(lane_bits(xmm, 0u) == 0x05060708u &&
                lane_bits(xmm, 1u) == 0x01020304u &&
                lane_bits(xmm, 2u) == 0xB1B2B3B4u &&
                lane_bits(xmm, 3u) == 0xA1A2A3A4u,
                "PASS: MOVHPS-style load replaces high lanes only",
                "FAIL: MOVHPS lane preservation");

    recomp_xmm_movlps_store(base + 0x91u, xmm);
    recomp_xmm_movhps_store(base + 0x99u, xmm);

    ok &= check(GUEST_READ64(base + 0x91u) == 0x0102030405060708ui64 &&
                GUEST_READ64(base + 0x99u) == 0xA1A2A3A4B1B2B3B4ui64,
                "PASS: MOVLPS/MOVHPS stores preserve raw lane payloads",
                "FAIL: MOVLPS/MOVHPS store payloads");

    /* Packed arithmetic with a memory source relies on recomp_xmm_load. */
    xmm[0] = 10.0f; xmm[1] = 20.0f; xmm[2] = 30.0f; xmm[3] = 40.0f;
    GUEST_WRITE32(base + 0xA1u, 0x3F800000u); /* 1 */
    GUEST_WRITE32(base + 0xA5u, 0x40000000u); /* 2 */
    GUEST_WRITE32(base + 0xA9u, 0x40400000u); /* 3 */
    GUEST_WRITE32(base + 0xADu, 0x40800000u); /* 4 */

    recomp_xmm_load(xmm2, base + 0xA1u);
    for (i = 0; i < 4u; ++i)
        xmm[i] += xmm2[i];

    ok &= check(xmm[0] == 11.0f &&
                xmm[1] == 22.0f &&
                xmm[2] == 33.0f &&
                xmm[3] == 44.0f,
                "PASS: packed ADDPS-style memory lanes are numerically correct",
                "FAIL: packed arithmetic memory lanes");

    /* Raw lane bitwise operations also depend on exact packed memory bits. */
    set_lane_bits(xmm, 0u, 0xFFFF0000u);
    set_lane_bits(xmm, 1u, 0xAAAAAAAAu);
    set_lane_bits(xmm, 2u, 0x12345678u);
    set_lane_bits(xmm, 3u, 0x00000000u);

    GUEST_WRITE32(base + 0xB1u, 0x00FFFF00u);
    GUEST_WRITE32(base + 0xB5u, 0x55555555u);
    GUEST_WRITE32(base + 0xB9u, 0xFFFFFFFFu);
    GUEST_WRITE32(base + 0xBDu, 0xDEADBEEFu);
    recomp_xmm_load(xmm2, base + 0xB1u);

    for (i = 0; i < 4u; ++i)
        set_lane_bits(xmm, i, lane_bits(xmm, i) ^ lane_bits(xmm2, i));

    ok &= check(lane_bits(xmm, 0u) == 0xFF00FF00u &&
                lane_bits(xmm, 1u) == 0xFFFFFFFFu &&
                lane_bits(xmm, 2u) == 0xEDCBA987u &&
                lane_bits(xmm, 3u) == 0xDEADBEEFu,
                "PASS: XORPS-style packed memory preserves raw lane bits",
                "FAIL: packed bitwise memory lanes");

    /* MMX memory operands use the explicit 64-bit scalar guest path. */
    GUEST_WRITE64(base + 0xC9u, 0xFFEEDDCCBBAA9988ui64);
    mm0 = GUEST_READ64(base + 0xC9u);

    ok &= check(mm0 == 0xFFEEDDCCBBAA9988ui64,
                "PASS: MMX MOVQ-style memory read preserves 64-bit payload",
                "FAIL: MMX MOVQ read");

    mask = 0x00FF00FF00FF00FFui64;
    mm0 &= mask;
    GUEST_WRITE64(base + 0xD1u, mm0);

    ok &= check(GUEST_READ64(base + 0xD1u) ==
                (0xFFEEDDCCBBAA9988ui64 & mask),
                "PASS: MMX PAND-style memory path uses explicit 64-bit access",
                "FAIL: MMX PAND-style path");

    /* SIMD payloads remain coherent through mirrors/KSEG. */
    src[0] = 1.25f; src[1] = 2.5f; src[2] = 5.0f; src[3] = 10.0f;
    recomp_xmm_store(0x0401A000u, src);
    recomp_xmm_load(xmm, 0x0001A000u);

    ok &= check(xmm[0] == 1.25f &&
                xmm[1] == 2.5f &&
                xmm[2] == 5.0f &&
                xmm[3] == 10.0f,
                "PASS: 128-bit XMM payload coherent through RAM mirror",
                "FAIL: XMM mirror coherence");

    GUEST_WRITE64(0x8123A000u, 0x0123456789ABCDEFui64);
    ok &= check(GUEST_READ64(0x0123A000u) == 0x0123456789ABCDEFui64,
                "PASS: MMX-width payload coherent through KSEG0 alias",
                "FAIL: MMX KSEG0 coherence");

    /* One 128-bit transfer must reject a window crossing as a whole. */
    s_fault = 0;
    recomp_xmm_load(xmm, 0x03FFFFF8u);
    ok &= check(s_fault != 0,
                "PASS: 128-bit XMM helper rejects cross-64MiB transfer",
                "FAIL: 128-bit XMM transfer wrapped into mirror");

    /* Same rule for one low-64 XMM/MMX transfer. */
    s_fault = 0;
    (void)GUEST_READ64(0x03FFFFFCu);
    ok &= check(s_fault != 0,
                "PASS: 64-bit SIMD/MMX helper rejects cross-64MiB transfer",
                "FAIL: 64-bit SIMD/MMX transfer crossed window");

    s_fault = 0;
    recomp_xmm_load(xmm, 0xFD001000u);
    ok &= check(s_fault != 0,
                "PASS: 128-bit XMM helper rejects NV2A MMIO as RAM",
                "FAIL: XMM MMIO rejection");

    s_fault = 0;
    return ok;
}

VOID __cdecl main()
{
    int result = 0;
    DWORD started;
    DWORD nextHeartbeat = 1000u;

    s_logFile = CreateFileA(
        "game:\\merc360-phase3c-sse-mmx.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 3C SSE/XMM + MMX GUEST-MEMORY ABI START");
    trace("BUILD TAG: P3C-SIMD-20261018-A");
    trace("No translated Mercenaries function executes in this fixture");

    g_ram = (BYTE*)malloc(RAM_SIZE);

    if (!g_ram)
    {
        trace("FATAL: could not allocate 64 MiB guest RAM");
        goto wait_for_exit;
    }

    memset(g_ram, 0, RAM_SIZE);

    result = run_fixture();

    if (result)
        trace("PHASE 3C SIMD MEMORY ABI RESULT: PASS");
    else
        trace("PHASE 3C SIMD MEMORY ABI RESULT: FAIL");

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

    trace("PHASE 3C SSE/XMM + MMX GUEST-MEMORY ABI END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

/*
 * Mercenaries Xbox 360 - Phase 3A explicit scalar guest-memory ABI.
 *
 * SELF-CONTAINED XDK TEST. No translated Mercenaries function executes here.
 *
 * This fixture uses the exact helper shape emitted by the Phase 3A lifter:
 *   GUEST_READ8/16/32/64
 *   GUEST_WRITE8/16/32/64
 *
 * The backing guest bytes are little-endian; Xenon is big-endian.
 */

#include <xtl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MERC_GUEST_RAM_SIZE  0x04000000u
#define MERC_GUEST_RAM_MASK  0x03FFFFFFu
#define MERC_RAM_MIRROR_END  0x74000000u
#define MERC_KSEG_BASE       0x80000000u
#define MERC_KSEG_END        0xC0000000u

#define MERC_SYNTH_FENCE_BASE  0x80000000u
#define MERC_SYNTH_FENCE_END   0x80001000u
#define MERC_SYNTH_KERNEL_BASE 0x80010000u
#define MERC_SYNTH_KERNEL_END  0x80011000u

typedef struct GuestMemory
{
    BYTE* ram;
} GuestMemory;

static GuestMemory g_guest;
static HANDLE s_logFile = INVALID_HANDLE_VALUE;
static int s_accessFault = 0;

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P3A] ");
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

static int guest_ram_offset(DWORD address, DWORD width, DWORD* offsetOut)
{
    DWORD offset;

    if (!offsetOut || width == 0u)
        return 0;

    if (address < MERC_RAM_MIRROR_END)
    {
        offset = address & MERC_GUEST_RAM_MASK;
    }
    else if (address >= MERC_KSEG_BASE && address < MERC_KSEG_END)
    {
        if ((address >= MERC_SYNTH_FENCE_BASE &&
             address < MERC_SYNTH_FENCE_END) ||
            (address >= MERC_SYNTH_KERNEL_BASE &&
             address < MERC_SYNTH_KERNEL_END))
            return 0;

        offset = address & MERC_GUEST_RAM_MASK;
    }
    else
    {
        return 0;
    }

    if (offset >= MERC_GUEST_RAM_SIZE ||
        width > MERC_GUEST_RAM_SIZE - offset)
        return 0;

    *offsetOut = offset;
    return 1;
}

static BYTE* guest_ptr(DWORD address, DWORD width)
{
    DWORD offset;

    if (!g_guest.ram || !guest_ram_offset(address, width, &offset))
        return NULL;

    return g_guest.ram + offset;
}

static BYTE recomp_guest_read8(DWORD address)
{
    BYTE* p = guest_ptr(address, 1u);
    if (!p)
    {
        s_accessFault = 1;
        return 0u;
    }
    return p[0];
}

static WORD recomp_guest_read16(DWORD address)
{
    BYTE* p = guest_ptr(address, 2u);
    if (!p)
    {
        s_accessFault = 1;
        return 0u;
    }

    return (WORD)((WORD)p[0] | ((WORD)p[1] << 8));
}

static DWORD recomp_guest_read32(DWORD address)
{
    BYTE* p = guest_ptr(address, 4u);
    if (!p)
    {
        s_accessFault = 1;
        return 0u;
    }

    return ((DWORD)p[0]) |
           ((DWORD)p[1] << 8) |
           ((DWORD)p[2] << 16) |
           ((DWORD)p[3] << 24);
}

static unsigned __int64 recomp_guest_read64(DWORD address)
{
    BYTE* p = guest_ptr(address, 8u);
    unsigned __int64 lo;
    unsigned __int64 hi;

    if (!p)
    {
        s_accessFault = 1;
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

static void recomp_guest_write8(DWORD address, BYTE value)
{
    BYTE* p = guest_ptr(address, 1u);
    if (!p)
    {
        s_accessFault = 1;
        return;
    }
    p[0] = value;
}

static void recomp_guest_write16(DWORD address, WORD value)
{
    BYTE* p = guest_ptr(address, 2u);
    if (!p)
    {
        s_accessFault = 1;
        return;
    }

    p[0] = (BYTE)value;
    p[1] = (BYTE)(value >> 8);
}

static void recomp_guest_write32(DWORD address, DWORD value)
{
    BYTE* p = guest_ptr(address, 4u);
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

static void recomp_guest_write64(DWORD address, unsigned __int64 value)
{
    BYTE* p = guest_ptr(address, 8u);
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

#define GUEST_READ8(addr)   recomp_guest_read8((DWORD)(addr))
#define GUEST_READ16(addr)  recomp_guest_read16((DWORD)(addr))
#define GUEST_READ32(addr)  recomp_guest_read32((DWORD)(addr))
#define GUEST_READ64(addr)  recomp_guest_read64((DWORD)(addr))
#define GUEST_WRITE8(addr, value)  recomp_guest_write8((DWORD)(addr), (BYTE)(value))
#define GUEST_WRITE16(addr, value) recomp_guest_write16((DWORD)(addr), (WORD)(value))
#define GUEST_WRITE32(addr, value) recomp_guest_write32((DWORD)(addr), (DWORD)(value))
#define GUEST_WRITE64(addr, value) recomp_guest_write64((DWORD)(addr), (unsigned __int64)(value))

#define EXPLICIT_PUSH32(sp, val) do { \
    DWORD _pushValue = (DWORD)(val); \
    (sp) -= 4u; \
    GUEST_WRITE32((sp), _pushValue); \
} while (0)

#define EXPLICIT_POP32(sp, dst) do { \
    (dst) = GUEST_READ32((sp)); \
    (sp) += 4u; \
} while (0)

static int run_generated_style_fixture(void)
{
    int ok = 1;
    DWORD eax = 0;
    DWORD ecx = 0x00012000u;
    DWORD esp = 0x008BFFF0u;
    DWORD popped = 0;
    DWORD cmpDest;
    DWORD cmpAcc;
    DWORD cmpSrc;
    BYTE* bytes;

    DWORD native = 0x01020304u;
    const BYTE* nativeBytes = (const BYTE*)&native;

    ok &= check(nativeBytes[0] == 0x01u &&
                nativeBytes[1] == 0x02u &&
                nativeBytes[2] == 0x03u &&
                nativeBytes[3] == 0x04u,
                "PASS: Xenon host byte order is big-endian",
                "FAIL: host byte order is not big-endian");

    GUEST_WRITE32(ecx + 4u, 0x12345678u);
    eax = GUEST_READ32(ecx + 4u);

    ok &= check(eax == 0x12345678u,
                "PASS: generated-style 32-bit MOV round-trip",
                "FAIL: generated-style 32-bit MOV round-trip");

    bytes = guest_ptr(ecx + 4u, 4u);
    ok &= check(bytes &&
                bytes[0] == 0x78u &&
                bytes[1] == 0x56u &&
                bytes[2] == 0x34u &&
                bytes[3] == 0x12u,
                "PASS: explicit 32-bit write stores little-endian guest bytes",
                "FAIL: explicit 32-bit guest byte order");

    eax = 5u;
    GUEST_WRITE32(ecx + 4u, GUEST_READ32(ecx + 4u) + eax);

    ok &= check(GUEST_READ32(ecx + 4u) == 0x1234567Du,
                "PASS: explicit generated-style 32-bit ADD RMW",
                "FAIL: explicit 32-bit ADD RMW");

    GUEST_WRITE16(ecx + 3u, 0x7FFEu);
    GUEST_WRITE16(ecx + 3u, GUEST_READ16(ecx + 3u) + 1u);

    ok &= check(GUEST_READ16(ecx + 3u) == 0x7FFFu,
                "PASS: unaligned 16-bit RMW",
                "FAIL: unaligned 16-bit RMW");

    GUEST_WRITE8(ecx + 9u, 0xA5u);
    GUEST_WRITE8(ecx + 9u, GUEST_READ8(ecx + 9u) ^ 0xFFu);

    ok &= check(GUEST_READ8(ecx + 9u) == 0x5Au,
                "PASS: 8-bit XOR RMW",
                "FAIL: 8-bit XOR RMW");

    GUEST_WRITE64(ecx + 0x11u, 0x0102030405060708ui64);

    ok &= check(GUEST_READ64(ecx + 0x11u) == 0x0102030405060708ui64,
                "PASS: unaligned 64-bit explicit round-trip",
                "FAIL: unaligned 64-bit explicit round-trip");

    bytes = guest_ptr(ecx + 0x11u, 8u);
    ok &= check(bytes &&
                bytes[0] == 0x08u &&
                bytes[1] == 0x07u &&
                bytes[2] == 0x06u &&
                bytes[3] == 0x05u &&
                bytes[4] == 0x04u &&
                bytes[5] == 0x03u &&
                bytes[6] == 0x02u &&
                bytes[7] == 0x01u,
                "PASS: explicit 64-bit write stores little-endian guest bytes",
                "FAIL: explicit 64-bit guest byte order");

    GUEST_WRITE32(0x04070000u, 0xA1B2C3D4u);
    ok &= check(GUEST_READ32(0x00070000u) == 0xA1B2C3D4u,
                "PASS: explicit helper coherent through RAM mirror",
                "FAIL: explicit RAM mirror coherence");

    GUEST_WRITE32(0x81230000u, 0x55667788u);
    ok &= check(GUEST_READ32(0x01230000u) == 0x55667788u,
                "PASS: explicit helper coherent through KSEG0 alias",
                "FAIL: explicit KSEG0 coherence");

    GUEST_WRITE32(0xA1230000u, 0xCAFEBABEu);
    ok &= check(GUEST_READ32(0x01230000u) == 0xCAFEBABEu,
                "PASS: explicit helper coherent through KSEG1 alias",
                "FAIL: explicit KSEG1 coherence");

    GUEST_WRITE32(0x00013000u, 0x11111111u);
    cmpAcc = 0x11111111u;
    cmpSrc = 0x22222222u;
    cmpDest = GUEST_READ32(0x00013000u);
    if (cmpDest == cmpAcc)
        GUEST_WRITE32(0x00013000u, cmpSrc);
    else
        cmpAcc = cmpDest;

    ok &= check(GUEST_READ32(0x00013000u) == 0x22222222u &&
                cmpAcc == 0x11111111u,
                "PASS: CMPXCHG-style equal path uses explicit read/write",
                "FAIL: CMPXCHG-style equal path");

    cmpAcc = 0x33333333u;
    cmpSrc = 0x44444444u;
    cmpDest = GUEST_READ32(0x00013000u);
    if (cmpDest == cmpAcc)
        GUEST_WRITE32(0x00013000u, cmpSrc);
    else
        cmpAcc = cmpDest;

    ok &= check(GUEST_READ32(0x00013000u) == 0x22222222u &&
                cmpAcc == 0x22222222u,
                "PASS: CMPXCHG-style mismatch preserves destination and loads EAX",
                "FAIL: CMPXCHG-style mismatch path");

    GUEST_WRITE32(esp + 4u, 0xDEADC0DEu);
    EXPLICIT_PUSH32(esp, GUEST_READ32(esp + 4u));

    ok &= check(esp == 0x008BFFECu &&
                GUEST_READ32(esp) == 0xDEADC0DEu,
                "PASS: explicit PUSH32 evaluates memory source before ESP decrement",
                "FAIL: explicit PUSH32 evaluation order");

    EXPLICIT_POP32(esp, popped);
    ok &= check(esp == 0x008BFFF0u &&
                popped == 0xDEADC0DEu,
                "PASS: explicit POP32 restores ESP and value",
                "FAIL: explicit POP32 contract");

    s_accessFault = 0;
    (void)GUEST_READ32(0xFD001000u);
    ok &= check(s_accessFault != 0,
                "PASS: explicit helper rejects NV2A MMIO as ordinary RAM",
                "FAIL: NV2A MMIO was treated as RAM");

    s_accessFault = 0;
    GUEST_WRITE32(0x03FFFFFFu, 0xDEADBEEFu);
    ok &= check(s_accessFault != 0,
                "PASS: explicit helper rejects cross-64MiB write",
                "FAIL: cross-64MiB write was accepted");

    s_accessFault = 0;
    return ok;
}

VOID __cdecl main()
{
    int result = 0;
    DWORD started;
    DWORD nextHeartbeat = 1000u;

    s_logFile = CreateFileA(
        "game:\\merc360-phase3a-scalar-memory.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 3A EXPLICIT SCALAR GUEST-MEMORY ABI START");
    trace("BUILD TAG: P3A-SCALAR-20261018-A");
    trace("No translated Mercenaries function executes in this fixture");

    g_guest.ram = (BYTE*)malloc(MERC_GUEST_RAM_SIZE);
    if (!g_guest.ram)
    {
        trace("FATAL: could not allocate 64 MiB guest RAM");
        goto wait_for_exit;
    }

    memset(g_guest.ram, 0, MERC_GUEST_RAM_SIZE);

    result = run_generated_style_fixture();

    if (result)
        trace("PHASE 3A SCALAR MEMORY ABI RESULT: PASS");
    else
        trace("PHASE 3A SCALAR MEMORY ABI RESULT: FAIL");

    free(g_guest.ram);
    g_guest.ram = NULL;
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

    trace("PHASE 3A EXPLICIT SCALAR GUEST-MEMORY ABI END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

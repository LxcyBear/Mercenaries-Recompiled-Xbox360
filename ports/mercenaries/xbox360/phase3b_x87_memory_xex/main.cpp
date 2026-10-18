/*
 * Mercenaries Xbox 360 - Phase 3B signed + x87 guest-memory ABI.
 *
 * SELF-CONTAINED XDK TEST. No translated Mercenaries function executes here.
 */

#include <xtl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RAM_SIZE       0x04000000u
#define RAM_MASK       0x03FFFFFFu
#define MIRROR_END     0x74000000u
#define KSEG_BASE      0x80000000u
#define KSEG_END       0xC0000000u
#define FENCE_BASE     0x80000000u
#define FENCE_END      0x80001000u
#define KERNEL_BASE    0x80010000u
#define KERNEL_END     0x80011000u

static BYTE* g_ram = NULL;
static HANDLE s_logFile = INVALID_HANDLE_VALUE;
static int s_fault = 0;

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P3B] ");
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

static BYTE read8(DWORD address)
{
    BYTE* p = guest_ptr(address, 1u);
    if (!p)
    {
        s_fault = 1;
        return 0u;
    }
    return p[0];
}

static WORD read16(DWORD address)
{
    BYTE* p = guest_ptr(address, 2u);
    if (!p)
    {
        s_fault = 1;
        return 0u;
    }
    return (WORD)((WORD)p[0] | ((WORD)p[1] << 8));
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
    unsigned __int64 lo;
    unsigned __int64 hi;
    BYTE* p = guest_ptr(address, 8u);

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

static void write8(DWORD address, BYTE value)
{
    BYTE* p = guest_ptr(address, 1u);
    if (!p)
    {
        s_fault = 1;
        return;
    }
    p[0] = value;
}

static void write16(DWORD address, WORD value)
{
    BYTE* p = guest_ptr(address, 2u);
    if (!p)
    {
        s_fault = 1;
        return;
    }
    p[0] = (BYTE)value;
    p[1] = (BYTE)(value >> 8);
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

#define GUEST_READ8(a)   read8((DWORD)(a))
#define GUEST_READ16(a)  read16((DWORD)(a))
#define GUEST_READ32(a)  read32((DWORD)(a))
#define GUEST_READ64(a)  read64((DWORD)(a))
#define GUEST_WRITE8(a,v)   write8((DWORD)(a),(BYTE)(v))
#define GUEST_WRITE16(a,v)  write16((DWORD)(a),(WORD)(v))
#define GUEST_WRITE32(a,v)  write32((DWORD)(a),(DWORD)(v))
#define GUEST_WRITE64(a,v)  write64((DWORD)(a),(unsigned __int64)(v))

#define GUEST_SREAD8(a)   ((CHAR)GUEST_READ8(a))
#define GUEST_SREAD16(a)  ((SHORT)GUEST_READ16(a))
#define GUEST_SREAD32(a)  ((LONG)GUEST_READ32(a))
#define GUEST_SREAD64(a)  ((__int64)GUEST_READ64(a))

static float recomp_guest_readf32(DWORD address)
{
    DWORD bits = GUEST_READ32(address);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static double recomp_guest_readf64(DWORD address)
{
    unsigned __int64 bits = GUEST_READ64(address);
    double value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static void recomp_guest_writef32(DWORD address, float value)
{
    DWORD bits;
    memcpy(&bits, &value, sizeof(bits));
    GUEST_WRITE32(address, bits);
}

static void recomp_guest_writef64(DWORD address, double value)
{
    unsigned __int64 bits;
    memcpy(&bits, &value, sizeof(bits));
    GUEST_WRITE64(address, bits);
}

#define GUEST_READF32(a) recomp_guest_readf32((DWORD)(a))
#define GUEST_READF64(a) recomp_guest_readf64((DWORD)(a))
#define GUEST_WRITEF32(a,v) recomp_guest_writef32((DWORD)(a),(float)(v))
#define GUEST_WRITEF64(a,v) recomp_guest_writef64((DWORD)(a),(double)(v))

static int run_fixture(void)
{
    int ok = 1;
    DWORD base = 0x00014000u;
    DWORD eax = 0;
    double fp = 0.0;
    double cmpMem = 0.0;
    BYTE* bytes;

    DWORD native = 0x01020304u;
    const BYTE* nativeBytes = (const BYTE*)&native;

    ok &= check(nativeBytes[0] == 0x01u,
                "PASS: Xenon host is big-endian",
                "FAIL: Xenon host-order probe");

    /* MOVSX-style signed loads. */
    GUEST_WRITE8(base + 1u, 0x80u);
    eax = (DWORD)(LONG)GUEST_SREAD8(base + 1u);
    ok &= check(eax == 0xFFFFFF80u,
                "PASS: signed 8-bit guest read sign-extends",
                "FAIL: signed 8-bit sign extension");

    GUEST_WRITE16(base + 3u, 0xFF85u);
    eax = (DWORD)(LONG)GUEST_SREAD16(base + 3u);
    ok &= check(eax == 0xFFFFFF85u,
                "PASS: unaligned signed 16-bit guest read sign-extends",
                "FAIL: signed 16-bit sign extension");

    GUEST_WRITE32(base + 7u, 0xFFFFCFC7u);
    ok &= check(GUEST_SREAD32(base + 7u) == -12345,
                "PASS: unaligned signed 32-bit guest read",
                "FAIL: signed 32-bit guest read");

    GUEST_WRITE64(base + 0x0Du, 0xFFFFFFFFFFFFFF9Cui64);
    ok &= check(GUEST_SREAD64(base + 0x0Du) == -100i64,
                "PASS: unaligned signed 64-bit guest read",
                "FAIL: signed 64-bit guest read");

    /* IEEE-754 float/double guest byte semantics. */
    GUEST_WRITEF32(base + 0x21u, -12.5f);
    ok &= check(GUEST_READF32(base + 0x21u) == -12.5f,
                "PASS: unaligned float32 round-trip",
                "FAIL: float32 round-trip");

    bytes = guest_ptr(base + 0x21u, 4u);
    ok &= check(bytes &&
                bytes[0] == 0x00u &&
                bytes[1] == 0x00u &&
                bytes[2] == 0x48u &&
                bytes[3] == 0xC1u,
                "PASS: float32 stored as little-endian IEEE-754 bytes",
                "FAIL: float32 guest byte layout");

    GUEST_WRITEF64(base + 0x29u, 1.5);
    ok &= check(GUEST_READF64(base + 0x29u) == 1.5,
                "PASS: unaligned float64 round-trip",
                "FAIL: float64 round-trip");

    bytes = guest_ptr(base + 0x29u, 8u);
    ok &= check(bytes &&
                bytes[0] == 0x00u &&
                bytes[1] == 0x00u &&
                bytes[2] == 0x00u &&
                bytes[3] == 0x00u &&
                bytes[4] == 0x00u &&
                bytes[5] == 0x00u &&
                bytes[6] == 0xF8u &&
                bytes[7] == 0x3Fu,
                "PASS: float64 stored as little-endian IEEE-754 bytes",
                "FAIL: float64 guest byte layout");

    /* FILD-like signed integer load into x87 double domain. */
    GUEST_WRITE16(base + 0x35u, 0xFF85u);
    fp = (double)GUEST_SREAD16(base + 0x35u);
    ok &= check(fp == -123.0,
                "PASS: FILD-style signed integer memory load",
                "FAIL: FILD-style load");

    /* FIADD-like signed integer-memory arithmetic. */
    GUEST_WRITE32(base + 0x39u, 0xFFFFFFF9u);
    fp = 10.0;
    fp += (double)GUEST_SREAD32(base + 0x39u);
    ok &= check(fp == 3.0,
                "PASS: FIADD-style signed memory arithmetic",
                "FAIL: FIADD-style arithmetic");

    /* FLD + FADD + FSTP-style explicit floating memory path. */
    GUEST_WRITEF32(base + 0x41u, 2.5f);
    GUEST_WRITEF64(base + 0x49u, 0.75);
    fp = (double)GUEST_READF32(base + 0x41u);
    fp += GUEST_READF64(base + 0x49u);
    GUEST_WRITEF64(base + 0x51u, fp);

    ok &= check(GUEST_READF64(base + 0x51u) == 3.25,
                "PASS: FLD/FADD/FSTP-style explicit floating memory path",
                "FAIL: x87 floating memory path");

    /* FISTP-style integer result store (exact integer avoids rounding ambiguity). */
    fp = -42.0;
    GUEST_WRITE32(base + 0x59u, (DWORD)(LONG)fp);
    ok &= check(GUEST_SREAD32(base + 0x59u) == -42,
                "PASS: FIST-style explicit integer destination write",
                "FAIL: FIST-style destination write");

    /* FCOM-style float memory comparison. */
    fp = 3.0;
    GUEST_WRITEF64(base + 0x61u, 4.0);
    cmpMem = GUEST_READF64(base + 0x61u);
    ok &= check(fp < cmpMem,
                "PASS: FCOM-style memory operand comparison",
                "FAIL: FCOM-style memory comparison");

    /* Alias coherence remains valid for floating payloads. */
    GUEST_WRITEF32(0x04015000u, 6.25f);
    ok &= check(GUEST_READF32(0x00015000u) == 6.25f,
                "PASS: float32 coherent through RAM mirror",
                "FAIL: float32 RAM mirror coherence");

    GUEST_WRITEF64(0x81236000u, -9.5);
    ok &= check(GUEST_READF64(0x01236000u) == -9.5,
                "PASS: float64 coherent through KSEG0 alias",
                "FAIL: float64 KSEG0 coherence");

    /* Non-RAM and boundary failures propagate through floating helpers. */
    s_fault = 0;
    (void)GUEST_READF32(0xFD001000u);
    ok &= check(s_fault != 0,
                "PASS: float32 helper rejects NV2A MMIO as RAM",
                "FAIL: float32 MMIO rejection");

    s_fault = 0;
    GUEST_WRITEF64(0x03FFFFFCu, 1.0);
    ok &= check(s_fault != 0,
                "PASS: float64 helper rejects cross-64MiB write",
                "FAIL: float64 cross-window rejection");

    s_fault = 0;
    return ok;
}

VOID __cdecl main()
{
    int result = 0;
    DWORD started;
    DWORD nextHeartbeat = 1000u;

    s_logFile = CreateFileA(
        "game:\\merc360-phase3b-x87-memory.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 3B SIGNED + X87 GUEST-MEMORY ABI START");
    trace("BUILD TAG: P3B-X87MEM-20261018-A");
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
        trace("PHASE 3B X87 MEMORY ABI RESULT: PASS");
    else
        trace("PHASE 3B X87 MEMORY ABI RESULT: FAIL");

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

    trace("PHASE 3B SIGNED + X87 GUEST-MEMORY ABI END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

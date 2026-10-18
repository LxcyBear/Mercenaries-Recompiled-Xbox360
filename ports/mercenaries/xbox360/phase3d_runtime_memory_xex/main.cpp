/*
 * Mercenaries Xbox 360 - Phase 3D explicit runtime/string memory cleanup.
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

#define RECOMP_EXPLICIT_GUEST_MEMORY_ABI 1

static BYTE* g_ram = NULL;
static HANDLE s_logFile = INVALID_HANDLE_VALUE;
static int s_fault = 0;

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P3D] ");
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

static BYTE recomp_guest_read8(DWORD address)
{
    BYTE* p = guest_ptr(address, 1u);
    if (!p)
    {
        s_fault = 1;
        return 0u;
    }
    return p[0];
}

static WORD recomp_guest_read16(DWORD address)
{
    BYTE* p = guest_ptr(address, 2u);
    if (!p)
    {
        s_fault = 1;
        return 0u;
    }
    return (WORD)((WORD)p[0] | ((WORD)p[1] << 8));
}

static DWORD recomp_guest_read32(DWORD address)
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

static unsigned __int64 recomp_guest_read64(DWORD address)
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

static void recomp_guest_write8(DWORD address, BYTE value)
{
    BYTE* p = guest_ptr(address, 1u);
    if (!p)
    {
        s_fault = 1;
        return;
    }
    p[0] = value;
}

static void recomp_guest_write16(DWORD address, WORD value)
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

static void recomp_guest_write32(DWORD address, DWORD value)
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

static void recomp_guest_write64(DWORD address, unsigned __int64 value)
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

#define GUEST_READ8(addr)   recomp_guest_read8((DWORD)(addr))
#define GUEST_READ16(addr)  recomp_guest_read16((DWORD)(addr))
#define GUEST_READ32(addr)  recomp_guest_read32((DWORD)(addr))
#define GUEST_READ64(addr)  recomp_guest_read64((DWORD)(addr))
#define GUEST_WRITE8(addr, value)  recomp_guest_write8((DWORD)(addr), (BYTE)(value))
#define GUEST_WRITE16(addr, value) recomp_guest_write16((DWORD)(addr), (WORD)(value))
#define GUEST_WRITE32(addr, value) recomp_guest_write32((DWORD)(addr), (DWORD)(value))
#define GUEST_WRITE64(addr, value) recomp_guest_write64((DWORD)(addr), (unsigned __int64)(value))

#define RECOMP_READ8(addr)        GUEST_READ8(addr)
#define RECOMP_READ16(addr)       GUEST_READ16(addr)
#define RECOMP_READ32(addr)       GUEST_READ32(addr)
#define RECOMP_READ64(addr)       GUEST_READ64(addr)
#define RECOMP_WRITE8(addr, v)    GUEST_WRITE8((addr), (v))
#define RECOMP_WRITE16(addr, v)   GUEST_WRITE16((addr), (v))
#define RECOMP_WRITE32(addr, v)   GUEST_WRITE32((addr), (v))
#define RECOMP_WRITE64(addr, v)   GUEST_WRITE64((addr), (v))

#define LO8(r)  ((BYTE)((r) & 0xFFu))
#define LO16(r) ((WORD)((r) & 0xFFFFu))
#define SET_LO8(r, v) ((r) = ((r) & 0xFFFFFF00u) | ((DWORD)(BYTE)(v)))
#define SET_LO16(r, v) ((r) = ((r) & 0xFFFF0000u) | ((DWORD)(WORD)(v)))

#define PUSH32(sp, val) do { \
    DWORD _pv = (DWORD)(val); \
    (sp) -= 4u; \
    RECOMP_WRITE32((sp), _pv); \
} while (0)

#define POP32(sp, dst) do { \
    (dst) = RECOMP_READ32(sp); \
    (sp) += 4u; \
} while (0)

static void XBOX_MEMCPY(DWORD destination, DWORD source, DWORD length)
{
    DWORD offset = 0u;

    while (length - offset >= 4u &&
           (((destination + offset) | (source + offset)) & 3u) == 0u)
    {
        RECOMP_WRITE32(destination + offset,
                       RECOMP_READ32(source + offset));
        offset += 4u;
    }

    while (offset < length)
    {
        RECOMP_WRITE8(destination + offset,
                      RECOMP_READ8(source + offset));
        ++offset;
    }
}

static void XBOX_REP_MOVS(DWORD destination,
                          DWORD source,
                          DWORD count,
                          DWORD width)
{
    while (count-- != 0u)
    {
        if (width == 4u)
            RECOMP_WRITE32(destination, RECOMP_READ32(source));
        else if (width == 2u)
            RECOMP_WRITE16(destination, RECOMP_READ16(source));
        else
            RECOMP_WRITE8(destination, RECOMP_READ8(source));

        destination += width;
        source += width;
    }
}

static int bytes_equal(DWORD address, const BYTE* expected, DWORD length)
{
    DWORD i;

    for (i = 0u; i < length; ++i)
    {
        if (RECOMP_READ8(address + i) != expected[i])
            return 0;
    }

    return 1;
}

static int run_fixture(void)
{
    int ok = 1;
    DWORD native = 0x01020304u;
    const BYTE* nativeBytes = (const BYTE*)&native;

    DWORD esp = 0x008BFFF0u;
    DWORD popped = 0u;
    DWORD eax = 0u;
    DWORD esi;
    DWORD edi;
    DWORD ecx;
    DWORD i;

    BYTE expected[16];

    ok &= check(nativeBytes[0] == 0x01u &&
                nativeBytes[1] == 0x02u &&
                nativeBytes[2] == 0x03u &&
                nativeBytes[3] == 0x04u,
                "PASS: Xenon host is big-endian",
                "FAIL: Xenon host-order probe");

    /*
     * Shared PUSH32/POP32 runtime macros. Source must be evaluated using old
     * ESP before PUSH decrements it.
     */
    RECOMP_WRITE32(esp + 4u, 0xDEADC0DEu);
    PUSH32(esp, RECOMP_READ32(esp + 4u));

    ok &= check(esp == 0x008BFFECu &&
                RECOMP_READ32(esp) == 0xDEADC0DEu,
                "PASS: shared PUSH32 uses explicit guest write and old-ESP source",
                "FAIL: shared PUSH32 explicit-memory contract");

    POP32(esp, popped);

    ok &= check(esp == 0x008BFFF0u &&
                popped == 0xDEADC0DEu,
                "PASS: shared POP32 uses explicit guest read and restores ESP",
                "FAIL: shared POP32 explicit-memory contract");

    /*
     * XBOX_MEMCPY: aligned dwords followed by byte tail.  This also proves the
     * endian conversion is transparent for raw guest bytes.
     */
    for (i = 0u; i < 11u; ++i)
    {
        RECOMP_WRITE8(0x00020000u + i, (BYTE)(0x30u + i));
        expected[i] = (BYTE)(0x30u + i);
    }

    XBOX_MEMCPY(0x00021000u, 0x00020000u, 11u);

    ok &= check(bytes_equal(0x00021000u, expected, 11u),
                "PASS: XBOX_MEMCPY preserves aligned dwords plus byte tail",
                "FAIL: XBOX_MEMCPY aligned/tail copy");

    /*
     * Unaligned copy must safely fall back to bytes rather than dereferencing
     * an unaligned native pointer.
     */
    for (i = 0u; i < 9u; ++i)
    {
        RECOMP_WRITE8(0x00022001u + i, (BYTE)(0x80u + i));
        expected[i] = (BYTE)(0x80u + i);
    }

    XBOX_MEMCPY(0x00023003u, 0x00022001u, 9u);

    ok &= check(bytes_equal(0x00023003u, expected, 9u),
                "PASS: XBOX_MEMCPY handles unaligned raw-byte copy",
                "FAIL: XBOX_MEMCPY unaligned copy");

    /* REP MOVSB forward non-overlap. */
    for (i = 0u; i < 8u; ++i)
    {
        RECOMP_WRITE8(0x00024000u + i, (BYTE)(i + 1u));
        expected[i] = (BYTE)(i + 1u);
    }

    XBOX_REP_MOVS(0x00024100u, 0x00024000u, 8u, 1u);

    ok &= check(bytes_equal(0x00024100u, expected, 8u),
                "PASS: REP MOVSB helper copies forward bytes",
                "FAIL: REP MOVSB forward copy");

    /*
     * REP MOVSB overlap with destination above source must preserve x86
     * element-at-a-time forward behavior, not memmove semantics.
     */
    RECOMP_WRITE8(0x00025000u, 1u);
    RECOMP_WRITE8(0x00025001u, 2u);
    RECOMP_WRITE8(0x00025002u, 3u);
    RECOMP_WRITE8(0x00025003u, 4u);
    RECOMP_WRITE8(0x00025004u, 5u);
    RECOMP_WRITE8(0x00025005u, 6u);

    XBOX_REP_MOVS(0x00025002u, 0x00025000u, 4u, 1u);

    expected[0] = 1u;
    expected[1] = 2u;
    expected[2] = 1u;
    expected[3] = 2u;
    expected[4] = 1u;
    expected[5] = 2u;

    ok &= check(bytes_equal(0x00025000u, expected, 6u),
                "PASS: REP MOVSB overlapping forward order matches x86",
                "FAIL: REP MOVSB overlap ordering");

    /* REP MOVSW and MOVSD preserve little-endian element values. */
    RECOMP_WRITE16(0x00026001u, 0x1122u);
    RECOMP_WRITE16(0x00026003u, 0x3344u);
    XBOX_REP_MOVS(0x00026101u, 0x00026001u, 2u, 2u);

    ok &= check(RECOMP_READ16(0x00026101u) == 0x1122u &&
                RECOMP_READ16(0x00026103u) == 0x3344u,
                "PASS: REP MOVSW preserves unaligned 16-bit elements",
                "FAIL: REP MOVSW element semantics");

    RECOMP_WRITE32(0x00027001u, 0x11223344u);
    RECOMP_WRITE32(0x00027005u, 0xA1B2C3D4u);
    XBOX_REP_MOVS(0x00027101u, 0x00027001u, 2u, 4u);

    ok &= check(RECOMP_READ32(0x00027101u) == 0x11223344u &&
                RECOMP_READ32(0x00027105u) == 0xA1B2C3D4u,
                "PASS: REP MOVSD preserves unaligned 32-bit elements",
                "FAIL: REP MOVSD element semantics");

    /*
     * Generated-style non-REP string operations emitted in explicit mode.
     */
    esi = 0x00028000u;
    edi = 0x00028100u;
    RECOMP_WRITE32(esi, 0x89ABCDEFu);
    GUEST_WRITE32(edi, GUEST_READ32(esi));
    esi += 4u;
    edi += 4u;

    ok &= check(RECOMP_READ32(0x00028100u) == 0x89ABCDEFu &&
                esi == 0x00028004u &&
                edi == 0x00028104u,
                "PASS: generated-style MOVSD uses explicit guest read/write",
                "FAIL: generated-style MOVSD");

    eax = 0x12345678u;
    edi = 0x00028201u;
    GUEST_WRITE16(edi, LO16(eax));
    edi += 2u;

    ok &= check(RECOMP_READ16(0x00028201u) == 0x5678u &&
                edi == 0x00028203u,
                "PASS: generated-style STOSW uses explicit guest write",
                "FAIL: generated-style STOSW");

    eax = 0xAABBCC00u;
    esi = 0x00028301u;
    RECOMP_WRITE8(esi, 0x5Au);
    SET_LO8(eax, GUEST_READ8(esi));
    ++esi;

    ok &= check(eax == 0xAABBCC5Au &&
                esi == 0x00028302u,
                "PASS: generated-style LODSB uses explicit guest read",
                "FAIL: generated-style LODSB");

    /*
     * Generated-style REP STOSD explicit loop.
     */
    eax = 0xCAFEBABEu;
    edi = 0x00029001u;
    ecx = 3u;

    for (i = 0u; i < ecx; ++i)
        GUEST_WRITE32(edi + i * 4u, eax);

    edi += ecx * 4u;
    ecx = 0u;

    ok &= check(RECOMP_READ32(0x00029001u) == 0xCAFEBABEu &&
                RECOMP_READ32(0x00029005u) == 0xCAFEBABEu &&
                RECOMP_READ32(0x00029009u) == 0xCAFEBABEu &&
                edi == 0x0002900Du &&
                ecx == 0u,
                "PASS: generated-style REP STOSD explicit loop",
                "FAIL: REP STOSD explicit loop");

    /*
     * Generated-style backwards REP MOVSD: source/destination step downward
     * and each element remains an explicit checked 32-bit transfer.
     */
    RECOMP_WRITE32(0x0002A008u, 0x11111111u);
    RECOMP_WRITE32(0x0002A004u, 0x22222222u);
    RECOMP_WRITE32(0x0002A000u, 0x33333333u);

    esi = 0x0002A008u;
    edi = 0x0002A108u;
    ecx = 3u;

    for (i = 0u; i < ecx; ++i)
        GUEST_WRITE32(edi - i * 4u, GUEST_READ32(esi - i * 4u));

    esi -= ecx * 4u;
    edi -= ecx * 4u;
    ecx = 0u;

    ok &= check(RECOMP_READ32(0x0002A108u) == 0x11111111u &&
                RECOMP_READ32(0x0002A104u) == 0x22222222u &&
                RECOMP_READ32(0x0002A100u) == 0x33333333u &&
                esi == 0x00029FFCu &&
                edi == 0x0002A0FCu,
                "PASS: backwards REP MOVSD explicit loop preserves direction",
                "FAIL: backwards REP MOVSD");

    /*
     * Generated-style CMPSW / SCASB memory reads.
     */
    RECOMP_WRITE16(0x0002B000u, 0x55AAu);
    RECOMP_WRITE16(0x0002B100u, 0x55AAu);

    ok &= check(GUEST_READ16(0x0002B000u) ==
                GUEST_READ16(0x0002B100u),
                "PASS: CMPSW-style explicit memory comparison",
                "FAIL: CMPSW-style explicit reads");

    eax = 0x1234007Fu;
    RECOMP_WRITE8(0x0002B200u, 0x7Fu);

    ok &= check(LO8(eax) == GUEST_READ8(0x0002B200u),
                "PASS: SCASB-style explicit memory comparison",
                "FAIL: SCASB-style explicit read");

    /* Runtime helper remains coherent through RAM mirrors and KSEG aliases. */
    RECOMP_WRITE32(0x0402C000u, 0x0BADF00Du);

    ok &= check(RECOMP_READ32(0x0002C000u) == 0x0BADF00Du,
                "PASS: runtime memory bridge coherent through RAM mirror",
                "FAIL: runtime RAM mirror coherence");

    RECOMP_WRITE32(0x8123C000u, 0x13579BDFu);

    ok &= check(RECOMP_READ32(0x0123C000u) == 0x13579BDFu,
                "PASS: runtime memory bridge coherent through KSEG0",
                "FAIL: runtime KSEG0 coherence");

    /* One scalar-width access still may not cross a 64 MiB window. */
    s_fault = 0;
    (void)RECOMP_READ32(0x03FFFFFFu);

    ok &= check(s_fault != 0,
                "PASS: runtime scalar bridge rejects cross-64MiB dword",
                "FAIL: runtime scalar bridge crossed RAM window");

    /*
     * String/copy helpers are sequences of individual x86 memory accesses.
     * Advancing into the next mapped mirror is therefore valid.
     */
    RECOMP_WRITE8(0x03FFFFFEu, 0xA1u);
    RECOMP_WRITE8(0x03FFFFFFu, 0xB2u);
    RECOMP_WRITE8(0x00000000u, 0xC3u);
    RECOMP_WRITE8(0x00000001u, 0xD4u);
    s_fault = 0;

    XBOX_MEMCPY(0x0002D000u, 0x03FFFFFEu, 4u);

    expected[0] = 0xA1u;
    expected[1] = 0xB2u;
    expected[2] = 0xC3u;
    expected[3] = 0xD4u;

    ok &= check(!s_fault &&
                bytes_equal(0x0002D000u, expected, 4u),
                "PASS: XBOX_MEMCPY advances element-wise into mapped RAM mirror",
                "FAIL: XBOX_MEMCPY mirror-boundary sequence");

    s_fault = 0;
    XBOX_REP_MOVS(0x0002E000u, 0xFD001000u, 1u, 4u);

    ok &= check(s_fault != 0,
                "PASS: XBOX_REP_MOVS rejects NV2A MMIO as ordinary RAM",
                "FAIL: XBOX_REP_MOVS MMIO rejection");

    s_fault = 0;
    return ok;
}

VOID __cdecl main()
{
    int result = 0;
    DWORD started;
    DWORD nextHeartbeat = 1000u;

    s_logFile = CreateFileA(
        "game:\\merc360-phase3d-runtime-memory.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 3D EXPLICIT RUNTIME/STRING MEMORY ABI START");
    trace("BUILD TAG: P3D-RUNTIME-20261018-A");
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
        trace("PHASE 3D RUNTIME MEMORY ABI RESULT: PASS");
    else
        trace("PHASE 3D RUNTIME MEMORY ABI RESULT: FAIL");

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

    trace("PHASE 3D EXPLICIT RUNTIME/STRING MEMORY ABI END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

/*
 * Mercenaries Xbox 360 - Phase 3E first bounded translated function.
 *
 * This file is a TEMPLATE. Prepare-Phase3E.ps1 locally lifts the reviewed
 * retail function at 0x00208F30 from the user's own verified default.xbe and
 * injects it at the marker below into build\phase3e_first_translated\main.cpp.
 *
 * No retail-derived generated function body is committed to this repository.
 */

#include <xtl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Old XDK/MSVC-compatible fixed-width aliases for generated C. */
typedef unsigned char      uint8_t;
typedef signed char        int8_t;
typedef unsigned short     uint16_t;
typedef signed short       int16_t;
typedef unsigned int       uint32_t;
typedef signed int         int32_t;
typedef unsigned __int64   uint64_t;
typedef __int64            int64_t;

#define RAM_SIZE        0x04000000u
#define RAM_MASK        0x03FFFFFFu
#define MIRROR_END      0x74000000u
#define KSEG_BASE       0x80000000u
#define KSEG_END        0xC0000000u
#define FENCE_BASE      0x80000000u
#define FENCE_END       0x80001000u
#define KERNEL_BASE     0x80010000u
#define KERNEL_END      0x80011000u

#define PHASE3E_FUNCTION_VA 0x00208F30u
#define PHASE3E_OBJECT_VA   0x00030000u
#define PHASE3E_STACK_TOP   0x008BFFF0u

static BYTE* g_ram = NULL;
static HANDLE s_logFile = INVALID_HANDLE_VALUE;
static int s_accessFault = 0;
static DWORD s_lastTranslatedFunction = 0u;

/* Architectural register state used by mechanically translated functions. */
uint32_t g_eax = 0u;
uint32_t g_ecx = 0u;
uint32_t g_edx = 0u;
uint32_t g_esp = 0u;
uint32_t g_ebx = 0u;
uint32_t g_esi = 0u;
uint32_t g_edi = 0u;
uint32_t g_seh_ebp = 0u;

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

#define RECOMP_TRACE_FUNC(va) do { s_lastTranslatedFunction = (DWORD)(va); } while (0)

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P3E] ");
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

/* The locally generated retail-derived function is injected here. */
/*__PHASE3E_GENERATED_FUNCTION__*/

static BYTE reference_accessor(BYTE value)
{
    return (BYTE)(value & 1u);
}

static int run_one_case(BYTE value)
{
    BYTE before;
    BYTE after;
    BYTE expected;
    BYTE actual;
    char line[192];

    s_accessFault = 0;
    s_lastTranslatedFunction = 0u;

    GUEST_WRITE8(PHASE3E_OBJECT_VA + 0x14u, value);
    before = GUEST_READ8(PHASE3E_OBJECT_VA + 0x14u);

    g_eax = 0xA5A5A5A5u;
    g_ecx = PHASE3E_OBJECT_VA;
    g_edx = 0xD2D2D2D2u;
    g_ebx = 0xB3B3B3B3u;
    g_esi = 0x51515151u;
    g_edi = 0xD1D1D1D1u;
    g_seh_ebp = 0u;

    /*
     * A translated x86 CALL would have pushed a return address before entering
     * the function.  Supply a harmless dummy slot so its translated RET can
     * consume exactly four guest-stack bytes.
     */
    g_esp = PHASE3E_STACK_TOP - 4u;
    GUEST_WRITE32(g_esp, 0xDEADC0DEu);

    expected = reference_accessor(value);

    sub_00208F30();

    actual = LO8(g_eax);
    after = GUEST_READ8(PHASE3E_OBJECT_VA + 0x14u);

    sprintf(line,
            "CASE input=%02X expected=%u actual=%u eax=%08X esp=%08X",
            (unsigned int)value,
            (unsigned int)expected,
            (unsigned int)actual,
            (unsigned int)g_eax,
            (unsigned int)g_esp);
    trace(line);

    if (s_accessFault)
    {
        trace("FAIL: translated function triggered guest-memory access fault");
        return 0;
    }

    if (s_lastTranslatedFunction != PHASE3E_FUNCTION_VA)
    {
        trace("FAIL: translated function trace VA mismatch");
        return 0;
    }

    if (actual != expected)
    {
        trace("FAIL: translated result differs from independent reference");
        return 0;
    }

    if (before != after)
    {
        trace("FAIL: read-only accessor mutated guest object state");
        return 0;
    }

    if (g_esp != PHASE3E_STACK_TOP)
    {
        trace("FAIL: translated RET did not consume exactly four guest-stack bytes");
        return 0;
    }

    trace("PASS: translated case matches reference and preserves guest state");
    return 1;
}

static int run_fixture(void)
{
    static const BYTE kCases[] = {
        0x00u, 0x01u, 0x02u, 0x03u, 0xFEu, 0xFFu
    };

    int ok = 1;
    DWORD i;

    for (i = 0u; i < (DWORD)(sizeof(kCases) / sizeof(kCases[0])); ++i)
        ok &= run_one_case(kCases[i]);

    ok &= check(
        GUEST_READ8(PHASE3E_OBJECT_VA + 0x14u) == 0xFFu,
        "PASS: final guest object byte remains the last supplied input",
        "FAIL: final guest object byte changed unexpectedly");

    return ok;
}

VOID __cdecl main()
{
    int result = 0;
    DWORD started;
    DWORD nextHeartbeat = 1000u;

    s_logFile = CreateFileA(
        "game:\\merc360-phase3e-first-translated.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 3E FIRST BOUNDED TRANSLATED FUNCTION START");
    trace("BUILD TAG: P3E-FIRSTFUNC-20261018-A");
    trace("Translated retail function VA: 0x00208F30");
    trace("Reference contract: return low bit of byte at ECX+0x14");

    g_ram = (BYTE*)malloc(RAM_SIZE);

    if (!g_ram)
    {
        trace("FATAL: could not allocate 64 MiB guest RAM");
        goto wait_for_exit;
    }

    memset(g_ram, 0, RAM_SIZE);

    result = run_fixture();

    if (result)
        trace("PHASE 3E FIRST TRANSLATED FUNCTION RESULT: PASS");
    else
        trace("PHASE 3E FIRST TRANSLATED FUNCTION RESULT: FAIL");

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

    trace("PHASE 3E FIRST BOUNDED TRANSLATED FUNCTION END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

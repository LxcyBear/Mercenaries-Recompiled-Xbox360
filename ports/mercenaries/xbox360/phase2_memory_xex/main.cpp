/*
 * Mercenaries Xbox 360 - Phase 2A guest-memory diagnostic.
 *
 * SELF-CONTAINED XDK TEST:
 *   - no guest_memory.h
 *   - no guest_endian.h
 *   - no additional include directories
 *
 * This does NOT load or execute Mercenaries yet.
 * It proves a bounded 64 MiB original-Xbox guest RAM arena and explicit
 * little-endian access semantics on the Xbox 360's Xenon CPU.
 */

#include <xtl.h>
#include <stdlib.h>
#include <string.h>

#define MERC_GUEST_RAM_SIZE (64u * 1024u * 1024u)

typedef struct MercGuestMemory
{
    BYTE* base;
    DWORD size;
} MercGuestMemory;

static HANDLE s_logFile = INVALID_HANDLE_VALUE;

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P2] ");
    OutputDebugStringA(line);
    OutputDebugStringA("\r\n");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        WriteFile(s_logFile, line, length, &written, NULL);
        WriteFile(s_logFile, "\r\n", 2, &written, NULL);
        FlushFileBuffers(s_logFile);
    }
}

static WORD guest_read_le16(const void* address)
{
    const BYTE* p = (const BYTE*)address;
    return (WORD)((WORD)p[0] | ((WORD)p[1] << 8));
}

static DWORD guest_read_le32(const void* address)
{
    const BYTE* p = (const BYTE*)address;
    return ((DWORD)p[0]) |
           ((DWORD)p[1] << 8) |
           ((DWORD)p[2] << 16) |
           ((DWORD)p[3] << 24);
}

static unsigned __int64 guest_read_le64(const void* address)
{
    const BYTE* p = (const BYTE*)address;
    return (unsigned __int64)guest_read_le32(p) |
           ((unsigned __int64)guest_read_le32(p + 4) << 32);
}

static void guest_write_le16(void* address, WORD value)
{
    BYTE* p = (BYTE*)address;
    p[0] = (BYTE)value;
    p[1] = (BYTE)(value >> 8);
}

static void guest_write_le32(void* address, DWORD value)
{
    BYTE* p = (BYTE*)address;
    p[0] = (BYTE)value;
    p[1] = (BYTE)(value >> 8);
    p[2] = (BYTE)(value >> 16);
    p[3] = (BYTE)(value >> 24);
}

static void guest_write_le64(void* address, unsigned __int64 value)
{
    BYTE* p = (BYTE*)address;
    guest_write_le32(p, (DWORD)value);
    guest_write_le32(p + 4, (DWORD)(value >> 32));
}

static float guest_read_le_float32(const void* address)
{
    DWORD bits = guest_read_le32(address);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static void guest_write_le_float32(void* address, float value)
{
    DWORD bits;
    memcpy(&bits, &value, sizeof(bits));
    guest_write_le32(address, bits);
}

static int guest_memory_init(MercGuestMemory* memory, DWORD size)
{
    if (!memory || size == 0)
        return 0;

    memory->base = (BYTE*)malloc((size_t)size);
    if (!memory->base)
    {
        memory->size = 0;
        return 0;
    }

    memory->size = size;
    memset(memory->base, 0, (size_t)size);
    return 1;
}

static void guest_memory_shutdown(MercGuestMemory* memory)
{
    if (!memory)
        return;

    if (memory->base)
        free(memory->base);

    memory->base = NULL;
    memory->size = 0;
}

static void* guest_memory_ptr(MercGuestMemory* memory,
                              DWORD address,
                              DWORD width)
{
    if (!memory || !memory->base || width == 0)
        return NULL;

    if (address >= memory->size)
        return NULL;

    if (width > memory->size - address)
        return NULL;

    return memory->base + address;
}

static const void* guest_memory_cptr(const MercGuestMemory* memory,
                                     DWORD address,
                                     DWORD width)
{
    if (!memory || !memory->base || width == 0)
        return NULL;

    if (address >= memory->size)
        return NULL;

    if (width > memory->size - address)
        return NULL;

    return memory->base + address;
}

static int guest_memory_write8(MercGuestMemory* memory,
                               DWORD address,
                               BYTE value)
{
    BYTE* p = (BYTE*)guest_memory_ptr(memory, address, 1);
    if (!p)
        return 0;

    *p = value;
    return 1;
}

static int guest_memory_write16(MercGuestMemory* memory,
                                DWORD address,
                                WORD value)
{
    void* p = guest_memory_ptr(memory, address, 2);
    if (!p)
        return 0;

    guest_write_le16(p, value);
    return 1;
}

static int guest_memory_write32(MercGuestMemory* memory,
                                DWORD address,
                                DWORD value)
{
    void* p = guest_memory_ptr(memory, address, 4);
    if (!p)
        return 0;

    guest_write_le32(p, value);
    return 1;
}

static int guest_memory_write64(MercGuestMemory* memory,
                                DWORD address,
                                unsigned __int64 value)
{
    void* p = guest_memory_ptr(memory, address, 8);
    if (!p)
        return 0;

    guest_write_le64(p, value);
    return 1;
}

static int guest_memory_write_float32(MercGuestMemory* memory,
                                      DWORD address,
                                      float value)
{
    void* p = guest_memory_ptr(memory, address, 4);
    if (!p)
        return 0;

    guest_write_le_float32(p, value);
    return 1;
}

static int guest_memory_read8(const MercGuestMemory* memory,
                              DWORD address,
                              BYTE* value)
{
    const BYTE* p = (const BYTE*)guest_memory_cptr(memory, address, 1);
    if (!p || !value)
        return 0;

    *value = *p;
    return 1;
}

static int guest_memory_read16(const MercGuestMemory* memory,
                               DWORD address,
                               WORD* value)
{
    const void* p = guest_memory_cptr(memory, address, 2);
    if (!p || !value)
        return 0;

    *value = guest_read_le16(p);
    return 1;
}

static int guest_memory_read32(const MercGuestMemory* memory,
                               DWORD address,
                               DWORD* value)
{
    const void* p = guest_memory_cptr(memory, address, 4);
    if (!p || !value)
        return 0;

    *value = guest_read_le32(p);
    return 1;
}

static int guest_memory_read64(const MercGuestMemory* memory,
                               DWORD address,
                               unsigned __int64* value)
{
    const void* p = guest_memory_cptr(memory, address, 8);
    if (!p || !value)
        return 0;

    *value = guest_read_le64(p);
    return 1;
}

static int guest_memory_read_float32(const MercGuestMemory* memory,
                                     DWORD address,
                                     float* value)
{
    const void* p = guest_memory_cptr(memory, address, 4);
    if (!p || !value)
        return 0;

    *value = guest_read_le_float32(p);
    return 1;
}

static int check(int condition,
                 const char* passText,
                 const char* failText)
{
    if (condition)
    {
        trace(passText);
        return 1;
    }

    trace(failText);
    return 0;
}

static int run_guest_memory_tests(MercGuestMemory* memory)
{
    int ok = 1;
    BYTE v8 = 0;
    WORD v16 = 0;
    DWORD v32 = 0;
    unsigned __int64 v64 = 0;
    float vf = 0.0f;

    DWORD native = 0x01020304u;
    const BYTE* nativeBytes = (const BYTE*)&native;

    if (nativeBytes[0] == 0x01 &&
        nativeBytes[1] == 0x02 &&
        nativeBytes[2] == 0x03 &&
        nativeBytes[3] == 0x04)
    {
        trace("HOST BYTE ORDER: BIG-ENDIAN (expected Xenon)");
    }
    else if (nativeBytes[0] == 0x04 &&
             nativeBytes[1] == 0x03 &&
             nativeBytes[2] == 0x02 &&
             nativeBytes[3] == 0x01)
    {
        trace("HOST BYTE ORDER: LITTLE-ENDIAN (unexpected for Xenon)");
    }
    else
    {
        trace("HOST BYTE ORDER: UNKNOWN");
    }

    ok &= check(memory &&
                memory->base &&
                memory->size == MERC_GUEST_RAM_SIZE,
                "PASS: 64 MiB guest arena allocated",
                "FAIL: 64 MiB guest arena unavailable or wrong size");

    ok &= check(guest_memory_write8(memory, 0u, 0xA5u),
                "PASS: low-address byte write",
                "FAIL: low-address byte write");

    ok &= check(guest_memory_read8(memory, 0u, &v8) &&
                v8 == 0xA5u,
                "PASS: low-address byte readback",
                "FAIL: low-address byte readback");

    ok &= check(guest_memory_write16(memory, 2u, 0xBEEFu),
                "PASS: 16-bit guest write",
                "FAIL: 16-bit guest write");

    ok &= check(guest_memory_read16(memory, 2u, &v16) &&
                v16 == 0xBEEFu,
                "PASS: 16-bit guest readback",
                "FAIL: 16-bit guest readback");

    ok &= check(guest_memory_write32(memory,
                                    0x00010000u,
                                    0x12345678u),
                "PASS: XBE-base 32-bit guest write",
                "FAIL: XBE-base 32-bit guest write");

    ok &= check(memory->base[0x00010000u] == 0x78u &&
                memory->base[0x00010001u] == 0x56u &&
                memory->base[0x00010002u] == 0x34u &&
                memory->base[0x00010003u] == 0x12u,
                "PASS: XBE-base bytes are little-endian in RAM",
                "FAIL: XBE-base byte representation is not little-endian");

    ok &= check(guest_memory_read32(memory,
                                   0x00010000u,
                                   &v32) &&
                v32 == 0x12345678u,
                "PASS: XBE-base 32-bit guest readback",
                "FAIL: XBE-base 32-bit guest readback");

    ok &= check(guest_memory_write32(memory,
                                    0x00010003u,
                                    0x89ABCDEFu),
                "PASS: unaligned 32-bit guest write",
                "FAIL: unaligned 32-bit guest write");

    ok &= check(memory->base[0x00010003u] == 0xEFu &&
                memory->base[0x00010004u] == 0xCDu &&
                memory->base[0x00010005u] == 0xABu &&
                memory->base[0x00010006u] == 0x89u,
                "PASS: unaligned bytes remain little-endian",
                "FAIL: unaligned byte representation");

    ok &= check(guest_memory_read32(memory,
                                   0x00010003u,
                                   &v32) &&
                v32 == 0x89ABCDEFu,
                "PASS: unaligned 32-bit guest readback",
                "FAIL: unaligned 32-bit guest readback");

    ok &= check(guest_memory_write_float32(memory,
                                          0x00012345u,
                                          1.0f),
                "PASS: unaligned guest float write",
                "FAIL: unaligned guest float write");

    ok &= check(memory->base[0x00012345u] == 0x00u &&
                memory->base[0x00012346u] == 0x00u &&
                memory->base[0x00012347u] == 0x80u &&
                memory->base[0x00012348u] == 0x3Fu,
                "PASS: float bytes are IEEE-754 little-endian",
                "FAIL: float byte representation");

    ok &= check(guest_memory_read_float32(memory,
                                         0x00012345u,
                                         &vf) &&
                vf == 1.0f,
                "PASS: guest float readback",
                "FAIL: guest float readback");

    ok &= check(guest_memory_write64(memory,
                                    MERC_GUEST_RAM_SIZE - 8u,
                                    0x0102030405060708ui64),
                "PASS: last valid 64-bit guest write",
                "FAIL: last valid 64-bit guest write");

    ok &= check(guest_memory_read64(memory,
                                   MERC_GUEST_RAM_SIZE - 8u,
                                   &v64) &&
                v64 == 0x0102030405060708ui64,
                "PASS: last valid 64-bit guest readback",
                "FAIL: last valid 64-bit guest readback");

    ok &= check(guest_memory_write16(memory,
                                    MERC_GUEST_RAM_SIZE - 2u,
                                    0xBEEFu),
                "PASS: last valid 16-bit guest write",
                "FAIL: last valid 16-bit guest write");

    ok &= check(guest_memory_read16(memory,
                                   MERC_GUEST_RAM_SIZE - 2u,
                                   &v16) &&
                v16 == 0xBEEFu,
                "PASS: last valid 16-bit guest readback",
                "FAIL: last valid 16-bit guest readback");

    ok &= check(!guest_memory_write32(memory,
                                     MERC_GUEST_RAM_SIZE - 2u,
                                     0xDEADBEEFu),
                "PASS: crossing upper bound rejected",
                "FAIL: crossing upper bound was NOT rejected");

    ok &= check(!guest_memory_read32(memory,
                                    MERC_GUEST_RAM_SIZE,
                                    &v32),
                "PASS: first out-of-range address rejected",
                "FAIL: first out-of-range address was NOT rejected");

    ok &= check(!guest_memory_write8(memory,
                                    0xFFFFFFFFu,
                                    0x11u),
                "PASS: wrapped/high address rejected",
                "FAIL: wrapped/high address was NOT rejected");

    return ok;
}

VOID __cdecl main()
{
    MercGuestMemory memory;
    int passed = 0;
    DWORD started;
    DWORD nextHeartbeat = 1000u;

    ZeroMemory(&memory, sizeof(memory));

    s_logFile = CreateFileA(
        "game:\\merc360-phase2-memory.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 2A GUEST MEMORY DIAGNOSTIC START");
    trace("Allocating and clearing 64 MiB low guest RAM arena");

    if (!guest_memory_init(&memory, MERC_GUEST_RAM_SIZE))
    {
        trace("FATAL: 64 MiB guest arena allocation failed");
        goto done;
    }

    passed = run_guest_memory_tests(&memory);

    if (passed)
        trace("PHASE 2 MEMORY TEST RESULT: PASS");
    else
        trace("PHASE 2 MEMORY TEST RESULT: FAIL");

    guest_memory_shutdown(&memory);
    trace("Guest arena released");

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

done:
    if (memory.base)
    {
        guest_memory_shutdown(&memory);
        trace("Guest arena released during cleanup");
    }

    trace("PHASE 2A GUEST MEMORY DIAGNOSTIC END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

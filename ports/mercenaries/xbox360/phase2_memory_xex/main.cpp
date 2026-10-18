/*
 * Mercenaries Xbox 360 - Phase 2 guest-memory diagnostic.
 *
 * This does NOT load or execute Mercenaries yet.
 * It proves the low 64 MiB original-Xbox guest RAM contract on real Xenon:
 * allocation, host byte order, explicit little-endian guest accesses,
 * unaligned accesses and bounds rejection.
 */

#include <xtl.h>
#include <string.h>
#include "../include/guest_memory.h"

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

static int run_guest_memory_tests(MercGuestMemory* memory)
{
    int ok = 1;
    uint32_t v32 = 0;
    uint64_t v64 = 0;
    uint16_t v16 = 0;
    float vf = 0.0f;
    uint8_t v8 = 0;
    uint32_t native = 0x01020304u;
    const uint8_t* nativeBytes = (const uint8_t*)&native;

    if (nativeBytes[0] == 0x01 && nativeBytes[1] == 0x02 &&
        nativeBytes[2] == 0x03 && nativeBytes[3] == 0x04)
        trace("HOST BYTE ORDER: BIG-ENDIAN (expected Xenon)");
    else if (nativeBytes[0] == 0x04 && nativeBytes[1] == 0x03 &&
             nativeBytes[2] == 0x02 && nativeBytes[3] == 0x01)
        trace("HOST BYTE ORDER: LITTLE-ENDIAN (unexpected for Xenon)");
    else
        trace("HOST BYTE ORDER: UNKNOWN");

    ok &= check(memory && memory->base && memory->size == MERC_GUEST_RAM_SIZE,
                "PASS: 64 MiB guest arena allocated",
                "FAIL: 64 MiB guest arena unavailable or wrong size");

    ok &= check(merc_guest_memory_write8(memory, 0u, 0xA5u),
                "PASS: low-address byte write",
                "FAIL: low-address byte write");
    ok &= check(merc_guest_memory_read8(memory, 0u, &v8) && v8 == 0xA5u,
                "PASS: low-address byte readback",
                "FAIL: low-address byte readback");

    ok &= check(merc_guest_memory_write32(memory, 0x00010000u, 0x12345678u),
                "PASS: XBE-base 32-bit guest write",
                "FAIL: XBE-base 32-bit guest write");
    ok &= check(memory->base[0x00010000u] == 0x78u &&
                memory->base[0x00010001u] == 0x56u &&
                memory->base[0x00010002u] == 0x34u &&
                memory->base[0x00010003u] == 0x12u,
                "PASS: XBE-base bytes are little-endian in RAM",
                "FAIL: XBE-base byte representation is not little-endian");
    ok &= check(merc_guest_memory_read32(memory, 0x00010000u, &v32) &&
                v32 == 0x12345678u,
                "PASS: XBE-base 32-bit guest readback",
                "FAIL: XBE-base 32-bit guest readback");

    ok &= check(merc_guest_memory_write32(memory, 0x00010003u, 0x89ABCDEFu),
                "PASS: unaligned 32-bit guest write",
                "FAIL: unaligned 32-bit guest write");
    ok &= check(memory->base[0x00010003u] == 0xEFu &&
                memory->base[0x00010004u] == 0xCDu &&
                memory->base[0x00010005u] == 0xABu &&
                memory->base[0x00010006u] == 0x89u,
                "PASS: unaligned bytes remain little-endian",
                "FAIL: unaligned byte representation");
    ok &= check(merc_guest_memory_read32(memory, 0x00010003u, &v32) &&
                v32 == 0x89ABCDEFu,
                "PASS: unaligned 32-bit guest readback",
                "FAIL: unaligned 32-bit guest readback");

    ok &= check(merc_guest_memory_write_float32(memory, 0x00012345u, 1.0f),
                "PASS: unaligned guest float write",
                "FAIL: unaligned guest float write");
    ok &= check(memory->base[0x00012345u] == 0x00u &&
                memory->base[0x00012346u] == 0x00u &&
                memory->base[0x00012347u] == 0x80u &&
                memory->base[0x00012348u] == 0x3Fu,
                "PASS: float bytes are IEEE-754 little-endian",
                "FAIL: float byte representation");
    ok &= check(merc_guest_memory_read_float32(memory, 0x00012345u, &vf) &&
                vf == 1.0f,
                "PASS: guest float readback",
                "FAIL: guest float readback");

    ok &= check(merc_guest_memory_write64(memory,
                MERC_GUEST_RAM_SIZE - 8u, 0x0102030405060708ULL),
                "PASS: last valid 64-bit guest write",
                "FAIL: last valid 64-bit guest write");
    ok &= check(merc_guest_memory_read64(memory,
                MERC_GUEST_RAM_SIZE - 8u, &v64) &&
                v64 == 0x0102030405060708ULL,
                "PASS: last valid 64-bit guest readback",
                "FAIL: last valid 64-bit guest readback");

    ok &= check(merc_guest_memory_write16(memory,
                MERC_GUEST_RAM_SIZE - 2u, 0xBEEFu),
                "PASS: last valid 16-bit guest write",
                "FAIL: last valid 16-bit guest write");
    ok &= check(merc_guest_memory_read16(memory,
                MERC_GUEST_RAM_SIZE - 2u, &v16) && v16 == 0xBEEFu,
                "PASS: last valid 16-bit guest readback",
                "FAIL: last valid 16-bit guest readback");

    ok &= check(!merc_guest_memory_write32(memory,
                MERC_GUEST_RAM_SIZE - 2u, 0xDEADBEEFu),
                "PASS: crossing upper bound rejected",
                "FAIL: crossing upper bound was NOT rejected");
    ok &= check(!merc_guest_memory_read32(memory,
                MERC_GUEST_RAM_SIZE, &v32),
                "PASS: first out-of-range address rejected",
                "FAIL: first out-of-range address was NOT rejected");
    ok &= check(!merc_guest_memory_write8(memory, 0xFFFFFFFFu, 0x11u),
                "PASS: wrapped/high address rejected",
                "FAIL: wrapped/high address was NOT rejected");

    return ok;
}

VOID __cdecl main()
{
    MercGuestMemory memory;
    int passed;
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

    trace("PHASE 2 GUEST MEMORY DIAGNOSTIC START");
    trace("Allocating and clearing 64 MiB low guest RAM arena");

    if (!merc_guest_memory_init(&memory, MERC_GUEST_RAM_SIZE))
    {
        trace("FATAL: 64 MiB guest arena allocation failed");
        goto done;
    }

    passed = run_guest_memory_tests(&memory);

    if (passed)
        trace("PHASE 2 MEMORY TEST RESULT: PASS");
    else
        trace("PHASE 2 MEMORY TEST RESULT: FAIL");

    merc_guest_memory_shutdown(&memory);
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
    trace("PHASE 2 GUEST MEMORY DIAGNOSTIC END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

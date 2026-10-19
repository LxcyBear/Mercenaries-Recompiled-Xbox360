/*
 * Mercenaries Xbox 360 - Phase 4B-C guest memory/protection hardware gate.
 *
 * SELF-CONTAINED XDK TEST.
 * This does not execute Mercenaries. It proves the guest-owned semantics used
 * to replace the final two direct host-backed retail import paths:
 *   - NtFreeVirtualMemory
 *   - MmSetAddressProtect
 *
 * The translated runtime owns one bounded guest RAM arena. Therefore guest
 * release/decommit/protection state must be modeled in guest metadata instead
 * of applying VirtualFree/VirtualProtect to translated native pointers.
 */

#include <xtl.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>

#define P4C_BUILD_TAG "P4B-MEMPROT-20261019-B"

#define GUEST_ARENA_SIZE   (1024u * 1024u)
#define GUEST_PAGE_SIZE    4096u
#define GUEST_PAGE_COUNT   (GUEST_ARENA_SIZE / GUEST_PAGE_SIZE)
#define GUEST_VA_BASE      0x01000000u
#define MAX_BLOCKS         64

#define GUEST_MEM_COMMIT   0x1000u
#define GUEST_MEM_RESERVE  0x2000u
#define GUEST_MEM_DECOMMIT 0x4000u
#define GUEST_MEM_RELEASE  0x8000u

#define GUEST_PAGE_NOACCESS          0x01u
#define GUEST_PAGE_READONLY          0x02u
#define GUEST_PAGE_READWRITE         0x04u
#define GUEST_PAGE_EXECUTE_READWRITE 0x40u

typedef struct GuestBlock
{
    DWORD va;
    DWORD size;
    BOOL inUse;
} GuestBlock;

typedef struct GuestArena
{
    BYTE* bytes;
    DWORD next;
    GuestBlock blocks[MAX_BLOCKS];
    BYTE protection[GUEST_PAGE_COUNT];
    BYTE committed[GUEST_PAGE_COUNT];
} GuestArena;

static HANDLE s_logFile = INVALID_HANDLE_VALUE;
static int s_failures = 0;

static void trace_line(const char* line)
{
    DWORD written = 0;

    OutputDebugStringA("[Merc360:P4B-MEM] ");
    OutputDebugStringA(line);
    OutputDebugStringA("\r\n");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        WriteFile(s_logFile, line, (DWORD)strlen(line), &written, NULL);
        WriteFile(s_logFile, "\r\n", 2, &written, NULL);
        FlushFileBuffers(s_logFile);
    }
}

static void tracef(const char* fmt, ...)
{
    char buffer[512];
    va_list args;

    va_start(args, fmt);
    _vsnprintf(buffer, sizeof(buffer) - 1, fmt, args);
    va_end(args);
    buffer[sizeof(buffer) - 1] = '\0';
    trace_line(buffer);
}

static void check_result(BOOL condition, const char* name)
{
    if (condition)
        tracef("PASS: %s", name);
    else
    {
        tracef("FAIL: %s", name);
        ++s_failures;
    }
}

static DWORD align_up(DWORD value, DWORD alignment)
{
    return (value + alignment - 1u) & ~(alignment - 1u);
}

static BOOL guest_range(
    DWORD va,
    DWORD size,
    DWORD* firstPage,
    DWORD* lastPage)
{
    DWORD offset;
    DWORD endOffset;

    if (size == 0 || va < GUEST_VA_BASE)
        return FALSE;

    offset = va - GUEST_VA_BASE;
    if (offset >= GUEST_ARENA_SIZE ||
        size > GUEST_ARENA_SIZE - offset)
        return FALSE;

    endOffset = offset + size - 1u;
    if (firstPage)
        *firstPage = offset / GUEST_PAGE_SIZE;
    if (lastPage)
        *lastPage = endOffset / GUEST_PAGE_SIZE;
    return TRUE;
}

static void arena_init(GuestArena* arena)
{
    DWORD i;

    ZeroMemory(arena, sizeof(*arena));
    arena->bytes = (BYTE*)malloc(GUEST_ARENA_SIZE);
    if (!arena->bytes)
        return;

    memset(arena->bytes, 0, GUEST_ARENA_SIZE);
    arena->next = 0;

    for (i = 0; i < GUEST_PAGE_COUNT; ++i)
    {
        arena->protection[i] = GUEST_PAGE_READWRITE;
        arena->committed[i] = 1;
    }
}

static void arena_shutdown(GuestArena* arena)
{
    if (!arena)
        return;
    if (arena->bytes)
        free(arena->bytes);
    ZeroMemory(arena, sizeof(*arena));
}

static GuestBlock* find_block(GuestArena* arena, DWORD va)
{
    int i;
    for (i = 0; i < MAX_BLOCKS; ++i)
    {
        if (arena->blocks[i].inUse &&
            arena->blocks[i].va == va)
            return &arena->blocks[i];
    }
    return NULL;
}

static DWORD guest_alloc(GuestArena* arena, DWORD requested)
{
    DWORD size = align_up(requested, GUEST_PAGE_SIZE);
    int i;

    if (!arena || !arena->bytes || requested == 0)
        return 0;

    for (i = 0; i < MAX_BLOCKS; ++i)
    {
        GuestBlock* block = &arena->blocks[i];
        if (!block->inUse && block->size >= size && block->va != 0)
        {
            DWORD firstPage, lastPage, p;
            block->inUse = TRUE;
            memset(
                arena->bytes + (block->va - GUEST_VA_BASE),
                0,
                block->size);
            guest_range(block->va, block->size, &firstPage, &lastPage);
            for (p = firstPage; p <= lastPage; ++p)
            {
                arena->committed[p] = 1;
                arena->protection[p] = GUEST_PAGE_READWRITE;
            }
            return block->va;
        }
    }

    if (size > GUEST_ARENA_SIZE - arena->next)
        return 0;

    for (i = 0; i < MAX_BLOCKS; ++i)
    {
        if (arena->blocks[i].va == 0)
        {
            DWORD va = GUEST_VA_BASE + arena->next;
            arena->blocks[i].va = va;
            arena->blocks[i].size = size;
            arena->blocks[i].inUse = TRUE;
            arena->next += size;
            return va;
        }
    }

    return 0;
}

static BOOL guest_release(
    GuestArena* arena,
    DWORD* baseAddress,
    DWORD* regionSize)
{
    GuestBlock* block;
    DWORD firstPage, lastPage, p;

    if (!arena || !baseAddress || *baseAddress == 0)
        return FALSE;

    block = find_block(arena, *baseAddress);
    if (!block)
        return FALSE;

    if (!guest_range(block->va, block->size, &firstPage, &lastPage))
        return FALSE;

    for (p = firstPage; p <= lastPage; ++p)
    {
        arena->committed[p] = 0;
        arena->protection[p] = GUEST_PAGE_NOACCESS;
    }

    memset(
        arena->bytes + (block->va - GUEST_VA_BASE),
        0xDD,
        block->size);

    block->inUse = FALSE;
    *baseAddress = 0;
    if (regionSize)
        *regionSize = 0;
    return TRUE;
}

static BOOL guest_decommit(
    GuestArena* arena,
    DWORD va,
    DWORD size)
{
    DWORD firstPage, lastPage, p;

    if (!arena || !arena->bytes ||
        !guest_range(va, size, &firstPage, &lastPage))
        return FALSE;

    for (p = firstPage; p <= lastPage; ++p)
    {
        arena->committed[p] = 0;
        arena->protection[p] = GUEST_PAGE_NOACCESS;
        memset(
            arena->bytes + p * GUEST_PAGE_SIZE,
            0,
            GUEST_PAGE_SIZE);
    }
    return TRUE;
}

static BOOL guest_commit(
    GuestArena* arena,
    DWORD va,
    DWORD size,
    BYTE protection)
{
    DWORD firstPage, lastPage, p;

    if (!arena || !arena->bytes ||
        !guest_range(va, size, &firstPage, &lastPage))
        return FALSE;

    for (p = firstPage; p <= lastPage; ++p)
    {
        arena->committed[p] = 1;
        arena->protection[p] = protection;
    }
    return TRUE;
}

static BOOL guest_set_protection(
    GuestArena* arena,
    DWORD va,
    DWORD size,
    BYTE protection)
{
    DWORD firstPage, lastPage, p;

    if (!arena ||
        !guest_range(va, size, &firstPage, &lastPage))
        return FALSE;

    for (p = firstPage; p <= lastPage; ++p)
        arena->protection[p] = protection;

    return TRUE;
}

static BYTE guest_query_protection(
    const GuestArena* arena,
    DWORD va)
{
    DWORD firstPage;

    if (!arena ||
        !guest_range(va, 1, &firstPage, NULL))
        return GUEST_PAGE_NOACCESS;

    return arena->protection[firstPage];
}

static BOOL guest_is_committed(
    const GuestArena* arena,
    DWORD va)
{
    DWORD page;

    if (!arena || !guest_range(va, 1, &page, NULL))
        return FALSE;

    return arena->committed[page] != 0;
}

static BYTE* guest_ptr(GuestArena* arena, DWORD va, DWORD size)
{
    DWORD offset;
    if (!arena || !arena->bytes ||
        !guest_range(va, size, NULL, NULL))
        return NULL;
    offset = va - GUEST_VA_BASE;
    return arena->bytes + offset;
}

static void run_tests(GuestArena* arena)
{
    DWORD va;
    DWORD releasedVa;
    DWORD releasedSize;
    DWORD reused;
    BYTE* ptr;

    check_result(
        arena && arena->bytes != NULL,
        "bounded guest arena allocated");
    if (!arena || !arena->bytes)
        return;

    va = guest_alloc(arena, 0x1800u);
    check_result(
        va != 0 && (va & (GUEST_PAGE_SIZE - 1u)) == 0,
        "guest allocation is 4 KiB aligned");

    ptr = guest_ptr(arena, va, 0x1800u);
    check_result(ptr != NULL, "guest allocation resolves inside arena");
    if (!ptr)
        return;

    memset(ptr, 0x5A, 0x1800u);
    check_result(
        ptr[0] == 0x5A && ptr[0x17FF] == 0x5A,
        "guest allocation payload is writable");

    check_result(
        guest_set_protection(
            arena, va, GUEST_PAGE_SIZE, GUEST_PAGE_READONLY),
        "set logical protection on first page");
    check_result(
        guest_query_protection(arena, va) == GUEST_PAGE_READONLY,
        "query returns first-page read-only protection");
    check_result(
        guest_query_protection(arena, va + GUEST_PAGE_SIZE) ==
            GUEST_PAGE_READWRITE,
        "adjacent page keeps original protection");

    check_result(
        guest_set_protection(
            arena, va, 0x1800u, GUEST_PAGE_EXECUTE_READWRITE),
        "set logical protection across multi-page range");
    check_result(
        guest_query_protection(arena, va) ==
            GUEST_PAGE_EXECUTE_READWRITE &&
        guest_query_protection(arena, va + 0x17FFu) ==
            GUEST_PAGE_EXECUTE_READWRITE,
        "multi-page protection metadata is coherent");

    check_result(
        guest_decommit(arena, va + GUEST_PAGE_SIZE, GUEST_PAGE_SIZE),
        "logical MEM_DECOMMIT succeeds");
    check_result(
        !guest_is_committed(arena, va + GUEST_PAGE_SIZE) &&
        guest_query_protection(arena, va + GUEST_PAGE_SIZE) ==
            GUEST_PAGE_NOACCESS,
        "decommit records no-access/uncommitted state");

    check_result(
        guest_commit(
            arena,
            va + GUEST_PAGE_SIZE,
            GUEST_PAGE_SIZE,
            GUEST_PAGE_READWRITE),
        "logical MEM_COMMIT succeeds on reserved range");
    check_result(
        guest_is_committed(arena, va + GUEST_PAGE_SIZE) &&
        guest_query_protection(arena, va + GUEST_PAGE_SIZE) ==
            GUEST_PAGE_READWRITE,
        "recommit restores committed protection state");

    releasedVa = va;
    releasedSize = 0x2000u;
    check_result(
        guest_release(arena, &releasedVa, &releasedSize),
        "MEM_RELEASE frees tracked guest allocation");
    check_result(
        releasedVa == 0 && releasedSize == 0,
        "MEM_RELEASE clears base and region size");

    /*
     * Check the stale original VA before the allocator is allowed to reuse
     * that range. Build A accidentally performed this check after reuse,
     * at which point the same VA was live again and a release was valid.
     */
    {
        DWORD staleVa = va;
        check_result(
            !guest_release(arena, &staleVa, NULL),
            "double release/untracked release is rejected");
    }

    reused = guest_alloc(arena, 0x1000u);
    check_result(
        reused == va,
        "released guest range is reusable");

    ptr = guest_ptr(arena, reused, 0x1000u);
    check_result(
        ptr && ptr[0] == 0 && ptr[0x0FFF] == 0,
        "reused guest allocation is zero-initialized");

    check_result(
        !guest_set_protection(
            arena,
            GUEST_VA_BASE + GUEST_ARENA_SIZE - 0x800u,
            0x1000u,
            GUEST_PAGE_READONLY),
        "cross-arena protection request is rejected");

    check_result(
        guest_release(arena, &reused, NULL) && reused == 0,
        "reused guest allocation can be released cleanly");
}

VOID __cdecl main()
{
    GuestArena arena;
    DWORD started;
    DWORD nextHeartbeat = 1000;

    s_logFile = CreateFileA(
        "game:\\merc360-phase4b-memory-protection.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace_line("PHASE 4B-C GUEST MEMORY/PROTECTION HARDWARE GATE START");
    tracef("BUILD TAG: %s", P4C_BUILD_TAG);
    trace_line("No Mercenaries retail code is executed by this gate");

    arena_init(&arena);
    run_tests(&arena);

    if (s_failures == 0)
        trace_line("PHASE 4B-C GUEST MEMORY/PROTECTION RESULT: PASS");
    else
        tracef(
            "PHASE 4B-C GUEST MEMORY/PROTECTION RESULT: FAIL (%d failures)",
            s_failures);

    arena_shutdown(&arena);

    trace_line("Press A to exit, or automatic exit after 10 seconds");
    started = GetTickCount();

    for (;;)
    {
        XINPUT_STATE state;
        DWORD elapsed = GetTickCount() - started;

        if (elapsed >= 10000)
            break;

        ZeroMemory(&state, sizeof(state));
        if (XInputGetState(0, &state) == ERROR_SUCCESS &&
            (state.Gamepad.wButtons & XINPUT_GAMEPAD_A) != 0)
            break;

        if (elapsed >= nextHeartbeat)
        {
            trace_line("POST-TEST HEARTBEAT");
            nextHeartbeat += 1000;
        }

        Sleep(33);
    }

    trace_line("PHASE 4B-C GUEST MEMORY/PROTECTION HARDWARE GATE END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

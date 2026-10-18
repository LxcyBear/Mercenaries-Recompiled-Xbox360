/*
 * Mercenaries Xbox 360 - Phase 2D checked guest-address routing diagnostic.
 *
 * SELF-CONTAINED XDK TEST. This program DOES NOT execute Mercenaries code.
 *
 * Phase 2D proves that a single explicit router can distinguish:
 *   - 64 MiB retail RAM
 *   - repeated 64 MiB CPU mirror windows
 *   - Xbox KSEG0/KSEG1 direct-physical aliases
 *   - synthetic D3D fence and fake kernel PE pages
 *   - shared VRAM aperture classification
 *   - NV2A, APU and AC97 MMIO classification
 *   - synthetic kernel-thunk VA classification
 *   - unsupported address gaps
 *
 * The router never treats MMIO or thunk addresses as ordinary RAM pointers.
 */

#include <xtl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MERC_GUEST_RAM_SIZE       0x04000000u
#define MERC_GUEST_RAM_MASK       0x03FFFFFFu

/* Primary 64 MiB + 28 64 MiB mirrors, matching the upstream retail layout. */
#define MERC_RAM_MIRROR_END       0x74000000u

#define MERC_SYNTH_FENCE_BASE     0x80000000u
#define MERC_SYNTH_FENCE_SIZE     0x00001000u
#define MERC_SYNTH_KERNEL_BASE    0x80010000u
#define MERC_SYNTH_KERNEL_SIZE    0x00001000u

#define MERC_KSEG_BASE            0x80000000u
#define MERC_KSEG_END             0xC0000000u

#define MERC_VRAM_BASE            0xF0000000u
#define MERC_VRAM_END             0xF4000000u

#define MERC_NV2A_BASE            0xFD000000u
#define MERC_NV2A_END             0xFE000000u

#define MERC_KERNEL_THUNK_BASE    0xFE000000u
#define MERC_KERNEL_THUNK_END     0xFE000600u

#define MERC_APU_BASE             0xFE800000u
#define MERC_APU_END              0xFE880000u

#define MERC_AC97_BASE            0xFEC00000u
#define MERC_AC97_END             0xFEC01000u

typedef enum GuestRouteKind
{
    GUEST_ROUTE_UNSUPPORTED = 0,
    GUEST_ROUTE_RAM,
    GUEST_ROUTE_SYNTH_FENCE,
    GUEST_ROUTE_SYNTH_KERNEL,
    GUEST_ROUTE_VRAM,
    GUEST_ROUTE_KERNEL_THUNK,
    GUEST_ROUTE_NV2A_MMIO,
    GUEST_ROUTE_APU_MMIO,
    GUEST_ROUTE_AC97_MMIO
} GuestRouteKind;

typedef struct GuestAddressSpace
{
    BYTE* ram;
    BYTE* synthFence;
    BYTE* synthKernel;
} GuestAddressSpace;

typedef struct GuestRoute
{
    GuestRouteKind kind;
    BYTE* pointer;
    DWORD offset;
} GuestRoute;

static HANDLE s_logFile = INVALID_HANDLE_VALUE;

static void trace(const char* line)
{
    DWORD written = 0;
    DWORD length = (DWORD)strlen(line);

    OutputDebugStringA("[Merc360:P2D] ");
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

static const char* route_name(GuestRouteKind kind)
{
    switch (kind)
    {
    case GUEST_ROUTE_RAM:          return "RAM";
    case GUEST_ROUTE_SYNTH_FENCE:  return "SYNTH_FENCE";
    case GUEST_ROUTE_SYNTH_KERNEL: return "SYNTH_KERNEL";
    case GUEST_ROUTE_VRAM:         return "VRAM";
    case GUEST_ROUTE_KERNEL_THUNK: return "KERNEL_THUNK";
    case GUEST_ROUTE_NV2A_MMIO:    return "NV2A_MMIO";
    case GUEST_ROUTE_APU_MMIO:     return "APU_MMIO";
    case GUEST_ROUTE_AC97_MMIO:    return "AC97_MMIO";
    default:                        return "UNSUPPORTED";
    }
}

static void trace_route(DWORD address, DWORD width, const GuestRoute* route)
{
    char line[192];
    sprintf(line,
            "ROUTE addr=%08X width=%u -> %s offset=%08X ptr=%p",
            (unsigned int)address,
            (unsigned int)width,
            route_name(route ? route->kind : GUEST_ROUTE_UNSUPPORTED),
            (unsigned int)(route ? route->offset : 0u),
            route ? route->pointer : NULL);
    trace(line);
}

static int range_contains(DWORD address,
                          DWORD width,
                          DWORD base,
                          DWORD endExclusive)
{
    DWORD offset;
    DWORD size;

    if (width == 0u || address < base || address >= endExclusive)
        return 0;

    offset = address - base;
    size = endExclusive - base;
    if (width > size - offset)
        return 0;

    return 1;
}

static int address_space_init(GuestAddressSpace* space)
{
    if (!space)
        return 0;

    ZeroMemory(space, sizeof(*space));

    space->ram = (BYTE*)malloc(MERC_GUEST_RAM_SIZE);
    space->synthFence = (BYTE*)malloc(MERC_SYNTH_FENCE_SIZE);
    space->synthKernel = (BYTE*)malloc(MERC_SYNTH_KERNEL_SIZE);

    if (!space->ram || !space->synthFence || !space->synthKernel)
        return 0;

    memset(space->ram, 0, MERC_GUEST_RAM_SIZE);
    memset(space->synthFence, 0, MERC_SYNTH_FENCE_SIZE);
    memset(space->synthKernel, 0, MERC_SYNTH_KERNEL_SIZE);

    /* Upstream fake Xbox kernel PE fixture: e_lfanew = 0x80. */
    space->synthKernel[0x3C] = 0x80u;

    return 1;
}

static void address_space_shutdown(GuestAddressSpace* space)
{
    if (!space)
        return;

    if (space->ram)
        free(space->ram);
    if (space->synthFence)
        free(space->synthFence);
    if (space->synthKernel)
        free(space->synthKernel);

    ZeroMemory(space, sizeof(*space));
}

static GuestRoute guest_route(GuestAddressSpace* space,
                              DWORD address,
                              DWORD width)
{
    GuestRoute route;
    DWORD offset;

    route.kind = GUEST_ROUTE_UNSUPPORTED;
    route.pointer = NULL;
    route.offset = 0u;

    if (!space || width == 0u)
        return route;

    /*
     * Primary RAM plus the 28 mirror windows used by the upstream runtime.
     * Every 64 MiB window resolves to the same underlying byte.
     */
    if (address < MERC_RAM_MIRROR_END)
    {
        offset = address & MERC_GUEST_RAM_MASK;
        if (offset < MERC_GUEST_RAM_SIZE &&
            width <= MERC_GUEST_RAM_SIZE - offset)
        {
            route.kind = GUEST_ROUTE_RAM;
            route.pointer = space->ram + offset;
            route.offset = offset;
        }
        return route;
    }

    /*
     * Synthetic pages override the normal KSEG physical alias rule.
     * This matches the upstream compatibility model.
     */
    if (range_contains(address, width,
                       MERC_SYNTH_FENCE_BASE,
                       MERC_SYNTH_FENCE_BASE + MERC_SYNTH_FENCE_SIZE))
    {
        offset = address - MERC_SYNTH_FENCE_BASE;
        route.kind = GUEST_ROUTE_SYNTH_FENCE;
        route.pointer = space->synthFence + offset;
        route.offset = offset;
        return route;
    }

    if (range_contains(address, width,
                       MERC_SYNTH_KERNEL_BASE,
                       MERC_SYNTH_KERNEL_BASE + MERC_SYNTH_KERNEL_SIZE))
    {
        offset = address - MERC_SYNTH_KERNEL_BASE;
        route.kind = GUEST_ROUTE_SYNTH_KERNEL;
        route.pointer = space->synthKernel + offset;
        route.offset = offset;
        return route;
    }

    /*
     * Original Xbox KSEG0/KSEG1 direct-physical aperture.
     * MCPX exposes 26 physical address bits, so 1 GiB repeats 64 MiB.
     */
    if (address >= MERC_KSEG_BASE && address < MERC_KSEG_END)
    {
        offset = address & MERC_GUEST_RAM_MASK;
        if (width <= MERC_GUEST_RAM_SIZE - offset)
        {
            route.kind = GUEST_ROUTE_RAM;
            route.pointer = space->ram + offset;
            route.offset = offset;
        }
        return route;
    }

    if (range_contains(address, width, MERC_VRAM_BASE, MERC_VRAM_END))
    {
        route.kind = GUEST_ROUTE_VRAM;
        route.offset = address - MERC_VRAM_BASE;
        return route;
    }

    if (range_contains(address, width, MERC_NV2A_BASE, MERC_NV2A_END))
    {
        route.kind = GUEST_ROUTE_NV2A_MMIO;
        route.offset = address - MERC_NV2A_BASE;
        return route;
    }

    if (range_contains(address, width,
                       MERC_KERNEL_THUNK_BASE,
                       MERC_KERNEL_THUNK_END))
    {
        route.kind = GUEST_ROUTE_KERNEL_THUNK;
        route.offset = address - MERC_KERNEL_THUNK_BASE;
        return route;
    }

    if (range_contains(address, width, MERC_APU_BASE, MERC_APU_END))
    {
        route.kind = GUEST_ROUTE_APU_MMIO;
        route.offset = address - MERC_APU_BASE;
        return route;
    }

    if (range_contains(address, width, MERC_AC97_BASE, MERC_AC97_END))
    {
        route.kind = GUEST_ROUTE_AC97_MMIO;
        route.offset = address - MERC_AC97_BASE;
        return route;
    }

    return route;
}

static DWORD read_le32(const BYTE* p)
{
    return ((DWORD)p[0]) |
           ((DWORD)p[1] << 8) |
           ((DWORD)p[2] << 16) |
           ((DWORD)p[3] << 24);
}

static void write_le32(BYTE* p, DWORD value)
{
    p[0] = (BYTE)value;
    p[1] = (BYTE)(value >> 8);
    p[2] = (BYTE)(value >> 16);
    p[3] = (BYTE)(value >> 24);
}

static int guest_write32(GuestAddressSpace* space,
                         DWORD address,
                         DWORD value)
{
    GuestRoute route = guest_route(space, address, 4u);

    if ((route.kind != GUEST_ROUTE_RAM &&
         route.kind != GUEST_ROUTE_SYNTH_FENCE &&
         route.kind != GUEST_ROUTE_SYNTH_KERNEL) ||
        !route.pointer)
        return 0;

    write_le32(route.pointer, value);
    return 1;
}

static int guest_read32(GuestAddressSpace* space,
                        DWORD address,
                        DWORD* value)
{
    GuestRoute route = guest_route(space, address, 4u);

    if (!value ||
        (route.kind != GUEST_ROUTE_RAM &&
         route.kind != GUEST_ROUTE_SYNTH_FENCE &&
         route.kind != GUEST_ROUTE_SYNTH_KERNEL) ||
        !route.pointer)
        return 0;

    *value = read_le32(route.pointer);
    return 1;
}

static int expect_route(GuestAddressSpace* space,
                        DWORD address,
                        DWORD width,
                        GuestRouteKind expected,
                        const char* passText,
                        const char* failText)
{
    GuestRoute route = guest_route(space, address, width);
    trace_route(address, width, &route);
    return check(route.kind == expected, passText, failText);
}

static int run_router_tests(GuestAddressSpace* space)
{
    int ok = 1;
    DWORD value = 0;
    GuestRoute route;

    ok &= check(space && space->ram && space->synthFence && space->synthKernel,
                "PASS: address-space backing allocated",
                "FAIL: address-space backing missing");

    ok &= expect_route(space, 0x00070000u, 4u, GUEST_ROUTE_RAM,
                       "PASS: primary RAM classified",
                       "FAIL: primary RAM classification");

    ok &= expect_route(space, 0x04070000u, 4u, GUEST_ROUTE_RAM,
                       "PASS: first 64 MiB mirror classified as RAM",
                       "FAIL: first RAM mirror classification");

    ok &= expect_route(space, 0x20000448u, 4u, GUEST_ROUTE_RAM,
                       "PASS: deep RenderWare-style mirror classified as RAM",
                       "FAIL: deep RAM mirror classification");

    ok &= expect_route(space, 0x70070000u, 4u, GUEST_ROUTE_RAM,
                       "PASS: final configured mirror window classified as RAM",
                       "FAIL: final configured mirror classification");

    ok &= expect_route(space, 0x74000000u, 4u, GUEST_ROUTE_UNSUPPORTED,
                       "PASS: address immediately after configured mirrors rejected",
                       "FAIL: mirror aperture over-accepted 0x74000000");

    ok &= check(guest_write32(space, 0x00070000u, 0x11223344u),
                "PASS: wrote primary RAM fixture",
                "FAIL: primary RAM write");

    ok &= check(guest_read32(space, 0x04070000u, &value) &&
                value == 0x11223344u,
                "PASS: first mirror aliases primary RAM coherently",
                "FAIL: first mirror coherence");

    ok &= check(guest_read32(space, 0x20070000u, &value) &&
                value == 0x11223344u,
                "PASS: deep mirror aliases primary RAM coherently",
                "FAIL: deep mirror coherence");

    ok &= check(guest_write32(space, 0x20000448u, 0xA1B2C3D4u),
                "PASS: wrote through deep RAM mirror",
                "FAIL: deep mirror write");

    ok &= check(guest_read32(space, 0x00000448u, &value) &&
                value == 0xA1B2C3D4u,
                "PASS: deep mirror write visible in base RAM",
                "FAIL: deep mirror write did not alias base RAM");

    ok &= expect_route(space, 0x81230000u, 4u, GUEST_ROUTE_RAM,
                       "PASS: KSEG0 physical alias classified as RAM",
                       "FAIL: KSEG0 classification");

    ok &= check(guest_write32(space, 0x81230000u, 0x55667788u),
                "PASS: wrote through KSEG0 alias",
                "FAIL: KSEG0 write");

    ok &= check(guest_read32(space, 0x01230000u, &value) &&
                value == 0x55667788u,
                "PASS: KSEG0 alias coherent with low RAM",
                "FAIL: KSEG0 alias coherence");

    ok &= expect_route(space, 0xA1230000u, 4u, GUEST_ROUTE_RAM,
                       "PASS: KSEG1 physical alias classified as RAM",
                       "FAIL: KSEG1 classification");

    ok &= check(guest_write32(space, 0xA1230000u, 0xCAFEBABEu),
                "PASS: wrote through KSEG1 alias",
                "FAIL: KSEG1 write");

    ok &= check(guest_read32(space, 0x01230000u, &value) &&
                value == 0xCAFEBABEu,
                "PASS: KSEG1 alias coherent with low RAM",
                "FAIL: KSEG1 alias coherence");

    /* Synthetic pages must override KSEG RAM aliasing. */
    ok &= expect_route(space, 0x80000000u, 4u, GUEST_ROUTE_SYNTH_FENCE,
                       "PASS: synthetic D3D fence overrides KSEG RAM",
                       "FAIL: synthetic fence priority");

    ok &= expect_route(space, 0x8001003Cu, 4u, GUEST_ROUTE_SYNTH_KERNEL,
                       "PASS: fake kernel PE page overrides KSEG RAM",
                       "FAIL: synthetic kernel priority");

    ok &= check(guest_write32(space, 0x0001003Cu, 0x11221122u),
                "PASS: wrote low RAM at 0x0001003C",
                "FAIL: low RAM kernel-shadow fixture write");

    ok &= check(guest_write32(space, 0x8001003Cu, 0x00000080u),
                "PASS: wrote fake kernel e_lfanew",
                "FAIL: fake kernel e_lfanew write");

    ok &= check(guest_read32(space, 0x8001003Cu, &value) &&
                value == 0x00000080u,
                "PASS: fake kernel e_lfanew reads 0x80",
                "FAIL: fake kernel e_lfanew readback");

    ok &= check(guest_read32(space, 0x0001003Cu, &value) &&
                value == 0x11221122u,
                "PASS: synthetic kernel page is distinct from low RAM alias",
                "FAIL: synthetic kernel page corrupted low RAM");

    route = guest_route(space, 0x03FFFFFCu, 4u);
    ok &= check(route.kind == GUEST_ROUTE_RAM && route.pointer != NULL,
                "PASS: last valid RAM dword accepted",
                "FAIL: last valid RAM dword rejected");

    route = guest_route(space, 0x03FFFFFFu, 4u);
    ok &= check(route.kind == GUEST_ROUTE_UNSUPPORTED,
                "PASS: cross-64MiB direct dword rejected",
                "FAIL: cross-64MiB direct dword was accepted");

    ok &= expect_route(space, 0xF0001000u, 4u, GUEST_ROUTE_VRAM,
                       "PASS: shared VRAM aperture classified separately",
                       "FAIL: VRAM classification");

    ok &= expect_route(space, 0xFD001000u, 4u, GUEST_ROUTE_NV2A_MMIO,
                       "PASS: NV2A MMIO classified separately",
                       "FAIL: NV2A MMIO classification");

    ok &= expect_route(space, 0xFE000000u, 4u, GUEST_ROUTE_KERNEL_THUNK,
                       "PASS: synthetic kernel thunk VA classified separately",
                       "FAIL: kernel thunk classification");

    ok &= expect_route(space, 0xFE820010u, 4u, GUEST_ROUTE_APU_MMIO,
                       "PASS: MCPX APU MMIO classified separately",
                       "FAIL: APU MMIO classification");

    ok &= expect_route(space, 0xFEC00010u, 4u, GUEST_ROUTE_AC97_MMIO,
                       "PASS: MCPX AC97 MMIO classified separately",
                       "FAIL: AC97 MMIO classification");

    /* MMIO/thunk addresses must never produce ordinary RAM pointers. */
    route = guest_route(space, 0xFD001000u, 4u);
    ok &= check(route.pointer == NULL,
                "PASS: NV2A route exposes no RAM pointer",
                "FAIL: NV2A route leaked RAM pointer");

    route = guest_route(space, 0xFE820010u, 4u);
    ok &= check(route.pointer == NULL,
                "PASS: APU route exposes no RAM pointer",
                "FAIL: APU route leaked RAM pointer");

    route = guest_route(space, 0xFE000000u, 4u);
    ok &= check(route.pointer == NULL,
                "PASS: kernel thunk route exposes no data pointer",
                "FAIL: kernel thunk route leaked data pointer");

    ok &= expect_route(space, 0x7FFFFFFFu, 1u, GUEST_ROUTE_UNSUPPORTED,
                       "PASS: pre-KSEG gap rejected",
                       "FAIL: pre-KSEG gap accepted");

    ok &= expect_route(space, 0xC0000000u, 4u, GUEST_ROUTE_UNSUPPORTED,
                       "PASS: post-KSEG gap rejected",
                       "FAIL: post-KSEG gap accepted");

    ok &= expect_route(space, 0xFFFFFFFFu, 1u, GUEST_ROUTE_UNSUPPORTED,
                       "PASS: 0xFFFFFFFF rejected",
                       "FAIL: 0xFFFFFFFF accepted");

    return ok;
}

VOID __cdecl main()
{
    GuestAddressSpace space;
    int result;
    DWORD started;
    DWORD nextHeartbeat = 1000u;

    ZeroMemory(&space, sizeof(space));

    s_logFile = CreateFileA(
        "game:\\merc360-phase2d-router.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace("PHASE 2D CHECKED GUEST ADDRESS ROUTER START");
    trace("BUILD TAG: P2D-ROUTER-20261018-A");
    trace("No Mercenaries guest code is executed by this diagnostic");

    if (!address_space_init(&space))
    {
        trace("FATAL: address-space allocation failed");
        address_space_shutdown(&space);
        goto wait_for_exit;
    }

    result = run_router_tests(&space);

    if (result)
        trace("PHASE 2D ADDRESS ROUTER RESULT: PASS");
    else
        trace("PHASE 2D ADDRESS ROUTER RESULT: FAIL");

    address_space_shutdown(&space);
    trace("Address-space backing released");

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

    trace("PHASE 2D CHECKED GUEST ADDRESS ROUTER END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

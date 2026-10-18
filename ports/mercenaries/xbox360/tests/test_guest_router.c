/*
 * Portable contract test for the Phase 2D guest-address router.
 * No Xbox/XDK/game content is required.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RAM_SIZE          0x04000000u
#define RAM_MASK          0x03FFFFFFu
#define MIRROR_END        0x74000000u
#define FENCE_BASE        0x80000000u
#define FENCE_SIZE        0x00001000u
#define KERNEL_BASE       0x80010000u
#define KERNEL_SIZE       0x00001000u
#define KSEG_BASE         0x80000000u
#define KSEG_END          0xC0000000u
#define VRAM_BASE         0xF0000000u
#define VRAM_END          0xF4000000u
#define NV2A_BASE         0xFD000000u
#define NV2A_END          0xFE000000u
#define THUNK_BASE        0xFE000000u
#define THUNK_END         0xFE000600u
#define APU_BASE          0xFE800000u
#define APU_END           0xFE880000u
#define AC97_BASE         0xFEC00000u
#define AC97_END          0xFEC01000u

typedef enum RouteKind {
    ROUTE_UNSUPPORTED = 0,
    ROUTE_RAM,
    ROUTE_FENCE,
    ROUTE_KERNEL,
    ROUTE_VRAM,
    ROUTE_THUNK,
    ROUTE_NV2A,
    ROUTE_APU,
    ROUTE_AC97
} RouteKind;

typedef struct Space {
    uint8_t *ram;
    uint8_t *fence;
    uint8_t *kernel;
} Space;

typedef struct Route {
    RouteKind kind;
    uint8_t *pointer;
    uint32_t offset;
} Route;

#define CHECK(expr) do { \
    if (!(expr)) { \
        fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #expr); \
        return 1; \
    } \
} while (0)

static int range_contains(uint32_t address, uint32_t width,
                          uint32_t base, uint32_t end)
{
    uint32_t offset;
    uint32_t size;
    if (width == 0u || address < base || address >= end) return 0;
    offset = address - base;
    size = end - base;
    return width <= size - offset;
}

static Route route_guest(Space *space, uint32_t address, uint32_t width)
{
    Route route = { ROUTE_UNSUPPORTED, NULL, 0u };
    uint32_t offset;

    if (!space || width == 0u) return route;

    if (address < MIRROR_END) {
        offset = address & RAM_MASK;
        if (width <= RAM_SIZE - offset) {
            route.kind = ROUTE_RAM;
            route.pointer = space->ram + offset;
            route.offset = offset;
        }
        return route;
    }

    if (range_contains(address, width, FENCE_BASE, FENCE_BASE + FENCE_SIZE)) {
        offset = address - FENCE_BASE;
        route.kind = ROUTE_FENCE;
        route.pointer = space->fence + offset;
        route.offset = offset;
        return route;
    }

    if (range_contains(address, width, KERNEL_BASE, KERNEL_BASE + KERNEL_SIZE)) {
        offset = address - KERNEL_BASE;
        route.kind = ROUTE_KERNEL;
        route.pointer = space->kernel + offset;
        route.offset = offset;
        return route;
    }

    if (address >= KSEG_BASE && address < KSEG_END) {
        offset = address & RAM_MASK;
        if (width <= RAM_SIZE - offset) {
            route.kind = ROUTE_RAM;
            route.pointer = space->ram + offset;
            route.offset = offset;
        }
        return route;
    }

    if (range_contains(address, width, VRAM_BASE, VRAM_END)) {
        route.kind = ROUTE_VRAM; route.offset = address - VRAM_BASE; return route;
    }
    if (range_contains(address, width, NV2A_BASE, NV2A_END)) {
        route.kind = ROUTE_NV2A; route.offset = address - NV2A_BASE; return route;
    }
    if (range_contains(address, width, THUNK_BASE, THUNK_END)) {
        route.kind = ROUTE_THUNK; route.offset = address - THUNK_BASE; return route;
    }
    if (range_contains(address, width, APU_BASE, APU_END)) {
        route.kind = ROUTE_APU; route.offset = address - APU_BASE; return route;
    }
    if (range_contains(address, width, AC97_BASE, AC97_END)) {
        route.kind = ROUTE_AC97; route.offset = address - AC97_BASE; return route;
    }
    return route;
}

static void write_le32(uint8_t *p, uint32_t v)
{
    p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8);
    p[2]=(uint8_t)(v>>16); p[3]=(uint8_t)(v>>24);
}

static uint32_t read_le32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
           ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}

static int write32(Space *s, uint32_t a, uint32_t v)
{
    Route r=route_guest(s,a,4u);
    if (!(r.kind==ROUTE_RAM || r.kind==ROUTE_FENCE || r.kind==ROUTE_KERNEL) ||
        !r.pointer) return 0;
    write_le32(r.pointer,v); return 1;
}

static int read32(Space *s, uint32_t a, uint32_t *v)
{
    Route r=route_guest(s,a,4u);
    if (!v || !(r.kind==ROUTE_RAM || r.kind==ROUTE_FENCE || r.kind==ROUTE_KERNEL) ||
        !r.pointer) return 0;
    *v=read_le32(r.pointer); return 1;
}

int main(void)
{
    Space s={0};
    Route r;
    uint32_t v=0;

    s.ram=(uint8_t*)calloc(1,RAM_SIZE);
    s.fence=(uint8_t*)calloc(1,FENCE_SIZE);
    s.kernel=(uint8_t*)calloc(1,KERNEL_SIZE);
    CHECK(s.ram && s.fence && s.kernel);

    CHECK(route_guest(&s,0x00070000u,4u).kind==ROUTE_RAM);
    CHECK(route_guest(&s,0x04070000u,4u).kind==ROUTE_RAM);
    CHECK(route_guest(&s,0x20000448u,4u).kind==ROUTE_RAM);
    CHECK(route_guest(&s,0x70070000u,4u).kind==ROUTE_RAM);
    CHECK(route_guest(&s,0x74000000u,4u).kind==ROUTE_UNSUPPORTED);

    CHECK(write32(&s,0x00070000u,0x11223344u));
    CHECK(read32(&s,0x04070000u,&v) && v==0x11223344u);
    CHECK(read32(&s,0x20070000u,&v) && v==0x11223344u);

    CHECK(write32(&s,0x20000448u,0xA1B2C3D4u));
    CHECK(read32(&s,0x00000448u,&v) && v==0xA1B2C3D4u);

    CHECK(write32(&s,0x81230000u,0x55667788u));
    CHECK(read32(&s,0x01230000u,&v) && v==0x55667788u);
    CHECK(write32(&s,0xA1230000u,0xCAFEBABEu));
    CHECK(read32(&s,0x01230000u,&v) && v==0xCAFEBABEu);

    CHECK(route_guest(&s,0x80000000u,4u).kind==ROUTE_FENCE);
    CHECK(route_guest(&s,0x8001003Cu,4u).kind==ROUTE_KERNEL);
    CHECK(write32(&s,0x0001003Cu,0x11221122u));
    CHECK(write32(&s,0x8001003Cu,0x80u));
    CHECK(read32(&s,0x8001003Cu,&v) && v==0x80u);
    CHECK(read32(&s,0x0001003Cu,&v) && v==0x11221122u);

    CHECK(route_guest(&s,0x03FFFFFCu,4u).kind==ROUTE_RAM);
    CHECK(route_guest(&s,0x03FFFFFFu,4u).kind==ROUTE_UNSUPPORTED);

    r=route_guest(&s,0xF0001000u,4u); CHECK(r.kind==ROUTE_VRAM && !r.pointer);
    r=route_guest(&s,0xFD001000u,4u); CHECK(r.kind==ROUTE_NV2A && !r.pointer);
    r=route_guest(&s,0xFE000000u,4u); CHECK(r.kind==ROUTE_THUNK && !r.pointer);
    r=route_guest(&s,0xFE820010u,4u); CHECK(r.kind==ROUTE_APU && !r.pointer);
    r=route_guest(&s,0xFEC00010u,4u); CHECK(r.kind==ROUTE_AC97 && !r.pointer);

    CHECK(route_guest(&s,0x7FFFFFFFu,1u).kind==ROUTE_UNSUPPORTED);
    CHECK(route_guest(&s,0xC0000000u,4u).kind==ROUTE_UNSUPPORTED);
    CHECK(route_guest(&s,0xFFFFFFFFu,1u).kind==ROUTE_UNSUPPORTED);

    free(s.ram); free(s.fence); free(s.kernel);
    puts("PASS: Phase 2D guest-address router contract");
    return 0;
}

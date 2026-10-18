/*
 * Host-side contract test for the bounded Phase 2 guest RAM arena.
 * This does not replace real Xenon testing.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "guest_memory.h"

#define CHECK(expr) do { \
    if (!(expr)) { \
        fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #expr); \
        return 1; \
    } \
} while (0)

int main(void)
{
    MercGuestMemory memory = { 0 };
    uint8_t v8 = 0;
    uint16_t v16 = 0;
    uint32_t v32 = 0;
    uint64_t v64 = 0;
    float vf = 0.0f;

    CHECK(merc_guest_memory_init(&memory, MERC_GUEST_RAM_SIZE));
    CHECK(memory.base != NULL);
    CHECK(memory.size == MERC_GUEST_RAM_SIZE);

    CHECK(merc_guest_memory_write8(&memory, 0u, 0xA5u));
    CHECK(merc_guest_memory_read8(&memory, 0u, &v8));
    CHECK(v8 == 0xA5u);

    CHECK(merc_guest_memory_write16(&memory, 2u, 0xBEEFu));
    CHECK(merc_guest_memory_read16(&memory, 2u, &v16));
    CHECK(v16 == 0xBEEFu);

    CHECK(merc_guest_memory_write32(&memory, 0x10000u, 0x12345678u));
    CHECK(memory.base[0x10000u] == 0x78u);
    CHECK(memory.base[0x10001u] == 0x56u);
    CHECK(memory.base[0x10002u] == 0x34u);
    CHECK(memory.base[0x10003u] == 0x12u);
    CHECK(merc_guest_memory_read32(&memory, 0x10000u, &v32));
    CHECK(v32 == 0x12345678u);

    CHECK(merc_guest_memory_write32(&memory, 0x10003u, 0x89ABCDEFu));
    CHECK(merc_guest_memory_read32(&memory, 0x10003u, &v32));
    CHECK(v32 == 0x89ABCDEFu);

    CHECK(merc_guest_memory_write_float32(&memory, 0x12345u, 1.0f));
    CHECK(merc_guest_memory_read_float32(&memory, 0x12345u, &vf));
    CHECK(vf == 1.0f);

    CHECK(merc_guest_memory_write64(&memory, MERC_GUEST_RAM_SIZE - 8u,
                                    UINT64_C(0x0102030405060708)));
    CHECK(merc_guest_memory_read64(&memory, MERC_GUEST_RAM_SIZE - 8u, &v64));
    CHECK(v64 == UINT64_C(0x0102030405060708));

    CHECK(!merc_guest_memory_write32(&memory, MERC_GUEST_RAM_SIZE - 2u,
                                     0xDEADBEEFu));
    CHECK(!merc_guest_memory_read32(&memory, MERC_GUEST_RAM_SIZE, &v32));
    CHECK(!merc_guest_memory_write8(&memory, UINT32_MAX, 0x11u));

    merc_guest_memory_shutdown(&memory);
    CHECK(memory.base == NULL);
    CHECK(memory.size == 0u);

    puts("PASS: bounded 64 MiB guest RAM contract");
    return 0;
}

/*
 * Platform-neutral test for little-endian original-Xbox guest data.
 * No XDK, retail game image, or proprietary assets are required.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "guest_endian.h"

#define CHECK(expr) do { \
    if (!(expr)) { \
        fprintf(stderr, "FAIL line %d: %s\\n", __LINE__, #expr); \
        return 1; \
    } \
} while (0)

int main(void)
{
    uint8_t bytes[24] = { 0 };
    const uint8_t sample[8] = { 0x01, 0x23, 0x45, 0x67,
                                0x89, 0xAB, 0xCD, 0xEF };
    const uint8_t expected32[4] = { 0x78, 0x56, 0x34, 0x12 };
    const uint8_t expected64[8] = { 0x08, 0x07, 0x06, 0x05,
                                    0x04, 0x03, 0x02, 0x01 };

    CHECK(sizeof(uint16_t) == 2);
    CHECK(sizeof(uint32_t) == 4);
    CHECK(sizeof(uint64_t) == 8);
    CHECK(sizeof(float) == 4);

    memcpy(bytes + 1, sample, sizeof(sample));  /* intentionally unaligned */
    CHECK(merc_guest_read_le16(bytes + 1) == UINT16_C(0x2301));
    CHECK(merc_guest_read_le32(bytes + 1) == UINT32_C(0x67452301));
    CHECK(merc_guest_read_le64(bytes + 1) == UINT64_C(0xEFCDAB8967452301));

    memset(bytes, 0, sizeof(bytes));
    merc_guest_write_le16(bytes + 1, UINT16_C(0xBEEF));
    CHECK(bytes[1] == 0xEF && bytes[2] == 0xBE);

    merc_guest_write_le32(bytes + 3, UINT32_C(0x12345678));
    CHECK(memcmp(bytes + 3, expected32, sizeof(expected32)) == 0);
    CHECK(merc_guest_read_le32(bytes + 3) == UINT32_C(0x12345678));

    merc_guest_write_le64(bytes + 5, UINT64_C(0x0102030405060708));
    CHECK(memcmp(bytes + 5, expected64, sizeof(expected64)) == 0);
    CHECK(merc_guest_read_le64(bytes + 5) == UINT64_C(0x0102030405060708));

    merc_guest_write_le_float32(bytes + 1, 1.0f);
    CHECK(bytes[1] == 0x00 && bytes[2] == 0x00);
    CHECK(bytes[3] == 0x80 && bytes[4] == 0x3F);
    CHECK(merc_guest_read_le_float32(bytes + 1) == 1.0f);

    merc_guest_write_le_float32(bytes + 1, -1.5f);
    CHECK(merc_guest_read_le32(bytes + 1) == UINT32_C(0xBFC00000));
    CHECK(merc_guest_read_le_float32(bytes + 1) == -1.5f);

    puts("PASS: little-endian guest access, unaligned reads/writes, float bits");
    return 0;
}

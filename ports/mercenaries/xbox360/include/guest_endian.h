/*
 * Mercenaries Xbox 360 port - host-independent original-Xbox data access.
 *
 * The original Xbox CPU is little-endian.  Xbox 360 Xenon is big-endian.
 * These primitives access the *guest* byte representation explicitly:
 * they do not assume host endianness or naturally aligned guest addresses.
 *
 * This is a portable reference building block, NOT an integrated replacement
 * for recomp_types.h MEM16/MEM32/MEM64.  Those macros are lvalues used by the
 * generated source and require a coordinated generator/runtime refactor.
 *
 * No proprietary Xbox 360 SDK headers or copyrighted game data are included.
 */
#ifndef MERC_XBOX360_GUEST_ENDIAN_H
#define MERC_XBOX360_GUEST_ENDIAN_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(_MSC_VER)
#define MERC_GUEST_INLINE static __inline
#else
#define MERC_GUEST_INLINE static inline
#endif

MERC_GUEST_INLINE uint16_t merc_guest_read_le16(const void *address)
{
    const uint8_t *p = (const uint8_t *)address;
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

MERC_GUEST_INLINE uint32_t merc_guest_read_le32(const void *address)
{
    const uint8_t *p = (const uint8_t *)address;
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

MERC_GUEST_INLINE uint64_t merc_guest_read_le64(const void *address)
{
    const uint8_t *p = (const uint8_t *)address;
    return (uint64_t)merc_guest_read_le32(p) |
           ((uint64_t)merc_guest_read_le32(p + 4) << 32);
}

MERC_GUEST_INLINE void merc_guest_write_le16(void *address, uint16_t value)
{
    uint8_t *p = (uint8_t *)address;
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
}

MERC_GUEST_INLINE void merc_guest_write_le32(void *address, uint32_t value)
{
    uint8_t *p = (uint8_t *)address;
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
    p[2] = (uint8_t)(value >> 16);
    p[3] = (uint8_t)(value >> 24);
}

MERC_GUEST_INLINE void merc_guest_write_le64(void *address, uint64_t value)
{
    uint8_t *p = (uint8_t *)address;
    merc_guest_write_le32(p, (uint32_t)value);
    merc_guest_write_le32(p + 4, (uint32_t)(value >> 32));
}

MERC_GUEST_INLINE float merc_guest_read_le_float32(const void *address)
{
    const uint32_t bits = merc_guest_read_le32(address);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

MERC_GUEST_INLINE void merc_guest_write_le_float32(void *address, float value)
{
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    merc_guest_write_le32(address, bits);
}

#undef MERC_GUEST_INLINE
#endif /* MERC_XBOX360_GUEST_ENDIAN_H */

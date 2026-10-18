/*
 * Mercenaries Xbox 360 - bounded original-Xbox guest RAM arena.
 *
 * Phase 2 intentionally models only the low 64 MiB guest RAM window.
 * Mirrors, KSEG aliases, synthetic kernel space and MMIO are added only after
 * the byte-order and bounds contract is proven on real Xenon hardware.
 */
#ifndef MERC_XBOX360_GUEST_MEMORY_H
#define MERC_XBOX360_GUEST_MEMORY_H

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "guest_endian.h"

#define MERC_GUEST_RAM_SIZE (64u * 1024u * 1024u)

#if defined(_MSC_VER)
#define MERC_GUEST_MEMORY_INLINE static __inline
#else
#define MERC_GUEST_MEMORY_INLINE static inline
#endif

typedef struct MercGuestMemory
{
    uint8_t* base;
    uint32_t size;
} MercGuestMemory;

MERC_GUEST_MEMORY_INLINE int merc_guest_memory_init(MercGuestMemory* memory, uint32_t size)
{
    if (!memory || size == 0u)
        return 0;

    memory->base = (uint8_t*)malloc((size_t)size);
    if (!memory->base)
    {
        memory->size = 0u;
        return 0;
    }

    memory->size = size;
    memset(memory->base, 0, (size_t)size);
    return 1;
}

MERC_GUEST_MEMORY_INLINE void merc_guest_memory_shutdown(MercGuestMemory* memory)
{
    if (!memory)
        return;
    if (memory->base)
        free(memory->base);
    memory->base = NULL;
    memory->size = 0u;
}

MERC_GUEST_MEMORY_INLINE void* merc_guest_memory_ptr(MercGuestMemory* memory,
                                   uint32_t address,
                                   uint32_t width)
{
    if (!memory || !memory->base || width == 0u)
        return NULL;
    if (address >= memory->size)
        return NULL;
    if (width > memory->size - address)
        return NULL;
    return memory->base + address;
}

MERC_GUEST_MEMORY_INLINE const void* merc_guest_memory_cptr(const MercGuestMemory* memory,
                                          uint32_t address,
                                          uint32_t width)
{
    if (!memory || !memory->base || width == 0u)
        return NULL;
    if (address >= memory->size)
        return NULL;
    if (width > memory->size - address)
        return NULL;
    return memory->base + address;
}

MERC_GUEST_MEMORY_INLINE int merc_guest_memory_read8(const MercGuestMemory* memory,
                                   uint32_t address,
                                   uint8_t* value)
{
    const uint8_t* p = (const uint8_t*)merc_guest_memory_cptr(memory, address, 1u);
    if (!p || !value)
        return 0;
    *value = *p;
    return 1;
}

MERC_GUEST_MEMORY_INLINE int merc_guest_memory_read16(const MercGuestMemory* memory,
                                    uint32_t address,
                                    uint16_t* value)
{
    const void* p = merc_guest_memory_cptr(memory, address, 2u);
    if (!p || !value)
        return 0;
    *value = merc_guest_read_le16(p);
    return 1;
}

MERC_GUEST_MEMORY_INLINE int merc_guest_memory_read32(const MercGuestMemory* memory,
                                    uint32_t address,
                                    uint32_t* value)
{
    const void* p = merc_guest_memory_cptr(memory, address, 4u);
    if (!p || !value)
        return 0;
    *value = merc_guest_read_le32(p);
    return 1;
}

MERC_GUEST_MEMORY_INLINE int merc_guest_memory_read64(const MercGuestMemory* memory,
                                    uint32_t address,
                                    uint64_t* value)
{
    const void* p = merc_guest_memory_cptr(memory, address, 8u);
    if (!p || !value)
        return 0;
    *value = merc_guest_read_le64(p);
    return 1;
}

MERC_GUEST_MEMORY_INLINE int merc_guest_memory_read_float32(const MercGuestMemory* memory,
                                          uint32_t address,
                                          float* value)
{
    const void* p = merc_guest_memory_cptr(memory, address, 4u);
    if (!p || !value)
        return 0;
    *value = merc_guest_read_le_float32(p);
    return 1;
}

MERC_GUEST_MEMORY_INLINE int merc_guest_memory_write8(MercGuestMemory* memory,
                                    uint32_t address,
                                    uint8_t value)
{
    uint8_t* p = (uint8_t*)merc_guest_memory_ptr(memory, address, 1u);
    if (!p)
        return 0;
    *p = value;
    return 1;
}

MERC_GUEST_MEMORY_INLINE int merc_guest_memory_write16(MercGuestMemory* memory,
                                     uint32_t address,
                                     uint16_t value)
{
    void* p = merc_guest_memory_ptr(memory, address, 2u);
    if (!p)
        return 0;
    merc_guest_write_le16(p, value);
    return 1;
}

MERC_GUEST_MEMORY_INLINE int merc_guest_memory_write32(MercGuestMemory* memory,
                                     uint32_t address,
                                     uint32_t value)
{
    void* p = merc_guest_memory_ptr(memory, address, 4u);
    if (!p)
        return 0;
    merc_guest_write_le32(p, value);
    return 1;
}

MERC_GUEST_MEMORY_INLINE int merc_guest_memory_write64(MercGuestMemory* memory,
                                     uint32_t address,
                                     uint64_t value)
{
    void* p = merc_guest_memory_ptr(memory, address, 8u);
    if (!p)
        return 0;
    merc_guest_write_le64(p, value);
    return 1;
}

MERC_GUEST_MEMORY_INLINE int merc_guest_memory_write_float32(MercGuestMemory* memory,
                                           uint32_t address,
                                           float value)
{
    void* p = merc_guest_memory_ptr(memory, address, 4u);
    if (!p)
        return 0;
    merc_guest_write_le_float32(p, value);
    return 1;
}

#undef MERC_GUEST_MEMORY_INLINE

#endif /* MERC_XBOX360_GUEST_MEMORY_H */

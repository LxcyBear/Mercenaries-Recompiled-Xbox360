#ifndef MERC360_KERNEL_CLOCK_GUEST_BRIDGE_H
#define MERC360_KERNEL_CLOCK_GUEST_BRIDGE_H
#include "KernelClockCore.h"
#include <stdint.h>
namespace merc360_k1 {
/* Guest memory contract: readable(address,length), writable(address,length),
   read16(), read32(), write16(), write32(). A real Xenon adapter must
   retain the source runtime's existing guest-address hard-fence model.
   This layer does not handle x86 global EAX/ESP; dispatch adapter must prove
   that exact savedEsp contract before binding these methods. */
template <typename Memory>
struct GuestClock {
    static bool valid_range(uint32_t address, uint32_t length) {
        return address != 0u &&
               (uint64_t)address + (uint64_t)length <= UINT64_C(0x100000000);
    }
    static bool query_system_time(Memory& mem, uint32_t out, uint64_t now) {
        if (!valid_range(out, 8u) || !mem.writable(out,8u)) return false;
        mem.write32(out, (uint32_t)now);
        mem.write32(out+4u, (uint32_t)(now>>32));
        return true;
    }
    static bool time_fields_to_time(Memory& mem, uint32_t input,
                                    uint32_t output, uint32_t* result) {
        if (!result || !valid_range(input,16u) || !valid_range(output,8u) ||
            !mem.readable(input,16u) || !mem.writable(output,8u)) return false;
        TimeFields fields;
        fields.year=(int16_t)mem.read16(input+0u);
        fields.month=(int16_t)mem.read16(input+2u);
        fields.day=(int16_t)mem.read16(input+4u);
        fields.hour=(int16_t)mem.read16(input+6u);
        fields.minute=(int16_t)mem.read16(input+8u);
        fields.second=(int16_t)mem.read16(input+10u);
        fields.milliseconds=(int16_t)mem.read16(input+12u);
        fields.weekday=(int16_t)mem.read16(input+14u);
        uint64_t ticks=0;
        if (!to_ticks(fields,&ticks)) { *result=0u; return true; }
        mem.write32(output,(uint32_t)ticks);
        mem.write32(output+4u,(uint32_t)(ticks>>32));
        *result=1u;
        return true;
    }
    static bool time_to_time_fields(Memory& mem, uint32_t input,
                                    uint32_t output) {
        if (!valid_range(input,8u) || !valid_range(output,16u) ||
            !mem.readable(input,8u) || !mem.writable(output,16u)) return false;
        uint64_t ticks=(uint64_t)mem.read32(input) |
            ((uint64_t)mem.read32(input+4u)<<32);
        TimeFields fields;
        if (!from_ticks(ticks,&fields)) return false;
        mem.write16(output+0u,(uint16_t)fields.year);
        mem.write16(output+2u,(uint16_t)fields.month);
        mem.write16(output+4u,(uint16_t)fields.day);
        mem.write16(output+6u,(uint16_t)fields.hour);
        mem.write16(output+8u,(uint16_t)fields.minute);
        mem.write16(output+10u,(uint16_t)fields.second);
        mem.write16(output+12u,(uint16_t)fields.milliseconds);
        mem.write16(output+14u,(uint16_t)fields.weekday);
        return true;
    }
};
} // namespace merc360_k1
#endif

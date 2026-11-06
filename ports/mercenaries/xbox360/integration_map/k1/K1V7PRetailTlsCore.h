#ifndef MERC360_K1_V7P_RETAIL_TLS_H
#define MERC360_K1_V7P_RETAIL_TLS_H
#include <stdint.h>
namespace merc360_v7p {
/* Verified original retail Xbox x86:
   0022B150: TLS get [TLS slot+4], ret 0
   0022B178: TLS set [TLS slot+4]=[ESP+4], ret 4

   These methods implement ONLY the memory dataflow. The eventual translated
   adapter must separately read FS:[24], conditionally read FS:[28] when <2,
   preserve CMP/JA(E) flags, EAX/ECX effects and ret_esp semantics.
   fs4 is the actual guest FS:[4], NOT a constant. Index is the original
   signed 32-bit TLS index in the XBE (negative values are intentional).
   Memory is a bounded guest reader/writer, with existing hard fences.
*/
template<typename GuestMemory>
struct RetailTls {
    static uint32_t slot(GuestMemory& mem, uint32_t fs4) {
        const uint32_t index = mem.read32(0x00869118u);
        // Original IA-32 addressing: modulo-2^32 arithmetic, index * 4.
        const uint32_t address = fs4 + index * 4u;
        return mem.read32(address);
    }
    static uint32_t get(GuestMemory& mem, uint32_t fs4) {
        const uint32_t pointer = slot(mem, fs4);
        return mem.read32(pointer + 4u);
    }
    static uint32_t set(GuestMemory& mem, uint32_t fs4, uint32_t value) {
        const uint32_t pointer = slot(mem, fs4);
        mem.write32(pointer + 4u, value);
        return pointer; // original EAX retains TLS slot pointer on return
    }
};
} // namespace merc360_v7p
#endif

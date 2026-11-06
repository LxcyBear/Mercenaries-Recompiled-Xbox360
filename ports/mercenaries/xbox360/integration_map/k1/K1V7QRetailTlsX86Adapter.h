#ifndef MERC360_K1_V7Q_X86_TLS_ADAPTER_H
#define MERC360_K1_V7Q_X86_TLS_ADAPTER_H
#include "K1V7PRetailTlsCore.h"
#include <stdint.h>
namespace merc360_v7q {
struct Flags {
    bool cf,zf,sf,of,af,pf;
};
inline bool even_parity8(uint8_t x) {
    x ^= (uint8_t)(x>>4);
    x &= 0x0fu;
    return ((0x9669u>>x)&1u)!=0u;
}
inline Flags cmp_al_2(uint8_t al) {
    const uint8_t result=(uint8_t)(al-2u);
    Flags f={al<2u,result==0u,(result&0x80u)!=0u,
        ((al^2u)&(al^result)&0x80u)!=0u,
        ((al^2u^result)&0x10u)!=0u,even_parity8(result)};
    return f;
}
struct Cpu {
    uint32_t eax,ecx,esp;
    Flags flags;
};
/* FS backend must read ORIGINAL GUEST FS address space, not native Xenon FS.
   memory.read32/write32 must retain existing guest-address hard fences.
   This adapter models verified x86 operations; no synthetic TLS storage.
   Flags exactly represent CMP AL,2. Other CPU registers/flags are preserved
   as in original MOV/MOVZX/RET instructions.
*/
template <typename GuestMemory,typename GuestFs>
struct RetailTlsX86 {
    static void get(Cpu& cpu,GuestMemory& mem,GuestFs& fs) {
        // 0022B150 movzx eax,byte ptr fs:[0x24]
        const uint8_t selector=fs.read8(0x24u);
        cpu.eax=selector;
        // 0022B158 cmp al,2 / 0022B15A jae
        cpu.flags=cmp_al_2(selector);
        if (selector<2u) {
            // Original read is retained even though later MOV overwrites EAX.
            cpu.eax=fs.read32(0x28u);
        }
        // 0022B162 mov eax,[0x869118]
        const uint32_t index=mem.read32(0x00869118u);
        // 0022B167 mov ecx,fs:[4]
        cpu.ecx=fs.read32(4u);
        // 0022B16E mov eax,[ecx+eax*4]
        cpu.eax=mem.read32(cpu.ecx+index*4u);
        // 0022B171 mov eax,[eax+4]
        cpu.eax=mem.read32(cpu.eax+4u);
        // 0022B177 ret; dispatcher follows existing guest return contract.
    }
    static void set(Cpu& cpu,GuestMemory& mem,GuestFs& fs) {
        // 0022B178 movzx eax,byte ptr fs:[0x24]
        const uint8_t selector=fs.read8(0x24u);
        cpu.eax=selector;
        // 0022B180 cmp al,2 / 0022B182 jae
        cpu.flags=cmp_al_2(selector);
        if(selector<2u)cpu.eax=fs.read32(0x28u);
        // 0022B18A mov ecx,fs:[4]
        cpu.ecx=fs.read32(4u);
        // 0022B191 mov eax,[0x869118]
        cpu.eax=mem.read32(0x00869118u);
        // 0022B196 mov eax,[ecx+eax*4]
        cpu.eax=mem.read32(cpu.ecx+cpu.eax*4u);
        // 0022B199 mov ecx,[esp+4]
        cpu.ecx=mem.read32(cpu.esp+4u);
        // 0022B19D mov [eax+4],ecx
        mem.write32(cpu.eax+4u,cpu.ecx);
        // 0022B1A3 ret 4; dispatcher follows existing guest return contract.
    }
};
} // namespace merc360_v7q
#endif

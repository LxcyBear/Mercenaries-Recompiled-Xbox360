#include "KernelClockGuestBridge.h"
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
struct MockGuest {
    uint8_t mem[512];
    MockGuest(){memset(mem,0xCD,sizeof(mem));}
    bool readable(uint32_t a,uint32_t n) const {
        return a>0 && (uint64_t)a+n<=sizeof(mem);
    }
    bool writable(uint32_t a,uint32_t n) const {return readable(a,n);}
    uint16_t read16(uint32_t a) const {assert(readable(a,2));return (uint16_t)(mem[a]|(mem[a+1]<<8));}
    uint32_t read32(uint32_t a) const {assert(readable(a,4));return
         (uint32_t)mem[a]|((uint32_t)mem[a+1]<<8)|((uint32_t)mem[a+2]<<16)|((uint32_t)mem[a+3]<<24);}
    void write16(uint32_t a,uint16_t v) {assert(writable(a,2));mem[a]=(uint8_t)v;mem[a+1]=(uint8_t)(v>>8);}
    void write32(uint32_t a,uint32_t v) {assert(writable(a,4));write16(a,(uint16_t)v);write16(a+2,(uint16_t)(v>>16));}
};
int main(){
    MockGuest mem;
    typedef merc360_k1::GuestClock<MockGuest> Bridge;
    const uint64_t t=UINT64_C(133536384000000000);
    assert(Bridge::query_system_time(mem,32u,t));
    assert(mem.read32(32u)==(uint32_t)t);
    assert(mem.read32(36u)==(uint32_t)(t>>32));
    assert(!Bridge::query_system_time(mem,0u,t));
    assert(!Bridge::query_system_time(mem,508u,t));
    assert(!Bridge::query_system_time(mem,0xFFFFFFFCu,t));
    mem.write16(64,2024);mem.write16(66,2);mem.write16(68,29);
    mem.write16(70,0);mem.write16(72,0);mem.write16(74,0);
    mem.write16(76,0);mem.write16(78,0);
    uint32_t result=99;
    assert(Bridge::time_fields_to_time(mem,64,120,&result));
    assert(result==1u);
    uint64_t back=(uint64_t)mem.read32(120)|((uint64_t)mem.read32(124)<<32);
    assert(back==t);
    mem.write16(64,1900);
    mem.write16(66,2);
    mem.write16(68,29);
    assert(Bridge::time_fields_to_time(mem,64,120,&result));
    assert(result==0u);
    assert(mem.read32(120)==(uint32_t)t); // invalid dates don't write output
    assert(!Bridge::time_fields_to_time(mem,64,120,(uint32_t*)0));
    assert(!Bridge::time_fields_to_time(mem,0,120,&result));
    assert(!Bridge::time_fields_to_time(mem,64,510,&result));
    assert(Bridge::time_to_time_fields(mem,120,160));
    assert(mem.read16(160)==2024 && mem.read16(162)==2 && mem.read16(164)==29);
    assert(mem.read16(174)==4); // 2024-02-29 Thursday; Sunday = 0
    assert(!Bridge::time_to_time_fields(mem,0,160));
    assert(!Bridge::time_to_time_fields(mem,120,500));
    mem.write32(120,0xFFFFFFFF);mem.write32(124,0xFFFFFFFF);
    assert(!Bridge::time_to_time_fields(mem,120,160));
    puts("[K1A] PASS: guest clock API memory contracts, 64-bit writes, invalid pointers and dates");
    return 0;
}

#include "K1V7PRetailTlsCore.h"
#include <stdint.h>
#include <map>
#include <stdexcept>
#include <stdio.h>
struct Memory {
    std::map<uint32_t,uint32_t> words;
    int read_count;
    int write_count;
    Memory():read_count(0),write_count(0){}
    uint32_t read32(uint32_t addr) {
        ++read_count;
        std::map<uint32_t,uint32_t>::const_iterator i=words.find(addr);
        if(i==words.end())throw std::runtime_error("unmapped guest read");
        return i->second;
    }
    void write32(uint32_t addr,uint32_t v) {
        ++write_count;
        if(words.find(addr)==words.end())throw std::runtime_error("unmapped guest write");
        words[addr]=v;
    }
};
static void check(bool ok,const char* msg) {
    if(!ok)throw std::runtime_error(msg);
}
int main(){
    try{
        Memory mem;
        // Original retail index uses wraparound addressing. Negative guest
        // TLS index must NOT be sanitized into a nonnegative array index.
        const uint32_t fs4=0x00700040u;
        mem.words[0x00869118u]=0xfffffff0u;
        mem.words[0x00700000u]=0x00710000u;
        mem.words[0x00710004u]=0x11223344u;
        check(merc360_v7p::RetailTls<Memory>::get(mem,fs4)==0x11223344u,
              "retail getter result mismatch");
        check(mem.read_count==3 && mem.write_count==0,
              "getter must read index, pointer, pointer+4");
        check(merc360_v7p::RetailTls<Memory>::set(mem,fs4,0xaabbccddu)==0x00710000u,
              "setter EAX must retain TLS slot pointer");
        check(mem.words[0x00710004u]==0xaabbccddu,
              "setter must update original pointer+4");
        check(mem.read_count==5 && mem.write_count==1,
              "setter must read index/pointer and write pointer+4");
        bool fenced=false;
        try{
            Memory invalid;
            invalid.words[0x00869118u]=0xfffffff0u;
            merc360_v7p::RetailTls<Memory>::get(invalid,fs4);
        }catch(const std::runtime_error&){fenced=true;}
        check(fenced,"unknown guest memory must hard fence");
        puts("[K1-V7P] TEST PASS original signed TLS index, getter/setter, EAX, bounded guest memory");
        puts("[K1-V7P] DATAFLOW ONLY; FS side effects/flags/return ABI require translator adapter; NO XDK");
        return 0;
    }catch(const std::exception& e){
        fprintf(stderr,"[K1-V7P] TEST FAIL %s\n",e.what());
        return 1;
    }
}

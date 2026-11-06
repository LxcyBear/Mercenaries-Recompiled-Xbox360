#include "K1V7QRetailTlsX86Adapter.h"
#include <stdint.h>
#include <map>
#include <vector>
#include <stdexcept>
#include <stdio.h>
struct Guest {
    std::map<uint32_t,uint32_t> words;
    std::vector<uint32_t> reads,writes;
    uint32_t read32(uint32_t a) {
        reads.push_back(a);
        std::map<uint32_t,uint32_t>::const_iterator i=words.find(a);
        if(i==words.end())throw std::runtime_error("guest read hard fence");
        return i->second;
    }
    void write32(uint32_t a,uint32_t v) {
        writes.push_back(a);
        if(words.find(a)==words.end())throw std::runtime_error("guest write hard fence");
        words[a]=v;
    }
};
struct Fs {
    uint8_t selector;
    uint32_t fs4,fs28;
    std::vector<uint32_t> reads8,reads32;
    uint8_t read8(uint32_t a) {
        reads8.push_back(a);
        if(a!=0x24u)throw std::runtime_error("unknown FS8");
        return selector;
    }
    uint32_t read32(uint32_t a) {
        reads32.push_back(a);
        if(a==4u)return fs4;
        if(a==0x28u)return fs28;
        throw std::runtime_error("unknown FS32");
    }
};
static void check(bool t,const char *m) {if(!t)throw std::runtime_error(m);}
static void test_one(unsigned int selector){
    Guest guest;
    const uint32_t fs4=0x00700040u;
    guest.words[0x00869118u]=0xfffffff0u;
    guest.words[0x00700000u]=0x00710000u;
    guest.words[0x00710004u]=0x11223344u;
    guest.words[0x00880004u]=0xaabbccddu;
    Fs fs={static_cast<uint8_t>(selector),fs4,0x42424242u};
    merc360_v7q::Cpu c={0xfeedbeefu,0xeeeeeeeeu,0x00880000u,{}};
    merc360_v7q::RetailTlsX86<Guest,Fs>::get(c,guest,fs);
    check(c.eax==0x11223344u && c.ecx==fs4 && c.esp==0x00880000u,
          "getter EAX/ECX/ESP semantics");
    check(fs.reads8.size()==1 && fs.reads8[0]==0x24u,"getter FS selector");
    check(fs.reads32.size()==(selector<2u?2u:1u),"getter conditional FS28");
    check(fs.reads32.back()==4u,"getter must read FS4");
    check(c.flags.cf==(selector<2u) && c.flags.zf==(selector==2u),
          "getter cmp flags");
    check(guest.reads.size()==3 && guest.writes.empty(),"getter memory traffic");
    guest.reads.clear();
    fs.reads8.clear(); fs.reads32.clear();
    c.eax=0; c.ecx=0;
    merc360_v7q::RetailTlsX86<Guest,Fs>::set(c,guest,fs);
    check(c.eax==0x00710000u && c.ecx==0xaabbccddu && c.esp==0x00880000u,
          "setter EAX ECX ESP semantics");
    check(guest.words[0x00710004u]==0xaabbccddu,"setter memory value");
    check(guest.reads.size()==3 && guest.writes.size()==1 &&
          guest.writes[0]==0x00710004u,"setter memory traffic/order");
    check(fs.reads32.size()==(selector<2u?2u:1u),"setter conditional FS28");
    check(c.flags.cf==(selector<2u) && c.flags.zf==(selector==2u),
          "setter cmp flags");
}
int main() {
    try {
        test_one(0u);test_one(1u);test_one(2u);test_one(3u);test_one(0x80u);
        for(unsigned int n=0;n<256u;++n){
            const merc360_v7q::Flags f=merc360_v7q::cmp_al_2(static_cast<uint8_t>(n));
            const uint8_t delta=static_cast<uint8_t>(n-2u);
            unsigned int bits=0;
            for(unsigned int b=0;b<8u;++b)bits+=(delta>>b)&1u;
            check(f.cf==(n<2u) && f.zf==(delta==0u) &&
                  f.sf==((delta&0x80u)!=0u) && f.pf==((bits%2u)==0u) &&
                  f.af==(((n^2u^delta)&0x10u)!=0u) &&
                  f.of==(((n^2u)&(n^delta)&0x80u)!=0u),
                  "all 256 byte compare flags");
        }
        bool hard_fence=false;
        try{
            Guest invalid;
            Fs fs={2u,0x00700040u,0u};
            merc360_v7q::Cpu c={0,0,0,{}};
            merc360_v7q::RetailTlsX86<Guest,Fs>::get(c,invalid,fs);
        }catch(const std::runtime_error&){hard_fence=true;}
        check(hard_fence,"unmapped memory still hard-fenced");
        puts("[K1-V7Q] HOST PASS: 2 original x86 functions, FS24/FS28/FS4, 256 CMP flags, signed index, guest fence");
        puts("[K1-V7Q] SOURCE ONLY: final runtime FS/CPU flag/RET binding NOT YET INTEGRATED; NO XDK/XBOX");
        return 0;
    } catch(const std::exception& e){
        fprintf(stderr,"[K1-V7Q] TEST FAIL: %s\n",e.what());return 1;
    }
}

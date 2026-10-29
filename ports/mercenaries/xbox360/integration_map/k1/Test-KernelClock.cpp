#include "KernelClockCore.h"
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
using merc360_k1::TimeFields;
static uint64_t encode(int y,int mo,int d,int h=0,int mi=0,int s=0,int ms=0) {
    TimeFields x={ (int16_t)y,(int16_t)mo,(int16_t)d,(int16_t)h,(int16_t)mi,(int16_t)s,(int16_t)ms,0 };
    uint64_t ticks=UINT64_MAX;
    assert(merc360_k1::to_ticks(x,&ticks));
    TimeFields back={};assert(merc360_k1::from_ticks(ticks,&back));
    assert(back.year==x.year && back.month==x.month && back.day==x.day);
    assert(back.hour==x.hour && back.minute==x.minute && back.second==x.second);
    assert(back.milliseconds==x.milliseconds);
    return ticks;
}
int main() {
    assert(encode(1601,1,1)==0u);
    TimeFields first={};assert(merc360_k1::from_ticks(0,&first));
    assert(first.weekday==1);
    assert(encode(1970,1,1)==UINT64_C(116444736000000000));
    assert(encode(2000,2,29)>encode(2000,2,28));
    assert(encode(2024,2,29)+merc360_k1::TICKS_DAY==encode(2024,3,1));
    assert(encode(9999,12,31,23,59,59,999)>0u);
    assert(!merc360_k1::from_ticks(UINT64_MAX,&first));
    TimeFields bad={1900,2,29,0,0,0,0,0};uint64_t v=42;
    assert(!merc360_k1::to_ticks(bad,&v) && v==42);
    bad.year=2100;assert(!merc360_k1::to_ticks(bad,&v));
    bad.year=2000;assert(merc360_k1::to_ticks(bad,&v));
    bad.year=1600;assert(!merc360_k1::to_ticks(bad,&v));
    bad.year=2026;bad.month=13;assert(!merc360_k1::to_ticks(bad,&v));
    bad.month=10;bad.day=29;bad.hour=24;assert(!merc360_k1::to_ticks(bad,&v));
    bad.hour=23;bad.minute=60;assert(!merc360_k1::to_ticks(bad,&v));
    bad.minute=59;bad.second=60;assert(!merc360_k1::to_ticks(bad,&v));
    bad.second=59;bad.milliseconds=1000;assert(!merc360_k1::to_ticks(bad,&v));
    assert(!merc360_k1::to_ticks(bad,0));
    assert(!merc360_k1::from_ticks(v,0));
    for(int y=1601;y<=9999;y+=37) {
      for(int m=1;m<=12;m++) {
        int d=merc360_k1::month_length(y,m);
        uint64_t t=encode(y,m,d,23,59,59,999);
        TimeFields round={};assert(merc360_k1::from_ticks(t,&round));
        assert(round.weekday>=0 && round.weekday<=6);
        assert((t%merc360_k1::TICKS_SECOND)==UINT64_C(9990000));
      }
    }
    puts("[K1A] PASS: host native C++ calendar/100ns round-trip and invalid cases");
    return 0;
}

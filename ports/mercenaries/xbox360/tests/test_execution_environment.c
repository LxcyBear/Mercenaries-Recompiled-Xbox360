/*
 * Portable Phase 2E execution-environment contract test.
 * No Xbox SDK or retail game content required.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RAM_SIZE          0x04000000u
#define RAM_MASK          0x03FFFFFFu
#define MIRROR_END        0x74000000u
#define KSEG_BASE         0x80000000u
#define KSEG_END          0xC0000000u
#define SYNTH_FENCE_BASE  0x80000000u
#define SYNTH_FENCE_END   0x80001000u
#define SYNTH_KERNEL_BASE 0x80010000u
#define SYNTH_KERNEL_END  0x80011000u

#define FAKE_TLS_VA       0x00700000u
#define FAKE_KTHREAD_VA   0x00760000u
#define KERNEL_DATA_BASE  0x0087E000u
#define KERNEL_DATA_SIZE  0x00001000u
#define STACK_BASE        0x00880000u
#define STACK_SIZE        0x00040000u
#define STACK_TOP         0x008BFFF0u
#define HEAP_BASE         0x008C0000u

#define KDATA_HW          0x000u
#define KDATA_VER         0x010u

#define CHECK(x) do { if (!(x)) { \
    fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); return 1; } } while(0)

static int offset_for(uint32_t a, uint32_t w, uint32_t *o)
{
    uint32_t off;
    if (!o || !w) return 0;
    if (a < MIRROR_END) {
        off = a & RAM_MASK;
    } else if (a >= KSEG_BASE && a < KSEG_END) {
        if ((a >= SYNTH_FENCE_BASE && a < SYNTH_FENCE_END) ||
            (a >= SYNTH_KERNEL_BASE && a < SYNTH_KERNEL_END))
            return 0;
        off = a & RAM_MASK;
    } else {
        return 0;
    }
    if (w > RAM_SIZE - off) return 0;
    *o = off;
    return 1;
}

static uint8_t *ptr(uint8_t *ram, uint32_t a, uint32_t w)
{
    uint32_t off;
    return offset_for(a,w,&off) ? ram+off : NULL;
}

static void w16(uint8_t *p,uint16_t v)
{
    p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8);
}
static uint16_t r16(const uint8_t *p)
{
    return (uint16_t)(p[0] | ((uint16_t)p[1]<<8));
}
static void w32(uint8_t *p,uint32_t v)
{
    p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8);
    p[2]=(uint8_t)(v>>16); p[3]=(uint8_t)(v>>24);
}
static uint32_t r32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
           ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}

int main(void)
{
    uint8_t *ram=(uint8_t*)calloc(1,RAM_SIZE);
    uint32_t tls_raw_size=12u;
    uint32_t tls_zero_size=20u;
    uint32_t aligned=(tls_raw_size+tls_zero_size+15u)&~15u;
    uint32_t block=4u+aligned;
    uint32_t tls_index_addr=0x0030B700u;
    uint32_t neg_index=0u-(block/4u);
    uint32_t base_field=FAKE_TLS_VA+block;
    int32_t signed_index=(int32_t)neg_index;
    uint32_t resolved=(uint32_t)((int32_t)base_field + signed_index*4);
    uint32_t esp=STACK_TOP;
    uint8_t raw[12]={1,2,3,4,5,6,7,8,9,10,11,12};
    uint8_t *tls;
    uint8_t *kd;

    CHECK(ram);
    CHECK(STACK_BASE+STACK_SIZE==HEAP_BASE);
    CHECK((STACK_TOP&15u)==0u);
    CHECK(KERNEL_DATA_BASE+KERNEL_DATA_SIZE<=STACK_BASE);

    tls=ptr(ram,FAKE_TLS_VA,block);
    CHECK(tls);
    memset(tls,0,block);
    w32(tls,FAKE_TLS_VA+4u);
    memcpy(tls+4u,raw,sizeof(raw));

    w32(ptr(ram,0x00u,4u),0xFFFFFFFFu);
    w32(ptr(ram,0x04u,4u),base_field);
    w32(ptr(ram,0x08u,4u),STACK_BASE);
    w32(ptr(ram,0x28u,4u),FAKE_KTHREAD_VA);
    w32(ptr(ram,FAKE_KTHREAD_VA+0x28u,4u),FAKE_TLS_VA);
    w32(ptr(ram,tls_index_addr,4u),neg_index);

    CHECK(r32(ptr(ram,0x00u,4u))==0xFFFFFFFFu);
    CHECK(r32(ptr(ram,0x28u,4u))==FAKE_KTHREAD_VA);
    CHECK(r32(ptr(ram,FAKE_KTHREAD_VA+0x28u,4u))==FAKE_TLS_VA);
    CHECK(r32(ptr(ram,FAKE_TLS_VA,4u))==FAKE_TLS_VA+4u);
    CHECK(resolved==FAKE_TLS_VA);
    CHECK(memcmp(ptr(ram,FAKE_TLS_VA+4u,sizeof(raw)),raw,sizeof(raw))==0);

    {
        uint32_t i;
        for(i=4u+sizeof(raw); i<block; ++i) CHECK(tls[i]==0u);
    }

    CHECK(r32(ptr(ram,0x04000004u,4u))==base_field);

    kd=ptr(ram,KERNEL_DATA_BASE,KERNEL_DATA_SIZE);
    CHECK(kd);
    memset(kd,0,KERNEL_DATA_SIZE);
    w32(kd+KDATA_HW,0u);
    kd[KDATA_HW+4u]=0xA1u;
    kd[KDATA_HW+5u]=0xB1u;
    w16(kd+KDATA_VER+0u,1u);
    w16(kd+KDATA_VER+2u,0u);
    w16(kd+KDATA_VER+4u,5849u);
    w16(kd+KDATA_VER+6u,0u);

    CHECK(r16(ptr(ram,KERNEL_DATA_BASE+KDATA_VER+4u,2u))==5849u);
    CHECK(r16(ptr(ram,0x0487E014u,2u))==5849u);
    CHECK(r16(ptr(ram,0x8087E014u,2u))==5849u);

    esp-=4u;
    w32(ptr(ram,esp,4u),0xC0DEF00Du);
    CHECK(r32(ptr(ram,esp,4u))==0xC0DEF00Du);
    esp+=4u;
    CHECK(esp==STACK_TOP);

    free(ram);
    puts("PASS: Phase 2E execution-environment contract");
    return 0;
}

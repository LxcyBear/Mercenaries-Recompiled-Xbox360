#include "phase6_oracle.h"

#include <stdio.h>
#include <stdlib.h>

static FILE *g_phase6_oracle_file;
static int g_phase6_oracle_initialized;
static uint64_t g_phase6_oracle_seq;

static void phase6_oracle_init(void)
{
    const char *path;

    if (g_phase6_oracle_initialized)
        return;
    g_phase6_oracle_initialized = 1;

    path = getenv("MERCENARIES_PHASE6_ORACLE_PATH");
    if (!path || !path[0])
        return;

#if defined(_MSC_VER)
    if (fopen_s(&g_phase6_oracle_file, path, "wb") != 0)
        g_phase6_oracle_file = NULL;
#else
    g_phase6_oracle_file = fopen(path, "wb");
#endif
    if (g_phase6_oracle_file) {
        setvbuf(g_phase6_oracle_file, NULL, _IOLBF, 0);
        fprintf(g_phase6_oracle_file,
                "{\"seq\":0,\"kind\":\"session\","
                "\"format\":\"merc360-phase6-oracle-v1\"}\n");
        fflush(g_phase6_oracle_file);
    }
}

int phase6_oracle_enabled(void)
{
    phase6_oracle_init();
    return g_phase6_oracle_file != NULL;
}

void phase6_oracle_shutdown(void)
{
    if (g_phase6_oracle_file) {
        fflush(g_phase6_oracle_file);
        fclose(g_phase6_oracle_file);
        g_phase6_oracle_file = NULL;
    }
}

static uint64_t phase6_oracle_next_seq(void)
{
    ++g_phase6_oracle_seq;
    return g_phase6_oracle_seq;
}

void phase6_oracle_pfifo(uint32_t submission,
                         uint32_t get,
                         uint32_t put,
                         uint32_t dma_instance,
                         uint32_t dma_base,
                         uint32_t dma_length)
{
    if (!phase6_oracle_enabled())
        return;

    fprintf(g_phase6_oracle_file,
            "{\"seq\":%llu,\"kind\":\"pfifo\","
            "\"submission\":%u,\"get\":\"0x%08X\","
            "\"put\":\"0x%08X\",\"dma_instance\":\"0x%08X\","
            "\"dma_base\":\"0x%08X\",\"dma_length\":%u}\n",
            (unsigned long long)phase6_oracle_next_seq(),
            submission, get, put, dma_instance, dma_base, dma_length);
}

void phase6_oracle_pgraph(uint32_t sequence,
                          uint32_t subchannel,
                          uint32_t method,
                          uint32_t value,
                          uint32_t graphics_class)
{
    if (!phase6_oracle_enabled())
        return;

    fprintf(g_phase6_oracle_file,
            "{\"seq\":%llu,\"kind\":\"pgraph\","
            "\"sequence\":%u,\"subchannel\":%u,"
            "\"method\":\"0x%04X\",\"value\":\"0x%08X\","
            "\"graphics_class\":\"0x%02X\"}\n",
            (unsigned long long)phase6_oracle_next_seq(),
            sequence, subchannel, method, value, graphics_class);
}

#ifndef MERCENARIES_PHASE6_ORACLE_H
#define MERCENARIES_PHASE6_ORACLE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

int phase6_oracle_enabled(void);
void phase6_oracle_shutdown(void);

void phase6_oracle_pfifo(uint32_t submission,
                         uint32_t get,
                         uint32_t put,
                         uint32_t dma_instance,
                         uint32_t dma_base,
                         uint32_t dma_length);

void phase6_oracle_pgraph(uint32_t sequence,
                          uint32_t subchannel,
                          uint32_t method,
                          uint32_t value,
                          uint32_t graphics_class);

#ifdef __cplusplus
}
#endif

#endif

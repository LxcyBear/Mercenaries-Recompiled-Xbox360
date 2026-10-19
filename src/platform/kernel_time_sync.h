/*
 * kernel_time_sync.h - host/Xenon timing and synchronization boundary.
 *
 * Phase 4B-A routes guest-kernel timing/synchronization services through this
 * small platform layer. The _XBOX backend uses XDK primitives proven on real
 * Xenon hardware; desktop/POSIX builds retain their existing host primitives.
 */
#ifndef XBOX_KERNEL_TIME_SYNC_H
#define XBOX_KERNEL_TIME_SYNC_H

#if defined(_XBOX)
#include <xtl.h>
#else
#include "xbox_winnt.h"
#if !defined(_WIN32)
#include "win32_compat.h"
#endif
#endif

#ifdef __cplusplus
extern "C" {
#endif

BOOL  merc_platform_query_performance_counter(PLARGE_INTEGER value);
BOOL  merc_platform_query_performance_frequency(PLARGE_INTEGER value);
DWORD merc_platform_get_tick_count(void);
void  merc_platform_query_system_time(PLARGE_INTEGER value);
DWORD merc_platform_sleep(DWORD milliseconds, BOOL alertable);
BOOL  merc_platform_set_event(HANDLE event_handle);
DWORD merc_platform_wait_single(HANDLE handle, DWORD milliseconds, BOOL alertable);
void  merc_platform_stall_us(DWORD microseconds);

#ifdef __cplusplus
}
#endif

#endif

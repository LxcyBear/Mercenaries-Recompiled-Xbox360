#include "kernel_time_sync.h"

BOOL merc_platform_query_performance_counter(PLARGE_INTEGER value)
{
    return QueryPerformanceCounter(value);
}

BOOL merc_platform_query_performance_frequency(PLARGE_INTEGER value)
{
    return QueryPerformanceFrequency(value);
}

DWORD merc_platform_get_tick_count(void)
{
    return GetTickCount();
}

void merc_platform_query_system_time(PLARGE_INTEGER value)
{
    if (value)
        GetSystemTimeAsFileTime((LPFILETIME)value);
}

DWORD merc_platform_sleep(DWORD milliseconds, BOOL alertable)
{
    if (alertable)
        return SleepEx(milliseconds, TRUE);
    Sleep(milliseconds);
    return 0u;
}

BOOL merc_platform_set_event(HANDLE event_handle)
{
    return SetEvent(event_handle);
}

DWORD merc_platform_wait_single(HANDLE handle, DWORD milliseconds, BOOL alertable)
{
    return WaitForSingleObjectEx(handle, milliseconds, alertable);
}

void merc_platform_stall_us(DWORD microseconds)
{
    LARGE_INTEGER frequency, start, now;
    LONGLONG target_counts;

    if (microseconds == 0u)
        return;
    if (!merc_platform_query_performance_frequency(&frequency) ||
        frequency.QuadPart <= 0 ||
        !merc_platform_query_performance_counter(&start))
        return;

    target_counts = (frequency.QuadPart * (LONGLONG)microseconds) / 1000000LL;
    if (target_counts <= 0)
        target_counts = 1;

    do {
        merc_platform_query_performance_counter(&now);
    } while ((now.QuadPart - start.QuadPart) < target_counts);
}

/*
 * Mercenaries Xbox 360 - Phase 4B-A native timing/synchronization gate.
 *
 * This is a self-contained XDK hardware proof. It does not load or execute
 * Mercenaries. It proves the native Xbox 360 primitives needed to replace the
 * remaining host-backed timing/synchronization guest-kernel paths.
 */

#include <xtl.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>

#define P4B_BUILD_TAG "P4B-TIMESYNC-20261019-A"

static HANDLE s_logFile = INVALID_HANDLE_VALUE;
static int s_failures = 0;

static void trace_line(const char* line)
{
    DWORD written = 0;
    OutputDebugStringA("[Merc360:P4B] ");
    OutputDebugStringA(line);
    OutputDebugStringA("\r\n");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        WriteFile(s_logFile, line, (DWORD)strlen(line), &written, NULL);
        WriteFile(s_logFile, "\r\n", 2, &written, NULL);
        FlushFileBuffers(s_logFile);
    }
}

static void tracef(const char* fmt, ...)
{
    char buffer[512];
    va_list args;
    va_start(args, fmt);
    _vsnprintf(buffer, sizeof(buffer) - 1, fmt, args);
    va_end(args);
    buffer[sizeof(buffer) - 1] = '\0';
    trace_line(buffer);
}

static void check_result(BOOL condition, const char* name)
{
    if (condition)
        tracef("PASS: %s", name);
    else
    {
        tracef("FAIL: %s", name);
        ++s_failures;
    }
}

static unsigned __int64 li_to_u64(const LARGE_INTEGER* value)
{
    return ((unsigned __int64)(DWORD)value->HighPart << 32) |
           (unsigned __int64)value->LowPart;
}

static unsigned __int64 filetime_to_u64(const FILETIME* value)
{
    return ((unsigned __int64)value->dwHighDateTime << 32) |
           (unsigned __int64)value->dwLowDateTime;
}

static unsigned __int64 qpc_elapsed_us(
    const LARGE_INTEGER* start,
    const LARGE_INTEGER* end,
    const LARGE_INTEGER* frequency)
{
    const unsigned __int64 a = li_to_u64(start);
    const unsigned __int64 b = li_to_u64(end);
    const unsigned __int64 f = li_to_u64(frequency);

    if (f == 0 || b < a)
        return 0;

    return ((b - a) * 1000000ui64) / f;
}

static DWORD relative_100ns_to_ms(__int64 interval)
{
    unsigned __int64 ticks;

    if (interval >= 0)
        return 0;

    ticks = (unsigned __int64)(-interval);
    ticks = (ticks + 9999ui64) / 10000ui64;
    if (ticks > 0xFFFFFFFFui64)
        return INFINITE;

    return (DWORD)ticks;
}

static void native_delay_relative(__int64 interval)
{
    DWORD milliseconds = relative_100ns_to_ms(interval);
    if (milliseconds != 0)
        Sleep(milliseconds);
    else
        SwitchToThread();
}

static void native_stall_us(DWORD microseconds)
{
    LARGE_INTEGER frequency;
    LARGE_INTEGER start;
    LARGE_INTEGER now;
    unsigned __int64 target;
    unsigned __int64 begin;
    unsigned __int64 current;

    if (microseconds == 0)
        return;

    if (!QueryPerformanceFrequency(&frequency) ||
        !QueryPerformanceCounter(&start))
        return;

    target = (li_to_u64(&frequency) * microseconds) / 1000000ui64;
    if (target == 0)
        target = 1;

    begin = li_to_u64(&start);
    do
    {
        QueryPerformanceCounter(&now);
        current = li_to_u64(&now);
    } while (current - begin < target);
}

typedef struct P4B_TIMER
{
    HANDLE Event;
    HANDLE Thread;
    volatile LONG Armed;
    DWORD DueMs;
} P4B_TIMER;

static DWORD WINAPI timer_thread_proc(LPVOID parameter)
{
    P4B_TIMER* timer = (P4B_TIMER*)parameter;
    Sleep(timer->DueMs);

    if (InterlockedCompareExchange(&timer->Armed, 1, 1) == 1)
        SetEvent(timer->Event);

    return 0;
}

static BOOL native_set_one_shot_timer(P4B_TIMER* timer, DWORD dueMs)
{
    DWORD threadId = 0;

    ZeroMemory(timer, sizeof(*timer));
    timer->Event = CreateEventA(NULL, FALSE, FALSE, NULL);
    if (!timer->Event)
        return FALSE;

    timer->DueMs = dueMs;
    timer->Armed = 1;
    timer->Thread = CreateThread(
        NULL, 0, timer_thread_proc, timer, 0, &threadId);

    if (!timer->Thread)
    {
        CloseHandle(timer->Event);
        timer->Event = NULL;
        return FALSE;
    }

    return TRUE;
}

static void native_timer_shutdown(P4B_TIMER* timer)
{
    if (!timer)
        return;

    InterlockedExchange(&timer->Armed, 0);

    if (timer->Thread)
    {
        WaitForSingleObject(timer->Thread, 1000);
        CloseHandle(timer->Thread);
    }

    if (timer->Event)
        CloseHandle(timer->Event);

    ZeroMemory(timer, sizeof(*timer));
}

static void test_performance_counter(void)
{
    LARGE_INTEGER frequency;
    LARGE_INTEGER a;
    LARGE_INTEGER b;

    check_result(QueryPerformanceFrequency(&frequency) != 0,
                 "QueryPerformanceFrequency available");
    check_result(li_to_u64(&frequency) != 0,
                 "performance-counter frequency is non-zero");

    QueryPerformanceCounter(&a);
    QueryPerformanceCounter(&b);

    tracef("QPC frequency=%I64u first=%I64u second=%I64u",
           li_to_u64(&frequency), li_to_u64(&a), li_to_u64(&b));

    check_result(li_to_u64(&b) >= li_to_u64(&a),
                 "performance counter is monotonic");
}

static void test_system_time(void)
{
    FILETIME a;
    FILETIME b;
    unsigned __int64 delta;

    GetSystemTimeAsFileTime(&a);
    Sleep(20);
    GetSystemTimeAsFileTime(&b);

    delta = filetime_to_u64(&b) - filetime_to_u64(&a);
    tracef("system-time delta=%I64u x100ns", delta);

    check_result(filetime_to_u64(&b) > filetime_to_u64(&a),
                 "system time advances");
    check_result(delta >= 100000ui64 && delta < 50000000ui64,
                 "system-time 20ms delay is plausible");
}

static void test_delay(void)
{
    LARGE_INTEGER frequency;
    LARGE_INTEGER a;
    LARGE_INTEGER b;
    unsigned __int64 elapsed;

    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&a);

    /* Original-Xbox relative interval: -200,000 * 100ns = 20 ms. */
    native_delay_relative(-200000i64);

    QueryPerformanceCounter(&b);
    elapsed = qpc_elapsed_us(&a, &b, &frequency);

    tracef("relative-delay elapsed=%I64u us", elapsed);
    check_result(elapsed >= 10000ui64 && elapsed < 500000ui64,
                 "relative 20ms delay");
}

static void test_stall(void)
{
    LARGE_INTEGER frequency;
    LARGE_INTEGER a;
    LARGE_INTEGER b;
    unsigned __int64 elapsed;

    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&a);
    native_stall_us(2000);
    QueryPerformanceCounter(&b);

    elapsed = qpc_elapsed_us(&a, &b, &frequency);
    tracef("stall-2000us elapsed=%I64u us", elapsed);

    check_result(elapsed >= 1000ui64 && elapsed < 500000ui64,
                 "2ms processor stall");
}

static void test_event_and_wait(void)
{
    HANDLE eventHandle;
    DWORD result;

    eventHandle = CreateEventA(NULL, FALSE, FALSE, NULL);
    check_result(eventHandle != NULL, "auto-reset event creation");
    if (!eventHandle)
        return;

    result = WaitForSingleObject(eventHandle, 0);
    check_result(result == WAIT_TIMEOUT, "unsignaled event zero-timeout");

    check_result(SetEvent(eventHandle) != 0, "SetEvent signals event");

    result = WaitForSingleObject(eventHandle, 100);
    check_result(result == WAIT_OBJECT_0, "wait observes signaled event");

    result = WaitForSingleObject(eventHandle, 0);
    check_result(result == WAIT_TIMEOUT, "auto-reset event consumed by wait");

    CloseHandle(eventHandle);
}

static void test_wait_timeout(void)
{
    HANDLE eventHandle;
    LARGE_INTEGER frequency;
    LARGE_INTEGER a;
    LARGE_INTEGER b;
    unsigned __int64 elapsed;
    DWORD result;

    eventHandle = CreateEventA(NULL, FALSE, FALSE, NULL);
    check_result(eventHandle != NULL, "timeout event creation");
    if (!eventHandle)
        return;

    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&a);
    result = WaitForSingleObject(eventHandle, 20);
    QueryPerformanceCounter(&b);

    elapsed = qpc_elapsed_us(&a, &b, &frequency);
    tracef("wait-timeout result=%08X elapsed=%I64u us", result, elapsed);

    check_result(result == WAIT_TIMEOUT, "20ms wait returns timeout");
    check_result(elapsed >= 10000ui64 && elapsed < 500000ui64,
                 "20ms wait duration is plausible");

    CloseHandle(eventHandle);
}

static void test_one_shot_timer(void)
{
    P4B_TIMER timer;
    LARGE_INTEGER frequency;
    LARGE_INTEGER a;
    LARGE_INTEGER b;
    unsigned __int64 elapsed;
    DWORD result;

    check_result(native_set_one_shot_timer(&timer, 25),
                 "one-shot timer creation");
    if (!timer.Event)
        return;

    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&a);
    result = WaitForSingleObject(timer.Event, 500);
    QueryPerformanceCounter(&b);

    elapsed = qpc_elapsed_us(&a, &b, &frequency);
    tracef("one-shot timer wait=%08X elapsed=%I64u us", result, elapsed);

    check_result(result == WAIT_OBJECT_0, "one-shot timer signals event");
    check_result(elapsed >= 10000ui64 && elapsed < 500000ui64,
                 "one-shot timer due time is plausible");
    check_result(WaitForSingleObject(timer.Event, 0) == WAIT_TIMEOUT,
                 "one-shot timer event auto-resets");

    native_timer_shutdown(&timer);
}

VOID __cdecl main()
{
    DWORD started;
    DWORD nextHeartbeat = 1000;

    s_logFile = CreateFileA(
        "game:\\merc360-phase4b-time-sync.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace_line("PHASE 4B-A NATIVE TIME/SYNC HARDWARE GATE START");
    tracef("BUILD TAG: %s", P4B_BUILD_TAG);

    test_performance_counter();
    test_system_time();
    test_delay();
    test_stall();
    test_event_and_wait();
    test_wait_timeout();
    test_one_shot_timer();

    if (s_failures == 0)
        trace_line("PHASE 4B-A NATIVE TIME/SYNC RESULT: PASS");
    else
        tracef("PHASE 4B-A NATIVE TIME/SYNC RESULT: FAIL (%d failures)", s_failures);

    trace_line("Press A to exit, or automatic exit after 10 seconds");
    started = GetTickCount();

    for (;;)
    {
        XINPUT_STATE state;
        DWORD elapsed = GetTickCount() - started;

        if (elapsed >= 10000)
            break;

        ZeroMemory(&state, sizeof(state));
        if (XInputGetState(0, &state) == ERROR_SUCCESS &&
            (state.Gamepad.wButtons & XINPUT_GAMEPAD_A) != 0)
            break;

        if (elapsed >= nextHeartbeat)
        {
            trace_line("POST-TEST HEARTBEAT");
            nextHeartbeat += 1000;
        }

        Sleep(33);
    }

    trace_line("PHASE 4B-A NATIVE TIME/SYNC HARDWARE GATE END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

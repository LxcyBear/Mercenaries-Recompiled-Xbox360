/*
 * Mercenaries Xbox 360 - Phase 4B-B native file/handle hardware gate.
 *
 * Self-contained XDK proof. This does not execute Mercenaries. It validates
 * the Xenon/XDK file primitives required by the retail guest file bridges
 * before the production runtime is migrated behind a platform boundary.
 */

#include <xtl.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>

#define P4B_FILE_BUILD_TAG "P4B-FILE-20261019-A"

#ifndef INVALID_FILE_ATTRIBUTES
#define INVALID_FILE_ATTRIBUTES ((DWORD)0xFFFFFFFFu)
#endif

static HANDLE s_logFile = INVALID_HANDLE_VALUE;
static int s_failures = 0;

static const char* kTestDir = "game:\\merc360-p4b-file";
static const char* kTestFile = "game:\\merc360-p4b-file\\sample.bin";
static const char* kMissingFile = "game:\\merc360-p4b-file\\missing.bin";

static void trace_line(const char* line)
{
    DWORD written = 0;

    OutputDebugStringA("[Merc360:P4B-FILE] ");
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

static unsigned __int64 make_u64(DWORD low, DWORD high)
{
    return ((unsigned __int64)high << 32) | (unsigned __int64)low;
}

static BOOL seek_absolute(HANDLE handle, unsigned __int64 offset)
{
    LONG high = (LONG)(offset >> 32);
    DWORD low;

    SetLastError(ERROR_SUCCESS);
    low = SetFilePointer(
        handle,
        (LONG)(offset & 0xFFFFFFFFui64),
        &high,
        FILE_BEGIN);

    if (low == INVALID_SET_FILE_POINTER && GetLastError() != ERROR_SUCCESS)
        return FALSE;

    return TRUE;
}

static BOOL query_current_offset(HANDLE handle, unsigned __int64* offset)
{
    LONG high = 0;
    DWORD low;

    if (!offset)
        return FALSE;

    SetLastError(ERROR_SUCCESS);
    low = SetFilePointer(handle, 0, &high, FILE_CURRENT);
    if (low == INVALID_SET_FILE_POINTER && GetLastError() != ERROR_SUCCESS)
        return FALSE;

    *offset = make_u64(low, (DWORD)high);
    return TRUE;
}

static BOOL query_size(HANDLE handle, unsigned __int64* size)
{
    DWORD high = 0;
    DWORD low;

    if (!size)
        return FALSE;

    SetLastError(ERROR_SUCCESS);
    low = GetFileSize(handle, &high);
    if (low == INVALID_FILE_SIZE && GetLastError() != ERROR_SUCCESS)
        return FALSE;

    *size = make_u64(low, high);
    return TRUE;
}

static void fill_pattern(BYTE* data, DWORD length)
{
    DWORD i;
    for (i = 0; i < length; ++i)
        data[i] = (BYTE)((i * 37u + 11u) & 0xFFu);
}

static void ensure_clean_test_area(void)
{
    DeleteFileA(kTestFile);
    RemoveDirectoryA(kTestDir);

    if (!CreateDirectoryA(kTestDir, NULL))
    {
        DWORD error = GetLastError();
        check_result(error == ERROR_ALREADY_EXISTS,
                     "test directory create/existing");
    }
    else
    {
        check_result(TRUE, "test directory create/existing");
    }
}

static void test_create_write_read_query(void)
{
    BYTE pattern[64];
    BYTE readback[64];
    HANDLE handle;
    DWORD transferred = 0;
    unsigned __int64 size = 0;
    unsigned __int64 position = 0;
    BY_HANDLE_FILE_INFORMATION information;

    fill_pattern(pattern, sizeof(pattern));
    ZeroMemory(readback, sizeof(readback));

    handle = CreateFileA(
        kTestFile,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    check_result(handle != INVALID_HANDLE_VALUE, "CreateFileA CREATE_ALWAYS");
    if (handle == INVALID_HANDLE_VALUE)
    {
        tracef("CreateFileA failed error=%lu", GetLastError());
        return;
    }

    check_result(
        WriteFile(handle, pattern, sizeof(pattern), &transferred, NULL) != 0 &&
        transferred == sizeof(pattern),
        "WriteFile writes full payload");

    check_result(FlushFileBuffers(handle) != 0,
                 "FlushFileBuffers succeeds");

    check_result(
        query_size(handle, &size) && size == sizeof(pattern),
        "GetFileSize reports written payload");

    ZeroMemory(&information, sizeof(information));
    check_result(
        GetFileInformationByHandle(handle, &information) != 0 &&
        make_u64(information.nFileSizeLow, information.nFileSizeHigh) ==
            sizeof(pattern),
        "GetFileInformationByHandle reports size");

    check_result(seek_absolute(handle, 0), "SetFilePointer seek begin");

    transferred = 0;
    check_result(
        ReadFile(handle, readback, sizeof(readback), &transferred, NULL) != 0 &&
        transferred == sizeof(readback) &&
        memcmp(pattern, readback, sizeof(pattern)) == 0,
        "ReadFile round-trip payload");

    check_result(seek_absolute(handle, 16), "SetFilePointer explicit offset");

    ZeroMemory(readback, sizeof(readback));
    transferred = 0;
    check_result(
        ReadFile(handle, readback, 8, &transferred, NULL) != 0 &&
        transferred == 8 &&
        memcmp(pattern + 16, readback, 8) == 0,
        "ReadFile explicit-offset data");

    check_result(
        query_current_offset(handle, &position) && position == 24,
        "FILE_CURRENT observes read position");

    check_result(seek_absolute(handle, 24), "seek before SetEndOfFile");
    check_result(SetEndOfFile(handle) != 0, "SetEndOfFile truncates file");

    check_result(
        query_size(handle, &size) && size == 24,
        "truncated size is 24 bytes");

    check_result(CloseHandle(handle) != 0, "CloseHandle closes created file");
}

static void test_open_existing_and_attributes(void)
{
    HANDLE handle;
    DWORD attrs;
    unsigned __int64 size = 0;
    BY_HANDLE_FILE_INFORMATION information;

    handle = CreateFileA(
        kTestFile,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    check_result(handle != INVALID_HANDLE_VALUE, "CreateFileA OPEN_EXISTING");
    if (handle == INVALID_HANDLE_VALUE)
    {
        tracef("OPEN_EXISTING failed error=%lu", GetLastError());
        return;
    }

    check_result(
        query_size(handle, &size) && size == 24,
        "reopened file preserves truncated size");

    ZeroMemory(&information, sizeof(information));
    check_result(
        GetFileInformationByHandle(handle, &information) != 0,
        "reopened handle information query");

    attrs = GetFileAttributesA(kTestFile);
    check_result(
        attrs != INVALID_FILE_ATTRIBUTES &&
        (attrs & FILE_ATTRIBUTE_DIRECTORY) == 0,
        "GetFileAttributesA identifies regular file");

    check_result(CloseHandle(handle) != 0, "CloseHandle closes reopened file");
}

static void test_directory_enumeration(void)
{
    WIN32_FIND_DATAA data;
    HANDLE findHandle;
    BOOL found = FALSE;

    ZeroMemory(&data, sizeof(data));
    findHandle = FindFirstFileA(
        "game:\\merc360-p4b-file\\*",
        &data);

    check_result(findHandle != INVALID_HANDLE_VALUE,
                 "FindFirstFileA opens directory enumeration");
    if (findHandle == INVALID_HANDLE_VALUE)
    {
        tracef("FindFirstFileA failed error=%lu", GetLastError());
        return;
    }

    do
    {
        if (strcmp(data.cFileName, "sample.bin") == 0)
        {
            found = TRUE;
            break;
        }
    } while (FindNextFileA(findHandle, &data));

    check_result(found, "directory enumeration finds sample.bin");
    check_result(FindClose(findHandle) != 0, "FindClose closes enumeration");
}

static void test_missing_file_failure(void)
{
    HANDLE handle;
    DWORD error;

    SetLastError(ERROR_SUCCESS);
    handle = CreateFileA(
        kMissingFile,
        GENERIC_READ,
        FILE_SHARE_READ,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        NULL);
    error = GetLastError();

    check_result(handle == INVALID_HANDLE_VALUE,
                 "missing OPEN_EXISTING fails");
    check_result(
        error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND,
        "missing file returns not-found error");

    if (handle != INVALID_HANDLE_VALUE)
        CloseHandle(handle);
}

static void cleanup_test_area(void)
{
    check_result(DeleteFileA(kTestFile) != 0,
                 "DeleteFileA removes test file");
    check_result(RemoveDirectoryA(kTestDir) != 0,
                 "RemoveDirectoryA removes test directory");
}

VOID __cdecl main()
{
    DWORD started;
    DWORD nextHeartbeat = 1000;

    s_logFile = CreateFileA(
        "game:\\merc360-phase4b-file-handles.log",
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);

    trace_line("PHASE 4B-B NATIVE FILE/HANDLE HARDWARE GATE START");
    tracef("BUILD TAG: %s", P4B_FILE_BUILD_TAG);

    ensure_clean_test_area();
    test_create_write_read_query();
    test_open_existing_and_attributes();
    test_directory_enumeration();
    test_missing_file_failure();
    cleanup_test_area();

    if (s_failures == 0)
        trace_line("PHASE 4B-B NATIVE FILE/HANDLE RESULT: PASS");
    else
        tracef("PHASE 4B-B NATIVE FILE/HANDLE RESULT: FAIL (%d failures)",
               s_failures);

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

    trace_line("PHASE 4B-B NATIVE FILE/HANDLE HARDWARE GATE END");

    if (s_logFile != INVALID_HANDLE_VALUE)
    {
        CloseHandle(s_logFile);
        s_logFile = INVALID_HANDLE_VALUE;
    }
}

#include "kernel_file_io.h"
#include <string.h>

#if defined(_XBOX)

static BOOL merc_wide_path_to_ansi(
    const WCHAR *wide, char *ansi, DWORD capacity)
{
    DWORD index = 0;

    if (!wide || !ansi || capacity == 0)
        return FALSE;

    while (wide[index] != 0) {
        unsigned int ch;
        if (index + 1 >= capacity)
            return FALSE;
        ch = (unsigned int)wide[index];
        if (ch > 0x7Fu)
            return FALSE;
        ansi[index] = (char)ch;
        ++index;
    }
    ansi[index] = '\0';
    return TRUE;
}

#define MERC_TRACKED_FILE_HANDLES 128

typedef struct MERC_TRACKED_FILE {
    HANDLE Handle;
    BOOL DeletePending;
    char Path[MAX_PATH];
} MERC_TRACKED_FILE;

static MERC_TRACKED_FILE s_tracked[MERC_TRACKED_FILE_HANDLES];
static volatile LONG s_track_lock;

static void merc_track_lock(void)
{
    while (InterlockedCompareExchange(&s_track_lock, 1, 0) != 0)
        Sleep(0);
}

static void merc_track_unlock(void)
{
    InterlockedExchange(&s_track_lock, 0);
}

static void merc_track_open(HANDLE handle, const char *path)
{
    int index;
    if (!handle || handle == INVALID_HANDLE_VALUE || !path)
        return;

    merc_track_lock();
    for (index = 0; index < MERC_TRACKED_FILE_HANDLES; ++index) {
        if (s_tracked[index].Handle == NULL) {
            s_tracked[index].Handle = handle;
            s_tracked[index].DeletePending = FALSE;
            strncpy(s_tracked[index].Path, path, MAX_PATH - 1);
            s_tracked[index].Path[MAX_PATH - 1] = '\0';
            break;
        }
    }
    merc_track_unlock();
}

static BOOL merc_track_path(HANDLE handle, char *path, DWORD capacity)
{
    int index;
    BOOL found = FALSE;

    if (!path || capacity == 0)
        return FALSE;

    merc_track_lock();
    for (index = 0; index < MERC_TRACKED_FILE_HANDLES; ++index) {
        if (s_tracked[index].Handle == handle) {
            strncpy(path, s_tracked[index].Path, capacity - 1);
            path[capacity - 1] = '\0';
            found = TRUE;
            break;
        }
    }
    merc_track_unlock();
    return found;
}

static BOOL merc_track_delete(HANDLE handle, BOOL delete_pending)
{
    int index;
    BOOL found = FALSE;

    merc_track_lock();
    for (index = 0; index < MERC_TRACKED_FILE_HANDLES; ++index) {
        if (s_tracked[index].Handle == handle) {
            s_tracked[index].DeletePending = delete_pending;
            found = TRUE;
            break;
        }
    }
    merc_track_unlock();
    return found;
}

static BOOL merc_track_take(
    HANDLE handle, char *path, DWORD capacity, BOOL *delete_pending)
{
    int index;
    BOOL found = FALSE;

    merc_track_lock();
    for (index = 0; index < MERC_TRACKED_FILE_HANDLES; ++index) {
        if (s_tracked[index].Handle == handle) {
            if (path && capacity) {
                strncpy(path, s_tracked[index].Path, capacity - 1);
                path[capacity - 1] = '\0';
            }
            if (delete_pending)
                *delete_pending = s_tracked[index].DeletePending;
            memset(&s_tracked[index], 0, sizeof(s_tracked[index]));
            found = TRUE;
            break;
        }
    }
    merc_track_unlock();
    return found;
}

#endif

DWORD merc_platform_file_last_error(void)
{
    return GetLastError();
}

void merc_platform_file_set_last_error(DWORD error)
{
    SetLastError(error);
}

DWORD merc_platform_file_get_attributes(const WCHAR *path)
{
#if defined(_XBOX)
    char ansi[MAX_PATH];
    if (!merc_wide_path_to_ansi(path, ansi, MAX_PATH))
        return MERC_PLATFORM_INVALID_FILE_ATTRIBUTES;
    return GetFileAttributesA(ansi);
#else
    return GetFileAttributesW(path);
#endif
}

BOOL merc_platform_file_create_directory(const WCHAR *path)
{
#if defined(_XBOX)
    char ansi[MAX_PATH];
    if (!merc_wide_path_to_ansi(path, ansi, MAX_PATH))
        return FALSE;
    return CreateDirectoryA(ansi, NULL);
#else
    return CreateDirectoryW(path, NULL);
#endif
}

HANDLE merc_platform_file_open(
    const WCHAR *path,
    DWORD desired_access,
    DWORD share_access,
    DWORD creation_disposition,
    DWORD flags_and_attributes)
{
#if defined(_XBOX)
    char ansi[MAX_PATH];
    HANDLE handle;

    if (!merc_wide_path_to_ansi(path, ansi, MAX_PATH))
        return INVALID_HANDLE_VALUE;

    handle = CreateFileA(
        ansi, desired_access, share_access, NULL,
        creation_disposition, flags_and_attributes, NULL);
    if (handle != INVALID_HANDLE_VALUE)
        merc_track_open(handle, ansi);
    return handle;
#else
    return CreateFileW(
        path, desired_access, share_access, NULL,
        creation_disposition, flags_and_attributes, NULL);
#endif
}

BOOL merc_platform_file_seek(
    HANDLE handle, LARGE_INTEGER distance,
    PLARGE_INTEGER new_position, DWORD move_method)
{
#if defined(_XBOX)
    LONG high = distance.HighPart;
    DWORD low;

    SetLastError(ERROR_SUCCESS);
    low = SetFilePointer(handle, distance.LowPart, &high, move_method);
    if (low == INVALID_SET_FILE_POINTER && GetLastError() != ERROR_SUCCESS)
        return FALSE;

    if (new_position) {
        new_position->LowPart = low;
        new_position->HighPart = high;
    }
    return TRUE;
#else
    return SetFilePointerEx(handle, distance, new_position, move_method);
#endif
}

BOOL merc_platform_file_read(
    HANDLE handle, PVOID buffer, DWORD length, LPDWORD bytes_read,
    const LARGE_INTEGER *byte_offset)
{
#if defined(_XBOX)
    LARGE_INTEGER zero, saved;
    BOOL result;

    if (!byte_offset)
        return ReadFile(handle, buffer, length, bytes_read, NULL);

    zero.QuadPart = 0;
    if (!merc_platform_file_seek(handle, zero, &saved, FILE_CURRENT))
        return FALSE;
    if (!merc_platform_file_seek(handle, *byte_offset, NULL, FILE_BEGIN))
        return FALSE;

    result = ReadFile(handle, buffer, length, bytes_read, NULL);
    merc_platform_file_seek(handle, saved, NULL, FILE_BEGIN);
    return result;
#else
    if (byte_offset) {
        OVERLAPPED ov;
        memset(&ov, 0, sizeof(ov));
        ov.Offset = byte_offset->LowPart;
        ov.OffsetHigh = byte_offset->HighPart;
        return ReadFile(handle, buffer, length, bytes_read, &ov);
    }
    return ReadFile(handle, buffer, length, bytes_read, NULL);
#endif
}

BOOL merc_platform_file_write(
    HANDLE handle, const VOID *buffer, DWORD length, LPDWORD bytes_written,
    const LARGE_INTEGER *byte_offset)
{
#if defined(_XBOX)
    LARGE_INTEGER zero, saved;
    BOOL result;

    if (!byte_offset)
        return WriteFile(handle, buffer, length, bytes_written, NULL);

    zero.QuadPart = 0;
    if (!merc_platform_file_seek(handle, zero, &saved, FILE_CURRENT))
        return FALSE;
    if (!merc_platform_file_seek(handle, *byte_offset, NULL, FILE_BEGIN))
        return FALSE;

    result = WriteFile(handle, buffer, length, bytes_written, NULL);
    merc_platform_file_seek(handle, saved, NULL, FILE_BEGIN);
    return result;
#else
    if (byte_offset) {
        OVERLAPPED ov;
        memset(&ov, 0, sizeof(ov));
        ov.Offset = byte_offset->LowPart;
        ov.OffsetHigh = byte_offset->HighPart;
        return WriteFile(handle, buffer, length, bytes_written, &ov);
    }
    return WriteFile(handle, buffer, length, bytes_written, NULL);
#endif
}

BOOL merc_platform_file_query_info(
    HANDLE handle, MERC_PLATFORM_FILE_INFO *info)
{
    BY_HANDLE_FILE_INFORMATION native_info;

    if (!info)
        return FALSE;
    memset(&native_info, 0, sizeof(native_info));
    if (!GetFileInformationByHandle(handle, &native_info))
        return FALSE;

    info->CreationTime = native_info.ftCreationTime;
    info->LastAccessTime = native_info.ftLastAccessTime;
    info->LastWriteTime = native_info.ftLastWriteTime;
    info->FileAttributes = native_info.dwFileAttributes;
    info->FileSizeHigh = native_info.nFileSizeHigh;
    info->FileSizeLow = native_info.nFileSizeLow;
    info->NumberOfLinks = native_info.nNumberOfLinks;
    return TRUE;
}

BOOL merc_platform_file_set_end(HANDLE handle)
{
    return SetEndOfFile(handle);
}

BOOL merc_platform_file_set_allocation(
    HANDLE handle, LARGE_INTEGER allocation_size)
{
#if defined(_XBOX)
    MERC_PLATFORM_FILE_INFO info;
    LARGE_INTEGER current, zero;
    unsigned __int64 current_size;
    unsigned __int64 requested_size;

    if (allocation_size.QuadPart < 0)
        return FALSE;
    if (!merc_platform_file_query_info(handle, &info))
        return FALSE;

    current_size =
        ((unsigned __int64)info.FileSizeHigh << 32) | info.FileSizeLow;
    requested_size = (unsigned __int64)allocation_size.QuadPart;

    if (requested_size >= current_size)
        return TRUE;

    zero.QuadPart = 0;
    if (!merc_platform_file_seek(handle, zero, &current, FILE_CURRENT))
        return FALSE;
    if (!merc_platform_file_seek(handle, allocation_size, NULL, FILE_BEGIN))
        return FALSE;
    if (!merc_platform_file_set_end(handle))
        return FALSE;
    if ((unsigned __int64)current.QuadPart <= requested_size)
        merc_platform_file_seek(handle, current, NULL, FILE_BEGIN);
    return TRUE;
#else
    FILE_ALLOCATION_INFO native_info;
    native_info.AllocationSize = allocation_size;
    return SetFileInformationByHandle(
        handle, FileAllocationInfo, &native_info, sizeof(native_info));
#endif
}

BOOL merc_platform_file_set_delete_pending(HANDLE handle, BOOL delete_file)
{
#if defined(_XBOX)
    return merc_track_delete(handle, delete_file);
#else
    FILE_DISPOSITION_INFO native_info;
    native_info.DeleteFile = delete_file;
    return SetFileInformationByHandle(
        handle, FileDispositionInfo, &native_info, sizeof(native_info));
#endif
}

BOOL merc_platform_file_set_times(
    HANDLE handle, const FILETIME *creation_time,
    const FILETIME *access_time, const FILETIME *write_time)
{
    return SetFileTime(handle, creation_time, access_time, write_time);
}

BOOL merc_platform_file_query_path_info(
    const WCHAR *path, MERC_PLATFORM_FILE_INFO *info)
{
#if defined(_XBOX)
    char ansi[MAX_PATH];
    HANDLE handle;
    BOOL result;

    if (!info || !merc_wide_path_to_ansi(path, ansi, MAX_PATH))
        return FALSE;

    handle = CreateFileA(
        ansi, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
    if (handle == INVALID_HANDLE_VALUE)
        return FALSE;

    result = merc_platform_file_query_info(handle, info);
    CloseHandle(handle);
    return result;
#else
    WIN32_FILE_ATTRIBUTE_DATA data;

    if (!info ||
        !GetFileAttributesExW(path, GetFileExInfoStandard, &data))
        return FALSE;

    info->CreationTime = data.ftCreationTime;
    info->LastAccessTime = data.ftLastAccessTime;
    info->LastWriteTime = data.ftLastWriteTime;
    info->FileAttributes = data.dwFileAttributes;
    info->FileSizeHigh = data.nFileSizeHigh;
    info->FileSizeLow = data.nFileSizeLow;
    info->NumberOfLinks = 1;
    return TRUE;
#endif
}

#if defined(_XBOX)
static void merc_copy_find_data(
    MERC_PLATFORM_FIND_DATA *out, const WIN32_FIND_DATAA *in)
{
    memset(out, 0, sizeof(*out));
    out->CreationTime = in->ftCreationTime;
    out->LastAccessTime = in->ftLastAccessTime;
    out->LastWriteTime = in->ftLastWriteTime;
    out->FileAttributes = in->dwFileAttributes;
    out->FileSizeHigh = in->nFileSizeHigh;
    out->FileSizeLow = in->nFileSizeLow;
    strncpy(out->FileName, in->cFileName, MAX_PATH - 1);
    out->FileName[MAX_PATH - 1] = '\0';
}
#else
static void merc_copy_find_data(
    MERC_PLATFORM_FIND_DATA *out, const WIN32_FIND_DATAW *in)
{
    int converted;

    memset(out, 0, sizeof(*out));
    out->CreationTime = in->ftCreationTime;
    out->LastAccessTime = in->ftLastAccessTime;
    out->LastWriteTime = in->ftLastWriteTime;
    out->FileAttributes = in->dwFileAttributes;
    out->FileSizeHigh = in->nFileSizeHigh;
    out->FileSizeLow = in->nFileSizeLow;
    converted = WideCharToMultiByte(
        CP_ACP, 0, in->cFileName, -1,
        out->FileName, MAX_PATH, NULL, NULL);
    if (converted <= 0)
        out->FileName[0] = '\0';
}
#endif

HANDLE merc_platform_file_find_first(
    HANDLE directory_handle, const char *pattern,
    MERC_PLATFORM_FIND_DATA *data)
{
    if (!pattern || !data)
        return INVALID_HANDLE_VALUE;

#if defined(_XBOX)
    char directory[MAX_PATH];
    char search[MAX_PATH];
    WIN32_FIND_DATAA native_data;
    HANDLE find_handle;

    if (!merc_track_path(directory_handle, directory, MAX_PATH))
        return INVALID_HANDLE_VALUE;

    _snprintf(
        search, MAX_PATH - 1, "%s\\%s",
        directory, pattern[0] ? pattern : "*");
    search[MAX_PATH - 1] = '\0';

    memset(&native_data, 0, sizeof(native_data));
    find_handle = FindFirstFileA(search, &native_data);
    if (find_handle == INVALID_HANDLE_VALUE)
        return INVALID_HANDLE_VALUE;

    merc_copy_find_data(data, &native_data);
    return find_handle;
#else
    WCHAR directory[MAX_PATH];
    WCHAR search[MAX_PATH];
    WCHAR pattern_wide[MAX_PATH];
    WCHAR *clean_path;
    WIN32_FIND_DATAW native_data;
    DWORD length;
    HANDLE find_handle;

    length = GetFinalPathNameByHandleW(
        directory_handle, directory, MAX_PATH, FILE_NAME_NORMALIZED);
    if (length == 0 || length >= MAX_PATH)
        return INVALID_HANDLE_VALUE;

    clean_path = directory;
    if (wcsncmp(clean_path, L"\\\\?\\", 4) == 0)
        clean_path += 4;

    if (MultiByteToWideChar(
            CP_ACP, 0, pattern, -1, pattern_wide, MAX_PATH) <= 0)
        return INVALID_HANDLE_VALUE;

    _snwprintf(
        search, MAX_PATH - 1, L"%s\\%s", clean_path, pattern_wide);
    search[MAX_PATH - 1] = L'\0';

    memset(&native_data, 0, sizeof(native_data));
    find_handle = FindFirstFileW(search, &native_data);
    if (find_handle == INVALID_HANDLE_VALUE)
        return INVALID_HANDLE_VALUE;

    merc_copy_find_data(data, &native_data);
    return find_handle;
#endif
}

BOOL merc_platform_file_find_next(
    HANDLE find_handle, MERC_PLATFORM_FIND_DATA *data)
{
    if (!data)
        return FALSE;

#if defined(_XBOX)
    WIN32_FIND_DATAA native_data;
    if (!FindNextFileA(find_handle, &native_data))
        return FALSE;
#else
    WIN32_FIND_DATAW native_data;
    if (!FindNextFileW(find_handle, &native_data))
        return FALSE;
#endif
    merc_copy_find_data(data, &native_data);
    return TRUE;
}

BOOL merc_platform_file_find_close(HANDLE find_handle)
{
    return FindClose(find_handle);
}

BOOL merc_platform_file_close(HANDLE handle)
{
#if defined(_XBOX)
    char path[MAX_PATH];
    BOOL delete_pending = FALSE;
    BOOL tracked;
    BOOL result;

    path[0] = '\0';
    tracked = merc_track_take(
        handle, path, MAX_PATH, &delete_pending);
    result = CloseHandle(handle);
    if (result && tracked && delete_pending && path[0])
        DeleteFileA(path);
    return result;
#else
    return CloseHandle(handle);
#endif
}

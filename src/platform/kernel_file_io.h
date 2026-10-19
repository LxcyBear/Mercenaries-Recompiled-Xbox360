/*
 * kernel_file_io.h - host/Xenon file primitive boundary for Phase 4B-B.
 *
 * Xbox guest semantics remain in src/kernel/kernel_file.c. This layer owns
 * only native file/handle primitives and the path/handle bookkeeping needed
 * where XDK differs from desktop Win32.
 */
#ifndef MERCENARIES_KERNEL_FILE_IO_H
#define MERCENARIES_KERNEL_FILE_IO_H

#if defined(_XBOX)
#include <xtl.h>
#else
#include "xbox_winnt.h"
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define MERC_PLATFORM_INVALID_FILE_ATTRIBUTES ((DWORD)0xFFFFFFFFu)

typedef struct MERC_PLATFORM_FILE_INFO {
    FILETIME CreationTime;
    FILETIME LastAccessTime;
    FILETIME LastWriteTime;
    DWORD FileAttributes;
    DWORD FileSizeHigh;
    DWORD FileSizeLow;
    DWORD NumberOfLinks;
} MERC_PLATFORM_FILE_INFO;

typedef struct MERC_PLATFORM_FIND_DATA {
    FILETIME CreationTime;
    FILETIME LastAccessTime;
    FILETIME LastWriteTime;
    DWORD FileAttributes;
    DWORD FileSizeHigh;
    DWORD FileSizeLow;
    CHAR FileName[MAX_PATH];
} MERC_PLATFORM_FIND_DATA;

DWORD merc_platform_file_last_error(void);
void merc_platform_file_set_last_error(DWORD error);
DWORD merc_platform_file_get_attributes(const WCHAR *path);
BOOL merc_platform_file_create_directory(const WCHAR *path);
HANDLE merc_platform_file_open(
    const WCHAR *path, DWORD desired_access, DWORD share_access,
    DWORD creation_disposition, DWORD flags_and_attributes);
BOOL merc_platform_file_read(
    HANDLE handle, PVOID buffer, DWORD length, LPDWORD bytes_read,
    const LARGE_INTEGER *byte_offset);
BOOL merc_platform_file_write(
    HANDLE handle, const VOID *buffer, DWORD length, LPDWORD bytes_written,
    const LARGE_INTEGER *byte_offset);
BOOL merc_platform_file_query_info(
    HANDLE handle, MERC_PLATFORM_FILE_INFO *info);
BOOL merc_platform_file_seek(
    HANDLE handle, LARGE_INTEGER distance, PLARGE_INTEGER new_position,
    DWORD move_method);
BOOL merc_platform_file_set_end(HANDLE handle);
BOOL merc_platform_file_set_allocation(
    HANDLE handle, LARGE_INTEGER allocation_size);
BOOL merc_platform_file_set_delete_pending(HANDLE handle, BOOL delete_file);
BOOL merc_platform_file_set_times(
    HANDLE handle, const FILETIME *creation_time,
    const FILETIME *access_time, const FILETIME *write_time);
BOOL merc_platform_file_query_path_info(
    const WCHAR *path, MERC_PLATFORM_FILE_INFO *info);
HANDLE merc_platform_file_find_first(
    HANDLE directory_handle, const char *pattern,
    MERC_PLATFORM_FIND_DATA *data);
BOOL merc_platform_file_find_next(
    HANDLE find_handle, MERC_PLATFORM_FIND_DATA *data);
BOOL merc_platform_file_find_close(HANDLE find_handle);
BOOL merc_platform_file_close(HANDLE handle);

#ifdef __cplusplus
}
#endif

#endif

#!/usr/bin/env python3
"""K1NT207 native real-directory bridge: inherited 64-TU guarded source stage.

Original Xbox hardware (Nov 1 2026) demonstrated NtQueryDirectoryFile ordinal
207, a 44-byte call frame, 10 args: handle, event, APC, context, IOSB, buffer,
length=328, class=1, ANSI filename-mask ptr, restart=0.

No game data or oracle output is embedded. Enumerate the actual mounted
game:\\dataxbox\\ directory, preserve the original Xbox *ANSI* (OCHAR)
FILE_DIRECTORY_INFORMATION 64-byte header, per-token cursor and genuine
result/status. All unobserved layouts/classes stay fenced, with no fabrication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import traceback
from pathlib import Path

TAG="K1NT207-REAL-DIRECTORY-ENUMERATION-20261102"
PARENT="K1NT207-DIRECTORY-FRAME-WITNESS-20261101"
KERN="0x800000CFu"

# Native cursor is indexed by the existing Phase5B virtual native file-handle
# slot; *never* treat an original Xbox file handle as a raw native HANDLE.
CURSOR=r'''
/* K1NT207-REAL-DIRECTORY-ENUMERATION-20261102: per-token live search. */
typedef struct K1Nt207Cursor
{
    HANDLE search;
    WIN32_FIND_DATAA entry;
    uint32_t active;
    uint32_t exhausted;
    uint32_t nextFileIndex;
    uint32_t filtered;
    char initialMask[129];
} K1Nt207Cursor;
static K1Nt207Cursor s_k1nt207Cursors[PHASE5B_HANDLE_CAP];
static uint32_t s_k1nt207Calls=0u;
static uint32_t s_k1nt207Successes=0u;

/* Minimal, exact equivalents of the original Phase5N filetime and guest-u64
 * helpers. TrueTU sharding can omit their earlier support-owned bodies.
 * Keep K1NT207 independent; never restore a guessed Phase5N function.
 * FILETIME is Windows/Xbox 100ns since 1601; guest u64 is two LE DWORDs.
 */
static uint64_t k1nt207_filetime_value(const FILETIME* value)
{
    return ((uint64_t)value->dwHighDateTime << 32) |
           (uint64_t)value->dwLowDateTime;
}
static void k1nt207_write_guest_u64(uint32_t address, uint64_t value)
{
    GUEST_WRITE32(address + 0u, (uint32_t)value);
    GUEST_WRITE32(address + 4u, (uint32_t)(value >> 32));
}

static void k1nt207_clear(uint32_t handleToken)
{
    const uint32_t index=handleToken & 0x00FFFFFFu;
    K1Nt207Cursor* c;
    if ((handleToken & 0xFF000000u)!=PHASE5B_HANDLE_TAG ||
        index==0u || index>=PHASE5B_HANDLE_CAP)
        return;
    c=&s_k1nt207Cursors[index];
    if (c->active && c->search!=INVALID_HANDLE_VALUE && c->search!=NULL)
        FindClose(c->search);
    ZeroMemory(c,sizeof(*c));
}

/* A directory enumeration must not report "." or ".." to the guest. */
static void k1nt207_skip_dots(K1Nt207Cursor* c)
{
    while (!c->exhausted &&
           ((c->entry.cFileName[0]=='.' && c->entry.cFileName[1]=='\0') ||
            (c->entry.cFileName[0]=='.' && c->entry.cFileName[1]=='.' &&
             c->entry.cFileName[2]=='\0')))
    {
        if (!FindNextFileA(c->search,&c->entry))
            c->exhausted=1u;
    }
}
'''

# The original 10-argument Xbox call has no ReturnSingleEntry argument.
# Do not use the *modern Windows* (11-argument) prototype.
HANDLER=r'''
void k1nt207_nt_query_directory_file(uint32_t savedEsp)
{
    const uint32_t callEsp=g_esp;
    uint32_t words[11];
    uint32_t token, event, apc, context, iosb, output, length, cls, maskVa, restart;
    uint32_t status=0u, bytes=0u, rows=0u, lastOffset=0u;
    uint32_t slot;
    DWORD error=ERROR_SUCCESS;
    DWORD nativeAttrs=0u;
    const char* path;
    HANDLE native;
    K1Nt207Cursor* cursor=NULL;
    char search[PHASE5B_HANDLE_PATH_CAP + 136u];
    char pattern[129];
    char line[480];
    char* outputGuest;
    uint32_t i, maskBytes=0u;
    uint32_t initialized=0u;

    /* Hardware: callEsp=008BF618 savedEsp=008BF644, delta=44. */
    if (savedEsp!=callEsp+44u ||
        callEsp<0x00010000u || callEsp>0x04000000u-44u ||
        (callEsp & 3u)!=0u)
    {
        trace("K1NT207 HARD FENCE: original @40/RET44 frame mismatch");
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000CFu,savedEsp);
        return;
    }
    for (i=0u;i<11u;++i)
        words[i]=GUEST_READ32(callEsp+i*4u);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000CFu,savedEsp);
        return;
    }
    token=words[1]; event=words[2]; apc=words[3]; context=words[4];
    iosb=words[5]; output=words[6]; length=words[7]; cls=words[8];
    maskVa=words[9]; restart=words[10];

    /* Only the hardware-observed synchronous class-1 ABI is supported. */
    if (words[0]!=0u || event!=0u || apc!=0u || context!=0u ||
        cls!=1u || restart>1u || length>0x00010000u)
    {
        sprintf(line,"K1NT207 HARD FENCE: ret=%08X event=%08X apc=%08X context=%08X class=%u restart=%u length=%u",
            (unsigned)words[0],(unsigned)event,(unsigned)apc,
            (unsigned)context,(unsigned)cls,(unsigned)restart,(unsigned)length);
        trace(line);
        phase4c_escape(PHASE4C_BOUNDARY_FILE_INFORMATION,0x800000CFu,savedEsp);
        return;
    }
    if (!iosb || iosb<0x00010000u || iosb>0x04000000u-8u ||
        !output || output<0x00010000u || length==0u ||
        length>0x04000000u-output)
    {
        trace("K1NT207 HARD FENCE: unsafe IOSB or guest output buffer");
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000CFu,savedEsp);
        return;
    }
    outputGuest=(char*)guest_ptr(output,length);
    if (!outputGuest || !guest_ptr(iosb,8u))
    {
        trace("K1NT207 HARD FENCE: guest buffer not mapped");
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000CFu,savedEsp);
        return;
    }
    slot=token & 0x00FFFFFFu;
    native=phase5c_read_native_handle(token);
    path=phase5b_read_handle_path(token);
    if (!native || !path || slot==0u || slot>=PHASE5B_HANDLE_CAP)
    {
        status=0xC0000008u; /* STATUS_INVALID_HANDLE */
        goto k1nt207_return_status;
    }
    nativeAttrs=GetFileAttributesA(path);
    /* XDK does not expose INVALID_FILE_ATTRIBUTES; GetFileAttributesA
     * documents failure as (DWORD)-1. Check once, not two native calls. */
    if (nativeAttrs==(DWORD)0xFFFFFFFFu ||
        (nativeAttrs & FILE_ATTRIBUTE_DIRECTORY)==0u)
    {
        status=0xC0000103u; /* STATUS_NOT_A_DIRECTORY */
        goto k1nt207_return_status;
    }
    cursor=&s_k1nt207Cursors[slot];
    if (!cursor->active || restart)
    {
        /* Clear unused mask bytes before storing the full 129-byte pattern.
         * The old stage copied uninitialized stack tail into cursor state. */
        ZeroMemory(pattern,sizeof(pattern));
        /* On initial enumeration capture and validate Xbox ANSI_STRING mask.
         * Later calls use the original filter even when caller passes a new one.
         * String layout: USHORT Length, USHORT MaximumLength, DWORD Buffer.
         */
        pattern[0]='*'; pattern[1]='\0';
        if (cursor->active && restart)
        {
            /* NT captures the first search expression for this handle. */
            memcpy(pattern,cursor->initialMask,sizeof(pattern));
            pattern[sizeof(pattern)-1u]='\0';
            maskBytes=cursor->filtered ? (uint32_t)strlen(pattern) : 0u;
        }
        if (!cursor->active && maskVa!=0u)
        {
            uint32_t nameVa, capacity;
            if (maskVa<0x00010000u || maskVa>0x04000000u-8u)
            {
                trace("K1NT207 HARD FENCE: filter ANSI_STRING address invalid");
                phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000CFu,savedEsp);
                return;
            }
            maskBytes=(uint32_t)GUEST_READ16(maskVa);
            capacity=(uint32_t)GUEST_READ16(maskVa+2u);
            nameVa=GUEST_READ32(maskVa+4u);
            if (s_accessFault || maskBytes>128u || maskBytes>capacity ||
                (maskBytes!=0u && (nameVa<0x00010000u ||
                 nameVa>0x04000000u-maskBytes)))
            {
                trace("K1NT207 HARD FENCE: filter length/pointer invalid");
                phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000CFu,savedEsp);
                return;
            }
            if (maskBytes)
            {
                for (i=0u;i<maskBytes;++i)
                {
                    const char ch=(char)GUEST_READ8(nameVa+i);
                    if (!ch || ch=='\\' || ch=='/' || ch==':' ||
                        ((unsigned char)ch)<0x20u)
                    {
                        trace("K1NT207 HARD FENCE: unsafe directory filter byte");
                        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,
                                       0x800000CFu,savedEsp);
                        return;
                    }
                    pattern[i]=ch;
                }
                pattern[maskBytes]='\0';
                if (s_accessFault)
                {
                    phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,
                                   0x800000CFu,savedEsp);
                    return;
                }
            }
        }
        /* Only one basename glob, never arbitrary traversal from guest. */
        if (strstr(pattern,"..")!=NULL)
        {
            trace("K1NT207 HARD FENCE: invalid directory traversal mask");
            phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000CFu,savedEsp);
            return;
        }
        if (_snprintf(search,sizeof(search)-1u,"%s%s%s",path,
             (path[strlen(path)-1u]=='\\') ? "" : "\\",pattern)<0)
        {
            trace("K1NT207 HARD FENCE: native directory search path too long");
            phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000CFu,savedEsp);
            return;
        }
        search[sizeof(search)-1u]='\0';
        k1nt207_clear(token);
        cursor=&s_k1nt207Cursors[slot];
        SetLastError(ERROR_SUCCESS);
        cursor->search=FindFirstFileA(search,&cursor->entry);
        error=GetLastError();
        cursor->active=1u;
        cursor->filtered=maskBytes>0u ? 1u : 0u;
        memcpy(cursor->initialMask,pattern,sizeof(pattern));
        cursor->nextFileIndex=1u;
        if (cursor->search==INVALID_HANDLE_VALUE)
        {
            cursor->exhausted=1u;
            status=(error==ERROR_FILE_NOT_FOUND || error==ERROR_NO_MORE_FILES) ?
                (cursor->filtered ? 0xC000000Fu : 0x80000006u) :
                phase5b_open_status_from_error(error);
        }
        else
            k1nt207_skip_dots(cursor);
        initialized=1u;
        sprintf(line,"K1NT207 REAL ENUM START: dir=%s mask=%s class=%u length=%u handle=%08X status=%08X",
            path,pattern,(unsigned)cls,(unsigned)length,
            (unsigned)token,(unsigned)status);
        trace(line);
    }
    if (status!=0u)
        goto k1nt207_return_status;
    if (length<64u)
    {
        status=0xC0000023u; /* STATUS_BUFFER_TOO_SMALL */
        goto k1nt207_return_status;
    }
    if (cursor->exhausted)
    {
        status=0x80000006u; /* STATUS_NO_MORE_FILES */
        goto k1nt207_return_status;
    }

    /* Do not write fabricated filenames. Use live native directory entries
     * with Xbox (ANSI/OCHAR) FILE_DIRECTORY_INFORMATION, 64-byte fixed part.
     * All records except final have 8-byte aligned NextEntryOffset.
     */
    ZeroMemory(outputGuest,length);
    for (;;)
    {
        uint32_t nameLen=0u, recLen, recordVa;
        uint64_t size, allocation;
        while (nameLen<MAX_PATH && cursor->entry.cFileName[nameLen])
            ++nameLen;
        if (nameLen>=MAX_PATH || nameLen==0u)
        {
            trace("K1NT207 HARD FENCE: native filename length invalid");
            phase4c_escape(PHASE4C_BOUNDARY_FILE_INFORMATION,
                           0x800000CFu,savedEsp);
            return;
        }
        recLen=(64u+nameLen+7u)&~7u;
        if (recLen>length-bytes)
        {
            if (rows)
                break; /* Leave pending native entry for the next query. */
            /* First matching record does not fit: don't consume it. */
            status=0x80000005u; /* STATUS_BUFFER_OVERFLOW */
            break;
        }
        recordVa=output+bytes;
        GUEST_WRITE32(recordVa+0u,0u);
        GUEST_WRITE32(recordVa+4u,cursor->nextFileIndex);
        k1nt207_write_guest_u64(recordVa+8u,
            k1nt207_filetime_value(&cursor->entry.ftCreationTime));
        k1nt207_write_guest_u64(recordVa+16u,
            k1nt207_filetime_value(&cursor->entry.ftLastAccessTime));
        k1nt207_write_guest_u64(recordVa+24u,
            k1nt207_filetime_value(&cursor->entry.ftLastWriteTime));
        k1nt207_write_guest_u64(recordVa+32u,
            k1nt207_filetime_value(&cursor->entry.ftLastWriteTime));
        size=((uint64_t)cursor->entry.nFileSizeHigh<<32) |
             (uint64_t)cursor->entry.nFileSizeLow;
        if ((cursor->entry.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)!=0u)
            size=0u;
        allocation=size==0u ? 0u :
            ((size<=0xFFFFFFFFFFFFC000ui64) ?
              ((size+0x3FFFui64)&~0x3FFFui64) : size);
        k1nt207_write_guest_u64(recordVa+40u,size);
        k1nt207_write_guest_u64(recordVa+48u,allocation);
        GUEST_WRITE32(recordVa+56u,cursor->entry.dwFileAttributes ?
            cursor->entry.dwFileAttributes : FILE_ATTRIBUTE_NORMAL);
        GUEST_WRITE32(recordVa+60u,nameLen);
        for (i=0u;i<nameLen;++i)
            GUEST_WRITE8(recordVa+64u+i,(uint8_t)cursor->entry.cFileName[i]);
        if (s_accessFault)
        {
            phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,
                           0x800000CFu,savedEsp);
            return;
        }
        if (rows>0u)
            GUEST_WRITE32(output+lastOffset,bytes-lastOffset);
        lastOffset=bytes;
        bytes+=recLen;
        ++rows;
        ++cursor->nextFileIndex;
        if (!FindNextFileA(cursor->search,&cursor->entry))
        {
            error=GetLastError();
            if (error!=ERROR_NO_MORE_FILES)
            {
                trace("K1NT207 HARD FENCE: unexpected FindNextFile error");
                phase4c_escape(PHASE4C_BOUNDARY_STORAGE_IO,
                               0x800000CFu,savedEsp);
                return;
            }
            cursor->exhausted=1u;
            break;
        }
        k1nt207_skip_dots(cursor);
        if (cursor->exhausted)
            break;
    }

k1nt207_return_status:
    GUEST_WRITE32(iosb+0u,status);
    GUEST_WRITE32(iosb+4u,bytes);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000CFu,savedEsp);
        return;
    }
    g_eax=status;
    g_esp=savedEsp;
    ++s_k1nt207Calls;
    if (status==0u)
        ++s_k1nt207Successes;
    sprintf(line,
        "K1NT207 REAL ENUM RESULT: handle=%08X status=%08X rows=%u bytes=%u calls=%u successes=%u first=%u next=%u esp=%08X",
        (unsigned)token,(unsigned)status,(unsigned)rows,(unsigned)bytes,
        (unsigned)s_k1nt207Calls,(unsigned)s_k1nt207Successes,
        (unsigned)initialized,(unsigned)(cursor?cursor->nextFileIndex:0u),
        (unsigned)g_esp);
    trace(line);
    if (status==0u && rows>0u)
        trace("K1NT207 REAL ENUM SUCCESS!!! genuine Xbox ANSI directory records returned");
}
'''

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def insert_once(src:str,needle:str, replacement:str, label:str)->str:
    count=src.count(needle)
    if count!=1:raise ValueError(f"{label} expected one source anchor, got {count}")
    return src.replace(needle,replacement,1)

def insert_before_definition(src: str, pattern: str, injection: str, label: str) -> str:
    """Insert only before one REAL function definition, static or TU-external.

    Phase6 TrueTU externalization removes 'static' from support definitions;
    the previously hardcoded static spelling was NOT an invariant.
    """
    rx = re.compile(pattern, re.M)
    matches = list(rx.finditer(src))
    if len(matches) != 1:
        raise ValueError(
            f"{label} expected one actual function definition, got {len(matches)}"
        )
    at = matches[0].start()
    return src[:at] + injection + src[at:]


def patch_dispatch(src: str, nl: str, label: str,
                   required: bool = True) -> str:
    """Wrap the exact RECOMP_ICALL_SAFE macro; preserve its original body.

    The Phase6 TrueTU emitter moves the macro into translated_runtime.h, and
    later support stages can change its 211/D3 cases. Never require any one
    historical ordinal case. Instead, gate ONLY the hardware-proven CF
    target and execute the unmodified existing macro body for every other
    target, retaining the pre-existing hard-stop fallback verbatim.

    A macro-less sharded host is fine; the shared TrueTU header is mandatory.
    """
    lines = src.splitlines(keepends=True)
    head = re.compile(
        r"^[ \t]*#define[ \t]+RECOMP_ICALL_SAFE"
        r"\(xbox_va,[ \t]*saved_esp\)[ \t]+do[ \t]*\{[ \t]*\\[ \t]*$"
    )
    positions = [
        i for i, line in enumerate(lines)
        if head.fullmatch(line.rstrip("\r\n"))
    ]
    if not positions:
        if required:
            matches = [
                line.strip() for line in lines
                if "define RECOMP_ICALL_SAFE" in line
            ]
            raise ValueError(
                f"{label}: exact RECOMP_ICALL_SAFE do-brace macro missing; "
                f"candidates={matches[:2]!r}. NO XDK."
            )
        if "define RECOMP_ICALL_SAFE" in src:
            raise ValueError(
                f"{label}: unexpected host ICALL macro shape. NO XDK."
            )
        return src
    if len(positions) != 1:
        raise ValueError(
            f"{label}: multiple original ICALL_SAFE macro definitions "
            f"({len(positions)}); NO XDK."
        )
    first = positions[0]
    last = first + 1
    while last < len(lines):
        line = lines[last].rstrip("\r\n")
        if not line.rstrip().endswith("\\"):
            break
        last += 1
    if last >= len(lines):
        raise ValueError(f"{label}: unterminated original ICALL macro")
    terminator = lines[last].rstrip("\r\n").strip()
    if not re.fullmatch(r"}[ \t]*while[ \t]*\([ \t]*0[ \t]*\)[ \t]*;?", terminator):
        raise ValueError(
            f"{label}: unexpected ICALL macro terminator {terminator!r}; "
            "NO XDK."
        )
    old_body = "".join(lines[first + 1:last])
    # The original hard stop must remain available for all other ordinals.
    if "phase4c_escape(" not in old_body:
        raise ValueError(
            f"{label}: original ICALL fallback not proven; NO XDK."
        )
    if ("k1nt207_nt_query_directory_file" in old_body
        or re.search(r"==[ \t]*0x800000CFu\b", old_body)):
        raise ValueError(
            f"{label}: ordinal207 dispatch already installed; NO XDK."
        )
    native_branch = (
        "    if ((uint32_t)(xbox_va) == 0x800000CFu) { \\" + nl
        + "        k1nt207_nt_query_directory_file((uint32_t)(saved_esp)); \\" + nl
        + "    } else { \\" + nl
    )
    # The original macro is not reinterpreted or rebuilt: original bytes
    # between the do-brace and while terminator are copied exactly.
    replacement = (
        lines[first] + native_branch + old_body
        + "    } \\" + nl + lines[last]
    )
    declaration = "void k1nt207_nt_query_directory_file(uint32_t savedEsp);" + nl
    result = "".join(lines[:first]) + replacement + "".join(lines[last + 1:])
    if required:
        # The TrueTU header starts with extracted #include/#define blocks.
        # It does NOT guarantee that uint32_t is defined at macro line 197.
        # Type definitions precede the generated "runtime/support entry
        # points" section; put our prototype there, just like other public
        # support declarations. The macro expands later in the shard bodies.
        anchor = "/* runtime/support entry points */" + nl
        if result.count(anchor) != 1:
            raise ValueError(
                f"{label}: generated typed support section missing or duplicate; "
                "NO XDK."
            )
        result = result.replace(anchor, anchor + declaration, 1)
        type_section = result.find("/* shared generated types */")
        decl_position = result.find(declaration)
        if type_section < 0 or decl_position < type_section:
            raise ValueError(
                f"{label}: native prototype appeared before shared types; NO XDK."
            )
    else:
        # The host main.cpp already compiled past the native handler call;
        # preserve its existing macro-near declaration placement.
        result = "".join(lines[:first]) + declaration + replacement \
                 + "".join(lines[last + 1:])
    if (result.count(
        "k1nt207_nt_query_directory_file((uint32_t)(saved_esp));") != 1
        or result.count(declaration) != 1
        or old_body not in result):
        raise ValueError(f"{label}: ordinal207 wrapper/body proof failed")
    return result


def transform(src: str, header: str) -> tuple[str, str]:
    if TAG in src or TAG in header:
        raise ValueError("Already patched; reject duplicate")
    if "\r" in src.replace("\r\n", "") or "\r" in header.replace("\r\n", ""):
        raise ValueError("Mixed newlines")
    nl = "\r\n" if "\r\n" in src else "\n"
    hn = "\r\n" if "\r\n" in header else "\n"
    # Sharding externalizes this native helper; don't require 'static'.
    src = insert_before_definition(
        src,
        r"^[ \t]*(?:static[ \t]+)?uint32_t[ \t]+"
        r"phase5b_native_handle_token[ \t]*\([ \t]*HANDLE[ \t]+handle[ \t]*\)"
        r"[ \t\r\n]*(?=\{)",
        CURSOR.replace("\n", nl) + nl,
        "Phase5B native-handle table owner")
    close_stmt = "nativeHandle = phase5c_take_native_handle(handleToken);"
    src = insert_once(
        src, close_stmt, "k1nt207_clear(handleToken);" + nl +
        "    " + close_stmt, "NtClose lifecycle")
    # The Phase6 TrueTU generator may rewrite the signature/layout of the
    # existing phase5n_nt_query_information_file support definition.  Its
    # spelling and position are NOT an insertion contract.  Place our new
    # top-level helper after ALL inherited host support definitions instead.
    # Its dispatcher prototype is installed separately BEFORE the macro.
    # The original Phase5N tiny FILETIME/guest-u64 helpers are NOT guaranteed
    # to survive TrueTU sharding. K1NT207 now owns exact local equivalents.
    # Keep only hard dependencies that actually exist in the proven host.
    required_host_helpers = (
        "phase5c_read_native_handle(",
        "phase5b_read_handle_path(",
        "phase5b_open_status_from_error(",
    )
    missing = [name for name in required_host_helpers if name not in src]
    if missing:
        raise ValueError(
            "Host native directory dependencies missing: " + ", ".join(missing)
            + ". Source stage fenced; NO XDK.")
    src = src.rstrip("\r\n") + nl + HANDLER.replace("\n", nl) + nl

    # The TRUE TU compiler consumes the shared HEADER macro. Do not assume
    # any particular pre-existing ordinal case survives in that macro.
    src = patch_dispatch(src, nl, "host main.cpp", required=False)
    header = patch_dispatch(header, hn, "translated_runtime.h", required=True)

    if src.count(TAG) != 1 or src.count("K1NT207 REAL ENUM RESULT:") != 1:
        raise ValueError("Native handler marker/trace uniqueness failed")
    if header.count("void k1nt207_nt_query_directory_file(uint32_t savedEsp);") != 1:
        raise ValueError("Cross-TU native handler declaration missing")
    if "K1NT207 FRAME GATE:" not in src or "P6DQ ROCKET HARD STOP" not in src:
        raise ValueError("Existing hardware ABI witness or hard stop not preserved")
    return src, header


def self_test():
    real_host = (
        "#define PHASE5B_HANDLE_TAG 0x48000000u\n"
        "#define PHASE5B_HANDLE_CAP 64u\n"
        "static uint32_t phase5b_native_handle_token(HANDLE handle){}\n"
        "static void phase5c_nt_close(uint32_t savedEsp){\n"
        "    nativeHandle = phase5c_take_native_handle(handleToken);\n}\n"
        "static void phase5n_nt_query_information_file(uint32_t savedEsp){}\n"
        "static HANDLE phase5c_read_native_handle(uint32_t token){}\n"
        "static const char* phase5b_read_handle_path(uint32_t token){}\n"
        "static uint32_t phase5b_open_status_from_error(DWORD error){}\n"
        "#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \\\n"
        "    uint32_t _phase4c_target = (uint32_t)(xbox_va); \\\n"
        "    if (_phase4c_target == 0x800000D3u) { \\\n"
        "        phase5n_nt_query_information_file((uint32_t)(saved_esp)); \\\n"
        "    } else { \\\n"
        "        phase4c_escape(PHASE4C_BOUNDARY_ICALL_SAFE, _phase4c_target, (uint32_t)(saved_esp)); \\\n"
        "    } \\\n"
        "} while (0)\n"
        "K1NT207 FRAME GATE:\nP6DQ ROCKET HARD STOP\n"
    )
    shared_header = (
        "#pragma once\n"
        "#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \\\n"
        "    uint32_t _phase4c_target = (uint32_t)(xbox_va); \\\n"
        "    if (_phase4c_target == 0x800000D3u) { \\\n"
        "        phase5n_nt_query_information_file((uint32_t)(saved_esp)); \\\n"
        "    } else { \\\n"
        "        phase4c_escape(PHASE4C_BOUNDARY_ICALL_SAFE, _phase4c_target, (uint32_t)(saved_esp)); \\\n"
        "    } \\\n"
        "} while (0)\n"
        "\n/* shared generated types */\n"
        "typedef unsigned int uint32_t;\n"
        "/* shared runtime storage */\n"
        "/* runtime/support entry points */\n"
    )
    print("[K1NT207-NATIVE] SELFTEST REV C: macro wraps original full ICALL hard-stop; old ordinal211 not required",flush=True)
    for externalized in (False, True):
        host = real_host
        if externalized:
            host = host.replace(
                "static uint32_t phase5b_native_handle_token",
                "uint32_t phase5b_native_handle_token")
            host = host.replace(
                "static void phase5n_nt_query_information_file",
                "void phase5n_nt_query_information_file")
        for newline in ("\n", "\r\n"):
            h0 = host.replace("\n", newline)
            s0 = shared_header.replace("\n", newline)
            label = "externalized=" + str(externalized) + " CRLF=" + str(newline == "\r\n")
            print("[K1NT207-NATIVE] SELFTEST CASE: " + label,flush=True)
            main, hdr = transform(h0, s0)
            assert main.count(TAG) == 1, label + " injected marker count mismatch"
            assert hdr.count("k1nt207_nt_query_directory_file((uint32_t)(saved_esp));") == 1
            decl_pos = hdr.find("void k1nt207_nt_query_directory_file(uint32_t savedEsp);")
            assert decl_pos > hdr.find("typedef unsigned int uint32_t;"), (
                label + " prototype precedes uint32_t; would break all TrueTUs"
            )
            assert hdr.find("/* runtime/support entry points */") < decl_pos
            assert hdr.count("phase4c_escape(") == 1, label + " original fallback lost"
            assert main.count("k1nt207_nt_query_directory_file((uint32_t)(saved_esp));") == 1
            assert "void k1nt207_nt_query_directory_file(uint32_t savedEsp);" in hdr
            assert main.count("k1nt207_clear(handleToken);") == 1
            assert "K1NT207 REAL ENUM SUCCESS!!!" in main
            assert "P6DQ ROCKET HARD STOP" in main
            assert main.rfind("void k1nt207_nt_query_directory_file(") > main.find(
                "k1nt207_write_guest_u64("), label + " helper not appended after inherited support"
            # The real TrueTU runtime may change the existing Phase5N support
            # definition's argument type, keyword or layout.  This must NOT
            # affect placement of the new native helper.
            drifted = h0.replace(
                "static void phase5n_nt_query_information_file(uint32_t savedEsp){}",
                "void phase5n_nt_query_information_file(DWORD renamedFrame){}")
            if drifted == h0:
                drifted = h0.replace(
                    "void phase5n_nt_query_information_file(uint32_t savedEsp){}",
                    "void phase5n_nt_query_information_file(DWORD renamedFrame){}")
            assert drifted != h0, label + " failed to construct Phase5N signature drift"
            drift_main, drift_header = transform(drifted, s0)
            assert drift_main.count(TAG) == 1, label + " signature drift was not handled"
            assert drift_header.count(
                "k1nt207_nt_query_directory_file((uint32_t)(saved_esp));") == 1
            try:
                transform(main, hdr)
            except ValueError:
                pass
            else:
                raise AssertionError("Repeated stage accepted")
    # The real TrueTU host can lack RECOMP_ICALL_SAFE/D3 entirely; all
    # translated callsites use the macro from the required shared header.
    host_macro = (
        "#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \\\n"
        "    uint32_t _phase4c_target = (uint32_t)(xbox_va); \\\n"
        "    if (_phase4c_target == 0x800000D3u) { \\\n"
        "        phase5n_nt_query_information_file((uint32_t)(saved_esp)); \\\n"
        "    } else { \\\n"
        "        phase4c_escape(PHASE4C_BOUNDARY_ICALL_SAFE, _phase4c_target, (uint32_t)(saved_esp)); \\\n"
        "    } \\\n"
        "} while (0)\n"
    )
    assert real_host.count(host_macro) == 1
    header_calls = "k1nt207_nt_query_directory_file((uint32_t)(saved_esp));"
    for externalized in (False, True):
        host = real_host.replace(host_macro, "")
        if externalized:
            host = host.replace(
                "static uint32_t phase5b_native_handle_token",
                "uint32_t phase5b_native_handle_token")
        for newline in ("\n", "\r\n"):
            original_host = host.replace("\n", newline)
            original_header = shared_header.replace("\n", newline)
            transformed_main, transformed_header = transform(
                original_host, original_header)
            assert TAG in transformed_main
            assert header_calls not in transformed_main
            assert transformed_header.count(header_calls) == 1
            assert "K1NT207 REAL ENUM SUCCESS!!!" in transformed_main
            try:
                transform(transformed_main, transformed_header)
            except ValueError:
                pass
            else:
                raise AssertionError("No-macro host accepted double native stage")
            print("[K1NT207-NATIVE] SELFTEST CASE: no host D3 macro "
                  "externalized=" + str(externalized) +
                  " CRLF=" + str(newline == "\r\n"), flush=True)
    # Changes to old kernel ordinals must not affect our exact CF
    # exception. This is the layout observed by the user's current build.
    changed_old_dispatch = shared_header.replace(
        "_phase4c_target == 0x800000D3u",
        "_phase4c_target == 0x800000D4u")
    assert changed_old_dispatch != shared_header
    generic_main, generic_header = transform(real_host, changed_old_dispatch)
    assert "k1nt207_nt_query_directory_file((uint32_t)(saved_esp));" in generic_header
    assert "_phase4c_target == 0x800000D4u" in generic_header
    assert "phase5n_nt_query_information_file((uint32_t)(saved_esp));" in generic_header
    # Missing type/support staging marker must fail BEFORE XDK, instead of
    # inserting a uint32_t prototype into the header's pre-type macro block.
    try:
        transform(real_host, shared_header.replace(
            "/* runtime/support entry points */",
            "/* wrong section; no typed declarations */"))
    except ValueError as exc:
        assert "typed support section" in str(exc)
    else:
        raise AssertionError("Unsafe header prototype location was accepted")
    # The shared header itself must retain a recognizable original macro.
    try:
        transform(real_host, shared_header.replace(
            "#define RECOMP_ICALL_SAFE", "#define RECOMP_MISSING_ICALL"))
    except ValueError as exc:
        assert "translated_runtime.h" in str(exc)
    else:
        raise AssertionError("Missing shared-header macro wrongly accepted")
    # A pre-existing dispatch really IS an unsafe double override and must
    # still be rejected; checking an unrelated helper body is not sufficient.
    preexisting = shared_header.replace(
        "    if (_phase4c_target == 0x800000D3u) { \\\n",
        "    if (_phase4c_target == 0x800000CFu) { \\\n"
        "        prior_nt207_handler((uint32_t)(saved_esp)); \\\n"
        "    } else if (_phase4c_target == 0x800000D3u) { \\\n",
    )
    assert preexisting != shared_header, "Duplicate-dispatch fixture missing"
    try:
        patch_dispatch(preexisting, "\n", "already-routed fixture")
    except ValueError as exc:
        assert "ordinal207 dispatch already installed" in str(exc)
    else:
        raise AssertionError("Existing ordinal207 dispatcher accepted")
    # Missing runtime dependencies must still be hard-fenced.  Broadening
    # insertion placement is NOT permission to emit an unlinked native helper.
    try:
        transform(real_host.replace("phase5b_open_status_from_error(", "missing_open_status("),
                  shared_header)
    except ValueError as exc:
        assert "phase5b_open_status_from_error(" in str(exc)
    else:
        raise AssertionError("Missing native filetime support was accepted")
    for forbidden in ("fopen(", "CreateDirectory(", "return STATUS_SUCCESS"):
        assert forbidden not in HANDLER
    assert "phase5n_filetime_value(" not in HANDLER
    assert "phase5n_write_guest_u64(" not in HANDLER
    assert "k1nt207_filetime_value(" in HANDLER
    assert "k1nt207_write_guest_u64(" in HANDLER
    assert "static uint64_t k1nt207_filetime_value(const FILETIME* value)" in CURSOR
    assert "static void k1nt207_write_guest_u64(uint32_t address, uint64_t value)" in CURSOR
    assert "((uint64_t)value->dwHighDateTime << 32)" in CURSOR
    assert "GUEST_WRITE32(address + 4u, (uint32_t)(value >> 32));" in CURSOR
    assert "ZeroMemory(pattern,sizeof(pattern));" in HANDLER
    assert "nativeAttrs=GetFileAttributesA(path);" in HANDLER
    assert HANDLER.count("GetFileAttributesA(path)") == 1
    assert "(DWORD)0xFFFFFFFFu" in HANDLER
    assert "INVALID_FILE_ATTRIBUTES" not in HANDLER.replace(
        "XDK does not expose INVALID_FILE_ATTRIBUTES", "")
    assert "GUEST_WRITE32(recordVa+60u,nameLen)" in HANDLER
    assert "GUEST_WRITE8(recordVa+64u+i," in HANDLER
    assert "void k1nt207_nt_query_directory_file(uint32_t savedEsp)\n{" in HANDLER
    assert "static void k1nt207_nt_query_directory_file" not in HANDLER
    assert "savedEsp!=callEsp+44u" in HANDLER
    assert "FindFirstFileA(search,&cursor->entry)" in HANDLER
    assert "FindNextFileA(cursor->search,&cursor->entry)" in HANDLER
    assert "k1nt207_clear(handleToken);" not in HANDLER
    assert "phase4c_escape(PHASE4C_BOUNDARY_FILE_INFORMATION" in HANDLER
    print("[K1NT207-NATIVE] SELFTEST PASS: TrueTU macro wrapper preserves "
          "old dispatch and hard-stop fallback even without ordinal211/D3, "
          "host macro optional, header mandatory, CRLF, RET44, ANSI class1")

def stage(a):
    for p in (a.parent_main,a.parent_manifest,a.parent_shards):
        if not p.exists():raise ValueError("Parent missing: "+str(p))
    meta=json.loads(a.parent_manifest.read_text(encoding="utf-8-sig"))
    if (meta.get("marker")!=PARENT
        or meta.get("status")!="FRAME_PROBE_STAGED_HARD_STOP_PRESERVED_NO_XDK"
        or meta.get("native_directory_service") is not False
        or meta.get("hard_stop_preserved") is not True
        or meta.get("mmio_fences")!="UNCHANGED"
        or meta.get("new_main_sha256")!=sha(a.parent_main.read_bytes())
        or Path(meta.get("out_main","MISSING")).resolve()!=a.parent_main.resolve()
        or Path(meta.get("out_shards","MISSING")).resolve()!=a.parent_shards.resolve()):
        raise ValueError("Last known hardware ABI witness provenance mismatch")
    if a.out_main.resolve()==a.parent_main.resolve() or a.out_shards.resolve()==a.parent_shards.resolve():
        raise ValueError("Cannot overwrite proven hardware witness")
    src=a.parent_main.read_bytes().decode("utf-8")
    runtime_h=a.parent_shards/"translated_runtime.h"
    if not runtime_h.is_file():
        raise ValueError("Missing inherited TrueTU runtime header")
    old_header=runtime_h.read_bytes()
    new,new_header=transform(src,old_header.decode("utf-8"))
    header_blob=new_header.encode("utf-8")
    files=sorted(p for p in a.parent_shards.glob("translated_???.cpp") if p.is_file())
    headers=sorted(a.parent_shards.glob("*.h"))
    if len(files)!=64 or not (a.parent_shards/"translated_runtime.h").is_file():
        raise ValueError("Expected 64 parent TrueTUs and runtime header")
    for tu in files:
        if tu.read_bytes().count(b'#include "translated_runtime.h"') != 1:
            raise ValueError("TrueTU not linked to shared runtime dispatcher: " + tu.name)

    # A previous candidate was successfully staged and then rejected by the
    # XDK. Allow regenerating it ONLY when the prior output manifest matches
    # every inherited source and the on-disk previously generated hashes.
    # Preserve the XDK build logs, all 64 TrueTUs, other generated headers,
    # and the hardware-proven original K1NT207 parent without any rewrite.
    prior_staged = False
    if a.manifest.is_file():
        try:
            prev = json.loads(a.manifest.read_text(encoding="utf-8-sig"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("Existing native manifest cannot be trusted") from exc
        old_staged_header = a.out_shards/"translated_runtime.h"
        if (prev.get("marker") != TAG
            or prev.get("status") != "NATIVE_DIRECTORY_SOURCE_STAGED_NO_XDK"
            or prev.get("source_only") is not True
            or prev.get("parent_main_sha256") != sha(a.parent_main.read_bytes())
            or prev.get("parent_runtime_header_sha256") != sha(old_header)
            or Path(prev.get("out_main","MISSING")).resolve() != a.out_main.resolve()
            or Path(prev.get("out_shards","MISSING")).resolve() != a.out_shards.resolve()
            or not a.out_main.is_file()
            or not old_staged_header.is_file()
            or prev.get("native_main_sha256") != sha(a.out_main.read_bytes())
            or prev.get("native_runtime_header_sha256")
               != sha(old_staged_header.read_bytes())):
            raise ValueError(
                "Native output drift or parent provenance mismatch; refusing restage"
            )
        prior_staged = True
    # Validate *all* preexisting non-target files before updating either
    # generated target, so one drifted TrueTU cannot cause half-restaging.
    for p in files + headers:
        dest = a.out_shards/p.name
        if p.name != "translated_runtime.h" and dest.exists():
            if dest.read_bytes() != p.read_bytes():
                raise ValueError("Changed inherited TrueTU/header: " + p.name)
    a.out_shards.mkdir(parents=True,exist_ok=True)
    for p in files+headers:
        dest=a.out_shards/p.name
        new_blob=header_blob if p.name=="translated_runtime.h" else p.read_bytes()
        if dest.exists() and dest.read_bytes()!=new_blob:
            if p.name!="translated_runtime.h" or not prior_staged:
                raise ValueError("Refusing changed inherited file "+p.name)
            dest.write_bytes(new_blob)
        if not dest.exists():dest.write_bytes(new_blob)
    blob=new.encode("utf-8")
    a.out_main.parent.mkdir(parents=True,exist_ok=True)
    if a.out_main.exists() and a.out_main.read_bytes()!=blob:
        if not prior_staged:
            raise ValueError("Refusing drifted native handler main")
        a.out_main.write_bytes(blob)
    if not a.out_main.exists():a.out_main.write_bytes(blob)
    output={
        "marker":TAG,
        "status":"NATIVE_DIRECTORY_SOURCE_STAGED_NO_XDK",
        "parent_marker":PARENT,
        "parent_main_sha256":sha(a.parent_main.read_bytes()),
        "native_main_sha256":sha(blob),
        "parent_runtime_header_sha256":sha(old_header),
        "native_runtime_header_sha256":sha(header_blob),
        "changed_headers":["translated_runtime.h"],
        "host_ordinal207_macro_patched":
            "k1nt207_nt_query_directory_file((uint32_t)(saved_esp));" in new,
        "true_tu_shared_dispatcher_includes":64,
        "out_main":str(a.out_main.resolve()),
        "out_shards":str(a.out_shards.resolve()),
        "source_original_ordinal":207,
        "xbox_original_stack_frame_bytes":44,
        "xbox_guest_file_directory_information_class":1,
        "xbox_guest_filename_encoding":"OCHAR/ANSI",
        "live_20261101_handle":"0x48000001",
        "native_directory_service_staged":True,
        "source_only":True,
        "no_faked_files_or_success":True,
        "hard_fences_unchanged_except_exact_original_207":True,
        "mmio_fences":"UNCHANGED",
        "xpp_guest_tus_unchanged":64,
        "display_calls_injected":False,
        "built_xex_verified":False,
        "hardware_ordinal207_verified":False
    }
    manifest=(json.dumps(output,indent=2)+"\n").encode("utf-8")
    a.manifest.parent.mkdir(parents=True,exist_ok=True)
    if a.manifest.exists() and a.manifest.read_bytes()!=manifest:
        if not prior_staged:
            raise ValueError("Refusing native manifest drift")
        a.manifest.write_bytes(manifest)
    if not a.manifest.exists():a.manifest.write_bytes(manifest)
    if prior_staged:
        print("[K1NT207-NATIVE] VERIFIED RESTAGE PASS: inherited parent and previous output SHA proven; native main/header updated, logs + 64 TUs retained")
    print("[K1NT207-NATIVE] STAGE PASS: native Xbox360 FindFirst/Next directory enumeration source")
    print("[K1NT207-NATIVE] Native FILETIME/u64 guest writers are K1NT207-owned; Phase5N omitted helpers NOT needed")
    print("[K1NT207-NATIVE] ORIGINAL XBOX ABI: NtQueryDirectoryFile @40 RET44, class1, ANSI 64B header")
    print("[K1NT207-NATIVE] 64 TrueTUs BYTE EXACT, all 64 include patched translated_runtime.h")
    print("[K1NT207-NATIVE] Host D3 macro: " +
          ("patched" if "k1nt207_nt_query_directory_file((uint32_t)(saved_esp));" in new
           else "absent; active shared-header dispatch patched"))
    print("[K1NT207-NATIVE] Existing XPP + original hard stop preserved; native NT207 is explicit exception")
    print("[K1NT207-NATIVE] SOURCE ONLY: no XDK, no Xbox execution, no guest display injected")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    for key in ("parent_main","parent_manifest","parent_shards","out_main",
                "out_shards","manifest"):
        p.add_argument("--"+key.replace("_","-"),type=Path)
    a=p.parse_args()
    if a.self_test:
        try:
            self_test()
        except Exception as exc:
            # Windows PowerShell 5.x can collapse native-process stderr into
            # one unhelpful wrapper line. Emit exact traceback on stdout.
            print("[K1NT207-NATIVE] SELFTEST FAILURE: "
                  + type(exc).__name__ + ": " + str(exc),flush=True)
            traceback.print_exc(file=sys.stdout)
            raise SystemExit(2)
        return
    for key in ("parent_main","parent_manifest","parent_shards",
                "out_main","out_shards","manifest"):
        if getattr(a,key) is None:
            p.error("--"+key.replace("_","-")+" required")
    stage(a)
if __name__=="__main__":
    main()

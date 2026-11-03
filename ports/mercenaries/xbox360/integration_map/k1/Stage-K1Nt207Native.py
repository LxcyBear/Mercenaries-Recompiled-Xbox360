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
} K1Nt207Cursor;
static K1Nt207Cursor s_k1nt207Cursors[PHASE5B_HANDLE_CAP];
static uint32_t s_k1nt207Calls=0u;
static uint32_t s_k1nt207Successes=0u;

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
static void k1nt207_nt_query_directory_file(uint32_t savedEsp)
{
    const uint32_t callEsp=g_esp;
    uint32_t words[11];
    uint32_t token, event, apc, context, iosb, output, length, cls, maskVa, restart;
    uint32_t status=0u, bytes=0u, rows=0u, lastOffset=0u;
    uint32_t slot;
    DWORD error=ERROR_SUCCESS;
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
    if (GetFileAttributesA(path)==INVALID_FILE_ATTRIBUTES ||
        (GetFileAttributesA(path) & FILE_ATTRIBUTE_DIRECTORY)==0u)
    {
        status=0xC0000103u; /* STATUS_NOT_A_DIRECTORY */
        goto k1nt207_return_status;
    }
    cursor=&s_k1nt207Cursors[slot];
    if (!cursor->active || restart)
    {
        /* On initial enumeration capture and validate Xbox ANSI_STRING mask.
         * Later calls use the original filter even when caller passes a new one.
         * String layout: USHORT Length, USHORT MaximumLength, DWORD Buffer.
         */
        pattern[0]='*'; pattern[1]='\0';
        if (maskVa!=0u)
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
        phase5n_write_guest_u64(recordVa+8u,
            phase5n_filetime_value(&cursor->entry.ftCreationTime));
        phase5n_write_guest_u64(recordVa+16u,
            phase5n_filetime_value(&cursor->entry.ftLastAccessTime));
        phase5n_write_guest_u64(recordVa+24u,
            phase5n_filetime_value(&cursor->entry.ftLastWriteTime));
        phase5n_write_guest_u64(recordVa+32u,
            phase5n_filetime_value(&cursor->entry.ftLastWriteTime));
        size=((uint64_t)cursor->entry.nFileSizeHigh<<32) |
             (uint64_t)cursor->entry.nFileSizeLow;
        if ((cursor->entry.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)!=0u)
            size=0u;
        allocation=size==0u ? 0u :
            ((size<=0xFFFFFFFFFFFFC000ui64) ?
              ((size+0x3FFFui64)&~0x3FFFui64) : size);
        phase5n_write_guest_u64(recordVa+40u,size);
        phase5n_write_guest_u64(recordVa+48u,allocation);
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

def transform(src:str)->str:
    if TAG in src:raise ValueError("Already patched; reject duplicate")
    if "\r" in src.replace("\r\n",""):raise ValueError("Mixed newlines")
    nl="\r\n" if "\r\n" in src else "\n"
    # The declarations belong in host main.cpp, not in any translated TU.
    header="static uint32_t phase5b_native_handle_token(HANDLE handle)"
    src=insert_once(src,header,CURSOR.replace("\n",nl)+nl+header,"cursor owner")

    close_stmt="nativeHandle = phase5c_take_native_handle(handleToken);"
    src=insert_once(src,close_stmt,
        "k1nt207_clear(handleToken);"+nl+"    "+close_stmt,
        "NtClose lifecycle")

    body="static void phase5n_nt_query_information_file(uint32_t savedEsp)"
    src=insert_once(src,body,HANDLER.replace("\n",nl)+nl+body,
                    "query handler insertion")

    # Source-backed packed ICALL_SAFE dispatch: call the native helper BEFORE
    # the preexisting D3/QueryInformation case or the fallback hard stop.
    case=("} else if (_phase4c_target == 0x800000D3u) { \\"+nl+
          "        phase5n_nt_query_information_file((uint32_t)(saved_esp)); \\")
    if case not in src:
        raise ValueError("Original native dispatcher D3 case not recognized; NO XDK")
    src=insert_once(src,case,
        ("} else if (_phase4c_target == 0x800000CFu) { \\"+nl+
         "        k1nt207_nt_query_directory_file((uint32_t)(saved_esp)); \\"+nl+
         "    "+case),"native ICALL_SAFE 207 dispatch")
    decl="#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \\"
    src=insert_once(src,decl,
        "static void k1nt207_nt_query_directory_file(uint32_t savedEsp);"+nl+
        decl,"forward declaration")
    if src.count(TAG)!=1:raise ValueError("Tag count mismatch")
    if src.count("K1NT207 REAL ENUM RESULT:")!=1:
        raise ValueError("Runtime success witness not unique")
    if "K1NT207 FRAME GATE:" not in src or "P6DQ ROCKET HARD STOP" not in src:
        raise ValueError("Existing ABI capture/hard-stop was modified")
    return src

def self_test():
    stub=("static uint32_t phase5b_native_handle_token(HANDLE handle){}"
          "\nstatic void phase5c_nt_close(uint32_t savedEsp){\n"
          "    nativeHandle = phase5c_take_native_handle(handleToken);\n}\n"
          "static void phase5n_nt_query_information_file(uint32_t savedEsp){}\n"
          "#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \\\n"
          "    } else if (_phase4c_target == 0x800000D3u) { \\\n"
          "        phase5n_nt_query_information_file((uint32_t)(saved_esp)); \\\n"
          "    } else { \\\n"
          "} while (0)\n"
          "K1NT207 FRAME GATE:\nP6DQ ROCKET HARD STOP\n")
    for inp in (stub,stub.replace("\n","\r\n")):
        got=transform(inp)
        assert got.count(TAG)==1
        assert got.count("k1nt207_clear(handleToken);")==1
        assert got.count("k1nt207_nt_query_directory_file((uint32_t)(saved_esp));")==1
        assert "K1NT207 REAL ENUM SUCCESS!!!" in got
        for forbidden in ("fopen(", "CreateDirectory(", "game:\\\\dataxbox\\\\hud", "return STATUS_SUCCESS"):
            assert forbidden not in HANDLER
        try:transform(got)
        except ValueError:pass
        else:raise AssertionError("Double stage accepted")
    assert "GUEST_WRITE32(recordVa+60u,nameLen)" in HANDLER
    assert "GUEST_WRITE8(recordVa+64u+i," in HANDLER
    assert "savedEsp!=callEsp+44u" in HANDLER
    assert "FindFirstFileA(search,&cursor->entry)" in HANDLER
    assert "FindNextFileA(cursor->search,&cursor->entry)" in HANDLER
    assert "k1nt207_clear(handleToken);" not in HANDLER
    assert "phase4c_escape(PHASE4C_BOUNDARY_FILE_INFORMATION" in HANDLER
    print("[K1NT207-NATIVE] SELFTEST PASS: 10-arg ABI, ANSI class1, bounded output, cursor/close, no fake data")

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
    new=transform(src)
    files=sorted(p for p in a.parent_shards.glob("translated_???.cpp") if p.is_file())
    headers=sorted(a.parent_shards.glob("*.h"))
    if len(files)!=64 or not (a.parent_shards/"translated_runtime.h").is_file():
        raise ValueError("Expected 64 parent TrueTUs and runtime header")
    a.out_shards.mkdir(parents=True,exist_ok=True)
    for p in files+headers:
        dest=a.out_shards/p.name
        if dest.exists() and dest.read_bytes()!=p.read_bytes():
            raise ValueError("Refusing changed TrueTU "+p.name)
        if not dest.exists():dest.write_bytes(p.read_bytes())
    blob=new.encode("utf-8")
    a.out_main.parent.mkdir(parents=True,exist_ok=True)
    if a.out_main.exists() and a.out_main.read_bytes()!=blob:
        raise ValueError("Refusing drifted native handler main")
    if not a.out_main.exists():a.out_main.write_bytes(blob)
    output={
        "marker":TAG,
        "status":"NATIVE_DIRECTORY_SOURCE_STAGED_NO_XDK",
        "parent_marker":PARENT,
        "parent_main_sha256":sha(a.parent_main.read_bytes()),
        "native_main_sha256":sha(blob),
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
        raise ValueError("Refusing native manifest drift")
    if not a.manifest.exists():a.manifest.write_bytes(manifest)
    print("[K1NT207-NATIVE] STAGE PASS: native Xbox360 FindFirst/Next directory enumeration source")
    print("[K1NT207-NATIVE] ORIGINAL XBOX ABI: NtQueryDirectoryFile @40 RET44, class1, ANSI 64B header")
    print("[K1NT207-NATIVE] 64 TrueTUs BYTE EXACT; existing XPP + old hard stop preserved")
    print("[K1NT207-NATIVE] SOURCE ONLY: no XDK, no Xbox execution, no guest display injected")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    for key in ("parent_main","parent_manifest","parent_shards","out_main",
                "out_shards","manifest"):
        p.add_argument("--"+key.replace("_","-"),type=Path)
    a=p.parse_args()
    if a.self_test:
        self_test();return
    for key in ("parent_main","parent_manifest","parent_shards",
                "out_main","out_shards","manifest"):
        if getattr(a,key) is None:
            p.error("--"+key.replace("_","-")+" required")
    stage(a)
if __name__=="__main__":
    main()

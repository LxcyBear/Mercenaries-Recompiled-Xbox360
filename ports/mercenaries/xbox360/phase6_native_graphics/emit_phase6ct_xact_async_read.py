#!/usr/bin/env python3
"""Phase 6CT: XACT asynchronous stream-read continuation.

6CS hardware crossed 0x0027E780 and reached the first real XACT wave-bank
stream read:
  NtReadFile handle=48000002 event=0 apc=0 context=01B5D648
  iosb=01B5D648 buffer=01B5D660 len=2048 offset=0
  file=game:\dataxbox\sound\music\shl_streams.xwb
The request was fenced only because Phase5H rejected any nonzero ApcContext.

Xbox/NT semantics distinguish synchronous handles through FILE_SYNCHRONOUS_IO_*
create options. Xenia likewise completes the host read immediately, fills the
IO_STATUS_BLOCK, and returns STATUS_PENDING for a non-synchronous Xbox file.

6CT mirrors that narrow behavior:
  * record Xbox create/open options per tagged native file handle;
  * keep Event and APC-routine forms fenced;
  * allow nonzero ApcContext when Event/APC routine are both NULL;
  * complete the native read immediately and write final IOSB status/bytes;
  * return STATUS_PENDING for async-opened handles after successful completion;
  * preserve all 6CS translated-pack, XACT, graphics, and hard-fence semantics.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CS-PIXEL-CHASE-0027E780-20261025-A"
BUILD_TAG = "P6CT-XACT-ASYNC-READ-20261025-A"
COOKIE_OLD = "phase6cs_env_build_cookie"
COOKIE_NEW = "phase6ct_env_build_cookie"
EMITTER_REVISION = "6CT-R1"

STATUS_SUCCESS = 0x00000000
STATUS_PENDING = 0x00000103


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CT] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"[Phase6CT] expected one {label}, found {count}"
        )
    return text.replace(old, new, 1)


def function_span(text: str, signature: str) -> tuple[int, int]:
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"[Phase6CT] function missing: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"[Phase6CT] function brace missing: {signature}")

    depth = 0
    for i in range(brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                if end < len(text) and text[end] == "\n":
                    end += 1
                return start, end
    raise SystemExit(f"[Phase6CT] function unterminated: {signature}")


def replace_function(text: str, signature: str, replacement: str) -> str:
    start, end = function_span(text, signature)
    return text[:start] + replacement + text[end:]


def install_handle_metadata(text: str) -> str:
    anchor = (
        "#define PHASE5B_HANDLE_CAP 64u\n"
        "static HANDLE s_phase5bHandles[PHASE5B_HANDLE_CAP];\n"
    )
    addition = r'''#define PHASE5B_HANDLE_CAP 64u
static HANDLE s_phase5bHandles[PHASE5B_HANDLE_CAP];
static uint32_t s_phase6ctHandleCreateOptions[PHASE5B_HANDLE_CAP];

static uint32_t s_phase6ctAsyncReadCalls;
static uint32_t s_phase6ctAsyncReadSuccesses;
static uint32_t s_phase6ctAsyncPendingReturns;
static uint32_t s_phase6ctAsyncLastHandle;
static uint32_t s_phase6ctAsyncLastOptions;
static uint32_t s_phase6ctAsyncLastContext;
static uint32_t s_phase6ctAsyncLastIoStatus;
static uint32_t s_phase6ctAsyncLastBytes;
static uint32_t s_phase6ctAsyncLastReturn;

static void phase6ct_record_handle_options(
    uint32_t token,
    uint32_t options)
{
    uint32_t index;
    if ((token & 0xFF000000u) != PHASE5B_HANDLE_TAG)
        return;
    index = token & 0x00FFFFFFu;
    if (index == 0u || index >= PHASE5B_HANDLE_CAP)
        return;
    s_phase6ctHandleCreateOptions[index] = options;
}

static uint32_t phase6ct_read_handle_options(uint32_t token)
{
    uint32_t index;
    if ((token & 0xFF000000u) != PHASE5B_HANDLE_TAG)
        return 0u;
    index = token & 0x00FFFFFFu;
    if (index == 0u || index >= PHASE5B_HANDLE_CAP)
        return 0u;
    return s_phase6ctHandleCreateOptions[index];
}

'''
    return replace_once(
        text,
        anchor,
        addition,
        "native-handle metadata anchor",
    )


def patch_open_option_recording(text: str, signature: str) -> str:
    start, end = function_span(text, signature)
    body = text[start:end]
    anchor = """    if (status == 0u)
    {
        GUEST_WRITE32(handleVa, token);"""
    replacement = """    if (status == 0u)
    {
        phase6ct_record_handle_options(token, options);
        GUEST_WRITE32(handleVa, token);"""
    if body.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CT] expected one successful-open block in {signature}, "
            f"found {body.count(anchor)}"
        )
    body = body.replace(anchor, replacement, 1)
    return text[:start] + body + text[end:]


def patch_close_metadata(text: str) -> str:
    signature = "static HANDLE phase5c_take_native_handle(uint32_t token)"
    start, end = function_span(text, signature)
    body = text[start:end]
    anchor = """    index = token & 0x00FFFFFFu;
    s_phase5bHandles[index] = NULL;
    return handle;"""
    replacement = """    index = token & 0x00FFFFFFu;
    s_phase5bHandles[index] = NULL;
    s_phase6ctHandleCreateOptions[index] = 0u;
    return handle;"""
    if body.count(anchor) != 1:
        raise SystemExit("[Phase6CT] phase5c_take_native_handle body changed")
    body = body.replace(anchor, replacement, 1)
    return text[:start] + body + text[end:]


def async_read_handler() -> str:
    return r'''static void phase5h_nt_read_file(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t handleToken;
    uint32_t eventToken;
    uint32_t apcRoutine;
    uint32_t apcContext;
    uint32_t ioStatusVa;
    uint32_t bufferVa;
    uint32_t length;
    uint32_t offsetVa;
    uint32_t offsetLow = 0u;
    uint32_t offsetHigh = 0u;
    uint32_t handleOptions;
    uint32_t completionStatus = 0u;
    uint32_t returnStatus = 0u;
    int synchronousHandle;
    DWORD bytesRead = 0u;
    DWORD error = ERROR_SUCCESS;
    HANDLE nativeHandle;
    BYTE* guestBuffer;
    char line[896];

    if (savedEsp != callEsp + 36u)
    {
        sprintf(
            line,
            "NtReadFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=36",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000DBu,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    handleToken = GUEST_READ32(callEsp + 4u);
    eventToken = GUEST_READ32(callEsp + 8u);
    apcRoutine = GUEST_READ32(callEsp + 12u);
    apcContext = GUEST_READ32(callEsp + 16u);
    ioStatusVa = GUEST_READ32(callEsp + 20u);
    bufferVa = GUEST_READ32(callEsp + 24u);
    length = GUEST_READ32(callEsp + 28u);
    offsetVa = GUEST_READ32(callEsp + 32u);

    if (offsetVa != 0u)
    {
        offsetLow = GUEST_READ32(offsetVa + 0u);
        offsetHigh = GUEST_READ32(offsetVa + 4u);
    }

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000DBu,
            savedEsp);
        return;
    }

    handleOptions = phase6ct_read_handle_options(handleToken);
    synchronousHandle =
        (handleOptions & (0x00000010u | 0x00000020u)) != 0u;

    sprintf(
        line,
        "NtReadFile LIVE FRAME: ret=%08X handle=%08X event=%08X apc=%08X context=%08X iosb=%08X buffer=%08X len=%u offset_ptr=%08X offset=%08X%08X options=%08X sync=%u esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)handleToken,
        (unsigned int)eventToken,
        (unsigned int)apcRoutine,
        (unsigned int)apcContext,
        (unsigned int)ioStatusVa,
        (unsigned int)bufferVa,
        (unsigned int)length,
        (unsigned int)offsetVa,
        (unsigned int)offsetHigh,
        (unsigned int)offsetLow,
        (unsigned int)handleOptions,
        (unsigned int)(synchronousHandle ? 1u : 0u),
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u || ioStatusVa == 0u ||
        (length != 0u && bufferVa == 0u))
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000DBu,
            savedEsp);
        return;
    }

    /*
     * Event signalling and guest APC delivery are still intentionally fenced.
     * ApcContext by itself is not an APC request. The observed XACT stream
     * request has Event=NULL, ApcRoutine=NULL and ApcContext==IoStatusBlock.
     */
    if (eventToken != 0u || apcRoutine != 0u)
    {
        trace(
            "STORAGE IO UNSUPPORTED: NtReadFile Event/APC callback form");
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_IO,
            0x800000DBu,
            savedEsp);
        return;
    }

    nativeHandle = phase5c_read_native_handle(handleToken);
    if (!nativeHandle)
        completionStatus = 0xC0000008u; /* STATUS_INVALID_HANDLE */

    guestBuffer =
        length ? guest_ptr((DWORD)bufferVa, (DWORD)length) : NULL;
    if (completionStatus == 0u && length != 0u && !guestBuffer)
    {
        phase4c_note_access_fault(bufferVa, length, 1u);
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            bufferVa,
            savedEsp);
        return;
    }

    if (completionStatus == 0u && offsetVa != 0u)
    {
        if (offsetHigh == 0xFFFFFFFFu && offsetLow == 0xFFFFFFFFu)
        {
            /* FILE_USE_FILE_POINTER_POSITION: preserve current position. */
        }
        else if ((offsetHigh & 0x80000000u) != 0u)
        {
            trace(
                "STORAGE IO UNSUPPORTED: NtReadFile negative/special byte offset");
            phase4c_escape(
                PHASE4C_BOUNDARY_STORAGE_IO,
                0x800000DBu,
                savedEsp);
            return;
        }
        else if (!phase5h_seek_absolute(
                     nativeHandle, offsetLow, offsetHigh))
        {
            error = GetLastError();
            completionStatus = 0xC0000001u; /* STATUS_UNSUCCESSFUL */
        }
    }

    if (completionStatus == 0u)
    {
        SetLastError(ERROR_SUCCESS);
        if (!ReadFile(
                nativeHandle,
                guestBuffer,
                length,
                &bytesRead,
                NULL))
        {
            error = GetLastError();
            if (error == ERROR_HANDLE_EOF)
                completionStatus = 0xC0000011u; /* STATUS_END_OF_FILE */
            else
                completionStatus = 0xC0000001u; /* STATUS_UNSUCCESSFUL */
        }
        else if (bytesRead == 0u && length > 0u)
        {
            completionStatus = 0xC0000011u; /* STATUS_END_OF_FILE */
        }
    }

    /* The host I/O is complete now, so IOSB always receives final state. */
    GUEST_WRITE32(ioStatusVa + 0u, completionStatus);
    GUEST_WRITE32(ioStatusVa + 4u, bytesRead);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000DBu,
            savedEsp);
        return;
    }

    ++s_phase5hNtReadFileCallCount;
    if (completionStatus == 0u)
        ++s_phase5hNtReadFileSuccessCount;

    returnStatus = completionStatus;

    if (!synchronousHandle && completionStatus == 0u)
    {
        /*
         * Match the practical Xbox-emulation behavior used by Xenia:
         * data + final IOSB are available immediately, but an async-opened
         * file reports STATUS_PENDING to the guest.
         */
        returnStatus = 0x00000103u; /* STATUS_PENDING */
        ++s_phase6ctAsyncReadCalls;
        ++s_phase6ctAsyncReadSuccesses;
        ++s_phase6ctAsyncPendingReturns;
        s_phase6ctAsyncLastHandle = handleToken;
        s_phase6ctAsyncLastOptions = handleOptions;
        s_phase6ctAsyncLastContext = apcContext;
        s_phase6ctAsyncLastIoStatus = completionStatus;
        s_phase6ctAsyncLastBytes = bytesRead;
        s_phase6ctAsyncLastReturn = returnStatus;

        sprintf(
            line,
            "PASS: Phase 6CT XACT async NtReadFile immediate completion handle=%08X options=%08X context=%08X iosb=%08X completion=%08X bytes=%u return=%08X calls=%u new_esp=%08X",
            (unsigned int)handleToken,
            (unsigned int)handleOptions,
            (unsigned int)apcContext,
            (unsigned int)ioStatusVa,
            (unsigned int)completionStatus,
            (unsigned int)bytesRead,
            (unsigned int)returnStatus,
            (unsigned int)s_phase6ctAsyncReadCalls,
            (unsigned int)savedEsp);
        trace(line);
    }
    else
    {
        sprintf(
            line,
            "PASS: Phase 6CT NtReadFile native continuation handle=%08X options=%08X status=%08X bytes=%u error=%u calls=%u successes=%u new_esp=%08X",
            (unsigned int)handleToken,
            (unsigned int)handleOptions,
            (unsigned int)completionStatus,
            (unsigned int)bytesRead,
            (unsigned int)error,
            (unsigned int)s_phase5hNtReadFileCallCount,
            (unsigned int)s_phase5hNtReadFileSuccessCount,
            (unsigned int)savedEsp);
        trace(line);
    }

    g_eax = returnStatus;
    g_esp = savedEsp;
}
'''


def insert_summary(text: str) -> str:
    marker = "P6CS PIXEL CHASE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CT] inherited pixel summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6CT] final summary insertion point missing")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CT ASYNC STREAM READ: calls=%u successes=%u pending=%u last_handle=%08X options=%08X context=%08X completion=%08X bytes=%u return=%08X",\n'
        f'{indent}    (unsigned int)s_phase6ctAsyncReadCalls,\n'
        f'{indent}    (unsigned int)s_phase6ctAsyncReadSuccesses,\n'
        f'{indent}    (unsigned int)s_phase6ctAsyncPendingReturns,\n'
        f'{indent}    (unsigned int)s_phase6ctAsyncLastHandle,\n'
        f'{indent}    (unsigned int)s_phase6ctAsyncLastOptions,\n'
        f'{indent}    (unsigned int)s_phase6ctAsyncLastContext,\n'
        f'{indent}    (unsigned int)s_phase6ctAsyncLastIoStatus,\n'
        f'{indent}    (unsigned int)s_phase6ctAsyncLastBytes,\n'
        f'{indent}    (unsigned int)s_phase6ctAsyncLastReturn);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    p6bl = load(args.phase6bl_emitter, "phase6ct_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cs-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CT] missing cached 6CS input: {path}")

    text = main_path.read_text(encoding="utf-8")
    env = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CS" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CT] cached 6CS identity mismatch")

    inherited = manifest.get("phase6cs_pixel_chase", {})
    if (
        inherited.get("execution_budget_inherited") != 64000000
        or inherited.get("hard_fences_changed") is not False
        or inherited.get("xact_continuity_repair_preserved") is not True
        or inherited.get("xact_sentinel_repair_preserved") is not True
    ):
        raise SystemExit("[Phase6CT] inherited 6CS policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6CS PIXEL CHASE:",
        "P6CS PRESENT PROXIMITY:",
        "case 0x0027E780u:",
        "STORAGE IO UNSUPPORTED: asynchronous NtReadFile event/APC form",
        "static HANDLE s_phase5bHandles[PHASE5B_HANDLE_CAP];",
    ):
        if marker not in text:
            raise SystemExit(f"[Phase6CT] inherited marker missing: {marker}")

    text = install_handle_metadata(text)
    text = patch_open_option_recording(
        text,
        "static void phase5h_nt_create_file(uint32_t savedEsp)",
    )
    text = patch_open_option_recording(
        text,
        "static void phase5b_nt_open_file(uint32_t savedEsp)",
    )
    text = patch_close_metadata(text)
    text = replace_function(
        text,
        "static void phase5h_nt_read_file(uint32_t savedEsp)",
        async_read_handler(),
    )
    text = insert_summary(text)

    text = replace_once(text, BASE_TAG, BUILD_TAG, "build tag")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    env = env.replace(COOKIE_OLD, COOKIE_NEW)

    text = (
        text.replace("PHASE 6CS", "PHASE 6CT")
        .replace("Phase 6CS", "Phase 6CT")
        .replace('"P6CS ', '"P6CT ')
    )
    env = (
        env.replace("PHASE 6CS", "PHASE 6CT")
        .replace("Phase 6CS", "Phase 6CT")
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "P6CT ASYNC STREAM READ:",
        "PASS: Phase 6CT XACT async NtReadFile immediate completion",
        "s_phase6ctHandleCreateOptions",
        "phase6ct_record_handle_options(token, options);",
        "0x00000103u; /* STATUS_PENDING */",
        "case 0x0027E780u:",
        "P6CT PIXEL CHASE:",
        "P6CT PRESENT PROXIMITY:",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    )
    for marker in required:
        if marker not in text:
            raise SystemExit(f"[Phase6CT] generated source lost marker: {marker}")

    if "STORAGE IO UNSUPPORTED: asynchronous NtReadFile event/APC form" in text:
        raise SystemExit("[Phase6CT] old blanket async-read fence remains")

    if text.count("phase6ct_record_handle_options(token, options);") != 2:
        raise SystemExit("[Phase6CT] handle-option recording count mismatch")

    if text.count(
        "STORAGE IO UNSUPPORTED: NtReadFile Event/APC callback form"
    ) != 1:
        raise SystemExit("[Phase6CT] Event/APC hard fence count mismatch")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env, encoding="utf-8")

    manifest.update({
        "phase": "6CT",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6ct_xact_async_read"] = {
        "source_phase": "6CS",
        "phase6cs_hardware": {
            "boundary_kind": "STORAGE_IO",
            "caller": "0x0023A3CE",
            "target": "0x800000DB",
            "ticks": 27019857,
            "trace": 1071510,
            "fault": 0,
            "xact_stream_root_entries": 1,
            "file": "game:\\dataxbox\\sound\\music\\shl_streams.xwb",
            "handle": "0x48000002",
            "event": "0x00000000",
            "apc_routine": "0x00000000",
            "apc_context": "0x01B5D648",
            "io_status_block": "0x01B5D648",
            "buffer": "0x01B5D660",
            "length": 2048,
            "offset": 0,
            "display_calls": 0,
            "framebuffer": "0x00000000",
        },
        "policy": {
            "record_handle_create_options": True,
            "immediate_host_completion": True,
            "async_guest_return": "STATUS_PENDING",
            "event_forms_fenced": True,
            "apc_callback_forms_fenced": True,
            "apc_context_without_callback_allowed": True,
            "iosb_receives_final_completion": True,
            "host_overlapped_io_used": False,
        },
        "execution_budget_inherited": 64000000,
        "translated_pack_changed": False,
        "xact_semantics_changed": False,
        "graphics_bridge_semantics_changed": False,
        "null_page_semantics_changed": False,
        "seh_terminator_semantics_changed": False,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }

    (args.out_dir / "phase6ct-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6CT] emitter revision: {EMITTER_REVISION}")
    print("[Phase6CT] HANDLE OPTIONS: NtCreateFile/NtOpenFile metadata armed")
    print(
        "[Phase6CT] XACT ASYNC READ: immediate host completion + final IOSB "
        "+ STATUS_PENDING for async handles"
    )
    print("[Phase6CT] Event/APC callback forms remain hard-fenced")
    print("[Phase6CT] 6CS translated pack/XACT/graphics semantics preserved")
    print("[Phase6CT] 64M watchdog preserved")
    print("[Phase6CT] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

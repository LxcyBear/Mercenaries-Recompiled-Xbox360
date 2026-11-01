#!/usr/bin/env python3
"""K1NT207: no-behavior-change runtime witness for retail NtQueryDirectoryFile.

Hardware stopped at ICALL_SAFE 0x800000CF immediately after an NtOpenFile
directory handle was returned. XDK/OpenXDK lists Xbox ordinal 207 as
NtQueryDirectoryFile @40 (10 DWORD arguments), but other emulator declarations
list fewer arguments. We MUST capture original live parameters before
choosing a guest FILE_DIRECTORY_INFORMATION or enumeration implementation.

This stage copies all 64 current TrueTUs untouched, adds a guarded one-shot
frame probe in phase6dq_note_hard_stop of host main.cpp, and leaves the
original hard stop in place. Absolutely NO synthetic NTSTATUS success.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

MARKER="K1NT207-DIRECTORY-FRAME-WITNESS-20261101"
PARENT="K1-XPP-INPUT-FAMILY-ONE-BUILD-20261031"
GUEST="0x800000CF"
CALLER="0x0023A3CE"
TICKS=27108191

PROBE=r'''    /* K1NT207-DIRECTORY-FRAME-WITNESS-20261101
     * Hardware: original Xbox ordinal 207, 0x800000CF, ICALL_SAFE.
     * Pure diagnostic at existing HARD STOP.  No handler, no guest writes,
     * no change to guest ABI, EAX/ESP, dispatcher or unknown MMIO fences.
     * The original Xbox @40 ABI implies ten 32-bit arguments after the
     * synthetic return dword. Capture RAW words; do not guess semantics.
     */
    if (kind == 2u && target == 0x800000CFu)
    {
        const uint32_t k1nt207_callEsp = g_esp;
        const uint32_t k1nt207_safeFrame =
            k1nt207_callEsp >= 0x00010000u &&
            k1nt207_callEsp <= 0x04000000u - 44u &&
            k1nt207_callEsp <= 0xFFFFFFFFu - 44u &&
            savedEsp == k1nt207_callEsp + 44u;
        sprintf(line,
                "K1NT207 FRAME GATE: ordinal=207 NtQueryDirectoryFile caller=%08X call_esp=%08X saved_esp=%08X delta=%u expected=44 guarded=%u",
                (unsigned)caller,
                (unsigned)k1nt207_callEsp,
                (unsigned)savedEsp,
                (unsigned)(savedEsp-k1nt207_callEsp),
                (unsigned)k1nt207_safeFrame);
        trace(line);
        if (k1nt207_safeFrame)
        {
            uint32_t a[11];
            unsigned j;
            for (j=0u;j<11u;++j)
                a[j]=GUEST_READ32(k1nt207_callEsp+j*4u);
            if (!s_accessFault)
            {
                sprintf(line,
                    "K1NT207 FRAME RAW0: ret=%08X a0=%08X a1=%08X a2=%08X a3=%08X a4=%08X",
                    (unsigned)a[0],(unsigned)a[1],(unsigned)a[2],
                    (unsigned)a[3],(unsigned)a[4],(unsigned)a[5]);
                trace(line);
                sprintf(line,
                    "K1NT207 FRAME RAW1: a5=%08X a6=%08X a7=%08X a8=%08X a9=%08X",
                    (unsigned)a[6],(unsigned)a[7],(unsigned)a[8],
                    (unsigned)a[9],(unsigned)a[10]);
                trace(line);
                sprintf(line,
                    "K1NT207 FRAME CAPTURED: original_ordinal=207 ret=%08X handle=%08X iosb_candidate=%08X output_candidate=%08X length_candidate=%u arg7=%08X arg8=%08X arg9=%08X",
                    (unsigned)a[0],(unsigned)a[1],(unsigned)a[5],
                    (unsigned)a[6],(unsigned)a[7],(unsigned)a[8],
                    (unsigned)a[9],(unsigned)a[10]);
                trace(line);
            }
            else
                trace("K1NT207 FRAME READ FAULT: capture aborted; hard fence retained");
        }
        trace("K1NT207 PROBE ONLY: NtQueryDirectoryFile NOT handled; original hard stop preserved");
    }
'''

REGEX=re.compile(
    r"(?P<start>static void phase6dq_note_hard_stop\s*\(\s*"
    r"uint32_t kind\s*,\s*uint32_t target\s*,\s*uint32_t caller\s*,\s*"
    r"uint32_t savedEsp\s*\)\s*\{\s*uint32_t i;\s*char line\[448\];)",
    re.M)

def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()

def transform(text:str)->str:
    if MARKER in text: raise ValueError("Existing K1NT207 probe present")
    if text.count("P6DQ ROCKET HARD STOP") != 1:
        raise ValueError("Rocket hard-stop runtime marker not unique")
    matches=list(REGEX.finditer(text))
    if len(matches)!=1:
        raise ValueError("phase6dq_note_hard_stop exact source anchor missing or duplicated")
    n="\r\n" if "\r\n" in text else "\n"
    if text.count("\r")!=text.count("\r\n"):
        raise ValueError("Mixed newlines in host")
    insertion=n+PROBE.replace("\n",n)
    result=text[:matches[0].end()] + insertion + text[matches[0].end():]
    if result.count(MARKER)!=1 or result.count("K1NT207 FRAME CAPTURED")!=1:
        raise ValueError("Frame probe insertion/uniqueness failed")
    if result.count("P6DQ ROCKET HARD STOP")!=1:
        raise ValueError("Original hard stop unexpectedly changed")
    return result

def stage(a):
    for p in (a.parent_main,a.parent_manifest,a.parent_shards):
        if not p.exists():raise ValueError("Missing parent source: "+str(p))
    parent=json.loads(a.parent_manifest.read_text(encoding="utf-8-sig"))
    if (parent.get("marker")!=PARENT
        or parent.get("status")!="SOURCE_CLOSED_STAGED_NO_XDK"
        or parent.get("new_main_sha")!=sha(a.parent_main)
        or Path(parent.get("staged_main","MISSING")).resolve()!=a.parent_main.resolve()
        or Path(parent.get("staged_directory","MISSING")).resolve()!=a.parent_shards.resolve()
        or parent.get("guest_display_calls_injected") is not False
        or parent.get("mmio_fences")!="UNCHANGED"
        or parent.get("hard_fences")!="UNCHANGED"):
        raise ValueError("Input family parent provenance/known-good state changed")

    grand_path=Path(parent.get("parent_manifest","MISSING"))
    if not grand_path.is_file():
        raise ValueError("Missing inherited D54AC manifest")
    grand=json.loads(grand_path.read_text(encoding="utf-8-sig"))
    if grand.get("marker")!="XPP-D54AC-NATIVE-GETSTATE-20261031":
        raise ValueError("Unexpected grandparent input stage")

    files=sorted(p for p in a.parent_shards.glob("translated_???.cpp") if p.is_file())
    headers=sorted(a.parent_shards.glob("*.h"))
    if len(files)!=64 or not (a.parent_shards/"translated_runtime.h").is_file():
        raise ValueError("Expected 64 inherited TrueTUs")
    for p in files+headers:
        expected=(parent.get("new_owner_hashes",{}).get(p.name)
                  or grand.get("new_owner_hashes",{}).get(p.name)
                  or grand.get("original_owner_hashes",{}).get(p.name))
        if not expected or sha(p)!=expected:
            raise ValueError("Inherited TrueTU hash mismatch: "+p.name)

    # Preserve the original Windows line endings; never normalize main.cpp.
    src=a.parent_main.read_bytes().decode("utf-8")
    for marker in ("XPP D54AC ENTRY", "XPP D551F ENTRY",
                   "XPP D52C8 ENTRY", "P6DQ ROCKET HARD STOP",
                   "P6DQ-R51-MM173-FRAME-20261029-A"):
        if marker not in src and marker.startswith("XPP"):
            # XPP entry instrumentation lives in the inherited TrueTU owner.
            owner=parent["parent_input_owner"]
            if marker not in (a.parent_shards/owner).read_text(encoding="utf-8"):
                raise ValueError("Missing existing input entry witness "+marker)
        elif marker not in src and not marker.startswith("XPP"):
            raise ValueError("Host provenance marker missing: "+marker)
    out=transform(src)
    if a.out_main.resolve()==a.parent_main.resolve() or a.out_shards.resolve()==a.parent_shards.resolve():
        raise ValueError("Refusing to overwrite inherited stage")
    a.out_shards.mkdir(parents=True,exist_ok=True)
    for p in files+headers:
        dst=a.out_shards/p.name
        if dst.is_file() and dst.read_bytes()!=p.read_bytes():
            raise ValueError("Existing output differs: "+str(dst))
        if not dst.exists():dst.write_bytes(p.read_bytes())
    outbytes=out.encode("utf-8")
    a.out_main.parent.mkdir(parents=True,exist_ok=True)
    if a.out_main.exists() and a.out_main.read_bytes()!=outbytes:
        raise ValueError("Existing main differs")
    if not a.out_main.exists():a.out_main.write_bytes(outbytes)
    meta={
      "marker":MARKER,
      "status":"FRAME_PROBE_STAGED_HARD_STOP_PRESERVED_NO_XDK",
      "retail_ordinal":207,
      "kernel_call_target":GUEST,
      "observed_caller":CALLER,
      "hardware_ticks_before_probe":TICKS,
      "expected_saved_esp_delta":44,
      "ten_guest_arguments_captured_raw":True,
      "native_directory_service":False,
      "hard_stop_preserved":True,
      "guest_registers_modified":False,
      "guest_memory_written":False,
      "mmio_fences":"UNCHANGED","hard_fences":"UNCHANGED",
      "guest_display_calls_injected":False,
      "parent_manifest":str(a.parent_manifest),
      "parent_main_sha256":sha(a.parent_main),
      "new_main_sha256":hashlib.sha256(outbytes).hexdigest(),
      "out_main":str(a.out_main.resolve()),
      "out_shards":str(a.out_shards.resolve()),
      "copied_true_tus":64,
      "changed_true_tus":[],
      "next_gate":"Capture raw Xbox NtQueryDirectoryFile args then implement real directory enumeration with exact guest ABI",
    }
    encoded=(json.dumps(meta,indent=2)+"\n").encode("utf-8")
    a.manifest.parent.mkdir(parents=True,exist_ok=True)
    if a.manifest.exists() and a.manifest.read_bytes()!=encoded:
        raise ValueError("Manifest drift")
    if not a.manifest.exists():a.manifest.write_bytes(encoded)
    print("[K1NT207] STAGE PASS: one host-only guarded probe, 64 TrueTUs byte-exact")
    print("[K1NT207] Original kernel ordinal 207 NtQueryDirectoryFile, call 0x800000CF")
    print("[K1NT207] NO HANDLER, NO FABRICATED SUCCESS; stops at same boundary")
    print("[K1NT207] Next hardware proof: raw a0..a9 + return, class/filename ABI analysis")

def self_test():
    stub="""static void phase6dq_note_hard_stop(
    uint32_t kind,
    uint32_t target,
    uint32_t caller,
    uint32_t savedEsp)
{
    uint32_t i;
    char line[448];

    sprintf(line,"P6DQ ROCKET HARD STOP");
}"""
    out=transform(stub)
    assert MARKER in out
    assert out.count("P6DQ ROCKET HARD STOP")==1
    assert "savedEsp == k1nt207_callEsp + 44u" in out
    assert "a[j]=GUEST_READ32(k1nt207_callEsp+j*4u)" in out
    assert "K1NT207 PROBE ONLY:" in out
    for forbidden in ("g_eax =", "g_esp =", "GUEST_WRITE32(",
                      "phase4c_escape(", "NtQueryDirectoryFile("):
        assert forbidden not in PROBE, "Unsafe behavior in diagnostic "+forbidden
    try:
        transform(out)
    except ValueError:pass
    else:raise AssertionError("Probe accidentally insertable twice")
    assert len(re.findall("GUEST_READ32\\(",PROBE))==1
    assert PROBE.count("if (kind == 2u && target == 0x800000CFu)") == 1
    print("[K1NT207] SELFTEST PASS: ordinal207 frame capture only, hard stop retained")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    for key in ("parent_main","parent_manifest","parent_shards",
                "out_main","out_shards","manifest"):
        p.add_argument("--"+key.replace("_","-"),type=Path)
    a=p.parse_args()
    if a.self_test:
        self_test();return
    for key in ("parent_main","parent_manifest","parent_shards",
                "out_main","out_shards","manifest"):
        if getattr(a,key) is None:p.error("--"+key.replace("_","-")+" required")
    stage(a)

if __name__=="__main__":
    main()

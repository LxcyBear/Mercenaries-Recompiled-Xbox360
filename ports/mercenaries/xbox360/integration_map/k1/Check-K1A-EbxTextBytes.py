#!/usr/bin/env python3
"""K1A DSOUND fault: check whether final EBX points at original retail .text.

Compares the two original XBE dwords at fault-time EBX and EBX+4 with the
observed [EBP-12] index (EAX-EDX). Does NOT touch guest RAM, disk files,
MMIO, generated sources or any deployed XEX.

A match is strong evidence the pointer was already inappropriate at the
source read, but does not prove the object pointer's earliest origin.
A mismatch could mean pre-call EBX changed, guest code was altered, or local
state was corrupted; it is NOT permission to bypass the memory fence.
"""
from __future__ import annotations
import argparse
import hashlib
import struct
from pathlib import Path

EXPECTED_SHA256="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
TEXT_GUEST_VA=0x00011000
TEXT_FILE_OFFSET=0x00001000
TEXT_RAW_SIZE=0x0024461C
FAULT_EBX=0x00041D70
FAULT_INDEX=0xFDB471D8
FAULT_TABLE_BASE=0x024A8000
FAULT_ESI=0xEFEE0EC0
MASK=0xFFFFFFFF

def read_pair(image:bytes, guest_va:int, guest_start:int, raw_start:int, raw_size:int)->tuple[int,int,int]:
    if not (guest_start<=guest_va and guest_va+8<=guest_start+raw_size):
        raise ValueError("candidate EBX not contained in verified .text section")
    offset=raw_start+(guest_va-guest_start)
    if offset+8>len(image):
        raise ValueError("retail file truncated before candidate .text dwords")
    a,b=struct.unpack_from("<II",image,offset)
    return offset,a,b

def inspect(image:bytes)->dict:
    offset,a,b=read_pair(image,FAULT_EBX,TEXT_GUEST_VA,TEXT_FILE_OFFSET,TEXT_RAW_SIZE)
    delta=(a-b)&MASK
    signed=delta-(1<<32) if delta&(1<<31) else delta
    return {
        "guest_va":FAULT_EBX, "file_offset":offset,
        "original_text_dword0":a, "original_text_dword4":b,
        "difference":delta,"signed_difference":signed,
        "observed_difference":FAULT_INDEX,
        "difference_matches_hardware":delta==FAULT_INDEX,
        "observed_index_computes_fault_esi":((FAULT_TABLE_BASE+FAULT_INDEX*8)&MASK)==FAULT_ESI,
    }

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--retail-xbe",required=True,type=Path)
    a=p.parse_args()
    if not a.retail_xbe.is_file():
        p.error("owned Mercenaries retail XBE missing: "+str(a.retail_xbe))
    image=a.retail_xbe.read_bytes()
    actual=hashlib.sha256(image).hexdigest().upper()
    if actual!=EXPECTED_SHA256:
        p.error("retail XBE SHA-256 mismatch, refuse interpretation: "+actual)
    if image[:4]!=b"XBEH":
        p.error("expected original Xbox XBE header not present")
    result=inspect(image)
    print("[K1A-EBX] RETAIL XBE IDENTITY: PASS (exact owned SHA)")
    print("[K1A-EBX] EBX=%08X is inside original .text section VA=%08X..%08X" % (
        FAULT_EBX,TEXT_GUEST_VA,TEXT_GUEST_VA+TEXT_RAW_SIZE-1))
    print("[K1A-EBX] Original .text offset=%08X dword0=%08X dword4=%08X" % (
        result["file_offset"],result["original_text_dword0"],result["original_text_dword4"]))
    print("[K1A-EBX] Original text dword difference=%08X (signed=%d)" % (
        result["difference"],result["signed_difference"]))
    print("[K1A-EBX] Observed EDX=%08X, source-byte difference match=%s" % (
        FAULT_INDEX,"YES" if result["difference_matches_hardware"] else "NO"))
    if result["difference_matches_hardware"]:
        print("[K1A-EBX] HYPOTHESIS STRONGLY SUPPORTED: DSOUND object pointer")
        print("[K1A-EBX] points into the game's original .text, yielding the exact bad index.")
        print("[K1A-EBX] STILL UNPROVEN: whether caller provided this pointer or a guest call clobbered EBX.")
    else:
        print("[K1A-EBX] HYPOTHESIS NOT CONFIRMED: final EBX dwords do not yield the")
        print("[K1A-EBX] observed index. Examine pre-call register/stack preservation")
        print("[K1A-EBX] and runtime memory mutation before interpreting this as an object.")
    print("[K1A-EBX] No game file modified, no XDK build, EFEE0EC4 remains HARD FENCED")

if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""Offline synthetic fixture for retail XBE EBX source-byte differential."""
import importlib.util
import struct
from pathlib import Path
f=Path(__file__).with_name("Check-K1A-EbxTextBytes.py")
spec=importlib.util.spec_from_file_location("merc_k1_ebx_probe",f)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)
# This is a fake byte array, not Mercenaries retail data.
mock=bytearray(32)
struct.pack_into("<II",mock,8,0,0x024B8E28)
offset,a,b=m.read_pair(mock,0x1008,0x1000,0,32)
assert (offset,a,b)==(8,0,0x024B8E28)
assert ((a-b)&0xffffffff)==m.FAULT_INDEX
assert ((m.FAULT_TABLE_BASE+m.FAULT_INDEX*8)&0xffffffff)==m.FAULT_ESI
struct.pack_into("<II",mock,8,0x104,0x100)
_,a,b=m.read_pair(mock,0x1008,0x1000,0,32)
assert ((a-b)&0xffffffff)==4
for va,raw_size in ((0x0FF8,32),(0x101C,32),(0x1008,8)):
    try:m.read_pair(mock,va,0x1000,0,raw_size)
    except ValueError:pass
    else:raise AssertionError("accepted out-of-range guest .text dwords")
try:m.read_pair(mock,0x1008,0x1000,28,32)
except ValueError:pass
else:raise AssertionError("accepted truncated file bytes")
print("[K1A-EBX] PASS: fake x86 dword subtraction, signed negative index, bounds and original fault equation")
print("[K1A-EBX] No real XBE bytes included, no source/build mutation")

#!/usr/bin/env python3
"""V6h candidate: retail-SHA-pinned SSE vec3/matrix operation at 0x0022F51C.

Read-only inherited V6g source, 64 TrueTUs and hard fences. Implements the
retail arithmetic/guest-stack behavior, no fake values, no gameplay shortcut.
The x86 SSE register side effects are caller-scratch and are not carried
forward into the translated guest state; hardware remains unverified.
"""
from pathlib import Path
import hashlib, json, re, struct, sys

ROOT=Path.cwd()
TAG="[K1-V6h]"
PARENT=ROOT/"build/phase6_integration_map/k1_pixel_camera_batch_v6g_sinebridge"
DEST=ROOT/"build/phase6_integration_map/k1_pixel_camera_vec3_v6h"
XBE=ROOT/"game_files/mercenaries-retail/default.xbe"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
VA=0x0022F51C
MARK="K1-V6H-RETAIL-SSE-VEC3-0022F51C-20261105"
# Complete retail x86 bytes from mov eax,[esp+8] through ret 0x000C.
OPCODES=bytes.fromhex(
    "8B 44 24 08 F3 0F 10 10 8B 4C 24 0C 0F C6 D2 00 "
    "0F 59 11 F3 0F 10 48 04 0F C6 C9 00 0F 59 49 10 "
    "F3 0F 10 58 08 0F C6 DB 00 0F 59 59 20 0F 58 D1 "
    "8B 44 24 04 0F 58 D3 0F 13 10 0F 12 D2 F3 0F 11 "
    "50 08 C2 0C 00"
)
# The compiler is required to materialize each single-precision product
# and sum; do not contract them into fused multiply-add operations.
BODY=r"""/* K1-V6H-RETAIL-SSE-VEC3-0022F51C-20261105
 * Retail: xmm2 = broadcast(src[0])*row0
 *               + broadcast(src[1])*row1
 *               + broadcast(src[2])*row2; store lanes 0..2.
 * This routine has three guest stack arguments and RET 0x0C.
 * Guest memory access remains under existing GUEST_READF32/WRITEF32 fences.
 */
void phase6v6h_retail_vec3_0022f51c(void)
{
    const uint32_t out = GUEST_READ32(esp + 4u);
    const uint32_t source = GUEST_READ32(esp + 8u);
    const uint32_t matrix = GUEST_READ32(esp + 12u);
    const float x = GUEST_READF32(source + 0u);
    const float y = GUEST_READF32(source + 4u);
    const float z = GUEST_READF32(source + 8u);
    const float m00 = GUEST_READF32(matrix + 0u);
    const float m01 = GUEST_READF32(matrix + 4u);
    const float m02 = GUEST_READF32(matrix + 8u);
    const float m10 = GUEST_READF32(matrix + 16u);
    const float m11 = GUEST_READF32(matrix + 20u);
    const float m12 = GUEST_READF32(matrix + 24u);
    const float m20 = GUEST_READF32(matrix + 32u);
    const float m21 = GUEST_READF32(matrix + 36u);
    const float m22 = GUEST_READF32(matrix + 40u);

    volatile float p00 = x * m00;
    volatile float p01 = y * m10;
    volatile float p02 = z * m20;
    volatile float a0 = p00 + p01;
    volatile float r0 = a0 + p02;

    volatile float p10 = x * m01;
    volatile float p11 = y * m11;
    volatile float p12 = z * m21;
    volatile float a1 = p10 + p11;
    volatile float r1 = a1 + p12;

    volatile float p20 = x * m02;
    volatile float p21 = y * m12;
    volatile float p22 = z * m22;
    volatile float a2 = p20 + p21;
    volatile float r2 = a2 + p22;

    eax = out; // retail MOV eax,[esp+4]
    ecx = matrix; // retail MOV ecx,[esp+0xC]
    GUEST_WRITEF32(out + 0u, r0);
    GUEST_WRITEF32(out + 4u, r1);
    GUEST_WRITEF32(out + 8u, r2);
    esp = esp + 16u; // RET 0x0C: pop synthetic return word + 12 argument bytes
}
"""

def sha(data): return hashlib.sha256(data).hexdigest()
def require(cond,msg):
    if not cond: raise RuntimeError(msg)

def check_retail():
    data=XBE.read_bytes()
    require(sha(data).upper()==RETAIL,"Retail XBE SHA mismatch")
    require(data[:4]==b"XBEH","Retail XBE signature mismatch")
    u32=lambda off: struct.unpack_from("<I",data,off)[0]
    base=u32(0x104); count=u32(0x11C); table=u32(0x120)-base
    require(1<=count<=64 and table>=0 and table+count*0x38<=len(data),
            "Malformed section table")
    owners=[]
    for i in range(count):
        off=table+i*0x38
        mem=u32(off+4); sz=u32(off+8); raw=u32(off+12); rawsz=u32(off+16)
        if mem<=VA and VA+len(OPCODES)<=mem+min(sz,rawsz):
            start=raw+VA-mem
            require(start+len(OPCODES)<=len(data),"Retail section raw out of bounds")
            owners.append((i,data[start:start+len(OPCODES)]))
    require(len(owners)==1 and owners[0][1]==OPCODES,
            "Original retail SSE transform byte sequence mismatch")
    return owners[0][0]

def main():
    sec=check_retail()
    manifest=json.loads((PARENT/"v6g-manifest.json").read_text(encoding="utf-8-sig"))
    parent=(PARENT/"main.cpp").read_bytes()
    require(manifest["retail_sha256"]==RETAIL,"V6g retail identity mismatch")
    require(sha(parent)==manifest["source_sha256"],"V6g parent SHA mismatch")
    tus=sorted(SHARDS.glob("translated_???.cpp"))
    require(len(tus)==64,"64 TrueTUs not present")
    hashes={f.name:sha(f.read_bytes()) for f in tus}
    require(hashes==manifest["true_tu_sha256"],"TrueTU hashes changed")
    parent_txt=parent.decode("utf-8-sig")
    eol="\r\n" if "\r\n" in parent_txt else "\n"
    base=parent_txt.replace("\r\n","\n")
    dispatch="    case 0x0022F51Cu: return phase6v6h_retail_vec3_0022f51c;"
    require("case 0x0022F51Cu:" not in base,"22F51C already owned by parent")
    require("void phase6v6h_retail_vec3_0022f51c" not in base,
            "V6h symbol already owned")
    anchor="    case 0x001F8F10u: return sub_001F8F10;"
    require(base.count(anchor)==1,"V6g dispatch anchor absent")
    where=base.index(anchor)
    headers=list(re.finditer(
        r"(?m)^[ \t]*(?:(?:static|inline)\s+)*recomp_func_t\s+"
        r"[A-Za-z_][A-Za-z_0-9]*\s*\([^;{}]*\)\s*\{", base[:where]))
    require(headers and "switch" in base[headers[-1].end():where],
            "Dispatch lookup scope is not verified")
    at=headers[-1].start()
    patched=base[:at]+BODY+"\n\n"+base[at:]
    patched=patched.replace(anchor,anchor+"\n"+dispatch,1)
    require(patched.count(MARK)==1,"V6h marker count mismatch")
    require(patched.count(dispatch)==1,"V6h dispatcher not unique")
    require(patched.count("P6DQ ROCKET HARD STOP")==base.count("P6DQ ROCKET HARD STOP"),
            "Original hard-stop evidence changed")
    require(patched.count("K1-V6b APC DELIVERED")==base.count("K1-V6b APC DELIVERED"),
            "APC evidence changed")
    require(patched.count("0x0ACE8000u")==base.count("0x0ACE8000u"),
            "Guest APC memory unchanged")
    encoded=patched.replace("\n",eol).encode("utf-8")
    info={
        "stage":"V6H_RETAIL_SSE_SOURCE_ONLY_HARDWARE_UNTESTED",
        "retail_sha256":RETAIL,
        "retail_function_va":"0x0022F51C",
        "retail_section_index":sec,
        "retail_function_bytes_sha256":sha(OPCODES),
        "retail_ret_immediate":12,
        "guest_return_stack_delta":16,
        "math":"three SSE scalar broadcasts * matrix rows; ADDPS row0+row1 then +row2; output 3 lanes",
        "floating_point_caveat":"scalar PPC arithmetic is not automatically bit-exact to x86 SSE for all NaNs/denormals/rounding modes",
        "parent_v6g_sha256":sha(parent),
        "source_sha256":sha(encoded),
        "true_tu_count":64,
        "true_tu_sha256":hashes,
        "marker":MARK,
        "source":"retail XBE exact matched bytes",
        "hardware_tested":False,
    }
    payloads=[(DEST/"main.cpp",encoded),
              (DEST/"v6h-manifest.json",(json.dumps(info,indent=2)+"\n").encode())]
    for path,content in payloads:
        if path.exists(): require(path.read_bytes()==content,"Refusing overwrite "+str(path))
    DEST.mkdir(parents=True,exist_ok=True)
    for path,content in payloads:
        if not path.exists(): path.write_bytes(content)
    require((PARENT/"main.cpp").read_bytes()==parent,"V6g source mutated")
    print(TAG+" SOURCE PASS; RETAIL BYTES PASS; section "+str(sec))
    print(TAG+" VEC3 0x0022F51C: 3x SSE rows + ret 0x0C; 64 TrueTUs intact")
    print(TAG+" MAIN: "+str(DEST/"main.cpp"))
    print(TAG+" SHA256: "+sha(encoded))
    print(TAG+" XDK BUILD AND HARDWARE EXECUTION NOT YET VERIFIED")
if __name__=="__main__":
    try: main()
    except Exception as exc:
        print(TAG+" BLOCKED: "+str(exc),file=sys.stderr)
        sys.exit(1)

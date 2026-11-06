#!/usr/bin/env python3
"""K1-V7U: insert two absent retail TLS helpers into V7I with their original x86.

Works on a local V7I main.cpp only; leaves parent and all TrueTUs untouched.
Requires original retail ABI (V7N), V7I manifest, and Phase2E TIB contract.
No inferred FS base, fake last-error synchronization, XDK, or Xbox run.
"""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path

RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
MARK="K1-V7U-RETAIL-TLS-X86-PAIR-20261106"
OLD_GET="""static void sub_0022B150(void)
{
    g_eax = s_phase4cLastError;
    g_esp += 4u;
}"""
OLD_SET="""static void sub_0022B178(void)
{
    s_phase4cLastError = GUEST_READ32(g_esp + 4u);
    g_esp += 8u;
}"""
# Exact x86 register/guest-memory order. The conditional FS28 read is
# preserved, even though its EAX result is subsequently overwritten.
# PHASE2E establishes the FS base at guest address zero (not Xenon FS).
# The only EFLAGS modification is the arithmetic flags from cmp al,2.
# As with the old translated functions, g_esp includes the return slot.
# We retain existing guest-access wrappers and their hard fences.
NEW_GET="""/* K1-V7U retail 0022B150: full FS/TLS getter, ret (4-byte return slot). */
static void sub_0022B150(void)
{
    const uint8_t selector = GUEST_READ8(0x24u);
    const uint8_t diff = (uint8_t)(selector - 2u);
    const uint32_t oldflags = g_eflags;
    uint32_t flags = 0u;
    uint8_t parity = diff;
    parity ^= (uint8_t)(parity >> 4);
    parity &= 0xFu;
    if (selector < 2u) flags |= 0x0001u; /* CF */
    if ((uint8_t)diff == 0u) flags |= 0x0040u; /* ZF */
    if ((diff & 0x80u) != 0u) flags |= 0x0080u; /* SF */
    if (((selector ^ 2u ^ diff) & 0x10u) != 0u) flags |= 0x0010u; /* AF */
    if (((selector ^ 2u) & (selector ^ diff) & 0x80u) != 0u) flags |= 0x0800u; /* OF */
    if (((0x9669u >> parity) & 1u) != 0u) flags |= 0x0004u; /* PF */
    g_eax = selector; /* movzx eax, byte ptr fs:[24] */
    g_eflags = (oldflags & ~0x08D5u) | flags;
    if (selector < 2u) g_eax = GUEST_READ32(0x28u);
    g_eax = GUEST_READ32(0x00869118u);
    g_ecx = GUEST_READ32(0x04u);
    g_eax = GUEST_READ32(g_ecx + g_eax * 4u);
    g_eax = GUEST_READ32(g_eax + 4u);
    g_esp += 4u;
}"""
NEW_SET="""/* K1-V7U retail 0022B178: full FS/TLS setter, ret 4 (8 bytes total). */
static void sub_0022B178(void)
{
    const uint8_t selector = GUEST_READ8(0x24u);
    const uint8_t diff = (uint8_t)(selector - 2u);
    const uint32_t oldflags = g_eflags;
    uint32_t flags = 0u;
    uint8_t parity = diff;
    parity ^= (uint8_t)(parity >> 4);
    parity &= 0xFu;
    if (selector < 2u) flags |= 0x0001u;
    if (diff == 0u) flags |= 0x0040u;
    if ((diff & 0x80u) != 0u) flags |= 0x0080u;
    if (((selector ^ 2u ^ diff) & 0x10u) != 0u) flags |= 0x0010u;
    if (((selector ^ 2u) & (selector ^ diff) & 0x80u) != 0u) flags |= 0x0800u;
    if (((0x9669u >> parity) & 1u) != 0u) flags |= 0x0004u;
    g_eax = selector;
    g_eflags = (oldflags & ~0x08D5u) | flags;
    if (selector < 2u) g_eax = GUEST_READ32(0x28u);
    g_ecx = GUEST_READ32(0x04u);
    g_eax = GUEST_READ32(0x00869118u);
    g_eax = GUEST_READ32(g_ecx + g_eax * 4u);
    g_ecx = GUEST_READ32(g_esp + 4u);
    GUEST_WRITE32(g_eax + 4u, g_ecx);
    g_esp += 8u;
}"""
def need(ok,msg):
    if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def fetch_func(code,name):
    pattern=r"(?m)^[ \t]*static void "+re.escape(name)+r"\(void\)\s*\{\s*"
    match=list(re.finditer(pattern,code))
    need(len(match)==1,"Missing or duplicate original helper definition: "+name)
    opening=code.index("{",match[0].start(),match[0].end())
    depth=0
    for idx in range(opening,len(code)):
        if code[idx]=="{":depth+=1
        elif code[idx]=="}":
            depth-=1
            if depth==0:
                return code[match[0].start():idx+1]
    raise ValueError("Unclosed original helper")
def check_provenance(parent,manifest,abi,phase2):
    need(manifest.get("stage")=="V7I_HARDWARE_OBSERVED_APC_IOSB_ALLOWLIST_SOURCE_ONLY" and
         manifest.get("source_sha256")==sha(parent) and
         manifest.get("retail_original_xbe_sha256")==RETAIL and
         len(manifest.get("true_tu_sha256",{}))==64 and
         manifest.get("apc_pending_wait_guard_preserved") is True and
         manifest.get("completion_status_check_preserved") is True and
         manifest.get("no_guest_abi_bypass") is True,
         "V7I SHA, retail identity or unchanged source safeguards did not validate")
    rows={int(x["va"],16):x for x in abi.get("functions",[])}
    need(abi.get("status")=="K1_V7N_RET_ABI_AND_INDIRECT_BRANCH_BATCH_PLAN" and
         abi.get("retail_sha256")==RETAIL and
         abi.get("v7i_source_sha256")==sha(parent) and
         rows[0x22B150]["ret_esp_values"]==[0] and
         rows[0x22B178]["ret_esp_values"]==[4] and
         not rows[0x22B150]["indirect_calls"] and
         not rows[0x22B178]["indirect_calls"],
         "Original retail x86 ABI evidence changed")
    for s in (
        "guest_write32(memory, 0x04u,",
        "guest_write32(memory, 0x28u, MERC_FAKE_KTHREAD_VA)",
        "guest_read32(memory, 0x04u, &tlsBaseField)",
        "guest_read32(memory, 0x28u, &fakeKthread)",
        "resolvedTls == MERC_FAKE_TLS_VA",
        "TLS index readback",
    ):need(s in phase2,"Phase2E guest FS/TLS low-memory contract absent: "+s)
def patch(src):
    """Insert the missing retail pair into the one real V7I pack lookup."""
    need(MARK not in src, "V7U marker already present")
    for sym in ("g_eflags","g_eax","g_ecx","g_esp","GUEST_READ8",
                "GUEST_READ32","GUEST_WRITE32"):
        need(sym in src,"Missing translated runtime primitive "+sym)
    for va in (0x22B150,0x22B178):
        name="sub_%08X"%va
        definitions=re.findall(
            r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+"+name+
            r"\s*\(\s*void\s*\)\s*\{",src)
        need(not definitions,
             "Existing TLS function needs manual reconciliation: "+name)
        need(not re.search(r"\bcase\s+0x%08X[uUlL]*\s*:"%va,src,re.I),
             "Pre-existing TLS switch case "+name)
        need(not re.search(r"\bif\s*\(\s*xbox_va\s*==\s*0x%08X[uUlL]*"%va,src,re.I),
             "Pre-existing TLS lookup route "+name)
    pattern=(r"(?m)^[ \t]*recomp_func_t[ \t]+phase4c_lookup_pack_func"
             r"\(uint32_t xbox_va\)\s*\{")
    matches=list(re.finditer(pattern,src))
    need(len(matches)==1,
         "Expected exactly one full packed lookup; found %d"%len(matches))
    definition=matches[0]
    anchor=definition.group(0)
    routes=(
        "    /* K1-V7U: unique original retail TLS lookup routes. */\n"
        "    if (xbox_va == 0x0022B150u) return sub_0022B150;\n"
        "    if (xbox_va == 0x0022B178u) return sub_0022B178;\n"
    )
    inserted=NEW_GET+"\n\n"+NEW_SET+"\n\n"+anchor+"\n"+routes
    result=src[:definition.start()]+inserted+src[definition.end():]
    need(result.replace(inserted,anchor,1)==src,
         "Unexpected modification outside TLS functions and lookup routes")
    for va in (0x22B150,0x22B178):
        name="sub_%08X"%va
        need(len(re.findall(r"\bstatic void "+name+r"\(void\)\s*\{",result))==1,
             "New TLS function definition not unique "+name)
        need(result.count("if (xbox_va == 0x%08Xu) return %s;"%(va,name))==1,
             "New TLS lookup route not unique "+name)
    return "/* "+MARK+" */\n"+result
def main():
    p=argparse.ArgumentParser()
    for n in ("parent","manifest","abi","phase2e","out","out_manifest"):
        p.add_argument("--"+n.replace("_","-"),required=True,type=Path)
    a=p.parse_args()
    original=a.parent.read_bytes()
    manifest=json.loads(a.manifest.read_text(encoding="utf-8-sig"))
    abi=json.loads(a.abi.read_text(encoding="utf-8-sig"))
    phase2=a.phase2e.read_text(encoding="utf-8-sig")
    check_provenance(original,manifest,abi,phase2)
    newline="\r\n" if b"\r\n" in original else "\n"
    before=original.decode("utf-8").replace("\r\n","\n")
    after=patch(before).replace("\n",newline).encode("utf-8")
    metadata=dict(manifest)
    metadata.update({
        "stage":"V7U_RETAIL_X86_TLS_PAIR_IN_V7I_SOURCE_ONLY",
        "parent_v7i_sha256":sha(original),
        "source_sha256":sha(after),
        "original_tls_functions":["0x0022B150","0x0022B178"],
        "tls_abi_return_cleanup_bytes":[0,4],
        "translated_guest_return_advances_bytes":[4,8],
        "fs_guest_low_address_mapping_proven_in_phase2e":True,
        "fs24_selector_source":"guest RAM byte at FS-relative 0x24 (no invented value)",
        "flags_mask":"0x08D5",
        "inserted_missing_tls_helpers_and_lookup_routes":True,
        "apc_and_storage_fences_unchanged":True,
        "source_only":True,"xdk_compiled":False,"xbox_verified":False,
    })
    outputs=[(a.out,after),
             (a.out_manifest,(json.dumps(metadata,indent=2)+"\n").encode("utf-8"))]
    for path,data in outputs:
        need(not path.exists() or path.read_bytes()==data,
             "Existing output differs; refusing overwrite: "+str(path))
    for path,data in outputs:
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.write_bytes(data)
    need(a.parent.read_bytes()==original,"Parent changed during stage")
    print("[K1-V7U] SOURCE PATCH PASS: original retail TLS pair inserted into V7I lookup")
    print("[K1-V7U] Original Phase2E FS4/FS28/negative-index mapping + V7N ret0/ret4 PASS")
    print("[K1-V7U] Preserve guest FS24 conditional read, EAX/ECX, CMP flags, 4/8 stack advances")
    print("[K1-V7U] Unique new lookup routes; V7I APC/stream/graphics unchanged")
    print("[K1-V7U] SOURCE OUTPUT "+str(a.out))
    print("[K1-V7U] NO XDK / NO XBOX; BUILD NOT YET AUTHORISED")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[K1-V7U] HARD FENCE "+str(e),file=sys.stderr)
        sys.exit(1)

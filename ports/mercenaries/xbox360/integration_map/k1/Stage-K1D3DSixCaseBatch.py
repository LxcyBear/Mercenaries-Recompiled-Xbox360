#!/usr/bin/env python3
"""K1 D3D: one source-authentic six-case graphics dispatch integration.

Replaces only the original RECOMP_ITAIL at sub_00296550 with a
SHA-verified 0..5 dispatch. All other targets retain the existing hard
fence. The six branches rejoin at real, already-compiled sub_002965A8.

No fabricated frame, result, source instruction or MMIO read; one changed
original 64-shard translation unit maximum; source-only by default.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

RETAIL_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
MARK = "K1D3D-296550-SIXCASES-ONEBUILD-20261103"
PARENT_STATUS = "K1_D3D_DIRECT_289E20_SOURCE_ONLY_NO_XDK"
STATUS = "K1_D3D_SIX_CASES_SOURCE_ONLY_NO_XDK"
ROOT = 0x00296550
COMMON = 0x002965A8
CASE_VAS = (0x002965A3, 0x00296599, 0x0029655D,
            0x00296577, 0x0029657E, 0x00296592)
SOURCE_SWITCH_BYTES_SHA256 = (
    "16cf010d3ac3a3db719ed76a153309897744e638bdcef0b99a3bf8f40083e191"
)
DEFINITION = re.compile(
    r'(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})'
    r'[ \t]*\(\s*void\s*\)\s*\{'
)
ONE_TAIL = re.compile(
    r'g_seh_ebp\s*=\s*ebp\s*;\s*'
    r'RECOMP_ITAIL\s*\(\s*GUEST_READ32\s*\(\s*eax\s*\*\s*4'
    r'\s*\+\s*0x2965D4\s*\)\s*\)\s*;\s*return\s*;\s*'
    r'/\*\s*indirect\s+tail\s+jmp\s*\*/'
)
ORIGINAL_PREFIX = (
    r'loc_00296550\s*:\s*;\s*'
    r'eax\s*=\s*edi\s*;\s*'
    r'PUSH32\s*\(\s*esp\s*,\s*esi\s*\)\s*;\s*'
    r'eax\s*=\s*eax\s*&\s*0xF\s*;'
)
RECOMP_HEADER = '#include "translated_runtime.h"'

# The guest register expressions are taken from all six exact retail
# instruction streams, plus their common original return target 002965A8.
# The original indirect-tail caller already executes PUSH32(esp, esi)
# and sets g_seh_ebp before this helper. Do NOT repeat that push.
SIX_CASES = r'''
/* K1D3D-296550-SIXCASES-ONEBUILD-20261103
 * Retail XBE SHA AA08EA21... / exact six-case x86 opcode fingerprint.
 * Guest source:
 *   00296550: eax=edi; PUSH32(esp,esi); eax &= 0xF;
 *             ITAIL(GUEST_READ32(eax*4+0x002965D4)).
 * If this original table contains anything but its six proved targets
 * at these six indices, return 0 and use the existing ITAIL hard fence.
 * No host fallback, synthetic pixels, or invented graphics success.
 */
static int k1d3d_296550_original_sixcase(uint32_t slot, uint32_t target)
{
    static const uint32_t original_case_target[6] = {
        0x002965A3u, 0x00296599u, 0x0029655Du,
        0x00296577u, 0x0029657Eu, 0x00296592u
    };
    if (slot >= 6u || target != original_case_target[slot])
        return 0;

    switch (slot)
    {
    case 0u:
        /* 002965A3: mov esi,4 */
        esi = 4u;
        break;
    case 1u:
        /* 00296599: test dl,10h; mov esi,0Ch; je A8; mov esi,4 */
        esi = ((edx & 0x10u) != 0u) ? 4u : 12u;
        break;
    case 2u:
        /* 0029655D: mov eax,edx; and eax,3;
         * mov esi,[eax*4+0029A308]; test esi,esi;
         * if zero: or esi,FFFFFFFF; else lea esi,[eax+8].
         */
        eax = edx & 3u;
        esi = GUEST_READ32(eax * 4u + 0x0029A308u);
        if (esi == 0u)
            esi = 0xFFFFFFFFu;
        else
            esi = eax + 8u;
        break;
    case 3u:
        /* 00296577: mov esi,1 */
        esi = 1u;
        break;
    case 4u:
        /* 0029657E: mov eax,[00299388]; or eax,40h;
         * mov esi,5; mov [00299388],eax.
         */
        eax = GUEST_READ32(0x00299388u);
        eax |= 0x40u;
        esi = 5u;
        GUEST_WRITE32(0x00299388u, eax);
        break;
    case 5u:
        /* 00296592: mov esi,0Dh */
        esi = 13u;
        break;
    default:
        return 0;
    }

    /* All six cases perform an original jmp/fall-through to 002965A8.
     * This is an x86 tail jump, NOT a guest call: do not PUSH32 a return
     * address. Already compiled original A8 performs shared arithmetic,
     * pop esi and ret, consuming the original 96550-saved guest ESI.
     */
    sub_002965A8();
    return 1;
}
'''

REWRITE = r'''g_seh_ebp = ebp;
    {
        const uint32_t k1_original_tail_target =
            GUEST_READ32(eax * 4u + 0x002965D4u);
        if (k1d3d_296550_original_sixcase(eax, k1_original_tail_target))
            return;
        RECOMP_ITAIL(k1_original_tail_target); return; /* original unknown-tail fence */
    }'''


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def imported(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Missing maintained source tool: " + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_function(blob: str, va: int, base) -> tuple[str, int, int]:
    masked = base.mask_noncode(blob)
    matches = [m for m in DEFINITION.finditer(masked)
               if int(m.group(1), 16) == va]
    if len(matches) != 1:
        raise ValueError("Expected one actual original %08X function definition; found %d" %
                         (va, len(matches)))
    found = matches[0]
    open_brace = masked.find("{", found.start(), found.end())
    if open_brace == -1:
        raise ValueError("Missing original x86 function brace")
    end = base.closing_brace(masked, open_brace)
    return blob[found.start():end], found.start(), end


def patch_owner(text: str, base, same_owner_common: bool,
                allow_other_translation_unit: bool) -> str:
    original, start, end = get_function(text, ROOT, base)
    if MARK in text:
        raise ValueError("D3D switch already installed; no duplicate patch")
    if len(re.findall(ORIGINAL_PREFIX, base.mask_noncode(original))) != 1:
        raise ValueError("Original 296550 EDI/index/ESI PUSH contract changed")
    if len(ONE_TAIL.findall(original)) != 1:
        raise ValueError("Original 296550 indirect-tail body differs; refuse ABI guess")
    if original.count("RECOMP_ITAIL") != 1:
        raise ValueError("Multiple RECOMP_ITAIL instructions in original function")
    if not same_owner_common and not allow_other_translation_unit:
        raise ValueError("Original common 2965A8 lacks external linker proof")
    changed, n = ONE_TAIL.subn(lambda _: REWRITE, original)
    if n != 1 or "RECOMP_ITAIL(k1_original_tail_target)" not in changed:
        raise ValueError("Original hard fence lost")
    prototype = "void sub_002965A8(void);"
    if same_owner_common and re.search(
        r'(?m)^[ \t]*static[ \t]+void[ \t]+sub_002965A8', text
    ):
        prototype = "static void sub_002965A8(void);"
    # The caller C++ unit sees the original common function through
    # a proof-checked declaration; it is never an emulated replacement.
    prefix = (prototype + "\n" + SIX_CASES + "\n")
    patched = text[:start] + prefix + changed + text[end:]
    if patched.count("k1d3d_296550_original_sixcase(eax, k1_original_tail_target)") != 1:
        raise ValueError("Six-case integration missing or duplicated")
    if patched.count(SIX_CASES) != 1 or patched.count("RECOMP_ITAIL(k1_original_tail_target)") != 1:
        raise ValueError("Authentic source or unknown-target hard fence lost")
    return patched


def proof_from_xbe(xbe: Path, auditor) -> dict:
    try:
        import capstone as cap
    except ImportError as exc:
        raise ValueError("Capstone x86-32 required: python -m pip install capstone") from exc
    blob, sections = auditor.get_retail_sections(xbe)
    table = auditor.bytes_at(blob, sections, auditor.TABLE, 28)
    import struct
    expected = struct.unpack("<7I", table)
    proof = auditor.classify_static_slots(expected)
    if tuple(expected[:6]) != CASE_VAS or expected[6] != 0xCCCCCCCC:
        raise ValueError("Original six-way case target or sentinel mismatch")
    cs = cap.Cs(cap.CS_ARCH_X86, cap.CS_MODE_32)
    cs.detail = True
    paths = [auditor.decode_case(cs, cap, blob, sections, addr)
             for addr in CASE_VAS]
    unique = {}
    for row in paths:
        if row["hazards"] or not row["decode_complete_within_static_code_window"]:
            raise ValueError("Unresolved original x86 branch path: " + row["case_entry_va"])
        if not any(e["kind"] == "return" and e["from"] == "0x002965D0"
                   for e in row["control_flow_edges"]):
            raise ValueError("Case lacks original common 002965D0 return")
        for ins in row["instructions"]:
            va = int(ins["va"], 16)
            raw = ins["bytes"].replace(" ", "")
            if va in unique and unique[va] != raw:
                raise ValueError("Original x86 instruction byte overlap changed")
            unique[va] = raw
    machine_fingerprint = digest(
        "\n".join("%08X:%s" % (va, unique[va]) for va in sorted(unique))
        .encode("ascii")
    )
    if len(unique) != 41 or machine_fingerprint != SOURCE_SWITCH_BYTES_SHA256:
        raise ValueError("Original six-case x86 opcode corpus changed: " + machine_fingerprint)
    if 0x002965A8 not in unique or unique.get(0x002965D0) != "c3":
        raise ValueError("Original case common-tail RET not decoded")
    return {
        "machine_opcode_fingerprint_sha256": machine_fingerprint,
        "machine_instruction_count": len(unique),
        "original_case_targets": ["0x%08X" % v for v in CASE_VAS],
        "retail_xbe_sha256": RETAIL_SHA,
        "source_dispatch_index_rule": proof["source_rule"],
        "all_paths_reach_original_002965D0_ret": True,
        "case_2_hardware_target": "0x0029655D",
        "original_case_source_window_sha256": digest(
            auditor.bytes_at(blob, sections, auditor.CODE_FIRST,
                             auditor.CODE_STOP - auditor.CODE_FIRST)),
    }


def safe_write(path: Path, payload: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_bytes() != payload:
            raise ValueError("Stale derived stage differs; refusing overwrite: " + str(path))
    elif path.exists():
        raise ValueError("Stage destination is not a regular file: " + str(path))
    else:
        path.write_bytes(payload)


def stage(a):
    audit = imported(a.audit_module, "k1sixcase_original_auditor")
    base = imported(a.base_module, "k1sixcase_recomp_source")
    prior = json.loads(a.parent_manifest.read_text(encoding="utf-8-sig"))
    if (prior.get("status") != PARENT_STATUS or
        prior.get("original_xbe_sha256") != RETAIL_SHA or
        prior.get("new_main_sha256") != digest(a.parent_main.read_bytes()) or
        prior.get("native_xenos_reset_replaced") is not False or
        prior.get("unknown_mmio_fences_changed") is not False or
        prior.get("fake_guest_pixels") is not False or
        prior.get("original_true_tus") != 64 or
        prior.get("modified_true_tus") != 0 or
        prior.get("pc_texture_diagnostic_caller_binding", {}).get(
            "diagnostic_caller_va") != "0x00289E20"):
        raise ValueError("Prior exact working graphics source and native Reset contract changed")
    proof = proof_from_xbe(a.xbe, audit)
    raw_main = a.parent_main.read_bytes()
    shard_paths = sorted(a.shards.glob("translated_???.cpp"))
    if len(shard_paths) != 64 or not (a.shards / "translated_runtime.h").is_file():
        raise ValueError("Exactly 64 original TrueTUs and their runtime header required")
    original_shards = {path.name: path.read_bytes() for path in shard_paths}
    for name, blob in original_shards.items():
        if prior.get("true_tu_sha256", {}).get(name) != digest(blob):
            raise ValueError("Original TrueTU hash changed vs hardware-proven predecessor: " + name)
    original_header = (a.shards / "translated_runtime.h").read_bytes()
    def files_with(va: int) -> list[tuple[str, str]]:
        sources = {"main.cpp": raw_main.decode("utf-8")}
        sources.update((n, b.decode("utf-8")) for n, b in original_shards.items())
        return [(name, text) for name, text in sources.items()
                if len([m for m in DEFINITION.finditer(base.mask_noncode(text))
                        if int(m.group(1), 16) == va]) == 1]
    original_owners = files_with(ROOT)
    common_owners = files_with(COMMON)
    if len(original_owners) != 1 or len(common_owners) != 1:
        raise ValueError("Original 296550 dispatcher or 2965A8 shared tail not uniquely compiled")
    owner, owner_source = original_owners[0]
    common_owner, common_source = common_owners[0]
    common_body, _, _ = get_function(common_source, COMMON, base)
    if (not re.search(r'loc_002965A8\s*:\s*;', common_body) or
        not re.search(r'\besi\s*=', common_body) or
        not re.search(r'\breturn\s*;', common_body)):
        raise ValueError("Original compiled 2965A8 common return contract missing")
    generated = base.load_generated(
        a.generated_root, base.load_ranges(a.functions)[1]
    )
    if ROOT not in generated or COMMON not in generated or \
       generated[ROOT]["file"] != "recomp_0013.c" or \
       generated[COMMON]["file"] != "recomp_0013.c":
        raise ValueError("Retail original switch/common functions absent from generated corpus")
    retail_original = generated[ROOT]["source"]
    if (len(re.findall(ORIGINAL_PREFIX, base.mask_noncode(retail_original))) != 1 or
        len(ONE_TAIL.findall(retail_original)) != 1):
        raise ValueError("Original retail-generated 296550 switch source changed")
    if (owner != common_owner and re.search(
         r'(?m)^[ \t]*static[ \t]+void[ \t]+sub_002965A8', common_source
    )):
        raise ValueError("2965A8 is local/static in another TrueTU: direct tail inaccessible")
    modified_owner = patch_owner(
        owner_source, base, same_owner_common=(owner == common_owner),
        allow_other_translation_unit=(owner != common_owner)
    ).encode("utf-8")
    if MARK not in modified_owner.decode("utf-8"):
        raise ValueError("Six-case source marker not staged")
    next_main = modified_owner if owner == "main.cpp" else raw_main
    changed_shards = {n: modified_owner if n == owner else blob
                      for n, blob in original_shards.items()}
    changed_count = sum(changed_shards[n] != original_shards[n]
                        for n in original_shards)
    if (owner == "main.cpp" and changed_count != 0) or \
       (owner != "main.cpp" and changed_count != 1):
        raise ValueError("Exactly one original compiler unit may change; header unchanged")
    if (b"K1D3D SECOND: native Xenos Reset PASS" not in next_main or
        b"P6DQ ROCKET HARD STOP" not in next_main or
        b"K1STATE MAIN CHECKPOINT:" not in next_main or
        b"case 0x00289E20u: return sub_00289E20;" not in next_main):
        raise ValueError("Hardware-proven graphics source, lookup, or hard fence lost")
    manifest = {
        "status": STATUS,
        "marker": MARK,
        "original_retail_xbe_sha256": RETAIL_SHA,
        "proof": proof,
        "parent_main_sha256": digest(raw_main),
        "staged_main_sha256": digest(next_main),
        "original_true_tus": 64,
        "changed_true_tus": [owner] if owner != "main.cpp" else [],
        "changed_true_tu_count": changed_count,
        "modified_runtime_header": False,
        "original_runtime_header_sha256": digest(original_header),
        "next_runtime_header_sha256": digest(original_header),
        "source_root_owner": owner,
        "original_common_tail_owner": common_owner,
        "real_original_common_tail_va": "0x002965A8",
        "original_indirect_tail_va": "0x00296550",
        "hardware_case_va": "0x0029655D",
        "preserves_unknown_tail_hard_fence": True,
        "original_64_tu_hashes": {n: digest(b) for n,b in original_shards.items()},
        "derived_64_tu_hashes": {n: digest(b) for n,b in changed_shards.items()},
        "xenos_reset_source_unchanged": True,
        "synthetic_guest_pixels": False,
        "xdk_verified": False,
        "hardware_verified": False,
        "remaining_original_d3d_graph_candidates_not_in_this_batch": [
            "0x00290610", "0x00290670"
        ],
    }
    safe_write(a.out_main, next_main)
    safe_write(a.out_shards / "translated_runtime.h", original_header)
    for name, blob in changed_shards.items():
        safe_write(a.out_shards / name, blob)
    safe_write(a.manifest, (json.dumps(manifest, indent=2)+"\n").encode("utf-8"))
    if a.parent_main.read_bytes() != raw_main:
        raise ValueError("Parent graphics main mutated during six-case source stage")
    for path in shard_paths:
        if path.read_bytes() != original_shards[path.name]:
            raise ValueError("Original 64 TrueTU source unexpectedly mutated")
    print("[K1D3D-SIX] RETAIL ORIGINAL XBE / SIX-CASE X86 BYTES PASS")
    print("[K1D3D-SIX] Original case targets 6/6; shared exact common tail 002965A8 -> pop esi; ret")
    print("[K1D3D-SIX] SOURCE OWNER %s; original shared common tail owner %s" %
          (owner, common_owner))
    print("[K1D3D-SIX] 64 TrueTUs retained; changed=%d (one compiled source unit maximum)" %
          changed_count)
    print("[K1D3D-SIX] All other indirect tail targets remain HARD FENCED")
    print("[K1D3D-SIX] Native second Xenos Reset and original graphics lookup retained")
    print("[K1D3D-SIX] SOURCE ONLY. NO XDK, no Xbox, no pixels claimed. Manifest: " +
          str(a.manifest))


def selftest():
    class Base:
        @staticmethod
        def mask_noncode(s):
            # Real generated source loader strips comments without changing
            # offset; these fixtures intentionally contain no string macros.
            return re.sub(r'/\*.*?\*/', lambda m: " "*len(m.group()), s, flags=re.S)
        @staticmethod
        def closing_brace(s, start):
            depth = 0
            for i in range(start, len(s)):
                if s[i] == "{":
                    depth += 1
                elif s[i] == "}":
                    depth -= 1
                    if not depth:
                        return i+1
            raise ValueError("Unterminated body")
    example = """
#include "translated_runtime.h"
void sub_002965A8(void) { loc_002965A8: ; esi = POP32(esp); return; }
void sub_00296550(void)
{
    uint32_t ebp;
    ebp = g_seh_ebp;
    loc_00296550: ;
    eax = edi;
    PUSH32(esp, esi);
    eax = eax & 0xF;
    g_seh_ebp = ebp; RECOMP_ITAIL(GUEST_READ32(eax * 4 + 0x2965D4)); return; /* indirect tail jmp */
}
"""
    updated = patch_owner(example, Base, same_owner_common=True,
                          allow_other_translation_unit=False)
    assert updated.count(MARK) == 1
    assert "RECOMP_ITAIL(k1_original_tail_target); return;" in updated
    assert "sub_002965A8();" in updated
    assert len(re.findall(r"case [0-5]u:", updated)) == 6
    assert len(re.findall(r"\bPUSH32\s*\(\s*esp\s*,\s*esi\s*\)", updated)) == 1
    assert example not in updated
    for invalid in (
        example.replace("eax = eax & 0xF;", "eax = eax & 7;"),
        example.replace("GUEST_READ32(eax * 4 + 0x2965D4)", "GUEST_READ32(eax*8 + 0x2965D4)"),
        example.replace("g_seh_ebp = ebp;", "g_seh_ebp = 0;"),
        updated,
    ):
        try:
            patch_owner(invalid, Base, True, False)
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe switch source accepted")
    print("[K1D3D-SIX] SELFTEST PASS: six exact cases, original PUSH/RET via common tail, unknown hard fence, no XDK")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    for name in ("xbe", "audit-module", "base-module", "parent-main",
                 "parent-manifest", "shards", "generated-root", "functions",
                 "out-main", "out-shards", "manifest"):
        p.add_argument("--"+name, type=Path)
    a = p.parse_args()
    if a.self_test:
        selftest()
        return
    for name in ("xbe", "audit_module", "base_module", "parent_main",
                 "parent_manifest", "shards", "generated_root", "functions",
                 "out_main", "out_shards", "manifest"):
        if getattr(a, name) is None:
            p.error("Missing --"+name.replace("_", "-"))
    stage(a)


if __name__ == "__main__":
    main()

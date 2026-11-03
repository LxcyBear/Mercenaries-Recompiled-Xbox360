#!/usr/bin/env python3
"""Read-only PC reference evidence + exact retail branch restoration.

This is NOT a generic PC->Xbox shim. The maintained PC project explicitly
changes retail branch 002228F0 for an optional developer-region import.
We accept only the exact known before/after templates whose SHA256s are in
the pinned PC patch inventory, plus independent verified retail XBE x86
CMP [ecx+0x48],3 / JNE 00222947 evidence.
Restore the retail branch, not a made-up true/false host helper.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PC_SHA = "f513ae4e041401b7b032410016940971488d523b"
XBE_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
PATCH_NAME = "developer import reuse of completed streaming buffers"
HELPER = "recomp_dev_region_import_active"
SITE = 0x002228F0
JNE_DEST = 0x00222947
PC_PATCH_SCRIPT = "ports/mercenaries/scripts/Patch-Generated.py"
PC_INVENTORY = "ports/mercenaries/data/generated-patch-inventory.json"


def digest(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def read_templates(pc_root: Path) -> tuple[str, str, dict]:
    code_file = pc_root / PC_PATCH_SCRIPT
    inventory_file = pc_root / PC_INVENTORY
    code = code_file.read_text(encoding="utf-8")
    doc = json.loads(inventory_file.read_text(encoding="utf-8"))
    if doc.get("retail_xbe_sha256", "").upper() != XBE_SHA:
        raise ValueError("Pinned PC patch inventory points to a different retail XBE")
    items = [x for x in doc.get("transformations", [])
             if x.get("name") == PATCH_NAME]
    if len(items) != 1:
        raise ValueError("Expected exactly one original developer import source transformation")
    item = items[0]
    if (item.get("guest_sites") != ["002228F0", "00222947"] or
            item.get("host_helpers") != [HELPER]):
        raise ValueError("PC developer import guest address/host helper provenance changed")
    pattern = (r'GeneratedPatch\(\s*"' + re.escape(PATCH_NAME) +
               r'"\s*,\s*"""(?P<before>.*?)"""\s*,\s*"""(?P<after>.*?)"""\s*,\s*\)')
    matches = list(re.finditer(pattern, code, re.DOTALL))
    if len(matches) != 1:
        raise ValueError("PC patch definition missing/duplicated in verified maintained source")
    before, after = matches[0].group("before"), matches[0].group("after")
    if (digest(before) != item["before_sha256"] or
            digest(after) != item["after_sha256"]):
        raise ValueError("PC original retail/host patch templates differ from inventory hashes")
    if (not before.startswith("loc_002228F0: ;\n") or
            "CMP_NE(MEM32(ecx + 0x48), 3)" not in before or
            "goto loc_00222947;" not in before or
            HELPER in before or
            not after.startswith("loc_002228F0: ;\n") or
            after.count(HELPER + "()") != 1):
        raise ValueError("PC original retail branch signature/provenance changed")
    return before, after, item


def verify_original_x86(xbe: Path, retail_auditor: Path) -> dict:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    import importlib.util

    spec = importlib.util.spec_from_file_location("k1_pc_retail_x86", retail_auditor)
    if not spec or not spec.loader:
        raise ValueError("Cannot load existing retail XBE/section verifier")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    blob, sections = audit.get_retail_sections(xbe)
    data = audit.bytes_at(blob, sections, SITE, 16)
    insns = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(data, SITE, count=2))
    if (len(insns) != 2 or
            insns[0].address != SITE or
            insns[0].mnemonic != "cmp" or
            not re.fullmatch(
                r'(?:dword ptr )?\[ecx \+ 0x48\], (?:3|0x3)',
                insns[0].op_str) or
            insns[1].address != SITE + insns[0].size or
            insns[1].mnemonic not in ("jne", "jnz") or
            int(insns[1].op_str, 16) != JNE_DEST):
        raise ValueError(
            "Retail XBE does not prove original CMP[ECX+48],3/JNE 00222947: " +
            repr([(x.mnemonic, x.op_str) for x in insns])
        )
    return {
        "retail_sha256": XBE_SHA,
        "original_002228f0_x86_cmp_jne": True,
        "instruction_bytes_hex": "".join(
            ("%02X" % x) for x in data[:sum(i.size for i in insns)]),
        "jmp_destination": "0x00222947",
    }


def restore_exact_pc_patch(source: str, pc_root: Path, *, attest_x86: dict) -> tuple[str, dict]:
    before, after, item = read_templates(pc_root)
    if attest_x86.get("original_002228f0_x86_cmp_jne") is not True:
        raise ValueError("Original retail XBE x86 branch proof absent")
    source = source.replace("\r\n", "\n")
    if (source.count(after) != 1 or source.count(before) != 0 or
            source.count(HELPER + "()") != 1):
        raise ValueError(
            "Generated 002228C0 developer patch does not match pinned PC template "
            "(do NOT replace helper with a guessed constant). "
            "After-template count=%d, before count=%d, host-helper calls=%d, source_sha=%s"
            % (source.count(after), source.count(before),
               source.count(HELPER + "()"), digest(source))
        )
    restored = source.replace(after, before, 1)
    if (HELPER in restored or restored.count(before) != 1 or
            len(restored) - len(source) != len(before) - len(after)):
        raise ValueError("Exact PC-only developer branch reversal not complete")
    return restored, {
        "status": "PINNED_PC_DEVELOPER_ONLY_PATCH_RESTORED_TO_RETAIL",
        "pc_reference_git_commit": PC_SHA,
        "patched_original_source_sha256": digest(source),
        "restored_original_source_sha256": digest(restored),
        "pc_generated_patch_index": item["index"],
        "pc_generated_patch_name": PATCH_NAME,
        "pc_patch_before_sha256": digest(before),
        "pc_patch_after_sha256": digest(after),
        "x86_retail_cmp_jne_proof": attest_x86,
        "arbitrary_helper_stub_used": False,
        "guest_register_abi_modified": False,
    }


def selftest():
    # Copied fixture only; real PC source, retail .xbe and manifest are
    # independently checked at staging time. No XDK or retail bytes here.
    from tempfile import TemporaryDirectory
    before = ('loc_002228F0: ;\n'
              '    if (CMP_NE(MEM32(ecx + 0x48), 3)) '
              'goto loc_00222947; /* jne: not equal / not zero */\n')
    after = ('loc_002228F0: ;\n'
             '    /* Developer chapter reloads can request a range whose pinned buffer was\n'
             '     * completed earlier. Fulfil new reads from it with the retail reference\n'
             '     * accounting; READ_DONE requests below are skipped, so no double-use. */\n'
             '    if (MEM32(ecx + 0x48) != 3 &&\n'
             '        !(MEM32(ecx + 0x48) == 4 && recomp_dev_region_import_active())) '
             'goto loc_00222947;\n')
    doc = {
        "retail_xbe_sha256": XBE_SHA,
        "transformations": [{
            "index": 278,
            "name": PATCH_NAME,
            "guest_sites": ["002228F0", "00222947"],
            "host_helpers": [HELPER],
            "before_sha256": digest(before),
            "after_sha256": digest(after),
        }],
    }
    with TemporaryDirectory() as tmp:
        pc = Path(tmp)
        a = pc / PC_PATCH_SCRIPT
        b = pc / PC_INVENTORY
        a.parent.mkdir(parents=True)
        b.parent.mkdir(parents=True)
        a.write_text('GeneratedPatch(\n    "' + PATCH_NAME + '",\n' +
                     '"""' + before + '""",\n"""' + after + '""",\n)\n',
                     encoding="utf-8")
        b.write_text(json.dumps(doc), encoding="utf-8")
        result, meta = restore_exact_pc_patch(
            "void sub_002228C0(void) {\n" + after + "\n}\n",
            pc, attest_x86={"original_002228f0_x86_cmp_jne": True})
        assert before in result and HELPER not in result
        assert meta["arbitrary_helper_stub_used"] is False
        for bad in (
            after.replace(" == 4", " == 5"),
            after.replace("recomp_dev_region_import_active()", "false"),
            after + after,
        ):
            try:
                restore_exact_pc_patch("void f(){\n" + bad + "}", pc,
                                        attest_x86={"original_002228f0_x86_cmp_jne": True})
            except ValueError:
                pass
            else:
                raise AssertionError("Incorrect PC-only patch accepted")
        try:
            restore_exact_pc_patch(after, pc, attest_x86={})
        except ValueError:
            pass
        else:
            raise AssertionError("Unproven original retail bytes accepted")
    print("[K1-PC-RETAIL] SELFTEST PASS: exact hash-verified PC before/after, no invented helper, original x86 gate, no XDK")


if __name__ == "__main__":
    selftest()

#!/usr/bin/env python3
"""Phase 6BY: relocate ordinal-357 IdexChannelObject as pointer-valued guest DATA.

6BX hardware proved the immediate post-IRQL fault is not arbitrary low-KSEG:
  * the retail path reaches 0x0022AC8F with EDX still 0x00406298;
  * translated source then executes EDX = GUEST_READ32(0x002DBDBC);
  * the immediate fault boundary has EDX = 0x8000018D and READ32 0x8000018D;
  * Phase-4A exact retail audit identifies thunk slot 55 / VA 0x002DBDBC as
    ordinal 357 IdexChannelObject, a DATA export.

The maintained kernel model defines IdexChannelObject as a pointer-valued
export: PVOID xbox_IdexChannelObject = &g_idex_channel_data, where the tiny
identity object contains 0x49444558 ('IDEX').

Model that shape exactly in guest kernel-data:
  thunk 0x002DBDBC -> pointer slot 0x0087E0A0
  [0x0087E0A0]    -> object      0x0087E0A4
  [0x0087E0A4]    -> marker      0x49444558

The generic startup data-thunk map gains ordinal 357, so the exact retail raw
ordinal token is relocated before title execution. The low-KSEG ambiguity
fence is not changed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BX-LOWKSEG-ORIGIN-PROBE-20261024-A"
BUILD_TAG = "P6BY-IDEX357-DATA-20261024-A"
COOKIE_OLD = "phase6bx_env_build_cookie"
COOKIE_NEW = "phase6by_env_build_cookie"

IDEX_THUNK_VA = 0x002DBDBC
IDEX_RAW_ORDINAL_TOKEN = 0x80000165
IDEX_POINTER_SLOT_VA = 0x0087E0A0
IDEX_OBJECT_VA = 0x0087E0A4
IDEX_MARKER = 0x49444558


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BY] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BY] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def find_function(text: str, base, name: str) -> tuple[str, int, int]:
    masked = base.mask_noncode(text)
    signature = f"static void {name}(void)"
    defs = []
    cursor = 0
    while True:
        pos = masked.find(signature, cursor)
        if pos < 0:
            break
        probe = pos + len(signature)
        while probe < len(masked) and masked[probe].isspace():
            probe += 1
        if probe < len(masked) and masked[probe] == "{":
            defs.append((pos, probe))
        cursor = pos + len(signature)
    if len(defs) != 1:
        raise SystemExit(
            f"[Phase6BY] expected one translated {name} definition, found {len(defs)}"
        )
    start, brace = defs[0]
    end = base.closing_brace(masked, brace)
    return text[start:end], start, end


def patch_idex_data_export(text: str) -> str:
    # Add ordinal 357 to the same startup DATA map that already owns ordinal 356.
    text = replace_unique(
        text,
        "    case 356u: return 0x0087E098u; /* HalBootSMCVideoMode ULONG */\n"
        "    default:   return 0u;",
        "    case 356u: return 0x0087E098u; /* HalBootSMCVideoMode ULONG */\n"
        "    case 357u: return 0x0087E0A0u; /* IdexChannelObject PVOID export slot */\n"
        "    default:   return 0u;",
        "startup data ordinal-357 map",
    )

    # Initialize the exported pointer variable and the tiny maintained identity
    # object immediately after the already-proven ordinal-356 initialization.
    lines = text.splitlines(keepends=True)
    hits = [
        i for i, line in enumerate(lines)
        if "HalBootSMCVideoMode initialized ordinal=356 va=0087E098 value=00000000" in line
    ]
    if len(hits) != 1:
        raise SystemExit(
            f"[Phase6BY] expected one HalBootSMCVideoMode initialization trace, found {len(hits)}"
        )
    insert_at = hits[0] + 1
    init = (
        "\n"
        "    /* Ordinal 357 IdexChannelObject is a pointer-valued DATA export. */\n"
        "    GUEST_WRITE32(0x0087E0A0u, 0x0087E0A4u);\n"
        "    GUEST_WRITE32(0x0087E0A4u, 0x49444558u); /* 'IDEX' */\n"
        "    if (s_accessFault ||\n"
        "        GUEST_READ32(0x0087E0A0u) != 0x0087E0A4u ||\n"
        "        GUEST_READ32(0x0087E0A4u) != 0x49444558u ||\n"
        "        s_accessFault)\n"
        "    {\n"
        "        trace(\"FAIL: Phase 6BY IdexChannelObject guest-data initialization invariant\");\n"
        "        return 0;\n"
        "    }\n"
        "    trace(\"PASS: Phase 6BY IdexChannelObject initialized ordinal=357 pointer_slot=0087E0A0 object=0087E0A4 marker=49444558\");\n"
    )
    lines.insert(insert_at, init)
    text = "".join(lines)

    # Count the new DATA relocation.
    text = replace_unique(
        text,
        "    DWORD seen356 = 0u;\n"
        "    DWORD sentinel;",
        "    DWORD seen356 = 0u;\n"
        "    DWORD seen357 = 0u;\n"
        "    DWORD idexThunkBefore = 0u;\n"
        "    DWORD sentinel;",
        "ordinal-357 count state",
    )

    # Capture the exact raw retail token before generic relocation.
    loop_anchor = "    for (i = 0u; i < 111u; ++i)\n"
    if text.count(loop_anchor) != 1:
        raise SystemExit(
            f"[Phase6BY] expected one startup thunk loop, found {text.count(loop_anchor)}"
        )
    pre = (
        "    idexThunkBefore = GUEST_READ32(0x002DBDBCu);\n"
        "    if (s_accessFault || idexThunkBefore != 0x80000165u)\n"
        "    {\n"
        "        sprintf(line, \"FAIL: Phase 6BY unexpected raw IdexChannelObject thunk slot=002DBDBC value=%08X expected=80000165\",\n"
        "            (unsigned int)idexThunkBefore);\n"
        "        trace(line);\n"
        "        return 0;\n"
        "    }\n"
        "    trace(\"PASS: Phase 6BY raw IdexChannelObject thunk slot=002DBDBC value=80000165 ordinal=357\");\n"
        "\n"
    )
    text = text.replace(loop_anchor, pre + loop_anchor, 1)

    text = replace_unique(
        text,
        "        if (ordinal == 356u) ++seen356;\n"
        "        ++relocated;",
        "        if (ordinal == 356u) ++seen356;\n"
        "        if (ordinal == 357u) ++seen357;\n"
        "        ++relocated;",
        "ordinal-357 count increment",
    )

    text = replace_unique(
        text,
        "        seen326 != 1u || seen356 != 1u ||\n"
        "        relocated != (7u + seen41 + seen42))",
        "        seen326 != 1u || seen356 != 1u || seen357 != 1u ||\n"
        "        relocated != (8u + seen41 + seen42))",
        "startup data count invariant",
    )

    # Keep the existing failure-format ABI untouched; seen357 is enforced by
    # the condition above and the exact slot readback below. Add readback proof
    # before the thunk terminator check.
    sentinel_anchor = "    sentinel = GUEST_READ32(0x002DBCE0u + 111u * 4u);"
    if text.count(sentinel_anchor) != 1:
        raise SystemExit(
            f"[Phase6BY] expected one thunk sentinel read, found {text.count(sentinel_anchor)}"
        )
    readback = (
        "    if (GUEST_READ32(0x002DBDBCu) != 0x0087E0A0u ||\n"
        "        GUEST_READ32(0x0087E0A0u) != 0x0087E0A4u ||\n"
        "        GUEST_READ32(0x0087E0A4u) != 0x49444558u ||\n"
        "        s_accessFault)\n"
        "    {\n"
        "        trace(\"FAIL: Phase 6BY IdexChannelObject thunk/pointer/object readback invariant\");\n"
        "        return 0;\n"
        "    }\n"
        "    trace(\"PASS: Phase 6BY IdexChannelObject thunk slot 002DBDBC -> 0087E0A0 -> 0087E0A4\");\n"
        "\n"
    )
    text = text.replace(sentinel_anchor, readback + sentinel_anchor, 1)

    # Add the new object storage to the existing kernel-data readback invariant.
    invariant_anchor = "        GUEST_READ32(0x0087E098u) != 0u ||"
    if text.count(invariant_anchor) != 1:
        raise SystemExit(
            f"[Phase6BY] expected one HalBoot readback invariant, found {text.count(invariant_anchor)}"
        )
    text = text.replace(
        invariant_anchor,
        invariant_anchor
        + "\n        GUEST_READ32(0x0087E0A0u) != 0x0087E0A4u ||"
        + "\n        GUEST_READ32(0x0087E0A4u) != 0x49444558u ||",
        1,
    )

    # Update the success text without adding a new printf placeholder.
    success_lines = [
        line for line in text.splitlines()
        if "PASS: startup data imports " in line
        and "/356 relocated" in line
    ]
    if len(success_lines) != 1:
        raise SystemExit(
            f"[Phase6BY] expected one startup DATA success format, found {len(success_lines)}"
        )
    old = success_lines[0]
    new = old.replace("/356 relocated", "/356/357 relocated", 1)
    marker = "HalBootSMCVideoMode=0"
    if marker in new:
        new = new.replace(marker, marker + " IdexChannelObject=0087E0A4", 1)
    text = replace_unique(text, old, new, "startup DATA success trace")

    return text


def patch_live_idex_trace(text: str, base) -> str:
    body, start, end = find_function(text, base, "sub_0022AC56")

    load_slot = "    edx = GUEST_READ32(0x2DBDBC);\n"
    if body.count(load_slot) != 1:
        raise SystemExit(
            f"[Phase6BY] expected one Idex thunk load in sub_0022AC56, found {body.count(load_slot)}"
        )
    body = body.replace(
        load_slot,
        load_slot
        + "    if (!s_accessFault)\n"
        + "    {\n"
        + "        char p6byIdexLine[256];\n"
        + "        sprintf(p6byIdexLine, \"P6BY IDEX LIVE THUNK: slot=002DBDBC value=%08X expected_slot=0087E0A0\", (unsigned int)edx);\n"
        + "        trace(p6byIdexLine);\n"
        + "    }\n",
        1,
    )

    deref = "    ecx = GUEST_READ32(edx);\n"
    if body.count(deref) < 1:
        raise SystemExit("[Phase6BY] Idex exported-pointer dereference missing")
    body = body.replace(
        deref,
        deref
        + "    if (!s_accessFault)\n"
        + "    {\n"
        + "        char p6byIdexObjectLine[256];\n"
        + "        sprintf(p6byIdexObjectLine, \"P6BY IDEX LIVE OBJECT: pointer_slot=%08X object=%08X expected_object=0087E0A4\", (unsigned int)edx, (unsigned int)ecx);\n"
        + "        trace(p6byIdexObjectLine);\n"
        + "    }\n",
        1,
    )

    return text[:start] + body + text[end:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6by_base")
    p6bl = load(args.phase6bl_emitter, "phase6by_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6bx-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6BY] cached Phase 6BX input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    env_text_before = env_text
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BX" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BY] cached Phase 6BX identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6BY] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "case 356u: return 0x0087E098u; /* HalBootSMCVideoMode ULONG */",
        "DWORD seen356 = 0u;",
        "if (ordinal == 356u) ++seen356;",
        "relocated != (7u + seen41 + seen42)",
        "GUEST_READ32(0x0087E098u) != 0u",
        "P6BX LOWKSEG ORIGIN: va=%08X",
        "PASS: Phase 6BX KeRaiseIrqlToDpcLevel guest continuation",
        "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BY] inherited 6BX marker missing: {marker}")

    main_text = patch_idex_data_export(main_text)
    main_text = patch_live_idex_trace(main_text, base)

    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6BY relocate ordinal-357 IdexChannelObject as pointer-valued guest DATA at 0087E0A0->0087E0A4; preserve 6BX low-KSEG fence, guest IRQL, FILE_OBJECT sentinel, file/delay/GPU semantics, allocator geometry and 8M budget",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6BX", "PHASE 6BY")
        .replace("Phase 6BX", "Phase 6BY")
        .replace('"P6BX ', '"P6BY ')
    )
    env_text = (
        env_text.replace("PHASE 6BX", "PHASE 6BY")
        .replace("Phase 6BX", "Phase 6BY")
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "case 357u: return 0x0087E0A0u; /* IdexChannelObject PVOID export slot */",
        "GUEST_WRITE32(0x0087E0A0u, 0x0087E0A4u);",
        "GUEST_WRITE32(0x0087E0A4u, 0x49444558u);",
        "DWORD seen357 = 0u;",
        "idexThunkBefore != 0x80000165u",
        "if (ordinal == 357u) ++seen357;",
        "seen357 != 1u",
        "relocated != (8u + seen41 + seen42)",
        "PASS: Phase 6BY IdexChannelObject thunk slot 002DBDBC -> 0087E0A0 -> 0087E0A4",
        "P6BY IDEX LIVE THUNK:",
        "P6BY IDEX LIVE OBJECT:",
        "P6BY LOWKSEG ORIGIN: va=%08X",
        "PHASE4C_BOUNDARY_GUEST_FAULT",
        "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6BY] generated source lost marker: {marker}")

    expected_env = (
        env_text_before.replace(COOKIE_OLD, COOKIE_NEW)
        .replace("PHASE 6BX", "PHASE 6BY")
        .replace("Phase 6BX", "Phase 6BY")
    )
    if env_text != expected_env:
        raise SystemExit(
            "[Phase6BY] phase5_env.cpp changed beyond expected tag/cookie renames"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6BY",
            "build_tag": BUILD_TAG,
            "pack_members": pack_count,
            "members": members,
        }
    )
    manifest["phase6by_idex357_data"] = {
        "source_phase": "6BX",
        "phase6bx_hardware": {
            "probe_hits": 4,
            "retail_path": [
                "0x0022AC56",
                "0x0022AC78",
                "0x0022AC89",
                "0x0022AC8F",
            ],
            "last_probe_edx_before_slot_load": "0x00406298",
            "fault_access": "READ32",
            "fault_address": "0x8000018D",
            "boundary_edx_after_slot_load": "0x8000018D",
            "fault": 1,
            "xapi_return": 0,
        },
        "phase4a_identity": {
            "thunk_slot": 55,
            "thunk_va": "0x002DBDBC",
            "ordinal": 357,
            "name": "IdexChannelObject",
            "kind": "data",
        },
        "continuation": {
            "raw_ordinal_token_expected": "0x80000165",
            "pointer_slot_va": "0x0087E0A0",
            "object_va": "0x0087E0A4",
            "object_marker": "0x49444558",
            "pointer_valued_data_export": True,
            "low_kseg_fence_changed": False,
            "phase5_env_semantics_changed": False,
        },
        "translated_membership_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6by-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BY] 6BX hardware: four origin probes PASS; fault EDX=8000018D at 0022AC8F")
    print("[Phase6BY] Phase-4A exact identity: slot55 VA=002DBDBC ordinal=357 IdexChannelObject DATA")
    print("[Phase6BY] maintained DATA shape: thunk -> guest PVOID slot -> tiny IDEX identity object")
    print("[Phase6BY] guest layout: 002DBDBC -> 0087E0A0 -> 0087E0A4 [49444558]")
    print("[Phase6BY] low-KSEG ambiguity fence unchanged")
    print("[Phase6BY] translated membership unchanged")
    print("[Phase6BY] all 6BX file/sentinel/IRQL/delay/GPU/allocator/8M-budget invariants inherited")
    print("[Phase6BY] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

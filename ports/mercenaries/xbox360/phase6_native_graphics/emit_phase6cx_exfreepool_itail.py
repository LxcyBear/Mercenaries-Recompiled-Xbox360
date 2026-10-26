#!/usr/bin/env python3
r"""Phase 6CX: hardware-proven ExFreePool kernel ITAIL continuation.

6CW hardware crossed the maintained DSOUND dsstdfx.bin decryptor and then
stopped cleanly at:
  ITAIL caller=0x0023A3CE target=0x80000011
  esp=0x008BF968 saved_esp=0x008BF968
  ticks=27,021,517 trace=1,071,667 fault=0

Ordinal 17 is ExFreePool. Phase 6CF already installed the maintained guest-title
heap implementation for ordinary ICALL_SAFE dispatch, but the live DSOUND path
reaches the same kernel export through RECOMP_ITAIL.

Xbox translated tail-call ABI is already proven by ordinal 24:
  [esp+0] synthetic/dummy return slot
  [esp+4] first stdcall argument

Therefore ExFreePool's tail frame consumes 8 bytes total. 6CX reuses the
existing Phase6CF ExFreePool implementation with resumeEsp=esp+8, rather than
duplicating allocator semantics or touching native host memory.

No translated membership, graphics policy, shadow-RAM alias, XACT async I/O,
APU MMIO policy, D3D/XGRPH state, watchdog budget, or hard fence is widened.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

BASE_TAG = "P6CW-DSOUND-SWEEP-002A6713-20261026-A"
BUILD_TAG = "P6CX-EXFREEPOOL-ITAIL-80000011-20261026-A"
COOKIE_OLD = "phase6cw_env_build_cookie"
COOKIE_NEW = "phase6cx_env_build_cookie"
EMITTER_REVISION = "6CX-R1"

TARGET = 0x80000011
ORDINAL = 17
CALLER = 0x0023A3CE


def macro_block(source: str, macro_name: str) -> tuple[int, int, str]:
    pattern = re.compile(rf"(?m)^#define[ \t]+{re.escape(macro_name)}\(")
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise SystemExit(
            f"[Phase6CX] expected one {macro_name} definition, found {len(matches)}"
        )

    start = matches[0].start()
    line_start = start
    line_end = source.find("\n", line_start)
    if line_end < 0:
        line_end = len(source)

    while True:
        line = source[line_start:line_end]
        if not line.rstrip().endswith("\\"):
            end = line_end + (1 if line_end < len(source) else 0)
            break
        line_start = line_end + 1
        line_end = source.find("\n", line_start)
        if line_end < 0:
            line_end = len(source)

    return start, end, source[start:end]


def install_state(text: str) -> str:
    anchor = "static uint32_t s_phase6cfExPoolLastQuerySize = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CX] expected one inherited ExPool state anchor, found {text.count(anchor)}"
        )

    state = """static uint32_t s_phase6cxExFreePoolItailCalls = 0u;
static uint32_t s_phase6cxExFreePoolItailLastAddress = 0u;
static uint32_t s_phase6cxExFreePoolItailLastSize = 0u;
static uint32_t s_phase6cxExFreePoolItailLastFreed = 0u;
static uint32_t s_phase6cxExFreePoolItailLastEspBefore = 0u;
static uint32_t s_phase6cxExFreePoolItailLastEspAfter = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def install_decl(text: str) -> str:
    anchor = "typedef void (*recomp_func_t)(void);\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CX] expected one recomp_func_t typedef, found {text.count(anchor)}"
        )

    decl = "static void phase6cx_ex_free_pool_itail(void);\n"
    if decl in text:
        raise SystemExit("[Phase6CX] ExFreePool ITAIL declaration already present")
    return text.replace(anchor, anchor + decl, 1)


def install_helper(text: str) -> str:
    lookup = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    pos = text.find(lookup)
    if pos < 0:
        raise SystemExit("[Phase6CX] pack lookup definition marker changed")

    for marker in (
        "static void phase6cf_ex_free_pool(uint32_t savedEsp)",
        "static uint32_t phase6cf_pool_block_size(uint32_t address)",
        "static uint32_t phase4c_heap_free(uint32_t address)",
    ):
        marker_pos = text.find(marker)
        if marker_pos < 0 or marker_pos > pos:
            raise SystemExit(
                f"[Phase6CX] inherited ExFreePool support missing or ordered after lookup: {marker}"
            )

    helper = r'''
static void phase6cx_ex_free_pool_itail(void)
{
    const uint32_t frameEsp = g_esp;
    const uint32_t returnSlot = GUEST_READ32(frameEsp + 0u);
    const uint32_t address = GUEST_READ32(frameEsp + 4u);
    const uint32_t knownSize = phase6cf_pool_block_size(address);
    const uint32_t freeCallsBefore = s_phase6cfExPoolFreeCalls;
    char line[448];

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000011u,
            frameEsp);
        return;
    }

    /*
     * Match the already-proven ordinal-24 kernel ITAIL frame. The translated
     * direct CALL contributes a synthetic zero return slot and the retail tail
     * JMP reuses that frame. ExFreePool has one stdcall argument, therefore the
     * complete kernel return consumes 4 + 4 bytes.
     */
    if (returnSlot != 0u)
    {
        sprintf(
            line,
            "ExFreePool ITAIL FRAME MISMATCH: ret=%08X address=%08X esp=%08X expected_ret=00000000",
            (unsigned int)returnSlot,
            (unsigned int)address,
            (unsigned int)frameEsp);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000011u,
            frameEsp);
        return;
    }

    s_phase6cxExFreePoolItailLastEspBefore = frameEsp;
    phase6cf_ex_free_pool(frameEsp + 8u);

    if (g_esp != frameEsp + 8u)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000011u,
            frameEsp);
        return;
    }

    ++s_phase6cxExFreePoolItailCalls;
    s_phase6cxExFreePoolItailLastAddress = address;
    s_phase6cxExFreePoolItailLastSize = knownSize;
    s_phase6cxExFreePoolItailLastFreed =
        s_phase6cfExPoolFreeCalls == freeCallsBefore + 1u ? 1u : 0u;
    s_phase6cxExFreePoolItailLastEspAfter = g_esp;

    sprintf(
        line,
        "PASS: Phase 6CX ExFreePool ITAIL caller=%08X address=%08X size=%u freed=%u calls=%u esp=%08X->%08X",
        (unsigned int)phase4c_current_caller(),
        (unsigned int)address,
        (unsigned int)knownSize,
        (unsigned int)s_phase6cxExFreePoolItailLastFreed,
        (unsigned int)s_phase6cxExFreePoolItailCalls,
        (unsigned int)frameEsp,
        (unsigned int)g_esp);
    trace(line);
}

'''
    return text[:pos] + helper + text[pos:]


def patch_itail(text: str) -> str:
    start, end, block = macro_block(text, "RECOMP_ITAIL")

    if "0x80000011u" in block:
        raise SystemExit("[Phase6CX] ExFreePool is already armed in RECOMP_ITAIL")
    if "0x80000018u" not in block:
        raise SystemExit("[Phase6CX] inherited ordinal-24 ITAIL continuation missing")
    if "phase4c_ex_query_nonvolatile_setting" not in block:
        raise SystemExit("[Phase6CX] inherited ordinal-24 handler missing")
    if "phase6cq_dispatch_packed_itail" not in block:
        raise SystemExit("[Phase6CX] inherited packed ITAIL fallback missing")

    ordinal24 = "if (_phase4c_tail_target == 0x80000018u"
    pos = block.find(ordinal24)
    if pos < 0:
        raise SystemExit("[Phase6CX] ordinal-24 ITAIL branch shape changed")

    replacement = (
        "if (_phase4c_tail_target == 0x80000011u) { \\\n"
        "        phase6cx_ex_free_pool_itail(); \\\n"
        "    } else " + ordinal24
    )
    block = block[:pos] + replacement + block[pos + len(ordinal24):]

    if block.count("0x80000011u") != 1:
        raise SystemExit("[Phase6CX] ExFreePool ITAIL insertion count mismatch")

    return text[:start] + block + text[end:]


def insert_summary(text: str) -> str:
    marker = "P6CW SHADOW RAM:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CX] inherited shadow-RAM summary marker missing")

    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 10000:
        raise SystemExit("[Phase6CX] final-summary insertion point changed")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CX EXFREEPOOL ITAIL: calls=%u address=%08X size=%u freed=%u esp_before=%08X esp_after=%08X",\n'
        f'{indent}    (unsigned int)s_phase6cxExFreePoolItailCalls,\n'
        f'{indent}    (unsigned int)s_phase6cxExFreePoolItailLastAddress,\n'
        f'{indent}    (unsigned int)s_phase6cxExFreePoolItailLastSize,\n'
        f'{indent}    (unsigned int)s_phase6cxExFreePoolItailLastFreed,\n'
        f'{indent}    (unsigned int)s_phase6cxExFreePoolItailLastEspBefore,\n'
        f'{indent}    (unsigned int)s_phase6cxExFreePoolItailLastEspAfter);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel(text: str) -> str:
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6CW", "PHASE 6CX")
        .replace("Phase 6CW", "Phase 6CX")
        .replace('"P6CW ', '"P6CX ')
    )


def patch_source(text: str) -> str:
    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "static void phase6cf_ex_free_pool(uint32_t savedEsp)",
        "_phase4c_target == 0x80000011u",
        "case 0x002A6713u:",
        "PASS: Phase 6CW manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "P6CW APU CORE:",
        "P6CW AV/DISPLAY SUMMARY:",
    ):
        if marker not in text:
            raise SystemExit(f"[Phase6CX] inherited 6CW marker missing: {marker}")

    text = install_state(text)
    text = install_decl(text)
    text = install_helper(text)
    text = patch_itail(text)
    text = insert_summary(text)
    text = relabel(text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "phase6cx_ex_free_pool_itail();",
        "PASS: Phase 6CX ExFreePool ITAIL",
        "P6CX EXFREEPOOL ITAIL:",
        "PASS: Phase 6CX manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6CX APU CORE:",
        "P6CX AV/DISPLAY SUMMARY:",
    )
    for marker in required:
        if marker not in text:
            raise SystemExit(f"[Phase6CX] patched source lost marker: {marker}")

    _, _, itail = macro_block(text, "RECOMP_ITAIL")
    if itail.count("0x80000011u") != 1:
        raise SystemExit("[Phase6CX] live ITAIL macro does not contain exact ExFreePool branch")
    if "0x80000018u" not in itail or "phase6cq_dispatch_packed_itail" not in itail:
        raise SystemExit("[Phase6CX] inherited ITAIL continuations were weakened")

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6CX] stale 6CW cookie remains")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base_main = args.base_dir / "main.cpp"
    base_mono = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6cw-manifest.json"
    base_shards = args.base_dir / "translated_shards"
    for path in (base_main, base_mono, base_env, base_manifest, base_shards):
        if not path.exists():
            raise SystemExit(f"[Phase6CX] missing cached 6CW input: {path}")

    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6CW" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CX] cached 6CW identity mismatch")

    cw = manifest.get("phase6cw_dsound_sweep", {})
    if (
        cw.get("root") != "0x002A6713"
        or cw.get("manual_root_dispatch") is not True
        or cw.get("shadow_ram_alias_preserved") is not True
        or cw.get("execution_budget_inherited") != 64000000
        or cw.get("hard_fences_weakened") is not False
    ):
        raise SystemExit("[Phase6CX] inherited 6CW policy mismatch")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_shards = args.out_dir / "translated_shards"
    if out_shards.exists():
        shutil.rmtree(out_shards)
    shutil.copytree(base_shards, out_shards)

    main_text = patch_source(base_main.read_text(encoding="utf-8"))
    mono_text = patch_source(base_mono.read_text(encoding="utf-8"))
    env_text = relabel(base_env.read_text(encoding="utf-8"))

    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6CX",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6cx_exfreepool_itail"] = {
        "source_phase": "6CW",
        "phase6cw_hardware": {
            "boundary_kind": "ITAIL",
            "caller": "0x0023A3CE",
            "target": "0x80000011",
            "ordinal": 17,
            "name": "ExFreePool",
            "esp": "0x008BF968",
            "saved_esp": "0x008BF968",
            "ticks": 27021517,
            "trace": 1071667,
            "fault": 0,
            "dsound_manual_decrypt_entered": True,
            "dsound_logged_calls": 8,
            "dsound_logged_bytes": 7156,
            "shadow_reads": 3,
            "display_calls": 0,
            "framebuffer": "0x00000000",
        },
        "tail_frame": {
            "dummy_return_offset": 0,
            "argument_address_offset": 4,
            "stdcall_bytes": 4,
            "total_consumed_bytes": 8,
            "resume_esp_expression": "frameEsp + 8",
        },
        "handler": "phase6cf_ex_free_pool reused through phase6cx_ex_free_pool_itail",
        "translated_membership_changed": False,
        "shadow_ram_alias_changed": False,
        "async_read_semantics_changed": False,
        "graphics_bridge_semantics_changed": False,
        "apu_semantics_changed": False,
        "allocator_semantics_changed": False,
        "execution_budget_inherited": 64000000,
        "kernel_itail_ordinal24_preserved": True,
        "packed_itail_dispatch_preserved": True,
        "hard_fences_weakened": False,
    }

    (args.out_dir / "phase6cx-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6CX] emitter revision: {EMITTER_REVISION}")
    print("[Phase6CX] hardware boundary: ITAIL 0023A3CE -> 80000011 (ExFreePool)")
    print("[Phase6CX] tail ABI: dummy return + one stdcall arg = 8 bytes")
    print("[Phase6CX] handler: reuse maintained Phase6CF ExFreePool guest-heap semantics")
    print("[Phase6CX] DSOUND decrypt + shadow RAM + APU + graphics state preserved")
    print("[Phase6CX] 64M watchdog + packed ITAIL + ordinal-24 tail preserved")
    print("[Phase6CX] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

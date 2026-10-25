#!/usr/bin/env python3
"""Phase 6CF: Xbox executive pool family continuation.

Phase 6CE crossed the hardware-proven XACTENG frontier 0x0027DB5C and then,
28 translated ticks later, stopped cleanly at:
  ICALL_SAFE caller=0x0023A3CE target=0x8000000F
  esp=0x008BF908 saved_esp=0x008BF914 ticks=26711208 fault=0

Ordinal 15 is ExAllocatePoolWithTag(NumberOfBytes, Tag). The maintained
production bridge already proves the required semantics: allocate zero-filled,
16-byte-aligned memory from guest Xbox heap space, never from the native host
heap. 6CF ports that semantic family into the XDK harness and proactively arms
the adjacent canonical pool exports:
  14 ExAllocatePool
  15 ExAllocatePoolWithTag
  17 ExFreePool
  23 ExQueryPoolBlockSize

No translated membership, XACTENG sweep membership, graphics policy, allocator
layout, watchdog budget, or hard-fence policy is changed.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

BASE_TAG = "P6CE-XACTENG-SIBLING-SWEEP-0027DB5C-20261025-A"
BUILD_TAG = "P6CF-EXPOOL-FAMILY-20261025-A"
COOKIE_OLD = "phase6ce_env_build_cookie"
COOKIE_NEW = "phase6cf_env_build_cookie"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CF] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def install_support(text: str) -> str:
    anchor = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CF] expected one pack lookup anchor, found {text.count(anchor)}"
        )

    support = r'''static uint32_t s_phase6cfExPoolAllocCalls = 0u;
static uint32_t s_phase6cfExPoolTaggedCalls = 0u;
static uint32_t s_phase6cfExPoolFreeCalls = 0u;
static uint32_t s_phase6cfExPoolQueryCalls = 0u;
static uint32_t s_phase6cfExPoolLastSize = 0u;
static uint32_t s_phase6cfExPoolLastTag = 0u;
static uint32_t s_phase6cfExPoolLastAddress = 0u;
static uint32_t s_phase6cfExPoolLastQuerySize = 0u;

static void phase6cf_validate_pool_frame(
    uint32_t target,
    uint32_t savedEsp,
    uint32_t expectedDelta,
    const char* name)
{
    const uint32_t callEsp = g_esp;
    char line[320];

    if (savedEsp != callEsp + expectedDelta)
    {
        sprintf(
            line,
            "%s FRAME MISMATCH: target=%08X esp=%08X saved_esp=%08X delta=%u expected=%u",
            name,
            (unsigned int)target,
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp),
            (unsigned int)expectedDelta);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            target,
            savedEsp);
    }
}

static uint32_t phase6cf_pool_block_size(uint32_t address)
{
    DWORD index;

    if (address == 0u)
        return 0u;

    phase4c_heap_init();
    for (index = 0u; index < s_phase4cHeapCount; ++index)
    {
        Phase4CHeapBlock* block = &s_phase4cHeap[index];
        if (!block->inUse || block->address != address)
            continue;

        return block->requested != 0u
            ? block->requested
            : block->capacity;
    }

    return 0u;
}

static void phase6cf_ex_allocate_pool(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t size;
    uint32_t result;
    char line[384];

    phase6cf_validate_pool_frame(
        0x8000000Eu, savedEsp, 8u, "ExAllocatePool");

    returnSlot = GUEST_READ32(callEsp + 0u);
    size = GUEST_READ32(callEsp + 4u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x8000000Eu,
            savedEsp);
        return;
    }

    result = phase4c_heap_allocate(PHASE4C_HEAP_ZERO_MEMORY, size);
    ++s_phase6cfExPoolAllocCalls;
    s_phase6cfExPoolLastSize = size;
    s_phase6cfExPoolLastTag = 0u;
    s_phase6cfExPoolLastAddress = result;

    g_eax = result;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6CF ExAllocatePool ret=%08X size=%u result=%08X calls=%u new_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)size,
        (unsigned int)result,
        (unsigned int)s_phase6cfExPoolAllocCalls,
        (unsigned int)g_esp);
    trace(line);
}

static void phase6cf_ex_allocate_pool_with_tag(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t size;
    uint32_t tag;
    uint32_t result;
    char line[448];

    phase6cf_validate_pool_frame(
        0x8000000Fu, savedEsp, 12u, "ExAllocatePoolWithTag");

    returnSlot = GUEST_READ32(callEsp + 0u);
    size = GUEST_READ32(callEsp + 4u);
    tag = GUEST_READ32(callEsp + 8u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x8000000Fu,
            savedEsp);
        return;
    }

    result = phase4c_heap_allocate(PHASE4C_HEAP_ZERO_MEMORY, size);
    ++s_phase6cfExPoolTaggedCalls;
    s_phase6cfExPoolLastSize = size;
    s_phase6cfExPoolLastTag = tag;
    s_phase6cfExPoolLastAddress = result;

    g_eax = result;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6CF ExAllocatePoolWithTag ret=%08X size=%u tag=%08X result=%08X calls=%u new_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)size,
        (unsigned int)tag,
        (unsigned int)result,
        (unsigned int)s_phase6cfExPoolTaggedCalls,
        (unsigned int)g_esp);
    trace(line);
}

static void phase6cf_ex_free_pool(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t address;
    uint32_t knownSize;
    uint32_t freed;
    char line[384];

    phase6cf_validate_pool_frame(
        0x80000011u, savedEsp, 8u, "ExFreePool");

    returnSlot = GUEST_READ32(callEsp + 0u);
    address = GUEST_READ32(callEsp + 4u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000011u,
            savedEsp);
        return;
    }

    knownSize = phase6cf_pool_block_size(address);
    freed = phase4c_heap_free(address);
    ++s_phase6cfExPoolFreeCalls;
    s_phase6cfExPoolLastAddress = address;
    s_phase6cfExPoolLastQuerySize = knownSize;

    /*
     * ExFreePool is VOID. The maintained bridge writes zero to EAX, so mirror
     * that observable bridge behavior while consuming the stdcall frame.
     */
    g_eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6CF ExFreePool ret=%08X address=%08X size=%u freed=%u calls=%u new_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)address,
        (unsigned int)knownSize,
        (unsigned int)freed,
        (unsigned int)s_phase6cfExPoolFreeCalls,
        (unsigned int)g_esp);
    trace(line);
}

static void phase6cf_ex_query_pool_block_size(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t address;
    uint32_t size;
    char line[384];

    phase6cf_validate_pool_frame(
        0x80000017u, savedEsp, 8u, "ExQueryPoolBlockSize");

    returnSlot = GUEST_READ32(callEsp + 0u);
    address = GUEST_READ32(callEsp + 4u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000017u,
            savedEsp);
        return;
    }

    size = phase6cf_pool_block_size(address);
    ++s_phase6cfExPoolQueryCalls;
    s_phase6cfExPoolLastAddress = address;
    s_phase6cfExPoolLastQuerySize = size;

    g_eax = size;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6CF ExQueryPoolBlockSize ret=%08X address=%08X size=%u calls=%u new_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)address,
        (unsigned int)size,
        (unsigned int)s_phase6cfExPoolQueryCalls,
        (unsigned int)g_esp);
    trace(line);
}

'''
    text = text.replace(anchor, support + anchor, 1)

    helper_pos = text.find("static void phase6cf_ex_allocate_pool_with_tag")
    heap_allocate_pos = text.find("static uint32_t phase4c_heap_allocate(")
    heap_free_pos = text.find("static uint32_t phase4c_heap_free(")
    heap_state_pos = text.find("static Phase4CHeapBlock s_phase4cHeap[")
    lookup_pos = text.find(anchor)
    if min(
        helper_pos,
        heap_allocate_pos,
        heap_free_pos,
        heap_state_pos,
        lookup_pos,
    ) < 0:
        raise SystemExit("[Phase6CF] compile-order proof marker missing")
    if not (
        heap_state_pos < heap_allocate_pos < helper_pos < lookup_pos
        and heap_free_pos < helper_pos
    ):
        raise SystemExit(
            "[Phase6CF] compile-order proof failed for guest pool helpers"
        )

    return text


def patch_icall_dispatch(text: str) -> str:
    macro_start = text.find("#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do {")
    if macro_start < 0:
        raise SystemExit("[Phase6CF] RECOMP_ICALL_SAFE macro start missing")
    next_macro = text.find("#define RECOMP_ITAIL", macro_start)
    if next_macro < 0:
        raise SystemExit("[Phase6CF] RECOMP_ITAIL anchor missing")

    macro = text[macro_start:next_macro]
    for target in ("0x8000000Eu", "0x8000000Fu", "0x80000011u", "0x80000017u"):
        if target in macro:
            raise SystemExit(f"[Phase6CF] pool target already dispatched: {target}")

    bs = chr(92)
    inherited = "if (_phase4c_target == 0x800000FAu) { " + bs
    pos = macro.find(inherited)
    if pos < 0:
        raise SystemExit("[Phase6CF] inherited ordinal-250 dispatch head missing")

    replacement = (
        "if (_phase4c_target == 0x8000000Eu) { " + bs + "\n"
        "        phase6cf_ex_allocate_pool((uint32_t)(saved_esp)); " + bs + "\n"
        "    } else if (_phase4c_target == 0x8000000Fu) { " + bs + "\n"
        "        phase6cf_ex_allocate_pool_with_tag((uint32_t)(saved_esp)); " + bs + "\n"
        "    } else if (_phase4c_target == 0x80000011u) { " + bs + "\n"
        "        phase6cf_ex_free_pool((uint32_t)(saved_esp)); " + bs + "\n"
        "    } else if (_phase4c_target == 0x80000017u) { " + bs + "\n"
        "        phase6cf_ex_query_pool_block_size((uint32_t)(saved_esp)); " + bs + "\n"
        "    } else if (_phase4c_target == 0x800000FAu) { " + bs
    )
    macro = macro[:pos] + replacement + macro[pos + len(inherited):]

    for target in ("0x8000000Eu", "0x8000000Fu", "0x80000011u", "0x80000017u"):
        if macro.count(target) != 1:
            raise SystemExit(f"[Phase6CF] dispatch insertion failed: {target}")

    return text[:macro_start] + macro + text[next_macro:]


def insert_arm_trace(text: str) -> str:
    marker = (
        '    trace("PASS: Phase 6CE ordinal 250 ObfDereferenceObject '
        'synthetic FILE_OBJECT release armed");\n'
    )
    if text.count(marker) != 1:
        raise SystemExit("[Phase6CF] inherited ordinal-250 arm trace missing")

    block = (
        marker
        + '    trace("PASS: Phase 6CF executive pool family armed: ordinals 14/15/17/23 guest-heap semantics");\n'
    )
    return text.replace(marker, block, 1)


def insert_summary(text: str) -> str:
    marker = "P6CE XACTENG ROOT:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CF] inherited XACTENG root summary missing")

    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6CF] could not locate XACTENG summary block")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CF EXPOOL: alloc=%u tagged=%u free=%u query=%u last_size=%u last_tag=%08X last_address=%08X last_query=%u",\n'
        f'{indent}    (unsigned int)s_phase6cfExPoolAllocCalls,\n'
        f'{indent}    (unsigned int)s_phase6cfExPoolTaggedCalls,\n'
        f'{indent}    (unsigned int)s_phase6cfExPoolFreeCalls,\n'
        f'{indent}    (unsigned int)s_phase6cfExPoolQueryCalls,\n'
        f'{indent}    (unsigned int)s_phase6cfExPoolLastSize,\n'
        f'{indent}    (unsigned int)s_phase6cfExPoolLastTag,\n'
        f'{indent}    (unsigned int)s_phase6cfExPoolLastAddress,\n'
        f'{indent}    (unsigned int)s_phase6cfExPoolLastQuerySize);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_main(text: str) -> str:
    # main.cpp is the sharded build wrapper, so the root-entry trace literal
    # itself lives inside translated_shards and is intentionally absent here.
    # Validate the root's packed lookup plus its inherited state/summary
    # instead; main_monolithic.cpp still receives the same structural proof.
    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "case 0x0027DB5Cu:",
        "static uint32_t s_phase6ceXactRootEntries = 0u;",
        "P6CE XACTENG ROOT:",
        "P6CE MANUAL PBL TRIG:",
    ):
        if marker not in text:
            raise SystemExit(f"[Phase6CF] inherited 6CE marker missing: {marker}")

    text = install_support(text)
    text = patch_icall_dispatch(text)
    text = insert_arm_trace(text)
    text = insert_summary(text)

    old_policy = (
        "Policy: Phase 6CE starts from hardware-proven 6CD 26.7M-tick DIRECT_FRONTIER "
        "0027DB5C and sweeps remaining exact generated XACTENG siblings with a 1024-member "
        "candidate cap under support-clean pruning; preserve the 32M watchdog, quiet "
        "dispatch logging, manual PblMath, graphics/file/IDEX/IRQL/allocator semantics "
        "and every genuine hard fence"
    )
    new_policy = (
        "Policy: Phase 6CF continues the hardware-proven 6CE XACTENG path through "
        "canonical Xbox executive pool ordinals 14/15/17/23 using the maintained "
        "zero-filled 16-byte-aligned guest title heap; preserve XACTENG membership, "
        "32M watchdog, quiet logging, manual PblMath, graphics/file/IDEX/IRQL semantics "
        "and every genuine hard fence"
    )
    text = replace_once(text, old_policy, new_policy, "runtime policy")
    text = replace_once(text, BASE_TAG, BUILD_TAG, "build tag")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)

    text = (
        text.replace("PHASE 6CE", "PHASE 6CF")
        .replace("Phase 6CE", "Phase 6CF")
        .replace('"P6CE ', '"P6CF ')
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "_phase4c_target == 0x8000000Eu",
        "_phase4c_target == 0x8000000Fu",
        "_phase4c_target == 0x80000011u",
        "_phase4c_target == 0x80000017u",
        "PASS: Phase 6CF ExAllocatePoolWithTag",
        "P6CF EXPOOL:",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "case 0x0027DB5Cu:",
    )
    for marker in required:
        if marker not in text:
            raise SystemExit(f"[Phase6CF] patched source lost marker: {marker}")

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6CF] stale 6CE env cookie remains")
    return text


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CE", "PHASE 6CF")
        .replace("Phase 6CE", "Phase 6CF")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CF] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base_main = args.base_dir / "main.cpp"
    base_mono = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6ce-manifest.json"
    base_shards = args.base_dir / "translated_shards"

    for path in (base_main, base_mono, base_env, base_manifest, base_shards):
        if not path.exists():
            raise SystemExit(f"[Phase6CF] missing cached 6CE input: {path}")

    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6CE" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CF] cached Phase 6CE identity mismatch")

    ce = manifest.get("phase6ce_xacteng_sibling_sweep", {})
    if (
        ce.get("root") != "0x0027DB5C"
        or ce.get("execution_budget_inherited") != 32000000
        or ce.get("hard_fences_changed") is not False
    ):
        raise SystemExit("[Phase6CF] inherited 6CE XACTENG policy mismatch")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_shards = args.out_dir / "translated_shards"
    if out_shards.exists():
        shutil.rmtree(out_shards)
    shutil.copytree(base_shards, out_shards)

    main_text = patch_main(base_main.read_text(encoding="utf-8"))
    mono_text = patch_main(base_mono.read_text(encoding="utf-8"))
    env_text = patch_env(base_env.read_text(encoding="utf-8"))

    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "6CF"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6cf_executive_pool_family"] = {
        "source_phase": "6CE",
        "phase6ce_hardware": {
            "boundary_kind": "ICALL_SAFE",
            "caller": "0x0023A3CE",
            "target": "0x8000000F",
            "ordinal": 15,
            "name": "ExAllocatePoolWithTag",
            "esp": "0x008BF908",
            "saved_esp": "0x008BF914",
            "frame_delta": 12,
            "ticks": 26711208,
            "trace": 1017505,
            "fault": 0,
            "eax": "0x00000000",
            "ecx": "0x00000000",
            "edx": "0x00000000",
            "ebx": "0x01B5C320",
            "esi": "0x00000030",
            "edi": "0x01B5C330",
            "xapi_return": 0,
        },
        "armed_ordinals": {
            "14": "ExAllocatePool",
            "15": "ExAllocatePoolWithTag",
            "17": "ExFreePool",
            "23": "ExQueryPoolBlockSize",
        },
        "allocation_alignment": 16,
        "allocation_zero_fill": True,
        "allocation_backing": "phase4c guest title heap",
        "source_semantics": "src/kernel/kernel_bridge.c executive pool family",
        "translated_membership_changed": False,
        "xacteng_membership_changed": False,
        "execution_budget_inherited": 32000000,
        "dispatch_log_stride_inherited": 4096,
        "manual_pbl_semantics_changed": False,
        "graphics_policy_changed": False,
        "hard_fences_changed": False,
        "shards_reused_byte_for_byte": True,
        "shard_count": len(list(out_shards.glob("*.inl"))),
    }

    (args.out_dir / "phase6cf-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6CF] 6CE hardware: XACTENG root PASS, then ordinal 15 at tick 26,711,208")
    print("[Phase6CF] ordinal 15 = ExAllocatePoolWithTag; live frame delta=12, fault=0")
    print("[Phase6CF] armed executive pool family: 14 / 15 / 17 / 23")
    print("[Phase6CF] allocator: existing zero-filled 16-byte-aligned guest title heap")
    print("[Phase6CF] translated/XACTENG membership changes: 0")
    print("[Phase6CF] execution budget: inherited 32,000,000 ticks")
    print("[Phase6CF] hard fences: unchanged")
    print("[Phase6CF] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

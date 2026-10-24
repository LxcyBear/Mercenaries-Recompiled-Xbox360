#!/usr/bin/env python3
"""Phase 6AT-A: continue the dual-frontier allocator during retail D3D init.

6AR hardware proved the selective retail initializer is correct enough to:
  * eliminate the old READ32 0x80000004 orange corruption;
  * change device+0x1A10 from 0 -> 2.

6AS then proved the next E_OUTOFMEMORY is allocator-policy, not real exhaustion:
  * the first 0x01680000 graphics claim trims only the free title-heap tail and
    moves s_phase4cVmPageNext from 0x03F00000 -> 0x02880000;
  * phase5bb_alloc_guest_pages still rejects any later request when pageNext is
    below the compile-time PHASE4C_TITLE_HEAP_END (0x028C0000);
  * therefore the later 0x00258000 request is guaranteed to return NULL even
    though the live heap high-water mark is far below the current frontier.

This phase keeps the existing exact first graphics-pool repair, then enables a
bounded dual-frontier fallback only while sub_0028F9E0 is active. Normal page
allocation is always attempted first. The fallback is allowed only for the
proven ordinal-166 full-range contiguous-memory shape and only when the region
to be claimed is exactly the current free heap tail, contains no live heap
allocation, and all pages are unmanaged.

KSEG/NV2A/MMIO/VRAM and guest-fault fences remain unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6AR-POST-CREATE-STATE-INIT-20261024-A"
BUILD_TAG = "P6AT-D3D-DUAL-FRONTIER-CONTINUE-20261024-A"
COOKIE_OLD = "phase6ar_env_build_cookie"
COOKIE_NEW = "phase6at_env_build_cookie"
SHARD_TARGET_CHARS = 750000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AT] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AT] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AT] runtime Policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AT] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return text[:line_start] + indent + 'trace("' + policy + '");' + text[line_end:]


def install_state(main_text: str) -> str:
    marker = "static DWORD s_phase6arInitCalls = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AT] inherited 6AR state marker missing")
    state = r'''static DWORD s_phase6atPostCreateInitActive = 0u;
static DWORD s_phase6atTailClaimCalls = 0u;
static DWORD s_phase6atTailClaimSuccesses = 0u;
static DWORD s_phase6atTailClaimLastRequested = 0u;
static DWORD s_phase6atTailClaimLastRounded = 0u;
static DWORD s_phase6atTailClaimLastOldNext = 0u;
static DWORD s_phase6atTailClaimLastBase = 0u;
static DWORD s_phase6atTailClaimLastHeapHigh = 0u;
static DWORD s_phase6atTailClaimLastAlignment = 0u;

'''
    return main_text.replace(marker, state + marker, 1)


def install_tail_claim_helper(main_text: str) -> str:
    marker = "static void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AT] ordinal-166 handler marker missing")

    helper = r'''static uint32_t phase6at_claim_post_create_tail(
    uint32_t requested,
    uint32_t alignment,
    uint32_t protect,
    uint32_t* actualSize)
{
    uint32_t size = phase4c_page_round(requested);
    uint32_t oldPageNext = s_phase4cVmPageNext;
    uint32_t base;
    uint32_t firstPage;
    uint32_t lastPage;
    uint32_t page;
    uint32_t index;
    uint32_t heapHigh = PHASE4C_TITLE_HEAP_START;
    int tailIndex = -1;
    Phase4CHeapBlock* tail;
    char line[768];

    ++s_phase6atTailClaimCalls;
    s_phase6atTailClaimLastRequested = requested;
    s_phase6atTailClaimLastRounded = size;
    s_phase6atTailClaimLastOldNext = oldPageNext;
    s_phase6atTailClaimLastBase = 0u;
    s_phase6atTailClaimLastHeapHigh = 0u;
    s_phase6atTailClaimLastAlignment = alignment;

    if (actualSize)
        *actualSize = 0u;

    if (!s_phase6atPostCreateInitActive ||
        size == 0u ||
        s_phase4cVmReservationCount >= PHASE4C_VM_RESERVATION_CAP)
        return 0u;

    if (alignment < 0x1000u ||
        (alignment & (alignment - 1u)) != 0u)
        alignment = 0x1000u;

    if (oldPageNext <= size)
        return 0u;

    base = (oldPageNext - size) & ~(alignment - 1u);
    if (base < PHASE4C_TITLE_HEAP_START ||
        base >= oldPageNext ||
        base + size != oldPageNext ||
        !phase4c_vm_page_range(base, size, &firstPage, &lastPage))
        return 0u;

    phase4c_heap_init();

    /*
     * The page frontier and the title heap now meet. Reclaim only the current
     * free heap tail. Any live allocation crossing the proposed base, any
     * second overlapping free block, or any non-tail overlap is a hard stop.
     */
    for (index = 0u; index < s_phase4cHeapCount; ++index)
    {
        Phase4CHeapBlock* block = &s_phase4cHeap[index];
        uint32_t blockEnd = block->address + block->capacity;

        if (blockEnd < block->address)
            return 0u;

        if (block->inUse)
        {
            if (blockEnd > heapHigh)
                heapHigh = blockEnd;
            if (blockEnd > base)
                return 0u;
            continue;
        }

        if (block->address < base &&
            blockEnd == oldPageNext &&
            base < blockEnd)
        {
            if (tailIndex >= 0)
                return 0u;
            tailIndex = (int)index;
            continue;
        }

        if (block->address >= base || blockEnd > base)
            return 0u;
    }

    if (tailIndex < 0 || heapHigh > base)
        return 0u;

    for (page = firstPage; page <= lastPage; ++page)
        if (s_phase4cVmPageState[page] != PHASE4C_VM_PAGE_UNMANAGED)
            return 0u;

    tail = &s_phase4cHeap[(uint32_t)tailIndex];
    if (tail->address >= base ||
        tail->address + tail->capacity != oldPageNext)
        return 0u;

    tail->capacity = base - tail->address;
    if (tail->capacity == 0u)
        phase4c_heap_remove((DWORD)tailIndex);

    s_phase4cVmReservations[s_phase4cVmReservationCount].base = base;
    s_phase4cVmReservations[s_phase4cVmReservationCount].size = size;
    s_phase4cVmReservations[s_phase4cVmReservationCount].protect = protect;
    s_phase4cVmReservations[s_phase4cVmReservationCount].inUse = 1u;
    ++s_phase4cVmReservationCount;

    for (page = firstPage; page <= lastPage; ++page)
    {
        s_phase4cVmPageState[page] = PHASE4C_VM_PAGE_COMMITTED;
        s_phase4cVmPageProtect[page] = protect;
    }

    memset(g_ram + base, 0, size);
    s_phase4cVmPageNext = base;
    if (actualSize)
        *actualSize = size;

    ++s_phase6atTailClaimSuccesses;
    s_phase6atTailClaimLastBase = base;
    s_phase6atTailClaimLastHeapHigh = heapHigh;
    s_phase6atTailClaimLastAlignment = alignment;

    sprintf(
        line,
        "PASS: Phase 6AT post-create tail claim base=%08X requested=%u rounded=%u actual=%u align=%u old_page_next=%08X new_page_next=%08X heap_high=%08X reservations=%u calls=%u successes=%u",
        (unsigned int)base,
        (unsigned int)requested,
        (unsigned int)size,
        (unsigned int)size,
        (unsigned int)alignment,
        (unsigned int)oldPageNext,
        (unsigned int)s_phase4cVmPageNext,
        (unsigned int)heapHigh,
        (unsigned int)s_phase4cVmReservationCount,
        (unsigned int)s_phase6atTailClaimCalls,
        (unsigned int)s_phase6atTailClaimSuccesses);
    trace(line);

    return base;
}

'''
    return main_text.replace(marker, helper + marker, 1)


def patch_mm166(main_text: str) -> str:
    old_decl = "    uint32_t retailGraphicsClaim=0u;\n"
    new_decl = (
        "    uint32_t retailGraphicsClaim=0u;\n"
        "    uint32_t postCreateTailClaim=0u;\n"
    )
    main_text = replace_unique(
        main_text, old_decl, new_decl, "ordinal-166 claim state"
    )

    old_else = r'''    else
    {
        va=phase5bb_alloc_guest_pages(size,align,prot?prot:0x4u,&actual);
    }

    if(va)
'''
    new_else = r'''    else
    {
        va=phase5bb_alloc_guest_pages(size,align,prot?prot:0x4u,&actual);

        /*
         * 6AS proved the normal allocator must fail after the first graphics
         * claim because it still compares pageNext against the compile-time
         * heap end. While the proven retail D3D initializer is active, allow
         * this exact ordinal-166 full-range physical shape to consume only the
         * current free heap tail.
         */
        if(va==0u &&
           s_phase6atPostCreateInitActive &&
           frameBytes==28u &&
           low==0u &&
           high==0xFFFFFFFFu &&
           prot==0x00000404u)
        {
            va=phase6at_claim_post_create_tail(
                size,
                align,
                prot,
                &actual);
            if(va!=0u)
                postCreateTailClaim=1u;
        }
    }

    if(va)
'''
    main_text = replace_unique(
        main_text, old_else, new_else, "ordinal-166 normal allocator branch"
    )

    old_fmt = (
        '"PASS: Phase 6AR ordinal 166 MmAllocateContiguousMemoryEx '
        'size=%u low=%08X high=%08X align=%u protect=%08X base=%08X '
        'rounded=%u frame=%u spill=%08X repair=%u graphics_claim=%u '
        'resume_esp=%08X saved_esp=%08X",'
    )
    new_fmt = (
        '"PASS: Phase 6AR ordinal 166 MmAllocateContiguousMemoryEx '
        'size=%u low=%08X high=%08X align=%u protect=%08X base=%08X '
        'rounded=%u frame=%u spill=%08X repair=%u graphics_claim=%u '
        'post_init_tail_claim=%u resume_esp=%08X saved_esp=%08X",'
    )
    main_text = replace_unique(main_text, old_fmt, new_fmt, "ordinal-166 trace format")

    old_args = (
        "        (unsigned)extra,(unsigned)repaired,(unsigned)retailGraphicsClaim,\n"
        "        (unsigned)g_esp,(unsigned)savedEsp);"
    )
    new_args = (
        "        (unsigned)extra,(unsigned)repaired,(unsigned)retailGraphicsClaim,\n"
        "        (unsigned)postCreateTailClaim,(unsigned)g_esp,(unsigned)savedEsp);"
    )
    main_text = replace_unique(main_text, old_args, new_args, "ordinal-166 trace args")
    return main_text


def patch_init_active(main_text: str) -> str:
    old = r'''    g_ecx = s_phase6afGuestDevice;
    PUSH32(g_esp, pp);
    PUSH32(g_esp, 0u);
    sub_0028F9E0();

    s_phase6arInitEspAfter = g_esp;
'''
    new = r'''    g_ecx = s_phase6afGuestDevice;
    PUSH32(g_esp, pp);
    PUSH32(g_esp, 0u);
    s_phase6atPostCreateInitActive = 1u;
    sub_0028F9E0();
    s_phase6atPostCreateInitActive = 0u;

    s_phase6arInitEspAfter = g_esp;
'''
    return replace_unique(
        main_text, old, new, "post-Create initializer active scope"
    )


def reset_state(main_text: str) -> str:
    marker = "    s_phase6arInitCalls = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AT] inherited 6AR reset marker missing")
    extra = (
        "    s_phase6atPostCreateInitActive = 0u;\n"
        "    s_phase6atTailClaimCalls = 0u;\n"
        "    s_phase6atTailClaimSuccesses = 0u;\n"
        "    s_phase6atTailClaimLastRequested = 0u;\n"
        "    s_phase6atTailClaimLastRounded = 0u;\n"
        "    s_phase6atTailClaimLastOldNext = 0u;\n"
        "    s_phase6atTailClaimLastBase = 0u;\n"
        "    s_phase6atTailClaimLastHeapHigh = 0u;\n"
        "    s_phase6atTailClaimLastAlignment = 0u;\n"
    )
    return main_text.replace(marker, extra + marker, 1)


def install_summary(main_text: str) -> str:
    marker = "P6AR POST-CREATE D3D INIT:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6AT] inherited 6AR summary marker missing")
    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 4000:
        raise SystemExit("[Phase6AT] could not locate inherited 6AR summary")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6AT D3D TAIL CLAIM: active=%u calls=%u successes=%u requested=%u rounded=%u old_next=%08X base=%08X heap_high=%08X align=%u",\n'
        f'{indent}    (unsigned int)s_phase6atPostCreateInitActive,\n'
        f'{indent}    (unsigned int)s_phase6atTailClaimCalls,\n'
        f'{indent}    (unsigned int)s_phase6atTailClaimSuccesses,\n'
        f'{indent}    (unsigned int)s_phase6atTailClaimLastRequested,\n'
        f'{indent}    (unsigned int)s_phase6atTailClaimLastRounded,\n'
        f'{indent}    (unsigned int)s_phase6atTailClaimLastOldNext,\n'
        f'{indent}    (unsigned int)s_phase6atTailClaimLastBase,\n'
        f'{indent}    (unsigned int)s_phase6atTailClaimLastHeapHigh,\n'
        f'{indent}    (unsigned int)s_phase6atTailClaimLastAlignment);\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + block + main_text[line_start:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AT] optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6AT] optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AT] translated body contains no functions")

    ends = []
    for match in matches:
        brace = masked.find("{", match.start(), match.end())
        if brace < 0:
            raise SystemExit("[Phase6AT] translated function opening brace missing")
        ends.append(base.closing_brace(masked, brace))

    cuts = []
    chunk_start = 0
    last_end = 0
    for end in ends:
        last_end = end
        if end - chunk_start >= SHARD_TARGET_CHARS:
            cuts.append(end)
            chunk_start = end
    if last_end < len(body):
        last_end = len(body)
    if not cuts or cuts[-1] != last_end:
        cuts.append(last_end)

    shard_dir = out_dir / "translated_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale in shard_dir.glob("*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cuts):
        if end <= start:
            continue
        name = f"phase6at_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({
            "name": name,
            "chars": len(payload),
            "lines": payload.count("\n") + 1,
        })
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AT] shard writer did not consume translated body")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n' for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]
    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8")
        for row in shards
    )
    if reconstructed != body:
        raise SystemExit("[Phase6AT] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6at_",
        "shard_count": len(shards),
        "shards": shards,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6ar-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AT] cached Phase 6AR-A input missing: {path}")

    base = load(args.base_emitter, "phase6at_base")
    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AR" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AT] cached Phase 6AR-A identity mismatch")

    ar = manifest.get("phase6ar_post_create_state_init") or {}
    if (
        ar.get("repair", {}).get("function") != "sub_0028F9E0"
        or ar.get("repair", {}).get("this") != "0x00299380"
        or ar.get("kseg_fence_relaxed") is not False
        or ar.get("nv2a_mmio_vram_policy_changed") is not False
    ):
        raise SystemExit("[Phase6AT] inherited Phase 6AR repair model drift")

    required = (
        BASE_TAG,
        COOKIE_OLD,
        "static uint32_t phase6z_claim_retail_graphics_pool(",
        "static void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)",
        "va=phase5bb_alloc_guest_pages(size,align,prot?prot:0x4u,&actual);",
        "sub_0028F9E0();",
        "s_phase6arCountAfter == 0u",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AT] inherited marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = install_tail_claim_helper(main_text)
    main_text = patch_mm166(main_text)
    main_text = patch_init_active(main_text)
    main_text = reset_state(main_text)
    main_text = install_summary(main_text)

    policy = (
        "Policy: inherit 6AR selective retail D3D init; during sub_0028F9E0 "
        "only, let proven ordinal-166 full-range contiguous requests trim the "
        "current free heap tail after normal allocation fails; keep all fences hard"
    )
    if len(policy) > 240:
        raise SystemExit("[Phase6AT] startup policy trace exceeds safe length")
    main_text = replace_policy_line(main_text, policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text
        .replace("PHASE 6AR", "PHASE 6AT")
        .replace("Phase 6AR", "Phase 6AT")
        .replace('"P6AR ', '"P6AT ')
    )
    env_text = (
        env_text
        .replace("PHASE 6AR", "PHASE 6AT")
        .replace("Phase 6AR", "Phase 6AT")
    )

    must = (
        BUILD_TAG,
        COOKIE_NEW,
        "phase6at_claim_post_create_tail(",
        "s_phase6atPostCreateInitActive = 1u;",
        "post_init_tail_claim=%u",
        "P6AT D3D TAIL CLAIM:",
        "P6AT POST-CREATE D3D INIT:",
    )
    for marker in must:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AT] generated source lost marker: {marker}")

    if "PHASE4C_TITLE_HEAP_END)" not in main_text:
        raise SystemExit("[Phase6AT] inherited fixed heap-boundary code unexpectedly absent")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6AT", "build_tag": BUILD_TAG})
    manifest["phase6at_d3d_dual_frontier_continue"] = {
        "source_phase": "6AR",
        "hardware_evidence": {
            "old_orange_fault_eliminated": True,
            "d3d_count_before": 0,
            "d3d_count_after": 2,
            "new_hresult": "0x8007000E",
            "first_graphics_claim": {
                "base": "0x02880000",
                "size": "0x01680000",
                "old_page_next": "0x03F00000",
                "new_page_next": "0x02880000",
            },
            "failed_followup": {
                "size": "0x00258000",
                "alignment": "0x00004000",
                "protect": "0x00000404",
                "result": "0x00000000",
            },
        },
        "repair": {
            "normal_allocator_first": True,
            "scope": "only while sub_0028F9E0 is active",
            "ordinal": 166,
            "require_frame_bytes": 28,
            "require_low": "0x00000000",
            "require_high": "0xFFFFFFFF",
            "require_protect": "0x00000404",
            "claim_only_current_free_heap_tail": True,
            "reject_live_heap_overlap": True,
            "require_unmanaged_pages": True,
        },
        "kseg_fence_relaxed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "source_layout": layout,
    }

    (args.out_dir / "phase6at-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print("[Phase6AT] D3D DUAL-FRONTIER CONTINUATION REPAIR: READY")
    print("[Phase6AT] Normal allocator     : FIRST")
    print("[Phase6AT] Tail fallback scope  : active sub_0028F9E0 only")
    print("[Phase6AT] Ordinal shape        : 166 / full range / prot 00000404")
    print("[Phase6AT] Heap safety          : free-tail only / no live overlap")
    print("[Phase6AT] KSEG/MMIO/VRAM       : unchanged / hard fenced")
    print("[Phase6AT] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

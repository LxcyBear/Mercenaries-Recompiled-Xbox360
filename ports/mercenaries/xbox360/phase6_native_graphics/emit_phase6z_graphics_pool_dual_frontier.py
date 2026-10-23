#!/usr/bin/env python3
"""Phase 6Z: restore dual-frontier RAM semantics for the retail graphics pool.

Hardware Phase 6Y-B proved:
  * the +28 ordinal-166 wrapper repair is correct;
  * MmAllocateContiguousMemoryEx receives the retail request 0x01680000;
  * the synthetic allocator returns NULL / error 8;
  * the failure then branches to direct frontier 0x0020FAE0.

The failure is an artifact of the focused Xbox360 allocator: page-backed
allocations are forbidden below the fixed PHASE4C_TITLE_HEAP_END, even though
that 32 MiB title-heap value is only arena capacity. The maintained production
allocator instead grows ordinary heap blocks upward and page-backed allocations
downward until the *live* frontiers meet.

For the hardware-proven retail graphics request, 6Z restores that behavior in a
bounded way. With the prior 1 MiB VM reservation, s_phase4cVmPageNext is
0x03F00000. A 0x01680000 page-backed allocation therefore begins at 0x02880000.
That is only 0x00040000 below the prior synthetic heap ceiling 0x028C0000.

Before claiming it, 6Z requires:
  * exact retail ordinal-166 request/frame/protection shape;
  * page_next == 0x03F00000 and candidate == 0x02880000;
  * every candidate page is unmanaged;
  * no in-use title-heap block crosses the candidate;
  * one free title-heap tail block contains the candidate and reaches exactly
    the old synthetic heap end.

It then trims only that free 256 KiB tail, records/commits the graphics range,
and moves the page frontier down to 0x02880000. No in-use title heap bytes are
moved or overwritten. All unrelated MmAllocateContiguousMemoryEx calls retain
the Phase 6Y behavior.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BUILD_TAG = "P6Z-GFXPOOL-DUAL-FRONTIER-20261023-A"
BASE_TAG = "P6Y-GFXPOOL-MM166-FRAME-20261023-B"
RETAIL_POOL_SIZE = 0x01680000
EXPECTED_OLD_PAGE_NEXT = 0x03F00000
EXPECTED_POOL_BASE = 0x02880000
EXPECTED_OLD_HEAP_END = 0x028C0000
EXPECTED_TRIM = 0x00040000
COOKIE_OLD = "phase6y_env_build_cookie"
COOKIE_NEW = "phase6z_env_build_cookie"
COOKIE_NUM_OLD = "50365959"
COOKIE_NUM_NEW = "50366060"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6Z] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def function_span(text: str, signature: str) -> tuple[int, int]:
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"[Phase6Z] function marker missing: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"[Phase6Z] opening brace missing: {signature}")
    depth = 0
    i = brace
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return start, i + 1
        i += 1
    raise SystemExit(f"[Phase6Z] unterminated function: {signature}")


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6Z] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6z_base")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6y-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6Z] cached Phase 6Y baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6Y" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6Z] cached Phase 6Y baseline identity mismatch")

    repair = manifest.get("phase6y_mm166_frame_repair") or {}
    proof = repair.get("generated_wrapper_proof") or {}
    if (
        repair.get("retail_pool_size") != "0x01680000"
        or int(proof.get("canonical_kernel_frame_bytes", 0)) != 24
        or int(proof.get("wrapper_spill_bytes", 0)) != 4
        or int(proof.get("observed_saved_esp_delta_proven", 0)) != 28
    ):
        raise SystemExit("[Phase6Z] inherited Phase 6Y ABI proof is incomplete")

    # Gate on the semantic symbols/capacities 6Z actually consumes rather
    # than whitespace-sensitive declaration formatting.  The inherited
    # Phase5BB donor intentionally line-wraps the reservation array and uses
    # Xbox/XDK BYTE/DWORD aliases for the page tables.
    required_base_markers = (
        "#define PHASE4C_TITLE_HEAP_BASE  0x008C0000u",
        "#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)",
        "typedef struct Phase4CHeapBlock",
        "s_phase4cHeap[PHASE4C_HEAP_BLOCKS];",
        "s_phase4cHeapCount;",
        "static void phase4c_heap_init(void)",
        "static void phase4c_heap_remove(DWORD index)",
        "#define PHASE4C_VM_RESERVATION_CAP 64u",
        "typedef struct Phase4CVmReservation",
        "s_phase4cVmReservations[PHASE4C_VM_RESERVATION_CAP];",
        "s_phase4cVmReservationCount;",
        "s_phase4cVmPageNext = RAM_SIZE;",
        "#define PHASE4C_VM_PAGE_UNMANAGED 0u",
        "s_phase4cVmPageState[PHASE4C_VM_PAGE_COUNT];",
        "P6Y-GFXPOOL-MM166-FRAME-20261023-B",
        "size!=0x01680000u || extra!=g_esi",
        "resumeEsp=c+24u",
    )
    for marker in required_base_markers:
        if marker not in main_text:
            raise SystemExit(f"[Phase6Z] Phase 6Y baseline lost marker: {marker}")

    signature = "static void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)"
    start, end = function_span(main_text, signature)

    replacement = r'''static uint32_t phase6z_claim_retail_graphics_pool(
    uint32_t requested,
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

    if (actualSize)
        *actualSize = 0u;

    /*
     * This is intentionally the exact Phase-6Y hardware case. General
     * page-backed allocation policy remains unchanged until hardware asks for
     * another shape.
     */
    if (size != 0x01680000u ||
        oldPageNext != 0x03F00000u ||
        s_phase4cVmReservationCount >= PHASE4C_VM_RESERVATION_CAP)
        return 0u;

    base = (oldPageNext - size) & ~0xFFFu;
    if (base != 0x02880000u ||
        base + size != oldPageNext ||
        !phase4c_vm_page_range(base, size, &firstPage, &lastPage))
        return 0u;

    phase4c_heap_init();

    /*
     * The fixed 32 MiB title heap is capacity, not live occupancy. Its block
     * table is sorted and first-fit. Require the candidate to cut only the
     * final free tail; any live allocation at/above the candidate is a hard
     * incompatibility with this bounded repair.
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
            blockEnd == PHASE4C_TITLE_HEAP_END &&
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
        tail->address + tail->capacity != PHASE4C_TITLE_HEAP_END)
        return 0u;

    /*
     * Trim only the free title-heap tail that overlaps the new page-backed
     * frontier. For this hardware state the trim is exactly 0x40000 bytes.
     */
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

    sprintf(
        line,
        "PASS: Phase 6Z retail graphics pool claim base=%08X size=%u old_page_next=%08X new_page_next=%08X heap_high=%08X old_heap_end=%08X trimmed=%u reservations=%u",
        (unsigned)base,
        (unsigned)size,
        (unsigned)oldPageNext,
        (unsigned)s_phase4cVmPageNext,
        (unsigned)heapHigh,
        (unsigned)PHASE4C_TITLE_HEAP_END,
        (unsigned)(PHASE4C_TITLE_HEAP_END - base),
        (unsigned)s_phase4cVmReservationCount);
    trace(line);

    return base;
}

static void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)
{
    uint32_t c=g_esp,ret,size,low,high,align,prot,actual=0u,va;
    uint32_t frameBytes=savedEsp-c;
    uint32_t extra=0u;
    uint32_t repaired=0u;
    uint32_t retailGraphicsClaim=0u;
    uint32_t resumeEsp=0u;
    char line[768];

    if(frameBytes!=24u && frameBytes!=28u)
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A6u,savedEsp);

    ret=GUEST_READ32(c);
    size=GUEST_READ32(c+4u);
    low=GUEST_READ32(c+8u);
    high=GUEST_READ32(c+12u);
    align=GUEST_READ32(c+16u);
    prot=GUEST_READ32(c+20u);
    if(frameBytes==28u)
        extra=GUEST_READ32(c+24u);

    if(s_accessFault)
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT,0x800000A6u,savedEsp);
    if(ret!=0u)
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A6u,savedEsp);

    if(frameBytes==28u)
    {
        if(size!=0x01680000u || extra!=g_esi)
            phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME,0x800000A6u,savedEsp);
        repaired=1u;
    }

    resumeEsp=c+24u;

    ++s_phase5bbMmCallCount;
    s_phase5bbMmLastOrdinal=166u;

    /*
     * Phase 6Y hardware uniquely identifies this call as the retail graphics
     * pool: full physical range, default alignment, PAGE_READWRITE|0x400, and
     * the proven wrapper frame. Give only that call the dual-frontier claim.
     */
    if(frameBytes==28u &&
       size==0x01680000u &&
       low==0u &&
       high==0xFFFFFFFFu &&
       align==0u &&
       prot==0x00000404u)
    {
        retailGraphicsClaim=1u;
        va=phase6z_claim_retail_graphics_pool(size,prot,&actual);
        if(va==0u)
        {
            trace("Phase 6Z retail graphics pool dual-frontier claim failed");
            phase4c_escape(
                PHASE4C_BOUNDARY_HEAP_EXHAUSTED,
                size,
                savedEsp);
        }
    }
    else
    {
        va=phase5bb_alloc_guest_pages(size,align,prot?prot:0x4u,&actual);
    }

    if(va)
        ++s_phase5bbMmAllocSuccessCount;
    s_phase5bbMmLastBase=va;
    s_phase5bbMmLastSize=actual;
    g_eax=va;
    g_esp=resumeEsp;

    sprintf(
        line,
        "PASS: Phase 6Z ordinal 166 MmAllocateContiguousMemoryEx size=%u low=%08X high=%08X align=%u protect=%08X base=%08X rounded=%u frame=%u spill=%08X repair=%u graphics_claim=%u resume_esp=%08X saved_esp=%08X",
        (unsigned)size,(unsigned)low,(unsigned)high,(unsigned)align,
        (unsigned)prot,(unsigned)va,(unsigned)actual,(unsigned)frameBytes,
        (unsigned)extra,(unsigned)repaired,(unsigned)retailGraphicsClaim,
        (unsigned)g_esp,(unsigned)savedEsp);
    trace(line);
}'''

    main_text = main_text[:start] + replacement + main_text[end:]

    main_text = replace_unique(
        main_text, BASE_TAG, BUILD_TAG, "Phase 6Y build tag"
    )
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = main_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)
    env_text = env_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)

    main_text = main_text.replace("P6Y MM166 SUMMARY:", "P6Z GFXPOOL CLAIM SUMMARY:")
    main_text = main_text.replace(
        "PHASE 6Y GRAPHICS-POOL MM166 RESULT",
        "PHASE 6Z GRAPHICS-POOL DUAL-FRONTIER RESULT",
    )
    main_text = main_text.replace("PHASE 6Y", "PHASE 6Z")
    main_text = main_text.replace("Phase 6Y", "Phase 6Z")
    main_text = main_text.replace('"P6Y ', '"P6Z ')
    env_text = env_text.replace("PHASE 6Y", "PHASE 6Z")
    env_text = env_text.replace("Phase 6Y", "Phase 6Z")

    required = (
        BUILD_TAG,
        "phase6z_env_build_cookie",
        "PASS: Phase 6Z retail graphics pool claim",
        "base != 0x02880000u",
        "oldPageNext != 0x03F00000u",
        "PHASE4C_TITLE_HEAP_END - base",
        "size==0x01680000u",
        "high==0xFFFFFFFFu",
        "prot==0x00000404u",
        "graphics_claim=%u",
        "resumeEsp=c+24u",
        "P6Z XENOS: PASS Direct3D_CreateDevice",
        "P6Z FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6Z FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "#define PHASE4C_EXEC_BUDGET 2000000u",
        "#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6Z] generated main lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    base6x_path = Path(__file__).with_name(
        "emit_phase6x_graphics_pool_frontier_0020f9c0.py"
    )
    p6x = load(base6x_path, "phase6z_phase6x")
    source_layout = p6x.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6Z",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6z_graphics_pool_dual_frontier"] = {
        "source_phase": "6Y",
        "phase6y_hardware_pass": True,
        "phase6y_hardware": {
            "allocator": "MmAllocateContiguousMemoryEx",
            "ordinal": 166,
            "size": "0x01680000",
            "low": "0x00000000",
            "high": "0xFFFFFFFF",
            "alignment": 0,
            "protect": "0x00000404",
            "result": "0x00000000",
            "last_error": 8,
            "failure_frontier": "0x0020FAE0",
            "ticks": 670789,
            "trace": 179925,
            "fault": 0,
        },
        "memory_model": {
            "policy": "bounded production-style dual frontier",
            "old_page_next": "0x03F00000",
            "retail_pool_size": "0x01680000",
            "expected_pool_base": "0x02880000",
            "old_title_heap_end": "0x028C0000",
            "free_title_heap_tail_trim": "0x00040000",
            "rule": (
                "trim only the free title-heap tail after proving no in-use "
                "heap block crosses the candidate; then commit the page-backed "
                "graphics range and move page_next downward"
            ),
        },
        "failure_frontier_policy": (
            "do not pack 0x0020FAE0 yet; it was observed only after the "
            "graphics allocation returned NULL / error 8"
        ),
        "source_layout": source_layout,
    }

    (args.out_dir / "phase6z-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print("[Phase6Z] DUAL-FRONTIER GRAPHICS POOL: READY")
    print("[Phase6Z] Old page frontier : 0x03F00000")
    print("[Phase6Z] Retail pool bytes : 0x01680000 (22.5 MiB)")
    print("[Phase6Z] Candidate base    : 0x02880000")
    print("[Phase6Z] Free heap trim    : 0x00040000 (256 KiB)")
    print("[Phase6Z] Failure frontier  : 0x0020FAE0 intentionally NOT packed")
    print("[Phase6Z] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

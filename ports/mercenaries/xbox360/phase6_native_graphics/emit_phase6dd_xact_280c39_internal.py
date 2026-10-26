#!/usr/bin/env python3
r"""Phase 6DD: localize the creation of FBE2 arg1=0x00041D90 inside 00280C39.

6DC hardware proved:
  * sub_0027ED57 calls sub_00280C39 with normal-looking args:
      1, 0x40, 1, 0x0085C604, 0x008BFF8C, 0
  * sub_00280C39 later calls sub_0029FBE2 with arg1=0x00041D90.
  * FBE2 transforms that to 0x00041D88, which reaches DSOUND and ultimately
    produces [0x00041D88] = 0xCCCCCCCC -> READ32 0xCCCCCCD0.

Therefore 0x00041D90 is produced or loaded inside sub_00280C39.

6DD is diagnostic only. It instruments only sub_00280C39:
  * every translated basic-block label records the live guest registers;
  * every literal GUEST_READ32 is wrapped with a site/VA-aware logger;
  * immediately before the proven FBE2 call, if the already-recorded 6DB
    argument is 0x00041D90, the recent block-history ring is dumped.

No pointer is substituted, no fault is suppressed, and no address range is
widened.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6DC-XACT-00280C39-PROVENANCE-20261026-A"
BUILD_TAG = "P6DD-XACT-280C39-ARG1-INTERNAL-20261026-A"
COOKIE_OLD = "phase6dc_env_build_cookie"
COOKIE_NEW = "phase6dd_env_build_cookie"
EMITTER_REVISION = "6DD-R2"

TARGET_NAME = "sub_00280C39"
TARGET_VA = 0x00280C39
EXPECTED_ARG1 = 0x00041D90
RING_CAP = 64


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DD] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def locate_target(text: str, base) -> tuple[int, int]:
    masked = base.mask_noncode(text)
    rows = []
    for match in base.FUNC_RE.finditer(masked):
        if match.group(1) != TARGET_NAME:
            continue
        open_pos = masked.find("{", match.start(), match.end())
        if open_pos < 0:
            continue
        end = base.closing_brace(masked, open_pos)
        rows.append((match.start(), end))

    if len(rows) != 1:
        raise SystemExit(
            f"[Phase6DD] expected one {TARGET_NAME} body, found {len(rows)}"
        )
    return rows[0]


def install_state(text: str) -> str:
    anchor = "static DWORD s_phase6dcEntryReports = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6DD] expected one 6DC state anchor, found {text.count(anchor)}"
        )

    state = f"""#define PHASE6DD_RING_CAP {RING_CAP}u
static DWORD s_phase6ddBlockNotes = 0u;
static DWORD s_phase6ddReadReports = 0u;
static DWORD s_phase6ddReadMatches = 0u;
static DWORD s_phase6ddDumpCalls = 0u;
static DWORD s_phase6ddLastReadVa = 0u;
static DWORD s_phase6ddLastReadSite = 0u;
static DWORD s_phase6ddLastReadAddress = 0u;
static DWORD s_phase6ddLastReadValue = 0u;
static DWORD s_phase6ddRingWrite = 0u;
static DWORD s_phase6ddRingCount = 0u;
static DWORD s_phase6ddRingVa[PHASE6DD_RING_CAP];
static DWORD s_phase6ddRingEax[PHASE6DD_RING_CAP];
static DWORD s_phase6ddRingEcx[PHASE6DD_RING_CAP];
static DWORD s_phase6ddRingEdx[PHASE6DD_RING_CAP];
static DWORD s_phase6ddRingEbx[PHASE6DD_RING_CAP];
static DWORD s_phase6ddRingEsi[PHASE6DD_RING_CAP];
static DWORD s_phase6ddRingEdi[PHASE6DD_RING_CAP];
static DWORD s_phase6ddRingEsp[PHASE6DD_RING_CAP];

"""
    return text.replace(anchor, state + anchor, 1)


def install_helpers(text: str) -> str:
    marker = '#pragma optimize("", off)\n'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DD] translated optimize-off marker missing")

    helper = r'''
static void phase6dd_note_280c39(DWORD va)
{
    DWORD index = s_phase6ddRingWrite;

    ++s_phase6ddBlockNotes;
    s_phase6ddRingVa[index] = va;
    s_phase6ddRingEax[index] = eax;
    s_phase6ddRingEcx[index] = ecx;
    s_phase6ddRingEdx[index] = edx;
    s_phase6ddRingEbx[index] = ebx;
    s_phase6ddRingEsi[index] = esi;
    s_phase6ddRingEdi[index] = edi;
    s_phase6ddRingEsp[index] = esp;

    ++index;
    if (index >= PHASE6DD_RING_CAP)
        index = 0u;
    s_phase6ddRingWrite = index;

    if (s_phase6ddRingCount < PHASE6DD_RING_CAP)
        ++s_phase6ddRingCount;
}

static uint32_t phase6dd_read32_280c39(
    DWORD va,
    DWORD site,
    DWORD sourceLine,
    uint32_t address)
{
    uint32_t value = phase6cy_read32_site(0x00280C39u, sourceLine, address);
    char line[512];

    ++s_phase6ddReadReports;
    s_phase6ddLastReadVa = va;
    s_phase6ddLastReadSite = site;
    s_phase6ddLastReadAddress = address;
    s_phase6ddLastReadValue = value;

    if (value == 0x00041D90u)
        ++s_phase6ddReadMatches;

    if (s_phase6ddReadReports <= 96u ||
        value == 0x00041D90u ||
        address == 0x00041D90u)
    {
        sprintf(
            line,
            "P6DD 280C39 READ32: seq=%u va=%08X site=%u line=%u address=%08X value=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X matches=%u",
            (unsigned int)s_phase6ddReadReports,
            (unsigned int)va,
            (unsigned int)site,
            (unsigned int)sourceLine,
            (unsigned int)address,
            (unsigned int)value,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)ebx,
            (unsigned int)esi,
            (unsigned int)edi,
            (unsigned int)esp,
            (unsigned int)s_phase6ddReadMatches);
        trace(line);
    }

    return value;
}

static void phase6dd_dump_280c39_ring(void)
{
    DWORD i;
    DWORD start = 0u;
    char line[512];

    ++s_phase6ddDumpCalls;
    sprintf(
        line,
        "P6DD 280C39 RING BEGIN: dump=%u count=%u read_reports=%u read_matches=%u",
        (unsigned int)s_phase6ddDumpCalls,
        (unsigned int)s_phase6ddRingCount,
        (unsigned int)s_phase6ddReadReports,
        (unsigned int)s_phase6ddReadMatches);
    trace(line);

    if (s_phase6ddRingCount == PHASE6DD_RING_CAP)
        start = s_phase6ddRingWrite;

    for (i = 0u; i < s_phase6ddRingCount; ++i)
    {
        DWORD index = start + i;
        if (index >= PHASE6DD_RING_CAP)
            index -= PHASE6DD_RING_CAP;

        sprintf(
            line,
            "P6DD 280C39 RING[%02u]: va=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
            (unsigned int)i,
            (unsigned int)s_phase6ddRingVa[index],
            (unsigned int)s_phase6ddRingEax[index],
            (unsigned int)s_phase6ddRingEcx[index],
            (unsigned int)s_phase6ddRingEdx[index],
            (unsigned int)s_phase6ddRingEbx[index],
            (unsigned int)s_phase6ddRingEsi[index],
            (unsigned int)s_phase6ddRingEdi[index],
            (unsigned int)s_phase6ddRingEsp[index]);
        trace(line);
    }

    trace("P6DD 280C39 RING END");
}

'''
    return text[:pos] + helper + text[pos:]


def patch_target(text: str, base):
    start, end = locate_target(text, base)
    body = text[start:end]

    # Preserve a source snapshot for the manifest/prep output.
    source_lines = body.splitlines()

    # Wrap each literal READ32 in the target only. Track the nearest retail
    # basic-block VA so the hardware log identifies the exact source block.
    current_va = TARGET_VA
    site = 0
    wrapped_lines = []
    read_sites = []

    label_re = re.compile(r"^\s*loc_([0-9A-Fa-f]{8})\s*:\s*;\s*$")
    read_re = re.compile(r"GUEST_READ32\(")

    for source_line, line in enumerate(source_lines, 1):
        lm = label_re.match(line)
        if lm:
            current_va = int(lm.group(1), 16)

        def repl(_match):
            nonlocal site
            site += 1
            read_sites.append({
                "site": site,
                "va": f"0x{current_va:08X}",
                "source_line": source_line,
                "source": line.strip()[:500],
            })
            return (
                f"phase6dd_read32_280c39("
                f"0x{current_va:08X}u, {site}u, {source_line}u, "
            )

        # Do not instrument inherited diagnostic reads from 6DB/6DC.
        # Those probes intentionally reread the already-known call frame and
        # would create a false "producer" hit for 0x00041D90.
        if "phase6db" in line or "phase6dc" in line:
            wrapped_lines.append(line)
        else:
            wrapped_lines.append(read_re.sub(repl, line))

    body = "\n".join(wrapped_lines)
    if text[start:end].endswith("\n"):
        body += "\n"

    # Record every basic-block transition.
    label_re_multi = re.compile(
        r"(?m)^(\s*)loc_([0-9A-Fa-f]{8})\s*:\s*;\s*$"
    )
    label_count = 0
    pieces = []
    cursor = 0
    for match in label_re_multi.finditer(body):
        label_count += 1
        pieces.append(body[cursor:match.end()])
        va = int(match.group(2), 16)
        pieces.append(
            f"\n{match.group(1)}    phase6dd_note_280c39(0x{va:08X}u);"
        )
        cursor = match.end()
    pieces.append(body[cursor:])
    body = "".join(pieces)

    if label_count < 1:
        raise SystemExit("[Phase6DD] target contains no basic-block labels")
    if site < 1:
        raise SystemExit("[Phase6DD] target contains no GUEST_READ32 sites")

    # The inherited 6DB call-site probe has already saved the exact FBE2 arg1
    # into s_phase6dbFbe2LastArg1 immediately before this call. Dump the ring
    # only for the failing hardware value.
    call = "PUSH32(esp, 0); sub_0029FBE2(); /* call 0x0029FBE2 */"
    call_pos = body.find(call)
    if call_pos < 0:
        raise SystemExit("[Phase6DD] 280C39->FBE2 call missing after READ32 patch")
    line_start = body.rfind("\n", 0, call_pos) + 1
    indent = body[line_start:call_pos]
    indent = indent[:len(indent) - len(indent.lstrip())]
    trigger = (
        f'{indent}if (s_phase6dbFbe2LastArg1 == 0x00041D90u)\n'
        f'{indent}    phase6dd_dump_280c39_ring();\n'
    )
    body = body[:line_start] + trigger + body[line_start:]

    audit = {
        "source_lines": source_lines,
        "read_sites": read_sites,
        "basic_block_count": label_count,
        "read_site_count": site,
    }
    return text[:start] + body + text[end:], audit


def insert_summary(text: str) -> str:
    marker = "P6DC XACT 00280C39 PROVENANCE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DD] inherited 6DC summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6DD] summary insertion point changed")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6DD 280C39 INTERNAL: block_notes=%u reads=%u read_matches=%u dumps=%u last_va=%08X last_site=%u last_addr=%08X last_value=%08X",\n'
        f'{indent}    (unsigned int)s_phase6ddBlockNotes,\n'
        f'{indent}    (unsigned int)s_phase6ddReadReports,\n'
        f'{indent}    (unsigned int)s_phase6ddReadMatches,\n'
        f'{indent}    (unsigned int)s_phase6ddDumpCalls,\n'
        f'{indent}    (unsigned int)s_phase6ddLastReadVa,\n'
        f'{indent}    (unsigned int)s_phase6ddLastReadSite,\n'
        f'{indent}    (unsigned int)s_phase6ddLastReadAddress,\n'
        f'{indent}    (unsigned int)s_phase6ddLastReadValue);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DD] expected one 6DC build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DC", "PHASE 6DD")
        .replace("Phase 6DC", "Phase 6DD")
        .replace('"P6DC ', '"P6DD ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DD] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DC", "PHASE 6DD")
        .replace("Phase 6DC", "Phase 6DD")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6dd_base")
    p6bl = load(args.phase6bl_emitter, "phase6dd_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6dc-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6DD] missing input: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DC" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DD] cached 6DC identity mismatch")

    dc = manifest.get("phase6dc_xact_00280c39_provenance", {})
    if (
        dc.get("probe_only") is not True
        or dc.get("guest_memory_semantics_changed") is not False
        or dc.get("value_fabrication") is not False
        or dc.get("fault_suppression") is not False
        or dc.get("address_range_widened") is not False
        or dc.get("execution_budget_inherited") != 64000000
        or dc.get("hard_fences_weakened") is not False
    ):
        raise SystemExit("[Phase6DD] inherited 6DC policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6DC XACT 00280C39 ENTRY:",
        "P6DC XACT 00280C39 PROVENANCE:",
        "P6DC FBE2 CALLER:",
        "P6DC PREFAULT ROUTER READ32:",
        "PASS: Phase 6DC ExFreePool ITAIL",
        "PASS: Phase 6DC manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6DC APU CORE:",
        "P6DC AV/DISPLAY SUMMARY:",
        TARGET_NAME,
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DD] inherited marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = install_helpers(main_text)
    main_text, audit = patch_target(main_text, base)
    main_text = insert_summary(main_text)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "P6DD 280C39 READ32:",
        "P6DD 280C39 RING BEGIN:",
        "P6DD 280C39 RING[",
        "P6DD 280C39 INTERNAL:",
        "P6DD XACT 00280C39 ENTRY:",
        "P6DD FBE2 CALLER:",
        "P6DD PREFAULT ROUTER READ32:",
        "PASS: Phase 6DD ExFreePool ITAIL",
        "PASS: Phase 6DD manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6DD APU CORE:",
        "P6DD AV/DISPLAY SUMMARY:",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6DD] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6DD",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6dd_xact_280c39_internal"] = {
        "source_phase": "6DC",
        "hardware_proof": {
            "caller_of_280c39": "0x0027ED57",
            "entry_args": [
                "0x00000001",
                "0x00000040",
                "0x00000001",
                "0x0085C604",
                "0x008BFF8C",
                "0x00000000",
            ],
            "fbe2_arg1": "0x00041D90",
            "downstream_bad_object": "0x00041D88",
            "fault_address": "0xCCCCCCD0",
            "ticks": 27021609,
        },
        "target": "0x00280C39",
        "basic_block_count": audit["basic_block_count"],
        "read_site_count": audit["read_site_count"],
        "read_sites": audit["read_sites"],
        "target_source_lines": audit["source_lines"],
        "ring_capacity": RING_CAP,
        "probe_only": True,
        "guest_memory_semantics_changed": False,
        "value_fabrication": False,
        "fault_suppression": False,
        "address_range_widened": False,
        "execution_budget_inherited": 64000000,
        "exfreepool_itail_preserved": True,
        "manual_dsound_decrypt_preserved": True,
        "shadow_ram_alias_preserved": True,
        "graphics_semantics_changed": False,
        "apu_semantics_changed": False,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }
    (args.out_dir / "phase6dd-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6DD] emitter revision: {EMITTER_REVISION}")
    print(
        f"[Phase6DD] target 00280C39: blocks={audit['basic_block_count']} "
        f"read32_sites={audit['read_site_count']} ring={RING_CAP}"
    )
    print("[Phase6DD] TARGET SOURCE AUDIT BEGIN")
    for i, line in enumerate(audit["source_lines"], 1):
        print(f"[Phase6DD] SRC {i:03d}: {line}")
    print("[Phase6DD] TARGET SOURCE AUDIT END")
    print("[Phase6DD] no pointer substitution; no fault suppression")
    print("[Phase6DD] money lines:")
    print("[Phase6DD]   P6DD 280C39 READ32: ... value=00041D90 ...")
    print("[Phase6DD]   P6DD 280C39 RING BEGIN: ...")
    print("[Phase6DD]   P6DD 280C39 RING[..]: va=... registers...")
    print("[Phase6DD] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

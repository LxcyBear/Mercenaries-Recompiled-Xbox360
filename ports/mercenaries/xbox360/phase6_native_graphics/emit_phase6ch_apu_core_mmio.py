#!/usr/bin/env python3
"""Phase 6CH: conservative MCPX APU core-MMIO bootstrap for translated DSOUND.

6CG hardware crossed ordinal 160 KfRaiseIrql and, four translated ticks later,
hit the first real Xbox audio hardware access:
  READ8 FE801100
  boundary=GUEST_FAULT ticks=26,711,305 fault=1

FE801100 is MCPX APU offset 0x1100 (NV_PAPU_FECTL). xemu's MCPX APU model
resets the core register array to zero and treats offsets below 0x20000 as
register storage, with ISTS writes using write-one-to-clear semantics and
FECTL/SECTL as ordinary stored controls.

6CH adds only that core register bootstrap, scoped to translated functions
inside the retail DSOUND XBE section. Normal RAM and every other MMIO region
continue to use the existing checked guest access path. No actual audio mixer,
voice processor, DSP worker, interrupt delivery, or host audio backend is
claimed by this phase.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6CG-KFRAISEIRQL160-20261025-A"
BUILD_TAG = "P6CH-APU-CORE-MMIO-20261025-A"
COOKIE_OLD = "phase6cg_env_build_cookie"
COOKIE_NEW = "phase6ch_env_build_cookie"

DSOUND_START = 0x0029CB80
DSOUND_END = 0x002BB274
FAULT_VA = 0x002A7254
APU_BASE = 0xFE800000
APU_CORE_SIZE = 0x00020000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CH] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CH] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def install_state(text: str) -> str:
    anchor = "static uint32_t s_phase6cgKfRaiseIrqlLastRawEcx = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CH] expected one early 6CG state anchor, found {text.count(anchor)}"
        )

    state = """static uint32_t s_phase6chApuRegs[0x8000];
static uint32_t s_phase6chApuRead8Count = 0u;
static uint32_t s_phase6chApuRead16Count = 0u;
static uint32_t s_phase6chApuRead32Count = 0u;
static uint32_t s_phase6chApuWrite8Count = 0u;
static uint32_t s_phase6chApuWrite16Count = 0u;
static uint32_t s_phase6chApuWrite32Count = 0u;
static uint32_t s_phase6chApuLastAddress = 0u;
static uint32_t s_phase6chApuLastValue = 0u;
static uint32_t s_phase6chApuFaultOwnerEntries = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def install_support(text: str) -> str:
    anchor = "static void phase4c_budget_tick(DWORD va)\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CH] expected one budget helper anchor, found {text.count(anchor)}"
        )

    support = r'''#define PHASE6CH_APU_BASE      0xFE800000u
#define PHASE6CH_APU_CORE_SIZE 0x00020000u
#define PHASE6CH_APU_ISTS      0x00001000u
#define PHASE6CH_APU_FECTL     0x00001100u
#define PHASE6CH_APU_SECTL     0x00002000u
#define PHASE6CH_APU_XGSCNT    0x0000200Cu
#define PHASE6CH_APU_FEMEMADDR 0x00001324u
#define PHASE6CH_APU_FEMEMDATA 0x00001334u

static int phase6ch_apu_core_range(
    uint32_t address,
    uint32_t width,
    uint32_t* outOffset)
{
    uint32_t offset;

    if (width == 0u || width > 4u)
        return 0;
    if (address < PHASE6CH_APU_BASE)
        return 0;

    offset = address - PHASE6CH_APU_BASE;
    if (offset >= PHASE6CH_APU_CORE_SIZE ||
        width > PHASE6CH_APU_CORE_SIZE - offset)
        return 0;

    if (outOffset)
        *outOffset = offset;
    return 1;
}

static uint8_t phase6ch_apu_shadow_read_byte(uint32_t offset)
{
    uint32_t word = s_phase6chApuRegs[(offset & ~3u) >> 2];
    return (uint8_t)((word >> ((offset & 3u) * 8u)) & 0xFFu);
}

static void phase6ch_apu_shadow_write_byte(
    uint32_t offset,
    uint8_t value)
{
    uint32_t index = (offset & ~3u) >> 2;
    uint32_t shift = (offset & 3u) * 8u;
    uint32_t mask = 0xFFu << shift;
    s_phase6chApuRegs[index] =
        (s_phase6chApuRegs[index] & ~mask) |
        ((uint32_t)value << shift);
}

static uint32_t phase6ch_apu_shadow_read(
    uint32_t address,
    uint32_t width)
{
    uint32_t offset;
    uint32_t value = 0u;
    uint32_t i;

    if (!phase6ch_apu_core_range(address, width, &offset))
        return 0u;

    /*
     * xemu resets the APU core register file to zero. Keep XGSCNT at zero in
     * this bootstrap because there is not yet an APU worker/frame engine on
     * Xenon. If retail later requires a moving sample counter, that remains a
     * separate hardware-evidence phase rather than inventing timing here.
     */
    for (i = 0u; i < width; ++i)
        value |=
            ((uint32_t)phase6ch_apu_shadow_read_byte(offset + i)) <<
            (i * 8u);

    return value;
}

static void phase6ch_apu_shadow_write(
    uint32_t address,
    uint32_t width,
    uint32_t value)
{
    uint32_t offset;
    uint32_t i;

    if (!phase6ch_apu_core_range(address, width, &offset))
        return;

    /*
     * NV_PAPU_ISTS is write-one-to-clear. Apply the same lane semantics for
     * 8/16/32-bit writes so the shadow behaves like the core MMIO register.
     */
    if (offset >= PHASE6CH_APU_ISTS &&
        offset + width <= PHASE6CH_APU_ISTS + 4u)
    {
        uint32_t index = PHASE6CH_APU_ISTS >> 2;
        uint32_t shift = (offset - PHASE6CH_APU_ISTS) * 8u;
        uint32_t mask =
            width == 4u ? 0xFFFFFFFFu :
            width == 2u ? 0x0000FFFFu :
                          0x000000FFu;
        s_phase6chApuRegs[index] &= ~((value & mask) << shift);
        return;
    }

    for (i = 0u; i < width; ++i)
        phase6ch_apu_shadow_write_byte(
            offset + i,
            (uint8_t)((value >> (i * 8u)) & 0xFFu));

    /*
     * xemu's core model mirrors FEMEMDATA to guest physical FEMEMADDR.
     * Preserve that documented side effect only for an exact dword write and
     * only when the destination is ordinary guest RAM. Anything else remains
     * observable through the checked GUEST_WRITE32 path.
     */
    if (offset == PHASE6CH_APU_FEMEMDATA && width == 4u)
    {
        uint32_t guestAddress =
            s_phase6chApuRegs[PHASE6CH_APU_FEMEMADDR >> 2];
        if (guestAddress < RAM_SIZE &&
            guestAddress <= RAM_SIZE - 4u)
            GUEST_WRITE32(guestAddress, value);
        else
            GUEST_WRITE32(guestAddress, value);
    }
}

static void phase6ch_apu_log(
    const char* op,
    uint32_t address,
    uint32_t value,
    uint32_t count)
{
    char line[256];
    if (count > 64u && (count & 0xFFFu) != 0u)
        return;

    sprintf(
        line,
        "P6CH APU %s addr=%08X offset=%05X value=%08X count=%u",
        op,
        (unsigned int)address,
        (unsigned int)(address - PHASE6CH_APU_BASE),
        (unsigned int)value,
        (unsigned int)count);
    trace(line);
}

static uint8_t phase6ch_apu_read8(uint32_t address)
{
    uint32_t offset;
    uint32_t value;

    if (!phase6ch_apu_core_range(address, 1u, &offset))
        return GUEST_READ8(address);

    value = phase6ch_apu_shadow_read(address, 1u);
    ++s_phase6chApuRead8Count;
    s_phase6chApuLastAddress = address;
    s_phase6chApuLastValue = value;
    phase6ch_apu_log(
        "READ8", address, value, s_phase6chApuRead8Count);
    return (uint8_t)value;
}

static uint16_t phase6ch_apu_read16(uint32_t address)
{
    uint32_t offset;
    uint32_t value;

    if (!phase6ch_apu_core_range(address, 2u, &offset))
        return GUEST_READ16(address);

    value = phase6ch_apu_shadow_read(address, 2u);
    ++s_phase6chApuRead16Count;
    s_phase6chApuLastAddress = address;
    s_phase6chApuLastValue = value;
    phase6ch_apu_log(
        "READ16", address, value, s_phase6chApuRead16Count);
    return (uint16_t)value;
}

static uint32_t phase6ch_apu_read32(uint32_t address)
{
    uint32_t offset;
    uint32_t value;

    if (!phase6ch_apu_core_range(address, 4u, &offset))
        return GUEST_READ32(address);

    value = phase6ch_apu_shadow_read(address, 4u);
    ++s_phase6chApuRead32Count;
    s_phase6chApuLastAddress = address;
    s_phase6chApuLastValue = value;
    phase6ch_apu_log(
        "READ32", address, value, s_phase6chApuRead32Count);
    return value;
}

static void phase6ch_apu_write8(uint32_t address, uint8_t value)
{
    uint32_t offset;
    if (!phase6ch_apu_core_range(address, 1u, &offset))
    {
        GUEST_WRITE8(address, value);
        return;
    }

    phase6ch_apu_shadow_write(address, 1u, (uint32_t)value);
    ++s_phase6chApuWrite8Count;
    s_phase6chApuLastAddress = address;
    s_phase6chApuLastValue = value;
    phase6ch_apu_log(
        "WRITE8", address, value, s_phase6chApuWrite8Count);
}

static void phase6ch_apu_write16(uint32_t address, uint16_t value)
{
    uint32_t offset;
    if (!phase6ch_apu_core_range(address, 2u, &offset))
    {
        GUEST_WRITE16(address, value);
        return;
    }

    phase6ch_apu_shadow_write(address, 2u, (uint32_t)value);
    ++s_phase6chApuWrite16Count;
    s_phase6chApuLastAddress = address;
    s_phase6chApuLastValue = value;
    phase6ch_apu_log(
        "WRITE16", address, value, s_phase6chApuWrite16Count);
}

static void phase6ch_apu_write32(uint32_t address, uint32_t value)
{
    uint32_t offset;
    if (!phase6ch_apu_core_range(address, 4u, &offset))
    {
        GUEST_WRITE32(address, value);
        return;
    }

    phase6ch_apu_shadow_write(address, 4u, value);
    ++s_phase6chApuWrite32Count;
    s_phase6chApuLastAddress = address;
    s_phase6chApuLastValue = value;
    phase6ch_apu_log(
        "WRITE32", address, value, s_phase6chApuWrite32Count);
}

'''
    return text.replace(anchor, support + anchor, 1)


def patch_dsound_functions(text: str, base) -> tuple[str, dict]:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6CH] optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6CH] optimize-on marker missing")

    body = text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    replacements = []
    patched_functions = []
    site_counts = {
        "read8": 0,
        "read16": 0,
        "read32": 0,
        "write8": 0,
        "write16": 0,
        "write32": 0,
    }
    fault_owner = None

    macros = (
        ("GUEST_READ8(", "phase6ch_apu_read8(", "read8"),
        ("GUEST_READ16(", "phase6ch_apu_read16(", "read16"),
        ("GUEST_READ32(", "phase6ch_apu_read32(", "read32"),
        ("GUEST_WRITE8(", "phase6ch_apu_write8(", "write8"),
        ("GUEST_WRITE16(", "phase6ch_apu_write16(", "write16"),
        ("GUEST_WRITE32(", "phase6ch_apu_write32(", "write32"),
    )

    for match in matches:
        name = match.group(1)
        m = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
        if not m:
            continue
        va = int(m.group(1), 16)
        if not (DSOUND_START <= va < DSOUND_END):
            continue

        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit(f"[Phase6CH] opening brace missing for {name}")
        end = base.closing_brace(masked, open_index)
        source = body[match.start():end]

        if f"0x{FAULT_VA:08X}u" in source:
            fault_owner = {
                "name": name,
                "start": va,
                "has_read8": source.count("GUEST_READ8(") > 0,
            }

        changed = source
        local_sites = 0
        for old, new, key in macros:
            n = changed.count(old)
            if n:
                changed = changed.replace(old, new)
                site_counts[key] += n
                local_sites += n

        if local_sites:
            patched_functions.append({
                "name": name,
                "address": va,
                "sites": local_sites,
            })
            replacements.append((match.start(), end, changed))

    if fault_owner is None:
        raise SystemExit(
            f"[Phase6CH] could not find translated owner of fault VA 0x{FAULT_VA:08X}"
        )
    if not fault_owner["has_read8"]:
        raise SystemExit(
            f"[Phase6CH] fault owner {fault_owner['name']} has no GUEST_READ8 site"
        )

    for start, end, changed in reversed(replacements):
        body = body[:start] + changed + body[end:]

    patched = text[:body_start] + body + text[on_pos:]
    if "phase6ch_apu_read8(" not in patched:
        raise SystemExit("[Phase6CH] no DSOUND READ8 sites were routed")

    return patched, {
        "patched_functions": patched_functions,
        "site_counts": site_counts,
        "fault_owner": fault_owner,
    }


def instrument_fault_owner(text: str, base, owner_name: str) -> str:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = text.find(off_marker)
    body_start = off_pos + len(off_marker)
    on_pos = text.find(on_marker, body_start)
    body = text[body_start:on_pos]
    masked = base.mask_noncode(body)

    for match in base.FUNC_RE.finditer(masked):
        if match.group(1) != owner_name:
            continue
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            break
        insert = r'''
    ++s_phase6chApuFaultOwnerEntries;
    if (s_phase6chApuFaultOwnerEntries == 1u)
        trace("PASS: Phase 6CH entered DSOUND owner of FE801100 APU access");
'''
        body = body[:open_index + 1] + insert + body[open_index + 1:]
        return text[:body_start] + body + text[on_pos:]

    raise SystemExit(
        f"[Phase6CH] could not instrument fault owner {owner_name}"
    )


def insert_summary(text: str) -> str:
    marker = "P6CG KFRAISEIRQL160:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CH] inherited 6CG IRQL summary missing")

    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 6000:
        raise SystemExit("[Phase6CH] could not locate summary insertion point")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CH APU CORE: owner_entries=%u r8=%u r16=%u r32=%u w8=%u w16=%u w32=%u last_addr=%08X last_value=%08X fectl=%08X sectl=%08X ists=%08X ien=%08X",\n'
        f'{indent}    (unsigned int)s_phase6chApuFaultOwnerEntries,\n'
        f'{indent}    (unsigned int)s_phase6chApuRead8Count,\n'
        f'{indent}    (unsigned int)s_phase6chApuRead16Count,\n'
        f'{indent}    (unsigned int)s_phase6chApuRead32Count,\n'
        f'{indent}    (unsigned int)s_phase6chApuWrite8Count,\n'
        f'{indent}    (unsigned int)s_phase6chApuWrite16Count,\n'
        f'{indent}    (unsigned int)s_phase6chApuWrite32Count,\n'
        f'{indent}    (unsigned int)s_phase6chApuLastAddress,\n'
        f'{indent}    (unsigned int)s_phase6chApuLastValue,\n'
        f'{indent}    (unsigned int)s_phase6chApuRegs[PHASE6CH_APU_FECTL >> 2],\n'
        f'{indent}    (unsigned int)s_phase6chApuRegs[PHASE6CH_APU_SECTL >> 2],\n'
        f'{indent}    (unsigned int)s_phase6chApuRegs[PHASE6CH_APU_ISTS >> 2],\n'
        f'{indent}    (unsigned int)s_phase6chApuRegs[0x00001004u >> 2]);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CG", "PHASE 6CH")
        .replace("Phase 6CG", "Phase 6CH")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CH] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6ch_base")
    p6bl = load(args.phase6bl_emitter, "phase6ch_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cg-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CH] missing cached 6CG input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CG" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CH] cached Phase 6CG identity mismatch")

    cg = manifest.get("phase6cg_kf_raise_irql", {})
    if (
        cg.get("execution_budget_inherited") != 32000000
        or cg.get("translated_membership_changed") is not False
        or cg.get("hard_fences_changed") is not False
    ):
        raise SystemExit("[Phase6CH] inherited 6CG policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "P6CG KFRAISEIRQL160:",
        "P6CG EXPOOL:",
        "case 0x0027DB5Cu:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CH] inherited 6CG marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = install_support(main_text)
    main_text, patch_info = patch_dsound_functions(main_text, base)
    owner_name = patch_info["fault_owner"]["name"]
    main_text = instrument_fault_owner(main_text, base, owner_name)
    main_text = insert_summary(main_text)

    old_policy = (
        "Policy: Phase 6CG continues the hardware-proven 6CF audio/XACT path through "
        "ordinal 160 KfRaiseIrql using the maintained guest-only IRQL model; preserve "
        "the executive pool family, XACTENG membership, 32M watchdog, quiet logging, "
        "manual PblMath, graphics/file/IDEX semantics and every genuine hard fence"
    )
    new_policy = (
        "Policy: Phase 6CH continues hardware-proven DSOUND startup through the first "
        "MCPX APU core MMIO access FE801100 using a reset-zero shadow of the documented "
        "core register window scoped only to translated DSOUND functions; preserve "
        "32M watchdog, guest-only IRQL, executive pool, XACTENG, graphics/file/IDEX "
        "semantics and fence all non-core APU/MMIO regions"
    )
    main_text = replace_once(main_text, old_policy, new_policy, "runtime policy")
    main_text = replace_once(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = (
        main_text.replace("PHASE 6CG", "PHASE 6CH")
        .replace("Phase 6CG", "Phase 6CH")
        .replace('"P6CG ', '"P6CH ')
    )
    env_text = patch_env(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "PHASE6CH_APU_BASE      0xFE800000u",
        "PHASE6CH_APU_CORE_SIZE 0x00020000u",
        "phase6ch_apu_read8(",
        "phase6ch_apu_write32(",
        "PASS: Phase 6CH entered DSOUND owner of FE801100 APU access",
        "P6CH APU CORE:",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "P6CH KFRAISEIRQL160:",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6CH] generated source lost marker: {marker}")

    state_pos = main_text.find("static uint32_t s_phase6chApuRegs[0x8000];")
    summary_pos = main_text.find("P6CH APU CORE:")
    helper_pos = main_text.find("static uint8_t phase6ch_apu_read8(")
    optimize_pos = main_text.find('#pragma optimize("", off)')
    if min(state_pos, summary_pos, helper_pos, optimize_pos) < 0:
        raise SystemExit("[Phase6CH] declaration-order proof marker missing")
    if not (
        state_pos < summary_pos and
        state_pos < helper_pos < optimize_pos
    ):
        raise SystemExit("[Phase6CH] APU state/helper declaration-order proof failed")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "6CH"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6ch_apu_core_mmio"] = {
        "source_phase": "6CG",
        "phase6cg_hardware": {
            "boundary_kind": "GUEST_FAULT",
            "target": "0xFE801100",
            "access": "READ8",
            "caller_trace": "0x0023A3CE",
            "esp": "0x008BF878",
            "saved_esp": "0x008BF878",
            "ticks": 26711305,
            "trace": 1017529,
            "fault": 1,
            "prior_kf_raise_irql_pass": True,
            "guest_irql_after_raise": 2,
        },
        "register_identity": {
            "base": "0xFE800000",
            "offset": "0x00001100",
            "name": "NV_PAPU_FECTL",
            "source_basis": "xemu MCPX APU register model",
        },
        "model": {
            "core_base": "0xFE800000",
            "core_size": "0x00020000",
            "reset_value": 0,
            "storage": "32-bit little-endian shadow register array",
            "ists_write_semantics": "write-one-to-clear",
            "fectl_sectl_semantics": "stored controls",
            "fememdata_semantics": "exact dword write mirrors to guest FEMEMADDR",
            "xgscnt_semantics": "bootstrap zero; no APU worker claimed",
            "actual_audio_processing": False,
            "apu_irq_delivery": False,
        },
        "scope": {
            "xbox_section": "DSOUND",
            "section_start": f"0x{DSOUND_START:08X}",
            "section_end": f"0x{DSOUND_END:08X}",
            "fault_va": f"0x{FAULT_VA:08X}",
            "fault_owner": patch_info["fault_owner"],
            "patched_function_count": len(patch_info["patched_functions"]),
            "site_counts": patch_info["site_counts"],
        },
        "patched_functions": [
            {
                "name": row["name"],
                "address": f"0x{row['address']:08X}",
                "sites": row["sites"],
            }
            for row in patch_info["patched_functions"]
        ],
        "translated_membership_changed": False,
        "xacteng_membership_changed": False,
        "executive_pool_semantics_changed": False,
        "guest_irql_semantics_changed": False,
        "execution_budget_inherited": 32000000,
        "dispatch_log_stride_inherited": 4096,
        "non_apu_mmio_fences_changed": False,
        "non_core_apu_mmio_fenced": True,
        "source_layout": layout,
    }

    (args.out_dir / "phase6ch-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    sites = patch_info["site_counts"]
    print(
        f"[Phase6CH] 6CG hardware: READ8 FE801100 after KfRaiseIrql PASS; "
        f"tick=26,711,305"
    )
    print(
        f"[Phase6CH] fault owner: {owner_name} "
        f"start=0x{patch_info['fault_owner']['start']:08X}"
    )
    print(
        f"[Phase6CH] DSOUND APU routing: functions={len(patch_info['patched_functions'])} "
        f"r8={sites['read8']} r16={sites['read16']} r32={sites['read32']} "
        f"w8={sites['write8']} w16={sites['write16']} w32={sites['write32']}"
    )
    print("[Phase6CH] APU core window: FE800000-FE81FFFF, reset-zero shadow")
    print("[Phase6CH] NV_PAPU_ISTS write-one-to-clear semantics armed")
    print("[Phase6CH] non-core APU and all other MMIO remain fenced")
    print("[Phase6CH] no host audio/mixer/DSP/IRQ behavior claimed")
    print("[Phase6CH] execution budget: inherited 32,000,000 ticks")
    print("[Phase6CH] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

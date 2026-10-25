#!/usr/bin/env python3
"""Phase 6CI: MCPX GP/EP DSP bootstrap shadows for translated DSOUND.

6CH hardware proved the main APU core register model and advanced through
FECTL/SECTL/interrupt/voice-list initialization. The next hard boundary was:
  WRITE32 FE83FFFC
  boundary=GUEST_FAULT ticks=26,711,365 fault=1

FE83FFFC is APU base + 0x30000 (GP region) + 0xFFFC
(NV_PAPU_GPRST). The retail Mercenaries APU model and xemu both expose paired
64 KiB GP/EP DSP windows at offsets 0x30000 and 0x50000.

6CI preserves GP/EP register and DSP-memory writes/readbacks as 24-bit words,
including reset/run transition bookkeeping. It deliberately does NOT execute
DSP microcode yet. VP (0x20000-0x2FFFF), the 0x40000 gap, and every other MMIO
region remain fenced.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CH-APU-CORE-MMIO-20261025-A"
BUILD_TAG = "P6CI-APU-GPEP-DSP-20261025-A"
COOKIE_OLD = "phase6ch_env_build_cookie"
COOKIE_NEW = "phase6ci_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CI] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CI] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def install_state(text: str) -> str:
    anchor = "static uint32_t s_phase6chApuFaultOwnerEntries = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CI] expected one 6CH APU state anchor, found {text.count(anchor)}"
        )
    state = """static uint32_t s_phase6ciGpDsp[0x4000];
static uint32_t s_phase6ciEpDsp[0x4000];
static uint32_t s_phase6ciGpReadCount = 0u;
static uint32_t s_phase6ciGpWriteCount = 0u;
static uint32_t s_phase6ciEpReadCount = 0u;
static uint32_t s_phase6ciEpWriteCount = 0u;
static uint32_t s_phase6ciGpResetCount = 0u;
static uint32_t s_phase6ciGpBootstrapCount = 0u;
static uint32_t s_phase6ciEpResetCount = 0u;
static uint32_t s_phase6ciEpBootstrapCount = 0u;
static uint32_t s_phase6ciDspLastAddress = 0u;
static uint32_t s_phase6ciDspLastValue = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def install_dsp_support(text: str) -> str:
    anchor = "static uint8_t phase6ch_apu_read8(uint32_t address)\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CI] expected one 6CH APU read8 anchor, found {text.count(anchor)}"
        )

    support = r'''#define PHASE6CI_APU_GP_BASE  0xFE830000u
#define PHASE6CI_APU_EP_BASE  0xFE850000u
#define PHASE6CI_DSP_SIZE     0x00010000u
#define PHASE6CI_DSP_RST      0x0000FFFCu
#define PHASE6CI_DSP_RUN_MASK 0x00000003u

static int phase6ci_dsp_range(
    uint32_t address,
    uint32_t width,
    uint32_t* outProcessor,
    uint32_t* outOffset)
{
    uint32_t base = 0u;
    uint32_t processor = 0u;

    if (width == 0u || width > 4u)
        return 0;

    if (address >= PHASE6CI_APU_GP_BASE &&
        address < PHASE6CI_APU_GP_BASE + PHASE6CI_DSP_SIZE)
    {
        base = PHASE6CI_APU_GP_BASE;
        processor = 1u;
    }
    else if (address >= PHASE6CI_APU_EP_BASE &&
             address < PHASE6CI_APU_EP_BASE + PHASE6CI_DSP_SIZE)
    {
        base = PHASE6CI_APU_EP_BASE;
        processor = 2u;
    }
    else
    {
        return 0;
    }

    if (width > PHASE6CI_DSP_SIZE - (address - base))
        return 0;

    if (outProcessor)
        *outProcessor = processor;
    if (outOffset)
        *outOffset = address - base;
    return 1;
}

static uint32_t* phase6ci_dsp_words(uint32_t processor)
{
    return processor == 1u ? s_phase6ciGpDsp : s_phase6ciEpDsp;
}

static uint8_t phase6ci_dsp_read_byte(
    uint32_t processor,
    uint32_t offset)
{
    uint32_t* words = phase6ci_dsp_words(processor);
    uint32_t word = words[(offset & ~3u) >> 2] & 0x00FFFFFFu;
    return (uint8_t)((word >> ((offset & 3u) * 8u)) & 0xFFu);
}

static uint32_t phase6ci_dsp_read(
    uint32_t processor,
    uint32_t offset,
    uint32_t width)
{
    uint32_t value = 0u;
    uint32_t i;
    for (i = 0u; i < width; ++i)
        value |=
            ((uint32_t)phase6ci_dsp_read_byte(processor, offset + i)) <<
            (i * 8u);
    return value;
}

static void phase6ci_dsp_note_reset_transition(
    uint32_t processor,
    uint32_t oldValue,
    uint32_t newValue)
{
    int oldRunning =
        (oldValue & PHASE6CI_DSP_RUN_MASK) == PHASE6CI_DSP_RUN_MASK;
    int newRunning =
        (newValue & PHASE6CI_DSP_RUN_MASK) == PHASE6CI_DSP_RUN_MASK;

    if (!newRunning)
    {
        if (processor == 1u)
            ++s_phase6ciGpResetCount;
        else
            ++s_phase6ciEpResetCount;
    }
    else if (!oldRunning)
    {
        if (processor == 1u)
            ++s_phase6ciGpBootstrapCount;
        else
            ++s_phase6ciEpBootstrapCount;
    }
}

static void phase6ci_dsp_write(
    uint32_t processor,
    uint32_t offset,
    uint32_t width,
    uint32_t value)
{
    uint32_t* words = phase6ci_dsp_words(processor);
    uint32_t resetIndex = PHASE6CI_DSP_RST >> 2;
    uint32_t oldReset = words[resetIndex] & 0x00FFFFFFu;
    uint32_t i;

    /*
     * Retail MCPX DSP words are 24-bit. Merge byte lanes so 8/16/32-bit guest
     * accesses retain the same little-endian behavior as the maintained APU
     * MMIO dispatcher, then clip each touched word to 24 bits.
     */
    for (i = 0u; i < width; ++i)
    {
        uint32_t byteOffset = offset + i;
        uint32_t index = (byteOffset & ~3u) >> 2;
        uint32_t shift = (byteOffset & 3u) * 8u;
        uint32_t mask = 0xFFu << shift;
        uint32_t word = words[index];
        word = (word & ~mask) |
            (((value >> (i * 8u)) & 0xFFu) << shift);
        words[index] = word & 0x00FFFFFFu;
    }

    if (offset <= PHASE6CI_DSP_RST &&
        offset + width > PHASE6CI_DSP_RST)
    {
        uint32_t newReset = words[resetIndex] & 0x00FFFFFFu;
        phase6ci_dsp_note_reset_transition(
            processor, oldReset, newReset);
    }
}

static void phase6ci_dsp_log(
    const char* op,
    uint32_t processor,
    uint32_t address,
    uint32_t value,
    uint32_t count)
{
    char line[256];
    const char* name = processor == 1u ? "GP" : "EP";

    if (count > 64u && (count & 0xFFFu) != 0u)
        return;

    sprintf(
        line,
        "P6CI APU %s %s addr=%08X offset=%04X value=%08X count=%u",
        name,
        op,
        (unsigned int)address,
        (unsigned int)(
            address - (processor == 1u
                ? PHASE6CI_APU_GP_BASE
                : PHASE6CI_APU_EP_BASE)),
        (unsigned int)value,
        (unsigned int)count);
    trace(line);
}

'''
    return text.replace(anchor, support + anchor, 1)


def replace_access_helpers(text: str) -> str:
    old = r'''static uint8_t phase6ch_apu_read8(uint32_t address)
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

    new = r'''static uint8_t phase6ch_apu_read8(uint32_t address)
{
    uint32_t offset;
    uint32_t processor;
    uint32_t value;

    if (phase6ch_apu_core_range(address, 1u, &offset))
    {
        value = phase6ch_apu_shadow_read(address, 1u);
        ++s_phase6chApuRead8Count;
        s_phase6chApuLastAddress = address;
        s_phase6chApuLastValue = value;
        phase6ch_apu_log(
            "READ8", address, value, s_phase6chApuRead8Count);
        return (uint8_t)value;
    }

    if (phase6ci_dsp_range(address, 1u, &processor, &offset))
    {
        value = phase6ci_dsp_read(processor, offset, 1u);
        if (processor == 1u)
            ++s_phase6ciGpReadCount;
        else
            ++s_phase6ciEpReadCount;
        s_phase6ciDspLastAddress = address;
        s_phase6ciDspLastValue = value;
        phase6ci_dsp_log(
            "READ8", processor, address, value,
            processor == 1u ? s_phase6ciGpReadCount : s_phase6ciEpReadCount);
        return (uint8_t)value;
    }

    return GUEST_READ8(address);
}

static uint16_t phase6ch_apu_read16(uint32_t address)
{
    uint32_t offset;
    uint32_t processor;
    uint32_t value;

    if (phase6ch_apu_core_range(address, 2u, &offset))
    {
        value = phase6ch_apu_shadow_read(address, 2u);
        ++s_phase6chApuRead16Count;
        s_phase6chApuLastAddress = address;
        s_phase6chApuLastValue = value;
        phase6ch_apu_log(
            "READ16", address, value, s_phase6chApuRead16Count);
        return (uint16_t)value;
    }

    if (phase6ci_dsp_range(address, 2u, &processor, &offset))
    {
        value = phase6ci_dsp_read(processor, offset, 2u);
        if (processor == 1u)
            ++s_phase6ciGpReadCount;
        else
            ++s_phase6ciEpReadCount;
        s_phase6ciDspLastAddress = address;
        s_phase6ciDspLastValue = value;
        phase6ci_dsp_log(
            "READ16", processor, address, value,
            processor == 1u ? s_phase6ciGpReadCount : s_phase6ciEpReadCount);
        return (uint16_t)value;
    }

    return GUEST_READ16(address);
}

static uint32_t phase6ch_apu_read32(uint32_t address)
{
    uint32_t offset;
    uint32_t processor;
    uint32_t value;

    if (phase6ch_apu_core_range(address, 4u, &offset))
    {
        value = phase6ch_apu_shadow_read(address, 4u);
        ++s_phase6chApuRead32Count;
        s_phase6chApuLastAddress = address;
        s_phase6chApuLastValue = value;
        phase6ch_apu_log(
            "READ32", address, value, s_phase6chApuRead32Count);
        return value;
    }

    if (phase6ci_dsp_range(address, 4u, &processor, &offset))
    {
        value = phase6ci_dsp_read(processor, offset, 4u);
        if (processor == 1u)
            ++s_phase6ciGpReadCount;
        else
            ++s_phase6ciEpReadCount;
        s_phase6ciDspLastAddress = address;
        s_phase6ciDspLastValue = value;
        phase6ci_dsp_log(
            "READ32", processor, address, value,
            processor == 1u ? s_phase6ciGpReadCount : s_phase6ciEpReadCount);
        return value;
    }

    return GUEST_READ32(address);
}

static void phase6ch_apu_write8(uint32_t address, uint8_t value)
{
    uint32_t offset;
    uint32_t processor;

    if (phase6ch_apu_core_range(address, 1u, &offset))
    {
        phase6ch_apu_shadow_write(address, 1u, (uint32_t)value);
        ++s_phase6chApuWrite8Count;
        s_phase6chApuLastAddress = address;
        s_phase6chApuLastValue = value;
        phase6ch_apu_log(
            "WRITE8", address, value, s_phase6chApuWrite8Count);
        return;
    }

    if (phase6ci_dsp_range(address, 1u, &processor, &offset))
    {
        phase6ci_dsp_write(processor, offset, 1u, (uint32_t)value);
        if (processor == 1u)
            ++s_phase6ciGpWriteCount;
        else
            ++s_phase6ciEpWriteCount;
        s_phase6ciDspLastAddress = address;
        s_phase6ciDspLastValue = value;
        phase6ci_dsp_log(
            "WRITE8", processor, address, value,
            processor == 1u ? s_phase6ciGpWriteCount : s_phase6ciEpWriteCount);
        return;
    }

    GUEST_WRITE8(address, value);
}

static void phase6ch_apu_write16(uint32_t address, uint16_t value)
{
    uint32_t offset;
    uint32_t processor;

    if (phase6ch_apu_core_range(address, 2u, &offset))
    {
        phase6ch_apu_shadow_write(address, 2u, (uint32_t)value);
        ++s_phase6chApuWrite16Count;
        s_phase6chApuLastAddress = address;
        s_phase6chApuLastValue = value;
        phase6ch_apu_log(
            "WRITE16", address, value, s_phase6chApuWrite16Count);
        return;
    }

    if (phase6ci_dsp_range(address, 2u, &processor, &offset))
    {
        phase6ci_dsp_write(processor, offset, 2u, (uint32_t)value);
        if (processor == 1u)
            ++s_phase6ciGpWriteCount;
        else
            ++s_phase6ciEpWriteCount;
        s_phase6ciDspLastAddress = address;
        s_phase6ciDspLastValue = value;
        phase6ci_dsp_log(
            "WRITE16", processor, address, value,
            processor == 1u ? s_phase6ciGpWriteCount : s_phase6ciEpWriteCount);
        return;
    }

    GUEST_WRITE16(address, value);
}

static void phase6ch_apu_write32(uint32_t address, uint32_t value)
{
    uint32_t offset;
    uint32_t processor;

    if (phase6ch_apu_core_range(address, 4u, &offset))
    {
        phase6ch_apu_shadow_write(address, 4u, value);
        ++s_phase6chApuWrite32Count;
        s_phase6chApuLastAddress = address;
        s_phase6chApuLastValue = value;
        phase6ch_apu_log(
            "WRITE32", address, value, s_phase6chApuWrite32Count);
        return;
    }

    if (phase6ci_dsp_range(address, 4u, &processor, &offset))
    {
        phase6ci_dsp_write(processor, offset, 4u, value);
        if (processor == 1u)
            ++s_phase6ciGpWriteCount;
        else
            ++s_phase6ciEpWriteCount;
        s_phase6ciDspLastAddress = address;
        s_phase6ciDspLastValue = value;
        phase6ci_dsp_log(
            "WRITE32", processor, address, value,
            processor == 1u ? s_phase6ciGpWriteCount : s_phase6ciEpWriteCount);
        return;
    }

    GUEST_WRITE32(address, value);
}
'''
    return replace_once(text, old, new, "6CH APU access helper family")


def insert_summary(text: str) -> str:
    marker = "P6CH APU CORE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CI] inherited 6CH APU summary missing")

    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 7000:
        raise SystemExit("[Phase6CI] could not locate APU summary insertion point")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CI APU DSP: gp_r=%u gp_w=%u gp_reset=%u gp_boot=%u gp_rst=%08X ep_r=%u ep_w=%u ep_reset=%u ep_boot=%u ep_rst=%08X last_addr=%08X last_value=%08X",\n'
        f'{indent}    (unsigned int)s_phase6ciGpReadCount,\n'
        f'{indent}    (unsigned int)s_phase6ciGpWriteCount,\n'
        f'{indent}    (unsigned int)s_phase6ciGpResetCount,\n'
        f'{indent}    (unsigned int)s_phase6ciGpBootstrapCount,\n'
        f'{indent}    (unsigned int)s_phase6ciGpDsp[PHASE6CI_DSP_RST >> 2],\n'
        f'{indent}    (unsigned int)s_phase6ciEpReadCount,\n'
        f'{indent}    (unsigned int)s_phase6ciEpWriteCount,\n'
        f'{indent}    (unsigned int)s_phase6ciEpResetCount,\n'
        f'{indent}    (unsigned int)s_phase6ciEpBootstrapCount,\n'
        f'{indent}    (unsigned int)s_phase6ciEpDsp[PHASE6CI_DSP_RST >> 2],\n'
        f'{indent}    (unsigned int)s_phase6ciDspLastAddress,\n'
        f'{indent}    (unsigned int)s_phase6ciDspLastValue);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CH", "PHASE 6CI")
        .replace("Phase 6CH", "Phase 6CI")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CI] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6ci_base")
    p6bl = load(args.phase6bl_emitter, "phase6ci_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6ch-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CI] missing cached 6CH input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CH" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CI] cached Phase 6CH identity mismatch")

    ch = manifest.get("phase6ch_apu_core_mmio", {})
    if (
        ch.get("execution_budget_inherited") != 32000000
        or ch.get("translated_membership_changed") is not False
        or ch.get("non_core_apu_mmio_fenced") is not True
    ):
        raise SystemExit("[Phase6CI] inherited 6CH policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "P6CH APU CORE:",
        "phase6ch_apu_read32(",
        "phase6ch_apu_write32(",
        "P6CH KFRAISEIRQL160:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CI] inherited 6CH marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = install_dsp_support(main_text)
    main_text = replace_access_helpers(main_text)
    main_text = insert_summary(main_text)

    old_policy = (
        "Policy: Phase 6CH continues hardware-proven DSOUND startup through the first "
        "MCPX APU core MMIO access FE801100 using a reset-zero shadow of the documented "
        "core register window scoped only to translated DSOUND functions; preserve "
        "32M watchdog, guest-only IRQL, executive pool, XACTENG, graphics/file/IDEX "
        "semantics and fence all non-core APU/MMIO regions"
    )
    new_policy = (
        "Policy: Phase 6CI continues hardware-proven DSOUND startup through GP DSP "
        "reset FE83FFFC using paired reset-zero 64KiB GP/EP 24-bit DSP shadows; retain "
        "the 6CH APU core model, preserve 32M watchdog, guest-only IRQL, executive pool, "
        "XACTENG, graphics/file/IDEX semantics, execute no DSP microcode, and keep VP, "
        "the APU gap, and all non-APU MMIO fenced"
    )
    main_text = replace_once(main_text, old_policy, new_policy, "runtime policy")
    main_text = replace_once(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = (
        main_text.replace("PHASE 6CH", "PHASE 6CI")
        .replace("Phase 6CH", "Phase 6CI")
        .replace('"P6CH ', '"P6CI ')
    )
    env_text = patch_env(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "PHASE6CI_APU_GP_BASE  0xFE830000u",
        "PHASE6CI_APU_EP_BASE  0xFE850000u",
        "PHASE6CI_DSP_RST      0x0000FFFCu",
        "phase6ci_dsp_range(",
        "phase6ci_dsp_write(",
        "P6CI APU DSP:",
        "P6CI APU CORE:",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6CI] generated source lost marker: {marker}")

    if "PHASE6CI_APU_GP_BASE  0xFE830000u" not in main_text:
        raise SystemExit("[Phase6CI] GP base proof failed")
    if "PHASE6CI_APU_EP_BASE  0xFE850000u" not in main_text:
        raise SystemExit("[Phase6CI] EP base proof failed")

    state_pos = main_text.find("static uint32_t s_phase6ciGpDsp[0x4000];")
    helper_pos = main_text.find("static int phase6ci_dsp_range(")
    read_pos = main_text.find("static uint8_t phase6ch_apu_read8(")
    optimize_pos = main_text.find('#pragma optimize("", off)')
    summary_pos = main_text.find("P6CI APU DSP:")
    if min(state_pos, helper_pos, read_pos, optimize_pos, summary_pos) < 0:
        raise SystemExit("[Phase6CI] declaration-order marker missing")
    if not (
        state_pos < summary_pos and
        state_pos < helper_pos < read_pos < optimize_pos
    ):
        raise SystemExit("[Phase6CI] DSP declaration-order proof failed")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "6CI"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6ci_apu_gp_ep_dsp"] = {
        "source_phase": "6CH",
        "phase6ch_hardware": {
            "boundary_kind": "GUEST_FAULT",
            "target": "0xFE83FFFC",
            "access": "WRITE32",
            "caller_trace": "0x0023A3CE",
            "esp": "0x008BF8A0",
            "saved_esp": "0x008BF8A0",
            "ticks": 26711365,
            "trace": 1017542,
            "fault": 1,
            "apu_core_transactions_before_fault": {
                "read8": 1,
                "read16": 0,
                "read32": 5,
                "write8": 0,
                "write16": 0,
                "write32": 13,
            },
            "fectl": "0x00000080",
            "sectl": "0x00000000",
            "ists": "0x00000000",
            "ien": "0x00000000",
        },
        "register_identity": {
            "address": "0xFE83FFFC",
            "apu_offset": "0x0003FFFC",
            "processor": "GP",
            "processor_offset": "0x0000FFFC",
            "name": "NV_PAPU_GPRST",
        },
        "model": {
            "gp_base": "0xFE830000",
            "ep_base": "0xFE850000",
            "window_size": "0x00010000",
            "word_width_bits": 24,
            "reset_register_offset": "0x0000FFFC",
            "run_mask": "0x00000003",
            "reset_semantics": "track reset when either run bit is clear",
            "bootstrap_semantics": "track stopped-to-running transition when both run bits become set",
            "memory_and_register_readback": True,
            "actual_dsp_microcode_execution": False,
            "actual_audio_processing": False,
        },
        "scope": {
            "routing": "existing 6CH translated-DSOUND APU access wrappers",
            "vp_region_fenced": "0xFE820000-0xFE82FFFF",
            "apu_gap_fenced": "0xFE840000-0xFE84FFFF",
            "other_apu_regions_fenced": True,
            "non_apu_mmio_fenced": True,
        },
        "translated_membership_changed": False,
        "apu_core_semantics_changed": False,
        "guest_irql_semantics_changed": False,
        "xacteng_membership_changed": False,
        "execution_budget_inherited": 32000000,
        "dispatch_log_stride_inherited": 4096,
        "source_layout": layout,
    }

    (args.out_dir / "phase6ci-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6CI] 6CH hardware: APU core bootstrap PASS through 19 transactions")
    print("[Phase6CI] next boundary: WRITE32 FE83FFFC at tick 26,711,365")
    print("[Phase6CI] FE83FFFC = GP DSP NV_PAPU_GPRST")
    print("[Phase6CI] GP window FE830000-FE83FFFF: 24-bit shadow armed")
    print("[Phase6CI] EP window FE850000-FE85FFFF: 24-bit shadow armed")
    print("[Phase6CI] reset/bootstrap transition bookkeeping armed")
    print("[Phase6CI] VP FE820000-FE82FFFF and FE840000 gap remain fenced")
    print("[Phase6CI] DSP microcode execution/audio output not yet claimed")
    print("[Phase6CI] execution budget: inherited 32,000,000 ticks")
    print("[Phase6CI] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

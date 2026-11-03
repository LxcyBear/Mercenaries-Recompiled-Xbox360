#!/usr/bin/env python3
"""Source-authentic, fail-closed 0017A0A0 direct-frontier promotion.

Reads user-local original xboxrecomp outputs; never distributes original XBE code.
Uses the existing Phase5BC support-clean pack rewriter (not dummy stubs).
Adds bodies to a new main.cpp; preserves all 64 compiled TrueTUs.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import re
from collections import deque
from pathlib import Path

ROOT = 0x0017A0A0
PARENT = 'P6K1-THREELANE-20261103'
MARK = 'P6K1-TEXT-DIRECT-20261103'
XBE_SHA = 'AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7'
MAX_NEW = 32
MAX_DEPTH = 2
DEF = re.compile(r'(?m)^\s*(?:static\s+)?void\s+sub_([0-9A-Fa-f]{8})\s*\(\s*void\s*\)\s*\{')



# Maintained PC port source, not original game code:
# ports/mercenaries/src/recomp_manual.c defines this checkpoint as a
# PC-specific test capture and optional trace. Its two uint32_t arguments
# are snapshots; it never mutates guest registers or guest RAM. On Xbox 360
# those PC capture/export features do not exist, so preserve a bounded
# observable checkpoint without implementing fake host captures.
PC_CHECKPOINT = 'recomp_main_state_checkpoint'
CALL_SITE = re.compile(
    r'\brecomp_main_state_checkpoint\s*\(\s*'
    r'GUEST_READ32\s*\(\s*esp\s*\+\s*4\s*\)\s*,\s*'
    r'GUEST_READ32\s*\(\s*esp\s*\+\s*8\s*\)\s*\)\s*;'
)
X360_CHECKPOINT = """
/* K1: PC-only Mercenaries capture hook adapted to Xbox 360 telemetry.
 * The maintained recomp_manual.c original uses getenv-driven PC capture
 * and optional fprintf tracing; not an original retail XBE function.
 * No guest register, guest RAM, return, branch, or framebuffer is modified.
 * Original translated call and the following retail GUEST_WRITE32 remain.
 */
static uint32_t s_k1MainCheckpointCalls = 0u;
static uint32_t s_k1MainCheckpointLastState = 0u;
static uint32_t s_k1MainCheckpointLastSubstate = 0u;
static void recomp_main_state_checkpoint(uint32_t state, uint32_t substate)
{
    ++s_k1MainCheckpointCalls;
    if (s_k1MainCheckpointCalls == 1u ||
        state != s_k1MainCheckpointLastState ||
        substate != s_k1MainCheckpointLastSubstate ||
        (s_k1MainCheckpointCalls & 1023u) == 0u)
    {
        char line[192];
        sprintf(line,
            "K1STATE MAIN CHECKPOINT: calls=%u state=%08X substate=%08X",
            (unsigned int)s_k1MainCheckpointCalls,
            (unsigned int)state, (unsigned int)substate);
        trace(line);
    }
    s_k1MainCheckpointLastState = state;
    s_k1MainCheckpointLastSubstate = substate;
}
"""


def verify_pc_checkpoint(manual: str, root_source: str) -> str:
    """Prove this is the PC capture/trace hook, not an Xbox game function."""
    start = manual.find('void recomp_main_state_checkpoint(uint32_t state, uint32_t substate)')
    end = manual.find('void recomp_frontend_shell_loop_checkpoint(', start + 1)
    if start < 0 or end < 0 or manual.count(
        'void recomp_main_state_checkpoint(uint32_t state, uint32_t substate)'
    ) != 1 or end <= start or end - start > 6000:
        raise ValueError("Maintained PC checkpoint source definition missing/changed")
    definition = manual[start:end]
    required = (
        'MERCENARIES_CAPTURE_GAME_PATH',
        'MERCENARIES_CAPTURE_SHELL_PLAY_PATH',
        'MERCENARIES_TRACE_STATE',
        'd3d8_DebugArmFlipCapture(',
        'd3d8_DebugCaptureFrameToPath(',
        'guest_u32(0x00413F6Cu)',
    )
    absent = [marker for marker in required if marker not in definition]
    if absent:
        raise ValueError("PC-only capture checkpoint contract drift: " + ", ".join(absent))
    # A helper that starts writing guest RAM or calling the original game's
    # code can no longer be replaced by purely observational Xbox telemetry.
    if re.search(r'\b(?:GUEST_WRITE\d*|guest_write\w*|recomp_guest_write\w*|MEM_WRITE\w*)\s*\(',
                 definition, re.I):
        raise ValueError("PC checkpoint now writes guest state; manual port audit required")
    if len(CALL_SITE.findall(root_source)) != 1:
        raise ValueError("Original 0017A0A0 checkpoint callsite/argument ABI drift")
    if not re.search(
        r'GUEST_WRITE32\s*\(\s*0x413F6C\s*,\s*eax\s*\)',
        root_source,
    ):
        raise ValueError("Original retail main-state write after checkpoint not found")
    return digest(definition.encode('utf-8'))

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError('Cannot load real source helper: ' + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pick(generated: dict, compiled: set[int], base) -> list[int]:
    if ROOT not in generated:
        raise ValueError('Original translated body 0017A0A0 missing; no stub permitted')
    if ROOT in compiled:
        raise ValueError('0017A0A0 already compiled: audit lookup/linkage instead of duplicate definition')
    names = {row['name']: va for va, row in generated.items()}
    queue = deque([(ROOT, 0)])
    seen = set()
    selected = []
    while queue and len(selected) < MAX_NEW:
        va, depth = queue.popleft()
        if va in seen:
            continue
        seen.add(va)
        if va not in generated:
            continue
        if va not in compiled:
            selected.append(va)
        if depth == MAX_DEPTH:
            continue
        row = generated[va]
        calls = sorted(set(base.CALL_RE.findall(base.mask_noncode(row['source']))))
        for name in calls:
            dep = names.get(name)
            if dep is not None and dep not in seen and dep not in compiled:
                queue.append((dep, depth + 1))
    if ROOT not in selected:
        raise ValueError('Bounded closure lost original retail root')
    return selected


def insert(parent: str, members: list[int], compiled: set[int],
           generated: dict, base, p5bb, p5bc, pc_manual: str):
    if parent.count(PARENT) != 1 or 'K1PFIFO DMA_PUT READ32:' not in parent:
        raise ValueError('Missing unique hardware-proven three-lane parent')
    if MARK in parent or 'case 0x0017A0A0u: return sub_0017A0A0;' in parent:
        raise ValueError('Text-direct patch already present')
    if 'P6DQ ROCKET HARD STOP' not in parent or 'phase4c_lookup_pack_func' not in parent:
        raise ValueError('Original fault/lookup path missing')
    # TrueTU main.cpp deliberately has no monolithic translated-code body.
    # Phase5BC still expects optimize-on to delimit inserted translated
    # functions. Make a *new* isolated region rather than assuming that the
    # old monolithic pragma survived sharding.
    if 'K1_TEXT_HIDDEN_OPT_ON_20261103' in parent:
        raise ValueError('Inherited optimize placeholder already present')
    if '\r' in parent.replace('\r\n', ''):
        raise ValueError('Mixed line endings in generated main')
    checkpoint_digest = verify_pc_checkpoint(pc_manual, generated[ROOT]['source'])
    if "static void recomp_main_state_checkpoint(" in parent or             "K1STATE MAIN CHECKPOINT:" in parent:
        raise ValueError("Already has a main-state checkpoint implementation")
    base.STANDARD_CALLS.update(('sin', 'cos'))
    # Reuse precisely the same support-clean pruning and DIRECT_FRONTIER
    # rewriting machinery that assembled Phase6DQ. No altered return values.
    before_helpers = p5bc.SWEEP_ROOT
    newline = '\r\n' if '\r\n' in parent else '\n'
    normalized = parent.replace('\r\n', '\n')
    # Install the real-ABI port of the verified PC-only diagnostic before
    # Phase5BC's support check and before the new translated callsite.
    # No blanket whitelist: only this exact helper is supplied.
    lookup_marker = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if normalized.count(lookup_marker) != 1:
        raise ValueError("Pack-lookup insertion anchor missing/duplicated")
    normalized = normalized.replace(lookup_marker,
                                    X360_CHECKPOINT + "\n" + lookup_marker, 1)
    # Hide existing optimize-on directives from the Phase5BC first-match
    # insertion finder, then restore them byte-for-byte after injection.
    original_on = '#pragma optimize("", on)'
    placeholder = '/* K1_TEXT_HIDDEN_OPT_ON_20261103 */'
    normalized = normalized.replace(original_on, placeholder)
    normalized += ('\n#pragma optimize("", off)\n'
                   '#pragma optimize("", on)\n')
    # We are promoting a MANDATORY hardware-proven root, unlike the
    # optional candidate sweeps in Phase6DQ. The old 0xFFFFFFFF sentinel
    # silently pruned this root and emitted only 'lost all candidates'.
    # Root-mode reports its actual missing helpers and local source lines.
    p5bc.SWEEP_ROOT = ROOT
    new = list(members)
    print("[K1-TEXT] MANDATORY ROOT: 0017A0A0; original source " +
          str(generated[ROOT].get("file", "<unknown>")) +
          "; candidate functions=" + str(len(new)))
    try:
        result, rendered, frontiers, pruned = p5bc.insert_pack_members(
            normalized, base, p5bb, generated, new, compiled | set(new),
            require_sweep_root=True,
        )
    finally:
        p5bc.SWEEP_ROOT = before_helpers
    result = result.replace(placeholder, original_on)
    if ROOT not in new or ROOT in pruned:
        raise ValueError('0017A0A0 has unresolved support; refusing synthetic continuation: '
                         + ', '.join(pruned.get(ROOT, [])))
    case = 'case 0x0017A0A0u: return ' + generated[ROOT]['name'] + ';'
    if result.count(case) != 1 or ROOT not in rendered:
        raise ValueError('Exact retail target missing from source and pack lookup')
    for va in new:
        case_i = 'case 0x%08Xu: return %s;' % (va, generated[va]['name'])
        if result.count(case_i) != 1:
            raise ValueError('Packed target has missing/duplicated lookup: %08X' % va)
    if not all(x in result for x in ('P6DQ ROCKET HARD STOP', 'K1PFIFO DMA_PUT READ32:')):
        raise ValueError('Guest hard fence or PFIFO trace lost')
    # No modification of translated shards. Rename only the boot marker.
    result = result.replace(PARENT, PARENT + ' | ' + MARK, 1)
    if newline == '\r\n':
        result = result.replace('\n', '\r\n')
    if result.count("K1STATE MAIN CHECKPOINT:") != 1:
        raise ValueError("Checkpoint implementation duplicated or lost")
    if checkpoint_digest is None:
        raise ValueError("PC-only checkpoint proof missing")
    return result, new, sorted(frontiers), pruned


def self_test(base, p5bb, p5bc):
    root_name = 'sub_0017A0A0'
    generated = {ROOT: {'name': root_name,
                        'source': ('void sub_0017A0A0(void)\n{\n'
                                   'loc_0017A0A0: ;\n'
                                   '    recomp_main_state_checkpoint(GUEST_READ32(esp + 4), GUEST_READ32(esp + 8));\n'
                                   '    GUEST_WRITE32(0x413F6C, eax);\n'
                                   '}\n'),
                        'file': 'recomp_test.c'}}
    pc_fixture = (
        'void recomp_main_state_checkpoint(uint32_t state, uint32_t substate)\n'
        '{\n  getenv("MERCENARIES_CAPTURE_GAME_PATH");\n'
        '  getenv("MERCENARIES_CAPTURE_SHELL_PLAY_PATH");\n'
        '  getenv("MERCENARIES_TRACE_STATE");\n'
        '  d3d8_DebugArmFlipCapture("test");\n'
        '  d3d8_DebugCaptureFrameToPath("test");\n'
        '  guest_u32(0x00413F6Cu);\n}\n'
        'void recomp_frontend_shell_loop_checkpoint(void) {}\n'
    )
    p = ('#define PHASE4C_BUDGET_TICK(va) ((void)0)\n'
         '#define GUEST_READ32(addr) ((uint32_t)0)\n'
         '#define GUEST_WRITE32(addr,value) ((void)0)\n'
         'P6K1-THREELANE-20261103\n'
         'K1PFIFO DMA_PUT READ32:\nP6DQ ROCKET HARD STOP\n'
         'static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n'
         '{\n    switch (xbox_va) {\n    default: return (recomp_func_t)0;\n    }\n}\n'
         '#pragma optimize("", on)\n')
    for text in (p, p.replace('\n', '\r\n'),
                 p.replace('#pragma optimize("", on)\n', '')):
        members = pick(generated, set(), base)
        assert members == [ROOT]
        result, retained, frontier, pruned = insert(text, members, set(), generated,
                                                     base, p5bb, p5bc, pc_fixture)
        assert retained == [ROOT] and not pruned and not frontier
        assert result.count('case 0x0017A0A0u: return sub_0017A0A0;') == 1
        assert result.count('PHASE4C_BUDGET_TICK(0x0017A0A0u)') == 1
        assert result.count('P6DQ ROCKET HARD STOP') == 1
        assert MARK in result
        assert result.count("K1STATE MAIN CHECKPOINT:") == 1
        assert result.count("recomp_main_state_checkpoint(GUEST_READ32(esp + 4), GUEST_READ32(esp + 8));") == 1
        assert result.count("GUEST_WRITE32(0x413F6C, eax);") == 1
        assert "MERCENARIES_CAPTURE_GAME_PATH" not in result
        for bad in (result, text.replace('P6DQ ROCKET HARD STOP', 'NO HARD STOP')):
            try:
                insert(bad, members, set(), generated, base, p5bb, p5bc, pc_fixture)
            except ValueError:
                pass
            else:
                raise AssertionError('Unsafe source passed fail-closed self-test')
    for bad_set in ({ROOT},):
        try:
            pick(generated, bad_set, base)
        except ValueError:
            pass
        else:
            raise AssertionError('Duplicate body admitted')
    # Regression for the actual hardware failure: the required root has a
    # genuinely unsupported helper. Report the symbol and source location,
    # rather than replacing the function with a fake success or vague prune.
    import contextlib
    import io
    unsupported = {ROOT: {'name': root_name,
                          'source': ('void sub_0017A0A0(void)\n{\n'
                                     'loc_0017A0A0: ;\n'
                                     '    k1_missing_real_helper();\n}\n'),
                          'file': 'recomp_test.c'}}
    witness = io.StringIO()
    try:
        with contextlib.redirect_stdout(witness):
            # The required PC helper is supported, but an unrelated missing
            # runtime function must remain a fail-closed original source stop.
            unsupported[ROOT]['source'] = (
                generated[ROOT]['source'].replace(
                    '    GUEST_WRITE32(0x413F6C, eax);',
                    '    k1_missing_real_helper();\n    GUEST_WRITE32(0x413F6C, eax);'
                )
            )
            insert(p, [ROOT], set(), unsupported, base, p5bb, p5bc, pc_fixture)
    except SystemExit as exc:
        assert 'k1_missing_real_helper' in str(exc)
        assert 'helper=k1_missing_real_helper' in witness.getvalue()
        assert 'sweep root 0x0017A0A0 itself has unresolved support' in witness.getvalue()
    else:
        raise AssertionError('Mandatory real root with missing helper silently pruned')
    for bad in (
        pc_fixture.replace('MERCENARIES_TRACE_STATE', 'OTHER_TRACE_MODE'),
        pc_fixture.replace('  guest_u32(0x00413F6Cu);',
                           '  guest_u32(0x00413F6Cu);\n  GUEST_WRITE32(0x413F6C, 0u);'),
    ):
        try:
            verify_pc_checkpoint(bad, generated[ROOT]['source'])
        except ValueError:
            pass
        else:
            raise AssertionError("Unverified/guest-writing host checkpoint allowed")
    print('[K1-TEXT] SELFTEST PASS: host-only checkpoint proven and Xbox telemetry ABI guarded; original guest writes intact; unresolved real helpers still fenced')


def stage(a, base, p5bb, p5bc):
    manual = a.pc_manual.read_text(encoding='utf-8', errors='replace')
    shards = sorted(a.shards.glob('translated_???.cpp'))
    if len(shards) != 64 or not (a.shards / 'translated_runtime.h').is_file():
        raise ValueError('Need 64 complete existing TrueTUs and runtime header')
    compiled = set()
    for file in shards:
        for m in DEF.finditer(file.read_text(encoding='utf-8', errors='replace')):
            va = int(m.group(1), 16)
            if va in compiled:
                raise ValueError('Duplicate original translated function in TrueTUs: %08X' % va)
            compiled.add(va)
    cache = a.functions.parent / '.disasm_cache.json'
    if not cache.is_file() or json.loads(cache.read_text(encoding='utf-8-sig')).get('xbe_hash','').upper() != XBE_SHA:
        raise ValueError('Original retail XBE hash provenance missing/mismatched')
    by_va, by_name = base.load_ranges(a.functions)
    row = by_va.get(ROOT)
    if row is None or row['start'] != ROOT or row['end'] <= ROOT or row['end'] > 0x00255620:
        raise ValueError('0017A0A0 not a bounded exact original .text function start')
    generated = base.load_generated(a.generated_root, by_name)
    # Existing functions and macros are provided by 64 external TrueTUs plus
    # their runtime header. The Phase5BC emitter originally saw one gigantic
    # monolithic main; don't falsely prune dependencies because of sharding.
    original_support = base.support_symbols
    extra_support = {f'sub_{va:08X}' for va in compiled}
    extra_support.update(original_support((a.shards / 'translated_runtime.h').read_text(encoding='utf-8', errors='replace')))
    base.support_symbols = lambda text: original_support(text) | extra_support
    members = pick(generated, compiled, base)
    if a.out.resolve() == a.parent.resolve() or a.out.parent.resolve() == a.parent.parent.resolve():
        raise ValueError('Refuse parent-main in-place patch')
    original = a.parent.read_bytes()
    next_text, retained, frontiers, pruned = insert(original.decode('utf-8'), members, compiled,
                                                    generated, base, p5bb, p5bc, manual)
    updated = next_text.encode('utf-8')
    summary = {
        'status': 'K1_TEXT_DIRECT_SOURCE_ONLY_NO_XDK', 'parent_sha256': digest(original),
        'new_main_sha256': digest(updated), 'original_retail_xbe_sha256': XBE_SHA,
        'original_root': '0x0017A0A0', 'original_function_end': '0x%08X' % row['end'],
        'original_body_sha256': digest(generated[ROOT]['source'].encode('utf-8')),
        'source_file_name': generated[ROOT]['file'],
        'pc_checkpoint_name': PC_CHECKPOINT,
        'pc_checkpoint_definition_sha256': verify_pc_checkpoint(
            manual, generated[ROOT]['source']),
        'checkpoint_scope': 'host-only PC capture/trace -> Xbox bounded telemetry',
        'guest_state_write_replaced': False,
        'candidate_count': len(members), 'promoted_count': len(retained),
        'promoted_vas': ['0x%08X' % v for v in retained],
        'pruned_support_missing': {'0x%08X' % k: v for k, v in pruned.items()},
        'remaining_direct_frontiers': ['0x%08X' % v for v in frontiers],
        'compiled_tus_unchanged': 64, 'xdk_verified': False, 'hardware_verified': False,
        'synthetic_guest_results': False, 'unknown_mmio_fences_changed': False,
    }
    manifest = (json.dumps(summary, indent=2) + '\n').encode('utf-8')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    if a.out.is_file() and a.out.read_bytes() != updated:
        raise ValueError('Already staged next-main differs; refusing overwrite')
    if a.manifest.is_file() and a.manifest.read_bytes() != manifest:
        raise ValueError('Existing manifest differs; refusing overwrite')
    if a.out.exists() != a.manifest.exists():
        raise ValueError('Incomplete previous staging: main/manifest mismatch')
    if not a.out.exists():
        a.out.write_bytes(updated)
        a.manifest.write_bytes(manifest)
    if a.parent.read_bytes() != original:
        raise ValueError('Verified parent changed during staging')
    print('[K1-TEXT] SOURCE PROMOTION PASS: root=0017A0A0 candidate=%d retained=%d pruned=%d next_direct=%d' %
          (len(members), len(retained), len(pruned), len(frontiers)))
    print('[K1-TEXT] PC-ONLY DIAGNOSTIC SUPPORT: verified recomp_main_state_checkpoint; no guest state mutation')
    print('[K1-TEXT] TRUE TUs UNCHANGED: 64; original helper/ABI and MMIO fences retained')
    print('[K1-TEXT] Main-only staged:', a.out)
    print('[K1-TEXT] SOURCE ONLY. XDK/hardware not yet verified')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    for k in ('base-module','p5bb-module','p5bc-module','parent','shards','functions','generated-root','pc-manual','out','manifest'):
        ap.add_argument('--' + k, type=Path)
    a = ap.parse_args()
    for k in ('base_module','p5bb_module','p5bc_module'):
        if getattr(a, k) is None:
            ap.error('--' + k.replace('_','-') + ' required')
    base = load(a.base_module, 'k1_text_base')
    p5bb = load(a.p5bb_module, 'k1_text_bb')
    p5bc = load(a.p5bc_module, 'k1_text_bc')
    if a.self_test:
        self_test(base, p5bb, p5bc)
        return
    for k in ('parent','shards','functions','generated_root','pc_manual','out','manifest'):
        if getattr(a, k) is None:
            ap.error('--' + k.replace('_','-') + ' required')
    stage(a, base, p5bb, p5bc)

if __name__ == '__main__':
    main()

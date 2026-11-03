#!/usr/bin/env python3
"""K1 D3D: source-authentic DIRECT frontier 0x00289E20 closure.

Uses local original retail XBE-hash-bound disassembly and xboxrecomp C.
Reuses the original Phase5BC support-clean pack/dispatch code and all 64
TrueTUs. Does NOT fabricate a native D3D result or any guest pixels.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import re
from collections import deque
from pathlib import Path

ROOT = 0x00289E20
PARENT_MARK = "P6K1-D3D-SECOND-CREATE-20261103"
MARK = "P6K1-D3D-DIRECT-289E20-20261103"
XBE_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
MAX_NEW = 32
MAX_DEPTH = 2
DEF = re.compile(r'(?m)^\s*(?:static\s+)?void\s+sub_([0-9A-Fa-f]{8})\s*\(\s*void\s*\)\s*\{')
LOOKUP_RE = re.compile(
    r'(?m)^(?:static[ \t]+)?recomp_func_t '
    r'phase4c_lookup_pack_func\(uint32_t xbox_va\)\n\{'
)
LOOKUP_CANON = 'static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{'
OPT_ON = '#pragma optimize("", on)'
OPT_PLACEHOLDER = '/* K1D3D_289E20_OPT_ON_HIDDEN */'
SCOPED_INVARIANTS = (
    'K1D3D SECOND: native Xenos Reset PASS',
    'K1STATE MAIN CHECKPOINT:',
    'K1PFIFO DMA_PUT READ32:',
    'P6DQ ROCKET HARD STOP',
    'D3DDevice_Reset(',
    'phase4c_lookup_pack_func',
)


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load trusted original source helper: " + str(path))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def prepare_parent(text: str) -> tuple[str, str, str]:
    newline = "\r\n" if "\r\n" in text else "\n"
    if "\r" in text.replace("\r\n", ""):
        raise ValueError("Mixed/invalid original main line endings")
    text = text.replace("\r\n", "\n")
    if MARK in text or OPT_PLACEHOLDER in text:
        raise ValueError("Already staged D3D direct frontier")
    if text.count(PARENT_MARK) != 1:
        raise ValueError("Missing/duplicated exact prior R2 renderer stage")
    missing = [s for s in SCOPED_INVARIANTS if s not in text]
    if missing:
        raise ValueError("Prior renderer, checkpoint or MMIO fence lost: " + ", ".join(missing))
    if re.search(r'\bcase\s+0x00289E20u\s*:', text):
        raise ValueError("289E20 already has a packed lookup (inspect dispatcher, not recompile)")
    definitions = list(LOOKUP_RE.finditer(text))
    if len(definitions) != 1:
        raise ValueError(f"Pack lookup real definition missing/duplicated: {len(definitions)}")
    found = definitions[0]
    original = found.group(0)
    text = text[:found.start()] + LOOKUP_CANON + text[found.end():]
    if text.count(LOOKUP_CANON) != 1:
        raise ValueError("Temporary packer lookup marker missing/duplicated")
    text = text.replace(OPT_ON, OPT_PLACEHOLDER)
    text += '\n#pragma optimize("", off)\n#pragma optimize("", on)\n'
    return text, original, newline


def restore_parent(text: str, original: str, newline: str) -> str:
    if text.count(LOOKUP_CANON) != 1 or OPT_PLACEHOLDER not in text:
        raise ValueError("Phase5BC packer changed lookup or optimization fences")
    text = text.replace(LOOKUP_CANON, original, 1)
    text = text.replace(OPT_PLACEHOLDER, OPT_ON)
    text = text.replace(PARENT_MARK, PARENT_MARK + " | " + MARK, 1)
    for marker in SCOPED_INVARIANTS:
        if marker not in text:
            raise ValueError("Lost inherited renderer / hard fence: " + marker)
    if newline == "\r\n":
        text = text.replace("\n", "\r\n")
    return text



# The maintained PC recomp port adds two hooks at this original game entry.
# Their production behavior is source-proven below, not a missing-helper
# whitelist or an artificial texture/movie success.
TEXTURE_HOOK = r'''
/* Port of maintained recomp_manual.c texture pointer validator.
 * An invalid pointer is not a legitimate source texture: preserve PC
 * semantics (return 0), record a bounded trace, never make an asset up.
 */
static uint32_t s_k1TextureBindInvalidReports = 0u;
static uint32_t recomp_validate_texture_bind(uint32_t caller,
                                             uint32_t stage,
                                             uint32_t texture)
{
    if (texture == 0u ||
        (texture >= 0x00010000u && texture <= 0x03FFFFE0u))
        return texture;
    if (s_k1TextureBindInvalidReports++ < 64u)
    {
        char line[192];
        sprintf(line,
            "K1D3D TEXTURE-BIND-INVALID caller=%08X stage=%u texture=%08X; binding NULL",
            (unsigned int)caller, (unsigned int)stage, (unsigned int)texture);
        trace(line);
    }
    return 0u;
}
'''

MOVIE_HOOK = r'''
/* Port ONLY of the PC movie checkpoint's stage-23 texture diagnostic.
 * The maintained PC stage-23 path is read-only and samples at most 128
 * events. Selected source calls are statically proven to be stage 23.
 * This does not emulate the movie decoder or alter a texture resource.
 */
static uint32_t s_k1MovieTextureSamples = 0u;
static void recomp_movie_checkpoint(uint32_t stage, uint32_t object,
                                    uint32_t path_address, uint32_t value0,
                                    uint32_t value1)
{
    int brush_valid;
    int pointer_valid;
    char line[256];
    if (stage != 23u)
    {
        trace("K1D3D MOVIE stage contract drift; stage-23-only hook");
        return;
    }
    if (s_k1MovieTextureSamples++ >= 128u)
        return;
    brush_valid = object >= 0x00010000u &&
                  object <= 0x04000000u - 0x60u;
    pointer_valid = path_address >= 0x00010000u &&
                    path_address <= 0x04000000u - 0x68u;
    sprintf(line,
        "K1D3D MOVIE-TEXTURE stage=%u brush=%08X pointer=%08X hash=%08X target=%08X",
        (unsigned int)stage, (unsigned int)object,
        (unsigned int)path_address, (unsigned int)value0, (unsigned int)value1);
    trace(line);
    sprintf(line,
        "K1D3D MOVIE BRUSH vt=%08X bound=%08X/%08X",
        (unsigned int)(brush_valid ? GUEST_READ32(object) : 0u),
        (unsigned int)(brush_valid ? GUEST_READ32(object + 0x24u) : 0u),
        (unsigned int)(brush_valid ? GUEST_READ32(object + 0x44u) : 0u));
    trace(line);
    sprintf(line,
        "K1D3D MOVIE RESOURCE %08X/%08X/%08X/%08X/%08X",
        (unsigned int)(pointer_valid ? GUEST_READ32(path_address) : 0u),
        (unsigned int)(pointer_valid ? GUEST_READ32(path_address + 4u) : 0u),
        (unsigned int)(pointer_valid ? GUEST_READ32(path_address + 8u) : 0u),
        (unsigned int)(pointer_valid ? GUEST_READ32(path_address + 0xCu) : 0u),
        (unsigned int)(pointer_valid ? GUEST_READ32(path_address + 0x10u) : 0u));
    trace(line);
    sprintf(line,
        "K1D3D MOVIE CONTEXT %08X/%08X/%08X/%08X/%08X",
        (unsigned int)(pointer_valid ? GUEST_READ32(path_address + 0x48u) : 0u),
        (unsigned int)(pointer_valid ? GUEST_READ32(path_address + 0x4Cu) : 0u),
        (unsigned int)(pointer_valid ? GUEST_READ32(path_address + 0x50u) : 0u),
        (unsigned int)(pointer_valid ? GUEST_READ32(path_address + 0x54u) : 0u),
        (unsigned int)(pointer_valid ? GUEST_READ32(path_address + 0x64u) : 0u));
    trace(line);
}
'''
SUPPORT_HOOKS = TEXTURE_HOOK + "\n" + MOVIE_HOOK
MOVIE_CALL = re.compile(r'\brecomp_movie_checkpoint\s*\(\s*(\d+)u\s*,')
TEXTURE_CALL = re.compile(r'\brecomp_validate_texture_bind\s*\(')


def verify_pc_hooks(manual: str, generated: dict, members: list[int]) -> dict:
    """Require the actual maintained PC implementations and stage-23 calls."""
    begin = manual.find('uint32_t recomp_validate_texture_bind(')
    end = manual.find('void recomp_transient_update_abi_checkpoint(', begin + 1)
    if begin < 0 or end < 0 or end - begin > 3500 or end <= begin:
        raise ValueError("Maintained PC texture validator source absent/changed")
    validator = manual[begin:end]
    # Preserve both PC branches: valid textures unchanged, invalid -> 0.
    if not all(k in validator for k in (
        'texture == 0u', 'texture >= 0x00010000u',
        'texture <= 0x03FFFFE0u', 'return texture;',
        'reports++ < 64u', 'return 0u;',
    )):
        raise ValueError("Maintained PC texture validation contract drift")
    begin = manual.find('void recomp_movie_checkpoint(')
    if begin < 0:
        raise ValueError("Maintained PC movie hook definition absent")
    next_function = re.search(r'\nvoid\s+[A-Za-z_]\w*\s*\(', manual[begin+1:])
    if next_function is None:
        raise ValueError("Maintained PC movie hook boundary missing")
    movie = manual[begin:begin+1+next_function.start()]
    start = movie.find('if (stage >= 10u && stage <= 24u)')
    finish = movie.find('if (path_address >= 0x00010000u', start+1)
    if start < 0 or finish < 0 or finish <= start or finish - start > 6500:
        raise ValueError("PC movie stage-23 diagnostic block absent/changed")
    stage_23 = movie[start:finish]
    for k in ('movie_texture_samples++ < 128u',
              'const int brush_valid', 'const int pointer_valid',
              '[RETAIL-MOVIE-TEXTURE]',
              'guest_u32(object + 0x24u)',
              'guest_u32(path_address + 0x64u)',
              'return;'):
        if k not in stage_23:
            raise ValueError("Maintained PC stage-23 movie diagnostic drift: " + k)
    if re.search(r'\b(?:GUEST_WRITE\d*|guest_write\w*|MEM_WRITE\w*|guest_ptr)\s*\(', stage_23):
        raise ValueError("PC movie stage-23 hook now writes guest memory")
    calls = []
    for va in members:
        source = generated[va]['source']
        movie_calls = MOVIE_CALL.findall(source)
        # Do not silently port unrelated movie stages or resolve a moving
        # support problem by accepting a different call form.
        if 'recomp_movie_checkpoint' in source and not movie_calls:
            raise ValueError("Unknown movie hook invocation shape: 0x%08X" % va)
        if any(item != "23" for item in movie_calls):
            raise ValueError("Non-stage-23 movie hook in selected D3D closure: 0x%08X" % va)
        if movie_calls:
            calls.append(va)
    if ROOT not in calls or not TEXTURE_CALL.search(generated[ROOT]['source']):
        raise ValueError("Actual 289E20 hooks missing; no reason to install compatibility helpers")
    return {
        'pc_texture_validator_sha256': sha(validator.encode('utf-8')),
        'pc_movie_stage_23_sha256': sha(stage_23.encode('utf-8')),
        'movie_callsite_vas': ['0x%08X' % v for v in calls],
        'texture_return_rule': 'unchanged if NULL or 0x00010000..0x03FFFFE0; else 0',
        'movie_hook_scope': 'stage-23 read-only 128-sample diagnostics only',
    }



# The maintained PC version passes g_recomp_current_func only as the
# TEXTURE-BIND-INVALID diagnostic caller field. The Xbox 360 TrueTU runtime
# does not export that mutable PC trace global. This exact translated
# function has an immutable original VA, and the validator return value
# depends ONLY on texture. Rebind that ONE reporting argument to its real
# function VA. Never define a fabricated global or suppress validation.
PC_CALLER_ARG = re.compile(
    r'(\brecomp_validate_texture_bind\s*\(\s*)g_recomp_current_func(?=\s*,)'
)
PC_CURRENT_SYMBOL = re.compile(r'\bg_recomp_current_func\b')


def bind_pc_diagnostic_caller(generated: dict, selected: list[int], base):
    """Return a copy with exactly one provenance-checked telemetry arg."""
    if ROOT not in selected or ROOT not in generated:
        raise ValueError("Missing actual retail D3D caller root")
    root_source = generated[ROOT]["source"]
    masked = base.mask_noncode(root_source)
    if len(PC_CURRENT_SYMBOL.findall(masked)) != 1 or \
       len(PC_CALLER_ARG.findall(masked)) != 1:
        raise ValueError(
            "PC caller global used outside the unique texture-diagnostic arg "
            "in original 0x00289E20; refusing guessed linkage"
        )
    for va in selected:
        if va != ROOT and PC_CURRENT_SYMBOL.search(
            base.mask_noncode(generated[va]["source"])
        ):
            raise ValueError(
                "PC current-function global also used by 0x%08X; "
                "cannot bind that diagnostic caller automatically" % va
            )
    rebound, count = PC_CALLER_ARG.subn(
        lambda m: m.group(1) + "0x%08Xu" % ROOT, root_source
    )
    if count != 1 or "g_recomp_current_func" in base.mask_noncode(rebound):
        raise ValueError("Unique caller telemetry rebind did not converge")
    # Preserve the user-local original C by cloning only the packer's
    # in-memory entry. Hash the original, not the single diagnostic rewrite.
    derived = dict(generated)
    derived[ROOT] = dict(generated[ROOT], source=rebound)
    return derived, {
        "binding": "original retail function VA as diagnostic caller only",
        "diagnostic_caller_va": "0x%08X" % ROOT,
        "original_source_sha256": sha(root_source.encode("utf-8")),
        "rebound_source_sha256": sha(rebound.encode("utf-8")),
        "diagnostic_callsite_rewrites": count,
        "texture_validation_return_rule_unchanged": True,
    }


def choose(generated: dict, compiled: set[int], base) -> list[int]:
    if ROOT in compiled:
        raise ValueError("Root already compiled in TrueTU; audit lookup/linkage, do not duplicate")
    if ROOT not in generated:
        raise ValueError("No original 00289E20 C body; cannot fabricate renderer function")
    lookup = {row["name"]: va for va, row in generated.items()}
    queue = deque([(ROOT, 0)])
    seen = set()
    chosen = []
    while queue and len(chosen) < MAX_NEW:
        va, depth = queue.popleft()
        if va in seen:
            continue
        seen.add(va)
        if va not in generated:
            continue
        if va not in compiled:
            chosen.append(va)
        if depth >= MAX_DEPTH:
            continue
        calls = sorted(set(base.CALL_RE.findall(base.mask_noncode(generated[va]["source"]))))
        for call in calls:
            dep = lookup.get(call)
            if dep is not None and dep not in seen and dep not in compiled:
                queue.append((dep, depth+1))
    if not chosen or chosen[0] != ROOT:
        raise ValueError("Original retail 00289E20 root not selected")
    return chosen


def emit(parent: str, choices: list[int], compiled: set[int], generated: dict,
         base, bb, bc) -> tuple[str, list[int], list[int], dict]:
    prepared, original_lookup, newline = prepare_parent(parent)
    for name in ('recomp_movie_checkpoint', 'recomp_validate_texture_bind'):
        if re.search(r'(?m)^(?:static\s+)?(?:void|uint32_t)\s+' + name +
                     r'\s*\(', prepared):
            raise ValueError("D3D helper already defined; no duplicate implementation: " + name)
    if prepared.count(LOOKUP_CANON) != 1:
        raise ValueError("No unique lookup anchor for original PC support")
    prepared = prepared.replace(LOOKUP_CANON, SUPPORT_HOOKS + "\n" + LOOKUP_CANON, 1)
    if prepared.count("static uint32_t recomp_validate_texture_bind(") != 1 or \
       prepared.count("static void recomp_movie_checkpoint(") != 1:
        raise ValueError("Authentic PC helper ports not uniquely installed")
    previous_root = bc.SWEEP_ROOT
    previous_entry = bc.instrument_root_entry
    previous_standard = set(base.STANDARD_CALLS)
    base.STANDARD_CALLS.update(("sin", "cos"))
    try:
        bc.SWEEP_ROOT = ROOT
        bc.instrument_root_entry = lambda rendered, name: rendered
        next_main, rendered, frontier, pruned = bc.insert_pack_members(
            prepared, base, bb, generated, choices, compiled | set(choices),
            require_sweep_root=True,
        )
    finally:
        bc.SWEEP_ROOT = previous_root
        bc.instrument_root_entry = previous_entry
        base.STANDARD_CALLS.clear()
        base.STANDARD_CALLS.update(previous_standard)
    if ROOT not in rendered or ROOT in pruned:
        raise ValueError("Mandatory original D3D root support unresolved: "
                         + ", ".join(pruned.get(ROOT, [])))
    # Only consider success when EVERY proposed function is present.
    # No silently lost helper or fake success at the end of a partial sweep.
    missing = [va for va in choices if va not in rendered or va in pruned]
    if missing:
        raise ValueError("Source-clean closure pruned real functions: "
                         + ", ".join("%08X:%s" % (v, pruned.get(v, [])) for v in missing))
    for va in choices:
        expected = "case 0x%08Xu: return %s;" % (va, generated[va]["name"])
        if next_main.count(expected) != 1:
            raise ValueError("Packed lookup target missing/duplicated: 0x%08X" % va)
    next_main = restore_parent(next_main, original_lookup, newline)
    return next_main, choices, sorted(frontier), pruned


def selftest() -> None:
    start = (
        'const char* build="P6K1-D3D-SECOND-CREATE-20261103";\n'
        + '\n'.join('// ' + key for key in SCOPED_INVARIANTS) + '\n'
        + 'recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{\n'
        + '  return NULL;\n}\n'
        + OPT_ON + '\n'
    )
    for exported in (True, False):
        for windows in (True, False):
            value = start if exported else start.replace(
                "recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)",
                "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)"
            )
            if windows:
                value = value.replace("\n", "\r\n")
            prepared, original, nl = prepare_parent(value)
            assert prepared.count(LOOKUP_CANON) == 1
            restored = restore_parent(prepared, original, nl)
            assert MARK in restored
            assert original.replace("\n", nl) in restored
            assert OPT_PLACEHOLDER not in restored
            assert '\r\n' in restored if windows else '\r\n' not in restored
            try:
                prepare_parent(restored)
            except ValueError:
                pass
            else:
                raise AssertionError("Second staging accepted")
    assert "return texture;" in SUPPORT_HOOKS and "return 0u;" in SUPPORT_HOOKS
    assert "s_k1MovieTextureSamples++ >= 128u" in SUPPORT_HOOKS
    assert SUPPORT_HOOKS.count("GUEST_WRITE32") == 0
    assert "GUEST_READ32(path_address + 0x64u)" in SUPPORT_HOOKS
    for bad in (start.replace("D3DDevice_Reset(", ""),
                start.replace("P6DQ ROCKET HARD STOP", ""),
                start.replace(PARENT_MARK, "")):
        try:
            prepare_parent(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe source accepted")
    class Base:
        CALL_RE = re.compile(r'\b(sub_[0-9A-Fa-f]{8})\s*\(')
        mask_noncode = staticmethod(lambda v: v)
    sources = {
        ROOT: {"name": "sub_00289E20", "source": "sub_00289E20(); sub_00289E80();"},
        0x00289E80: {"name": "sub_00289E80", "source": "return;"},
    }
    assert choose(sources, set(), Base()) == [ROOT, 0x00289E80]
    actual_pc_source = Path(__file__).resolve().parents[3] / "src" / "recomp_manual.c"
    if not actual_pc_source.is_file():
        raise AssertionError("Maintained PC hook implementations missing from checkout")
    real_proof_source = actual_pc_source.read_text(encoding="utf-8")
    support_source = {
        ROOT: {"name": "sub_00289E20", "source":
               "recomp_validate_texture_bind(g_recomp_current_func, 0u, 0u); "
               "recomp_movie_checkpoint(23u, 0u, 0u, 0u, 0u);"}
    }
    proof = verify_pc_hooks(real_proof_source, support_source, [ROOT])
    assert len(proof["pc_texture_validator_sha256"]) == 64
    assert len(proof["pc_movie_stage_23_sha256"]) == 64
    rebound_fixture, binding = bind_pc_diagnostic_caller(
        support_source, [ROOT], Base()
    )
    assert rebound_fixture[ROOT]["source"].count(
        "recomp_validate_texture_bind(0x00289E20u,") == 1
    assert "g_recomp_current_func" not in rebound_fixture[ROOT]["source"]
    assert "recomp_movie_checkpoint(23u," in rebound_fixture[ROOT]["source"]
    assert support_source[ROOT]["source"].count("g_recomp_current_func") == 1
    assert binding["diagnostic_callsite_rewrites"] == 1
    assert binding["diagnostic_caller_va"] == "0x00289E20"
    for bad_source in (
        "recomp_validate_texture_bind(g_recomp_current_func, 1u, 2u); "
        "GUEST_WRITE32(8u, g_recomp_current_func);",
        "recomp_validate_texture_bind(g_recomp_current_func, 1u, 2u); "
        "recomp_validate_texture_bind(g_recomp_current_func, 2u, 3u);",
        "recomp_movie_checkpoint(23u, 0u, 0u, 0u, 0u);",
    ):
        try:
            bind_pc_diagnostic_caller(
                {ROOT: {"source": bad_source}}, [ROOT], Base()
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Non-unique/misplaced PC caller global accepted")
    try:
        bind_pc_diagnostic_caller(
            {**support_source, 0x00289E80: {
                "source": "GUEST_WRITE32(4u, g_recomp_current_func);"}},
            [ROOT, 0x00289E80], Base()
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Additional caller-global use accepted")
    for changed in ("recomp_movie_checkpoint(6u, 0u, 0u, 0u, 0u);",
                    "recomp_movie_checkpoint(0u, 0u, 0u, 0u, 0u);"):
        try:
            verify_pc_hooks(real_proof_source,
                            {ROOT: {"source": changed +
                                    "recomp_validate_texture_bind(0u,0u,0u);"}},
                            [ROOT])
        except ValueError:
            pass
        else:
            raise AssertionError("Unsupported PC movie stage accepted")
    try:
        choose(sources, {ROOT}, Base())
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate TrueTU source accepted")
    print("[K1D3D-DIRECT] SELFTEST PASS: mandatory original D3D root, 64-TU compatible lookup, intact R2 Reset, hard fences, CRLF")


def write_once(path: Path, blob: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file() or path.read_bytes() != blob:
            raise ValueError("Existing output differs; refusing overwrite: " + str(path))
    else:
        path.write_bytes(blob)


def stage(a: argparse.Namespace, base, bb, bc) -> None:
    if not a.pc_manual.is_file():
        raise ValueError("Original maintained PC helper source unavailable")
    originals = sorted(a.shards.glob("translated_???.cpp"))
    if len(originals) != 64 or not (a.shards / "translated_runtime.h").is_file():
        raise ValueError("Exactly 64 original TrueTUs and header required")
    compiled: set[int] = set()
    originals_hashes = {}
    for file in originals:
        data = file.read_bytes()
        originals_hashes[file.name] = sha(data)
        for match in DEF.finditer(data.decode("utf-8", "replace")):
            va = int(match.group(1), 16)
            if va in compiled:
                raise ValueError("Duplicate original TrueTU function VA: %08X" % va)
            compiled.add(va)
    if a.output.resolve() == a.parent.resolve():
        raise ValueError("Refusing in-place changes to parent source")
    cache = a.functions.parent / ".disasm_cache.json"
    if not cache.is_file() or json.loads(cache.read_text(encoding="utf-8-sig")).get(
            "xbe_hash", "").upper() != XBE_SHA:
        raise ValueError("Original retail XBE provenance absent/mismatched")
    by_va, by_name = base.load_ranges(a.functions)
    row = by_va.get(ROOT)
    if row is None or row["start"] != ROOT or not (
        0x00288640 <= ROOT < row["end"] <= 0x0029B874
    ):
        raise ValueError("289E20 is not a bounded retail original D3D-section function start")
    generated = base.load_generated(a.generated_root, by_name)
    orig_support = base.support_symbols
    extra_support = {'sub_%08X' % va for va in compiled}
    extra_support.update(orig_support(
        (a.shards / "translated_runtime.h").read_text(encoding="utf-8", errors="replace")))
    base.support_symbols = lambda text: orig_support(text) | extra_support

    chosen = choose(generated, compiled, base)
    support_proof = verify_pc_hooks(a.pc_manual.read_text(encoding="utf-8"), generated, chosen)
    # The true original source hash remains available as provenance. Only
    # the diagnostic caller argument is rebound in the packer's copy.
    original_root_sha256 = sha(generated[ROOT]["source"].encode("utf-8"))
    generated, diagnostic_binding = bind_pc_diagnostic_caller(generated, chosen, base)
    if diagnostic_binding["original_source_sha256"] != original_root_sha256:
        raise ValueError("Original 289E20 source provenance changed")
    original_bytes = a.parent.read_bytes()
    result, retained, frontier, pruned = emit(
        original_bytes.decode("utf-8"), chosen, compiled, generated, base, bb, bc
    )
    produced = result.encode("utf-8")
    if not all(tag in result for tag in SCOPED_INVARIANTS):
        raise ValueError("R2 native renderer and/or guest hard-fence lost")
    if not ('case 0x00289E20u: return sub_00289E20;' in result):
        raise ValueError("Hardware target has not been linked into lookup")

    summary = {
        "status": "K1_D3D_DIRECT_289E20_SOURCE_ONLY_NO_XDK",
        "original_xbe_sha256": XBE_SHA,
        "root_va": "0x00289E20",
        "root_end": "0x%08X" % row["end"],
        "root_original_source_file": generated[ROOT]["file"],
        "root_original_body_sha256": original_root_sha256,
        "pc_texture_diagnostic_caller_binding": diagnostic_binding,
        "parent_sha256": sha(original_bytes),
        "new_main_sha256": sha(produced),
        "promoted_vas": ["0x%08X" % v for v in retained],
        "remaining_direct_frontiers": ["0x%08X" % v for v in frontier],
        "pruned_support_missing": {"0x%08X" % v: issue for v, issue in pruned.items()},
        "pc_support_proof": support_proof,
        "pc_supported_texture_hook_implemented": True,
        "pc_stage23_telemetry_implemented": True,
        "original_true_tus": 64, "modified_true_tus": 0,
        "true_tu_sha256": originals_hashes,
        "native_xenos_reset_replaced": False,
        "guest_state_checkpoint_replaced": False,
        "unknown_mmio_fences_changed": False,
        "fake_guest_pixels": False,
        "xdk_verified": False,
        "hardware_verified": False,
    }
    manifest = (json.dumps(summary, indent=2) + "\n").encode("utf-8")
    write_once(a.output, produced)
    write_once(a.manifest, manifest)
    if a.parent.read_bytes() != original_bytes:
        raise ValueError("R2 parent main mutated during stage")
    for file in originals:
        if sha(file.read_bytes()) != originals_hashes[file.name]:
            raise ValueError("Original TrueTU changed: " + file.name)
    print("[K1D3D-DIRECT] SOURCE PASS root=00289E20 source=%s candidates=%u packed=%u" %
          (generated[ROOT]["file"], len(chosen), len(retained)))
    print("[K1D3D-DIRECT] Original 64 TrueTUs untouched; R2 native Reset and guest hard fences preserved")
    print("[K1D3D-DIRECT] XDK/HARDWARE NOT VERIFIED")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    for name in ("base-module", "p5bb-module", "p5bc-module", "parent",
                 "shards", "functions", "generated-root", "pc-manual", "output", "manifest"):
        p.add_argument("--" + name, type=Path)
    a = p.parse_args()
    if a.self_test:
        selftest()
        return
    for name in ("base_module", "p5bb_module", "p5bc_module", "parent", "shards",
                 "functions", "generated_root", "pc_manual", "output", "manifest"):
        if getattr(a, name) is None:
            p.error("Missing --" + name.replace("_", "-"))
    stage(a, load(a.base_module, "k1direct_base"),
          load(a.p5bb_module, "k1direct_bb"),
          load(a.p5bc_module, "k1direct_bc"))


if __name__ == "__main__":
    main()

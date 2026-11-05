#!/usr/bin/env python3
"""V6g: dependency-closed original camera neighborhood, no game-state shortcuts.

The V6f Xbox log proved the next hard stop 0x001F8B30 (tick 58,665,261).
This stages the root and optional support-clean neighbors from the same frozen
generated source. Guest behavior and telemetry remain identical to V6f.
"""
from pathlib import Path
import hashlib, json, re, sys

TAG = "[K1-V6g]"
ROOT = Path.cwd()
PARENT = ROOT / "build/phase6_integration_map/k1_pixel_camera_followup_v6f"
DEST = ROOT / "build/phase6_integration_map/k1_pixel_camera_batch_v6g"
SRC = ROOT / "build/phase3n_final_abi_scale/runtime/gen/recomp_0010.c"
SHARDS = ROOT / "build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
MARK = "K1-V6G-RETAIL-CAMERA-BATCH-20261105"
RETAIL = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
SEED = "sub_001F8B30"
MAX_FUNCS = 48
# These adjacent original camera routines are only optional: decline any
# that would require unknown source, PC options hooks, or unsupported state.
NEIGHBOR_LOW, NEIGHBOR_HIGH = 0x001F8900, 0x001F9200

def sha(x): return hashlib.sha256(x).hexdigest()
def require(ok, why):
    if not ok: raise RuntimeError(why)

def definitions_from(src):
    defs = {}
    pattern = r"(?m)^void (sub_[0-9A-Fa-f]{8})\(void\)\s*\{.*?^\}"
    for m in re.finditer(pattern, src, re.M | re.S):
        require(m.group(1) not in defs, "Duplicate original function " + m.group(1))
        defs[m.group(1)] = m.group(0)
    return defs

def calls_in(fn):
    return set(re.findall(r"\b(sub_[0-9A-Fa-f]{8})\s*\(", fn))

def inspect(name, defs, known, staged, trail):
    if name in known or name in staged: return ({}, None)
    if name in trail: return ({}, None)
    if name not in defs: return ({}, "source_missing:" + name)
    fn = defs[name]
    unsupported = sorted(set(re.findall(r"\b(recomp_(?:options|crt)_[A-Za-z_0-9]+)\s*\(", fn)))
    if unsupported: return ({}, name + " unsupported helper: " + ", ".join(unsupported))
    if "return;" not in fn: return ({}, name + " no recognized return")
    results = {name: fn}
    # Small closure, with no unsafe writes. Other original functions already
    # in the 64 TrueTUs or V6f are linked, never copied twice.
    for dep in sorted(calls_in(fn) - {name} - known - staged.keys()):
        sub, issue = inspect(dep, defs, known, {**staged, **results}, trail | {name})
        if issue: return ({}, name + " -> " + issue)
        results.update(sub)
        if len(staged) + len(results) > MAX_FUNCS:
            return ({}, "closure_limit:" + name)
    return (results, None)

def main():
    manifest = json.loads((PARENT / "v6f-manifest.json").read_text(encoding="utf-8-sig"))
    parent = (PARENT / "main.cpp").read_bytes()
    require(manifest["retail_sha256"] == RETAIL, "Retail XBE identity mismatch")
    require(manifest["source_sha256"] == sha(parent), "V6f main.cpp hash mismatch")
    tus = sorted(SHARDS.glob("translated_???.cpp"))
    require(len(tus) == 64, "Expected exactly 64 TrueTUs")
    hashes = {p.name: sha(p.read_bytes()) for p in tus}
    require(hashes == manifest["true_tu_sha256"], "TrueTU source drift")

    raw = SRC.read_bytes()
    require(sha(raw) == manifest["original_recomp_0010_sha256"],
            "Original generated recomp_0010.c drift")
    defs = definitions_from(raw.decode("utf-8-sig").replace("\r\n", "\n"))
    parent_txt = parent.decode("utf-8-sig")
    eol = "\r\n" if "\r\n" in parent_txt else "\n"
    base = parent_txt.replace("\r\n", "\n")
    known = set(re.findall(r"(?m)^\s*void (sub_[0-9A-Fa-f]{8})\(void\)\s*\{", base))
    for tu in tus:
        known.update(re.findall(r"(?m)^\s*void (sub_[0-9A-Fa-f]{8})\(void\)\s*\{",
                     tu.read_text(encoding="utf-8-sig", errors="replace")))
    # PblMath sin 0x001F9D70 is an existing manually maintained runtime
    # target, not an emitted recomp_0010.c function. The V6f hardware log
    # proves it executed. Accept ONLY this exact support-owned dependency,
    # and only if the inherited compiled main retains its recognizable
    # manual execution handler and target literal. Do not broadly whitelist
    # every undefined function.
    manual_sin = "sub_001F9D70"
    manual_witness = "entered manual PblMath sin 001F9D70"
    manual_target = "0x001F9D70u"
    require(base.count(manual_witness) == 1,
            "Manual PblMath sin handler witness absent or duplicated in V6f")
    require(manual_target in base,
            "Manual PblMath sin dispatch address absent in V6f")
    require(manual_sin not in defs,
            "PblMath sin unexpectedly generated; re-audit ownership")
    manual_owners = [manual_sin]
    known.add(manual_sin)
    require(SEED not in known, "Hardware frontier already implemented")
    require(SEED in defs, "Hardware frontier missing from verified recomp_0010.c")

    staged, issue = inspect(SEED, defs, known, {}, set())
    require(issue is None, "REQUIRED " + SEED + " BLOCKED: " + str(issue))
    require(SEED in staged, "Root not included")
    # A runtime-dispatch witness does not provide a C++ symbol. Never
    # silently declare a nonexistent translated function. Until its ABI is
    # bridged, emit the handler/callsite evidence and block staging/build.
    references = [n for n, fn in staged.items() if manual_sin in calls_in(fn)]
    if references:
        lines = base.splitlines()
        matches = [i for i, line in enumerate(lines)
                   if manual_witness in line or manual_target in line]
        excerpts = []
        for i in matches[:16]:
            lo, hi = max(0, i - 18), min(len(lines), i + 23)
            excerpts.append("--- V6f runtime line " + str(i + 1) + " ---\n" +
                            "\n".join("%d: %s" % (j + 1, lines[j])
                                      for j in range(lo, hi)))
        call_excerpts = []
        for name in references:
            f_lines = staged[name].splitlines()
            for i, line in enumerate(f_lines):
                if manual_sin in line:
                    lo, hi = max(0, i - 12), min(len(f_lines), i + 13)
                    call_excerpts.append("--- " + name + " call ---\n" +
                       "\n".join("%d: %s" % (j + 1, f_lines[j])
                                 for j in range(lo, hi)))
        path = ROOT / "build/phase6_integration_map/k1_v6g_manual_sin_abi_audit.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "PblMath manual handler is runtime dispatch, NOT a C++ symbol.\n"
            "Callers: " + ", ".join(references) + "\n" +
            "\n\n".join(excerpts + call_excerpts) + "\n", encoding="utf-8")
        raise RuntimeError("Manual PblMath sin requires a verified C++/runtime ABI bridge; "
                           "audit: " + str(path))
    optional_skips = {}
    candidates = [name for name in sorted(defs)
                  if NEIGHBOR_LOW <= int(name[4:], 16) < NEIGHBOR_HIGH
                  and name not in known and name not in staged]
    for name in candidates:
        added, issue = inspect(name, defs, known, staged, set())
        if issue:
            optional_skips[name] = issue
        elif len(staged) + len(added) <= MAX_FUNCS:
            staged.update(added)
        else:
            optional_skips[name] = "cap"
    require(len(staged) <= MAX_FUNCS, "Batch cap exceeded")

    # Explicit declaration and dispatch coverage, not just dead-code packing.
    for name in staged:
        require(name not in known, "Duplicate compiled symbol " + name)
        addr = name[4:].upper()
        require("case 0x" + addr + "u:" not in base, "Already dispatched " + name)
    prototypes = "\n".join("void " + n + "(void);" for n in sorted(staged))
    bodies = "\n\n".join(staged[n] for n in sorted(staged))
    marker = "/* " + MARK + " */"
    bodies = marker + "\n" + bodies
    anchor = "    case 0x001F8F10u: return sub_001F8F10;"
    require(base.count(anchor) == 1, "V6f dispatch anchor missing/nonunique")
    pos = base.index(anchor)
    headers = list(re.finditer(
        r"(?m)^[ \t]*(?:(?:static|inline)\s+)*recomp_func_t\s+"
        r"[A-Za-z_][A-Za-z_0-9]*\s*\([^;{}]*\)\s*\{",
        base[:pos]))
    require(headers and "switch" in base[headers[-1].end():pos],
            "Dispatch lookup scope unverified")
    at = headers[-1].start()
    patched = base[:at] + prototypes + "\n\n" + bodies + "\n\n" + base[at:]
    dispatches = "\n".join("    case 0x" + n[4:].upper() + "u: return " + n + ";"
                         for n in sorted(staged))
    patched = patched.replace(anchor, anchor + "\n" + dispatches, 1)
    for name in staged:
        require(patched.count("case 0x" + name[4:].upper() + "u:") == 1,
                "Missing/duplicate dispatch " + name)
    for anchor in (
        "K1-V6b APC QUEUED", "K1-V6b APC DELIVERED",
        "0x0ACE8000u", "s_k1v6Delivered >= 16u",
        "P6DQ ROCKET HARD STOP", "K1-V6E-RED-CAMERA-001F89F0-20261105",
        "K1-V6F-ORIGINAL-001F8F10-20261105"):
        require(patched.count(anchor) == base.count(anchor),
                "Inherited V6f evidence changed: " + anchor)
    require(patched.count(MARK) == 1, "V6g marker count")
    output = patched.replace("\n", eol).encode("utf-8")
    report = {
        "stage": "V6G_SOURCE_ONLY_NOT_BUILT_OR_HARDWARE_TESTED",
        "hardware_frontier": "0x001F8B30",
        "source": str(SRC.relative_to(ROOT)).replace("\\", "/"),
        "retail_sha256": RETAIL,
        "parent_v6f_sha256": sha(parent),
        "original_recomp_0010_sha256": sha(raw),
        "source_sha256": sha(output),
        "true_tu_count": 64, "true_tu_sha256": hashes,
        "included": sorted(staged),
        "verified_manual_dependencies": manual_owners,
        "optional_skipped": optional_skips,
        "dispatch_count": len(staged),
        "marker": MARK,
        "guest_state_or_tick_skipped": False,
        "debug_overhead_optimization_enabled": False,
        "original_apc_and_hard_fences_unchanged": True,
        "hardware_tested": False
    }
    payloads = [
        (DEST / "main.cpp", output),
        (DEST / "v6g-manifest.json", (json.dumps(report, indent=2) + "\n").encode()),
    ]
    for dest, data in payloads:
        if dest.exists(): require(dest.read_bytes() == data, "Refusing overwrite " + str(dest))
    DEST.mkdir(parents=True, exist_ok=True)
    for dest, data in payloads:
        if not dest.exists(): dest.write_bytes(data)
    require((PARENT / "main.cpp").read_bytes() == parent, "V6f parent mutated")
    print(TAG + " SOURCE PASS: root " + SEED + " plus " + str(len(staged)-1) + " original camera/support functions")
    print(TAG + " STAGED: " + ", ".join(sorted(staged)))
    print(TAG + " VERIFIED MANUAL OWNER: " + manual_sin + " (runtime handler already staged in V6f)")
    print(TAG + " OPTIONAL SKIPPED: " + str(len(optional_skips)) + " (manifest contains reasons)")
    print(TAG + " PASS: all dispatches, 64 TrueTUs, APC and hard fences preserved")
    print(TAG + " MAIN: " + str(DEST / "main.cpp"))
    print(TAG + " SHA256: " + sha(output))
    print(TAG + " SOURCE-ONLY. XDK compile and hardware proof still required.")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print(TAG + " BLOCKED: " + str(e), file=sys.stderr)
        sys.exit(1)

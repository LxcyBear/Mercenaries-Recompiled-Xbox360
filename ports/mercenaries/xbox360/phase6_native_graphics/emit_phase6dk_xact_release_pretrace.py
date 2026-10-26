#!/usr/bin/env python3
r"""Phase 6DK: catch the real predecessor that enters XACT Release 0x0027F2C2.

6DI proved the live XACT root 0x01B5C320 drops refcount 1 -> 0 in
sub_0027F2C2, but neither of its two direct translated callers was active.

6DJ wrapped 9,035 translated RECOMP_ICALL_SAFE sites and proved none targeted
0x0027F2C2.

6DK closes both remaining blind spots:
  1) inject a PRE-TRACE probe immediately before RECOMP_TRACE_FUNC in
     sub_0027F2C2, so phase4c_current_caller() still names the previously
     executed translated VA rather than 0x0027F2C2 itself;
  2) probe phase4c_lookup_pack_func(0x0027F2C2) to catch packed
     DIRECT/ITAIL/other dynamic lookup dispatch.

Diagnostic only. No refcount, branch, destructor, free, dispatch, guest-memory,
graphics, audio or hard-fence semantics are changed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6DJ-XACT-INDIRECT-RELEASE-CALLER-20261026-A"
BUILD_TAG = "P6DK-XACT-RELEASE-PRETRACE-20261026-A"
COOKIE_OLD = "phase6dj_env_build_cookie"
COOKIE_NEW = "phase6dk_env_build_cookie"
EMITTER_REVISION = "6DK-R2"
TARGET_NAME = "sub_0027F2C2"
TARGET_VA = 0x0027F2C2


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DK] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def function_span(text: str, name: str) -> tuple[int, int]:
    pat = re.compile(
        rf"(?m)^\s*(?:static\s+)?(?:__forceinline\s+)?"
        rf"void\s+{re.escape(name)}\s*\(\s*void\s*\)\s*\{{"
    )
    matches = list(pat.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"[Phase6DK] expected one {name} definition, found {len(matches)}"
        )
    start = matches[0].start()
    brace = text.find("{", matches[0].start(), matches[0].end())
    depth = 0
    i = brace
    in_string = False
    quote = ""
    escape = False
    in_line = False
    in_block = False
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if in_line:
            if c == "\n":
                in_line = False
            i += 1
            continue
        if in_block:
            if c == "*" and n == "/":
                in_block = False
                i += 2
            else:
                i += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                in_string = False
            i += 1
            continue
        if c == "/" and n == "/":
            in_line = True
            i += 2
            continue
        if c == "/" and n == "*":
            in_block = True
            i += 2
            continue
        if c in ('"', "'"):
            in_string = True
            quote = c
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    raise SystemExit(f"[Phase6DK] unterminated function {name}")


def install_state(text: str) -> str:
    # These globals are consumed by phase4c_lookup_pack_func itself, so they
    # must be declared before that function definition. The inherited 6DJ
    # state block lives too late in the file for that use.
    anchor = "typedef void (*recomp_func_t)(void);\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6DK] expected one recomp_func_t typedef anchor, found {text.count(anchor)}"
        )
    state = """static DWORD s_phase6dkPretraceReports = 0u;
static DWORD s_phase6dkPretracePrevious = 0u;
static DWORD s_phase6dkPretraceObject = 0u;
static DWORD s_phase6dkPretraceRef = 0u;
static DWORD s_phase6dkPretraceEsp = 0u;
static DWORD s_phase6dkLookupReports = 0u;
static DWORD s_phase6dkLookupCaller = 0u;
static DWORD s_phase6dkLookupEsp = 0u;

"""
    return text.replace(anchor, state + anchor, 1)


def instrument_target_pretrace(text: str) -> str:
    start, end = function_span(text, TARGET_NAME)
    body = text[start:end]
    needle = "RECOMP_TRACE_FUNC(0x0027F2C2u);"
    if body.count(needle) != 1:
        raise SystemExit(
            f"[Phase6DK] expected one target RECOMP_TRACE_FUNC, found {body.count(needle)}"
        )
    probe = r'''{
        DWORD phase6dk_prev = phase4c_current_caller();
        DWORD phase6dk_obj = ecx;
        DWORD phase6dk_ref =
            phase6dk_obj ? GUEST_READ32(phase6dk_obj + 8u) : 0u;
        char phase6dk_line[512];

        ++s_phase6dkPretraceReports;
        s_phase6dkPretracePrevious = phase6dk_prev;
        s_phase6dkPretraceObject = phase6dk_obj;
        s_phase6dkPretraceRef = phase6dk_ref;
        s_phase6dkPretraceEsp = esp;

        sprintf(
            phase6dk_line,
            "P6DK XACT RELEASE PRETRACE: previous=%08X target=0027F2C2 object=%08X ref=%u esp=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X reports=%u",
            (unsigned int)phase6dk_prev,
            (unsigned int)phase6dk_obj,
            (unsigned int)phase6dk_ref,
            (unsigned int)esp,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)ebx,
            (unsigned int)esi,
            (unsigned int)edi,
            (unsigned int)s_phase6dkPretraceReports);
        trace(phase6dk_line);
    }
    '''
    body = body.replace(needle, probe + needle, 1)
    return text[:start] + body + text[end:]


def instrument_pack_lookup(text: str) -> str:
    signature = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if text.count(signature) != 1:
        raise SystemExit(
            "[Phase6DK] expected one phase4c_lookup_pack_func definition"
        )
    probe = r'''
    if (xbox_va == 0x0027F2C2u)
    {
        DWORD phase6dk_caller = phase4c_current_caller();
        char phase6dk_line[448];
        ++s_phase6dkLookupReports;
        s_phase6dkLookupCaller = phase6dk_caller;
        s_phase6dkLookupEsp = esp;
        sprintf(
            phase6dk_line,
            "P6DK XACT RELEASE PACK LOOKUP: caller=%08X target=%08X esp=%08X object=%08X ref=%u reports=%u",
            (unsigned int)phase6dk_caller,
            (unsigned int)xbox_va,
            (unsigned int)esp,
            (unsigned int)GUEST_READ32(0x0028836Cu),
            (unsigned int)(GUEST_READ32(0x0028836Cu)
                ? GUEST_READ32(GUEST_READ32(0x0028836Cu) + 8u) : 0u),
            (unsigned int)s_phase6dkLookupReports);
        trace(phase6dk_line);
    }
'''
    return text.replace(signature, signature + probe, 1)


def insert_summary(text: str) -> str:
    marker = "P6DJ XACT INDIRECT RELEASE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DK] inherited 6DJ summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6DK] summary insertion point changed")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6DK XACT RELEASE ORIGIN: pretrace_reports=%u previous=%08X object=%08X ref=%u esp=%08X lookup_reports=%u lookup_caller=%08X lookup_esp=%08X",\n'
        f'{indent}    (unsigned int)s_phase6dkPretraceReports,\n'
        f'{indent}    (unsigned int)s_phase6dkPretracePrevious,\n'
        f'{indent}    (unsigned int)s_phase6dkPretraceObject,\n'
        f'{indent}    (unsigned int)s_phase6dkPretraceRef,\n'
        f'{indent}    (unsigned int)s_phase6dkPretraceEsp,\n'
        f'{indent}    (unsigned int)s_phase6dkLookupReports,\n'
        f'{indent}    (unsigned int)s_phase6dkLookupCaller,\n'
        f'{indent}    (unsigned int)s_phase6dkLookupEsp);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DK] expected one 6DJ build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DJ", "PHASE 6DK")
        .replace("Phase 6DJ", "Phase 6DK")
        .replace('"P6DJ ', '"P6DK ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DK] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DJ", "PHASE 6DK")
        .replace("Phase 6DJ", "Phase 6DK")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6dk_base")
    p6bl = load(args.phase6bl_emitter, "phase6dk_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6dj-manifest.json"
    for p in (main_path, env_path, manifest_path):
        if not p.exists():
            raise SystemExit(f"[Phase6DK] missing input: {p}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DK] cached 6DJ identity mismatch")

    dj = manifest.get("phase6dj_xact_indirect_release") or {}
    if (
        dj.get("target") != "0x0027F2C2"
        or dj.get("probe_only") is not True
        or dj.get("dispatch_semantics_changed") is not False
        or dj.get("refcount_changed_by_probe") is not False
        or dj.get("destructor_suppressed") is not False
        or dj.get("free_suppressed") is not False
    ):
        raise SystemExit("[Phase6DK] inherited 6DJ policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6DJ XACT INDIRECT RELEASE:",
        "P6DJ XACT RELEASE ENTRY:",
        "P6DJ XACT RELEASE AFTER:",
        "sub_0027F2C2",
        "#pragma warning(disable:4146)",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DK] inherited marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = instrument_target_pretrace(main_text)
    main_text = instrument_pack_lookup(main_text)

    state_pos = main_text.find("static DWORD s_phase6dkLookupReports = 0u;")
    lookup_pos = main_text.find(
        "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    )
    if state_pos < 0 or lookup_pos < 0 or state_pos > lookup_pos:
        raise SystemExit(
            "[Phase6DK] compile-order gate failed: 6DK lookup state must precede pack lookup"
        )

    main_text = insert_summary(main_text)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "P6DK XACT RELEASE PRETRACE:",
        "P6DK XACT RELEASE PACK LOOKUP:",
        "P6DK XACT RELEASE ORIGIN:",
        "P6DK XACT RELEASE ENTRY:",
        "P6DK XACT RELEASE AFTER:",
        "#pragma warning(disable:4146)",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DK] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6DK", "build_tag": BUILD_TAG})
    manifest["phase6dk_xact_release_pretrace"] = {
        "target": "0x0027F2C2",
        "phase6di_hardware": {
            "object": "0x01B5C320",
            "ref_before": 1,
            "ref_after": 0,
        },
        "phase6dj_hardware": {
            "instrumented_icall_sites": 9035,
            "indirect_release_reports": 0,
            "interpretation": "release did not enter through translated ICALL_SAFE",
        },
        "pretrace_probe": True,
        "pack_lookup_probe": True,
        "probe_only": True,
        "dispatch_semantics_changed": False,
        "refcount_changed_by_probe": False,
        "destructor_suppressed": False,
        "free_suppressed": False,
        "guest_memory_semantics_changed": False,
        "generated_c4146_scope_inherited": True,
        "execution_budget_inherited": 64000000,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }
    (args.out_dir / "phase6dk-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[Phase6DK] emitter revision: {EMITTER_REVISION}")
    print("[Phase6DK] target release: 0027F2C2")
    print("[Phase6DK] pretrace probe installed before target RECOMP_TRACE_FUNC")
    print("[Phase6DK] packed lookup probe installed for target 0027F2C2")
    print("[Phase6DK] C4146 generated-code cleanup inherited from 6DJ")
    print("[Phase6DK] refcount/destructor/free/dispatch semantics unchanged")
    print("[Phase6DK] money line:")
    print("[Phase6DK]   P6DK XACT RELEASE PRETRACE: previous=... target=0027F2C2 object=01B5C320 ref=1")
    print("[Phase6DK] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

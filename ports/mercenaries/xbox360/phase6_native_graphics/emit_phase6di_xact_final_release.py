#!/usr/bin/env python3
r"""Phase 6DI: identify the XACT final Release caller.

6DF hardware proved sub_0027F194 clears global 0x0028836C and frees the
XACT root. 6DH proved the ownership chain:
    sub_0027F2C2: --root->refcount; if zero -> sub_0027F282(1)
    sub_0027F282: deleting destructor -> sub_0027F194
and only two direct translated callers of sub_0027F2C2 exist:
    sub_00280062
    sub_00282A9B

6DI tags those two call sites and instruments the refcount decrement. It does
not change the refcount, branch, destructor, free, or guest-memory semantics.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6DF-XACT-GLOBAL-0028836C-WRITE-SITE-20261026-A"
BUILD_TAG = "P6DI-XACT-FINAL-RELEASE-CALLER-20261026-A"
COOKIE_OLD = "phase6df_env_build_cookie"
COOKIE_NEW = "phase6di_env_build_cookie"
EMITTER_REVISION = "6DI-R1"

CALLERS = (
    ("sub_00280062", 0x00280062, 1),
    ("sub_00282A9B", 0x00282A9B, 2),
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DI] could not load helper {path}")
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
            f"[Phase6DI] expected exactly one definition for {name}, found {len(matches)}"
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
    raise SystemExit(f"[Phase6DI] unterminated function {name}")


def replace_once_in_function(text: str, name: str, old: str, new: str) -> str:
    start, end = function_span(text, name)
    body = text[start:end]
    count = body.count(old)
    if count != 1:
        raise SystemExit(
            f"[Phase6DI] expected one target in {name}, found {count}: {old!r}"
        )
    body = body.replace(old, new, 1)
    return text[:start] + body + text[end:]


def install_support(text: str) -> str:
    marker = '#pragma optimize("", off)\n'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DI] translated-body insertion marker missing")
    block = r'''
static DWORD s_phase6diReleaseCallSite = 0u;
static DWORD s_phase6diReleaseCaller = 0u;
static DWORD s_phase6diReleaseEntries = 0u;
static DWORD s_phase6diReleaseZeroes = 0u;
static DWORD s_phase6diLastObject = 0u;
static DWORD s_phase6diLastBefore = 0u;
static DWORD s_phase6diLastAfter = 0u;

static void phase6di_release_callsite(
    DWORD site,
    DWORD caller,
    uint32_t object,
    uint32_t before)
{
    char line[512];
    s_phase6diReleaseCallSite = site;
    s_phase6diReleaseCaller = caller;
    s_phase6diLastObject = object;
    s_phase6diLastBefore = before;
    sprintf(
        line,
        "P6DI XACT RELEASE CALLER: site=%u caller=%08X object=%08X ref_before=%u esp=%08X eax=%08X ecx=%08X edx=%08X esi=%08X edi=%08X",
        (unsigned int)site,
        (unsigned int)caller,
        (unsigned int)object,
        (unsigned int)before,
        (unsigned int)esp,
        (unsigned int)eax,
        (unsigned int)ecx,
        (unsigned int)edx,
        (unsigned int)esi,
        (unsigned int)edi);
    trace(line);
}

static void phase6di_release_before(
    uint32_t object,
    uint32_t before)
{
    char line[512];
    ++s_phase6diReleaseEntries;
    s_phase6diLastObject = object;
    s_phase6diLastBefore = before;
    sprintf(
        line,
        "P6DI XACT RELEASE ENTRY: site=%u caller=%08X object=%08X ref_before=%u entries=%u esp=%08X",
        (unsigned int)s_phase6diReleaseCallSite,
        (unsigned int)s_phase6diReleaseCaller,
        (unsigned int)object,
        (unsigned int)before,
        (unsigned int)s_phase6diReleaseEntries,
        (unsigned int)esp);
    trace(line);
}

static void phase6di_release_after(
    uint32_t object,
    uint32_t after)
{
    char line[512];
    s_phase6diLastObject = object;
    s_phase6diLastAfter = after;
    if (after == 0u)
        ++s_phase6diReleaseZeroes;
    sprintf(
        line,
        "P6DI XACT RELEASE AFTER: site=%u caller=%08X object=%08X ref_after=%u zeroes=%u esp=%08X",
        (unsigned int)s_phase6diReleaseCallSite,
        (unsigned int)s_phase6diReleaseCaller,
        (unsigned int)object,
        (unsigned int)after,
        (unsigned int)s_phase6diReleaseZeroes,
        (unsigned int)esp);
    trace(line);
}

static void phase6di_release_clear_site(void)
{
    s_phase6diReleaseCallSite = 0u;
    s_phase6diReleaseCaller = 0u;
}

'''
    return text[:pos] + block + text[pos:]


def instrument_callers(text: str) -> str:
    call = "PUSH32(esp, 0); sub_0027F2C2(); /* call 0x0027F2C2 */"
    for name, va, site in CALLERS:
        start, end = function_span(text, name)
        body = text[start:end]
        if body.count(call) != 1:
            raise SystemExit(
                f"[Phase6DI] expected one F2C2 call in {name}, found {body.count(call)}"
            )
        # Both proven direct callers push the global root immediately before F2C2.
        root_push = "PUSH32(esp, GUEST_READ32(0x28836C));\n"
        idx = body.find(call)
        push_idx = body.rfind(root_push, 0, idx)
        if push_idx < 0 or idx - push_idx > 320:
            raise SystemExit(
                f"[Phase6DI] {name} lost immediate global-root push before F2C2"
            )

        # Evaluate the root once for telemetry without changing the pushed argument.
        probe = (
            f"phase6di_release_callsite({site}u, 0x{va:08X}u, "
            f"GUEST_READ32(0x28836C), "
            f"(GUEST_READ32(0x28836C) ? "
            f"GUEST_READ32(GUEST_READ32(0x28836C) + 8) : 0u));\n"
        )
        body = body[:push_idx] + probe + body[push_idx:]
        body = body.replace(
            call,
            call + "\n    phase6di_release_clear_site();",
            1,
        )
        text = text[:start] + body + text[end:]
    return text


def instrument_release(text: str) -> str:
    name = "sub_0027F2C2"
    old = "GUEST_WRITE32(ecx + 8, GUEST_READ32(ecx + 8) - 1);"
    new = (
        "phase6di_release_before(ecx, GUEST_READ32(ecx + 8));\n"
        "    GUEST_WRITE32(ecx + 8, GUEST_READ32(ecx + 8) - 1);\n"
        "    phase6di_release_after(ecx, GUEST_READ32(ecx + 8));"
    )
    return replace_once_in_function(text, name, old, new)


def insert_summary(text: str) -> str:
    marker = "P6DF XACT GLOBAL WRITE SITE SUMMARY:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DI] inherited 6DF summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6DI] summary insertion point changed")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6DI XACT FINAL RELEASE: entries=%u zeroes=%u last_site=%u last_caller=%08X last_object=%08X last_before=%u last_after=%u",\n'
        f'{indent}    (unsigned int)s_phase6diReleaseEntries,\n'
        f'{indent}    (unsigned int)s_phase6diReleaseZeroes,\n'
        f'{indent}    (unsigned int)s_phase6diReleaseCallSite,\n'
        f'{indent}    (unsigned int)s_phase6diReleaseCaller,\n'
        f'{indent}    (unsigned int)s_phase6diLastObject,\n'
        f'{indent}    (unsigned int)s_phase6diLastBefore,\n'
        f'{indent}    (unsigned int)s_phase6diLastAfter);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DI] expected one 6DF build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DF", "PHASE 6DI")
        .replace("Phase 6DF", "Phase 6DI")
        .replace('"P6DF ', '"P6DI ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DI] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DF", "PHASE 6DI")
        .replace("Phase 6DF", "Phase 6DI")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6di_base")
    p6bl = load(args.phase6bl_emitter, "phase6di_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6df-manifest.json"
    for p in (main_path, env_path, manifest_path):
        if not p.exists():
            raise SystemExit(f"[Phase6DI] missing input: {p}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DF" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DI] cached 6DF identity mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6DF XACT GLOBAL WRITE SITE:",
        "P6DF XACT GLOBAL WRITE SITE SUMMARY:",
        "sub_0027F2C2",
        "sub_0027F282",
        "sub_0027F194",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DI] inherited marker missing: {marker}")

    main_text = install_support(main_text)
    main_text = instrument_callers(main_text)
    main_text = instrument_release(main_text)
    main_text = insert_summary(main_text)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "P6DI XACT RELEASE CALLER:",
        "P6DI XACT RELEASE ENTRY:",
        "P6DI XACT RELEASE AFTER:",
        "P6DI XACT FINAL RELEASE:",
        "phase6di_release_callsite(1u, 0x00280062u",
        "phase6di_release_callsite(2u, 0x00282A9Bu",
        "phase6di_release_before(ecx",
        "P6DI XACT GLOBAL WRITE SITE:",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DI] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6DI", "build_tag": BUILD_TAG})
    manifest["phase6di_xact_final_release"] = {
        "release_function": "0x0027F2C2",
        "deleting_destructor": "0x0027F282",
        "destructor": "0x0027F194",
        "global": "0x0028836C",
        "candidate_callers": ["0x00280062", "0x00282A9B"],
        "probe_only": True,
        "refcount_changed_by_probe": False,
        "destructor_suppressed": False,
        "free_suppressed": False,
        "guest_memory_semantics_changed": False,
        "execution_budget_inherited": 64000000,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }
    (args.out_dir / "phase6di-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[Phase6DI] emitter revision: {EMITTER_REVISION}")
    print("[Phase6DI] release function: 0027F2C2")
    print("[Phase6DI] candidate caller site 1: 00280062")
    print("[Phase6DI] candidate caller site 2: 00282A9B")
    print("[Phase6DI] refcount/destructor/free semantics unchanged")
    print("[Phase6DI] money line:")
    print("[Phase6DI]   P6DI XACT RELEASE AFTER: site=... caller=... object=01B5C320 ref_after=0")
    print("[Phase6DI] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

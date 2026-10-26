#!/usr/bin/env python3
r"""Phase 6DJ: identify the indirect caller that performs the final XACT Release.

6DI hardware proved:
  object 0x01B5C320 refcount 1 -> 0 inside sub_0027F2C2
  site=0/caller=0, so neither known direct call site performed the release.
Therefore the final Release reaches sub_0027F2C2 through RECOMP_ICALL_SAFE.

6DJ wraps translated ICALL_SAFE sites without changing dispatch semantics and
reports the owning translated function whenever the runtime target is exactly
0x0027F2C2.

Also scopes MSVC C4146 suppression to generated translated code only. The
translator intentionally uses modulo-2^32 unsigned negation; native/support
code keeps C4146 enabled.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6DI-XACT-FINAL-RELEASE-CALLER-20261026-A"
BUILD_TAG = "P6DJ-XACT-INDIRECT-RELEASE-CALLER-20261026-A"
COOKIE_OLD = "phase6di_env_build_cookie"
COOKIE_NEW = "phase6dj_env_build_cookie"
EMITTER_REVISION = "6DJ-R1"
TARGET = 0x0027F2C2


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DJ] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def translated_bounds(text: str) -> tuple[int, int]:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off = text.find(off_marker)
    if off < 0:
        raise SystemExit("[Phase6DJ] optimize-off marker missing")
    start = off + len(off_marker)
    end = text.find(on_marker, start)
    if end < 0:
        raise SystemExit("[Phase6DJ] optimize-on marker missing")
    return start, end


def install_support(text: str) -> str:
    marker = '#pragma optimize("", off)\n'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DJ] support insertion marker missing")
    block = r'''
static DWORD s_phase6djIndirectReleaseReports = 0u;
static DWORD s_phase6djLastIndirectCaller = 0u;
static DWORD s_phase6djLastIndirectTarget = 0u;
static DWORD s_phase6djLastIndirectEsp = 0u;

static void phase6dj_icall_probe(
    DWORD caller,
    uint32_t target,
    uint32_t savedEsp)
{
    if (target == 0x0027F2C2u)
    {
        char line[512];
        ++s_phase6djIndirectReleaseReports;
        s_phase6djLastIndirectCaller = caller;
        s_phase6djLastIndirectTarget = target;
        s_phase6djLastIndirectEsp = savedEsp;
        sprintf(
            line,
            "P6DJ XACT INDIRECT RELEASE CALLER: caller=%08X target=%08X saved_esp=%08X live_esp=%08X object=%08X ref=%u eax=%08X ecx=%08X edx=%08X esi=%08X edi=%08X reports=%u",
            (unsigned int)caller,
            (unsigned int)target,
            (unsigned int)savedEsp,
            (unsigned int)esp,
            (unsigned int)GUEST_READ32(0x0028836Cu),
            (unsigned int)(GUEST_READ32(0x0028836Cu)
                ? GUEST_READ32(GUEST_READ32(0x0028836Cu) + 8u) : 0u),
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)esi,
            (unsigned int)edi,
            (unsigned int)s_phase6djIndirectReleaseReports);
        trace(line);
    }
}

#define PHASE6DJ_ICALL_SAFE(caller, target_expr, saved_esp_expr) \
    do { \
        uint32_t phase6dj_target_once = (uint32_t)(target_expr); \
        uint32_t phase6dj_saved_esp_once = (uint32_t)(saved_esp_expr); \
        phase6dj_icall_probe( \
            (DWORD)(caller), phase6dj_target_once, phase6dj_saved_esp_once); \
        RECOMP_ICALL_SAFE(phase6dj_target_once, phase6dj_saved_esp_once); \
    } while (0)

'''
    return text[:pos] + block + text[pos:]


def instrument_translated_icalls(text: str) -> tuple[str, int]:
    start, end = translated_bounds(text)
    body = text[start:end]

    needle = "RECOMP_ICALL_SAFE("
    count = body.count(needle)
    if count < 1:
        raise SystemExit("[Phase6DJ] no translated ICALL_SAFE sites found")

    # phase6df_function_va was installed into every translated function by 6DF.
    if "phase6df_function_va" not in body:
        raise SystemExit("[Phase6DJ] inherited per-function VA provenance missing")

    body = body.replace(
        needle,
        "PHASE6DJ_ICALL_SAFE(phase6df_function_va, ",
    )

    # C4146 is a known generated-code nuisance: the translated x86 NEG model
    # intentionally relies on uint32 modulo wrap. Keep the warning enabled for
    # all hand-written/native support code and suppress it only for translated
    # generated bodies.
    body = (
        "#pragma warning(push)\n"
        "#pragma warning(disable:4146) /* generated uint32 x86 NEG semantics */\n"
        + body
        + "\n#pragma warning(pop)\n"
    )

    return text[:start] + body + text[end:], count


def insert_summary(text: str, icall_sites: int) -> str:
    marker = "P6DI XACT FINAL RELEASE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DJ] inherited 6DI final-release summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6DJ] summary insertion point changed")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6DJ XACT INDIRECT RELEASE: reports=%u caller=%08X target=%08X saved_esp=%08X instrumented_icalls={icall_sites}",\n'
        f'{indent}    (unsigned int)s_phase6djIndirectReleaseReports,\n'
        f'{indent}    (unsigned int)s_phase6djLastIndirectCaller,\n'
        f'{indent}    (unsigned int)s_phase6djLastIndirectTarget,\n'
        f'{indent}    (unsigned int)s_phase6djLastIndirectEsp);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DJ] expected one 6DI build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DI", "PHASE 6DJ")
        .replace("Phase 6DI", "Phase 6DJ")
        .replace('"P6DI ', '"P6DJ ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DJ] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DI", "PHASE 6DJ")
        .replace("Phase 6DI", "Phase 6DJ")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6dj_base")
    p6bl = load(args.phase6bl_emitter, "phase6dj_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6di-manifest.json"
    for p in (main_path, env_path, manifest_path):
        if not p.exists():
            raise SystemExit(f"[Phase6DJ] missing input: {p}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DI" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DJ] cached 6DI identity mismatch")

    di = manifest.get("phase6di_xact_final_release") or {}
    if (
        di.get("release_function") != "0x0027F2C2"
        or di.get("probe_only") is not True
        or di.get("refcount_changed_by_probe") is not False
        or di.get("destructor_suppressed") is not False
        or di.get("free_suppressed") is not False
    ):
        raise SystemExit("[Phase6DJ] inherited 6DI policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6DI XACT RELEASE ENTRY:",
        "P6DI XACT RELEASE AFTER:",
        "P6DI XACT FINAL RELEASE:",
        "P6DI XACT GLOBAL WRITE SITE:",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DJ] inherited marker missing: {marker}")

    main_text = install_support(main_text)
    main_text, icall_sites = instrument_translated_icalls(main_text)
    main_text = insert_summary(main_text, icall_sites)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "P6DJ XACT INDIRECT RELEASE CALLER:",
        "P6DJ XACT INDIRECT RELEASE:",
        "PHASE6DJ_ICALL_SAFE(phase6df_function_va,",
        "#pragma warning(disable:4146)",
        "P6DJ XACT RELEASE ENTRY:",
        "P6DJ XACT RELEASE AFTER:",
        "P6DJ XACT GLOBAL WRITE SITE:",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DJ] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6DJ", "build_tag": BUILD_TAG})
    manifest["phase6dj_xact_indirect_release"] = {
        "target": "0x0027F2C2",
        "phase6di_hardware": {
            "object": "0x01B5C320",
            "ref_before": 1,
            "ref_after": 0,
            "direct_site": 0,
            "direct_caller": "0x00000000",
            "interpretation": "final release arrived through indirect dispatch",
        },
        "instrumented_icall_sites": icall_sites,
        "probe_only": True,
        "dispatch_semantics_changed": False,
        "refcount_changed_by_probe": False,
        "destructor_suppressed": False,
        "free_suppressed": False,
        "guest_memory_semantics_changed": False,
        "generated_c4146_scope_only": True,
        "native_c4146_still_enabled": True,
        "execution_budget_inherited": 64000000,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }
    (args.out_dir / "phase6dj-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[Phase6DJ] emitter revision: {EMITTER_REVISION}")
    print(f"[Phase6DJ] translated ICALL_SAFE sites wrapped={icall_sites}")
    print("[Phase6DJ] runtime target filter: 0027F2C2")
    print("[Phase6DJ] C4146: disabled only inside generated translated body")
    print("[Phase6DJ] refcount/destructor/free/dispatch semantics unchanged")
    print("[Phase6DJ] money line:")
    print("[Phase6DJ]   P6DJ XACT INDIRECT RELEASE CALLER: caller=... target=0027F2C2 object=01B5C320 ref=1")
    print("[Phase6DJ] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""K1: hardware-observed SECOND retail 0028CAA0 presentation contract.

User-local source only. Keeps all 64 TrueTUs, changes at most one translated TU
and derives main.cpp. Performs a real native Xenos Reset before publishing
second CreateDevice success. No fake S_OK, no fake guest pixels. Unexpected
parameters, a missing live device, reset failure and unsafe ABI stay fenced.

Xbox multisample 0x1121 is the original-Xbox 2-sample quincunx pattern. Xenos
D3DMULTISAMPLE_2_SAMPLES preserves sample count but NOT the quincunx resolve
filter; the approximation is explicitly logged instead of misrepresented.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

PARENT_MARK = "P6K1-TEXT-DIRECT-20261103"
MARK = "P6K1-D3D-SECOND-CREATE-20261103"
TARGET = "sub_0028CAA0"
HARD_FENCE = "P6DQ ROCKET HARD STOP"
OLD_GUARD = "        backBuffers != 1u ||\n        swap != 1u ||"
NEW_GUARD = (
    "        !((backBuffers == 1u && multisample == 0x0011u) ||\n"
    "          (backBuffers == 2u && multisample == 0x1121u)) ||\n"
    "        swap != 1u ||"
)
OLD_PUBLISH = "    s_phase6afGuestDevice = 0x00299380u;\n    GUEST_WRITE32(out, s_phase6afGuestDevice);"
SECOND_BRANCH = r'''    /* Retail second request: same device/out identity, real native Reset.
     * Never publish success on a merely-observed presentation request.
     */
    if (backBuffers == 2u)
    {
        if (s_phase6afCreateDeviceBridgeCount != 1u ||
            s_phase6afGuestDevice != 0x00299380u ||
            GUEST_READ32(out) != 0x00299380u)
        {
            trace("K1D3D SECOND: first-device ownership/out-pointer contract drift");
            phase4c_escape(PHASE4C_BOUNDARY_RENDERER_FATAL, 0x80070057u, c);
            return;
        }
        if (s_accessFault)
        {
            phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, out, c);
            return;
        }
        if (!phase6k1_native_xenos_reconfigure(backBuffers, multisample))
        {
            trace("K1D3D SECOND: native Reset failed; refusing guest success");
            phase4c_escape(PHASE4C_BOUNDARY_RENDERER_FATAL, 0x80004005u, c);
            return;
        }
    }

'''
NATIVE_HELPER = r'''/* Hardware-owned Xenos device: reconfigure swapchain, not a fake guest
 * success. Original Xbox quincunx 0x1121 maps to 2 native MSAA samples;
 * native resolve is not bit-exact quincunx.
 */
int phase6k1_native_xenos_reconfigure(uint32_t buffers, uint32_t xboxMs)
{
    D3DPRESENT_PARAMETERS p;
    HRESULT hr;
    char line[256];

    if (buffers != 2u || xboxMs != 0x1121u || !phase6af_native_xenos_ready())
    {
        trace("K1D3D SECOND: unsupported mode or native device unavailable");
        return 0;
    }

    ZeroMemory(&p, sizeof(p));
    p.BackBufferWidth = 640u;
    p.BackBufferHeight = 480u;
    p.BackBufferFormat = D3DFMT_A8R8G8B8;
    p.BackBufferCount = 2u;
    p.MultiSampleType = D3DMULTISAMPLE_2_SAMPLES;
    p.MultiSampleQuality = 0u;
    p.SwapEffect = D3DSWAPEFFECT_DISCARD;
    p.hDeviceWindow = NULL;
    p.Windowed = FALSE;
    p.EnableAutoDepthStencil = FALSE;
    p.AutoDepthStencilFormat = D3DFMT_UNKNOWN;
    p.Flags = 0u;
    p.FullScreen_RefreshRateInHz = 0u;
    p.PresentationInterval = D3DPRESENT_INTERVAL_ONE;

    trace("K1D3D SECOND: native Xenos Reset begin: 640x480 buffers=2 samples=2; quincunx resolve approximated");
    hr = D3DDevice_Reset(s_phase6bXenosDevice, &p);
    sprintf(line, "K1D3D SECOND: native Reset HRESULT=%08X", (unsigned int)hr);
    trace(line);
    if (FAILED(hr))
        return 0;

    trace("K1D3D SECOND: native Xenos Reset PASS; guest return may proceed");
    return 1;
}

'''
PROTOTYPE = "int phase6k1_native_xenos_reconfigure(uint32_t buffers, uint32_t xboxMs);\n"
DEFINITION = re.compile(r"(?m)^(?:static\s+)?void\s+sub_0028CAA0\s*\(\s*void\s*\)\s*\{")


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def one(haystack: str, needle: str, label: str) -> None:
    count = haystack.count(needle)
    if count != 1:
        raise ValueError(f"{label}: expected one, found {count}")


# The 64-TrueTU emitter exports runtime support helpers (strips static)
# and can separate their definitions. Match the actual body, not legacy
# adjacency to phase6b_xenos_create. This is intentionally NOT a loose
# string-token search: a declaration or comment cannot become the anchor.
READY_DEFINITION = re.compile(
    r'(?m)^(?:static[ \\t]+)?int[ \\t]+phase6af_native_xenos_ready'
    r'[ \\t]*\\([ \\t]*void[ \\t]*\\)[ \\t]*\\n'
    r'[ \\t]*\\{[ \\t]*\\n'
    r'[ \\t]*return[ \\t]+s_phase6bXenosReady[ \\t]*&&[ \\t]*'
    r's_phase6bXenosDevice[ \\t]*!=[ \\t]*NULL;[ \\t]*\\n'
    r'[ \\t]*\\}'
)


def native_main(parent: str) -> str:
    one(parent, PARENT_MARK, "unique K1 TEXT parent marker")
    if MARK in parent:
        raise ValueError("K1 D3D second patch already installed")
    if HARD_FENCE not in parent:
        raise ValueError("Inherited renderer/fault hard fence missing")
    matches = list(READY_DEFINITION.finditer(parent))
    if len(matches) != 1:
        nearby = []
        for m in list(re.finditer("phase6af_native_xenos_ready", parent))[:6]:
            nearby.append(repr(parent[max(0, m.start()-60):m.start()+130]))
        raise ValueError(
            f"native Xenos ready definition missing/duplicated: matches={len(matches)} "
            f"references={len(list(re.finditer('phase6af_native_xenos_ready', parent)))} "
            f"contexts={nearby}"
        )
    at = matches[0].end()
    return parent[:at] + "\n\n" + NATIVE_HELPER + parent[at:]


def bridge_source(source: str, is_shard: bool) -> str:
    if len(DEFINITION.findall(source)) != 1:
        raise ValueError("Expected unique real translated sub_0028CAA0 definition")
    one(source, OLD_GUARD, "6AF original CreateDevice backbuffer guard")
    one(source, OLD_PUBLISH, "6AF original guest device publish")
    if "Phase 6AF CreateDevice contract mismatch" not in source and \
       "Phase 6DQ CreateDevice contract mismatch" not in source:
        raise ValueError("Original CreateDevice mismatch hard fence missing")
    source = source.replace(OLD_GUARD, NEW_GUARD, 1)
    source = source.replace(OLD_PUBLISH, SECOND_BRANCH + OLD_PUBLISH, 1)
    if is_shard:
        header = re.compile(r'(?m)^(#include\s+["<]translated_runtime\.h[">][^\n]*\n)')
        matches = list(header.finditer(source))
        if len(matches) != 1:
            raise ValueError("Translated TU runtime include missing/duplicated")
        pos = matches[0].end()
        source = source[:pos] + PROTOTYPE + source[pos:]
    return source


def check_eol(src: str, label: str) -> tuple[str, str]:
    if "\r" in src.replace("\r\n", ""):
        raise ValueError(label + ": mixed/invalid line endings")
    return src.replace("\r\n", "\n"), "\r\n" if "\r\n" in src else "\n"


def patch(main: str, shards: dict[str, str]) -> tuple[str, dict[str, str], str]:
    main_lf, main_nl = check_eol(main, "main")
    source_rows = {"main.cpp": main_lf}
    endings = {"main.cpp": main_nl}
    for name, source in shards.items():
        source_rows[name], endings[name] = check_eol(source, name)
    holders = [
        name for name, source in source_rows.items()
        if OLD_GUARD in source and OLD_PUBLISH in source
    ]
    if len(holders) != 1:
        raise ValueError("Real CreateDevice bridge must reside in exactly one file: " + repr(holders))
    owner = holders[0]
    source_rows["main.cpp"] = native_main(source_rows["main.cpp"])
    source_rows[owner] = bridge_source(source_rows[owner], is_shard=(owner != "main.cpp"))
    source_rows["main.cpp"] = source_rows["main.cpp"].replace(
        PARENT_MARK, PARENT_MARK + " | " + MARK, 1
    )
    if source_rows["main.cpp"].count(NATIVE_HELPER) != 1 or \
       source_rows[owner].count("K1D3D SECOND: native Reset failed") != 1:
        raise ValueError("Native reset implementation or guest hard-fence lost")
    return (source_rows.pop("main.cpp").replace("\n", endings["main.cpp"]),
            {n: t.replace("\n", endings[n]) for n, t in source_rows.items()},
            owner)


def test() -> None:
    main = (
        PARENT_MARK + "\n" + HARD_FENCE + "\n"
        + "static int phase6af_native_xenos_ready(void)\n"
          "{\n    return s_phase6bXenosReady && s_phase6bXenosDevice != NULL;\n"
          "}\n\nstatic int phase6b_xenos_create(void)\n"
    )
    bridge = (
        '#include "translated_runtime.h"\n'
        'void sub_0028CAA0(void)\n{\n'
        + OLD_GUARD + '\n'
        + 'trace("Phase 6DQ CreateDevice contract mismatch: refusing generalized device fabrication");\n'
        + OLD_PUBLISH + '\n}\n'
    )
    for in_main in (False, True):
        for crlf in (False, True):
            for true_tu_export in (False, True):
                # The real 64-TU source has external runtime linkage, and its
                # next function is not guaranteed to be phase6b_xenos_create.
                convert = lambda s: s.replace("\n", "\r\n") if crlf else s
                m = main + (bridge if in_main else "")
                if true_tu_export:
                    m = m.replace("static int phase6af_native_xenos_ready(void)",
                                  "int phase6af_native_xenos_ready(void)")
                    m = m.replace("static int phase6b_xenos_create(void)",
                                  "int phase6b_xenos_create(void)")
                    m = m.replace("int phase6b_xenos_create(void)",
                                  "void unrelated_runtime_support(void);\n"
                                  "int phase6b_xenos_create(void)")
                ss = {"translated_001.cpp": "#include \"translated_runtime.h\"\n"} if in_main \
                     else {"translated_001.cpp": bridge}
                res_main, res_shards, owner = patch(
                    convert(m), {k: convert(v) for k,v in ss.items()}
                )
                assert owner == ("main.cpp" if in_main else "translated_001.cpp")
                assert res_main.count("D3DDevice_Reset(") == 1
                assert res_shards["translated_001.cpp"].count(PROTOTYPE.strip()) == (0 if in_main else 1)
                edited = res_main if in_main else res_shards["translated_001.cpp"]
                assert "backBuffers == 2u && multisample == 0x1121u" in edited
                assert "if (!phase6k1_native_xenos_reconfigure" in edited
                assert "GUEST_READ32(out)" in edited
                assert res_main.count("int phase6k1_native_xenos_reconfigure(") == 1
                try:
                    patch(res_main, res_shards)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Double patch accepted")
    for bad in (main.replace(HARD_FENCE, ""), main.replace(PARENT_MARK, "")):
        try:
            patch(bad, {"translated_001.cpp": bridge})
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe parent accepted")
    print("[K1D3D] SELFTEST PASS: exact source bridge, 2-buffer quincunx guard, native Reset, hard fences, CRLF, TrueTU owner")


def write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_bytes() != data:
            raise ValueError("Stale staged output differs; refusing overwrite: " + str(path))
    elif path.exists():
        raise ValueError("Expected regular file output: " + str(path))
    else:
        path.write_bytes(data)


def stage(a: argparse.Namespace) -> None:
    if not a.parent_main.is_file() or not a.shards.is_dir():
        raise ValueError("Missing K1 TEXT main or original TrueTUs")
    if a.out_main.resolve() == a.parent_main.resolve() or \
       a.out_shards.resolve() == a.shards.resolve():
        raise ValueError("Refuse in-place changes to original source")
    names = sorted(f.name for f in a.shards.glob("translated_???.cpp"))
    if len(names) != 64 or len(set(names)) != 64:
        raise ValueError(f"Expected 64 exact translated_???.cpp files, found {len(names)}")
    if not (a.shards / "translated_runtime.h").is_file():
        raise ValueError("Missing original runtime header")

    parent_blob = a.parent_main.read_bytes()
    blobs = {name: (a.shards / name).read_bytes() for name in names}
    main_text, changed, owner = patch(
        parent_blob.decode("utf-8"),
        {name: blob.decode("utf-8") for name, blob in blobs.items()}
    )
    main_out = main_text.encode("utf-8")
    shard_out = {n: changed[n].encode("utf-8") for n in names}
    changed_names = [n for n in names if blobs[n] != shard_out[n]]
    if (owner == "main.cpp" and changed_names) or \
       (owner != "main.cpp" and changed_names != [owner]):
        raise ValueError("Only bridge-owner TrueTU may change")
    if HARD_FENCE not in main_text or "K1PFIFO DMA_PUT READ32:" not in main_text:
        raise ValueError("Inherited PFIFO or hard fence lost")

    summary = {
        "status": "K1_D3D_SECOND_SOURCE_ONLY_NO_XDK",
        "parent_main_sha256": sha(parent_blob),
        "next_main_sha256": sha(main_out),
        "parent_shard_sha256": {n: sha(blobs[n]) for n in names},
        "next_shard_sha256": {n: sha(shard_out[n]) for n in names},
        "owner": owner, "shards_count": 64,
        "shards_changed": changed_names, "runtime_header_changed": False,
        "exact_hardware_request": {
            "first": {"buffers": 1, "multisample": "0x0011"},
            "second": {"buffers": 2, "multisample": "0x1121"}
        },
        "native_second_mode": "real Xenos Reset, 640x480, 2 buffers, 2x MSAA",
        "quincunx_filter_exact": False,
        "guest_success_requires_native_reset_pass": True,
        "unknown_configs_fenced": True,
        "hardware_verified": False, "xdk_verified": False,
        "synthetic_guest_pixels": False
    }
    manifest = (json.dumps(summary, indent=2) + "\n").encode("utf-8")
    write_new(a.out_main, main_out)
    for n, blob in shard_out.items():
        write_new(a.out_shards / n, blob)
    write_new(a.out_shards / "translated_runtime.h",
              (a.shards / "translated_runtime.h").read_bytes())
    write_new(a.manifest, manifest)
    if a.parent_main.read_bytes() != parent_blob:
        raise ValueError("Parent main mutated during staging")
    for name in names:
        if (a.shards / name).read_bytes() != blobs[name]:
            raise ValueError("Original TrueTU mutated during staging: " + name)
    print(f"[K1D3D] SOURCE PASS: bridge_owner={owner}; TrueTUs={len(names)} modified={len(changed_names)}")
    print("[K1D3D] Native two-buffer/two-sample Reset required before guest success")
    print("[K1D3D] Quincunx resolve not bit exact; unknown config and failed Reset hard fenced")
    print(f"[K1D3D] Derived main={a.out_main}")
    print("[K1D3D] SOURCE ONLY: XDK/hardware not verified")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    for name in ("parent-main", "shards", "out-main", "out-shards", "manifest"):
        p.add_argument("--" + name, type=Path)
    a = p.parse_args()
    if a.self_test:
        test()
        return
    if not all((a.parent_main, a.shards, a.out_main, a.out_shards, a.manifest)):
        p.error("--parent-main --shards --out-main --out-shards --manifest required")
    stage(a)


if __name__ == "__main__":
    main()

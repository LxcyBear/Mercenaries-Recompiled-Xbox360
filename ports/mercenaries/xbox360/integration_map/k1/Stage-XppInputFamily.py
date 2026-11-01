#!/usr/bin/env python3
"""Stage the two remaining original-Xbox XPP input wrappers in ONE TrueTU batch.

Local-only original guest source; strict hashes/ABI, no source exported.
This is NOT an Xbox run. Unknown MMIO/VP, indirect calls and graphics stay fenced.
The inherited D54AC GetState stage must already have passed its own preflight.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

MARKER = "K1-XPP-INPUT-FAMILY-ONE-BUILD-20261031"
PARENT = "XPP-D54AC-NATIVE-GETSTATE-20261031"
HEADER = '#include "translated_runtime.h"'
SHARD_RE = re.compile(r"translated_\d{3}\.cpp\Z")
DEFINITION = re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})[ \t]*\([ \t]*void[ \t]*\)\s*\{")
CALL = re.compile(r"\bsub_([0-9A-Fa-f]{8})\s*\(")
HELPER = re.compile(r"\b(recomp_[A-Za-z_0-9]+)\s*\(")
RETURN = re.compile(r"\besp\s*\+=\s*(\d+)u?\s*;\s*return\s*;")

# Source digests are from the user's local independent predictive audit;
# originals never become repo content.
TARGETS = (
    {
        "va": 0x002D52C8, "end": 0x002D52D4,
        "sha": "a9291e01162d4dd585b0741bc3f94cc43d57df68d99219510967675fe4108545",
        "helper": "recomp_xinput_close",
        "owner": "translated_005.cpp",
        "ret": 8, "args": 1, "returns_eax": False,
    },
    {
        "va": 0x002D551F, "end": 0x002D5552,
        "sha": "89d0db5daf13dcf73e04c61ea26d2152c014f8c1e27e5692926dff1e9a172dd0",
        "helper": "recomp_xinput_set_state",
        "owner": "translated_027.cpp",
        "ret": 12, "args": 2, "returns_eax": True,
    },
)
NATIVE = r'''/* K1-XPP-INPUT-FAMILY-ONE-BUILD-20261031: real X360 input.
 * XInputClose has no native per-port close; original compat is a no-op.
 * Original XInputSetState feedback is 0x46 bytes, motors at +0x42/+0x44.
 * Never memcpy an X360 struct into original Xbox guest memory.
 */
static void recomp_xinput_close(uint32_t handle)
{
    (void)handle;
}
static uint32_t recomp_xinput_set_state(uint32_t handle,
                                       uint32_t feedback_address)
{
    const uint32_t port=handle-1u;
    if (handle<1u || handle>4u)
        return ERROR_DEVICE_NOT_CONNECTED;
    XINPUT_VIBRATION vibration;
    ZeroMemory(&vibration,sizeof(vibration));
    if (feedback_address>=0x00010000u &&
        feedback_address<=0x04000000u-0x46u)
    {
        vibration.wLeftMotorSpeed=(WORD)GUEST_READ16(feedback_address+0x42u);
        vibration.wRightMotorSpeed=(WORD)GUEST_READ16(feedback_address+0x44u);
    }
    const uint32_t result=(uint32_t)XInputSetState((DWORD)port,&vibration);
    static unsigned trace_count=0u;
    if (++trace_count<=8u)
    {
        char line[160];
        sprintf(line,"XPP XINPUT setstate: handle=%u status=%08X left=%u right=%u",
                (unsigned)handle,(unsigned)result,
                (unsigned)vibration.wLeftMotorSpeed,
                (unsigned)vibration.wRightMotorSpeed);
        trace(line);
    }
    return result;
}
'''

def sha(buf: bytes) -> str:
    return hashlib.sha256(buf).hexdigest()

def nl(s: str) -> str:
    if s.count("\r") != s.count("\r\n"):
        raise ValueError("Mixed newline source")
    return "\r\n" if "\r\n" in s else "\n"

def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("xpp_input_family_local_reader", str(path))
    if spec is None or spec.loader is None:
        raise ValueError("Original source loader not found")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def shape(target: dict) -> re.Pattern:
    args = r"\s*,\s*".join(
        rf"GUEST_READ32\(\s*esp\s*\+\s*{4 + 4*i}u?\s*\)"
        for i in range(target["args"]))
    prefix = r"\beax\s*=\s*" if target["returns_eax"] else r"(?<![\w=])"
    return re.compile(
        prefix + re.escape(target["helper"]) + r"\(\s*" + args
        + rf"\s*\)\s*;\s*esp\s*\+=\s*{target['ret']}u?\s*;\s*return\s*;"
    )

def original(target: dict, item: dict, reader) -> str:
    at = target["va"]
    raw = item["source"]
    if sha(raw.encode("utf-8")) != target["sha"]:
        raise ValueError(f"Retail source hash mismatch at {at:08X}")
    pat = re.compile(rf"(?m)^[ \t]*(?:static[ \t]+)?void\s+sub_{at:08X}\s*\(\s*void\s*\)\s*\{{")
    decl = list(pat.finditer(raw))
    if len(decl) != 1:
        raise ValueError(f"Original function declaration ambiguous at {at:08X}")
    masked = reader.mask_noncode(raw)
    m = pat.search(masked)
    if not m:
        raise ValueError("Original declaration masked away")
    body = masked[m.end():]
    # The original declaration is not a recursive call.
    if CALL.findall(body):
        raise ValueError(f"Unreviewed guest callee in {at:08X}")
    if HELPER.findall(body) != [target["helper"]]:
        raise ValueError(f"Unreviewed host helpers at {at:08X}")
    if len(RETURN.findall(body)) != 1 or RETURN.findall(body) != [str(target["ret"])]:
        raise ValueError(f"Guest stack cleanup mismatch at {at:08X}")
    if len(shape(target).findall(body)) != 1:
        raise ValueError(f"Original stack-arg/EAX ABI mismatch at {at:08X}")
    if len(re.findall(rf"\bRECOMP_TRACE_FUNC\(\s*0x{at:08X}u\s*\)\s*;", masked)) != 1:
        raise ValueError(f"Original trace anchor missing at {at:08X}")
    if re.sub(r"/\*.*?\*/|//[^\n]*", "", raw[:decl[0].start()], flags=re.S).strip():
        raise ValueError("Unexpected original executable prefix")
    # No synthesis: take the original generated body, changing only debugbreak
    # and adding entry/budget probes after its original RECOMP_TRACE_FUNC.
    src = raw[:decl[0].start()] + f"void sub_{at:08X}(void)\n{{" + raw[decl[0].end():]
    lines = []
    probes = 0
    for line in src.splitlines():
        lines.append(line.replace("__debugbreak()", "PHASE4C_DEBUGBREAK()"))
        if re.fullmatch(rf"\s*RECOMP_TRACE_FUNC\(\s*0x{at:08X}u\s*\)\s*;", line):
            probes += 1
            lines += [
                f"    PHASE4C_BUDGET_TICK(0x{at:08X}u);",
                "    {",
                "        static unsigned count=0u;",
                "        if (++count<=8u)",
                "        {",
                "            char msg[128];",
                f'            sprintf(msg,"XPP {at:06X} ENTRY n=%u esp=%08X eax=%08X",',
                "                    (unsigned)count,(unsigned)esp,(unsigned)eax);",
                "            trace(msg);",
                "        }",
                "    }",
            ]
    if probes != 1:
        raise ValueError("Instrumentation anchor drift")
    return "\n".join(lines) + "\n"

def rewrite(text: str, target: dict, host: bool = False):
    at = target["va"]
    fence = f"phase4c_direct_frontier(0x{at:08X}u);"
    count = text.count(fence)
    if count == 0:
        return text, 0
    if not host and HEADER not in text:
        raise ValueError("Guest caller lacks translated runtime header")
    newline = nl(text)
    proto = f"void sub_{at:08X}(void);"
    if proto not in text:
        if HEADER in text:
            text = text.replace(HEADER, HEADER + newline + proto, 1)
        else:
            text = proto + newline + text
    text = text.replace(fence, f"sub_{at:08X}();")
    return text, count

def stage(a):
    for p in (a.shards, a.parent_main, a.parent_manifest,
              a.generated, a.functions, a.emitter):
        if not p.exists():
            raise ValueError("Required user-local input absent: " + str(p))
    parent = json.loads(a.parent_manifest.read_text(encoding="utf-8-sig"))
    if (parent.get("marker") != PARENT
            or parent.get("status") != "SOURCE_CLOSED_STAGED_NO_XDK"
            or parent.get("hardware_target") != "0x002D54AC"
            or parent.get("native_state_buffer_bytes") != 22
            or parent.get("source_return") != "EAX/ESP_PLUS_12_RET8"
            or parent.get("guest_display_calls_injected") is not False
            or parent.get("mmio_fences") != "UNCHANGED"
            or parent.get("hard_fences") != "UNCHANGED"
            or Path(parent.get("staged_directory", "MISSING")).resolve() != a.shards.resolve()
            or Path(parent.get("staged_main", "MISSING")).resolve() != a.parent_main.resolve()
            or sha(a.parent_main.read_bytes()) != parent.get("new_main_sha")):
        raise ValueError("Inherited D54AC manifest/main SHA/provenance failed")
    files = sorted(p for p in a.shards.iterdir() if SHARD_RE.fullmatch(p.name))
    headers = sorted(a.shards.glob("*.h"))
    if len(files) != 64 or not (a.shards / "translated_runtime.h").is_file():
        raise ValueError("Expected exact 64 current TrueTUs and runtime header")
    before = {}
    for p in files + headers:
        expected = parent.get("new_owner_hashes", {}).get(
            p.name, parent.get("original_owner_hashes", {}).get(p.name))
        if not expected or sha(p.read_bytes()) != expected:
            raise ValueError("D54AC owner/hash drift: " + p.name)
        if p in files:
            before[p.name] = p.read_text(encoding="utf-8")
    host = a.parent_main.read_text(encoding="utf-8")
    owner = parent.get("parent_input_owner")
    if owner not in before or before[owner].count("#include <xtl.h>") != 1:
        raise ValueError("Unique inherited native XInput TrueTU owner absent")
    if (sum("XPP D54AC ENTRY" in x for x in before.values()) != 1
            or sum("XPP D52D4 ENTRY" in x for x in before.values()) != 1
            or sum("XPP D5272 ENTRY" in x for x in before.values()) != 1
            or "K1S HALGETVECTOR44 ESI SLOT:" not in before["translated_044.cpp"]
            or "P6DQ-R51-MM173-FRAME-20261029-A" not in host):
        raise ValueError("Inherited controller, stack, host checkpoint missing")
    if any(MARKER in x for x in list(before.values()) + [host]):
        raise ValueError("New family already staged; refuse double insertion")
    defined = set()
    for s in list(before.values()) + [host]:
        defined.update(int(x, 16) for x in DEFINITION.findall(s))
    if any(t["va"] in defined for t in TARGETS):
        raise ValueError("Target already defined; refuse duplicate guest function")
    base = load_module(a.emitter)
    ranges, by_name = base.load_ranges(a.functions)
    generated = base.load_generated(a.generated, by_name)
    originals = {}
    for t in TARGETS:
        rg, item = ranges.get(t["va"]), generated.get(t["va"])
        if not rg or rg["start"] != t["va"] or rg["end"] != t["end"]:
            raise ValueError(f"Original XPP function boundary drift {t['va']:08X}")
        if not item:
            raise ValueError(f"Original generated body missing {t['va']:08X}")
        originals[t["va"]] = original(t, item, base)
    # Only two original callsites (one per target) were discovered in the
    # predictive manifest; refuse any change in their actual location/count.
    altered = dict(before)
    new_host = host
    callsites = {}
    for t in TARGETS:
        total = 0
        owners = []
        for name, current in altered.items():
            revised, count = rewrite(current, t)
            if count:
                owners.append(name)
                altered[name] = revised
                total += count
        new_host, hc = rewrite(new_host, t, host=True)
        total += hc
        if total != 1 or owners != [t["owner"]] or hc:
            raise ValueError(f"Unexpected direct frontier location for {t['va']:08X}: {owners}, count={total}")
        callsites[f"0x{t['va']:08X}"] = owners[0]
    newline = nl(altered[owner])
    anchor = "#include <xtl.h>" + newline
    if altered[owner].count(anchor) != 1:
        raise ValueError("Expected one XDK include anchor in input owner")
    altered[owner] = altered[owner].replace(
        anchor, anchor + NATIVE.replace("\n", newline) + newline, 1)
    for t in TARGETS:
        at = t["va"]
        altered[owner] = (altered[owner].rstrip("\r\n") + newline
                          + newline + f"/* {MARKER} original guest {at:08X} */"
                          + newline + originals[at].replace("\n", newline))
    changed = sorted(name for name in altered if altered[name] != before[name])
    if not 1 <= len(changed) <= 4:
        raise ValueError("TrueTU mutation fanout >4")
    if set(changed) != {owner, "translated_005.cpp", "translated_027.cpp"}:
        raise ValueError("Unexpected changed TrueTU set: " + ",".join(changed))
    for t in TARGETS:
        if sum(len(re.findall(rf"\bvoid sub_{t['va']:08X}\(void\)\s*\{{", text))
               for text in altered.values()) != 1:
            raise ValueError("Guest definition count not unique")
    if (altered[owner].count("GUEST_READ16(feedback_address+0x42u)") != 1
            or altered[owner].count("GUEST_READ16(feedback_address+0x44u)") != 1
            or altered[owner].count("XInputSetState((DWORD)port,&vibration)") != 1):
        raise ValueError("Genuine feedback buffer/native rumble bridge missing")
    if (a.out.resolve() == a.shards.resolve()
            or a.out_main.resolve() == a.parent_main.resolve()
            or a.out.parent == a.shards):
        raise ValueError("Refusing overwrite of last known staged sources")
    # Preserve byte-identical files so VS2017 can reuse every unchanged TU.
    # Reading text normalizes Windows CRLF; never re-encode unchanged shards.
    expected_files = {p.name: (altered[p.name].encode("utf-8") if p.name in changed
                               else p.read_bytes()) for p in files}
    expected_files.update({p.name: p.read_bytes() for p in headers})
    a.out.mkdir(parents=True, exist_ok=True)
    if {p.name for p in a.out.iterdir()} not in (set(), set(expected_files)):
        raise ValueError("Existing output folder incompatible with batch")
    for name, blob in expected_files.items():
        dest = a.out / name
        if dest.exists() and dest.read_bytes() != blob:
            raise ValueError("Refusing overwrite of different staged output: " + name)
        if not dest.exists():
            dest.write_bytes(blob)
    main_bytes = new_host.encode("utf-8")
    a.out_main.parent.mkdir(parents=True, exist_ok=True)
    if a.out_main.exists() and a.out_main.read_bytes() != main_bytes:
        raise ValueError("Host main output drift")
    if not a.out_main.exists():
        a.out_main.write_bytes(main_bytes)
    manifest = {
        "marker": MARKER,
        "status": "SOURCE_CLOSED_STAGED_NO_XDK",
        "parent_marker": PARENT,
        "parent_manifest": str(a.parent_manifest),
        "parent_main_sha256": sha(a.parent_main.read_bytes()),
        "staged_directory": str(a.out.resolve()),
        "staged_main": str(a.out_main.resolve()),
        "new_main_sha": sha(main_bytes),
        "parent_input_owner": owner,
        "target_sha256": {f"0x{t['va']:08X}": t["sha"] for t in TARGETS},
        "original_ret_esp": {f"0x{t['va']:08X}": t["ret"] for t in TARGETS},
        "direct_callsite_owners": callsites,
        "changed_true_tus": changed,
        "new_owner_hashes": {n: sha(expected_files[n]) for n in changed},
        "translated_shards": 64,
        "native_feedback_bytes": 0x46,
        "native_feedback_motor_offsets": [0x42, 0x44],
        "native_close_noop": True,
        "hardware_last_verified": "0x002D54AC",
        "hardware_ticks_last_verified": 27107620,
        "guest_display_calls_injected": False,
        "mmio_fences": "UNCHANGED",
        "hard_fences": "UNCHANGED",
    }
    encoded = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    if a.manifest.exists() and a.manifest.read_bytes() != encoded:
        raise ValueError("Refusing manifest drift")
    if not a.manifest.exists():
        a.manifest.write_bytes(encoded)
    print("[XPP-FAMILY] SOURCE/ABI CLOSED: Close 0x002D52C8 (ret4), SetState 0x002D551F (ret8)")
    print("[XPP-FAMILY] Parent GetState 0x002D54AC preserved; no native struct memcpy")
    print("[XPP-FAMILY] NATIVE rumble feedback: +0x42/+0x44, exact 0x46B guest boundary")
    print("[XPP-FAMILY] TrueTU changes: " + ", ".join(changed))
    print("[XPP-FAMILY] STAGED ONLY. NO XDK, NO Xbox, NO fake presentation.")

def self_test():
    assert len(TARGETS) == 2
    assert [t["end"] - t["va"] for t in TARGETS] == [12, 51]
    assert all(len(t["sha"]) == 64 for t in TARGETS)
    for t in TARGETS:
        body = ("eax = " if t["returns_eax"] else "") + t["helper"] + "(" + ", ".join(
            f"GUEST_READ32(esp + {4 + 4*i}u)" for i in range(t["args"]))
        body += f"); esp += {t['ret']}u; return;"
        assert shape(t).search(body)
        assert not shape(t).search(body.replace(f"esp += {t['ret']}u", "esp += 100u"))
        assert not shape(t).search(body.replace("GUEST_READ32", "GUEST_READ16"))
        for newline in ("\n", "\r\n"):
            before = HEADER + newline + f"void f(void) {{ phase4c_direct_frontier(0x{t['va']:08X}u); }}" + newline
            after, n = rewrite(before, t)
            assert n == 1 and f"sub_{t['va']:08X}();" in after
            again, n = rewrite(after, t)
            assert n == 0 and again == after
    assert NATIVE.count("GUEST_READ16(feedback_address+0x42u)") == 1
    assert NATIVE.count("GUEST_READ16(feedback_address+0x44u)") == 1
    assert NATIVE.count("XInputSetState((DWORD)port,&vibration)") == 1
    assert NATIVE.count("static void recomp_xinput_close(uint32_t handle)") == 1
    print("[XPP-FAMILY] SELFTEST PASS: strict source stack/EAX ABI; exact feedback; idempotent site rewrite")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    for k in ("shards", "parent_main", "parent_manifest", "generated",
              "functions", "emitter", "out", "out_main", "manifest"):
        p.add_argument("--" + k.replace("_", "-"), type=Path)
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    for k in ("shards", "parent_main", "parent_manifest", "generated",
              "functions", "emitter", "out", "out_main", "manifest"):
        if getattr(a, k) is None:
            p.error("--" + k.replace("_", "-") + " required")
    stage(a)

if __name__ == "__main__":
    main()

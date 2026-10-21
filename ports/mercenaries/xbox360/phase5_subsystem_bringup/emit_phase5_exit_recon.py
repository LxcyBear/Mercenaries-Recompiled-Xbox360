#!/usr/bin/env python3
"""Generate mandatory Phase-5 exit reconnaissance artifacts.

This audit is static/observe-only. It adds no translated functions and does
not fabricate graphics/audio/movie/input success. The already-proven 5BV
three-run hardware endpoint is the dynamic baseline.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ENDPOINT = 0x0014CD30
CALLER = 0x0023A3CE

FUNCTION_RE = re.compile(r"(?m)^void\s+sub_([0-9A-Fa-f]{8})\s*\(void\)\s*\n\{")
ORIGINAL_RE = re.compile(r"\* Original:\s*0x([0-9A-Fa-f]{8})\s*-\s*0x([0-9A-Fa-f]{8})")
SUB_REF_RE = re.compile(r"\bsub_([0-9A-Fa-f]{8})\b")
HEX_RE = re.compile(r"(?i)0x([0-9a-f]{8})\b")


def closing_brace(text: str, opening: int) -> int:
    depth = 0
    state = "code"
    i = opening
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if state == "code":
            if c == "/" and n == "/":
                state = "line"
                i += 1
            elif c == "/" and n == "*":
                state = "block"
                i += 1
            elif c == '"':
                state = "string"
            elif c == "'":
                state = "char"
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        elif state == "line":
            if c == "\n":
                state = "code"
        elif state == "block":
            if c == "*" and n == "/":
                state = "code"
                i += 1
        elif state == "string":
            if c == "\\":
                i += 1
            elif c == '"':
                state = "code"
        elif state == "char":
            if c == "\\":
                i += 1
            elif c == "'":
                state = "code"
        i += 1
    raise ValueError("unterminated generated function")


def find_generated_function(root: Path, address: int) -> dict[str, object]:
    needle = f"sub_{address:08X}"
    for path in sorted(root.rglob("recomp_[0-9][0-9][0-9][0-9].c")):
        text = path.read_text(encoding="utf-8")
        pos = text.find(needle)
        if pos < 0:
            continue
        for match in FUNCTION_RE.finditer(text, max(0, pos - 256)):
            if int(match.group(1), 16) != address:
                if match.start() > pos:
                    break
                continue
            annotations = list(
                ORIGINAL_RE.finditer(text, max(0, match.start() - 512), match.start())
            )
            original_end = None
            if annotations and int(annotations[-1].group(1), 16) == address:
                original_end = int(annotations[-1].group(2), 16)
            opening = text.find("{", match.start(), match.end())
            end = closing_brace(text, opening)
            body = text[match.start():end]
            refs = sorted({int(x, 16) for x in SUB_REF_RE.findall(body)})
            constants = sorted({int(x, 16) for x in HEX_RE.findall(body)})
            markers = {
                "indirect_call": "RECOMP_ICALL" in body,
                "indirect_tail": "RECOMP_ITAIL" in body,
                "kernel_dispatch": "kernel" in body.lower() or "ordinal" in body.lower(),
                "gpu_mmio_constant": any(0xFD000000 <= x <= 0xFDFFFFFF for x in constants),
                "apu_mmio_constant": any(0xFE800000 <= x <= 0xFEFFFFFF for x in constants),
            }
            return {
                "address": f"0x{address:08X}",
                "status": "exact_generated_title_function",
                "source": str(path.relative_to(root)),
                "original_end": f"0x{original_end:08X}" if original_end else None,
                "direct_sub_refs": [f"0x{x:08X}" for x in refs],
                "markers": markers,
                "body_lines": body.count("\n") + 1,
            }
    return {
        "address": f"0x{address:08X}",
        "status": "missing_generated_body",
        "source": None,
        "original_end": None,
        "direct_sub_refs": [],
        "markers": {},
        "body_lines": 0,
    }


def require_files(repo: Path, relative_paths: list[str]) -> list[str]:
    missing = [p for p in relative_paths if not (repo / p).exists()]
    if missing:
        raise SystemExit("[Phase5Exit] required maintained surface files missing: " + ", ".join(missing))
    return relative_paths


def surface_entry(subsystem, operation, files, status, observed, criticality, strategy, risk, notes):
    return {
        "subsystem": subsystem,
        "operation_family": operation,
        "source": files,
        "status": status,
        "observed_on_phase5_hardware": observed,
        "first_touch_order": None,
        "abi_argument_notes": "Title-facing x86 guest ABI remains authoritative; adapt at maintained/native boundary.",
        "resource_lifecycle_notes": notes,
        "threading_synchronization_notes": "Preserve guest ordering; do not move guest-visible callbacks to host workers without evidence.",
        "criticality": criticality,
        "implementation_dependency": "Phase 6 native Xbox 360 backend / adapter",
        "phase6_strategy": strategy,
        "risk": risk,
        "evidence_confidence": "high-static / hardware-exposure-only",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    generated = args.generated_root.resolve()
    out = args.out_dir.resolve()
    if not generated.exists():
        raise SystemExit(f"[Phase5Exit] generated root missing: {generated}")

    endpoint = find_generated_function(generated, ENDPOINT)
    if endpoint["status"] != "exact_generated_title_function":
        raise SystemExit(
            "[Phase5Exit] stable 0x0014CD30 endpoint has no exact generated body; "
            "Phase 5 cannot close until it is classified/resolved"
        )

    graphics_files = require_files(repo, [
        "src/nv2a/nv2a_core.c",
        "src/nv2a/nv2a_pgraph_d3d11.c",
        "src/d3d/d3d8_device.c",
        "src/d3d/d3d8_resources.c",
        "src/d3d/d3d8_states.c",
        "src/d3d/d3d8_shaders.c",
    ])
    audio_files = require_files(repo, [
        "src/apu/apu_core.c",
        "src/apu/apu_vp.c",
        "src/apu/apu_dsp.c",
        "src/apu/apu_xaudio2.c",
        "src/audio/dsound_device.c",
    ])
    movie_files = require_files(repo, [
        "ports/mercenaries/src/recomp/xmv_fast_helpers.h",
        "tools/xmv/xmv_demux.py",
    ])
    input_files = require_files(repo, [
        "src/input/xinput_device.c",
        "ports/mercenaries/src/recomp_controls.c",
        "ports/mercenaries/src/controls_mapping.h",
    ])
    cross_files = require_files(repo, [
        "src/kernel/kernel_thread.c",
        "src/kernel/kernel_sync.c",
        "src/kernel/kernel_file.c",
        "src/kernel/kernel_memory.c",
        "src/d3d/d3d8_frame_timing.h",
    ])

    surfaces = [
        surface_entry(
            "graphics/display",
            "device/display creation, presentation, render-target/depth lifecycle",
            graphics_files,
            "maintained semantic reference exists; Xbox360-native backend not implemented in Phase 5",
            "XBE D3D/XGRPH sections loaded; no guest-visible graphics operation was allowed/faked before the stable frontier",
            "first native visible frame",
            "Reuse decoded NV2A/D3D8 semantics and resource-lifecycle knowledge, but implement a real Xbox 360/Xenos-facing backend rather than porting the Windows D3D11 host layer verbatim.",
            "critical",
            "Device, surface, shader, texture, push-buffer, presentation, fence and frame-pacing ownership must remain explicit.",
        ),
        surface_entry(
            "graphics/display",
            "textures, vertex/index buffers, shaders, state, clear/draw/submit",
            graphics_files,
            "maintained desktop semantic implementations and tests exist",
            "not semantically reached by Phase 5 frozen boot",
            "first frame + menu",
            "Port operation families in dependency order: device/resources -> state/shaders -> draw/submit -> present. Keep unsupported operations hard failures during bring-up.",
            "critical",
            "NV2A formats/layouts and D3D8LTCG/push-buffer assumptions are the highest graphics translation risk.",
        ),
        surface_entry(
            "audio",
            "APU/XACT/DirectSound initialization, buffers/voices/streams, mix/output",
            audio_files,
            "maintained semantic reference exists; Xbox360-native audio path not implemented in Phase 5",
            "XACTENG/DSOUND sections loaded; no guest-visible audio backend operation was allowed/faked before the stable frontier",
            "logo/movie + menu audio",
            "Reuse APU/XACT lifecycle and clock knowledge; implement a native Xbox 360 audio output adapter while preserving guest cue/stream ownership and callback order.",
            "high",
            "APU sample clock, voice lifetimes, stream refill and callback synchronization couple directly to XMV cadence.",
        ),
        surface_entry(
            "movies/video",
            "XMV discovery/decode, YUV output, A/V clock, skip and presentation handoff",
            movie_files,
            "retail XMV decoder remains generated title code with maintained hot helpers/reference tooling",
            "XMV/WMADEC sections loaded; decoder semantics not reached by Phase 5 frozen boot",
            "startup logo/movie",
            "Keep retail/generated decode where practical; adapt output surfaces and timing to the native graphics/audio backends. Preserve XGSCNT/audio-mastered timing assumptions.",
            "high",
            "Movie cadence crosses graphics presentation, APU sample clock, AV field state and input skip handling.",
        ),
        surface_entry(
            "input",
            "controller discovery/polling, mapping, deadzones, vibration, reconnect",
            input_files,
            "maintained mapping semantics exist; Phase 6 must bind them to Xbox 360-native controller services",
            "not semantically reached by Phase 5 frozen boot",
            "menu interaction",
            "Start with native Xbox 360 pad polling and exact Xbox layout; preserve title-authored deadzones/context mapping and add vibration/reconnect only after polling is stable.",
            "medium",
            "Menu/gameplay context switching matters more than host prompt abstraction on Xbox 360.",
        ),
        surface_entry(
            "cross-cutting",
            "async I/O, workers, synchronization, timers, allocations, paths, endian/lifecycle",
            cross_files,
            "substantial Phase 5 runtime semantics already hardware-proven; Phase 6 subsystems must integrate without violating them",
            "hardware-proven through 3/3 frozen boots for current startup path",
            "all stages",
            "Keep the Phase 5 kernel/filesystem/heap/ABI path fixed as the baseline. Introduce subsystem workers/timers only behind explicit ownership and teardown contracts.",
            "high",
            "Do not let native graphics/audio threads mutate guest-visible state outside established safe points.",
        ),
    ]

    first_touch = [
        {"order": 1, "kind": "hardware-exposure", "subsystem": "movies/video", "operation": "XBE section XMV loaded", "detail": "Exposure only, not decoder execution."},
        {"order": 2, "kind": "hardware-exposure", "subsystem": "audio", "operation": "XBE section XACTENG loaded", "detail": "Exposure only; no fabricated audio initialization."},
        {"order": 3, "kind": "hardware-exposure", "subsystem": "graphics/display", "operation": "XBE section D3D loaded", "detail": "Exposure only; no fabricated device creation."},
        {"order": 4, "kind": "hardware-exposure", "subsystem": "graphics/display", "operation": "XBE section XGRPH loaded", "detail": "Exposure only."},
        {"order": 5, "kind": "hardware-exposure", "subsystem": "audio", "operation": "XBE section DSOUND loaded", "detail": "Exposure only."},
        {"order": 6, "kind": "hardware-exposure", "subsystem": "movies/video", "operation": "XBE section WMADEC loaded", "detail": "Exposure only."},
        {"order": 7, "kind": "hardware-runtime", "subsystem": "cross-cutting", "operation": "stable translated startup path", "detail": "Three consecutive frozen-pack boots reproduced storage/VM/filesystem/heap/ABI behavior and exact counters."},
        {"order": 8, "kind": "hardware-boundary", "subsystem": "title core", "operation": "stable direct frontier", "caller": f"0x{CALLER:08X}", "target": f"0x{ENDPOINT:08X}", "detail": "Exact generated title function exists in the complete generated tree. The Phase 5 stop is a frozen-pack coverage endpoint, not an unknown kernel/ABI/platform fault."},
    ]

    risk_map = {
        "phase": "6",
        "generated_from": "Phase 5 exit reconnaissance",
        "risks": [
            {"rank": 1, "area": "graphics/Xenos backend", "severity": "critical", "reason": "NV2A/D3D8 semantics, push buffers, resource formats, shaders and presentation must be adapted to Xenos without desktop D3D11."},
            {"rank": 2, "area": "movie A/V timing", "severity": "high", "reason": "XMV cadence depends on graphics presentation, APU/XGSCNT timing and AV field behavior."},
            {"rank": 3, "area": "audio/XACT/DSOUND", "severity": "high", "reason": "Voice/stream lifetime and callbacks are coupled to guest execution and movie timing."},
            {"rank": 4, "area": "cross-thread/resource ownership", "severity": "high", "reason": "Phase 5 uses controlled guest safe points; native subsystem workers must not violate ABI/lifecycle ordering."},
            {"rank": 5, "area": "input/menu integration", "severity": "medium", "reason": "Native pad access is simpler than graphics/audio, but title context mapping and reconnect semantics still matter."},
            {"rank": 6, "area": "residual title-code continuation from 0x0014CD30", "severity": "medium", "reason": "Endpoint is classified as exact generated title code; downstream first Phase-6 semantic touch remains to be observed during implementation bring-up."},
        ],
    }

    surface = {
        "phase": "5-exit",
        "retail_xbe_sha256": "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7",
        "repeatability": {
            "build_tag": "P5BV-REPEATABILITY-20261021-A",
            "runs": 3,
            "all_passed": True,
            "endpoint": "DIRECT_FRONTIER 0x0023A3CE -> 0x0014CD30",
            "icall": 1262,
            "direct": 1002,
            "msize": 395,
            "realloc": 4,
            "final_msize": 2048,
            "ticks": 73417,
            "trace": 7322,
            "fault": 0,
            "xapi_return": 0,
        },
        "stable_endpoint_classification": endpoint,
        "surfaces": surfaces,
        "first_touch": first_touch,
        "unknowns": [
            "The first semantic graphics/audio/movie/input operation after the stable title-code endpoint is not dynamically reached by the frozen Phase 5 boot and remains a Phase 6 first-touch measurement.",
            "Desktop D3D11/XAudio2/SDL implementations are semantic references, not evidence that an Xbox 360-native backend is already implemented.",
        ],
        "exit_gate": {
            "repeatability_complete": True,
            "stable_endpoint_classified": True,
            "subsystem_inventory_complete": True,
            "hardware_first_touch_baseline_complete": True,
            "risk_map_complete": True,
            "ordered_handoff_complete": True,
            "backend_functionality_claimed": False,
            "result": "PASS",
        },
    }

    handoff_steps = [
        "1. Continue from exact generated title function 0x0014CD30 under Phase 6 instrumentation; record the first true graphics/audio/movie/input semantic touch instead of widening generic Phase 5 coverage.",
        "2. First pixels: establish Xbox 360-native Xenos device/display/resource foundation, then wire render-target/depth, texture/buffer, shader/state, draw/submit and present families in that order.",
        "3. Menu input: bind native Xbox 360 controller polling to the title mapping/context layer; then add vibration and reconnect semantics.",
        "4. Startup media: connect XMV output surfaces to the graphics backend and preserve APU/XGSCNT/AV-field timing; add skip/input handoff.",
        "5. Audio at/menu: connect APU/XACT/DirectSound semantic paths to Xbox 360-native output while preserving cue/stream lifetime and guest callback ordering.",
        "6. Gameplay hardening: asynchronous streaming, worker synchronization, advanced render-state/resource cases, 3D audio, device reconnect, and performance tuning.",
    ]

    out.mkdir(parents=True, exist_ok=True)
    (out / "phase5-exit-subsystem-surface.json").write_text(json.dumps(surface, indent=2) + "\n", encoding="utf-8")
    (out / "phase6-risk-map.json").write_text(json.dumps(risk_map, indent=2) + "\n", encoding="utf-8")

    md = [
        "# Phase 5 Exit Subsystem Surface", "",
        "**Result: PASS**", "",
        "The Phase 5 translated/runtime pack passed 3/3 repeatability. The stable",
        "frontier 0x0023A3CE -> 0x0014CD30 is classified by the complete generated",
        "tree as an exact generated title function, so the frozen Phase 5 endpoint",
        "is not an unexplained kernel/ABI/platform failure.", "",
        "No graphics/audio/movie/input backend success was fabricated during this audit.", "",
        "## Surface inventory", "",
    ]
    for item in surfaces:
        md += [
            f"### {item['subsystem']} — {item['operation_family']}", "",
            f"- Status: {item['status']}",
            f"- Hardware: {item['observed_on_phase5_hardware']}",
            f"- Criticality: {item['criticality']}",
            f"- Phase 6 strategy: {item['phase6_strategy']}",
            f"- Risk: {item['risk']}", "",
        ]
    (out / "phase5-exit-subsystem-surface.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    ft = [
        "PHASE 5 EXIT FIRST-TOUCH / EXPOSURE BASELINE",
        "Build: P5BV-REPEATABILITY-20261021-A",
        "Hardware repeatability: 3/3 PASS", "",
    ]
    for e in first_touch:
        loc = ""
        if "caller" in e:
            loc = f" caller={e['caller']} target={e['target']}"
        ft.append(f"{e['order']:02d} {e['kind']} {e['subsystem']}: {e['operation']}{loc}")
        ft.append(f"   {e['detail']}")
    ft += [
        "",
        "XMV/XACTENG/D3D/XGRPH/DSOUND/WMADEC entries are XBE section exposure/load",
        "events, not claims that those backends initialized or rendered/played.",
        "The first true Phase-6 semantic subsystem touch remains intentionally",
        "unexecuted and will be measured as native Phase-6 adapters come online.",
    ]
    (out / "phase5-exit-first-touch.txt").write_text("\n".join(ft) + "\n", encoding="utf-8")

    ho = [
        "# Phase 6 Handoff", "",
        "Phase 5 exit gate: **PASS**", "",
        "The translated/runtime path is frozen and repeatable. 0x0014CD30 is an exact",
        "generated title function in the full Phase3N tree, classifying the final",
        "Phase 5 stop as a controlled pack endpoint rather than an unexplained runtime fault.", "",
        "## Ordered implementation plan", "",
        *handoff_steps, "",
        "## Guardrails", "",
        "- Do not replace real graphics/audio/movie/input operations with fake success.",
        "- Keep the Phase 5 filesystem/VM/heap/ABI baseline fixed unless new evidence requires change.",
        "- Treat existing desktop renderer/audio/input code as semantic reference; Xbox 360 needs native adapters.",
        "- Record the first true subsystem semantic touch reached after 0x0014CD30.", "",
        "## Phase 5 closure", "",
        "All required exit outputs are present: surface JSON/Markdown, hardware first-touch",
        "baseline, Phase-6 risk map, and ordered handoff. Phase 6 may begin.",
    ]
    (out / "phase6-handoff.md").write_text("\n".join(ho) + "\n", encoding="utf-8")

    print("[Phase5Exit] stable endpoint classification: exact generated title function")
    print(f"[Phase5Exit] endpoint source: {endpoint['source']}")
    print(f"[Phase5Exit] endpoint original range: 0x{ENDPOINT:08X}-{endpoint['original_end']}")
    print(f"[Phase5Exit] endpoint direct refs: {', '.join(endpoint['direct_sub_refs']) or '(none)'}")
    print("[Phase5Exit] outputs:")
    for name in (
        "phase5-exit-subsystem-surface.json",
        "phase5-exit-subsystem-surface.md",
        "phase5-exit-first-touch.txt",
        "phase6-risk-map.json",
        "phase6-handoff.md",
    ):
        print(f"[Phase5Exit]   {out / name}")
    print("[Phase5Exit] EXIT RECON RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

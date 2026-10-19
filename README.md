# Mercenaries Recompiled Xbox 360 Edition

Native Xbox 360 / Xenon port of *Mercenaries: Playground of Destruction* using
static recompilation and a gradually migrated Xbox-kernel/platform runtime.

## Xbox 360 port status

Snapshot: 2026-10-19.

| Phase | Status | Evidence / purpose |
| --- | --- | --- |
| 1-2 | Complete | Xenon/XDK bring-up, guest-memory/execution foundations, real-Xbox hardware test path. |
| 3A | Complete | Scalar guest-memory semantics on Xenon. |
| 3B | Complete | x87 guest-memory semantics. |
| 3C | Complete | SSE/MMX guest-memory semantics. |
| 3D | Complete | Runtime guest-memory execution surface. |
| 3E | Complete | First real retail translated function executes in the XDK harness. |
| 3F | Complete | Translated tail-call path. |
| 3G | Complete | Direct translated-call path. |
| 3H | Complete | Indirect-call / ICALL path. |
| 3I | Complete | Composite translated slice. |
| 3J | Complete | Dependency-closed translated cluster on real hardware. |
| 3K | Complete | Wider control/flags plus mixed x87/XMM state. |
| 3L | Complete | Bounded translated loop surface. |
| 3M | Complete | Maintained x87 rounding/exception behavior. |
| 3N / 3N-B | **Phase 3 final PASS** | 128-function audited translated-code scale pack; loaded-XEX anchors; six independent-reference runs of retail `0x00208F30`; XAPI return 0. |
| 4A | **Locked PASS** | Exact 111-import guest-kernel/ABI audit; baseline 17 semantic host-backed callable paths. |
| 4B-A | **Hardware PASS** | Native Xenon timing/synchronization primitive gate. |
| 4B-A2 | **Complete PASS** | Six timing/sync imports migrated to `merc_platform_*`; 11 direct host-backed + 6 platform-bound; 0 ABI errors; 0 referenced fallbacks; 7,722 deadline cases PASS. |
| 4B-B | **Hardware PASS** | `P4B-FILE-20261019-A` passed on real Xenon: create/open/read/write, offsets, size/query, truncate, attributes, directory enumeration, missing-file errors, and cleanup all PASS. |
| 4B-B2 | **Complete PASS** | Nine file/handle imports route through `merc_platform_file_*`; verifier passed at 2 direct host-backed + 15 platform-bound with ABI/fallback checks clean and all regressions green. |
| 4B-C | **Hardware PASS** | `P4B-MEMPROT-20261019-B` passed on real Xenon: guest allocation, per-page protection, decommit/recommit, tracked release/reuse, zero-init, bounds and stale-release checks all PASS. |
| 4B-C2 | **Complete PASS** | Final verifier passes at 0 direct host-backed / 15 platform-bound / 2 guest-native with ABI/fallback, timing, file/handle and memory ownership regressions all green. |
| 4C | **Active** | First real translated Mercenaries startup path with the migrated Xenon service layer. |
| 4C-A | **Complete PASS** | Retail entry `0x0022964A` resolves exactly to `xbe_entry_point`; direct closure is 40 translated bodies, depth 8, 5,918 guest bytes, 111,376 generated-source bytes, 0 missing direct dependencies, 14 dynamic/indirect-boundary bodies. |
| 4C-B | **Hardware PASS** | Real retail-derived `xbe_entry_point` executed on Xbox 360 and reached the first live boundary with fault=0: caller `0x0022B4D7`, target `0x800000FF` = kernel ordinal 255 `PsCreateSystemThreadEx`. |
| 4C-C | **Hardware PASS** | Live ordinal-255 frame captured on Xbox 360: StartRoutine `0x0022B43F`, ctx1 `0x002295D6`, ctx2 `0x00000000`, exact 44-byte frame, fault=0. |
| 4C-D | **Complete PASS** | Hardware-observed `0x0022B43F` resolves exactly; closure is 6 bodies, depth 2, 460 guest bytes, 8,556 generated-source bytes, 0 missing translated dependencies, 5 dynamic-boundary bodies. |
| 4C-E | **Package prep ready** | Continuous Xenon slice: real XBE entry -> ordinal 255 -> hardware-observed title thread `0x0022B43F`; pack is 43 unique translated bodies and stops at the first subsequent live ICALL/ITAIL boundary. |
| 5 | Planned | Runtime subsystem bring-up driven by actual native startup blockers. |
| 6 | Planned | First reproducible title-controlled interactive milestone. |
| 7 | Planned | Gameplay, compatibility, stability, and performance hardening. |

Latest completed hardware gate:

```text
P4B-FILE-20261019-A  PASS
```

Latest memory/protection hardware gate:

```text
P4B-MEMPROT-20261019-B  PASS
```

Final Phase 4B service accounting:

```text
imports=111
guest_bridge=74
data=11
fallback=26
arg_missing=0
arg_mismatch=0
host_surface=0
platform_bound=15
guest_native=2
fallback_referenced=0
fallback_refs=0
```

Phase 4B is complete. All 17 semantic host-backed paths identified by the
locked Phase-4A baseline have been migrated or reclassified: six timing/sync
and nine file/handle paths are platform-bound, while the two memory/protection
paths are guest-native. Phase 4C is the first real translated Mercenaries
startup-path phase.

For the detailed evidence gates and next-step requirements, see
[`ports/mercenaries/xbox360/ROADMAP.md`](ports/mercenaries/xbox360/ROADMAP.md).
For code-location/navigation details, see [`CODE_MAP.md`](CODE_MAP.md).

> Hardware harness PASS means only the bounded surface executed by that harness
> is proven. It does not by itself prove full translated-game startup or
> gameplay.

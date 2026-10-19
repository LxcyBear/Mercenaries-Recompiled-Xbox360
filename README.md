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
| 4B-C | **Hardware gate A ready** | Final direct host-backed pair: `NtFreeVirtualMemory` and `MmSetAddressProtect`; Xenon gate proves guest release/reuse plus logical decommit/recommit/protection metadata. |
| 4C | Planned | First real translated Mercenaries startup path with the migrated Xenon service layer. |
| 5 | Planned | Runtime subsystem bring-up driven by actual native startup blockers. |
| 6 | Planned | First reproducible title-controlled interactive milestone. |
| 7 | Planned | Gameplay, compatibility, stability, and performance hardening. |

Latest completed hardware gate:

```text
P4B-FILE-20261019-A  PASS
```

Current hardware gate:

```text
P4B-MEMPROT-20261019-A  READY
```

Current verified service accounting after the Phase 4B-B2 PASS:

```text
imports=111
guest_bridge=74
data=11
fallback=26
arg_missing=0
arg_mismatch=0
host_surface=2
platform_bound=15
fallback_referenced=0
fallback_refs=0
```

Phase 4B-B/B2 is complete: hardware proof and runtime verification both passed.
Only the two memory/protection paths remain direct host-backed before the native
translated-game startup push.

For the detailed evidence gates and next-step requirements, see
[`ports/mercenaries/xbox360/ROADMAP.md`](ports/mercenaries/xbox360/ROADMAP.md).
For code-location/navigation details, see [`CODE_MAP.md`](CODE_MAP.md).

> Hardware harness PASS means only the bounded surface executed by that harness
> is proven. It does not by itself prove full translated-game startup or
> gameplay.

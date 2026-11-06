# K1 hardware-last / batch-first policy (2026-11-06)

**Project priority:** reach actual first guest pixels, successful Swap/Present, startup/main menu, and eventually audio. Maintain exact retail behavior and hard-fence unknown semantics. **No per-function Xbox testing and no tick mining.**

## Decision rule

The default for every investigation and patch is **offline source-only**: verify original retail XBE SHA, use xboxrecomp function inventory and decompiler/disassembly, inspect generated C, prove ABI and source ownership, stage under a new path, check manifests/source hashes/64 TrueTUs, run local tests, and collect multiple fixes together.

**Do not build a new XEX for each isolated source test.** A single XDK build is justified only for a coherent batch that materially changes expected coverage, for a substantial newly discovered execution/ABI dependency cluster, or when offline evidence is exhausted and a targeted on-console result is essential. "Big jump" is an *expected opportunity*, not a promised tick threshold. Prepare a manifest stating the included changes, original addresses and source provenance, ABI constraints, previous frontiers and the new observable milestone.

**Do not run each new XEX on hardware.** Test only when all source, ABI, uniqueness, compile, and safety gates pass and the proposed run can answer a specific high-value question (e.g., reach guest Swap/Present, consume more original streaming data, clear a major cluster, reach menu). Reuse the most recent known-good XEX between such milestones. One consolidated xbWatson capture per approved batch, not a loop of trial builds.

An urgent *safety regression* or necessary ABI correction may justify an exception. A passed source stage does **not** imply a successful Xbox run, and more ticks alone do not demonstrate visible pixels.

## Retained safety fences

Do not remove unknown VP/NV2A/MMIO, stack-frame/ABI, object-pointer, async Event/APC, guest pointer, or unexplained retail function boundaries. Real IO_STATUS_BLOCK/byte-count/return/stack semantics are mandatory. Never invent game assets, success returns, fake Swap/Present, fabricated audio or callback completions. Do not publish actual original XBE bytes or privately generated game source. Prior GPU debugger dumps require healthy console confirmation before a new run.

## Current evidence and work queue

- **V7E:** five retail functions, 197 original x86 instructions, 64 TrueTUs; Xbox reached tick 62,777,793 at kind 17 target 80000063. Guest display_calls=0.
- **V7I:** candidate IOSB guard repair was staged and compiled. Hardware reached tick 62,777,809; actual seventh read at IOSB 00424D58 delivered its APC. Next verified boundary is `NtReadFile` Event/APC form, kind 17 target 800000DB. Seven reads succeeded; guest display_calls=0.
- **Next:** map original read/callback control flow from verified XBE, xboxrecomp graph, generated C and TrueTU ownership. Inspect pending APC queuing/delivery, frame ABI, and other reachable graphics/audio roots **as a batch**. Do not widen the NtReadFile admission predicate from one log line. Combine supported independent patches into one source manifest before authorizing an XDK build.

## Default commands

`Advance-K1V7IApcIosbSecondCompletion.ps1` now stages and validates **without XDK** by default. `-BuildBatch` is an explicit opt-in for a compilation (still **never** launches the console). Older stage/build scripts may retain legacy automatic build behavior; inspect their flags before running them. This policy does not imply every historical script was retrofitted.

`Audit-K1V7JRecompSourceBatch.py` combines an available local xboxrecomp inventory, generated C corpus, and TrueTUs to prioritize offline recovery. Treat static graph links as leads, not runtime proof.

## Suggested batch gates

1. Verified inputs: retail SHA/source provenance and exact addresses; no source-name guesswork.
2. Dependency batch: record all staged functions, x87/SSE and calling convention, return ESP, import contracts, generated C ownership and duplicate-dispatch audit.
3. Regression gate: previously proven seven reads, callbacks, native D3D create/reset and all safety fences remain; report any unsupported cases.
4. Build decision: enumerate substantial new capability expected from this **combined** batch and what a single hardware run could confirm.
5. Hardware decision: first healthy-console check; fresh XEX identity, one controlled run, xbWatson markers, exact milestone or boundary report, no repeated runs for an isolated issue.

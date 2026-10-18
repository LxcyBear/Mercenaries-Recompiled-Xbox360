# Phase 2D — Checked guest-address router

**Status: source ready; real Xbox 360 hardware test pending.**

Phase 2C proved exact retail-XBE identity and section integrity. Phase 2D does
not execute the game. It isolates the next requirement: **a guest address must
be classified before it can ever become a native pointer or a hardware access.**

## Build

Use the same known-good VS17 + Xbox 360 XDK project.

1. Replace its \`main.cpp\` with this directory's latest \`main.cpp\`.
2. No \`default.xbe\` is required for this test.
3. No extra project headers or include directories are required.
4. Clean, rebuild and deploy the new XEX.

Verify the runtime tag:

~~~text
[Merc360:P2D] BUILD TAG: P2D-ROUTER-20261018-A
~~~

## What is being tested

The router models the address classes already used by the upstream runtime:

- **0x00000000–0x73FFFFFF** — 64 MiB RAM plus the 28 configured 64 MiB
  mirror windows; address bits wrap with \`& 0x03FFFFFF\`.
- **0x80000000–0xBFFFFFFF** — KSEG0/KSEG1 direct physical aliases, also
  repeating 64 MiB.
- **0x80000000 page** — synthetic D3D cache-fence page; intentionally wins over
  the generic KSEG rule.
- **0x80010000 page** — synthetic Xbox kernel PE page; intentionally wins over
  the generic KSEG rule.
- **0xF0000000–0xF3FFFFFF** — shared VRAM aperture classification.
- **0xFD000000–0xFDFFFFFF** — NV2A MMIO classification.
- **0xFE000000–0xFE0005FF** — synthetic kernel function-thunk VA class.
- **0xFE800000–0xFE87FFFF** — MCPX APU MMIO.
- **0xFEC00000–0xFEC00FFF** — MCPX AC97 MMIO.
- everything else — unsupported unless a later explicitly documented region is
  added.

This diagnostic does **not** emulate those devices yet. The important safety
property is that MMIO/thunk regions return a classification and **no RAM
pointer**.

## Coherence fixtures

The hardware test writes through one view and reads another to prove:

- \`0x04070000 == 0x00070000\`
- \`0x20000448 == 0x00000448\`
- KSEG0 \`0x81230000 == 0x01230000\`
- KSEG1 \`0xA1230000 == 0x01230000\`
- the synthetic \`0x80010000\` kernel page remains distinct from ordinary low
  RAM even though generic KSEG translation would otherwise alias it.

The test also rejects a direct 32-bit access that crosses the end of one
64 MiB RAM window rather than silently producing a host out-of-bounds pointer.

## Expected finish

~~~text
[Merc360:P2D] PASS: NV2A route exposes no RAM pointer
[Merc360:P2D] PASS: APU route exposes no RAM pointer
[Merc360:P2D] PASS: kernel thunk route exposes no data pointer
...
[Merc360:P2D] PHASE 2D ADDRESS ROUTER RESULT: PASS
~~~

Send the entire xbWatson output.

## After Phase 2D

If this passes, the next bounded memory test will populate the Mercenaries
guest stack and synthetic low-memory TIB/TLS/KTHREAD/kernel-data fixtures
through this router. Broad translated game execution is still disabled.

# Phase 2E — Guest execution-environment fixture

**Status: source ready; portable contract PASS; Xbox 360 hardware run pending.**

Phase 2D proved the checked guest-address router. Phase 2E now builds the
Mercenaries-specific low-memory and stack environment that the current upstream
runtime expects **without executing any translated game function**.

## Build

Use the same working VS17 + Xbox 360 XDK project.

1. Replace its source with this directory's latest \`main.cpp\`.
2. Keep your own supported original-Xbox \`default.xbe\` beside the test XEX.
3. No auxiliary project headers or include directories are required.
4. Clean, rebuild, deploy and run.

Require this tag before evaluating the result:

~~~text
[Merc360:P2E] BUILD TAG: P2E-ENV-20261018-A
~~~

## What Phase 2E builds

After re-verifying the exact pinned retail XBE and loading all 14 sections,
the diagnostic constructs the current Mercenaries guest ABI fixture:

- fake TLS block: \`0x00700000\`
- fake KTHREAD: \`0x00760000\`
- kernel data page: \`0x0087E000\`
- 256 KiB guest stack: \`0x00880000-0x008BFFFF\`
- initial guest ESP: \`0x008BFFF0\`
- heap begins immediately after the stack at \`0x008C0000\`

The XBE's real TLS directory at \`0x00302CB4\` is read from the loaded guest
image. Phase 2E derives its raw-data range, index address and zero-fill size,
builds the synthetic TLS payload, and verifies the Xbox negative-index equation:

~~~text
fs:[4] + (signed_tls_index * 4) == 0x00700000
~~~

This is title-specific behavior from the current upstream Mercenaries runtime;
\`fs:[4]\` is deliberately the TLS-addressing base here, not a generic stack-top
field.

## TIB/KTHREAD checks

The fixture initializes and reads back:

- \`fs:[0x00] = 0xFFFFFFFF\` — SEH terminator
- \`fs:[0x04]\` — TLS addressing base
- \`fs:[0x08] = 0x00880000\` — stack limit
- \`fs:[0x18] = 0\` — TIB self compatibility value
- \`fs:[0x20] = 0\` — PRCB compatibility value
- \`fs:[0x28] = 0x00760000\` — fake KTHREAD
- \`[0x00760000 + 0x28] = 0x00700000\` — KTHREAD TlsData

The TIB is also read through the first 64 MiB mirror to prove router coherence.

## Kernel data + stack checks

The initial kernel-data page is zeroed and receives the currently required
fixtures:

- XboxHardwareInfo: retail flags, NV2A revision \`A1\`, MCPX revision \`B1\`
- XboxKrnlVersion: \`1.0.5849.0\`
- KeTickCount fixture

Kernel build \`5849\` is then read through primary RAM, a RAM mirror and KSEG0.

Finally, a simulated x86 \`PUSH32\`/\`POP32\` round-trip is performed at the
initial guest ESP. This changes Xbox-visible guest RAM only; it does not use the
native Xenon C stack as the guest stack.

## Expected finish

~~~text
[Merc360:P2E] PASS: Xbox negative TLS-index address equation resolves
[Merc360:P2E] PASS: kernel data coherent through KSEG0 alias
[Merc360:P2E] PASS: guest POP32 fixture restores initial ESP
[Merc360:P2E] PASS: Phase 2E TIB/TLS/stack/kernel-data environment is internally coherent
[Merc360:P2E] PHASE 2E EXECUTION ENVIRONMENT RESULT: PASS
~~~

The entry point remains disabled.

Send the full xbWatson trace.

## Next

A PASS makes the static guest memory environment much closer to what lifted
code expects. The next gate is the generated-memory ABI itself: audit and
replace assignable native-endian \`MEM16/32/64\` lvalues with explicit
endian-safe read/write/RMW operations before executing a bounded translated
function.


## Hardware result — PASS

Build tag `P2E-ENV-20261018-A` passed the complete Phase 2E fixture on
modified Xbox 360 hardware.

Notable observed retail TLS values:
- raw start/end: `0`
- TLS index address: `0x00869118`
- zero-fill: 8 bytes
- synthetic TLS block: 20 bytes

The TIB/KTHREAD/TLS chain, negative-index equation, kernel-data aliases,
256 KiB guest stack, initial ESP and PUSH32/POP32 fixture all passed.

Cleanup and the 10-second timeout completed with `[XAPI RETURN VALUE] 0`.

**Phase 2E and Gate 2 are complete.**
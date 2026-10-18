# Phase 2C — Exact retail verification + load invariants

**Status: source ready; SHA-256 host vectors PASS; Xbox 360 hardware run pending.**

Phase 2B proved that the supported retail XBE can be parsed and all 14 sections
can be copied into the 64 MiB guest arena on real Xenon hardware.

Phase 2C makes the identity and copy checks strict enough that later translated
guest execution cannot accidentally run against the wrong executable.

## Build

Use another copy of the same known-good VS17 + Xbox 360 XDK project.

1. Replace its source with this directory's \`main.cpp\`.
2. No extra project headers or include directories are required.
3. Build with the same Xbox 360 / PowerPC configuration.
4. Deploy your own supported original-Xbox \`default.xbe\` beside the XEX.

~~~text
default.xex
default.xbe
~~~

Do not commit or upload the retail XBE.

## New Phase 2C checks

Before any section load, the diagnostic computes SHA-256 over the complete XBE
and requires exactly:

~~~text
AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7
~~~

It also requires the known supported build invariants:

- file size \`0x00313000\`
- XBE base \`0x00010000\`
- header size \`0x00000A70\`
- image size \`0x00868AA0\`
- decoded retail entry \`0x0022964A\`
- TLS VA \`0x00302CB4\`
- decoded kernel thunk VA \`0x002DBCE0\`
- Title ID \`0x4C410015\`
- 14 sections in the expected order

For every section it additionally:

- rejects overlapping guest virtual ranges,
- verifies initialized guest bytes with \`memcmp\` after the copy,
- verifies every BSS/virtual tail byte remains zero.

The complete XBE header is also compared byte-for-byte after loading at guest
VA \`0x00010000\`.

**The entry point remains disabled.**

## SHA-256 preflight

The same SHA-256 implementation has been exercised with the standard:

- empty-string vector,
- \`abc\` vector,
- “The quick brown fox jumps over the lazy dog” vector,

under GCC, Clang, and Clang ASan+UBSan.

## Success markers

A successful hardware run should include:

~~~text
[Merc360:P2C] Computed SHA-256: AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7
[Merc360:P2C] PASS: SHA-256 exactly matches supported retail Mercenaries XBE
[Merc360:P2C] PHASE 2C EXACT RETAIL VERIFICATION: PASS
...
[Merc360:P2C] PASS: entire XBE header exactly copied to guest 0x00010000
...
[Merc360:P2C] PASS: every loaded section matches source bytes + zero-fill invariant
[Merc360:P2C] ENTRY POINT EXECUTION: DISABLED BY PHASE 2C DESIGN
[Merc360:P2C] PHASE 2C VERIFIED XBE LOAD RESULT: PASS
~~~

Send the entire xbWatson output.

## What follows

If this passes, exact executable identity and low-RAM section loading are no
longer open questions. The remaining Phase 2 work moves to original-Xbox
address aliases, synthetic low-memory/TIB/kernel structures and MMIO routing
needed by the translated ABI — still before broad game execution.


## First hardware attempt — partial PASS / diagnostic fix

The first real-console run successfully computed the exact pinned SHA-256 and
passed all exact XBE identity checks. It then stopped at section 11,
`$$XTIMAGE`, because the test's expected-name table accidentally stored only
one leading `$`.

This was a test-harness bug, not a retail-XBE failure. The expected names are
now encoded as `\x24\x24XTIMAGE` and `\x24\x24XSIMAGE`, and mismatch
logs now print both actual and expected names.

Rebuild the latest `main.cpp` and rerun Phase 2C.
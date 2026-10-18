# Phase 2B — Retail XBE parse + bounded section load

**Status: source ready; not yet compiled or tested on Xbox 360 hardware.**

Phase 2A proved the 64 MiB little-endian guest byte arena on real Xenon.
Phase 2B now loads the user's own supported original-Xbox
\`default.xbe\` **as data only**.

The diagnostic **does not execute the entry point**.

## Setup

Use another copy of the same known-good VS17 + Xbox 360 XDK project.

1. Replace its source with this directory's latest \`main.cpp\`.
2. Build exactly as Phase 1 / Phase 2A. It is self-contained; no project include
   directories or auxiliary project headers are required.
3. In the folder where you deploy the resulting Xbox 360 XEX, place your own
   original-Xbox Mercenaries retail executable beside it as:

~~~text
default.xex        <- our Xbox 360 diagnostic
default.xbe        <- your own original-Xbox retail Mercenaries executable
~~~

The two filenames do not conflict because one is \`.xex\` and one is \`.xbe\`.

**Do not commit, upload, or send the retail XBE.**

## What the test validates

The parser mirrors the upstream project's format assumptions but performs all
multi-byte reads explicitly as little-endian because Xenon is big-endian.

For the supported Mercenaries retail executable it expects:

- magic: \`XBEH\`
- Xbox base: \`0x00010000\`
- Title ID: \`0x4C410015\`
- retail entry XOR key: \`0xA8FC57AB\`
- decoded entry point: \`0x0022964A\`
- section count: \`14\`
- section headers: 56 bytes each

It then:

- verifies header / certificate / section-table file bounds,
- copies the bounded XBE header to guest VA \`0x00010000\`,
- zero-fills each section's virtual size,
- copies its initialized raw data into the correct guest VA,
- rejects any raw or virtual range outside its file / 64 MiB arena,
- confirms the decoded entry lies in a loaded section,
- confirms the decoded retail kernel thunk VA fits guest RAM,
- frees all data and exits without invoking guest code.

## Expected success markers

Look for:

~~~text
[Merc360:P2B] PASS: XBE magic is XBEH
[Merc360:P2B] PASS: XBE base matches supported Mercenaries
[Merc360:P2B] PASS: retail entry point matches supported Mercenaries
[Merc360:P2B] PASS: section count matches supported Mercenaries
[Merc360:P2B] PASS: Title ID matches Mercenaries
...
[Merc360:P2B] PASS: every XBE section loaded
[Merc360:P2B] PASS: decoded entry point lies inside a loaded section
[Merc360:P2B] ENTRY POINT EXECUTION: DISABLED BY PHASE 2B DESIGN
[Merc360:P2B] PHASE 2B XBE LOAD RESULT: PASS
~~~

Send the **entire xbWatson trace**, including every \`SECTION ...\` line.

## Important limitation

This phase performs a strong **structural identity** check but does not yet
calculate the pinned SHA-256
\`AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7\`
on the Xbox 360.

Exact hash verification will be added before any translated Mercenaries game
code is allowed to execute.

If this phase passes, the next work is Phase 2C: exact retail-XBE verification,
guest aliases/synthetic kernel data, and load invariants required by the
translated ABI.

# Phase 6 Parallel Acceleration Plan — PC Oracle, GPU Replay, Typed Xenos Shader Table

Status: active design and tooling track alongside the live Phase-6 hardware frontier.

This track does **not** replace Phase 6X or subsequent real-console frontier
testing. It removes the requirement that renderer development wait for every
translated-startup boundary to be crossed on Xbox 360 hardware.

## Track A — PC semantic oracle

Use the working upstream Mercenaries-Recompiled runtime as a guest-semantic
oracle. The oracle is not expected to match host implementation details,
wall-clock timing, or instruction-for-instruction behavior. It records the
guest-visible sequence that should remain stable across hosts.

Canonical event classes:

- `direct`: translated direct dispatch, caller + target.
- `icall`: translated indirect dispatch, caller + target.
- `kernel`: Xbox kernel ordinal/service boundary.
- `vm`: guest virtual-memory operation.
- `heap`: guest title-heap allocation/reallocation/free.
- `file`: guest path/open/read/write/query operation.
- `mmio-read` / `mmio-write`: NV2A register aperture access.
- `vram-read` / `vram-write`: guest NV2A VRAM aperture access.
- `pfifo`: pushbuffer submission/progress boundary.
- `pgraph`: decoded PGRAPH method + parameter.
- `draw`: normalized draw-state identity.
- `shader`: normalized vertex/combiner shader identity.

Each event uses JSON Lines with the mandatory fields:

```json
{"seq":1,"kind":"direct","caller":"0x0023A3CE","target":"0x0020F9C0"}
```

Optional fields may include `width`, `value`, `ordinal`, `path`,
`method`, `subchannel`, `hash`, `size`, `offset`, and `note`.

The comparison contract deliberately ignores host-only timing unless explicitly
requested. The first semantic divergence is more useful than thousands of
matching host log lines.

Upstream evidence for the instrumentation points:

- bounded async diagnostics already exist through `preview_log.c`;
- `pfifo_process_pushbuffer()` is the central pushbuffer decoder;
- `pgraph_method()` is the central decoded NV2A method dispatcher;
- existing diagnostics already report normalized last-draw GPU state.

## Track B — local GPU capture/replay

A replay capture is a **local developer artifact**, never a repository payload.
It may contain bytes derived from the user's legally obtained retail game and
therefore must not be committed, uploaded to releases, or redistributed.

Capture directory contract:

```text
capture/
  capture.json
  pushbuffer.bin
  memory/
    <sha256>.bin
  shaders/
    vertex/
    combiner/
```

`capture.json` version 1 records:

- source retail-XBE identity;
- capture point / frame index;
- pushbuffer blob + SHA-256;
- guest-memory ranges required by that pushbuffer;
- vertex/index ranges;
- texture/palette ranges;
- color/depth surface descriptors;
- DMA object mappings;
- NV2A state required to interpret the batch;
- vertex-program identity;
- register-combiner identity;
- expected dimensions/primitive where known.

Every referenced binary is content-addressed and SHA-256 verified before replay.
Paths are capture-relative and may not escape the capture directory.

The first replay XEX should be intentionally narrow: load one validated local
capture, recreate only the required resources/state, execute the captured draw
sequence through Xenos, present, and stop. It is a renderer laboratory, not an
alternate game runtime.

## Track C — hash-keyed typed Xenos shader table

Do not rely on runtime HLSL compilation on Xbox 360 unless the XDK path is
explicitly proven and desirable. Upstream already generates shader source from
NV2A semantics and already uses stable cache identities.

Use two typed key domains:

1. **Combiner pixel shader key**
   - semantic combiner-state hash for state identity;
   - source hash retained as provenance/translator-version guard;
   - animated constants remain runtime data and are not part of shader identity,
     matching upstream cache behavior.

2. **Vertex shader key**
   - guest vertex-program/microcode identity;
   - input declaration/layout identity;
   - generated source hash retained as provenance.

Offline compilation flow:

```text
NV2A state / microcode
        |
existing upstream semantic translator
        |
canonical generated shader source
        |
Xbox 360 offline shader compiler
        |
Xenos bytecode
        |
typed hash-keyed table
```

The runtime table must distinguish vertex and pixel entries even if hashes
collide numerically. Each entry also carries bytecode size and SHA-256 so build
tooling can reject a stale or mismatched blob.

Suggested generated C contract:

```cpp
enum Merc360ShaderKind {
    MERC360_SHADER_VERTEX = 1,
    MERC360_SHADER_COMBINER_PIXEL = 2
};

struct Merc360ShaderEntry {
    Merc360ShaderKind kind;
    uint64_t semantic_key;
    uint64_t source_hash;
    const unsigned char *bytecode;
    uint32_t bytecode_size;
};
```

Missing shader behavior during development is a visible diagnostic/hard stop,
not a silent fallback to an unrelated shader.

## Work ordering

The live hardware frontier remains authoritative:

1. Complete/test Phase 6X and continue the real retail startup path.
2. Add PC oracle instrumentation and normalize its guest-semantic trace.
3. Diff each new Xbox 360 trace against the oracle near the live frontier.
4. Add PC capture at PFIFO/PGRAPH once a representative game draw is available.
5. Bring up the standalone replay XEX from a local validated capture.
6. Populate the typed shader table from actually observed shader identities.
7. Expand capture/replay coverage from first draw -> menu -> representative 3D scene.

Do not solve every theoretical NV2A state before the game demonstrates that it
uses it.

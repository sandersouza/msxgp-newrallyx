# Arcade scene reconstruction and MSX composition

Status: design and direct execution approved by the user on 2026-10-20;
local implementation validated and independently reviewed, pending authorized delivery.
Issue: https://github.com/sandersouza/msxgp-newrallyx/issues/6

## Purpose and boundaries

Create a reproducible reference for a future MSX2+ renderer: capture real
New Rally-X gameplay, reconstruct its native image from issue #1 assets, prove
pixel agreement, and propose a 256x212 composition with measured constraints.
The subsequent user selection below establishes compact as the approved default.
Preserve asset sizes, world coordinates, simulation state and original CPU
execution. A preview does not approve a final layout, select an MSX screen mode,
prove performance or implement an MSX ROM.

## Verified starting point

- Existing extraction exports source pens, lookup tables and native dimensions;
  reuse `scripts/graphics/` instead of decoding ROMs a second time.
- All 13 contributor ROMs passed size, CRC32 and SHA-1 validation on 2026-10-20.
- Installed MAME reports 0.289. The source contract is `mame0289`, commit
  `f34f02505e32c1993c6a782b6814232cbfc74e36` in `nrallyx.json`.
- `rallyx.cpp` configures X=[0,288), Y=[16,240), giving a 288x224 image.
- `rallyx_v.cpp` uses shared video RAM, a separate radar attribute share,
  write-only scroll registers, a flip latch, category priority, lookup-index
  sprite transparency and two dot passes including shadow mixing.
- The current reference harness replaces the emulated program with an idle
  loop. Keep it for extraction tests; do not reuse it for gameplay evidence.

## Approach and alternatives

Use a Lua gameplay recorder plus an independent Python compositor and analyzer.
Their interface is a versioned capture bundle, so comparison and analysis run
without MAME once capture is complete. Keep the existing Pillow dependency.

A screenshot-only crop workflow is simpler but cannot validate addressing,
priority or object state. A custom MAME build exposing renderer internals could
make synchronization easier but adds a build dependency. Use the installed
MAME Lua API first; if it cannot expose a coherent render state, report the
specific limitation before adopting a patched emulator.

## Capture contract and synchronization

Store each new capture under a fresh ignored `references/scenes/<run>/<case>/`.
The schema version 1 bundle contains `capture.json`, `video.bin`,
`radar-attributes.bin`, a native RGB reference PNG and a manifest of payload
SHA-256 hashes. Record set, emulator version, source pin, ROM hashes, asset
manifest hash, visible rectangle, frame number, emulated time, callback phase,
scroll values, flip/control state, palette/shadow information and input history.
Object arrays are derived from raw state rather than maintained independently.

Read video RAM and radar attributes through their actual shares; observe
write-only scroll/latch writes using retained Lua taps installed before relevant
game writes. Do not infer scroll by reading unmapped addresses. Unknown initial
register values or unsupported APIs invalidate the capture.

Before production captures, verify callback ordering against the pinned MAME
implementation. Select a point after the screen bitmap is rendered and before
the next gameplay interrupt can mutate its contributing state, or retain the
state at the renderer's sampling point and pair it with the completed bitmap.
Record both state and bitmap frame identities. A frame-done callback alone is
not evidence of coherence. A moving-scene comparison must detect a deliberate
one-frame pairing error. If coherent pairing cannot be demonstrated, fail the
capture rather than publish a reference.

Use fresh machine configuration and frame-scheduled coin/start/direction/smoke
inputs where reproducible. Record the input sequence and reset assumptions.
Allow an explicit capture trigger for cases that need manual play, recording
how they were obtained. Neither path writes program ROM, changes CPU logic,
sets synthetic object state or disables normal shadow rendering.

## Native compositor and comparison

Keep indexed intermediate pixels and a priority buffer until final RGB
conversion. Implement the pinned renderer's tile addressing, attribute flips,
scroll offsets, modulo wrapping, foreground repetition/clips, category priority,
sprite ordering and masks, dot placement and both dot passes. Native raster
coordinates become PNG coordinates by subtracting the visible-area origin.
Verify global flip behavior separately rather than assuming a whole-image flip.

Compare all 288x224 RGB pixels with zero tolerance by default. Export the
reconstruction, a difference image and JSON containing mismatch count, bounds,
maximum channel difference and region diagnostics. Wrong dimensions, missing
state, inconsistent provenance or any pixel mismatch cause a failing command.
Any future exception requires a documented cause and explicit acceptance;
do not normalize away shadow or palette differences to make comparison pass.

## Proposed 256x212 layout

Use half-open rectangles and emit every transform in machine-readable output.
The first candidate retains the original right-hand 64-pixel information strip:
maze destination [0,192)x[0,212), information destination [192,256)x[0,212).
Crop the maze to 192x212 with camera offsets recorded in world coordinates.
Split the original 64x224 information strip into semantic HUD/radar rectangles
and repack them at 1:1 size; do not crop away twelve rows of information.

A second candidate can relocate individual HUD blocks around a wider maze
viewport. Derive exact source blocks from the real captures before selecting
its rectangles. Each candidate must include every required score, fuel, lives,
round and radar element without overlap or scaling; report an infeasible packing
instead of hiding information. Final rectangles are an implementation output
for user review, not an approved layout in this design.

Keep the complete native capture. Transform and clip each visible object using
the same camera as the maze; relocating the HUD cannot change simulation data.

## SCREEN 4 and SCREEN 5 analysis

Report distinct source palette indices and RGB values for the entire image,
regions and scanlines. For SCREEN 4, count colors in each aligned 8-pixel pattern
row of the proposed background and identify rows exceeding two colors. Separate
tile-layer constraints from the final image with objects composited over it.
Report SCREEN 5's 16-color palette budget without selecting a final conversion.

Build scanline occupancy from decoded object positions and nontransparent pens.
Distinguish source object counts, bounding-box occupancy and estimated MSX
hardware sprite entries. Estimate color-separated 16x16 sprite layers and any
extra pieces for dots or mixed effects, with explicit assumptions about color
combination, clipping and software-rendered objects. Report total entries and
the eight-entry scanline limit; do not claim these estimates prove feasibility.

## Validation and delivery

Synthetic tests cover asymmetric tile/sprite flips, scroll wrapping, foreground
addressing, clipping, category/object priority, lookup transparency, dot shadow,
coordinate transforms, malformed bundles and comparison failures. Fixtures must
contain no original game data. Existing tests must remain green.

Local integration must include a normal gameplay case and a moving-object
overlap/smoke case. Inspect images and record features actually exercised;
button input alone does not prove visible smoke or overlap. Repeat composition
and report generation from stable bundles to verify deterministic output.

Reuse output validation conventions: reject unsafe paths, symlinks, tracked or
unignored destinations and existing output by default. Publish complete bundles
from staging. Preserve earlier captures and never download ROMs. Verify source
checksums after integration and check that no derived game data is tracked.

Document exact commands, capture schema, synchronization evidence, native
comparison results, layout rectangles, constraints and untested cases in a
focused usage guide. Keep raw state, screenshots, replay data and derived
images local under ignored references paths. Link non-game-data evidence in
the delivery handoff. Do not close the issue before all acceptance and delivery
conditions are satisfied.

## Review and implementation sequence

Review this capture/comparison design first. Then prepare the implementation
plan: capture API/order verification, schema and recorder, native compositor,
comparison, real gameplay cases, layout candidates and constraint analysis,
documentation and final validation. Move project status to In Progress when
implementation starts. Commits, pushing and PR publication remain subject to
the user's authorization; this proposal does not perform those actions.

## Approved default layout decision — 2026-10-20

After reviewing the native arcade versus compact comparison, the user selected
compact as the default viewport/HUD arrangement. This supersedes the pending
layout choice in the original proposal above.

- Canvas: 256x212. Maze: native [12,6,212,218), destination [0,0,200,212).
- Right-hand HUD/radar panel: 56 pixels, X=[200,256).
- Title: `HISCORE`, omitting the dash cell while preserving glyph dimensions.
- Score, lives and round glyphs remain 1:1. Fuel uses a 52-pixel inner track
  preserving the captured fill fraction. Radar marker centres use horizontal
  7/8 projection while marker glyphs retain their original dimensions.
- CLI `--layout` and Make `SCENE_LAYOUT` default to `compact`. Generated compact
  metadata reports `status: "approved"`. The sidebar and wide proposals remain
  available through explicit overrides.

World coordinates and game rules remain unchanged. This decision selects the
layout only; MSX SCREEN mode, palette conversion and measured renderer
performance remain future work. See `docs/arcade-scenes.md` for transforms,
validation commands, constraints and remaining coverage limits.

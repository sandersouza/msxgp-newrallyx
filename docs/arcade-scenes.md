# Gameplay scene capture and composition

Issue [#6](https://github.com/sandersouza/msxgp-newrallyx/issues/6) adds a local
reference workflow used to prepare and verify the MSX build inputs. Supply the supported unpacked `nrallyx`
ROMs and run the existing setup/extractor first. Nothing downloads game data.
Python 3.14, Pillow 13.0.0 and MAME 0.289 are reused.

## Capture and reconstruct

From the repository root:

```sh
.venv/bin/python -B scripts/extract_graphics.py \
  --input references/roms/nrallyx \
  --output references/assets/nrallyx
.venv/bin/python -B scripts/arcade_scene.py capture \
  --output references/scenes/capture
.venv/bin/python -B scripts/arcade_scene.py reconstruct \
  --capture references/scenes/capture/frame-02200 \
  --output references/scenes/report
.venv/bin/python -B scripts/arcade_scene.py analyze \
  --capture references/scenes/capture/frame-02200 \
  --output references/scenes/normal-compact
.venv/bin/python -B scripts/arcade_scene.py analyze \
  --capture references/scenes/capture/frame-02760 \
  --output references/scenes/overlap-compact
```

If assets already exist unchanged, reuse them; the extractor intentionally
refuses existing output unless its documented overwrite option is supplied.
Every scene/report destination must be new. Use `--output`, `--capture`,
`--frames` to select paths and processing. There is no scene
overwrite option. Choose fresh paths to preserve prior evidence. The `preview`
command emits the preview/transforms without constraint analysis.

Direct CLI equivalents:

```sh
.venv/bin/python -B scripts/arcade_scene.py capture \
  --output references/scenes/capture \
  --frames 2200 2410 2411 2760 2761
.venv/bin/python -B scripts/arcade_scene.py analyze \
  --capture references/scenes/capture/frame-02760 \
  --output references/scenes/overlap-compact
```

The `preview` and `analyze` commands use the compact reference-input composition.
The live ROM uses the [raster layout](raster-scroll.md), not this input layout.

`--assets` defaults to `references/assets/nrallyx`; `--replay` defaults to
`scripts/scenes/gameplay-inputs.json`. Arguments use the caller's working
directory. Exit 0 means exact agreement, 1 means pixel differences (diagnostics
are retained), and 2 means invalid input or a capture/publication failure.
Previews are generated only after exact comparison passes.

Capture validates all 13 source ROMs before and after emulation. It disables
personal MAME configuration, plugins, cheats, autosave, automatic frameskip and
snapshot filtering; brightness, contrast and gamma are 1. All emulator writable
paths are below the ignored acquisition directory. Taps observe writes without
replacing data. Program ROM, CPU behavior and video RAM are never patched.

The recorder installs taps and then requests a normal machine reset. Its Lua
autoboot guard prevents recursive reinitialization after that reset. Unknown
scroll/flip state at capture or another reset invalidates the capture. An external
write-map change clears the cached observations and requires fresh writes to all
three registers. Map-change/reset subscriptions are retained alongside the taps. Replay injects input
field values after the named frame's image/state has been captured, for subsequent
game execution. The supplied replay waits through boot, inserts a coin at 1800,
starts at 1860, smokes at 2400..2429, holds Up at 2600..2999 and smokes again at
2750..2899. These are replay-frame numbers after reset, not wall-clock seconds.

Acquisition work/logs remain in ignored `references/scenes/.acquisition-*` even
on failure. Only complete, validated cases are copied to the requested run.
Publication uses a sibling lock and staging directory, with no replacement.
Every planned and actual staging/final payload is checked against Git ignore
rules, including explicit unignore exceptions. Acquisition filenames are checked
before emulation and the resulting acquisition inventory is checked afterward.
Do not delete an active acquisition/lock. If an interrupted process leaves a
lock, inspect its acquisition log and ensure the process has exited before
removing the stale lock manually. Captures, save data, RAM and screenshots must
never be attached to GitHub or committed.

## Capture schema 1 and provenance

A run contains `replay.json`, one `frame-NNNNN/` bundle per requested replay
frame and a parent `manifest.json` covering all nested payloads/manifests.
Each case contains:

| File | Meaning |
| --- | --- |
| `capture.json` | Schema/source/emulator pin, ROM hashes, asset-manifest SHA-256, phase, frame identities, emulated time, reset generation, scroll/flip, shadow factor, applied input history and acquisition description |
| `video.bin` | 4096 bytes from `:videoram`, corresponding to 0x8000..0x8fff; includes both tile layers, attributes, sprite positions/flags and dot positions |
| `radar-attributes.bin` | 16 bytes from `:radarattr`; reads at 0xa000 would instead access input ports |
| `reference.png` | Unfiltered 288x224 RGB native MAME snapshot |
| `manifest.json` | Version and sorted path/size/SHA-256 inventory of the four payloads |

`emulated_time` preserves MAME's formatted seconds (for example
`0036.299,999,999`, with grouped fractional digits); the validator also accepts
nonnegative finite decimal seconds. Both time and positive integer `replay_frame`
are required.

Scroll X/Y are observed at writes to 0xa130/0xa140; flip is bit 0 of writes to
0xa183. Reading those write-only registers is not used. Tap handles remain live
and are reinstalled after reset. Sprite/dot lists are derived from the raw RAM,
not separately edited copies. The palette comes from the verified asset export;
normal MAME shadow factor 0.6 and pen-table overrides are reproduced.

The source contract is MAME tag `mame0289`, commit
`f34f02505e32c1993c6a782b6814232cbfc74e36`, matching `scripts/graphics/nrallyx.json`.
Capture frame identities use `screen:frame_number()`; `replay_frame` names the
reset-relative input schedule. The bundle stores the entire video state, not a
resumable whole-machine save state. Composition leaves the running simulation,
the original captures and their world/scroll state intact.

## Same-frame ordering and comparison

The pinned source establishes this synchronous call chain:

1. `screen.cpp`, `screen_device::vblank_begin`: calls `video.frame_update()`
   before invoking `m_screen_vblank(1)`.
2. `video.cpp`, `video_manager::frame_update`: calls `finish_screen_updates()`,
   then `emulator_info::frame_hook()`.
3. `luaengine.cpp`, `lua_engine::frame_hook`: runs registered frame-done callbacks.
4. After the callback returns, `rallyx.cpp`, `rallyx_vblank_irq` asserts CPU IRQ.

There is no intervening gameplay CPU execution between completed rendering and
RAM/register sampling. `rallyx` does not set `VIDEO_UPDATE_AFTER_VBLANK` or perform
partial scanline updates. Zero frameskip ensures every selected frame renders.
The visible hardware rectangle is X=[0,288), Y=[16,240), not a 240-line image.

`screen:pixels()` reads `m_curbitmap`; `screen_device::update_quads` may already
have switched that bitmap to the next draw buffer. Use native
`screen:snapshot()` at the hook instead, obtaining the just-presented texture
at exactly 288x224. Python converts its lossless PNG to RGB without resampling.
Moving-frame exact matches and the negative control below test this ordering.

The compositor retains pen values until after both dot passes. In particular,
the game's shadow table remaps pens 0..15 to 16..31, leaves 16..31 unchanged,
and otherwise uses MAME's shadow bank. Replacing all of this with a transparent
dot overlay or applying 0.6 to every covered pixel is incorrect. The compositor
also follows foreground repetition, scroll offset 3, modulo-256 addressing,
attribute flips, tile category and sprite priority/lookup transparency.

Each report directory contains `reconstruction.png`, `difference.png`,
`comparison.json` and a manifest. Analysis adds `preview.png`, `layout.json`
and `constraints.json`. Comparison covers all 64,512 RGB pixels with tolerance 0;
it records mismatches, half-open bounds, maximum channel difference, maze/HUD
counts and input capture/asset manifest hashes. There are no accepted exceptions.
JSON and images have no generated timestamps or absolute acquisition paths.

## Compact build input

This composition prepares the source bundles consumed by the renderer build.
It uses a 200x212 maze crop from [12,6,212,218), placed at [0,0,200,212),
and a 56-pixel right-hand panel. `layout.json` reports `name: "compact"`
and `status: "approved"`. The live ROM recomposes the original assets into its
[raster scoreboard and sprite HUD](raster-scroll.md).
Upright cabinet captures are required for reference-input composition; native
flipped rendering remains covered by synthetic tests.

```sh
.venv/bin/python -B scripts/arcade_scene.py analyze \
  --capture references/scenes/capture/frame-02760 \
  --output references/scenes/compact-trial
open references/scenes/compact-trial/preview.png
```

The title copies `HI` and `SCORE` at their original pixel sizes, omitting only
the dash cell [240,0,248,8), so `HISCORE` occupies seven 8-pixel cells. Score
digits remain right-aligned and unscaled. The round label drops one blank cell,
retaining `ROUND` and the last two numeric cells, which accommodates one- and
two-digit round numbers. Lives and other text retain their original pixels;
the command rejects nonblank content in margins that this packing cannot fit.

| Block | Compact destination |
| --- | --- |
| Score/player information | [200,0,256,32) |
| Fuel label, ticks and gauge | [200,40,256,56) |
| Radar | [200,64,256,176) |
| Lives | [200,180,256,196) |
| Round | [200,196,256,212) |

The fuel label is copied without resizing. Tick marks are repositioned; the
gauge is redrawn with a 52-pixel inner track instead of 60, preserving the
captured fill fraction to the nearest destination pixel. It does not change
the game's fuel counter or any original assets.

Radar background flags are extracted as connected tile-layer ink components
(2x2 in the tested scenes); hardware dots retain their 4x4 source patterns.
Only horizontal centres are projected by 7/8. For a source marker with left
coordinate `x` and width `w`, its new left edge is
`200 + floor((14*(x-224) - w + 8)/16)`; Y becomes `native_y-16`.
All marker bitmaps remain 1:1 and all source coordinates/state remain intact.
Game car sprites are represented in this schematic radar by their existing
hardware dots. Dots retain their order, transparency and normal shadow colors.

`layout.json` records every text fragment, fuel row and marker transform.
Its `compact.radar` section (also `radar_projection` in `constraints.json`)
compares source/projected opaque-pixel overlaps and lists newly overlapping
marker pairs and newly clipped marker ink. Compression can introduce overlaps
in denser cases; the report exposes them rather than promising worst-case
readability. No new marker clipping or overlap was found in the five accepted
frames; each contained ten tile flags and two visible hardware dots.

## Constraint report interpretation

The [Yamaha V9938 Technical Data Book](https://map.grauw.nl/resources/video/yamaha_v9938.pdf),
Graphic 2/3, Graphic 4 and Sprite Mode 2 sections, is the hardware reference.
SCREEN 4's background patterns allow two colors per eight-pixel row. SCREEN 5
uses a 16-color palette. Sprite mode 2 has 32 entries and eight per scanline,
with per-row color selection and optional color combination.

The report measures RGB/source-index counts globally, by region and by scanline.
SCREEN 4 violations count background rows at final pattern-grid alignment,
before sprite/dot overlay. SCREEN 5 reports palette-count fit only; final
3-bit-channel palette conversion is handled by the [renderer build](raster-scroll.md). A 212-line
SCREEN 4 implementation must still resolve pattern/name-table allocation and
address wrapping, not just satisfy the row-color test.

Entry demand uses a conservative model: separate fixed-color 16x16 entries
per visible color per placed object, with 4x4 dots padded to 16x16. All 16 Y
rows consume slots even if a layer has blank pattern rows. Completely invisible
objects are omitted. The report separates bounding boxes, visible source pixels
and estimated hardware entries. Per-row recoloring/color combination could
reduce demand; priority masks, clipping and software effects may increase it.
Smoke in the tested scenes is tile-layer data and is included in background
constraints. Dot shadow mixing is an effect that ordinary opaque sprite layers
alone do not reproduce. These are measured constraints, not renderer benchmarks.

## Validation and renderer handoff

Run synthetic tests without ROMs:

```sh
.venv/bin/python -B -m unittest discover -s tests -v
git diff --check
```

Fixtures exercise flips, tile/foreground addressing, horizontal/vertical wrapping,
clipping, indirect transparency, tile/object priority, repeated shadow passes,
HUD packing, corruption/provenance failures, comparison
failure, guarded publication, row-color restrictions and multicolor entry demand.
When a standalone `lua` interpreter is available, the suite also executes the
actual recorder against a synthetic lifecycle harness covering delayed setup
notifications, lost taps, reset and incomplete initialization. That optional
harness requires no ROMs; it is skipped when `lua` is unavailable.

Local gameplay evidence includes a normal scene at replay frame 2200 and an
enemy/smoke overlap at 2760. The latter was visually inspected: the enemy at
native [126,150,142,166) crosses the smoke tile area; 49 opaque source pixels
lie over smoke tile IDs 191/194/197. This is not a claim of sprite/sprite
collision coverage. Both scenes reconstruct with zero differences. A moving
negative control using frame 2410's image and frame 2411's state produces 2,560
different pixels, bounds [14,0,190,224).

Reproduce the negative control without modifying either bundle:

```sh
.venv/bin/python -B -c 'from pathlib import Path; from scripts.scenes.bundle import load_assets,load_capture; from scripts.scenes.render import render; from scripts.scenes.compare import compare; a=load_assets(Path("references/assets/nrallyx")); p=Path("references/scenes/capture"); print(compare(load_capture(p/"frame-02410",a).reference,render(load_capture(p/"frame-02411",a),a).image))'
```

Re-run capture and analysis with fresh `--output` paths; never add derived
files inside a sealed case. Verify output
manifest hashes and pixel/report identity for unchanged inputs. Keep all actual
screenshots/RAM below ignored references paths. Hashes and mismatch/count summaries
may be shared without including original images or bytes.

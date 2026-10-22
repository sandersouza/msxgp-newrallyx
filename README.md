# New Rally-X for MSX2+

A work-in-progress port of the New Rally-X arcade game to MSX2+, focused on
preserving the original graphics, game rules and gameplay speed.

The repository provides environment setup, original-graphics tools and a
SCREEN 5 renderer with the complete original first-stage map and a controllable
car using the original movement and wall collision. The complete game runtime
is still in development.

The port targets **at least 128 KB of RAM mapper and 128 KB VRAM**. The openMSX
launchers use a session-local FS-A1WSX configuration with a 128 KB main mapper.

## Port direction

- Preserve original graphics at **1:1 pixel scale**, including 8x8 tiles and
  16x16 sprites.
- Target a **256x212** display by reducing the visible maze viewport and
  rearranging the HUD and radar. Preserve world coordinates and game rules.
- Prefer retaining the original **Z80 game logic** and adapting its hardware
  interfaces to the MSX2+.
- Use the arcade as the reference for behavior, timing, graphics and sound.
  Rendering performance and sound fidelity still require feasibility measurements
  on the target platform.

The current runtime integrates original player movement, steering and wall
collision. Enemy AI, collection, smoke, scoring/Fuel rules and sound remain
pending.

## Current status

| Area | Status |
| --- | --- |
| Development environment | macOS bootstrap with dependency and toolchain verification |
| Z80 cross-assembly | Pinned sjasmplus with a synthetic cartridge smoke test |
| Original graphics | ROM validation and extraction of tiles, sprites, dots and palette metadata |
| Arcade reference validation | Local graphics comparisons documented in the extraction guide |
| Current renderer | Complete original first-stage map with cached hardware scrolling, a fixed raster scoreboard and dynamic sprite HUD |
| HUD integration | Reusable Z80 API for score, record, lives, Fuel and radar, with a read-only original-RAM adapter |
| Player driving test | Starts automatically with original continuous movement, steering, wall collision and a following camera |
| Gameplay and hardware adaptation | [Original Z80 map and arcade traces](docs/z80-native-analysis.md), [patch/allocation contracts](docs/native-patching.md) and [clock/input/state contracts](docs/native-runtime-contracts.md); complete native runtime pending |
| Linux and Windows bootstrap | Detected, but setup is not implemented |

`make build` generates the current default diagnostic at
`references/build/newrallyx.rom`: full-screen hardware scrolling at 50 Hz, with
one-pixel bounded camera movement across the complete 768x1344 maze, original
flower borders, an eight-pixel scoreboard
fixed by a line interrupt, and a yellow life icon with a black outline followed
by a white remaining-life digit.
The scoreboard places HISCORE: and its value on the left, and 1UP: and its value
on the right, both aligned with the maze's inner edges. ROUND is deferred.
Three separator rows contain the raster transition. The native V9958 left mask
leaves a 248x201 maze; fixed R18 adjustment centres it without a right mask or
asset rescaling. The HUD and car occupy 19 sprite slots, leaving 13 free.
The ROM starts in the [driving test](docs/player.md): arrows steer the original
car, releasing them retains movement, Space pauses and Home restarts. The camera
and radar follow the car. Press **Enter** to switch to map inspection.
In inspection mode, use arrows to scroll; Space pauses, Home reloads the selected starting point and
1–5 jump to the starting area or the four map corners. Key 0
cycles the life digit through 0–9, and 9 adds test points. A transparent 48x58 sprite radar
overlays the upper right: white border/flags, a red enemy and a white/black
blinking player. The radar tracks the car while driving and the viewport center during
inspection; its patterns update every two refreshes. See [controls and verification](docs/raster-scroll.md).
Press Enter again to restart driving.
Directly below the radar, a white fuel-pump icon and yellow gauge share its
48-pixel width. Press F to cycle the diagnostic fuel levels.
The [HUD integration guide](docs/hud.md) documents every component, public calls,
state formats, register preservation and original-routine replacement boundaries.
The HUD adapter reads the original score, lives, Fuel and visibility state;
the current keyboard producer supplies demonstration values separately.
The [map guide](docs/stage-one-map.md) documents exact reconstruction, native Z80
comparisons and the VRAM tile cache. The cartridge is 1 MB; its first build
acquires and validates the original map through MAME 0.289. Complete-game and
physical-hardware validation remain pending.

`make run` opens the default ROM in openMSX and calls `make build` first if that
file is missing. An existing ROM is reused; use `make build` to rebuild after
source changes. Each build keeps its evidence in a fresh `references/build/default-*/`
directory and publishes the default ROM only on success. Each launch uses fresh
isolated settings in `references/build/run-*/`. The launcher uses Panasonic
FS-A1WSX and contributor-supplied BIOS under `references/msxbios/`; see the
[BIOS requirements](docs/setup.md#machine-and-contributor-supplied-bios).

Use `python3 -B scripts/clean.py --dry-run` to preview generated builds and
`make clean` to remove all contents of `references/build/`, including ROMs, screenshots,
reports and emulator session data. The build directory and its top-level
`.gitkeep`, if present, are retained. Original ROMs, BIOS, extracted assets,
scene captures, `.venv` and `.tools` are preserved. Cleaning also removes local
evidence linked by the renderer guide; rebuild to recreate it.

## Quick start

Run the following commands from the repository root.

### 1. Prepare the development environment

On macOS, install Xcode Command Line Tools and native Homebrew first. Use a
native Apple Silicon or Intel terminal; Rosetta shells are not supported by the
bootstrap. See the [setup guide](docs/setup.md#macos-prerequisites) for details.

Preview the required changes, then install and verify:

```sh
bash scripts/setup.sh --dry-run
make environment
make environment-check
```

Setup prepares Python/Pillow, a pinned local sjasmplus cross-assembler, z80dasm,
MAME, openMSX, ShellCheck, Git and GitHub CLI. It creates a project-local `.venv`
and stores the managed assembler and smoke-test outputs under `.tools/`.

Setup does not download game ROMs or MSX BIOS ROMs. Emulator availability checks
do not boot an arcade or MSX machine.

### 2. Supply the original ROM set

Place your own **unpacked** `nrallyx` ROM set in:

```text
references/roms/nrallyx/
```

The supported set is pinned to MAME 0.289. All 13 files must match the names,
sizes and checksums in the [ROM inventory](scripts/graphics/nrallyx.json),
including program and sound ROMs that the graphics extractor does not decode.
Other revisions and ZIP input are not supported by this extractor.

### 3. Extract the graphics

```sh
.venv/bin/python -B scripts/extract_graphics.py \
  --input references/roms/nrallyx --output references/assets/nrallyx
```

Output is written to `references/assets/nrallyx/`. It includes original pixel
indices, indexed atlases, color previews, palette and layout metadata, and a
manifest recording source and output hashes. Original dimensions are preserved.

Existing output is protected. To replace a complete, unchanged extraction:

```sh
.venv/bin/python -B scripts/extract_graphics.py \
  --input references/roms/nrallyx --output references/assets/nrallyx --overwrite
```

To keep an earlier extraction, choose a different destination below
`references/assets/`:

```sh
.venv/bin/python -B scripts/extract_graphics.py \
  --input references/roms/nrallyx --output references/assets/nrallyx-other
```

See [graphics extraction](docs/graphics-extraction.md) for input overrides,
output formats, overwrite checks, recovery and optional MAME comparisons.

### 4. Prepare scenes and run the diagnostic

Follow the [scene guide](docs/arcade-scenes.md) to capture the reference scenes,
then analyze the normal and overlap captures to generate the approved bundles at `references/scenes/rom-input/normal` and
`references/scenes/rom-input/overlap`. The default build reads captures from
`references/scenes/review-fixed-v3/`; use that path when capturing:

```sh
.venv/bin/python -B scripts/arcade_scene.py capture \
  --output references/scenes/review-fixed-v3
.venv/bin/python -B scripts/arcade_scene.py analyze \
  --capture references/scenes/review-fixed-v3/frame-02200 \
  --output references/scenes/rom-input/normal
.venv/bin/python -B scripts/arcade_scene.py analyze \
  --capture references/scenes/review-fixed-v3/frame-02760 \
  --output references/scenes/rom-input/overlap
```

Reuse existing verified captures and input bundles if present. Supply the
compatible BIOS locally, then:

```sh
make run
```

## Commands

| Command | Purpose |
| --- | --- |
| `make environment` | Install dependencies and prepare or verify the local environment |
| `make environment-check` | Verify the environment without installing or rebuilding |
| `make build` | Rebuild and publish `references/build/newrallyx.rom` |
| `make run` | Build if the default ROM is missing, then start openMSX |
| `make test` | Run the automated test suite |
| `make clean` | Remove generated builds and emulator sessions |

Plain `make` is equivalent to `make build`. Asset extraction, scene processing
and renderer verification use their script CLIs; they are not Make targets.

## Repository layout

| Path | Contents |
| --- | --- |
| `docs/setup.md` | Environment prerequisites, toolchain, troubleshooting and validation evidence |
| `docs/graphics-extraction.md` | ROM requirements, extraction schema, provenance and reference checks |
| `docs/raster-scroll.md` | Current renderer, controls, memory ownership, integration contract and measured timing |
| `docs/hud.md` | Reusable HUD API, initialization, scheduling and original-game adapter |
| `docs/player.md` | Original player movement, driving controls, sprites and raster integration |
| `docs/stage-one-map.md` | Exact first-stage reconstruction, native checks and hidden-tile streaming |
| `scripts/environment/` | macOS provisioning support and toolchain verification |
| `scripts/graphics/` | ROM inventory, graphics decoding/export and MAME reference harness |
| `scripts/extract_graphics.py` | Graphics-extraction CLI |
| `tests/` | Automated tests and synthetic fixtures |
| `references/roms/` | Local contributor-supplied ROMs; ignored by Git |
| `references/assets/` | Local extracted graphics; ignored by Git |
| `references/disassembly/` | Local disassembly material; ignored by Git |
| `.venv/`, `.tools/` | Generated environment, managed tools and smoke-test cache; ignored by Git |

Use the setup, extraction, map and renderer guides for the supported workflow.

## Validation and contributions

Capture real arcade gameplay, reconstruct native frames and generate the approved
256x212 compact reference layout with `scripts/arcade_scene.py capture` and
`analyze`. These input bundles use the earlier 200x212 maze and 56-pixel sidebar;
the current ROM recomposes their original-size assets into the raster layout. See the
[arcade scene guide](docs/arcade-scenes.md) for commands, synchronization evidence,
comparison results and SCREEN 4/5 constraints. Captures and previews remain local.

The automated tests use synthetic fixtures and do not require original game data.
Run them after preparing the environment:

```sh
make test
git diff --check
```

Local comparisons against the original game require contributor-supplied ROMs and
MAME. Reproduction commands and limitations are documented in the
[player guide](docs/player.md#verification), [HUD guide](docs/hud.md#verification)
and [extraction guide](docs/graphics-extraction.md#synthetic-tests-and-optional-local-mame-validation).

Keep documentation, issue bodies and code in English. Read [AGENTS.md](AGENTS.md)
before changing the repository or managing GitHub work.

## Original game data

ROMs, extracted assets, disassembly and captures must remain local under ignored
`references/` directories. Only directory markers are tracked there. Commit
tools, documentation, metadata and synthetic fixtures; never commit original
game data, including data embedded in test fixtures.

Contributors supply their own ROMs. Project tools must not download or
redistribute game ROMs or proprietary BIOS images. No permission to redistribute
original game data is granted by this repository.

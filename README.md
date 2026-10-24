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
| Gameplay and hardware adaptation | [Original Z80 map](docs/z80-native-analysis.md), [patch/allocation](docs/native-patching.md), [clock/input/state contracts](docs/native-runtime-contracts.md) and [native loader/mapper proof](docs/native-loader.md); complete native runtime pending |
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

Select a test cartridge with `make run ROM=references/build/<test-build>/native.rom`.
The selected file is launched directly; a missing test ROM reports an error.
Omit `ROM` to use the default development cartridge.
The approved Issue 11 build is **stage 12**, selected by plain `make build` and
`make run`. Its ROM matches the user-tested v260 cartridge. The earlier driving
reference remains available with `make build STAGE=8` or its named checkpoints.

The preserved **stage 08** build is the fast driving baseline plus an
explicit bitmap-rock fixture. Normal first-stage initialization has no rocks;
this test adds two original placement outputs and records diagnostic collision
entry events without extra sprites. Selected original player movement/steering/wall routines remain active;
the complete arcade foreground/IRQ loop is absent. Rock contact now triggers the
original 24x24 bitmap explosion and one life loss. The hold lasts 120 logical
ticks with lives remaining, 96 on the final life. Automatic restart preserves
the same round's collected flags, score and high score, refills fuel and resets
the new life's flag-point ordinal. The HUD shows actual spare cars. Flags are
now collected once and removed from the bitmap/radar, including after cache
reload. The score/high-score HUD now uses actual flag points and the special
multiplier. Original decimal fuel consumption, empty-fuel deceleration and the
round-dependent lucky countdown are now active; the gauge shows actual fuel.
Lucky restores the pre-countdown fuel and is excluded when collected last.
One original enemy now pursues the player, appears on the radar, and causes
the same explosion/life loss on contact. Two additional sprite planes bring
the total to 21 slots, with 11 free; the measured line peak remains eight.
The score header has its original black background. The transparent radar has
a square white border, using the same sprite patterns and instruction stream.
A solid blue radar fill would require another layer or work during scrolling;
the existing transparent background is retained under the zero-extra-cost constraint.
Zero lives stops this fixture; Home starts a fresh test run. Additional enemies,
credit/start/transition presentation remain pending in this reference. F and 0 fixture keys are
disabled while driving. See the [fuel performance report](docs/fuel-performance-fix.md)
and [one-enemy evidence and adaptations](docs/one-enemy-plan.md).
Use `make build STAGE=0` to
recreate the preserved movement-only baseline.
`make run LATEST=1` selects approved session `11-r12-smoke-irq-v260`. Press **5**
for credit and **1** to start. Arrows or joystick1 steer, **Space**, Ctrl or triggerA
releases smoke, **P** pauses and Home resets the development run. Original
graphics, complete sprite cars, normal sprite radar and HUD remain. All ten
flags lead to the source fuel bonus and a clear screen; credit/start begins a
new game with its high score retained. Game-over screens hide gameplay sprites.
The fuel bar turns red below 10% (less than six original tank units); exactly
10% stays yellow. The S flag blinks on the existing sprite radar. The life icon
keeps its yellow silhouette and black outline. The footer uses three sprites,
sharing the fuel gauge's three slots; peak allocation stays
20 entries with twelve free. Keyboard/joystick directions pass through a four-way
gate: a new direction wins over a still-held old direction. A corner guard rejects
wall-center movement while retaining steering so the car can escape. Fuel patterns
publish on VBlank, including the restored amount on the refresh after the L bonus.
Score publication and input preparation keep raster interrupts serviceable;
the extended L route and multi-key stress test check every header reservation.
Smoke queue preparation and publication bookkeeping also service interrupts;
explosions retain priority over smoke copies. Repeated Space firing is included
in the header regression. Corner rejection preserves native centering as well
as the newly selected direction.
Occasional timing delays remain.
Rebuild with `make build STAGE=12`. Later rounds/two players and sound remain
outside this segment. See [validation and limits](docs/completion-integration-plan.md).
The rock/smoke stress checkpoint remains available as
`make run CHECKPOINT=11-r10-coherent-v207` (1,812 cache states/59 RGB, 2.26%
held refreshes). See [checkpoints and limits](docs/checkpoints.md).

`make run CHECKPOINT=11-r09-two-gameplay-v152` selects two original enemies,
complete car drawings/windows, sprite radar and full HUD at 50 Hz. The natural
route passes 1,138 complete visible-cache states and 28 full RGB images. Its
22 SAT entries leave ten free; line occupancy peaks at nine candidates with
real hardware limits enabled. Main intervals have median 19.937 ms and maximum
33.313 ms, so this is a test checkpoint with timing still unaccepted.
Rebuild this population with `make build STAGE=9 ENEMIES=2`.
The default `make run` cartridge remains the accepted one-enemy
`11-r09-player-dot-50-v115` until explicitly rebuilt.
The user rejected `11-outline-flicker-60-v144`: its row-color simplification
removed upper window detail, and moving gameplay was slow with broken scenery.
It is preserved only as failed experimental evidence. Any subsequent priority
test must preserve the original dependent car planes together; stationary
overflow success does not establish moving gameplay acceptance.
See [the rejected experiment](docs/sprite-flicker-experiment.md).
The rejected blue bitmap-radar test is preserved outside `LATEST` as
`11-r09-radar-blitter-hud-v139`.

The accepted reference is `make run CHECKPOINT=11-r09-player-dot-50-v115`: one original enemy with
HUD at 50 Hz and the original 16.5 ms logical clock. Twelve radar sprites keep
the map, flags and enemy dynamic; one independent player dot alternates white
and black every eight native ticks, matching the original routine. Moving the
player does not dirty the map cells. Twenty SAT slots are used, leaving twelve
free. Both the 1,138-state contact/restart route (28 RGB images) and the
1,600-state movement/cache control (39 RGB) pass the unchanged timing gate.
Arrows steer, Space pauses and Home resets. Rebuild with `make build STAGE=9`.
The two-enemy HUD-off reference remains
`make run CHECKPOINT=11-r09-two-no-hud-v80` (60 Hz, six slots, 26 free).
`ENEMIES=3` is a separate diagnostic: native logic and car/radar component
proofs pass, but its moving predecessor corrupts the bottom scenery row. It
is not selected by `LATEST`. Neither checkpoint completes #11. Sprite-line
overflow alone no longer blocks gameplay integration, following the user's
decision; keep hardware limits enabled and document resulting culling.
The integrated bitmap-player test is available separately as
`make run CHECKPOINT=11-r09-player-blitter-hud-v130`: eighteen sprites used,
fourteen free, with the full HUD and one enemy. It passes natural-route pixels
and cache but still fails timing and radar backlog. It remains available for
future correction; the radar experiment uses the sprite car instead.
New gameplay/performance tests keep the HUD enabled unless explicitly requested
otherwise. See [the blitter evidence](docs/bitmap-blitter-experiments.md).
The preserved stage 08 reference is `make run CHECKPOINT=11-r08-restored-v1`.
See the
[current checkpoint guide](docs/checkpoints.md).
The preserved sprite priority experiment starts paused with two enemies over
the radar: `make run CHECKPOINT=11-flicker-60-v6`; compare with
`make run CHECKPOINT=11-flicker-50-v6`. Space resumes an unaccepted moving
prototype, Home resets the controlled fixture. Rebuild with
`make build STAGE=9 SPRITE_FLICKER=1 FLICKER_STRESS=1 HZ=60` (or `HZ=50`).
Both rates pass controlled display/RGB checks; moving integration remains
pending. Flicker changes priority and uses 24 slots/eight free, without lifting
the hardware limit. See [evidence and limitations](docs/sprite-flicker-experiment.md).
The previous rendering experiment uses the movement baseline with a bitmap
player: `make build STAGE=0 PLAYER_BLITTER=1`, also supporting `NO_HUD=1`.
`RADAR_BLITTER=1` additionally selects the **slow diagnostic** with a blue
48x80 bitmap radar. The approved gameplay default is stage 12; see
[blitter checkpoints, measurements and limitations](docs/bitmap-blitter-experiments.md).
See the [incremental gameplay plan](docs/incremental-gameplay-plan.md).
Use `make build NO_HUD=1` to compile this same baseline without HUD frame work;
plain `make build` includes HUD. `NATIVE=1` remains a compatibility alias for the
baseline and no longer starts the abandoned full-loop candidate.
Both builds publish the default ROM and update `references/build/latest.rom`, a
relative symlink to the sealed stage cartridge. Run it with `make run LATEST=1`.
Historical full-runtime probe commands do not replace this active latest link.
Missing latest builds fail explicitly;
`LATEST`, `CHECKPOINT`, and an explicit `ROM` selection are mutually exclusive.
Use `make checkpoints` to list published local test builds, then
`make run CHECKPOINT=<name>` to launch one. Checkpoint names retain their exact
cartridge/evidence hashes; later experiments receive new names. Cleaning the
build directory removes these local checkpoints too.
See the [checkpoint comparison guide](docs/checkpoints.md) for enabled components,
controls and current validation limits.

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
make extract-graphics
```

Output is written to `references/assets/nrallyx/`. It includes original pixel
indices, indexed atlases, color previews, palette and layout metadata, and a
manifest recording source and output hashes. Original dimensions are preserved.

Existing output is protected. To replace a complete, unchanged extraction:

```sh
make extract-graphics OVERWRITE=1
```

To keep an earlier extraction, choose a different destination below
`references/assets/`:

```sh
make extract-graphics GRAPHICS_OUTPUT="references/assets/nrallyx-other"
```

See [graphics extraction](docs/graphics-extraction.md) for input overrides,
output formats, overwrite checks, recovery and optional MAME comparisons.

### 4. Prepare scenes and run the diagnostic

Follow the [scene guide](docs/arcade-scenes.md) to capture the reference scenes,
then analyze the normal and overlap captures to generate the approved bundles at `references/scenes/rom-input/normal` and
`references/scenes/rom-input/overlap`. The default build reads captures from
`references/scenes/review-fixed-v3/`; use that path when capturing:

```sh
make prepare-scenes
```

This captures the reference frames first, then analyzes the normal and overlap
frames in order. To run the steps separately, use `make capture-scenes` and
`make analyze-scenes`. Existing destinations are protected by default. Use
`make prepare-scenes OVERWRITE=1` to replace complete, unchanged capture and
analysis bundles with matching payload inventories. Modified bundles, unknown
files, directories or symlinks are preserved and cause an error. Override `SCENES_CAPTURE`,
`SCENES_NORMAL` and `SCENES_OVERLAP` for a fresh run; `GRAPHICS_OUTPUT` selects
the extracted assets. The default build expects the standard paths above.

Reuse existing verified captures and input bundles if present: run only
`make analyze-scenes` if captures already exist, or proceed to `make run` if
both bundles are ready. Supply the compatible BIOS locally, then:

```sh
make run
```

## Commands

| Command | Purpose |
| --- | --- |
| `make environment` | Install dependencies and prepare or verify the local environment |
| `make environment-check` | Verify the environment without installing or rebuilding |
| `make extract-graphics` | Extract original arcade graphics into `references/assets/nrallyx/` |
| `make capture-scenes` | Capture the arcade reference frames with MAME |
| `make analyze-scenes` | Analyze normal and overlap captures into build input bundles |
| `make prepare-scenes` | Capture scenes, then analyze both input bundles in order |
| `make build` | Rebuild and publish `references/build/newrallyx.rom` |
| `make run` | Build if the default ROM is missing, then start openMSX |
| `make test` | Run the automated test suite |
| `make clean` | Remove generated builds and emulator sessions |

Plain `make` is equivalent to `make build`. Renderer verification uses its
script CLIs.

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

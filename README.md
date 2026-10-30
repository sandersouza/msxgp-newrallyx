[![Buy me a coffee!](docs/bymeacoffee.png)](https://link.mercadopago.com.br/buymecoke)

**Help bring more projects to the community.** This is a passion project with
no profit motive, no sponsors and no outside funding so far. Every piece of
equipment, all materials and every hour of development have been paid for or
contributed personally, without reimbursement.

Your contribution helps sustain New Rally-X for MSX2+ and makes room for new
projects, with the code always freely available to the community. More financial
support means more resources and time to build, test and share. If you enjoy
this work and want to see more of it, please consider buying me a coffee.
Every contribution helps keep these projects moving. Thank you for being part
of what comes next!

# New Rally-X for MSX2+
![](docs/image03.png)

MSX2+ port of the New Rally-X arcade game, focused on
preserving the original graphics and core game rules within a measured MSX timing budget.

The repository provides environment setup, original-graphics tools and a
default SCREEN 4 presenter integrating the original Z80 gameplay routines with
dynamic rounds, enemies, smoke, PSG audio and one/two-player sessions. The earlier
SCREEN 5 presenter with sprite HUD remains available as an independent build.

The default port requires **64 KiB mapper RAM and 128 KiB VRAM**. One ROM
automatically selects the faster radar cache when at least128 KiB RAM is
available, and factory CPU acceleration on supported Panasonic machines.
The first hardware-check screen reports `MAPPER <size>K` and `TURBO ON/OFF`.
The cartridge remains below the mandatory **2 MiB** limit. The openMSX launcher
uses a private FS-A1WSX definition with cartridge type ASCII16.
See the [current architecture](docs/architecture.md) for source ownership and
[maintenance guide](docs/maintenance.md) for dependency/retention decisions,
baseline ROM hashes and cycle-ledger reproduction.

## Port direction

Developer handoff: [guide and code map](docs/developer-guide.md),
[engineering lessons](docs/engineering-lessons.md) and
[include/API contracts](src/screen4/modules/README.md). These preserve the
techniques and their reuse limits; raw experiment directories are disposable.

- Preserve original graphics at **1:1 pixel scale**, including 8x8 tiles and
  16x16 sprites.
- Target a **256x212** display by reducing the visible maze viewport and
  rearranging the HUD and radar. Preserve world coordinates and game rules.
- Prefer retaining the original **Z80 game logic** and adapting its hardware
  interfaces to the MSX2+.
- Use the arcade as the reference for behavior, timing, graphics and sound.
  Rendering performance and sound fidelity still require feasibility measurements
  on the target platform.

## Current status

### Build and launch modes

```sh
make run                     # one automatic ROM;64KiB emulator, HUD enabled
make run MAPPER=1            # same ROM;128KiB emulator
make run TEST_MODE=1         # Enter: next round; =: toggle invulnerability
make run TURBO=0             # automatic RAM detection; base-CPU diagnostic
make run LEGACY=1            # original SCREEN 5 / sprite HUD / PSG baseline
```

The lowercase spelling `legacy=1` is also accepted. Test mode keeps walls solid;
it prevents collision deaths and advances rounds without the fuel bonus. It is
an optimized-presenter option; it is not added to the preserved legacy build.
`make build` uses the same selection without opening the emulator.
The default ROM is **`dist/newrallyx.rom`**, or `dist/test/newrallyx.rom` with
test mode. Both use ASCII16; select that cartridge type when loading in WebMSX.
`dist/manifest.json` records the exact ROM hash, size and configuration.
`MAPPER=1` selects128KiB in the emulator; the default and `MAPPER=0` select64KiB.
All select the same automatic ROM, build options and exported filename.
The legacy ROM remains
`dist/legacy/newrallyx.rom`. Unqualified `make run` rebuilds before launch;
an explicit `ROM=...`, `CHECKPOINT=...` or `LATEST=1` selects an existing artifact.
`make run-experiments` remains an alias for the optimized build.
See the [artifact layout](docs/artifact-layout.md) for generated intermediates,
diagnostic variants, emulator sessions and cleanup. Raw development data is
disposable; compact results and hashes remain in `docs/`.

The [automatic hardware selection](docs/issue39-software-turbo.md) defaults to
`MAPPER=auto TURBO=1`. Supported machines use Panasonic factory Z80 turbo or
turboR R800 ROM for measured CPU-only scopes; other machines use base Z80.
`TURBO ON` reports the available acceleration backend; hardware transfers,
audio, menus and synchronization run at base timing. No separate user builds
are needed for different machines. Stock turboR tests use, for example,
`NRX_REFERENCE_MACHINE=Panasonic_FS-A1ST make run` (256KiB).

The [64 KiB cache strategy](docs/ram64-variant.md) remains the fallback.
`MAPPER` controls emulated RAM only; `TURBO=0` retains a base-CPU diagnostic build. Original graphics,
128 KiB VRAM and ASCII16 requirements remain. Emulator results and pending user
audio/perceptual acceptance are separate from physical-hardware qualification.

Original game ROMs and MSX BIOS must be supplied locally as described in
[setup](docs/setup.md). The original 56x8 `namco` title artwork is extracted from
those ROMs and checked against its native pixel digest.
The optional MSX logo uses [`assets/msxlogo.bmp`](assets/msxlogo.bmp), the supplied
54x20 one-bit artwork, copied at1:1 without resizing or color reduction.

The following historical renderer details and diagnostic flags describe
`LEGACY=1`. For the optimized presenter and measured limits see
[the full-session laboratory](src/screen4/README.md).

The `LEGACY=1` cartridge provides PSG music/effects, normal/challenge rounds,
original flag/rock placement on four maps, MSX-adapted enemies and native smoke, fuel bonuses,
death/restart, alternating two-player sessions, game over and an autonomous
attract demonstration. It retains original-size graphics, the complete car
drawings, the full HUD and the real V9958 sprite limit.

The eight-pixel header aligns with the maze viewport and shows seven score/high-score
digits, the selected player and two round digits (infinity above 99). Credits use
one digit, capped visually at nine. Native score/round/credit counters retain
their full range. The life digit shows spare cars, capped at nine.
A 248x201 maze viewport preserves world coordinates. The full game targets
**30 FPS presentation** on approximately 60 Hz NTSC output, as approved by the
user. Complete car masks, attributes and both camera axes publish together.
Input, fuel, phase and startup/spin clocks target approximately 59.92 Hz.
Player/enemy motion and spatial decisions use doubled fractional steps every
other tick; presentation consumes the completed preceding simulation snapshot. Pursuit is
adapted for the MSX, with decisions at intersections and bounded speeds.
Original art, colors, complete cars and the HUD remain intact. Occasional
missed publication slots and camera waits remain measured separately from
average FPS. See [current measurements and limits](docs/issue12-performance-analysis.md).

```sh
make build LEGACY=1
make run LEGACY=1
```

Press **5** for a credit, **1** for one player or **2** for two players (two
credits). Both players use arrows or joystick1 on alternating turns. **Space**,
Ctrl or triggerA releases smoke; **P** pauses; Home resets the development run.
**F5** advances one round per press for debugging, preserving score and lives
without awarding the completion bonus. It also resumes a paused game.
**F4** toggles audio without stopping the music clock or changing gameplay.
Development openMSX launches bind **F6** to save the screen, complete state and
preceding replay. Closing the emulator also saves the replay automatically in
the printed session directory under ignored `references/build/`.
With no credits, the original cast screen periodically enters an automatic demo.

Start/completion music plays all three original parts together. During driving,
two music parts leave channel C for a hardware-envelope engine and pitched
effects; smoke/crash also use noise. Credit, flags and fuel retain their original
note contours. Scores are compiled locally, and short deferred publication keeps
audio off the car/camera snapshot path. PSG timbres remain an adaptation of the
arcade sound. See the [audio contract and validation](docs/issue13-audio-interface.md).
`make build LEGACY=1 AUDIO=0` reconstructs the accepted silent full-game baseline.

Builds use fresh sealed directories under `references/build/default-*/` and
publish `dist/legacy/newrallyx.rom` only after success in legacy mode.
`make run LATEST=1` launches the most recent sealed build; named historical
cartridges remain available through `make checkpoints` and
`make run CHECKPOINT=<name>`. An explicit `ROM=<path>` selects another cartridge.

`make build LEGACY=1 FULL_GAME=0` reconstructs the bounded Issue 11 stage12 reference.
Earlier diagnostic stages remain available with `LEGACY=1 STAGE=0..11`; their controls,
contracts and historical limitations are in the [checkpoint guide](docs/checkpoints.md).
They do not provide complete-game progression. `NATIVE=1` remains a compatibility
alias for the bounded selected-routine reference.

Validation uses openMSX 21.0, 60 Hz full-game VDP output, a 128 KB RAM mapper and 128 KB
VRAM. The game detects the Panasonic's factory 5.37 MHz mode for pure CPU work;
VDP access and raster IRQs use 3.58 MHz. Other machines retain their base clock;
the reported cadence depends on the factory mode. The launcher uses an isolated FS-A1WSX
configuration and contributor-supplied BIOS under `references/msxbios/`.
See [setup](docs/setup.md#machine-and-contributor-supplied-bios).
Bounded stages retain 50 Hz; `make build LEGACY=1 HZ=50` explicitly selects that refresh
for a full-game diagnostic.
Validation distinguishes real scanout recordings, source-pixel/VRAM proofs,
natural routes and controlled population fixtures. Physical hardware and full
human gameplay/culling acceptance remain review items.

Use `python3 -B scripts/clean.py --dry-run` to inspect generated build contents.
`make clean` deletes generated builds, caches, raw measurements, sessions,
archives and per-issue working data. It preserves the playable `dist/` ROM,
contributor inputs and compact documented results. Required caches regenerate
on the next build; raw historical traces are not retained.

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
sizes and checksums in the [ROM inventory](src/toolchain/graphics/nrallyx.json),
including program and sound ROMs that the graphics extractor does not decode.
Other revisions and ZIP input are not supported by this extractor.

### 3. Build or run

```sh
make build                   # Creates dist/newrallyx.rom (ASCII16)
make run                     # Builds, then launches openMSX (your BIOS required)
```

Both commands automatically check and prepare missing graphics, arcade captures,
reconstructed scenes and original native-state inputs under `assets/arcade/`.
The first build runs headless MAME; later builds verify and reuse valid bundles.
You do not need to copy generated assets from another developer or an old build.

To prepare all inputs explicitly before compiling, run `make extract-all`.
Individual stages are `make extract-graphics`, `make extract-scenes` and
`make extract-native`; `make extract-grafics` is also accepted. Default extraction
commands are safe to repeat. Edited or incompatible bundles cause an error;
they are preserved for inspection.

**First time here?** Follow [Build your first MSX ROM](docs/building.md), including
all 13 required filenames, emulator BIOS requirements and simple recovery steps.
The [graphics guide](docs/graphics-extraction.md) documents custom destinations
and guarded overwrite behavior for advanced use.

## Commands

| Command | Purpose |
| --- | --- |
| `make environment` | Install dependencies and prepare or verify the local environment |
| `make environment-check` | Verify the environment without installing or rebuilding |
| `make extract-all` | Prepare every arcade input required by the build |
| `make extract-scenes` / `make extract-native` | Prepare and verify individual capture/native stages |
| `make extract-graphics` | Extract original arcade graphics into `assets/arcade/nrallyx/` |
| `make capture-scenes` | Capture the arcade reference frames with MAME |
| `make analyze-scenes` | Analyze normal and overlap captures into build input bundles |
| `make prepare-scenes` | Alias for idempotent `make extract-scenes` |
| `make build` | Rebuild optimized SCREEN 4 and export the normal/ASCII16 cartridge copies |
| `make build TEST_MODE=1` | Rebuild a separate optimized test-mode cartridge |
| `make build LEGACY=1` | Rebuild SCREEN 5 and publish `references/build/newrallyx.rom` |
| `make run` | Rebuild the selected presenter, then start isolated openMSX |
| `make run ROM=<path>` | Launch an existing cartridge without rebuilding |
| `make run CHECKPOINT=<name>` / `make run LATEST=1` | Launch a named checkpoint / latest sealed legacy artifact |
| `make test` | Run general unit tests |
| `make test-experiments` | Rebuild and verify the full optimized session |
| `make clean` | Remove generated builds and emulator sessions |

Plain `make` is equivalent to `make build`. Renderer verification uses its
script CLIs.

## Repository layout

| Path | Contents |
| --- | --- |
| `docs/architecture.md` | Current SCREEN 4/5 source, memory, mapper and IRQ ownership |
| `docs/maintenance.md` | Inventory, generated-output retention and cycle-ledger reproduction |
| `src/screen4/` | Optimized Z80 presenter and assembly adapters |
| `src/toolchain/` | Host conversion/build tools, emulator contracts and maintained workloads |
| `src/screen5/` | Maintained SCREEN 5 legacy sources and shared Z80 helpers |
| `docs/setup.md` | Environment prerequisites, toolchain, troubleshooting and validation evidence |
| `docs/graphics-extraction.md` | ROM requirements, extraction schema, provenance and reference checks |
| `docs/full-gameplay-inventory.md` | Complete-game integration, evidence and remaining limits |
| `docs/raster-scroll.md` | Renderer baseline, controls, memory ownership, integration contract and measured timing |
| `docs/hud.md` | Reusable HUD API, initialization, scheduling and original-game adapter |
| `docs/player.md` | Original player movement, driving controls, sprites and raster integration |
| `docs/stage-one-map.md` | Exact first-stage reconstruction, native checks and hidden-tile streaming |
| `src/toolchain/environment/` | macOS provisioning support and toolchain verification |
| `src/toolchain/graphics/` | ROM inventory, graphics decoding/export and MAME reference harness |
| `scripts/extract_graphics.py` | Graphics-extraction CLI |
| `tests/` | Automated tests and synthetic fixtures |
| `dist/` | Delivered cartridges and manifests; ignored by Git |
| `docs/measurements/audio/` | Retained historical metadata used by audio regression checks |
| `references/roms/` | Local contributor-supplied ROMs; ignored by Git |
| `assets/arcade/` | Canonical extracted inputs and exact converted ROM resources; ignored by Git |
| `references/disassembly/` | Local disassembly material; ignored by Git |
| `.venv/`, `.tools/` | Generated environment, managed tools and smoke-test cache; ignored by Git |

Start with setup and the current architecture; bounded-stage renderer/map guides
and old checkpoint measurements retain their explicitly historical scopes.

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

See [resource ownership and port scaffold](docs/repository-layout.md) for extraction, conversion, tool placement and retention rules.

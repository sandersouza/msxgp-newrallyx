# New Rally-X for MSX2+

A work-in-progress port of the New Rally-X arcade game to MSX2+, focused on
preserving the original graphics, game rules and gameplay speed.

The repository currently provides development-environment setup and tools for
extracting original graphics from contributor-supplied ROMs. **There is no
playable MSX build yet.**

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

These are project goals and constraints; the current extraction tools do not
convert graphics to an MSX video format or implement the game runtime.

## Current status

| Area | Status |
| --- | --- |
| Development environment | macOS bootstrap with dependency and toolchain verification |
| Z80 cross-assembly | Pinned sjasmplus with a synthetic cartridge smoke test |
| Original graphics | ROM validation and extraction of tiles, sprites, dots and palette metadata |
| Arcade reference validation | Local graphics comparisons documented in the extraction guide |
| MSX runtime, hardware adaptation and game build | Pending |
| Linux and Windows bootstrap | Detected, but setup is not implemented |

The synthetic cartridge verifies assembly and disassembly; it does not establish
that the game runs in openMSX or on physical hardware.

## Quick start

Run the following commands from the repository root.

### 1. Prepare the development environment

On macOS, install Xcode Command Line Tools and native Homebrew first. Use a
native Apple Silicon or Intel terminal; Rosetta shells are not supported by the
bootstrap. See the [setup guide](docs/setup.md#macos-prerequisites) for details.

Preview the required changes, then install and verify:

```sh
make environment-dry-run
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

## Commands

| Command | Purpose |
| --- | --- |
| `make environment` | Install missing dependencies and prepare or verify the local environment |
| `make environment-dry-run` | Preview setup changes without installing or creating the environment |
| `make environment-check` | Verify an existing environment without installing or rebuilding |
| `make extract-graphics` | Validate contributor ROMs and extract original graphics locally |
| `.venv/bin/python -B -m unittest discover -s tests -v` | Run the test suite with the project interpreter |

There is no game build or play target yet. For tool paths and manual debugging
entry points, see the [Z80 toolchain guide](docs/setup.md#complete-z80-toolchain).

## Repository layout

| Path | Contents |
| --- | --- |
| `docs/setup.md` | Environment prerequisites, toolchain, troubleshooting and validation evidence |
| `docs/graphics-extraction.md` | ROM requirements, extraction schema, provenance and reference checks |
| `docs/superpowers/specs/` | Design documents for scoped work |
| `docs/superpowers/plans/` | Implementation plans and progress notes |
| `scripts/environment/` | macOS provisioning support and toolchain verification |
| `scripts/graphics/` | ROM inventory, graphics decoding/export and MAME reference harness |
| `scripts/extract_graphics.py` | Graphics-extraction CLI |
| `tests/` | Automated tests and synthetic fixtures |
| `references/roms/` | Local contributor-supplied ROMs; ignored by Git |
| `references/assets/` | Local extracted graphics; ignored by Git |
| `references/disassembly/` | Local disassembly material; ignored by Git |
| `.venv/`, `.tools/` | Generated environment, managed tools and smoke-test cache; ignored by Git |

Use the setup and extraction guides for current operational instructions. Design
documents and implementation plans describe individual work items and may include
historical decisions or steps that have since been completed.

## Validation and contributions

Capture real arcade gameplay, reconstruct native frames and generate the approved
256x212 compact layout with `make capture-scene` and `make analyze-scene`. The
default uses a 200x212 maze and a 56-pixel HUD/radar panel with `HISCORE`. See the
[arcade scene guide](docs/arcade-scenes.md) for commands, synchronization evidence,
comparison results and SCREEN 4/5 constraints. Captures and previews remain local.

The automated tests use synthetic fixtures and do not require original game data.
Run them after preparing the environment:

```sh
.venv/bin/python -B -m unittest discover -s tests -v
git diff --check
```

Local comparisons against the original game require contributor-supplied ROMs and
MAME. Recorded results and their limitations are available in the
[setup guide](docs/setup.md#validation-evidence--2026-10-20) and
[extraction guide](docs/graphics-extraction.md#validation-recorded-on-2026-10-20).

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

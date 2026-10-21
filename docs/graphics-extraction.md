# Original graphics extraction

This tool supports the unpacked Namco New Rally-X set named `nrallyx` in MAME
0.289. Supply your own ROMs; no tool downloads or distributes them. The extractor
preserves source dimensions and indices and performs no MSX conversion.

## Install and run

The existing macOS bootstrap prepares the dependencies:

```sh
make environment
.venv/bin/python -B scripts/extract_graphics.py \
  --input references/roms/nrallyx \
  --output references/assets/nrallyx
```

Both `--input` and `--output` are required. Existing output is protected by
default. Add `--overwrite` to replace an unchanged complete extraction.
Choose another output path to preserve earlier results:

```sh
.venv/bin/python -B scripts/extract_graphics.py \
  --input references/roms/nrallyx \
  --output references/assets/nrallyx-other
```

For the standard input and output paths:

```sh
.venv/bin/python -B scripts/extract_graphics.py \
  --input references/roms/nrallyx \
  --output references/assets/nrallyx
```

For the extractor alone, install Python 3.14, then from the repository root:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Reuse an existing compatible environment. `requirements.txt` pins Pillow 13.0.0;
the extractor requires Python 3.14 and that Pillow version. Git must be available
to verify that outputs are ignored and untracked. MAME is needed for reference
validation, rather than normal extraction. No global Python packages are needed.

Both CLI paths are required. Relative paths use the caller's working directory;
output must be strictly below this checkout's `references/assets/`. An absolute
script invocation works from another working directory. Run `--help` for options.
Missing, corrupt, wrong-size and unsupported ROMs fail before creating output.
Messages identify the affected filename and expected checksum or size. Required
ROM files must be regular files, not symlinks. Extra unrelated input files are
ignored. All 13 ROMs are validated, including program and sound files that are
not decoded. Source files are opened read-only and never modified.

## Source inventory and provenance

The exact filenames, physical sizes, CRC32, SHA-1, region roles and load segments
are recorded in [nrallyx.json](../scripts/graphics/nrallyx.json). Four program
ROMs are 4096 bytes each, two graphics ROMs are 2048 bytes each, the dot PROM is
256 bytes, the palette PROM is 32 bytes and the lookup PROM is 256 bytes. The
remaining two video PROMs are 32 bytes each and two sound PROMs 256 bytes each.
Program load continuations are described as segments; no CPU region is exported.

The source pin is MAME tag `mame0289`, commit
`f34f02505e32c1993c6a782b6814232cbfc74e36`:

- [rallyx.cpp](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/mame/namco/rallyx.cpp):
  `ROM_START(nrallyx)`, character/sprite/dot layouts and graphics decode entries.
- [rallyx_v.cpp](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/mame/namco/rallyx_v.cpp):
  palette network, lookup mapping, transparency, attribute flips and bullet mixing.
- [drawgfx.cpp](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/emu/drawgfx.cpp):
  MSB-first bit addressing and first-plane weight 2, second-plane weight 1.
- [resnet.cpp](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/emu/video/resnet.cpp)
  and [resnet.h](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/emu/video/resnet.h):
  resistor calculation, global autoscale and integer rounding.

RGB uses the 1000/470/220-ohm red/green networks and 470/220-ohm blue
network with a 1000-ohm blue pull-down. Absent pull resistors use MAME's 1e12-ohm
convention. Each channel is combined before rounding with `int(value + 0.5)`;
rounding separate bit weights would change some colors.

## Output schema 1

The tool produces 137 payload files plus `manifest.json`:

| Output | Interpretation |
| --- | --- |
| `tiles/indices.bin` | 256 original 8x8 graphics, 16384 bytes |
| `sprites/indices.bin` | 64 original 16x16 graphics, 16384 bytes |
| `dots/indices.bin` | Eight original 4x4 graphics, 128 bytes |
| Each group's `atlas-indexed.png` | Source pen indices 0..3 in P mode, neutral inspection palette |
| `tiles/color-00.png` through `color-63.png` | All 64 opaque lookup variants |
| `sprites/color-00.png` through `color-63.png` | All 64 lookup variants with logical transparency |
| `dots/color-00.png` | Dedicated dot colors, source pen 3 transparent |
| `palette.json` | Raw PROM bytes, 32 RGB entries, 256 lookup entries, variants and alpha rules |
| `graphics.json` | Counts, dimensions, bit layouts, flips, atlas sizes and ID-to-slot coordinates |
| `manifest.json` | Source pin, tool/schema/runtime versions, parameters, input hashes and payload hashes |

Binary ordering is ID, row, column, one unsigned byte per original source pen.
The origin is top left. All duplicate and empty IDs are retained. The tile
atlas uses 16 columns and the sprite atlas eight; both are 128x128 pixels. Dots
use eight columns and a 32x4 atlas. There is no scaling, padding or labeling.

Canonical exports are unflipped, as in MAME's graphic definitions. Runtime tiles
apply flip X = NOT attribute bit 6 and flip Y = attribute bit 7. Sprite byte bits
0 and 1 select X/Y flips. Dot runtime code selection XORs the attribute code
with 7; exported dot IDs are the original layout IDs, before that runtime mapping.

Tiles are opaque. Sprite alpha is zero for source pens whose selected lookup
entry maps to indirect index 0. It is not selected by RGB black or a fixed source
pen. Dot previews use indices 16..19 and source pen 3 is transparent. Raw index
atlases are always opaque so every source pen remains inspectable. PNG color
variants are RGBA, while binary and P-mode outputs retain source indices.

JSON is sorted UTF-8 with a trailing newline. `manifest.json` lists sorted input
records (`name`, `size`, `crc32`, `sha1`) and sorted output records (`path`, `size`,
`sha256`). Output paths are relative POSIX paths. The manifest does not hash itself.
It records tool version 1.0.0, schema version 1, Python/Pillow versions and fixed
extraction parameters, with no timestamps or absolute paths. Identical inputs,
tool and recorded runtime versions produce identical bytes. PNG byte identity
across different Python/Pillow builds is not promised.

## Output protection and recovery

Default behavior refuses an existing destination. Use `--overwrite` only to
replace this tool's unchanged complete output. The manifest, exact inventory and
all hashes must match; extra files, edited assets, unknown versions and symlinks
prevent overwrite. Choose another output directory to preserve modified assets.

The tool rejects the assets root itself, output outside that root, `..`, symlink
components, overlapping input/output paths and tracked or insufficiently ignored
outputs. Existing directory spellings are recovered by filesystem identity;
tracked-file checks account for case aliases on case-insensitive filesystems.
These checks apply even with `--overwrite`.

Publication uses ignored sibling paths `.NAME.lock`, `.NAME.staging-*` and
`.NAME.backup-*`. A complete manifest is written last in staging; a new destination
is published by rename. Overwrite first preserves the old directory as a backup,
then installs staging and removes the backup. Ordinary installation failure
restores the old output. Concurrent runs to the same destination are refused.

After an abrupt process termination, inspect any lock, staging or backup before
removing it. Ensure the owning process is no longer running. A backup contains
the previous complete output; if the destination is absent, move the backup back
to its original destination. Do not treat a staging directory as a complete
published extraction. The command never silently deletes an unknown backup or
stale lock. A backup cleanup failure reports both the installed destination and
the retained backup. This is protection against mistakes, not a security boundary
against another process changing paths concurrently.

## Synthetic tests and optional local MAME validation

Run the full suite with the project's dependency-enabled interpreter:

```sh
.venv/bin/python -B -m unittest discover -s tests -v
```

Tests generate synthetic inventories, graphics and PROMs. They cover bit/plane
ordering, boundaries, flips, network rounding, lookup alpha, atlas placement,
checksum failures, safe paths, ignored/tracked files, overwrite preservation,
locks, rollback, repeatability and CLI behavior. No original bytes or captures
are embedded in tests. The pre-existing base-interpreter verification test now
uses `sys._base_executable`, allowing the suite itself to run in `.venv`.

For local integration, extract twice to separate ignored destinations, compare
every file byte-for-byte (including manifests), verify output SHA-256 values and
rehash the 13 source files. This requires contributor ROMs and is not part of
the synthetic suite.

For reproducible MAME reference captures, first create a new ignored directory
and verify ignore coverage. The following command uses the original MAME renderer
with synthetic video-RAM scenes. It changes the emulated CPU's ROM region to an
idle loop in memory, without modifying source ROM files. Use MAME 0.289:

```sh
mkdir -p references/mame-validation
git check-ignore references/mame-validation/tiles-1.png
NRALLYX_REFERENCE_DIR="$PWD/references/mame-validation" \
mame nrallyx -rompath references/roms -video none -sound none -nothrottle \
  -skip_gameinfo -autoboot_delay 0 \
  -autoboot_script scripts/graphics/mame_reference.lua -seconds_to_run 8 \
  -cfg_directory references/mame-validation/cfg \
  -nvram_directory references/mame-validation/nvram \
  -snapshot_directory references/mame-validation \
  -state_directory references/mame-validation/sta \
  -diff_directory references/mame-validation/diff
```

This optional harness writes fixed capture filenames; use a fresh directory to
preserve earlier evidence. It does not provide the extractor's overwrite guards.
Captures must remain local and ignored. Inspect the images as well as comparing
pixels: tile captures contain all IDs in a 128x128 region at (35,32); sprite
captures show IDs 0,1,31,63 at x=32,64,96,128 and y=48 (16x16 each). Dot IDs 0..7
are at x=32+16*ID, y=80 (4x4 each). Compare with the corresponding atlas slots
from `graphics.json`. Composite sprite/dot alpha over black for these scenes.
`palette-reference.txt` records 32 hexadecimal RGB entries then 256 decimal
lookup values reported directly by MAME's palette device.

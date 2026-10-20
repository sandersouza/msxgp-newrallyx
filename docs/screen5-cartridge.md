# Static SCREEN 5 cartridge

Issue [#8](https://github.com/sandersouza/msxgp-newrallyx/issues/8) builds two
approved compact compositions into a local MSX2+ cartridge. Press **1** for the
normal scene and **2** for the enemy/smoke scene. Images retain the 200x212 maze
and 56-pixel sidebar at their original pixel dimensions. There is no gameplay,
animation or audio, and this bitmap upload establishes no dynamic frame rate.

## Build and run

Use the environment from [setup.md](setup.md) and the verified captures from
[#6](arcade-scenes.md). The following preparation commands use the actual local
capture paths; substitute your own verified capture directories as needed:

```sh
make analyze-scene SCENE_INPUT=references/scenes/review-fixed-v3/frame-02200 \
  SCENE_REPORT=references/scenes/rom-input/normal
make analyze-scene SCENE_INPUT=references/scenes/review-fixed-v3/frame-02760 \
  SCENE_REPORT=references/scenes/rom-input/overlap
make rom
make run
make verify-rom
```

Existing input bundles may be reused. Build, run and verification destinations
must be new: previous evidence is never replaced. Select another `ROM_OUTPUT`
for subsequent builds. To rerun an existing cartridge with fresh run outputs:

```sh
make run ROM=references/build/screen5/static-scene.rom \
  ROM_OUTPUT=references/build/screen5-rerun
make verify-rom ROM=references/build/screen5/static-scene.rom \
  ROM_OUTPUT=references/build/screen5-recheck
```

| Override | Default |
| --- | --- |
| `ROM_NORMAL` | `references/scenes/rom-input/normal` |
| `ROM_OVERLAP` | `references/scenes/rom-input/overlap` |
| `ROM_OUTPUT` | `references/build/screen5` |
| `ROM` | `$(ROM_OUTPUT)/static-scene.rom` |
| `MSX_MACHINE` | `Panasonic_FS-A1WSX` |
| `MSX_BIOS` | `references/msxbios` |
| `OPENMSX` | `openmsx` |
| `SJASMPLUS` | `.tools/sjasmplus/1.24.0/sjasmplus` |

The direct CLI is `.venv/bin/python -B scripts/msx_rom.py --help`. Inputs must
have valid manifests, zero arcade reconstruction differences and approved
`compact` layout metadata. Old preview bundles marked `proposal` must be
regenerated with the current compositor. No input pixels are resized.

The build emits `static-scene.rom`, symbols/listing, packed `.sc5` bitmaps,
`palette.bin`, converted previews, `conversion.json`, `build.json` and a hashed
manifest. All outputs stay under ignored `references/build/`. The source ROMs,
BIOS, captures and exported assets remain local; no downloading is performed.

## Machine and contributor-supplied BIOS

Local validation uses openMSX **21.0**, `Panasonic_FS-A1WSX`, V9958 with 128 KB
VRAM and 64 KB RAM. The launcher sets the CPU to **3,579,545 Hz**, emulator speed
100%, firmware off and NTSC 212-line display. The cartridge itself sets 60 Hz
through VDP R9. Its BIOS calls require an MSX2 or later machine; the recorded
integration target is MSX2+.

Supply compatible system ROMs under `references/msxbios`. The launcher adds
that directory as a session-local `system_rom` file pool **before** loading the
machine. openMSX resolves files by the machine definition's SHA-1, recursively;
renaming files or copying BIOS into a global emulator directory is unnecessary.
The launcher isolates `OPENMSX_HOME` and `OPENMSX_USER_DATA` inside the run output,
disables saving settings and leaves global emulator configuration untouched.

These split ROMs are the compatible inputs for the selected machine:

| Filename in machine definition | SHA-1 |
| --- | --- |
| `fs-a1wsx_basic-bios2p.rom` | `f4433752d3bf876bfefb363c749d4d2e08a218b6` |
| `fs-a1wsx_msx2psub.rom` | `fe0254cbfc11405b79e7c86c7769bd6322b04995` |
| `fs-a1wsx_fmbasic.rom` | `aad42ba4289b33d8eed225d42cea930b7fc5c228` |
| `fs-a1wsx_kanjibasic.rom` | `dcc3a67732aa01c4f2ee8d1ad886444a4dbafe06` |
| `fs-a1wsx_disk.rom` | `7ed7c55e0359737ac5e68d38cb6903f9e5d7c2b6` |
| `fs-a1wsx_firmware.rom` | `3330d9b6b76e3c4ccb7cf252496ed15d08b95d3f` |
| `fs-a1wsx_kanjifont.rom` | `5aff2d9b6efc723bc395b0f96f0adfa83cc54a49` |

openMSX also accepts combined IC18/IC17 dumps and an alternate FM-BASIC hash;
see the installed `share/machines/Panasonic_FS-A1WSX.xml` for alternatives.
Local supplied combined dumps have SHA-1 `28cc0fbab62d9b4ff5d16971795ebb8a4e02f1f6`
and `9da0306506640ea89acaa9516cb836233a9221ec`, respectively. These identifiers are
metadata only. No BIOS payload belongs in Git.

On missing/mismatched BIOS, inspect the run's `emulator.log`: openMSX identifies
the failed ROM lookup and the launcher reports the selected machine/BIOS
diagnostic. Verify hashes against that machine's XML, or set `MSX_MACHINE` and
`MSX_BIOS` to compatible contributor-supplied inputs. No global settings edits
or BIOS downloads are required. A first-run missing `firmwareswitch` persistent
file warning is expected in the isolated, initially empty home directory.

## Cartridge and memory allocation

The 128 KB cartridge uses ASCII16. Bank 0 at CPU 0x4000..0x7fff contains the `AB`
header, initialization, keyboard loop and palette. BIOS occupies page 0; the
cartridge detects its own primary/expanded slot and maps it into page 2 using
`ENASLT`. Writes to 0x7000 select data banks at 0x8000..0xbfff.

| ROM file offset | Contents |
| --- | --- |
| 0x00000 | Bank 0: authored code and 32-byte palette, padded with 0xff |
| 0x04000 | Banks 1–2: normal 27,136-byte bitmap, padded to 32 KB |
| 0x0c000 | Banks 3–4: overlap 27,136-byte bitmap, padded to 32 KB |
| 0x14000..0x1ffff | Unused 0xff padding |

RAM 0xc000 stores the selected scene. The stack starts at 0xf380 and grows
down into page-3 RAM, below BIOS work areas. No bitmap RAM copy is required.
VRAM 0x00000..0x069ff holds the SCREEN 5 page-0 image (128 bytes per row).
The left pixel occupies the high nibble. Sprites, YJK, scrolling and interlace
are disabled. The display blanks during CPU upload; the complete scene becomes
visible at a VBlank. Interrupts stay disabled in the polling loop. PSG amplitude
and OPLL key-on registers are cleared; the cartridge produces no sound.

## Palette policy and independent measurements

One deterministic 16-entry palette serves both scenes. Source RGB colors are
sorted; unused entries are black. Each channel maps to the nearest V9958 DAC
level, with lower code breaking ties. More than 16 source colors or any collision
between converted source colors stops the build and requires explicit review.
No dithering, spatial filtering or silent palette merging occurs.

The preview models openMSX 21.0's V9958 conversion: RGB3 code `v` expands to RGB5
`(v << 2) | (v >> 1)`, then `floor(code * 255 / 31)` at gamma 1, brightness 0,
contrast 0 and identity color matrix. Levels are
`0,32,74,106,148,180,222,255`. This behavior is defined in
[openMSX SDLRasterizer.cc](https://github.com/openMSX/openMSX/blob/RELEASE_21_0/src/video/SDLRasterizer.cc).
It is a specified emulator comparison model, not a claim about every analog monitor.

The local pair contains **14** distinct colors, preserved as 14 distinct palette
codes. Converted previews were inspected alongside the unfiltered captures.

| Measurement | Normal | Enemy/smoke |
| --- | ---: | ---: |
| Source pixels changed by DAC conversion | 48,690 | 46,895 |
| Maximum RGB channel error (0..255) | 5 | 5 |
| Mean squared channel error | 4.189600531 | 3.435086232 |
| openMSX active-region mismatches after conversion | 0 | 0 |

Color conversion error compares the arcade preview with the converted preview.
Emulator mismatch counts compare the converted preview with the actual capture;
these are separate measurements.

## Verification evidence (2026-10-20)

```sh
.venv/bin/python -B -m unittest discover -s tests -q
make rom
make rom ROM_OUTPUT=references/build/screen5-repeat
cmp references/build/screen5/static-scene.rom \
  references/build/screen5-repeat/static-scene.rom
make verify-rom
```

The full test suite passed: **118 tests**. The synthetic converter/build tests check nibble order, row offsets, palette
bounds and collision rejection, color-byte order, scene bank boundaries,
padding, deterministic real assembly, protected outputs and Tcl quoting.
They use authored solid-color fixtures; assembler integration skips explicitly
if the pinned local executable is unavailable. Emulator validation is separate
and requires the local game-derived bundles and supplied BIOS.

Two real builds with sjasmplus 1.24.0 produced identical 131,072-byte cartridges:
SHA-256 `2ee951736fea4c913a2b289e45069e106cfcb61834f26f4431b847226e1e9387`.
openMSX captured normal at 8 seconds, enemy/smoke at 10 seconds and normal again
at 12 seconds, with matrix key presses/releases between captures. All three
active regions matched exactly: **0 / 0 / 0** differing pixels, tolerance 0.
The selection byte was asserted for each case; frequency/speed and VDP registers
are recorded alongside the screenshots. All 13 source ROMs match the pinned
inventory; the final verification also checks the entire BIOS inventory before
and after emulation.

`screenshot -raw -size auto` produces a 320x240 raw NTSC image on this version.
Comparison crops the fixed active rectangle **[32,14,288,226)**, with R18=0,
and performs no resampling. The full original screenshot remains available.
See the official [screenshot/filepool command reference](https://openmsx.org/manual/commands.html)
and [environment variable documentation](https://openmsx.org/manual/setup.html#configuration).

Local evidence is in `references/build/screen5/verification` and
`references/build/screen5-final-check/verification`; repeat bytes are in
`references/build/screen5-repeat`. `build.json`, `conversion.json` and
`integration.json` carry hashes and measured results. These artifacts must remain
ignored and must not be attached to issues or committed. Physical hardware and
other machine/VDP combinations have not been tested.

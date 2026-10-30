# Build your first MSX ROM

Run commands in the folder containing `Makefile`. You supply the original arcade
ROMs; the tools prepare all generated assets automatically. No arcade ROM or MSX
BIOS is included or downloaded by this project.

## 1. Install tools

The automated installer currently supports native macOS (Apple Silicon or Intel).
Install Xcode Command Line Tools and Homebrew as described in [setup](setup.md#macos-prerequisites), then run:

```sh
make environment
```

This prepares Python/Pillow, MAME 0.289 and the pinned Z80 assembler. Other systems
need the equivalent tools installed manually; automatic provisioning is currently
macOS-only.

## 2. Copy your arcade ROM files

Unpack your supported **New Rally-X (`nrallyx`)** set into
`references/roms/nrallyx/`. Put the files directly in that folder, without another
folder around them. Do not leave the ZIP there as the only input.

| Filename | Bytes |
| --- | ---: |
| `nrx_prg1.1d` | 4096 |
| `nrx_prg2.1e` | 4096 |
| `nrx_prg3.1k` | 4096 |
| `nrx_prg4.1l` | 4096 |
| `nrx_chg1.8e` | 2048 |
| `nrx_chg2.8d` | 2048 |
| `rx1-6.8m` | 256 |
| `nrx1-1.11n` | 32 |
| `nrx1-7.8p` | 256 |
| `rx1-2.4n` | 32 |
| `rx1-3.7k` | 32 |
| `rx1-5.3p` | 256 |
| `rx1-4.2m` | 256 |

All 13 files are required, including program, palette and sound data. The tools
check their sizes, CRC32 and SHA-1 against the [supported inventory](../src/toolchain/graphics/nrallyx.json).
A different revision or a renamed file is rejected with an error.

## 3. Build

```sh
make build
```

On the first build, this automatically extracts graphics, uses headless MAME to
capture the required original scenes, reconstructs the two approved HUD inputs,
acquires original native geometry/rock/explosion state, and recreates the original
56x8 Namco wordmark. Then it compiles the MSX cartridge.

The first preparation takes longer. Later builds verify and reuse valid bundles;
if one bundle is missing, its stage is regenerated. Modified, incomplete or
incompatible bundles cause an error instead of being silently overwritten.

The playable result is **`dist/newrallyx.rom`**. Its cartridge type is **ASCII16**.
The hard size limit is 2,097,152 bytes. One ROM supports 64KiB RAM and detects
larger mapper RAM and supported CPU acceleration automatically.

To build and open it in openMSX:

```sh
make run
make run MAPPER=1  # Same ROM; emulator configured with 128KiB instead of 64KiB
```

Running the MSX emulator also requires your own BIOS files under
`references/msxbios/`; see [emulator setup](setup.md). BIOS files are unnecessary
for `make build`. Loading the delivered cartridge in WebMSX requires selecting
ASCII16. Final physical-hardware and perceptual acceptance remain separate from
host/emulator test results.

## Optional extraction commands

You can prepare everything before compiling:

```sh
make extract-all
```

Or prepare individual stages:

```sh
make extract-graphics   # Original pixel indices, palette and metadata
make extract-scenes    # Graphics if absent, five captures, two reconstructed inputs
make extract-native    # Graphics if absent, original geometry/rocks/explosion state
```

`make extract-grafics` is accepted as an alias for `make extract-graphics`.
`make prepare-assets` is equivalent to `make extract-all`; `make prepare-scenes`
is equivalent to `make extract-scenes`. These default commands are safe to repeat.
The lower-level capture/extraction CLIs also support custom paths and guarded
`OVERWRITE=1`; see [graphics extraction](graphics-extraction.md).

All build inputs live under **`assets/arcade/`**. Exact final converted resource
banks are published under `assets/arcade/msx/default/` after linking. Their manifest
records cartridge offsets and hashes. The generated wordmark lives at
`assets/namco-title-56x8.png`; the supplied MSX logo is `assets/msxlogo.bmp`.

## If something goes wrong

- **Missing ROM or checksum error:** check the folder, filenames and supported set above.
- **Missing Python, Pillow, MAME or assembler:** run `make environment`, then `make environment-check`.
- **Incomplete/edited asset bundle:** preserve or move the specific folder named
  in the error outside `assets/arcade`, then rerun `make build`. Other valid bundles
  are reused. Do not use `git add -f` to publish these local files.
- **Start over with extraction:** remove only the generated `assets/arcade/`
  directory, then run `make build`. Your original ROM files remain in `references/roms`.
- **Free intermediate disk space:** run `make clean`. This preserves original ROMs,
  BIOS files, canonical assets, documentation, empty directory markers and `dist/`.

## What belongs in Git

`assets/arcade/**` and all contents of `references/**` are ignored. The only
publishable files inside `references` are empty `.gitkeep` markers, which preserve
the input directory tree for a new developer. Original ROMs, BIOS, extracted pixels,
captures, generated banks and build logs must stay local. Ignoring files does not
untrack anything already committed; the unit suite also checks the Git index for
private payloads.

## Reuse the laboratory

Start with the [developer guide](developer-guide.md), [engineering lessons](engineering-lessons.md)
and [source/resource map](repository-layout.md). The reusable tools and techniques
live in `src/toolchain`; Z80/MSX runtime code lives in `src/screen4` and
`src/screen5`. Keep algorithms, synthetic tests and compact measured results in
Git; regenerate game data and disposable evidence locally.

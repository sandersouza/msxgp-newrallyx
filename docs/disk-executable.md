# Disk executable

This guide covers the preserved standard system-mapper edition. The new
[compact game and MegaRAM loader](issue42-768-optimization.md) additionally support
768 KiB MegaRAM with 64 KiB main RAM. Both packages remain available.

## Run

The disk edition targets MSX2+/V9958, 128 KiB VRAM and a standard **4 MiB
RAM mapper in the main RAM slot**. The normal cartridge now uses ASCII8 below
1 MiB and retains its 64 KiB main-RAM minimum. This older disk edition requires
no MegaRAM or flash cartridge.

Extract `newrallyx-disk.zip`, then copy all four `NRALLYX.*` files to the same
directory on a disk, SD or CF volume. The executable package itself fits on
one 720 KiB disk. Supply your own operating-system files when booting DOS.

- MSX-DOS: `NRALLYX`
- Disk BASIC: `RUN "NRALLYX.BAS"`

The loader reads and validates the complete game before starting. **Reset to
exit.** A floppy load can take several minutes; storage-interface speed and
CPU speed affect loading. The packaged file is 577,376 bytes, expanding to
125 banks / 2,048,000 bytes. RAM mapper expansion and MegaRAM are different
interfaces; this edition uses the standard FC..FF RAM-mapper ports.

## Implementation

Load all resources before entering the game. Replace authored ASCII16 bank
writes with Page 2 RAM-mapper writes, preserving A and flags. Reserve segments
250..255 for the existing main/map/radar/state lifetimes; resident code uses
segment 0 and resources retain their bank numbers. Rebuild generated sources
in an ignored temporary directory. Never rewrite contributor ROMs, normal
build outputs or resource pixels. No disk calls occur during gameplay.

Alternatives: loading resources during gameplay would require new scheduling
and disk-latency compromises; a MegaRAM loader would require a cartridge.
Preloading into expanded mapper RAM preserves the existing gameplay workload.

The package contains a relocatable MSX-DOS entry, a BLOAD entry and a BASIC
launcher, plus a bank-compressed data file. Disk BASIC uses ROMBDOS at F37D;
MSX-DOS uses 0005. FCB reads provide compatibility with DOS1 disk interfaces.
The loader must restore OS mapping before every disk call, reject insufficient
RAM, and stop on missing/truncated data. It takes over the machine; reset to
return to the operating system.

The decoder bounds literals and matches to their current 16 KiB bank, checks
compressed lengths and verifies an additive checksum for every expanded bank.
The DOS2 allocation API is used when available; errors free allocated segments.
The preserved audio worker has four explicitly checked, equal-length bank-write
patches. Source/data bytes are never searched and patched indiscriminately.

## Reproduce

From the source release `1.0.0`, copy the package's `SOURCE/` directory contents
into the checkout and supply the documented contributor arcade ROMs. The source
overlay is included because the disk add-on is published against the existing
release, without changing its tag or cartridge.

```sh
make environment
make -f Makefile -f src/disk/targets.mk build-disk
.venv/bin/python -B scripts/verify_disk.py --mode basic
.venv/bin/python -B scripts/verify_disk.py --mode dos
.venv/bin/python -B scripts/verify_disk.py --mode rom
.venv/bin/python -B scripts/verify_disk.py --ram-kib 2048 --expect-error
.venv/bin/python -B scripts/verify_disk.py --fault missing --expect-error
.venv/bin/python -B scripts/verify_disk.py --fault truncated --expect-error
.venv/bin/python -B scripts/verify_disk.py --fault checksum --expect-error
.venv/bin/python -B scripts/verify_disk.py --fault distance --expect-error
make test
make timing-workbook
```

The DOS verification requires locally supplied `msxdos.sys` and `command.com`
in ignored `references/cache/dos-validation/`. They are test inputs only and
are absent from the game package. The measured run used MSX-DOS1.03 and
COMMAND1.11 from the [MSX archive](https://www.msxarchive.nl/pub/msx/utils/misc/msxdos1.lzh).
BIOS files also remain local. `make build-disk` is available directly in the
updated working checkout. Intermediates use `references/build/game-disk/`;
the distributable is `dist/disk/newrallyx-disk.zip`.

## Verification

openMSX 21.0, FS-A1WSX with a 4 MiB main mapper, factory CPU acceleration,
128 KiB VRAM and real sprite limits. Both Disk BASIC and MSX-DOS boot from the
actual files through the disk ROM. All125 installed banks match the linked
image byte for byte and remain unchanged after300 gameplay presentations.
The DOS differential run has zero differences against the cartridge in full
128 KiB VRAM, all VDP registers, PSG registers and E000..E2FF native state at
the same completed presentation. Credit, start, steering and smoke use actual
keyboard-matrix input. PSG activity is automated evidence, not listening acceptance.

| Edition | Presented FPS | Mean work | p95 work | Maximum work |
| --- | ---: | ---: | ---: | ---: |
| Cartridge |31.994467|65,440|92,395|124,327|
| DOS disk |31.994464|65,422|92,367|124,304|
| BASIC disk |32.109140|65,243|92,316|124,379|

Costs are elapsed base-Z80-equivalent cycles at3,579,545Hz, with foreground
callees and IRQ/VDP stalls included. These are short, three-enemy, first-round
samples; the BASIC run follows a slightly different clock/input trajectory.
The DOS presentation rate is effectively unchanged. BASIC's maximum work is
slightly higher. These results do not establish a speedup or full-game acceptance.
Refresh is59.922743Hz (nominal60), separate from presented FPS. One refresh
is59,736 cycles; two refreshes are119,472. Some maximum work exceeds that
budget. Synchronization and publication are recorded separately in the
[disk ledger](measurements/timing/disk-executable.json); inclusive parent and
child costs are not added. Usable VBlank was not measured.

The default cartridge remains byte-identical (`d73539eb...8ea963`); its existing
timing ledger/workbook retain their original ROM/workload identities.
`make timing-workbook` was run; duplicate regeneration was discarded rather
than relabeling cartridge measurements as disk measurements.

470 general tests and93 component tests pass, with one documented component
skip. Error fixtures reject64 KiB/2 MiB RAM, missing/truncated data, checksum
corruption and an LZ match that would wrap into OS memory; each returns to
Disk BASIC. DOS2 allocation was reviewed against its specification, but no
DOS2/Nextor execution or physical machine was tested.

Source owners: `scripts/disk_package.py`, `src/disk/loader.asm` and the generated
SCREEN4 assembly adapters. Source ROM identity remains in `dist/manifest.json`.
Hardware tests and manual perceptual acceptance must be reported separately
from automated emulator results.

References: [MSX2 Technical Handbook, disk system calls](https://konamiman.github.io/MSX2-Technical-Handbook/md/Chapter3.html),
[MSX-DOS2 mapper allocation specification](https://map.grauw.nl/resources/dos2_environment.php).

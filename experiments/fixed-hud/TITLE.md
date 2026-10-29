# Experimental cast screen

The original static header and all96 reveal units move up8px. Original glyph
bitmaps, item dimensions and reveal delays are unchanged. The final smoke
drawing ends at row175. The terminal caption occupies rows186..193, centered
between that drawing and the supplied wordmark at x8, rows195..209:

```text
[5] insert coin - [1/2] start player(s)
```

The BIOS terminal font remains at its original pixel size. No text is reversed.
Only the5 and1/2 masks blink, every32 physical refreshes per half-period;
brackets and the other caption pixels stay fixed. Two small byte-aligned
rectangles upload only when the phase changes. This runs in the cast handler,
not in active gameplay or the IRQ. `session-title.inc` uses one UI-only byte
at DFE3 and the existing blit scratch. Its inclusive timing is recorded in the
ROM-bound ledger; CPU-only/self costs are not inferred from overlapping rows.

The wordmark is the original arcade56x8 tile block (tiles0x19..0x1f), extracted to
`references/exports/namco-original/namco-title-56x8.png`. Copy its alpha
mask one-to-one, including transparent margins and letter counters. Only the
foreground color maps to the existing RED palette entry. No resizing, filtering,
thresholding, glyph reconstruction, crop or kerning changes are allowed.

On the256x212 active screen, place the complete PNG at100,200. Both horizontal
margins are100 pixels; rows208..211 provide exactly four pixels below the PNG.
Oversized inputs or non-binary alpha fail explicitly instead of being resampled.
Metadata records the exact source SHA256, dimensions, scale1 and bottom margin4.

Only fixed-size title bitmap bytes change. Executable/gameplay bytes, title
transfer length and persistent memory remain unchanged. The emulator proof
compares every footer pixel directly with this exact PNG, including placement,
transparent holes and all blank margins. Both title blink states are checked.

## Optional MSX logo include

`session-ui-options.inc` selects `session-msx-logo.inc`. Remove or comment that
one INCLUDE to omit the module's bitmap, routine and caller. There is no runtime
enable/disable branch. A convenient separate comparison build is also available:

```sh
make run-experiments MSX_LOGO=0
make run-experiments MSX_LOGO=1
```

The no-logo export ends in `-no-logo.rom`; the default export retains its usual
name. Fixed bank padding means both cartridge files can have the same total
length even though the omitted module occupies no code/data space.

The contributor-supplied reference is stored, untracked, at
`references/experiments/msx-logo/source.png`. The importer extracts its162x60
black label and samples both axes with the same integer divisor3, producing
54x20 pixels at x194,y8. Top and right margins are exactly8px. The blue surround
is excluded. The logo module uses the existing SCREEN5 blitter, allocates no
persistent RAM, and is called once with the display off before each cast reveal.
Its inline contract specifies clobbers and dependencies. Original ROM-derived
and generated artwork stays under ignored `references/` directories.

## Reproducible checks

```sh
make test-experiments
make test-experiments MSX_LOGO=0
```

`session_boot_verify.py` compares static header pixels against the pinned
original production resources and the complete signature against the supplied
complete source crop, including placement and blank margins;
the generated mask alone is not the placement oracle. It checks every reveal
destination moved by exactly1024 packed bytes (8 rows), with all96 glyph/item
bitmaps and delays unchanged. Both complete visible title blink states are
compared with committed VRAM, with real scanout retained. The no-logo run also
asserts that the optional routine's symbol is absent. UI cost probes require
the correct ROM-bank prefix and match caller PC/SP through RET; they are
separate cold/UI evidence, not active-game performance measurements.

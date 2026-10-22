# Original player movement on MSX2+

The default ROM starts directly in the driving test, with the car moving upward.
Arrows request direction changes. Releasing the arrows retains
movement. The original steering, centering and wall probes determine which
requests are possible. Space pauses; Home restarts at the original first-stage
player position. **Enter** switches to inspection, where arrows move the camera
and keys 1–5 select map landmarks; pressing Enter again restarts driving.

The camera follows the actual player and keeps the 16x16 car centred at screen
(128,116), below radar/Fuel and above the life counter. Near maze edges it shows
more of the original repeating flower field. Maze coordinates and asset sizes
remain unchanged. The radar follows the car in driving mode and the viewport
centre in inspection mode.

This integrates movement and wall interaction. Enemy AI, flag collection,
scoring, Fuel consumption, smoke and progression remain future game-runtime
integration. HUD shortcuts still publish demonstration values.

## Retained Z80 routines

[`player.py`](../scripts/msx/player.py) links selected routines from the locally
supplied, validated `nrallyx` program. Original addresses become `$8000+address`
in bank 47; direct native `$8000..$8fff` RAM operands become `$e000..$efff`.
Fixed-point velocity constants retain their values.

| Original entry | Responsibility |
| --- | --- |
| `$0069` | Fractional movement and descriptor updates |
| `$0c6c` | Initial player descriptor, including cell (15,50) |
| `$1052`, `$118a` | Direction requests, continuation, reversal and assistance |
| `$0e63`, `$14e0` | Wall probes and original first-stage wall bitmap |
| `$0f3e` | Native coordinate accumulation helper |
| `$1ddf` | Original twelve-angle steering animation |
| `$212b` | Signed velocity helper |

The linker relocates address operands, omits arcade watchdog/output-latch writes,
removes native DI/EI boundaries owned by the renderer, and replaces the main-loop
continuation at `$0c2c` with RET. Movement, collision and animation algorithms
remain original. `player.json` records adaptations. Original-derived code,
pixels and snapshots remain ignored under `references/`; source ROM files stay
read-only and are never downloaded.

The forward velocity is `$0220`, or 2.125 pixels per original tick. A fractional
clock resamples the original 16.5 ms tick onto the actual 50 Hz display period,
executing one or two native ticks per advancing refresh. It preserves native
velocity and fractional accumulation. Animation advances every four native
ticks. Pause freezes this clock.

World centres use native cells and signed intra-cell offsets:

```text
x = 24 + 12 + cell_x*24 + signed(offset_x)
y = 24 + 12 + cell_y*24 - signed(offset_y)
camera = (x-124, y-105)
```

The 24-pixel term is border padding; the 12-pixel term locates a cell centre.
Camera overscroll uses signed 16-bit positions and does not alter collisions.

## Integration and ownership

[`player.inc`](../src/player.inc) supplies the adapter used by
[`raster-scroll.asm`](../src/raster-scroll.asm). Calls run with DI, may clobber
general, index and alternate registers, and balance SP. The renderer owns the
ISR, display, palette and mapper.

| Entry | Phase / purpose |
| --- | --- |
| `Player_Init` | Blanked display: initialize isolated native RAM, forward speed and clock |
| `Player_Update` | Before header: present the already calculated position; delegate to camera movement in inspection mode |
| `Player_Radar` | Publish the current car marker through the public HUD API |
| `Player_Draw` | After `HUD_PrepareFrame`: upload changed car patterns and attributes |
| `Player_Patch` | After header: restore/complete the exceptional Y=216 bitmap row |
| `Player_Advance` | After header: apply requested directions and compute the next simulation state |

Simulation prepares the next presentation refresh, keeping native wall probes
outside the hard header deadline. Native active-low joystick bits 5/4/3/2 mean
up/down/right/left. Perpendicular requests use original assistance; simultaneous
arrows do not introduce unrestricted diagonal movement.

The renderer temporarily enables interrupts during pure native computation;
its handlers preserve native registers, the mapper bank and native RAM. The
adapter returns to DI before submitting VDP commands. This keeps raster events
reachable during more expensive wall and turn decisions.

The adapter and streamer use `$c400..$c472`; the isolated native RAM occupies
`$e000..$efff`. Its seed initializes only movement state. Before integrating the
full game, adapt this initialization to its authoritative RAM; do not overwrite
live game state with the prototype seed. Existing IM2, trampoline, stack and
[HUD API contracts](hud.md) remain separate.

## Two sprites, unchanged car pixels

The car occupies attribute slots **17 and 18**, bringing allocation to 19 and
leaving 13 free. Its logical left edge is 124; fixed R18=4 moves the complete
display four pixels left, keeping the car's physical centre at 128. The camera
uses half of the 248-pixel useful viewport. Native world coordinates do not change.
Mode-2 color planes preserve original blue, pale yellow and black using indices
3, 9 and combined `3|9=11`. A palette permutation preserves the displayed RGB
values throughout the maze and HUD. Original flip bits and animation survive.

Bank 48 contains twelve 128-byte car variants, their last-row colors and the RAM
seed. Each car variant has normal and
shifted phases, with two 32-byte planes per phase. Only the needed 64-byte phase
uploads on a change, using pattern numbers 180 and 184. `Player_Draw` replaces
the HUD's slot-17 terminator in driving mode and writes a new terminator at 19;
inspection keeps the car hidden.

Some original frames use all sixteen rows. To avoid reserved SAT Y=216 without
cropping, the adapter uses Y=215 and shifted patterns, then paints the missing
last row into the maze bitmap. It saves/restores eight or nine packed bytes,
preserves neighboring nibbles and handles horizontal-page crossings. Original
source pixels remain intact.

## Cache and raster scheduling

Native speed can move the camera several pixels per refresh. Cache jobs persist
across tile crossings. The complete first stage needs only 28 distinct 8x8
bitmaps; a 1024-byte atlas at VRAM `$10800` stores them below the header and
separator. Banks 49/50 hold their world-position IDs. HMMM copies each hidden
tile from this atlas to the scrolling cache. Both axes share a bounded budget
of at most 22 tile jobs per refresh, reduced to 16 when two native ticks are
needed. The exceptional sprite-row patch reserves six further jobs' worth of
CPU time. Unused budget starts the next queued job.
Every copy checks current residency, so a stale row cannot overwrite a newer
column through a modulo address after a turn or reversal.

VDP command packets remain atomic; interrupts run between tile jobs. Command
completion is checked before publishing a finished frame. The row-176 split
still swaps Fuel into the life counter. The bounded command budget leaves time
for the next VBlank. Frame waiting consumes the VBlank
corresponding to the presented header, including after a scene reload.

## Verification

```sh
make build
make test
.venv/bin/python -B scripts/raster_scroll.py verify-player \
  --rom references/build/default-<id>/raster-scroll.rom \
  --output references/build/player-check
```

Use a fresh sealed build and output directory. The verifier drives real keyboard
matrix inputs and compares 1,600 movement states with original unrelocated Z80
routines independently executed in MAME. That harness changes only in-memory
main-loop return/EI boundaries; source ROM files remain unchanged. It also
checks keyboard mapping, clock resampling, native fractional/steering fields,
visible VRAM, complete images and refresh timing, with real VDP timing and sprite
limits at 3,579,545 Hz.

For machines without an active display, append `--headless`. This still executes
the keyboard, native-oracle, visible-VRAM and refresh checks with real VDP timing,
but disables the renderer and explicitly records zero RGB comparisons. Use a new
output directory when rerunning with the display enabled.

The verifier rejects a ROM that does not start in driving mode. Its keyboard
sequence covers continuous motion, steering, wall probes, pause/resume and
restart, comparing 1,600 native states and visible-VRAM frames. Full rendering
also compares complete RGB images, including car animation and the bitmap row
used to avoid reserved sprite Y=216.
Presentation RAM is frozen at the footer; screenshots wait for openMSX's
`after frame` event to avoid comparing state with the previous rendered frame.

Run the [map/raster](raster-scroll.md#reproduce-verification) and
[HUD API](hud.md#verification) regressions after shared scheduling changes.
Reports include the checked ROM hash; use reports from the same sealed build
when assessing a change.
Generated traces, ROMs, images and native data stay under ignored
`references/build/`; `make clean` removes them. Physical hardware and the
remaining original game loop need separate integration measurements.

# Full-screen hardware scrolling and a raster scoreboard — issue #9

The default SCREEN 5 renderer combines a bounded full-map hardware scroll with
a fixed top scoreboard and dynamic sprite radar, Fuel and life counter. It is a
keyboard graphics diagnostic with an [original-car driving mode](player.md).
Enemy AI, other gameplay rules and sound remain future integration work.

The [HUD integration guide](hud.md) defines the reusable Z80 interface for every
display component and its read-only native-RAM adapter. Keyboard fixtures and
test arithmetic are isolated in `hud-demo.inc`; game integration publishes the
results of the retained original logic through the same public calls.

## Default build and controls

```sh
make build
make run
```

The default cartridge is `references/build/newrallyx.rom`, a 1 MB ASCII16 ROM
containing the [complete original first stage](stage-one-map.md).
It starts with the car moving and the original wall collision and steering active.
Enter switches between driving and map inspection.
Make exposes only `environment`, `environment-check`, `build`, `run`, `test` and `clean`. Supply the existing extracted assets,
five verified scene captures, compact input bundles and compatible BIOS as
described in the README. Each build keeps a sealed bundle under
`references/build/default-*/`; the published ROM is a separate identical copy.

| Key | Action |
| --- | --- |
| Arrows | Steer the car; in inspection, move the camera one pixel per refresh |
| Enter | Toggle driving/inspection; restarting driving restores the original player position |
| Space | Pause/resume movement and diagnostic HUD updates |
| Home | Restart the car; in inspection, reload the selected map landmark |
| 1–5 | Inspection only: jump to the start area, top left, top right, bottom left, bottom right |
| 0 | Increment the remaining-life digit modulo 10, starting at 2 |
| F | Cycle test fuel: full → about 3/4 → 1/2 → 1/4 → empty → full |
| 9 | Queue +5,000 test points, up to 155,000 |
| 6 / 7 / 8 | Select score/fuel-content cadence: 2 / 3 / 4 refreshes |

The record starts at 20,000 and changes only when exceeded. The HISCORE: and 1UP:
labels remain static; ROUND is deferred. Life and scene controls
also work while paused, as does F. World camera coordinates are bounded 16-bit
positions; the 512x256 VRAM cache wraps without repeating the map. Maze pixels, car silhouette and
font glyphs retain their native sizes.

## Transparent sprite radar

The overlay occupies `[196,20,244,78)`, inset four pixels from the maze's right
edge. Its 48x58 outline has a one-pixel white line and chamfered corners; every
unpainted pixel is transparent. The original blue radar background is omitted.
Original first-stage flag anchors are projected onto the bordered map; markers
retain their native 2x2 footprints. Flags are white instead of yellow, as explicitly
requested. The captured enemy stays red; the player blinks white/black every
16 running refreshes. Sprite collision reporting is disabled for these HUD sprites.

Twelve combined sprites hold the white outline and flags. Two further sprites
hold player/enemy markers independently, preserving their colors without
recoloring the outline. The white frame/flags have priority on overlaps.
The Z80 regenerates the player's normal and shifted 16x16 patterns at runtime:
coordinates select a local 8x8 anchor, including markers crossing a byte boundary.
Only a changed marker uploads its 64 pattern bytes and 16 color bytes, with a
two-refresh content cadence. Attribute Y compensation still runs every refresh.
Pausing flushes the latest cursor position and freezes blinking. Landmark selection
reloads the stage flags and enemy fixture, and resets the camera cursor.

In inspection mode the player marker is a **diagnostic camera-center cursor**, projected from the
full 816x1392 image. It is not a simulated vehicle. Landmark selection reloads
the same original stage flags and captured enemy fixture. Integration with live
enemy state remains pending; the enemy is captured, not simulated. Driving mode
publishes the actual player's position through the same HUD interface.

Each column uses four 15-row bands with an empty sixteenth pattern row. Column
origins differ by one scanline, so their overlap rows do not coincide. The two
extra top padding rows explain the 58-pixel height. Shifted pattern variants
avoid SAT Y=216 without clipping any frame or marker pixel. A synthetic check
evaluates all 256 vertical phases, reserving both marker sprites on every radar
row, and proves at most eight active sprites per visible scanline including the
right margin, fuel and lives.

## Fuel and the outlined-car life counter

The fuel display occupies `[196,82,244,98)`, four pixels below the radar and
exactly aligned with its 48-pixel width. One white sprite draws an authored
fuel-pump silhouette; two yellow sprites draw a 32-pixel gauge to its right.
The interior empties to transparency while its thin yellow outline preserves
the full gauge width. The pump uses a simple authored silhouette.
F cycles five test states (30/22/15/7/0 filled interior columns), including while
paused. Only changed gauge patterns upload: 128 bytes for both columns and
their sentinel-avoidance variants. Running updates use the selected 2/3/4-refresh
cadence. This is a controllable display fixture; original fuel consumption is
not simulated.

The life display now uses **one original-size yellow car with its black outline,
followed by one white digit from 0 through 9**. It occupies three sprite slots
regardless of the count: two layers for the car at x=212 and one for the digit at
x=230, all anchored at y=194. Zero still draws the car and a visible zero. Sprites remain 16x16/1x throughout the maze and HUD.

The counter reuses the original 8x8 numeric tile assets. The ROM stores only their
eight mask bytes per digit. On a count change, Z80 code expands the selected
glyph into the **same** sprite pattern plus its sentinel-avoidance variant,
uploading 64 bytes. No attribute slot or pattern number is allocated per value.
The glyph keeps its original 8x8 footprint inside a transparent 16x16 sprite.
Its pattern is regenerated after the header/maze split, well before the footer
is displayed, keeping this work outside the header's raster deadline.
An alternate form shifts pixels down one row while moving SAT Y up one pixel,
avoiding reserved Y=216 without clipping the car, outline or digit.

To fit the outlined portrait, digit and Fuel, the three Fuel slots are reused
after their screen region has passed. A second line interrupt after row 176
changes only their colors and attributes into the life footer. VBlank restores
Fuel colors, and the normal per-frame SAT upload restores its attributes. The
comparator's R19 value is `(176+R23)&255`. Maze scroll registers and sprite
size/magnification do not change at this split. Both regions appear in the same
frame; no alternating-frame rendering is used.

Allocation is 13 margin + 14 radar + 3 shared Fuel/footer slots = **30 slots**,
leaving two free. The white radar outline and fixed points still share the same
3x4 matrix of twelve sprites; player and enemy remain separate.
The driving adapter uses both remaining slots for the full-color car, for a
total of 32 while driving. Its fixed screen band avoids the other HUD regions.

## Raster and VRAM

- Rows 0–7 contain the original 8x8 glyph cells, with one empty cell on each
  side: ` HISCORE:020000      1UP:000000 `. The left label begins at x=8 and
  the player-score field ends at x=248, matching the maze's inner edges.
  Labels are white, record digits red, and player-score digits cyan, using the
  original converted palette.
- VBlank selects the fixed header bitmap in VRAM page 2 and zeros R23/R26/R27.
  An R19 line interrupt after row 7 switches back to the maze. SCREEN 5
  remains selected throughout; rows 8–10 are an explicit black separator while
  register writes latch. The maze starts at row 11 and fills the remaining height.
- R26/R27 provide one-pixel horizontal scrolling and R23 provides vertical
  scrolling. SP2 uses different adjacent map regions in VRAM pages 0/1, forming
  a 512x256 ring. A bounded tile streamer updates hidden guard rows/columns
  without copying the visible maze.
  The V9958's fine-scroll mask hides columns 0–7 below the header. An opaque
  sprite strip covers columns 248–255, giving equal eight-pixel side margins.
  The remaining 240x201 maze pixels retain their original size and include the
  flower field. The original world textures remain intact behind both margins.
- The header uses no mask, and sprites are disabled while it is drawn. R23 also
  affects sprite Y, so every VBlank adjusts all overlay attributes. All visible
  HUD sprites use 16x16/1x mode.
- The right margin uses thirteen 16-row black strips. A strip whose Y attribute
  would become 216 moves up one pixel, along with every following strip;
  propagating that adjustment prevents gaps. Thirteen margin, fourteen radar
  and three shared fuel/life slots use thirty attributes, with at most eight
  sprites per visible scanline. The SAT has 120 attribute bytes and a Y=216
  terminator. Additional gameplay sprites must respect the remaining two slots
  and the per-line limit. The header disables
  all sprites and supplies its two black margins directly in the bitmap.
- Sprite colors, attributes and patterns live at 0x1F400, 0x1F600 and 0x1F800.
  The first active row needs an eight-pixel VRAM patch behind the right mask,
  because sprites appear one line after the display is unblanked. The CPU saves
  the original four/five bytes, restores them before moving the mask and preserves
  the neighboring nibble for odd camera positions. The patch follows the
  actual horizontal page and handles page crossings; the complete source map
  remains unchanged. Normal updates
  also write sprite attributes, dirty radar/fuel patterns/colors and due six-digit
  score/record fields. Numeric fields are patched after the raster split, while
  their page is hidden; camera/mask/sprite updates precede the split.

Original tilemap/asset/capture files are read-only. Flower borders are retained.
Inspection covers the complete static map; driving reuses the original player
movement and collision routines. Other game logic remains separate.

The horizontal-scroll register and mask behavior follows the
[Yamaha V9958 technical data book](https://www.vgamuseum.info/images/doc/yamaha/v9958.pdf).
Line-interrupt timing and vertical sprite compensation are also checked against
the tested openMSX 21.0 [VDP](https://github.com/openMSX/openMSX/blob/RELEASE_21_0/src/video/VDP.cc)
and [sprite checker](https://github.com/openMSX/openMSX/blob/RELEASE_21_0/src/video/SpriteChecker.cc).

## Reproduce verification

Experiment commands remain script CLIs, with fresh output directories:

```sh
.venv/bin/python -B scripts/raster_scroll.py build \
  --output references/build/raster-local
.venv/bin/python -B scripts/raster_scroll.py verify \
  --rom references/build/raster-local/raster-scroll.rom \
  --output references/build/raster-local-verification
```

Verification uses the sealed build's ROM, rather than the published copy, so its
input manifests, world textures, glyphs and sprite patterns can be checked.
It drives actual keyboard-matrix inputs without writing camera/state memory.
The complete screenshot must match a separate screen-coordinate compositor,
including every header/separator/mask pixel and every sprite overlay. It also
checks all three raster register sets, the visible map pixels in the 512x256
cache, the first-row mask, scoreboard bytes, exact camera displacement,
pause/reset, all map corners, full-height traversal, direction reversal, fine
scroll phases, life digits, fuel states and a simultaneous score/fuel/life move.
The native map-acquisition check separately covers the entire original layout.

Verification blocks physical host-keyboard events while injecting matrix inputs,
so interactive typing cannot disturb a run. The emulator uses a 3,579,545 Hz CPU, 100% emulated speed, real VDP timing, enabled
sprite limits and no frame skipping. Full-map automation retains host throttling so screenshot captures contain
the completed rendered frame. A strict callback rejects VRAM writes that
are too fast. Reports include normal main-loop durations, separately marked
scene loads, raster-handler sections and held-movement presentation intervals.
Generated data, screenshots, manifests and reports remain ignored below
`references/build/`. `make clean` removes them.

Physical hardware, larger live radar populations and original-game logic
budgets still require separate validation.

## HUD/map baseline validation — 2026-10-21

Before player integration, the HUD/map baseline ROM passed **53 exact complete-image comparisons** and
**3,800 continuous visible-map VRAM checks**, covering 48,240 maze pixels per
frame. Tests include full-height traversal, both horizontal pages, all four
map boundaries, direction reversal, all fine phases, ten life values, all Fuel
levels, score/record updates at all three cadences and a combined moving update.
All three raster register sets and strict VRAM access timing also pass.
The native arcade comparison separately checks 28,672 original tile selections.
At that baseline, **147 automated tests** passed, including synthetic map-selector, bank-layout
and native HUD-state contract
tests.

A separate Z80 consumer passed **121 API/ABI checks** and **118 exact complete-image
comparisons**, covering arbitrary six-digit scores, both player labels, all
Fuel units, lives, moving/hidden matrix points, native coordinate helpers,
native RAM decoding, rejected inputs, register preservation and cadence.

| Measurement | Result |
| --- | --- |
| Held camera movement | 3,537 intervals, 19.9355–19.9377 ms |
| Header/maze and footer commits outside reloads | 3,726 intervals each, 19.9355–19.9377 ms |
| Main-loop elapsed time outside reloads, including split wait | 6.6690–14.8639 ms, 3,772 samples |
| Instrumented VBlank / header / footer handler sections | 0.5942 / 0.1713 / 0.4713 ms |
| Landmark reload | Up to 1482.0 ms, display blanked |

No tested continuous movement or raster commit missed a refresh. Handler sections
exclude entry/status dispatch and return instructions. Main-loop measurements
include deliberate waiting; they are not CPU-utilization figures or a budget
for original game logic. Fixed-ROM projection tables keep variable division work out of the header split.

Evidence: `references/build/hud-final-navigation-verified/report.json`,
`references/build/hud-final-api-verified/report.json`, adjacent
RGB/VRAM captures, `movement.bin` and timestamp logs. The verifier checks the BIOS
inventory before and after emulation. All 13 contributor ROMs validate against
the pinned checksums. Two independent full-map builds and the published default
ROM are byte-identical, SHA-256
`6ccec6cdc40daf18763420271b935b805c913a7f3fbaae17853bf7db0d90ae6b`.
All generated payloads remain ignored. These measurements and this hash identify
the HUD/map baseline, not the current driving ROM. See
[player verification](player.md#verification) for current movement evidence.
The current ROM is available through `make run`; physical hardware and the
remaining original game loop require separate validation.

## Runtime integration contract

Shared input/palette preparation lives in [`inputs.py`](../scripts/msx/inputs.py);
packing and color conversion live in [`screen5.py`](../scripts/msx/screen5.py).
The executable entry is [`raster-scroll.asm`](../src/raster-scroll.asm).
[`stage-one-stream.inc`](../src/stage-one-stream.inc) supplies the full-map camera,
ROM tile lookup, guard-cache jobs and radar projection. Camera-center projection
uses 577-byte X and 1192-byte Y tables in fixed ROM, avoiding variable division
work before the header split. The builder enables this
path for `make build` and the renderer CLI; there is one supported rendering path.

| Resource | Owner / contract |
| --- | --- |
| SCREEN 5 pages 0/1, 0x00000–0x0FFFF | 512x256 ring; streamer owns hidden tile writes; never treat pages as duplicates |
| Page 2, header at 0x10000 | Scoreboard; patch due numeric fields after the header split |
| Page 2, 0x10800–0x10BFF | Exact first-stage tile atlas for driving-mode HMMM copies |
| 0x1F400 / 0x1F600 / 0x1F800 | Sprite color / attribute / pattern tables |
| Fixed ROM bank 0 | Code, IRQs, palette and small HUD assets; must remain mapped during interrupts |
| Switchable 0x8000–0xBFFF | Map tile / HUD font and resource banks; each consumer selects its own bank |
| 0xC0B0 / 0xC0B2, words | World camera X/Y; inspection clamps them, driving permits signed overscroll into the flower field |
| 0xC006 / 0xC007, bytes | Cached hardware X/Y phases; not world positions |
| 0xC0B4–0xC0BF | Streamer jobs, previous tile coordinates and horizontal-page bookkeeping |
| 0xC100 / 0xC200 / 0xC280 / 0xC290 | Main SAT / point patterns / Fuel SAT / life SAT buffers |
| 0xC400–0xC472 / 0xE000–0xEFFF | Player adapter and isolated original movement RAM; see [player ownership](player.md#integration-and-ownership) |
| 0xD000–0xD100, 0xD2D2 | IM2 vector table and trampoline |
| Stack | Starts at 0xF380; reserve the renderer's RAM before adding game state |

The IRQ owns VDP display/scroll registers. VBlank selects the unscrolled header,
disables header sprites and restores Fuel colors. The first line interrupt
selects the scrolling maze, applies cached R23/R26/R27, enables sprites and arms
the footer split. The second line interrupt changes the three shared Fuel slots
to car/outline/digit. VDP register/command packets remain atomic. Interrupts run
between driving-mode tile copies, during pure native computation, and at explicit
EI/HALT waits, keeping raster events reachable.

Before the header split, main reads input, clamps/moves the camera, computes
cached scroll registers, restores/moves the small right-edge patch, updates due
radar/Fuel patterns and rebuilds compensated sprite attributes. After the split,
inspection streams at most 12 hidden tiles, regenerates a changed life digit and
patches due score fields. Driving presents the previously calculated position
before the split, then computes the next native state and uses the bounded
[HMMM tile budget](player.md#cache-and-raster-scheduling).
**Do not put arbitrary game work into the pre-split section.**
Keep the footer IRQ reachable before row 176 and the next VBlank reachable every
refresh. The 2/3/4-frame HUD cadence reduces dirty-content work; sprite Y
compensation still runs every refresh.

To integrate live state, replace diagnostic input/fixtures with game camera and
calls to the [public HUD API](hud.md#public-state-api-version-1), publish actual
map entities into the radar, and retain bank selection,
SAT allocation and raster deadlines. A tile mutation must update its ROM/RAM
source abstraction and any resident cache copy; this static-map version does not
implement mutable terrain. The 30 HUD slots and eight-sprites-per-line limit
also constrain any later gameplay sprite allocation. The existing RGB oracle,
strict VRAM timing callback and held-movement interval checks should accompany
changes to these interfaces.

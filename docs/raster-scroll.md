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

The overlay occupies logical `[204,20,252,78)`, inset four pixels from the maze's right
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
  fuel, lives and the two-plane player car.

## Fuel and the outlined-car life counter

The fuel display occupies logical `[204,82,252,98)`, four pixels below the radar and
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
regardless of the count: two layers for the car at logical x=220 and one for the digit at
x=238, all anchored at y=194; the car icon starts at logical x=220. Zero still draws the car and a visible zero. Sprites remain 16x16/1x throughout the maze and HUD.

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

Allocation is 14 radar + 3 shared Fuel/footer + 2 car slots = **19 slots**,
leaving **13 free**. The white radar outline and fixed points still share the
3x4 matrix of twelve sprites; player and enemy remain separate. The fixed car
band avoids the other HUD regions.

| SAT slots | Owner |
| --- | --- |
| 0–11 | Radar outline and flag matrix |
| 12–13 | Player and enemy radar markers |
| 14–16 | Fuel, reused for lives after row 176 |
| 17–18 | Two original-color car planes while driving |
| 19–31 | Free; slot 19 contains the Y=216 terminator |

## Raster and VRAM

- Rows 0–7 contain original 8x8 glyph cells: ` HISCORE:020000       1UP:000000`.
  HISCORE begins at logical x=8; 1UP and its score move eight pixels right and
  end at logical x=256, matching the widened maze. With fixed R18=4 those edges
  appear at x=4 and 252 within the nominal 256-pixel display.
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
  The V9958's native fine-scroll mask hides logical columns 0–7 below the header.
  There is no right mask. The 248x201 useful maze retains original pixel sizes
  and flower borders. Fixed R18=4 shifts the whole display four pixels left,
  centring the useful range at physical `[4,252)`. It does not scroll the world;
  R26/R27 still handle background scrolling. Overlays move eight logical pixels
  right, and the camera uses 124 horizontal pixels from the car's world centre.
- The header uses no mask, and sprites are disabled while it is drawn. R23 also
  affects sprite Y, so every VBlank adjusts all overlay attributes. All visible
  HUD sprites use 16x16/1x mode.
- There are no right-mask attributes, colors or first-row mask patches. The HUD
  uploads 68 attribute bytes and its slot 17 terminator; driving replaces it with
  the two car entries and writes a new terminator at slot 19. All 256 vertical
  phases retain at most eight sprites per scanline. Future actors must respect
  that limit as well as the 13 free slots. The header disables sprites.
- Sprite colors, attributes and patterns live at 0x1F400, 0x1F600 and 0x1F800.
  The obsolete right-mask read/patch/restore path has been removed. The separate
  `Player_Patch` still preserves the last car row at the sprite Y=216 boundary.
  A 32-byte blank pattern reservation retains subsequent established pattern IDs;
  it holds no opaque mask and consumes no SAT entry. Normal updates
  also write sprite attributes, dirty radar/fuel patterns/colors and due six-digit
  score/record fields. Numeric fields are patched after the raster split, while
  their page is hidden; camera/sprite updates precede the split.

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
including all 320x240 pixels with borders, every header/separator pixel and every sprite overlay. It also
checks all three raster register sets, the visible map pixels in the 512x256
cache, scoreboard bytes, exact camera displacement,
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

## Issue24 validation — 2026-10-22

The final diagnostic cartridge SHA-256 is
`a89f20da0553295c0dcd71c2725ad0ea560bdf1767fdd221eaabff69bed86f49`.
The build remains 1 MiB ASCII16. `make build` publishes the same cartridge as the
sealed `default-2bce75947ad54e559a1c9e2a8eadc551` bundle; its ROM is byte-identical
to the directly tested `default-3f29dad869c64811a26b0f26f7581785` bundle.

- `make test`: 191 tests pass, including all 256 vertical sprite phases and an
  independent original-font regression for the relocated 1UP/2UP label.
- `issue24-player4`: 1,600 original movement/keyboard/VRAM frames and 34 complete
  320x240 images pass. Every refresh checks R18 and the actual slot 19 terminator,
  confirming 19 occupied slots and 13 free. Pause, restart, native steering,
  collisions, animation and the separate car-row patch remain covered.
- `issue24-raster4`: 53 complete images and 3,801 visible-map checks pass, including
  all eight horizontal fine-scroll phases, both pages, vertical wrap, map
  boundaries, diagonal motion, reversal, pause and restart. Held movement and
  raster commits stay within 19.93549–19.93773 ms per refresh. Normal main work,
  excluding map loads, remains within the frame budget.
- `issue24-hud4`: 121 API/ABI checks and 118 complete images pass, covering label
  selection, scores, all 31 Fuel widths, life digits, radar flags and setters.
- All rendering checks use real VDP timing and enabled sprite limits, with no
  VRAM access violations. Full 320x240 comparison includes every border pixel;
  there is no overscan crop used to conceal undefined pixels.

The isolated attribute-cost probe covers all 256 renderer scroll phases:
8052–8088 cycles before, 5949–5985 after. Every phase saves 2103 cycles, approximately
0.588 ms at 3.579545 MHz, or 26.1% of this routine's cost. This excludes other frame
work and the removed first-row mask patch; it is not a whole-game speed claim.
Reproduce with `scripts/raster_scroll.py verify-hud-cost --rom <sealed-rom>
--output <fresh-dir>`, using the same BIOS/machine options as the other verifiers.
The probe temporarily sets only the renderer scroll shadow and restores it
around the measured call; its output makes no RGB claim.

The normal `make run` launcher is also exercised with the display active and a
bounded test shutdown, loading the published ROM at standard CPU speed. Its
evidence is `references/build/issue24-run-check/`. Physical hardware and monitor
framing remain unmeasured; these results make no general television overscan
compatibility claim. Original-game integration and its combined performance
remain issue #11 work after the branch merge.

## Runtime integration contract

Shared input/palette preparation lives in [`inputs.py`](../scripts/msx/inputs.py);
packing and color conversion live in [`screen5.py`](../scripts/msx/screen5.py).
The executable entry is [`raster-scroll.asm`](../src/raster-scroll.asm).
[`stage-one-stream.inc`](../src/stage-one-stream.inc) supplies the full-map camera,
ROM tile lookup, guard-cache jobs and radar projection. Camera-center projection
uses 569-byte X and 1192-byte Y tables in fixed ROM, avoiding variable division
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
implement mutable terrain. The 17 HUD slots and eight-sprites-per-line limit
also constrain any later gameplay sprite allocation. The existing RGB oracle,
strict VRAM timing callback and held-movement interval checks should accompany
changes to these interfaces.

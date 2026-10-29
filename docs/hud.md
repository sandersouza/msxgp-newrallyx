# Reusable HUD and original-game integration

The HUD is a source-level Z80 component for the current SCREEN 5 raster renderer.
Game code publishes state through `HUD_*` entry points; scheduled drawing calls
update the display. The component does not calculate scores, compare records,
award lives, consume fuel, collect flags or advance turns. Retaining those
original routines preserves the original rules, including their side effects.

The keyboard ROM is one consumer of this interface. Its initial record, life
count, five Fuel shortcuts, camera cursor and captured stage points belong to
[`hud-demo.inc`](../src/screen5/hud-demo.inc), not to the reusable component. The full
original game runtime has not yet been integrated. This interface replaces
presentation calls inside a port; it is not a binary patch for the arcade ROM.

## Components and display ownership

| Item | Display and implementation | State owner |
| --- | --- | --- |
| HISCORE | White label, red six-digit value, logical left edge x=8; fixed bitmap header | Original record comparison and storage |
| 1UP / 2UP | White label, cyan six-digit value, logical right edge x=256 (physical x=252) | Original active-player selection and score arithmetic |
| Radar frame and points | Transparent 48x58 overlay at logical (204,20); white frame and 2x2 points share a 3x4 matrix of twelve sprites | Original flag collection, point visibility and positions |
| Radar player / enemy | Two separate 2x2 markers; player white/black blink, enemy red | Game positions; caller chooses whether the blink clock advances |
| Fuel | White pump and yellow outlined gauge at logical (204,82), exactly 48x16 | Original fractional fuel, consumption, smoke cost, depletion and bonus rules |
| Spare lives | One yellow original-size car with black outline at logical (220,194), white digit at (238,194) | Original car count and extra-life/death logic |

ROUND is intentionally absent. Numeric glyphs and the car retain original pixel
dimensions. The life digit is expanded from the existing eight-byte font mask
into one fixed 16x16 pattern and its shifted variant only when the count changes.
It does not allocate a sprite for each number or each spare life.

All sprites use 16x16, 1x mode. The native V9958 mask needs no right-margin
sprites. Allocation is twelve radar cells, two colored markers and three shared
Fuel/life slots: **17 HUD attributes**. At row 176, the footer interrupt changes the last
three slots from Fuel to car/outline/digit. VBlank restores Fuel colors. This
sharing is within each frame; it does not alternate HUD elements between frames.
The staggered radar cells and shifted pattern variants respect the eight-sprite
scanline limit and avoid the Y=216 terminator at every vertical scroll phase.
Additional white points use the existing matrix and require no extra attributes.
The [driving adapter](player.md) uses slots 17/18; the complete driving display
uses 19 attributes and leaves 13 free. Slots 0–11 hold radar cells, 12/13 hold
player/enemy markers, and 14–16 share Fuel/lives. Fixed R18=4 shifts the whole
display four pixels left; overlay coordinates move eight logical pixels right
to retain their inset against the widened maze. No per-frame R18 compensation
or overscan masking is used.

## Public state API, version 1

Public definitions are in [`hud-api.inc`](../src/screen5/hud-api.inc) and
[`hud-native.inc`](../src/screen5/hud-native.inc). Call setters with interrupts disabled
and stable input memory. They copy the input immediately, write HUD-owned RAM
only, and do not touch VDP ports or switch ROM banks. They are not reentrant.

All setters, including `HUD_SyncNative`, preserve BC, DE, HL, IX, IY, the stack
pointer and all alternate registers. AF is scratch. Carry clear means accepted;
carry set rejects invalid input without publishing a partial value. `HUD_SetForce`
simply uses bit 0. Caller buffers may be reused immediately after return.

| Entry | Input | Meaning / validation |
| --- | --- | --- |
| `HUD_SetScore` | HL → six bytes, most significant first | Each byte is numeric 0..9; arbitrary values 000000..999999. Reject the whole field if any digit is invalid. |
| `HUD_SetHiscore` | Same as score | Independent record display; does not compare it with the score. |
| `HUD_SetPlayerNumber` | A=1 or 2 | Change only the leading label glyph; reject other values. |
| `HUD_SetLives` | A=0..9 | Spare cars, excluding the car being driven; reject other values. Zero remains visible. |
| `HUD_SetFuel` | A=whole native gauge units | Clip at 54; fill `min(A,54)*30/54`, rounded down, interior columns. All 31 pixel widths are supported. |
| `HUD_SetPlayer` | B=X, C=Y | Radar-local 2x2 anchor; X=2..46, Y=2..56. B=255 hides it. |
| `HUD_SetEnemy` | Same as player | One separate red marker. |
| `HUD_SetFlag` | A=ID 0..9; B/C=anchor | Stable flag identity, same bounds; B=255 hides a collected flag. |
| `HUD_SetRadarPoint` | A=ID 0..19; B/C=anchor | Same matrix; IDs 0..9 alias flags, 10..19 hold other white points. |
| `HUD_SetNativePlayer` | B=0..63, C=0..111 | Arcade-local radar coordinates; B=255 hides. |
| `HUD_SetNativeEnemy` | Same as native player | Project into the separate enemy marker. |
| `HUD_SetNativePoint` | A=ID 0..19; native B/C | Project into the shared white matrix. |
| `HUD_SetCadence` | A=2, 3 or 4 | Minimum refresh interval for score/record fields and Fuel; reject other values. |
| `HUD_SetForce` | A bit 0 | 0=schedule normally, 1=flush pending content while paused or blanked. |
| `HUD_SyncNative` | HL → stable 4096-byte native RAM view | Read selected score, record, spare lives and Fuel; see the adapter contract below. |

Score input is neither packed BCD nor ASCII. For example, 123450 is
`db 1,2,3,4,5,0`. Caller arithmetic remains separate. `HUD_SetFuel` accepts the
whole gauge byte, not a percentage or one of the demonstration's five levels.
It never discards or rewrites the original fractional fuel counter.

Native coordinate helpers use fixed tables:
`local_x = 2 + native_x*44/64`, `local_y = 2 + native_y*54/112`, rounded down.
They expect radar-local coordinates, not world pixels or the arcade radar's
screen origin. Use stable IDs and publish B=255 when the original logic hides a
point. These calls do not enumerate native actors or infer flag visibility.
The demonstration instead projects its bordered world through camera tables;
that diagnostic policy is not part of the component.

## Initialization and frame calls

The implementation is [`hud.inc`](../src/screen5/hud.inc), with resource declarations in
[`hud-assets.inc`](../src/screen5/hud-assets.inc), RAM definitions in
[`hud-state.inc`](../src/screen5/hud-state.inc), and inline ISR hooks in
[`hud-raster.inc`](../src/screen5/hud-raster.inc). Include these through the current
renderer as shown in [`raster-scroll.asm`](../src/screen5/raster-scroll.asm). Do not
include `hud-demo.inc` in the game adapter.

| Entry | When to call | Contract |
| --- | --- | --- |
| `HUD_Init` | Display blanked, DI, after SCREEN 5/palette/table setup | Upload static resources/header and seed SAT; neutral state: zero scores/lives/Fuel, hidden points, player 1, cadence 2, blink clock 0. |
| `HUD_Prime` | After publishing initial state, still blanked and DI | Prepare sprites and drain all pending header/matrix changes; restore prior force setting. May exceed one refresh; initialization only. |
| `HUD_Tick` | Once per advancing logical tick | Advance radar cadence/blink clock; preserves the setter register set, AF scratch. Caller decides pause behavior. |
| `HUD_PrepareFrame` | Every refresh before the header/maze split, DI | Upload due marker/Fuel patterns and complete scroll-compensated SAT. |
| `HUD_DrawContent` | After the header split, DI | Patch changed player label/life digit, due numeric field and up to two dirty radar cells. |

Initialization, priming and drawing may clobber AF, BC, DE, HL and IX; preserve
IY and alternate registers. Drawing changes R14, the VRAM pointer and potentially
the switchable ROM bank. Every subsequent bank consumer must select its own
bank. Do not call drawing recursively, from gameplay callbacks or from setters.
`HUD_Tick` does not access VRAM or the mapper.

Inside the existing renderer, initialization becomes:

```asm
    ; DI, display blank, renderer palette and VDP tables configured.
    call HUD_Init
    ld hl,native_ram_view     ; logical $8000..$8fff mapped here, stable
    call HUD_SyncNative
    jp c,bad_native_state     ; caller handles rejection
    ld a,1                   ; use the original turn's selected player
    call HUD_SetPlayerNumber
    ; Publish visible player/enemy/flag coordinates through the point setters.
    call HUD_Prime
    ; Enable the existing renderer's raster interrupts and display.
```

For each game tick, retain original computation first, then publish its completed
state. Call `HUD_SetNativePlayer/Enemy/Point` from the corresponding logical
point updates. A collected flag becomes `A=flag_id, B=255; call HUD_SetFlag`.
Call `HUD_Tick` when the game advances. During every display refresh, call
`HUD_PrepareFrame`, reach the existing header-split wait, then call
`HUD_DrawContent`. Enable interrupts at the renderer's scheduled waits so the
footer and next VBlank remain reachable. The library does not enable interrupts
or own the main loop. See [raster scheduling](raster-scroll.md#runtime-integration-contract).

The VBlank ISR increments the renderer's `ticks` byte once per refresh and runs
`HUD_VBlankSprites`. The footer ISR runs `HUD_FooterSprites` at row 176. These
are macros: caller saves AF/BC; they preserve HL, DE, IX/IY and alternate
registers. They leave R14=7 and the VRAM pointer advanced. The footer hook also
writes R0=6 to disable the completed line interrupt. Header/maze page selection,
sprite enable, R19 arming and R23/R26/R27 remain the renderer's responsibility.

## Original RAM adapter and replacement boundaries

`HUD_SyncNative` targets the contributor-supplied `nrallyx` revision pinned by
[`nrallyx.json`](../scripts/graphics/nrallyx.json), MAME 0.289. HL points at a
stable, already relocated view of logical RAM `$8000..$8fff`; native pointers
inside it still contain arcade addresses. The adapter relocates those pointers
for reading. Do not copy 4 KB each refresh merely for this call: use the port's
authoritative RAM placement or adapt the pointer accessor to its final layout.
The verifier's fixture copying is test setup, not proposed gameplay work.

| Original location | Interpretation |
| --- | --- |
| Word at `$8990` | Pointer to the selected player's eight-cell score buffer; follow it, do not assume a player-one buffer address. |
| `$8060` | Eight-cell record buffer. |
| Word at `$8988` | Pointer to car count, including the currently driven car; display `max(0,min(9,count-1))`. |
| Word at `$898e` | Pointer to fractional decimal Fuel byte followed by whole gauge units. Fraction must be 0..9; whole units clip only for display. |

Native score cells are tile codes with a decimal low nibble, not packed BCD.
The original foreground wrap orders eight visible cells as offsets
`4,5,6,7,0,1,2,3`. The six-digit HUD reads offsets `6,7,0,1,2,3` and masks each
byte with 15: native `$30` zero and `$40` blank both display zero. Invalid digits
or pointers outside `$8000..$8ff8` reject the entire score/record/lives/Fuel
publication. All four values are validated before any setter is called. Native
RAM is never written. Player label selection still comes from original turn
logic through `HUD_SetPlayerNumber`.

The display has six score digits and one spare-life digit. Original eight-cell
score arithmetic, carry and counts remain untouched; only their presentation
is capped. A score above six digits displays its lower six digits. This must
not change original bonus thresholds or comparisons.

The following original entry points identify where to retain computation and
retarget presentation. Addresses apply to the pinned original program, not the
new cartridge's linked addresses:

| Original routine | Integration requirement |
| --- | --- |
| `$210f`, decimal score increment/carry | Keep the original arithmetic and storage; publish the resulting score. |
| `$2064`, record and bonus-life checks | Keep the eight-cell comparisons, DIP-derived threshold checks and once-per-player flags including `$81b2`; publish afterward. Replacing the whole routine with a display setter would lose game logic. |
| `$0b2f`, spare-car drawing | Retarget the presentation; use the authoritative count via `$8988`. Keep awards/death updates, including the decrement at `$18e4`. |
| `$1ecc` / `$1f13`, Fuel timing/decrement | Keep scheduled timing, decimal fraction and low/depleted flags such as `$8292`/`$828c`. |
| `$1f2f..$1f5c`, Fuel drawing portion | Retarget drawing; retain following flag logic at `$1f5e..$1f7b`. |
| `$1fa9`, remaining-Fuel score bonus | Keep conversion and scoring calls; publish the completed values. Smoke-related Fuel rules also remain original. |
| Original radar/flag/actor updates | Retain visibility, collection, S/L effects and actor logic; publish positions/hide events through stable point IDs. |

The adapter does not simulate these routines or replace them with parallel
rules. Original disassembly and snapshots used to establish this mapping remain
ignored below `references/`. Live native radar enumeration and full game-loop
hooking remain port integration work; the existing helpers expose their display
boundary without inventing actor behavior.

## Bounded work and scheduling

Repeated setters coalesce to the latest pending value. Unchanged values do not
upload content. Scores redraw only changed two-digit pairs; at most one complete
six-digit field is processed per refresh. Each field has its own cadence
timestamp, and fair selection prevents a continuously changing score from
starving the record. If both are pending, they may appear on adjacent refreshes.
Fuel uploads 128 pattern bytes only when the quantized fill changes and its
cadence is due. The label and life digit update only on change.

The player marker updates on the two-tick radar cadence; its color toggles every
16 advancing ticks. The separate enemy uploads only on position/visibility
change. White-point updates dirty the old and new matrix cells, rebuilding the
frame plus all points in each affected cell. At most two cells upload per
refresh, with a round-robin cursor to prevent starvation. Twelve dirty cells
drain in six calls if no new changes arrive. Large moving point populations
therefore require measured latency and game-loop budgeting; they do not allocate
extra sprites. `HUD_SetForce(1)` bypasses content cadence, not the per-call
numeric/matrix work limits; `HUD_Prime` drains those limits while blanked.

Scroll-compensated attributes must still update every refresh even when content
is unchanged. Do not throttle `HUD_PrepareFrame` to the score cadence. The main
renderer also owns its right-edge VRAM patch and tile-streaming work.

## RAM, ROM and hardware dependencies

The two configured RAM bases are declared before `hud-state.inc`:

```asm
HUD_WORK_BASE EQU $c000
HUD_API_BASE  EQU $c300
```

`HUD_WORK_BYTES=$29c` describes a sparse legacy window through `$c29b`;
`HUD_API_BYTES=$9a` reserves `$c300..$c399`. The current renderer deliberately
shares holes in the work window with its own state. The exact HUD-owned offsets
are defined in `hud-state.inc`; do not clear the entire work window during a
running scene. The library initializes its own fields. In a new embedding,
reserve both complete nonoverlapping windows or explicitly allocate their named
fields. External renderer symbols `ticks` and `scroll_y` remain separate.

Important buffers are SAT at work+$100, 64-byte point scratch at +$200,
Fuel SAT at +$280 and life SAT at +$290. The current renderer also reserves
IM2 `$d000..$d100`, trampoline `$d2d2` and a stack starting at `$f380`.
The test consumer places its native RAM view at `$e000..$efff`; that is not a
mandatory allocation for the port.

| Resource | Contract |
| --- | --- |
| Header | VRAM page 2 at `$10000`; 8 rows, plus explicit separator below. |
| Sprite tables | Colors `$1f400`, SAT `$1f600`, patterns `$1f800`; renderer config and allocation must agree. |
| Fixed ROM bank 0 | HUD code, ISR-visible patterns/colors, glyph masks and lookup tables remain mapped. |
| Bank 45, `HUD_BANK` | 1024-byte neutral header at `$8000`, cyan two-digit font at `$8400`, red font at `$9d00`; 100 glyph pairs per color. |
| Bank 46, `HUD_DATA_BANK` | 31 Fuel fills at `$8000`, bare radar-frame variants at `$9000`, player-label glyphs at `$9300`/`$9320`. |
| Mapper | ASCII16, switchable `$8000..$bfff` selected by writing `$7000`; each consumer selects its own bank. |
| Palette / geometry | Generated `config.inc`, including palette indices, sprite counts, header and overlay positions; assets generated with the same configuration. |
| Port helpers | `register`: B=VDP register, A=value; `upload`: HL=source, DE=length; existing `vdp_write` macro. Preserve their measured VDP pacing. |

The builder emits and seals these assets from locally supplied data. Scores do
not require an image per value: the bank contains reusable glyph pairs. The
32-entry `hud-states.bin` contains independent verifier fixtures only and is not
the runtime score implementation. Changing geometry, sprite allocation, mapper
or palette requires regenerating matching resources and rerunning raster tests.

## Verification

```sh
make test
make build
.venv/bin/python -B scripts/raster_scroll.py verify-hud \
  --rom references/build/default-<id>/raster-scroll.rom \
  --output references/build/hud-api-check
.venv/bin/python -B scripts/raster_scroll.py verify \
  --rom references/build/default-<id>/raster-scroll.rom \
  --output references/build/renderer-check
```

Use the freshly built sealed directory and fresh output paths. The API verifier
links a separate [synthetic Z80 consumer](../tests/fixtures/hud-api-driver.asm)
against the production HUD and tests register/stack/alternate-register
preservation, rejection behavior, arbitrary scores, all Fuel units, lives,
native pointers, native coordinate helpers, moving/hidden matrix points,
player labels and cadence/coalescing. Completed images are compared against an
independent screen-coordinate compositor; native input RAM must remain identical.
The driver and its synthetic fixtures are not shipped in the default ROM.

The navigation verifier independently checks the full map, keyboard producer,
all raster phases, scanline limits and strict VRAM access timing at the normal
3,579,545 Hz CPU setting. Reports are local evidence below ignored
`references/build/`. These checks establish the display interface; they do not
establish the CPU budget of the still-unported original game loop or replace
physical hardware testing.

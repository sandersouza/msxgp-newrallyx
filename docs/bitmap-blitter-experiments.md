# Player and 48x80 radar bitmap experiments

## Radar-only stage09 experiment: sprite car, blue 48x80 bitmap

The user requested preserving the bitmap car for future work, returning the
car to sprites and testing the taller radar as a bitmap. Run:

```sh
make run CHECKPOINT=11-r09-radar-blitter-hud-v139
# Rebuild, with the HUD enabled and sprite car:
make build STAGE=9 RADAR_BLITTER=1
```

V139 SHA-256: `eed4eea0a48f7862ffd35854d04edd2dcbedc4fa2db3c1c734ecc982d448021a`.
The user rejected this experiment because of slowness/flicker. It is preserved
but no longer selected by `LATEST`; active work returned to sprite radar.
The bitmap is 48x80, blue, borderless, with dynamic flags and one red enemy.
The player's 2x2 point remains a separate sprite with the native eight-tick
white/black cadence. The car retains both original sprite planes. Eight SAT
entries are used, 24 free; this saves twelve relative to v115. The fuel display
is moved below the taller radar. The score header remains black.
The radar experiment restores its twelve shared fuel SAT bytes every VBlank
after footer reuse, so the long copy loop does not hide the fuel display.

The flag base is regenerated only when its public forty-byte list changes,
covering collection/hiding/reset. Two precomputed byte phases allow HMMM for
the full image at either X parity. Odd X copies two padding pixels, then
restores both from the saved background with one-pixel IMP commands. No maze
pixels outside the radar are intentionally replaced. Full restore/save/draw
copies still run when the camera or enemy point changes; moving the separate
player dot alone does not dirty the bitmap.

The experiment is **not performance accepted**. The steady component median
fell from 52.024 ms (v133 pixel copies) to 38.898 ms (v135 phased byte copies).
The final proof additionally changes flag lists during each transaction:
540 full 64KiB canaries pass, including all twelve poses/flag variants, X
parity and both torus wraps; its 75.673 ms median includes base rebuilding
and is not the steady-motion cost. Another 1,024 cases verify all 256 scroll
phases, marker masks, hidden state, white/black colors and the SAT cursor
contract used by fuel. Enemy presentation passes 1,928 cases after rebasing
both bytes of its color-table address into slots6/7. Native enemy/contact
logic passes 2,643 cases on v137 before that color-address-only correction.
All 321 unit tests pass; stage08 still reproduces its accepted ROM hash.

A final HUD-on 300-iteration keyboard smoke run captures the blue radar and
sprite car but records approximately 60 ms median main intervals, well above
the 20 ms display period. It does not establish full moving-cache/RGB or
raster acceptance. Late HUD publication and full-copy latency remain open.
An incremental exposed-edge save/restore is the next candidate; it has not
been implemented or measured here.

Local evidence: `references/build/issue11-r09-radar-blitter-proof-v139/`,
`issue11-r09-radar-enemy-presentation-v139/`,
`issue11-r09-radar-smoke-v139/`, and
`references/analysis/issue11-v139-tests.log`.
The accepted sprite-radar reference remains explicitly available as
`11-r09-player-dot-50-v115`. The bitmap-car alternative below is preserved.

## Stage09 integration: testable, not accepted

The player's bitmap renderer is now integrated experimentally with one original enemy, death,
collection, score, fuel, lives and the full compact sprite HUD:

```sh
make run CHECKPOINT=11-r09-player-blitter-hud-v130
```

This is an **experimental checkpoint with known timing and radar-backlog
failures**. It is not selected by `LATEST`, which has returned to the accepted
v115 sprite-car/radar build. The v130 ROM is byte-identical to measured v126
(`1b6a35edfae207a291c663ef3df87250882377e3238331d7332bee3689f23cb4`).
Do not treat successful component/pixel tests as gameplay performance acceptance.
From 2026-10-23, all new gameplay/performance builds retain the HUD; HUD-off
comparisons require an explicit user request. Older results below are historical.

The maze car uses zero hardware sprites. Twelve composite radar cells, one
white/black blinking player point, three shared fuel/life entries and two enemy
planes occupy eighteen SAT entries, leaving fourteen free. Enemy sprites appear
above bitmap car pixels when they overlap. Native dimensions, coordinates,
collision and logical tick order remain unchanged.

Static certificates identify complete color-zero road tiles. Where a
conservative 24x24 neighborhood proves an aligned 18x16 footprint is road, HMMV
restores the previous footprint and HMMM draws an opaque padded car. Two
precomputed horizontal phases preserve odd/even X exactly. Elsewhere the
original exact save-under/transparent-copy path remains in use. Collected
flag cells become eligible only after their bitmap repair has completed.
The two added ROM banks keep the cartridge at 1 MiB; source images stay local.

Car/terrain presentation is frozen before the next simulation tick. A separate
eleven-byte flag display snapshot defers visual removal by one refresh;
logical collection, score and fuel still change in their original ticks.
Continuous natural-route evidence checks the exact preceding snapshot and
reset boundaries, rather than accepting arbitrary stale displayed flags.
Fuel sprites publish before the car's scanline, and exact solid terrain uses
bounded grouped fill commands. These changes do not resolve the combined
refresh budget yet.

Measured v126/v130 evidence: 1,138 complete visible-cache states and 28 complete
RGB captures pass for natural enemy contact, explosion, 120-tick hold, pause,
life loss, restart and Home. The 1,600-state render-only control passes cache
and RGB before failing the unchanged refresh-period gate (main maximum
41.634 ms). The natural route exceeds the existing sixteen-refresh radar
queue limit and also misses raster periods. The deadline/backlog gates remain
unchanged. Actual blitter canaries cover 1,080 cases, including 372 certified
new road footprints and all twelve poses; native/presentation components remain
separate from full gameplay acceptance.

Experiments v116..129 are not accepted: transparent full copies missed
terrain deadlines; moving both due ticks early still left late car scanout;
late collection could erase a freshly drawn car; late fuel publication tore
the gauge; guard/defer/interleaved radar variants failed timing, RGB or cache.
The source retains the reproducible v126/v130 experiment, not those later
failed scheduling variants. The next investigation must trace the remaining
deadline and publication interactions; sprite savings alone are not a speedup.

Rebuild explicitly with `make build STAGE=9 PLAYER_BLITTER=1` (HUD on).
As with other explicit builds, that command updates `latest.rom` to its requested
experimental cartridge. Normal `make build` remains the accepted stage 08.

## Historical stage00 experiments

The user requested a player blitter first, then a blue radar equivalent to
three by five 16x16 sprites. These are isolated rendering experiments on the
stage 00 keyboard/movement/wall-collision baseline. They do not complete issue
#11 or integrate the pending enemy population, smoke or round transitions.
The accepted stage 08 v25 gameplay cartridge remains unchanged.

## Test cartridges

```sh
# Preserved movement-only test: bitmap player, existing sprite HUD/radar
make run CHECKPOINT=11-blitter-player-v9

# Matching sprite-player control, same 48-column cache and 248-pixel viewport
make run CHECKPOINT=11-blitter-sprites-control-v1

# Deliberately slow diagnostic: bitmap player and blue 48x80 bitmap radar
make run CHECKPOINT=11-blitter-radar-v4

# Return to the accepted one-enemy gameplay build
make run CHECKPOINT=11-r08-enemy-v25
```

Arrows steer, Space pauses and Home resets. These stage 00 experiments start
directly in driving mode; enemies, collection, fuel rules and life loss are
absent. HUD values and flag locations are fixtures. The bitmap radar preserves
2x2 markers while projecting their positions into the taller radar. Its border
is absent, the score header remains black, and fuel moves below the taller panel.

Rebuild explicitly:

```sh
make build STAGE=0 PLAYER_BLITTER=1
make build STAGE=0 PLAYER_BLITTER=1 RADAR_BLITTER=1
```

The last command intentionally selects the slow diagnostic and publishes it to
`latest.rom`, like every explicit `make build`. Normal `make build` still selects
stage 08 v25. The original isolated blitter experiments support stages00/01; radar requires
HUD and player blitter. Unsupported combinations fail before publication.

## Player result

The player uses transparent LMMM/TIMP with the exact twelve original 16x16
poses. Each moving frame restores the old background, saves the new background
and draws the car. Odd X saves an even-aligned 18x16 rectangle so neighboring
nibbles survive. Transfers split at both boundaries of the 512x256 maze ring.
All background pixels are preserved, including walls and flags underneath the
car; assuming a uniform road color would not provide that guarantee.

The three operations run in the blank interval. CPU packet preparation permits
raster interrupts; only VDP control pairs and each command submission are
atomic. Optional cache work uses the line-196 deadline and a VBlank hard stop.
Tile preparation services pending interrupts before its command transaction.
The old one-row sprite-sentinel repair no longer consumes a cache-work reserve.

Both HUD modes pass 1,600 original-Z80 movement states, full visible-cache
comparisons, pause/Home/keyboard checks, strict VRAM timing and the unchanged
0.6 ms display-period gate. Full images: 32 with HUD, 26 without. Main refresh
interval is about 19.937 ms (50.16 Hz); this is distinct from elapsed foreground
work and from the large, separately recognizable Home reload transaction.
The executed v8 ROM and published v9 ROM are byte-identical.
Both HUD modes meet the refresh gate; elapsed foreground time includes the
blank wait and a different amount of optional prefetch, so this comparison does
not establish an isolated HUD CPU cost or prove later gameplay integration.

The actual cartridge routines also pass 540 arbitrary full-64KiB scene canaries,
all twelve poses and both wraps. Their isolated restore/save/draw elapsed time
is median 5.485 ms, maximum 6.836 ms, including assembly preparation, VDP waits
and interrupts. This is larger than the earlier packet-only component result
(3.3–4.6 ms); neither number is whole-game frame time.

The stage 00 sprite-player control uses 19 slots. Player blitter uses 17,
freeing two slots. Both retain the same 248-pixel viewport and 48-column cache;
there are no enemies in this comparison. Integrating bitmap player with enemy
overlap/death/dirty-terrain publication is still pending: hardware enemy sprites
would appear above bitmap player pixels and this must be evaluated explicitly.

## Radar result: correct component, rejected full-copy performance

The prototype has an opaque blue 48x80 rectangle, white flag fixtures, a red
enemy fixture and a black live player point. No radar or player sprites remain;
only three shared fuel/life slots are allocated (29 free). Relative to the
accepted fourteen-slot radar, it frees fourteen slots: twelve map cells and
two independent markers. A future enemy sprite allocation is not included in
this stage 00 count.

The actual cartridge passes 540 complete-scene canaries with both blitters,
including old terrain restoration and simultaneous X/Y wraps. Source marker
footprints are restored from a pristine offscreen bitmap before drawing their
new positions. A paused-layout capture verifies the blue panel, absent frame,
black score header and fuel placement; it does not establish moving-frame
raster correctness or speed. An unchanged radar skips its copies while paused.

Moving both blitters takes median 56.511 ms, maximum 59.813 ms in the executed
component. Against matching player-only cases, the radar adds approximately
50.95 ms median. The earlier minimal packet benchmark measured about 43 ms for
radar alone. A partial moving-route diagnostic observed roughly 78 ms refresh
intervals (about 13 FPS) and hit its 75-second scenario timeout after 941 frames;
this is a failed performance result, not an acceptance pass. Its full moving
RGB/cache route remains unaccepted. The radar diagnostic is not selected by
`LATEST` after delivery and does not replace the gameplay reference.

Full restoration, full save-under and full drawing every scroll frame are too
expensive for this renderer. The next viable experiment must restore only newly
exposed terrain strips and update only changed radar pixels, or change the HUD
layout to give the bitmap a fixed raster region. Do not advance this full-copy
approach to gameplay or describe the sprite reduction as a free speedup.

## Local evidence (ignored, contributor inputs unchanged)

All 303 repository tests pass. Fresh stage 08 HUD-on/off builds reproduce the
accepted v25 ROM hashes; these opt-in experiments do not alter that reference.

- `references/build/issue11-player-blitter-r00-v8-rgb-check/report.json`
- `references/build/issue11-player-blitter-r00-no-hud-v8-rgb-check/report.json`
- `references/build/issue11-player-sprites-r00-control-v1-check/report.json`
- `references/build/issue11-player-blitter-r00-v8-components/report.json`
- `references/build/issue11-radar-blitter-r00-v4-components/report.json`
- `references/build/issue11-radar-blitter-r00-v4-preview/paused-layout.png`
- `references/build/issue11-radar-blitter-cost-v1/report.json`
- `references/build/issue11-radar-blitter-r00-v1-fast-check/` (failed route)

Player atlas is at VRAM y640..655, backup at (208,672), at most 18x16.
Radar mutable source is at (0,704), backup at (0,800), pristine source at
(0,880), each 48x80 except the at-most-50-pixel backup. These avoid the header,
terrain atlas, maze ring and sprite tables. Original-derived graphics and all
cartridges/captures remain local under ignored `references/`.

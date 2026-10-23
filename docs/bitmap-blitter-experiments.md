# Player and 48x80 radar bitmap experiments

The user requested a player blitter first, then a blue radar equivalent to
three by five 16x16 sprites. These are isolated rendering experiments on the
stage 00 keyboard/movement/wall-collision baseline. They do not complete issue
#11 or integrate the pending enemy population, smoke or round transitions.
The accepted stage 08 v25 gameplay cartridge remains unchanged.

## Test cartridges

```sh
# Current test: bitmap player, existing sprite HUD/radar
make run LATEST=1
make run CHECKPOINT=11-blitter-player-v9
make run CHECKPOINT=11-blitter-player-no-hud-v8

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
make build STAGE=0 PLAYER_BLITTER=1 NO_HUD=1
make build STAGE=0 PLAYER_BLITTER=1 RADAR_BLITTER=1
```

The last command intentionally selects the slow diagnostic and publishes it to
`latest.rom`, like every explicit `make build`. Normal `make build` still selects
stage 08 v25. Blitter experiments currently support stages 00/01; radar requires
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

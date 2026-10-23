# Local test checkpoints

## Current test: independent blinking player radar sprite

`make run LATEST=1` selects `11-r09-player-dot-50-v115`. One original enemy,
the complete HUD and maze viewport run at 50 Hz, retaining the original
16.5 ms simulation clock. The radar uses twelve dynamic composite sprites for
the frame, flags and enemy, plus one higher-priority 2x2 player sprite.
Its white/black colors alternate every eight native ticks, following the
contributor-supplied program's dot selection at $0300. Pause freezes the clock.
Only the player is separated; enemy markers remain part of the twelve cells.

The player's movement never dirties the composite cells. Its two sentinel-safe
masks are uploaded once; the frame changes four SAT bytes and only uploads
three color bytes when the blink changes. The two pattern groups come from one
preloaded enemy facing, which now uses the existing victim cache when needed.
No original dimensions, enemy colors, game coordinates or rules change.
Twenty SAT entries are active, twelve free; natural-route line occupancy peaks
at seven with the hardware limit enabled. This checkpoint uses 50 Hz because
the preceding 60 Hz experiment failed the long cache route at frame 1225.

The natural keyboard route passes 1,138 full cache states, 28 complete RGB
images, 1,206 contact comparisons, pause, explosion, the 120-tick hold, life
loss, restart and Home. Main intervals peak at 20.270174 ms. The long control
passes 1,600 original movement/cache states and 39 RGB images. The unchanged
0.6 ms refresh tolerance remains in force. Independent checks pass 512
coordinate/blink/hidden-marker cases covering all 256 scroll phases, with no
player-induced map dirtiness; 16,416 cell cases; 12,288 flag/base cases;
1,928 enemy presentation cases; and 2,048 interruptible uploads with 327
actual IRQ overlaps. Marker backlog peaks at two refreshes, below the existing
sixteen-refresh limit.

Rebuild with `make build STAGE=9`; normal `make build` remains stage 08.
The two-enemy no-HUD and previous 60 Hz HUD checkpoints remain available below.
Stage 09 population acceptance, smoke and completion/start remain open.

## Preserved two-enemy test without HUD

`make run CHECKPOINT=11-r09-two-no-hud-v80` selects two original enemies using
their full two-plane colors; HUD work and its unused SAT entries are removed.
Six slots remain active, leaving 26 free, with a measured six-per-line peak.
The original 16.5 ms logical clock remains resampled onto 60 Hz.

The natural route passes 493 complete cache states, nineteen full RGB images,
337 exact contacts, pause, explosion, life loss, restart and Home. Its maximum
main interval is 17.156650 ms. The longer control passes 1,600 original
movement/cache states and 38 RGB images, with a maximum main interval of
17.226491 ms. Both retain the unchanged 0.6 ms raster-period tolerance.
Independent checks pass 2,643 native states, 3,856 presentation cases,
4,608 solid-run/canary cases and 2,048 uploads with 238 actual IRQ overlaps.

This isolates the HUD cost. The two-enemy HUD-on configuration still fails
moving acceptance; stage 09, smoke and completion remain open. The verified
HUD-on one-enemy reference below remains available explicitly. Normal
`make build` still selects stage 08. See [the cache experiment](solid-cache-runs.md).

## Preserved HUD-on checkpoint: twelve-cell radar at 60 Hz

`make run CHECKPOINT=11-r09-one-60-v61` selects one original enemy, a
twelve-sprite radar, the full maze viewport, forty cached columns and the
original 16.5 ms logical clock resampled onto 60 Hz. Arrows steer, Space pauses
and Home resets. Death presentation uses the next refresh's snapshot, adding
at most one display period of visual latency while native collision/hold/life
rules keep their original tick order. Both one-enemy moving routes pass.
The natural contact/restart route passes 493 cache states, 19 full RGB images,
337 exact source contact observations and the unchanged timing gates. Main
intervals peak at 17.249678 ms. The long render-only reversal control passes
1,600 original movement/cache states and 44 full RGB images, with a maximum
main interval of 17.284599 ms against the unchanged 17.287875 ms limit.
`11-r09-one-no-hud-60-v61` passes the same contact route and 1,600-state control
(35 RGB images), allowing a direct HUD comparison. It reserves 19 SAT slots,
13 free. Radar updates start only between physical lines 80 and 144; deferred
cells remain queued (observed maximum four refreshes, limit sixteen). The player uses a
one-pixel upward presentation bias only for forbidden SAT Y=216, preserving its
full 16×16 pixels without bitmap save/restore. Native movement/collision stays
unchanged. No further enemy population is accepted yet.
The default build remains stage 08; its preserved reference is
`11-r08-restored-v1` at 50 Hz. Stage 09 population, smoke and completion are open.
Rendered verifiers record complete frames to avoid host frame skipping leaving
a stale screenshot; guest clocks and pixel/timing checks are unchanged.
See [cache and timing work](enemy-population-cache-fix.md) and the
[presentation contract](death-presentation-pipeline.md).

## Preserved controlled experiment: sprite flicker

`11-flicker-60-v6` starts paused with two enemies aligned
over the radar, alternating real SAT priority every refresh. Compare with
`make run CHECKPOINT=11-flicker-50-v6`. Both pass 120 controlled refreshes and
ten complete RGB images with real hardware sprite limits. Space resumes an
unaccepted moving prototype; Home restores the controlled fixture. The test
uses 24 slots/eight free and does not increase the eight-per-line limit.
See [commands, measured cost and integration limits](sprite-flicker-experiment.md).

After the user's `make clean`, the accepted stage 08 cartridges were rebuilt as
`11-r08-restored-v1` / `11-r08-no-hud-restored-v1`; both reproduce v25 ROM bytes.
Those four checkpoints were restored before the moving one-enemy pair above. The sections below
record historical results; their old cartridges and proof bundles were removed
by the clean. Use `make checkpoints` for the actual local inventory.

## Previous rendering experiment: bitmap player

The previous `LATEST` selected `11-blitter-player-v9`: stage 00 movement with bitmap player,
existing sprite HUD/radar, 17 occupied slots and no enemies. Both HUD modes pass
1,600 movement/cache states, full RGB (32/26 images) and the unchanged timing
gate. `11-blitter-player-no-hud-v8` and `11-blitter-sprites-control-v1` provide
the matching comparisons. The accepted gameplay build remains stage 08 v25.

`11-blitter-radar-v4` is a separate **slow diagnostic**: blue 48x80 radar,
no border, black score header and just three fuel/life slots. Its executed
component passes 540 scene/wrap cases, but full-copy moving performance fails.
It is not the selected latest build. See [methods, commands and measured
limitations](bitmap-blitter-experiments.md).

## Active incremental build: stage 08

`11-r08-enemy-v25` / `11-r08-no-hud-v25` add one original enemy: initialization,
AI, movement/facing, six-slot virtual visibility, real radar position and contact
through the established explosion/life system. Score/flags persist on restart;
pause freezes the enemy. Following the user's clarification, v25 restores the
black score header and square white radar border. The radar remains transparent;
a solid blue fill does not fit the zero-extra-sprite/CPU requirement at this
geometry. All seven timing/gameplay traces are byte-identical to v24 in both
HUD modes, and executable bytes, symbols and sprite allocation are unchanged.

The original enemy oracle passes 2,643 cases; executed presentation passes 1,928
facing/cache/clipping cases without changing maze VRAM. Grouped flag repair
passes 512 wrap/budget canaries. Both modes pass 1,600 cache/movement states
(38/36 full RGB) and the enemy keyboard route (1,138 cache states / 28 RGB,
40 paused refreshes, one exact contact, 120-tick hold, restart and Home).
Continuous sprite occupancy peaks at eight with HUD / four without, 21 SAT slots
reserved and 11 free. Main maxima are 20.101 ms standard / 20.050 ms enemy route;
the unchanged 0.6 ms display-period gate passes for every measured raster phase.
All 303 tests pass, including the square-corner/resource-size check. The preserved
stage 07 ROM reproduces its original hash.

Graphics adaptations: the enemy retains exact 16x16 source masks, with a
one-pixel upward presentation bias only at forbidden SAT Y=216 and one clipped
sprite scanline at the VDP header/prefetch boundary (sprite viewport starts at
y12, bitmap maze at y11). World coordinates and collision rules do not change.
The cache retains 48 columns/eight guard tiles; an actual line-196 deadline
bounds invisible prefetch. Pending score publication can drain on the next
refresh after a two-tick driving frame. See [measurements and rejected fixes](one-enemy-performance-fix.md).

`make run CHECKPOINT=11-r08-enemy-v25` selects this HUD-on checkpoint; `make build NO_HUD=1`
rebuilds the same systems without HUD. Controls: arrows, Space pause, Home reset.
The two-rock fixture remains explicit until normal initialization/transitions.

## Preserved lives/restart component: stage 07

`11-r07-lives-v4` / `11-r07-no-hud-v4` add one life loss per collision, a live
spare-car HUD, same-round restart and a stopped zero-life run. Score, high score
and collected flags persist; fuel refills and the new life's point ordinal
resets. Holds are 120/120/96 logical ticks across the initial three lives. Home
starts a fresh fixture run. Credit/start/game-over presentation remains stage 11.

The original component oracle passes 48 decrement/wait/restart/next-flag cases.
Both HUD modes pass the three-life keyboard route (1,289 full cache states,
19 complete RGB images, 40 paused refreshes), and the standard 1,600-state
route (37/39 RGB). Scene reloads measure 714 ms with HUD / 669 ms without;
they and two warm-up frames are reported separately from steady driving.
Standard main maximum is 20.304 ms; life-route main maximum is 19.938 ms.
All 295 tests pass. V4 bytes equal the V2/V3 proof candidates and refreshes
metadata. `make run LATEST=1` selects HUD-on; `make build NO_HUD=1` selects
the same rules without HUD. See the [lives plan and results](lives-restart-plan.md).

## Preserved fuel component: stage 06

`11-r06-fuel-v6` / `11-r06-no-hud-v6` add original decimal fuel consumption,
empty-fuel deceleration and the lucky countdown. The gauge shows actual fuel;
F no longer changes it while driving. Lucky restores the saved fuel, follows
the original round-dependent cadence, and is excluded when it is the last flag.
Arrows steer, Space pauses, Home resets. Lives/restart remain the next component.

The independent original oracle passes 91 cases / 9,982 exact ticks, including
full depletion, low/empty boundaries, carries and bonus-life accounting. Both
HUD modes pass 1,600 movement/cache states (37/39 full RGB), the complete ten-flag
route (2,786 cache states / 12 RGB / 177 exact original lucky ticks), and the
death/pause/reset route (10 RGB). Grouped explosion copies pass 512 cache-wrap/
budget cases. All 291 tests pass. See the [measured fix](fuel-performance-fix.md).
`make run LATEST=1` selects the accepted HUD-on cartridge; `make build NO_HUD=1`
rebuilds the same stage without HUD. The stage 02 rock/contact build also received
the user's manual confirmation of normal speed and a clean right edge.

## Preserved scoring component: stage 05

`11-r05-score-v5` / `11-r05-no-hud-v5` add actual flag points, special multiplier,
original digit carry/high score and source bonus-life accounting. The HUD now
shows actual score values. Lucky fuel conversion is the next component and
remains pending. The [score performance fix](score-performance-fix.md) records
the initial regression and exact-output adapter. Both HUD modes pass standard
and all-ten-flag keyboard/cache/RGB routes; 1,278 original scoring cases and the
death/reset regression pass. V5 ROM bytes equal the V4 visual/proof candidates;
V5 adds accurate metadata and complete component profiling. `make run LATEST=1`
selects the accepted HUD-on build. Home resets this diagnostic game.

## Preserved collection component: stage 04

`11-r04-flags-v7` and `11-r04-no-hud-v7` add one-time normal/special/lucky flag
collection and persistent bitmap/radar removal. Scoring and lucky fuel rewards
remain pending. The visible viewport is unchanged; only its invisible cache halo
is smaller. The [performance fix](flag-collection-performance-fix.md) records the
first regression and accepted measurements. Both HUD modes pass the complete
ten-flag/revisit/reset route (2,642 cache states, 12 full RGB images), the original
boundary oracle and the standard movement regression. `make run LATEST=1` selects
this accepted HUD-on build. Home resets the diagnostic board.

## Preserved explosion component: stage 03

`11-r03-explosion-v2` and `11-r03-no-hud-v2` add the original 24x24 bitmap
explosion, movement lock and 120 logical-tick hold. It uses zero new sprites and
shares the existing 22-command ceiling. Terrain returns when the hold expires;
press Home to reset this fixture. Lives and automatic restart arrive in stage 07.
Keyboard death/pause/reset and 11 full RGB images pass in each HUD configuration;
the regular route passes 1,600 movement/cache states and 34/36 full RGB images.
`make run LATEST=1` selects the accepted HUD-on cartridge.

## Preserved contact detector: stage 02

`make build` / `make run LATEST=1` now select bitmap rocks plus diagnostic contact
events. `11-r02-contact-v1` and `11-r02-no-hud-v1` are the accepted immutable
builds for isolated contact detection. The car still crosses rocks in stage 02.
The detector does not alter movement or draw a replacement visual cue.

Original geometry is independently checked in 2,196 boundary/event cases and a
real keyboard entry/pause/departure/re-entry/restart/resume route. All 281 live
logical contacts match the original branch. Isolated detector maximum: 573 cycles
(0.160 ms); maximum steady GPU commands remains 22, with zero new sprite slots.
HUD-on/off each pass 1,600 movement/cache frames and 34 complete RGB images.

## Accepted bitmap foundation: stage 01

`make build STAGE=1` selects the accepted bitmap-rock fixture. `make build STAGE=0`
recreates the preserved movement-only baseline. Both support `NO_HUD=1`.

```sh
make run CHECKPOINT=11-r01-rocks-v3
make run CHECKPOINT=11-r00-base-v1
```

Stage 01 adds two original rock-placement outputs as bitmap scenery on the
baseline maze. The untouched first stage normally has no rocks; this is an
explicit presentation fixture, not a claim to run a complete later round.
Collision and explosion are absent at this stage, so the car can cross rocks.
`11-r01-no-hud-v3` is the same fixture without HUD frame work. Versions v1/v2
remain available as failed-timing comparisons; use v3 for the accepted result.

V3 passes 1,600 movement/cache states, 33 car images, 53 complete-map images and
19 focused rock edge/reversal/eviction images. GPU command counts per frame and
movement records exactly match the stage 00 control; no rock sprites are added.
Main-loop intervals: median 19.937 ms, maximum 20.052 ms. The HUD-off fixture
passes 1,600 states and 34 images as well. See the [atlas fix](rock-atlas-performance-fix.md).

## Preserved restart: stage 00

The user-directed [incremental gameplay plan](incremental-gameplay-plan.md)
supersedes the earlier full-runtime experiments below. Start with:

```sh
make build STAGE=0
make run LATEST=1
make run CHECKPOINT=11-r00-base-v1
```

`11-r00-base-v1` contains the first maze, HUD fixtures and original player movement,
steering, wall collision and animation, with the issue 24 native mask. No complete
arcade loop, enemy AI, collection, scoring or fuel rules execute. `11-r00-no-hud-v1`
contains the same baseline without HUD frame work; rebuild it with
`make build STAGE=0 NO_HUD=1`. `make build STAGE=0` restores HUD. Both commands update the
default cartridge and `latest.rom`; `NATIVE=1` is a compatibility alias for this
baseline. Historical full-loop CLI builds no longer update `latest.rom`.

Controls for these stage 00 builds: **arrows** steer, **Space** pauses, **Home**
restarts, **Enter** toggles driving/map inspection. No credit/start sequence is
required. Score, fuel and remaining lives are display fixtures at this stage.

## Historical full-runtime experiments

The following builds failed playable-speed acceptance and remain available only
for comparison. They are not incremental additions to stage 00.

Run `make checkpoints` to list the cartridges available in this checkout. Open
one with `make run CHECKPOINT=11-06-actor-cache`. Names retain the exact ROM and
sealed build-manifest hashes; later changes receive new names. A missing or
modified checkpoint fails explicitly. These local artifacts are removed by
`make clean` and are never committed with original game data.

| Checkpoint | Components to evaluate | Status |
| --- | --- | --- |
| `24-base` | First maze, HUD, keyboard-controlled car and maze collisions | Fast reference from issue 24; excludes full original gameplay |
| `11-01-host` | Full original logic, input and display host | Diagnostic: one frozen image; actors and HUD hidden |
| `11-02-scenery` | Full original logic and updating scenery | Diagnostic: actors and HUD hidden |
| `11-03-actors` | Full logic, scenery and hardware actors | HUD disabled; source pixels and four full raster captures verified |
| `11-04-full` | Full logic, scenery, hardware actors and HUD | Comparison baseline; source pixels and four full raster captures verified |
| `11-05-edge-cache` | Full presentation with cheaper right-edge restoration | Source pixels and four full raster captures verified |
| `11-06-actor-cache` | Previous optimization plus exact actor-pattern reuse | Source pixels and four full raster captures verified |
| `11-07-scenery-cache` | Scenery-only presentation with the cheaper right-edge repair | Source pixels verified across 167 frames and four raster captures; actors and HUD hidden |
| `11-08-no-hud-cache` | Optimized scenery and cached hardware actors | Source pixels verified across 180 frames and four raster captures; HUD disabled |

For the issue 11 cartridges, insert credit with **5**, start with **1**, move with
the **arrow keys**, and release smoke with **Space**. The frozen and scenery-only
diagnostics intentionally cannot provide a complete visual gameplay test.

For the current component comparison, use `11-07-scenery-cache`, then
`11-08-no-hud-cache`, then `11-06-actor-cache`. This sequence keeps the cheaper
edge repair enabled throughout and adds actor presentation followed by the HUD.
The earlier `11-02-scenery` / `11-03-actors` / `11-04-full` sequence retains the
original expensive repair as an unchanged historical comparison.

The same 2440-tick replay reproduced multi-second presentation delays with only
scenery enabled. Removing the HUD alone did not resolve them. Replacing the
expensive edge repair reduced the all-scene median from about 259 ms to 80 ms;
the actor cache reduced the median actor-drawing stage from about 44 ms to 28 ms.
These are experiment observations, not a playable-speed acceptance result:
gameplay frame delays still reached about 3.2 seconds, and title frames dominate
the overall median. Issue 11 remains incomplete.

The optimized component sequence produced the following observations with the
same 2440-tick input replay. "Gameplay-visible" means the original radar dot
outputs identify gameplay/demo; the game logic remains enabled in every build.

| Checkpoint | Prepared frames | Overall median latency | Gameplay-visible frames | Gameplay-visible median latency | Maximum latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| `11-07-scenery-cache` | 167 | 40 ms | 19 | 859 ms | 2413 ms |
| `11-08-no-hud-cache` | 180 | 43 ms | 27 | 299 ms | 1936 ms |
| `11-06-actor-cache` | 151 | 80 ms | 11 | 1544 ms | 3249 ms |

These runs do not execute identical rendering work: scheduling changes when the
next snapshot is captured and how far the camera moves between prepared frames.
Consequently, subtracting these medians does not measure a component's isolated
CPU cost. The HUD-free variant improves this replay, but none meets playable
speed. Sealed local evidence is summarized in
`references/analysis/issue11-optimized-isolation-report.json`.
Checkpoint descriptions preserve the status at publication; this guide records
subsequent verification results.

New checkpoints should identify the changed component, enabled presentation
layers, completed validation and remaining limitations here. Publish a sealed
local cartridge using:

```sh
.venv/bin/python -B scripts/native_runtime.py checkpoint \
  --name <new-name> \
  --rom references/build/<bundle>/native.rom \
  --description '<components and purpose>' \
  --kind experimental
```

Use `diagnostic` for deliberately hidden or frozen presentation and `reference`
for a known comparison build. Publishing a checkpoint does not replace the
default cartridge.

Named checkpoints stay unchanged. A failed build retains the previous latest
cartridge; `make run LATEST=1` validates the linked bundle and never falls back to
a default ROM.

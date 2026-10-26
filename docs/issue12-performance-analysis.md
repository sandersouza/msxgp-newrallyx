# Issue #12: bounded 30 Hz presentation

The slowdown grows with enemy count across ordinary rounds. The challenge
round is a useful stationary-car workload, not the scope of the problem.
The user approved stable 30 FPS with occasional stutters, approximately 60 Hz
game clocks, and MSX-specific enemy behavior resembling the arcade.

Original scenery pixels, colors, dimensions, complete two-plane cars, the full
HUD and real V9958 sprite limits remain enabled. This iteration changes enemy
decisions and movement scheduling; it does not claim identical arcade AI or
speed. The reference machine is openMSX 21.0's Panasonic FS-A1WSX with a
128 KB main RAM mapper, 128 KB VRAM and its factory 5.37 MHz CPU mode.

## Why earlier measurements were insufficient

Native tick rate, foreground loop rate and visible motion are different clocks.
Near-60 Hz logic can coexist with irregular camera updates and large catch-up
steps. A low percentage of foreground loops above 40 ms did not establish smooth
physical presentation. The previous v127 default also ran arcade virtual OAM,
registration and screen-coordinate maintenance alongside the MSX renderer.

The current probe observes complete VBlank packet commits and actual maze
R26/R27/R23 latches. It measures repeats while native motion is still owed,
not just an average loop rate. Loading, pause, death and completion boundaries
are explicit; active stalls remain in the relevant denominators. Controlled
population/initial-round fixtures are reported separately from natural routes.

## Runtime changes

The display refreshes at approximately 59.92 Hz. A complete actor/camera packet
is published every second VBlank, targeting **29.961 FPS**. An unfinished packet
cannot replace another pending packet. Both scroll axes and complete enemy
attributes/masks share the same publication. Player, radar, fuel and footer use
the actual latched scroll every physical refresh.

The player, input, fuel, phase clocks, contact and original startup/spin recovery
continue at the native clock. Enemy movement and decisions run every other
native tick, using twice the fractional delta. Their source descriptors retain
the ordinary per-tick velocity. Smoke immunity is decremented in native tick
units; smoke detection is sampled with the enemy update. Maximum player speed
is two pixels per native tick; maximum enemy speed is 1.875 pixels. Lower original
near/far speeds and original challenge activation remain effective. Difficulty
also comes from the original population/phase parameters and pursuit policy.

Enemy decisions use reciprocal maze exits, alternating pursuit-axis priority,
and reversal only at a dead end. Each actor decides once at a new cell centre
and coasts between centres. The centre tolerance covers the doubled movement
step. World-space contact checks all seven actors with the documented inclusive
ten-pixel rectangle. Arcade virtual OAM and five-pointer visibility/contact
maintenance are excluded from this full-game path. The bounded build retains
the previous original adapter.

Twelve shared complete-car mask slots replace seven independent private caches.
Matching poses are reserved before eviction. At most two front-referenced masks
need replacement at VBlank; other required masks are preloaded into unreferenced
slots. Negative-X projection preserves every visible source pixel while using
anchor zero and the same initialized OR colors. Source-pixel proofs include
seven simultaneous cars, all original facings, clipping and cache eviction.

The terrain cache retains exact global ownership for every physical tile.
Clean original cells and smoke cells use larger exact bitmap copies. At a
32-tile seam, the renderer copies the contiguous one- or two-tile fragment of
the original cell, rather than reducing all seam work to individual tiles.
Overlap, expiry, explosions and unsafe cases retain smaller exact copies.
Old smoke shadows from another torus lap do not invalidate unrelated cells.

Camera candidates validate both axes independently and advance at most eight
pixels from the packet's starting centre, including an urgent in-frame retry.
Hidden queues retain perpendicular guards and forecast the current movement
axis. Urgent copies precede the snapshot within a bounded budget; optional
guards, scoring and bitmap-HUD maintenance follow readiness. A completed packet
does not wait for future scenery work.

## Interrupt and state-transition corrections

- Preparing a new scroll must not overwrite the scroll used by the frame on
  screen. Active preparation sets the existing session-position protection;
  scene initialization can still latch immediately.
- VBlank publication preserves the **actual interrupted Page0 mapping**, including
  primary/secondary slot and mapper segment. Restoring the BIOS unconditionally
  could remove an interrupted terrain instruction stream and reach a restart
  vector. Mapper/code guards and loaded routes cover this case.
- Foreground RAM work and ordinary uploads yield to raster IRQs. Fuel publication
  follows the radar/player attributes in the maze IRQ, leaving VBlank room for
  complete car masks. The footer has its own reserved interval.
- Session screens bypass gameplay-packet backpressure. Otherwise a demonstration
  or game-over transition could wait for a packet that UI VBlank never commits.

Presentation code occupies EA00..EBFF, unused sound workspace in this selected
core. Native E988/E9F4 pointers and EC00 smoke attributes remain intact. The
spare mapper segment contains packets/cache metadata below 0384, terrain code
at 1000..1FFF, ownership at 2000..2FFF and navigation at 3000..36FF. Fresh native
RAM initialization restores executable presentation code. Future sound work
must reconcile this reservation. The host stack still starts at F380; cold-code
write guards remain active in loaded routes.

## Measurements and qualification

Cartridge SHA-256:
`3f2de3a86b53cb47723fda5c13eed24fe91e32ed131a4bc7651743d24de3cebf`.
The independently rebuilt default must match the sealed
`issue12-msx-enemies-qualified-v210` cartridge. All measurements below use that
same ROM. Ignored reports retain every interval, clock debt/drop counter,
actual camera step, ownership check and fixed-sprite comparison.

| Workload | Population | Complete packets/s | Missed 30 Hz slots | Native ticks/s | Worst owed camera repeat |
| --- | --- | ---: | ---: | ---: | ---: |
| Eight naturally completed rounds | Original 1..4 moving / 7 challenge | 29.29..29.96 | 0..2.28% | 58.36..59.90 | 117 ms |
| Controlled round 1 | 6 moving | 29.82 | 0.48% | 59.96 | 117 ms |
| Controlled round 1 | 7 moving | 29.82 | 0.48% | 59.73 | 83 ms |
| Original round 3, explicitly seeded | 7 initially parked | 29.93 | 0.12% | 59.92 | 50 ms |
| Original round 8, explicitly seeded | 4 moving | 29.30 | 2.25% | 58.45 | 83 ms |

The 95th-percentile complete-packet interval is approximately **33.41 ms** in
every measured round. Moving-camera update intervals have a 95th percentile
of **33.38 ms** on both axes; their observed rates are about 28..29.5 updates/s.
The longest complete-packet interval is 66.79 ms. Camera waits can last longer
than a packet interval because a repeated coherent snapshot can still owe an
edge. Both properties are measured. Camera steps remain bounded to eight pixels.

This is a near-30 FPS profile with occasional hitches, not a guarantee that
every frame meets 33 ms. Approximately **97.7..100%** of intervals meet the
ordinary two-refresh cadence. The exploratory 2% missed-slot gate fails in the
eighth natural round and the seeded round-eight workload; those sealed failures
remain recorded. The reviewed profile allows at most 2.5%, a 67 ms packet gap,
117 ms owed camera repeat, a 34 ms p95 packet/camera interval, and 58 native
ticks/s per round. It passes all five workloads. This is an explicit timing
concession under the user's occasional-stutter allowance, not an unchanged
arcade-speed claim. The worst complete five-second native window is 56.54 Hz.

Across these routes, 27,892 native ticks execute and 117 are discarded at the
bounded debt limit (0.42% of executed-plus-discarded ticks). The natural eight-round
route accounts for 69 of those discarded ticks. This small debt loss is reported
instead of hiding it behind a foreground-loop average or claiming exact 60 Hz.

There are **zero errors** in 157,605 live radar checks, 31,520 fuel checks,
31,508 footer checks and 30,930 player checks. Header reservations stay below
6.026 ms. Every sampled latched viewport owns its world tiles; mapper restoration,
executable RAM guards, complete-mask budget and real VDP access checks pass.

Current local evidence uses the `issue12-qualified-*-v210` prefix:

- `natural`, `six`, `seven`, `bonus`, `heavy`: actual packet/camera/native traces;
  only `natural` has no guest-state setup writes and completes eight rounds.
- Matching `*-pixels`: 58 independent cache/smoke/HUD snapshots and 62 complete
  enemy images. Real sprite overflow reaches ten enemy planes per scanline;
  hardware culling remains enabled.
- `contracts`: 15,978 executed MSX steering/contact/smoke/speed/motion cases.
  `cars`: 13,496 full-car cases, including seven simultaneous complete masks.
- `terrain`: 66,560 ownership-row cases and 768 contiguous-fragment cases.
  `clock`: 384 elapsed-clock cases.
- `preparation`: 508 exact original/native preparations; `rules`: 1,728 original
  phase boundaries; `scenes`: 254 explicitly seeded map/object/header transitions.
- `session`, `state`, `attract`: real two-player credit/turn/death lifecycle,
  distinct partial-board restores, 14 HUD boundaries, challenge failure and the
  real title/demo/title/credit/human-start cycle.
- `six/scanout.avi`: eight seconds of actual six-enemy scanout with selected
  images inspected. Its first recorded frame is entirely black initialization;
  all following **478 gameplay frames** retain both complete radar borders at
  identical decoded pixel coordinates (`issue12-media-review-v210`). Recordings,
  source inputs and extracted pixels stay ignored.
- `issue12-performance-review-v210`: sealed aggregate of the reviewed profile,
  keeping the stricter failed gates explicit. All **381 authored tests** pass.

The bounded Issue 11 build remains byte-identical:
`9771e72b394f5a3c66018f638318caa5e4e060eed85c2dcc27d5f5328f5efc12`.

The exploratory zero-discard/100 ms freeze gates were also stricter than the
accepted occasional-stutter requirement. Complete packet intervals and actual
camera cadence remain separate acceptance observations.

The controlled tick benchmark restores the same declared gameplay fixture,
preserves the candidate's executable RAM, samples both enemy cadence phases
equally and subtracts actual IRQ duration. In the qualified implementation, six
moving enemies cost a median **2.72 ms** at intersections and **2.63 ms** between
intersections, versus **8.48/8.19 ms** in the original v130 adapter. This isolates
CPU scaling; it is not a replay-identical gameplay comparison. Evidence is local
and ignored (`issue12-msx-runtime-baseline-tick-v130`, `issue12-qualified-tick-v210`).

The twelve-slot seven-car transfer body measured 1.89 ms in executed presentation
fixtures. That interval excludes the mapping/register prologue and epilogue.
Live header and sprite-band checks, ordinary-transfer frequency guards and real
VDP access timing remain the independent deadline checks.

## Reproduce

Use fresh ignored output directories and contributor-supplied inputs. Set
`ROM` to a sealed build's `raster-scroll.rom`.

```sh
.venv/bin/python -B scripts/raster_scroll.py build --stage 12 --full-game --hz 60 --output references/build/my-30hz
.venv/bin/python -B scripts/full_game_route.py --rom "$ROM" --output references/build/my-natural --rounds 8 --avoid-enemies --allow-game-over --profile --radar-trace --require-stable-radar --require-stable-fuel --require-stable-player --maximum-scroll-step 8
.venv/bin/python -B scripts/full_game_route.py --rom "$ROM" --output references/build/my-seven --rounds 1 --fixture-enemies 7 --avoid-enemies --allow-game-over --radar-trace --require-stable-radar --require-stable-fuel --require-stable-player
.venv/bin/python -B scripts/full_game_route.py --rom "$ROM" --output references/build/my-round-eight --rounds 1 --fixture-first-round 8 --avoid-enemies --allow-game-over --radar-trace
.venv/bin/python -B scripts/full_game_evidence.py --rom "$ROM" --capture references/build/my-natural --output references/build/my-pixels
.venv/bin/python -B scripts/full_msx_enemy_probe.py --rom "$ROM" --output references/build/my-enemy-contracts
.venv/bin/python -B scripts/full_enemy_probe.py --rom "$ROM" --output references/build/my-complete-cars
.venv/bin/python -B scripts/full_terrain_probe.py --rom "$ROM" --output references/build/my-terrain
.venv/bin/python -B scripts/full_clock_probe.py --rom "$ROM" --output references/build/my-clock
.venv/bin/python -B scripts/full_tick_cost.py --rom "$ROM" --output references/build/my-tick-cost
.venv/bin/python -B -m unittest discover -s tests
```

`--fixture-enemies` changes only the controlled initial population before the
original initializer. `--fixture-first-round` changes the initial round before
original preparation. Both are guest setup writes, not natural progression.
`--allow-game-over` preserves a legitimately ended route and its actual completed
round count. `--record-round N` records eight seconds of real scanout with VDP
limits enabled. Seeded all-round scene/preparation probes do not prove 254
naturally completed rounds.

Performance remains qualified on the stated factory-clock reference, not generic
3.58 MHz machines or physical hardware. An explicit PAL diagnostic presents at
half its own refresh rate and is not a 30 FPS qualification. Sprite culling
above eight candidates per scanline remains a real hardware limitation. Audio
is still silent. Issue #12 acceptance and merging retain their review gates.

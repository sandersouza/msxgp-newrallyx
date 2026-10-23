# Issue 11: rebuild gameplay from the fast driving baseline

## Decision and scope

User decision, 2026-10-22: stop integrating the complete arcade foreground/IRQ
loop and then hiding presentation layers. Return to the controllable maze/HUD/
wall-collision build available before issue 11 and add gameplay systems one at a
time. The issue 24 native mask is retained: 19 sprite slots in the reference,
13 free, original-size assets and world coordinates. This is a selective-routine
integration, not a restart of the complete arcade scheduler.

The previous full-runtime candidates and authored work remain available as
historical evidence. They are not the active baseline. Exact original routines,
tables and rules are reused where practical, behind explicit adapters with bounded
work. A subsystem is not allowed to silently start the original foreground,
boot diagnostics, attract loop or a second renderer.

Stage 0 already retains the selected player initialization, fixed-point movement,
steering, maze wall probes and animation from the earlier driving build. Other
gameplay is absent. Its score, fuel, remaining lives and enemy radar point are
display fixtures, not implemented game systems. This distinction stays visible
in build metadata and test reports.

## Execution sequence

Each row adds one behavior to the preceding accepted checkpoint. No next row is
integrated while the current row fails correctness or performance. Collision
death is introduced after rocks so it has a real collision source; enemy-car
collisions later reuse that same death state.

| Stage | Addition | Required behavior and focused scenario |
| --- | --- | --- |
| 00 | Restore the fast driving baseline | First maze, controllable player, wall collision, HUD fixture; no full arcade loop. Verify the entire rightmost visible column during movement, turns, wrapping and all map corners. |
| 01 | Rocks in the bitmap scenery | Load original rock positions and original-size rock graphics into the world/tile cache. Zero new SAT entries. Rocks survive cache eviction, camera movement and reversal. No collision/death logic yet. |
| 02 | Rock collision detection | Original collision geometry and positions; report collision once per contact in a diagnostic event field. Near misses and wall overlap do not trigger it. No death animation yet. |
| 03 | Explosion/death animation | Consume the collision event; run only the selected original death sequence. Validate frame order, duration, movement lock and completion. Reuse the player's sprite allocation where possible; no enemy AI yet. |
| 04 | Flag collision and collection | Original flag positions and normal/special/lucky distinctions. Each flag is collected once; remove it from the authoritative world state and bitmap/radar, including after cache reload. Record collection events; no score calculation yet. |
| 05 | Score | Apply original scoring/BCD rules to collection events. Validate normal, special/lucky and carry cases; publish actual score/high score through the existing HUD. Disable the score demo fixture. |
| 06 | Fuel | Original consumption timing, collection effects and empty-fuel transition. Replace the fuel demo fixture. Test full/empty, pause and collection boundaries independently of score. |
| 07 | Lives and restart | Original life loss and stage restart state; update the actual lives HUD. Validate explosion completion, one decrement, restart and zero lives. |
| 08 | One enemy | Add one visible enemy and its selected original update routines. Respect sprite-line and total-slot limits; show its real radar point. Test pathing, near misses and collision through the existing death sequence. |
| 09 | Remaining enemies | Add one enemy at a time up to the original population, measuring each increment. Keep original behavior and priority; identify the exact count/routine that breaches the budget. |
| 10 | Smoke | Original activation, resource/rate limits, lifetime and effect on enemies. Test creation/expiry and worst simultaneous population; publish the sprite budget. |
| 11 | First-stage completion and transitions | Remaining flags, completion bonus, stage transition and game-over behavior for the agreed playable slice. Title/credit/start integration is separate from the driving baseline and cannot restart the complete foreground loop. |

Sound, additional stages and presentation polish do not block locating the
performance offender in these steps. They remain separately scoped work.

## Measurement and acceptance for every stage

1. Keep the previous accepted ROM immutable. Build the candidate with a name such
   as `11-r01-rocks-v1`, its enabled systems, source/configuration hashes and SAT
   ownership. Point `references/build/latest.rom` at the explicitly delivered
   candidate; `make run LATEST=1` must select that exact ROM.
2. Run the same baseline driving input sequence (1,600 movement states), plus a
   focused sequence for the new behavior and a worst-load sequence. Compare the
   common route before an intentional gameplay divergence. Do not mix title/
   startup frames into gameplay latency statistics.
3. Use standard 3,579,545 Hz MSX2+ CPU, real VDP command timing, sprite limits and
   50 Hz display timing. Keep the original 16.5 ms simulation tick resampled onto
   refreshes. No CPU overclock, clock slowdown, skipped logical ticks, repeated
   screenshots presented as new frames or full-screen bitmap redraw per tick.
4. Record median/p95/maximum subsystem CPU cost, renderer CPU cost, end-to-end
   update/presentation time, GPU command count/time and sprite totals/per-line
   peak. A measurement that is unavailable must be labelled unmeasured.
5. Retain one presentation per advancing refresh, no accumulated work queue and
   no missed raster/VRAM deadlines. The established verifier compares refresh
   intervals to the selected display period with a 0.6 ms tolerance; report exact
   measured min/max rather than inventing a nominal FPS result.
6. Verify original dimensions/coordinates and complete visible graphics,
   including the full right edge, with actual rendered RGB captures plus cache
   checks. Check collection persistence, collision boundaries and original rule
   outputs using contributor-supplied ROMs or independent synthetic fixtures.
7. Publish correctness/performance results and a runnable checkpoint before
   advancing. A ROM that boots is not sufficient acceptance.

## When a stage breaches the budget

Stop adding systems. Reproduce the regression against the immediately preceding
accepted build with the same inputs. Measure the added routine, dirty tiles,
cache misses, VDP commands and sprite occupancy separately. Write a focused fix
plan for that measured cost, apply it, and rerun both the focused scenario and
the baseline regression. Only then advance. Permitted adaptations include a
smaller maze viewport or scenery palette simplification; preserve original asset
dimensions, world coordinates and gameplay rules, and document the tradeoff.

## Tracking

- Parent: https://github.com/sandersouza/msxgp-newrallyx/issues/11
- Existing #19–#23 retain useful loader, contract and evidence work; their earlier
  full-runtime execution order is superseded for gameplay integration by this
  user-directed sequence. They are not automatically completed or closed.
- Stage 00: restored and emulator-verified. HUD-on ROM is byte-identical to the
  accepted issue 24 fast reference (`a89f20da...`), with no full arcade loop.
  Fresh verification passes 1,600 movement/cache states and 34 full RGB images;
  HUD-off passes the same 1,600 states and 32 RGB images. A separate full-map
  test passes 3,801 continuous cache checks and 53 full RGB images, including the
  entire right edge. No VRAM/raster deadline failures occurred. The measured
  main-loop refresh interval was 19.523–20.351 ms with HUD and
  19.935–19.938 ms without HUD, using the verifier's documented startup/reload
  exclusion policy. Explicit Home scene reload still takes about 0.9 seconds;
  it is not steady driving and is not hidden in the raw evidence.
  Local evidence: `references/build/issue11-r00-{player-check,raster-check,no-hud-player-check}/report.json`.
- Stage 01: accepted as the explicit rock-presentation fixture `11-r01-rocks-v3`.
  The normal first-stage initialization has no rocks. For this incremental test,
  isolated original parameter/placement routines provide two rock positions from
  internal round record 3 on the same maze; only those rock cells are added to
  the baseline board. Flags and movement remain unchanged. Every resulting tile
  is checked against the original Z80 redraw across 28,672 code/attribute pairs.
  The 37-tile atlas uses 2,048 VRAM bytes and four source-address ROM banks; it
  allocates no rock sprites or extra runtime RAM. Initial atlas versions failed
  the existing timing gate; [the measured fix](rock-atlas-performance-fix.md)
  passes without relaxing it. Fresh v3: 1,600 movement states, 33 moving-car RGB,
  53 map RGB, 19 focused edge/eviction RGB; HUD-off 1,600 states and 34 RGB.
  Stage 00 rebuilt from current sources remains byte-identical to its reference.
- Stage 02: accepted. Only original contact-cell geometry `$1774..$17a5` is
  linked, with an explicit return before the flag/death/AI logic. An immutable
  two-address lookup and eight host RAM bytes record entry events; the original
  player RAM and VRAM remain unchanged by the detector. Independent original
  full-branch oracle passes 2,196 signed-boundary/contact/debounce cases. A real
  keyboard route reaches a rock, holds contact paused, leaves, re-enters, pauses,
  restarts and resumes: all 281 logical contact observations match the original
  routine. Home preserves pause, so the test explicitly resumes to check the
  first restarted tick. Detector worst isolated cost is 573 cycles (0.160 ms).
  Standard 1,600-frame movement/cache/RGB/timing tests pass with and without HUD
  (34 full RGB images each), retaining maximum 22 GPU commands per steady frame.
  Checkpoints: `11-r02-contact-v1`, `11-r02-no-hud-v1`. No explosion yet.
- Stage 03: accepted as `11-r03-explosion-v2` and `11-r03-no-hud-v2`.
  Isolated original `$1960` drawing validates all 64 fine-scroll phases: a static
  24x24 bitmap, nine original tiles, no added sprites. Original `$1929` confirms
  the 120-tick non-final-life wait. The selected adapter freezes movement and
  animation, hides only player SAT slots, restores terrain on completion and
  waits for diagnostic Home; gameplay life loss/restart remains stage 07.
  Its nine effect/restore jobs share the existing 22-command budget. Keyboard
  contact, 40 paused refreshes, all 121 hold states and Home reset pass with
  11 exact full RGB images, both with and without HUD. Standard movement/cache
  checks pass 1,600 states in each configuration (34/36 full RGB images).
  Death-route main maximum 19.938 ms, footer maximum 20.305 ms, GPU maximum 22;
  adapter elapsed maximum 978 cycles (includes interrupts). Evidence:
  `references/build/issue11-r03-{v2,no-hud-v2}-{death,player}-check/report.json`.
- Stage 04: accepted as `11-r04-flags-v7` / `11-r04-no-hud-v7`. Original
  geometry/order/type and one-time cell/list clearing pass 10,931 independent
  original-Z80 boundary/persistence cases. A keyboard-only 286-cell route collects
  all ten flags, revisits the first after eviction and resets with Home: 3,139
  live collection observations match the original, 2,642 complete visible-cache
  states and 12 full RGB images pass in each HUD configuration. Collection
  removes both bitmap and radar flags without allocating sprites. The score,
  lucky fuel reward, fuel, remaining lives and enemy point still use fixtures.
  The first candidate regressed to 23.467 ms; the measured radar-work reservation
  and smaller invisible cache halo fix is documented in
  [the performance report](flag-collection-performance-fix.md). The visible
  viewport/assets/coordinates are unchanged. Standard 1,600-state regressions
  pass (34/35 RGB), plus the existing death regression (11 RGB). Main maximum
  20.159 ms on the standard route, 19.938 ms on the all-flag route; GPU maximum
  20. Stage 00 still rebuilds byte-identically to its original reference.
- Stage 05: accepted as `11-r05-score-v5` / `11-r05-no-hud-v5`. Live ordinal
  flag points, the special multiplier, original digit carries, high score and
  source bonus-life accounting replace the score fixture. Lucky flag base points
  and its pending fuel request are retained; stage 06 owns the fuel conversion.
  The initial score loop failed at 22.533 ms. The bounded adapter and numeric
  HUD reservations pass without changing timing gates; see
  [the measured fix](score-performance-fix.md). All 1,278 independent original
  score/high-score/life-accounting cases match exact packets and pending HUD
  digits. Standard routes pass 1,600 states each (32/35 RGB), all-flag routes
  pass 2,642 cache states and 12 RGB each with independent live point totals,
  and the death regression passes 11 RGB. Main maximum is 20.136 ms on the
  standard route and 20.030 ms on the all-flag route. V5 has identical cartridge
  bytes to these V4 RGB/proof runs; its fresh profiling trace covers every call.
  The full suite passes 288 tests. Fuel, life loss/restart and enemies are pending.
- Stage 06: accepted as `11-r06-fuel-v6` / `11-r06-no-hud-v6`. Original
  consumption/gauge shadow and empty-fuel deceleration are selected routines;
  an explicit fresh active clock replaces boot/IRQ phases. The bounded lucky
  adapter preserves all four round-dependent conversion branches, per-tick
  score/life checks, the last-flag exclusion and unchanged restored fuel.
  Independent original component proof: 91 cases, 9,982 exact ticks, maximum
  6,238 cycles. Both standard routes pass 1,600 movement/cache states and 37/39
  full RGB images, including fuel clock, pause and Home checks. Both all-flag
  routes pass 2,786 cache states, 12 RGB and 177 exact original lucky ticks from
  the actual event state. Death/pause/reset passes 10 RGB each; 512 grouped
  death-copy cases cover all horizontal cache positions, vertical wrap, and
  small budgets with unchanged surrounding canaries. All 291 tests pass.
  Initial refresh/cache/death-image regressions and their measured fixes are in
  [the fuel report](fuel-performance-fix.md). Main maximum: 20.247 ms standard,
  20.334 ms all flags; GPU maximum 19. No viewport, original pixel, sprite count,
  CPU clock or timing tolerance change. Life/enemy fixtures remain; source
  post-flag difficulty parameter dispatch is explicitly deferred.
- Stage 07: accepted as `11-r07-lives-v4` / `11-r07-no-hud-v4`. Selected
  original life decrement/refill/car initialization plus a bounded same-round
  reload retain score, high score and cleared flags. Current-life ordinal and
  multiplier reset; actual spare cars replace the life fixture. Independent
  original proof: 48 exact loss/wait/restart/next-flag cases. Both three-life
  keyboard routes pass 1,289 visible-cache states / 19 full RGB, 40 paused
  refreshes, 120/120/96 holds, stopped zero-life input and Home. Both standard
  routes pass 1,600 states / 37 and 39 RGB; the complete ten-flag route passes
  2,786 cache states / 12 RGB. Main maximum 20.304 ms standard, 19.938 ms life
  route; GPU maximum 19. Bounded reloads take 714 ms HUD-on / 669 ms HUD-off,
  explicitly excluded with two warm-up frames from normal driving. All 295
  tests pass. V4 ROM bytes equal the V2/V3 proof candidates. See
  [the plan and evidence](lives-restart-plan.md). Game-over/credit presentation
  and source difficulty/enemy dispatch remain pending.
- Stages 08–11: pending.
- Manual feedback: the user confirmed normal speed and right-edge graphics for
  the stage 02 rock/contact checkpoint. Later stages have emulator evidence;
  they have not been labelled manually approved.
- Physical MSX/controller validation remains unmeasured until performed.

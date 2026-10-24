# Issue 11: bounded first-stage completion

The agreed playable segment covers the initial normal round. Later rounds,
challenge stages and two-player turns remain outside this delivery. Do not
increment the round counter and silently replay the first board as a new round.
Preserve the current smoke checkpoint while implementing these steps.

## Validated session candidate

Stage12 candidate `issue11-r12-smoke-irq-v260/raster-scroll.rom` is the current
HUD/session revision. The previous v229/v221 evidence below remains archived;
the new revision's evidence is listed separately under Smoke header regression.
It uses a 1 MiB ASCII16 cartridge, standard 3,579,545 Hz Z80 and 50 Hz display
on openMSX21.0 `Panasonic_FS-A1WSX_NR128`, with real VDP timing and sprite limits.
MAME0.289 independently executes the original routines; sjasmplus1.24.0 assembles
the authored adapter. Contributor ROMs/BIOS and every generated game payload
remain ignored below `references/`; no ROM download or distribution is required.

Controls: **5** inserts credit, **1** starts a new single-player game, arrows or
joystick1 steer, Space/Ctrl or triggerA releases smoke, P pauses, and Home resets
the current development run. Enter's old fixture toggle is disabled. Credits
saturate at255 and decrement once per start. A new game retains the high score,
starts with three lives, resets flags/score/fuel and reloads the original initial
normal round. That round has no rocks and keeps one enemy. The separate Stage10
rock fixture remains available. Completing the round shows its final score and
an explicit clear screen; starting again begins a **new game**. Later rounds,
challenge rounds, two-player turns and arcade foreground/boot diagnostics are
outside this bounded delivery. The sound adapter is still silent.

Original scenery colors, asset dimensions and complete car drawings are
preserved. The full sprite HUD/radar is enabled during gameplay. Session screens
disable sprites and maze raster splits, preventing radar/fuel leakage. Their
text uses original 8x8 glyphs at1:1 scale. No flicker/blitter experiment is active.

Native simulation normally retains its original16.5ms tick. When an unfinished
hidden cache job approaches the viewport, motion and **all native clocks** hold
for a refresh while rendering catches up. This is a declared timing concession,
not a graphics reduction or collision/rule rewrite. The real session route held
19/3,576 observed refreshes (0.53%), at most one consecutively; motion and native
tick-counter freeze are independently checked. Main-start median19.937ms,
p9520.857ms, maximum39.873ms still fail exact cadence. The user explicitly permits
small measured timing concessions; exact-cadence diagnostics remain failing.
The matched rock/smoke stress fixture held41/1,812 refreshes (2.26%), at most3.

| Verification | Evidence and result |
| --- | --- |
| Real keyboard session and first-round completion | `issue11-r12-route-v222`: 3,576 complete visible-cache states,44 full maze RGB images,2 full menu RGB images,197 exact source bonus ticks, two40-refresh pauses, two actual life losses, clear menu and real credit/start into a fresh game; no guest state writes |
| UI edge cases | `issue11-r12-ui-proof-v222`:5 full RGB images; no-credit start ignored, held coin counted once, live-game credit,255 saturation and record123450 retained. Terminal/high-score edge states are explicitly seeded; this component is separate from the real keyboard route |
| Actual final life and game over | `issue11-r12-natural-over-v231`: real keyboard enemy pursuit produces all3 deaths, lives2/1/0 and every original hold tick0..120/120/96, then the actual game-over screen. Subsequent high-score/saturation/clear edge cases remain explicitly seeded UI components |
| Real emulated joystick | `issue11-r12-input-proof-v225`:144 peripheral/output/keyboard cases plus9 complete4098-byte native gameplay frames equal to their keyboard counterparts; physical controller testing is not claimed |
| Original smoke | `issue11-r12-smoke-proof-v226`:1,254 exact independent source cases |
| Cloud/flag ownership and queue | `issue11-r12-smoke-flags-v226`:490 original overlaps,40 publication-row canaries,960 queue wrap/dedup/full cases |
| Original completion | `issue11-r12-completion-proof-v226`:64 cases,2,842 exact yielded source ticks |
| Original post-flag/per-life parameters | `issue11-r12-parameters-proof-v226`:1,330 exact cases |
| GPU copy boundaries | `issue11-r12-copy-proof-v227`:512 complete VRAM/cache-wrap canaries |
| Repeated firing, rocks and restart | Stage10 `issue11-r10-stress-v207`:1,812 cache states,59 full RGB images,1,984 exact live source smoke calls,136 stun ticks, pause/death/restart/Home |
| Authored regression suite |336 tests pass, including missed-header and S-blink oracle regressions; `git diff --check` passes |

Each evidence name is a local directory below `references/build/`, with sealed
manifest/report files. Fresh Stage8/9 builds remain byte-identical to their
accepted references. The user tested and approved v260 on 2026-10-24 and asked
to proceed with delivery. Plain `make build` now selects Stage12 and reproduces
the approved cartridge; the prior v115 reference remains available separately.
The archived evidence below distinguishes each ROM revision explicitly.

Final delivery verification after promotion: all 337 authored tests pass;
plain `make build` produces the exact approved v260 ROM. Default/LATEST hashes,
the sealed build manifest, 167 Python syntax parses and whitespace checks pass.
`11-r12-approved-v260` preserves the approved ROM as a named reference.

## Smoke header regression

Current checkpoint: `11-r12-smoke-irq-v260`, SHA-256
`9771e72b394f5a3c66018f638318caa5e4e060eed85c2dcc27d5f5328f5efc12`.
The user still saw title-page remnants while releasing smoke. Repeated real
Space input on v255 reproduces 46 missed header reservations across 16,000
refreshes (`issue11-r12-smoke-header-baseline-v256`); the longest reservation
lasts 26.336 ms instead of completing within its own refresh. IRQ traces locate
the delay in smoke publication bookkeeping, queue selection and the final
foreground RAM checks after VDP work.

These RAM paths now service interrupts. VDP command/status/address transactions
remain protected. The original pixels, clock frequencies, viewport, full HUD,
sprite drawings and 20-entry allocation remain unchanged. A smoke/death overlap
also exposed a grouped cloud copy overwriting the explosion; while an explosion
is active, smoke rows use the existing per-tile source selection instead. The
multi-key smoke route exposed a corner guard restoring an obsolete perpendicular
centering velocity; retain that native decision alongside primary steering when
rejecting only the unsafe position/camera change.

The regression runs 16,000 keyboard refreshes with repeated Space firing and
checks every header reservation. Its first 1,200 refreshes also capture complete
visible-cache states. Full RGB captures require a settled smoke publication,
because cloud rows intentionally publish over multiple refreshes; transient
row appearance is not claimed to be atomic. Header checks still cover all busy
and transitional refreshes, with standard guest Z80/VDP timing and real sprite
limits. The frontend runs throttled while screenshots are collected, then
continues the remaining hardware-timed stress without frontend rendering.

Final smoke proof `issue11-r12-smoke-settled-proof-v260` passes 477 placements,
15,973 original-maze contact checks, 38 explicit newest-direction checks and
16,060 header reservations (maximum 6.399 ms), with no missed reservation. It
checks 1,193 complete visible-cache states and 95 complete RGB images, including
88 with published smoke. Nine games and 6,590 distinct later poses confirm
continued movement. The separate no-smoke-input steering run still has its HUD
enabled and passes another 16,000 refreshes, 13,937 contact checks and 15,862
header reservations (`issue11-r12-steering-proof-v260`).

Reproduce with a fresh output directory:

```sh
.venv/bin/python -B scripts/raster_scroll.py verify-steering --smoke-stress --rom references/build/issue11-r12-smoke-irq-v260/raster-scroll.rom --output references/build/my-smoke-header-check
```

The full first-round route on v260 passes 3,606 visible-cache states, 44 gameplay
RGB images, two menu images and 197 exact original completion ticks. All 3,607
header reservations pass (maximum 6.397 ms). The separate L route passes 848 cache
states, 329 RGB images, 297 original converter ticks and a one-refresh gauge
restoration. It observes 95 post-bonus refreshes; all 847 header reservations
pass. Evidence: `issue11-r12-smoke-full-route-v260` and
`issue11-r12-smoke-lucky-proof-v260`.

The full route holds native clocks for 54/3,606 refreshes (1.50%), at most two
consecutively. Main median is 19.937 ms, p95 20.848 ms and maximum 38.885 ms;
the radar backlog stays within 14 of its 16-refresh limit. Exact arcade cadence
remains unclaimed. Twenty focused unit tests and Python syntax checks pass.

## Previous input and presentation regressions

Previous checkpoint: `11-r12-input-fuel-v255`, SHA-256
`df372f1a2ca35c1d813f3fd8e089c8a06d250910e60e747510b0420097a528f8`.
The user reported L title-page remnants, a gauge that did not restore promptly,
and wall penetration while holding two arrows. The previous L reproduction stopped
at the native conversion's completion and did not prove the subsequent HUD refill.

The input gate now accepts one direction, giving a new edge priority over a held
direction. New Rally-X inherits the four-way Rally-X input definitions in the
[MAME driver](https://github.com/mamedev/mame/blob/master/src/mame/namco/rallyx.cpp).
Rapid reversals also need a position check: after rollover or when both signed
offsets approach an inside corner, save 44 bytes of motion/camera state and check
the original wall map. Reject an invalid position while retaining the new steering
direction, fuel, score, enemies and clocks. A test that checks continuing movement
prevents replacing penetration with a frozen corner. This is a bounded adapter
for keyboard input rather than a rewrite of the original steering routines.

The old fuel upload required raster phase 0 and could starve for more than 95
refreshes after native fuel was restored. Prepare a complete 128-byte payload in
RAM at D180, then publish it on VBlank without mapper changes. The ISR consumes a
ready flag only after the RAM copy finishes. The L rule still restores the amount
saved at pickup, as verified against the original converter; it does not invent
additional fuel. The displayed bar now follows the restored amount after one refresh.

Header traces identified long DI spans in numeric RAM publication during the bonus
and in early cache/input preparation. These producers now service interrupts;
cache calculation runs outside the short atomic scroll snapshot. VDP latch/data
transactions keep their existing protection. Visible line6/9 latches and original
scenery/car pixels remain unchanged. The outlined life icon, red warning, S blink,
Space smoke/P pause, full HUD and 20-slot allocation remain.

| Final v255 validation | Evidence and result |
| --- | --- |
| Multi-key movement | `issue11-r12-steering-proof-v255`: 16,000 keyboard refreshes, 12,982 original-maze contact checks, 38 explicit newest-direction checks, 21 played games, 542 protected steps and 5,105 distinct poses after refresh 5,000; no wall-center entry or frozen corner |
| Extended L route | `issue11-r12-lucky-after-proof-v255`: 297 exact original converter ticks, 848 complete cache states, 329 full RGB images, 95 post-bonus observations and one-refresh gauge restoration; real keyboard input, no game-state writes |
| Header deadlines | Multi-key: 15,860 reservations, maximum 6.397 ms; L: 847, maximum 6.397 ms; full session: 3,612, maximum 6.398 ms; no missed refresh |
| Complete first round | `issue11-r12-full-route-v255`: 3,611 cache states, 44 gameplay RGB images, 2 menus, 197 original completion ticks, pause, clear and new-game reset |
| HUD/input | `issue11-r12-input-fuel-hud-v255`: 5 full RGB images and 128 live S refreshes; `issue11-r12-input-fuel-inputs-v255`: 144 peripheral cases and 9 complete native keyboard/joystick frame pairs |

Full-route median 19.937 ms, p95 20.845 ms, maximum 39.321 ms; cache holds 54/3,611
refreshes (1.50%), at most two consecutively. Radar backlog remains 14 against
the 16-refresh limit. Exact arcade cadence is still not claimed. The 337 authored
unit tests pass; fresh Stage8/9 ROMs remain byte-identical to accepted references.

Reproduce the added regressions with fresh output directories:

```sh
.venv/bin/python -B scripts/raster_scroll.py verify-steering --rom references/build/issue11-r12-input-fuel-v255/raster-scroll.rom --output references/build/my-steering-check
.venv/bin/python -B scripts/raster_scroll.py verify-lucky-route --rom references/build/issue11-r12-input-fuel-v255/raster-scroll.rom --output references/build/my-lucky-check
```

## Preserved HUD/session adjustments

Previous checkpoint: `11-r12-life-outline-v243`, SHA-256
`1af1eef410b24ff5ab0adec26bd7740b5248d0630b0b79ca97d183bf2c049598`.
This revision restores only the life icon's black outline after the user's
decision to retain it. Its five-image HUD check is `issue11-r12-life-outline-proof-v243`;
the complete gameplay and input evidence below belongs to the preceding v242.
The gauge is red below6 of60 native units, yellow at exactly10%, and its pump
stays white. Fuel patterns publish before body scanout to avoid partial columns.
The S flag alternates every32 gameplay refreshes using its existing radar cell;
ordinary flags stay visible, and collection still removes S through the existing
HUD API. Pause freezes the blink clock. Space releases smoke, P pauses, and Ctrl
remains a smoke alias. The life icon uses yellow and black planes plus its count
digit. These three footer slots are reused by the fuel gauge during the body,
so retaining the outline preserves the20-slot peak and twelve free entries.

The original L-first route exposed two late header interrupts that programmed
the line6 comparator after its deadline, waiting until the following frame and
showing remnants of the title page. Reserve the header at line1 while keeping
the same visible line6/9 latches. Flag-row RAM preparation now services pending
interrupts before its atomic command transactions. Original scenery pixels and
car drawings remain unchanged.

| Current revision verification | Evidence and result |
| --- | --- |
| HUD and controls | `issue11-r12-hud-alerts-proof-v242`:5 full RGB images at60/6/5/0/60 fuel units,128 live S refreshes, ordinary flags retained, real Space smoke and P pause; fuel boundary inputs are explicitly seeded |
| Full keyboard session | `issue11-r12-hud-route-v242`:3,598 complete cache states,44 gameplay RGB images,2 menus,197 exact original bonus ticks, two40-refresh pauses, clear/new-game reset; no guest state writes |
| Header regression | The full route checks3,600 reservations, maximum6.409ms, without a missed refresh; the L-first reproduction has separate continuous video and sampled RGB evidence in `issue11-r12-lucky-proof-v242` |
| Input compatibility | `issue11-r12-hud-inputs-v242`:144 peripheral cases and9 complete native gameplay-frame pairs; keyboard counterparts use Space for smoke |
| Preserved checkpoints | Fresh Stage8 and Stage9 builds remain byte-identical to their accepted ROMs |

Current full-route timing: median19.937ms, p9520.833ms, maximum38.637ms.
Cache backpressure holds41/3,598 refreshes (1.14%), at most two consecutively.
The radar backlog drains within14 refreshes against the existing16-refresh limit.
Exact arcade cadence remains unaccepted; this is the same declared timing-concession
policy as the previous candidate, with original graphics and all native clocks held
together under cache pressure.

Reproduce with `make build STAGE=12`. Verification commands require fresh output
directories and the contributor-supplied local ROM/BIOS inputs:

```sh
.venv/bin/python -B scripts/raster_scroll.py verify-completion-route --rom references/build/issue11-r12-hud-lucky-v242/raster-scroll.rom --output references/build/my-session-route
.venv/bin/python -B scripts/raster_scroll.py verify-hud-alerts --rom references/build/issue11-r12-hud-lucky-v242/raster-scroll.rom --output references/build/my-hud-alerts
.venv/bin/python -B scripts/raster_scroll.py verify-session --rom references/build/issue11-r12-hud-lucky-v242/raster-scroll.rom --output references/build/my-session-ui
.venv/bin/python -B scripts/raster_scroll.py verify-session-inputs --rom references/build/issue11-r12-hud-lucky-v242/raster-scroll.rom --output references/build/my-session-inputs
```

`make build STAGE=12` publishes the newly built ROM as default/latest. To build
without replacing the default cartridge, run:

```sh
.venv/bin/python -B scripts/raster_scroll.py build --stage 12 --output references/build/my-session-build
```

## Implementation sequence

1. Independently reproduce original `$1fa9` remaining-fuel conversion as a
   resumable adapter. Unlike the lucky flag, completion consumes fuel to zero
   and does not restore it. Preserve all four round-dependent decrement/award
   branches, including the second ten points after HALT in rounds 9–12, the
   five-tick chunk wait, digit carries, high score and bonus lives. Compare
   every yielded tick against independently executed original code.
2. Detect the tenth flag only after its score and visible flag repair finish.
   Freeze movement/contact/consumption, retain the source counter phase
   (three to the next multiple of 64), then run the bounded completion bonus.
   Pause must freeze this state. The silent port does not wait on unimplemented
   sound completion; declare that temporal adaptation explicitly.
3. Present an explicit end-of-segment state. Add bounded credit/single-player
   start and game-over transitions using the original initial state and life
   rules. Preserve high score across games. Do not restart the full arcade
   boot diagnostics, foreground loop or renderer.
4. Validate completion, bonus, paused transitions, new-game reset and game
   over with the HUD enabled. Replay the unchanged driving/smoke checks,
   original input/source guards and standard-clock timing. Publish a testable
   checkpoint after each functional addition. Keep measured timing failures
   and unimplemented paths explicit; they do not become an acceptance pass.

The source parameter routine `$1b1f` keeps one enemy throughout the initial
normal round, but changes movement parameters at collection thresholds.
The isolated1,330-case proof and Stage11/12 integration now cover this dispatch;
fixed population stress checkpoints remain separate from those game rules.

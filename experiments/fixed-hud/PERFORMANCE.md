# Performance policy and cycle ledger

Performance is the priority, with approximately 30 presented gameplay frames per
second as the target. The user has final acceptance of every visual concession
and perceptual timing change. Existing SCREEN 4 and right-edge reductions remain
authorized for this laboratory only. This policy does not authorize further
graphical reductions in active gameplay.

## Current playable-stage measurements

`make profile-experiments` now profiles the complete keyboard-only first stage.
The original camera-only profile below remains available as `profile-hud-lab`.
The current comparison is recorded in `references/experiments/stage-one/optimization-comparison.json`
and `outputs/first-stage/cycle-budget.xlsx`, including active-only FPS and tails.
See [FIRST-STAGE.md](FIRST-STAGE.md) for scope and remaining limits.

## Reproduce the free-camera measurements

```sh
gnumake profile-hud-lab
```

This rebuilds the laboratory ROM and runs an isolated openMSX continuous-key
workload. It records every measured call in `calls.tsv`, each presentation in
`frames.tsv`, a control run in `control-frames.tsv`, and the cycle ledger in
`summary.json`. Outputs are under the ignored
`references/experiments/fixed-hud/profile-*` directory; `last-profile.txt` points
to the latest successful run. No guest instructions or ROM bytes are patched.

`workbook.mjs` exports the summary as an editable Excel workbook using
`@oai/artifact-tool`:

```sh
node workbook.mjs /absolute/path/to/summary.json /absolute/path/to/output-directory
```

The package must be installed in that script's Node module resolution path.
The workbook contains Budget, Routines, Frames and Sources sheets, with formulas
for milliseconds, utilization, timing margins and summary results. Its blue
input cells distinguish planning inputs from measured results. The amber
5,000-cycle reserve is explicitly provisional.

## Keep the budgets distinct

The checked-in timing model (`scripts/msx/inputs.py`) uses a 3,579,545 Hz Z80
clock and 228 CPU clock periods per scanline. The laboratory sets R9=$82 and
currently runs at nominal 50 Hz. The following are clock-budget calculations,
not measurements of an available VBlank service window:

| Budget | CPU cycles | Time |
| --- | ---: | ---: |
| Current 313-line refresh | 71,364 | 19.937 ms |
| Proposed 262-line refresh | 59,736 | 16.688 ms |
| Two 262-line refreshes | 119,472 | 33.376 ms |
| Provisional VBlank work reserve | 5,000 | 1.397 ms |
| Exactly 30 FPS presentation interval | 119,318.17 | 33.333 ms |

The user's “5000 mil” is provisionally interpreted as **5,000 cycles**. Five
million cycles would take approximately 1.397 seconds at this clock. The actual
usable VBlank deadline, interrupt-entry latency, other interrupt work and safety
margin still need a dedicated scanline/deadline measurement. Do not equate the
full refresh budget with VBlank time.

Near-30 FPS can use two refreshes at nominal 60 Hz, but a single drawing phase
may still have a tighter one-refresh budget. Moving work into a second refresh
requires an explicit scheduler and a complete logic/audio/input budget. This
measurement does not switch the ROM to 60 Hz or establish production-game costs.

## Baseline measured on 2026-10-27

Source: `references/experiments/fixed-hud/profile-m9umw_8l/summary.json`.
ROM SHA-256:
`e20f246393198bb80b63b0d85d3b49eb1c3d6da8dca61ca0835d2325608e2843`.
Machine: Panasonic_FS-A1WSX_NR128, openMSX 21.0, standard Z80 clock, real VDP
limits. HUD remains enabled. Frames 5..312 exercise diagonal, horizontal and
vertical key movement, normal/Shift speed, and stationary frames.

| Measurement | Result |
| --- | ---: |
| Measured presentations | 308 |
| Tracked routines / hooks | 18 |
| Recorded routine calls | 11,766 |
| Active work mean / maximum | 20.565 / 37.116 ms |
| Active work P95 (nearest rank) | 31.961 ms |
| Presentation interval mean | 30.811 ms |
| Average presentation rate | 32.456 FPS |
| One-refresh / two-refresh presentations | 140 / 168 |
| Work exceeding a 59,736-cycle drawing budget | 201 / 308 |
| Atomic register commit mean / maximum | 413 / 417 cycles |
| VBlank ISR body per call | 139 cycles |

Average presentation rate is not stable 30 FPS: the current 50 Hz lab alternates
between one and two refreshes. Its maximum active work also exceeds a two-refresh
60 Hz budget. Earlier README timings measured a different route/sample boundary
and the rendering segment; this ledger includes input, render, commit and loop
overhead, with synchronization waiting separated.

The largest measured self costs per presentation are `hud_upload` (21,069 cycles),
`Ring_UploadNames` (17,708), and `upload` (12,461). These are disjoint self costs,
not inclusive parent costs. They identify optimization candidates; no claimed
speedup has been implemented or measured in this task.

## Measurement contract

- Use emulated elapsed seconds multiplied by the configured CPU clock. Retain
  fractional values in raw files; display rounded cycles in the workbook.
- Match routine entries and returns by both PC and SP. Handle tail calls and
  interrupt returns before a resumed routine entry. Inclusive costs contain
  descendants; self costs subtract measured descendants. Untracked helpers are
  charged to the nearest measured ancestor.
- Charge CALL instruction costs to the caller. Entry-through-return spans
  include the routine's return instruction. ISR body costs exclude hardware
  interrupt entry and the IM2 vector jump, which remain in the interrupted phase.
- `wait_blank` includes HALT and its wake-up interrupt. Active work is input +
  render + commit + loop overhead, excluding that complete synchronization span.
  It is not a claim about useful instructions executed while halted.
- Check that all self costs plus loop overhead reconcile to every frame total;
  never add inclusive parent and child spans. Assert one input/render/wait/commit
  span per presentation and exercise every advertised routine.
- Run the same key workload with routine breakpoints removed. All 308 camera and
  elapsed-tick states agree; total elapsed time agrees within 0.01 cycle. Individual
  frame observation boundaries differ by at most five cycles. Treat differences
  at that scale as measurement sensitivity, not optimization gains.
- Keep ROM hash, emulator, machine, clock, video mode and workload with results.
  This is a free-camera rendering laboratory. Original game logic, enemy AI,
  collisions, sound and flag capture are not exercised. Physical hardware has
  not been validated.

## Movement breakdown

```sh
gnumake profile-movement-experiments
```

This adds a separate 480-presentation workload: horizontal and vertical movement
in both directions, normal/Shift speed, then 32 released-key frames. The first
four startup presentations are excluded. Every moving sample is checked for
correct displacement per elapsed VBlank, without a clamp or diagonal movement.
The normal-speed routes cover all eight fine phases on both axes.

Source: `references/experiments/fixed-hud/profile-yu8xr8df/summary.json`.
The ROM hash is unchanged from the baseline above. No rendering or movement
behavior is modified. The run records 15,122 calls across the same 18 routines;
the control run matches all 480 states and total time, with at most five cycles
of per-presentation observation jitter.

| Axis | Speed | Camera transition | Samples | Mean cycles | Mean ms | P95 ms | Max ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Horizontal | Normal | Fine only | 99 | 74,681 | 20.863 | 23.981 | 24.558 |
| Horizontal | Normal | Tile crossing | 29 | 98,390 | 27.487 | 30.078 | 30.084 |
| Horizontal | Shift | Fine only | 56 | 68,829 | 19.228 | 25.500 | 25.564 |
| Horizontal | Shift | Tile crossing | 40 | 91,770 | 25.637 | 31.908 | 35.882 |
| Vertical | Normal | Fine only | 110 | 53,867 | 15.049 | 15.670 | 15.679 |
| Vertical | Normal | Tile crossing | 18 | 71,951 | 20.101 | 27.354 | 27.354 |
| Vertical | Shift | Fine only | 68 | 55,590 | 15.530 | 16.046 | 24.195 |
| Vertical | Shift | Tile crossing | 28 | 70,031 | 19.564 | 20.379 | 20.379 |
| Stationary | None | No movement | 32 | 28,727 | 8.025 | 7.783 | 15.667 |

The crossing classifier compares the integer world tile coordinates before and
after input, rather than testing whether the final fine phase equals zero.
Reverse movement can cross from phase 0 to 7; elapsed ticks can also skip phases.
Both directions are pooled in this table. These groups visit different positions
and back-buffer states, so their differences are descriptive, not a controlled
measurement of a single instruction or of an eighth-pixel surcharge.

`Ring_Prepare` takes 212 cycles when no world-ring update is required. In these
normal-speed groups it averages 25,170 cycles at horizontal crossings and 16,044
at vertical crossings. HUD uploads and name-table updates remain substantial
even between crossings. A reused back table can require a row or column update
after the camera's crossing frame, so `Frames` records camera crossing and
actual name-strip call count separately. The `Movement` sheet includes all eight
normal-speed phases and disjoint per-group world/HUD/name routine costs.

Total active work averages 18.422 ms and reaches 35.882 ms. 246/480 presentations
exceed the proposed 59,736-cycle drawing interval; one exceeds the 119,472-cycle
two-refresh interval. The highest-cost sample is frame 276, horizontal Shift,
camera x311 to x313. It uses 128,440 active cycles: its world-ring preparation
accounts for 38,789, HUD upload 22,588 and name-table publication 30,511 cycles.
Those three disjoint children are only part of the complete rendering cost.

This route presents 289 frames in one refresh and 191 in two, averaging 35.881
presentations/second. It is not a stable-rate claim or a speedup over the earlier
mixed route. Stationary statistics include the first released-key frames while
the alternate tables settle. The existing hardware/production-game limitations
continue to apply.

## Wider-HUD baseline

The user explicitly authorized an eight-pixel fixed left mask for this laboratory
to use the former right inset. The HUD content spans x208..255: six-digit scores,
a 48-pixel fuel bar and a 48-pixel radar panel. The radar projection expands from
24 to 32 horizontal pixels. Original glyphs remain 8x8, camera/world rules remain
unchanged and the right-edge scenery simplification remains in force.

R26/R27 scrolling replaces R18 adjustment. The first name-table column is masked
by hardware and stores the seventh compensated HUD cell for right-edge wrapping.
The old left-edge atlas uploads are no longer needed. No sprites or VDP copy
commands are introduced.

ROM SHA-256:
`dd1c7dd5ac583ba2bd6d66c3843fc2955fe5665a819aa573c441a7829c168d17`.
The isolated branch is `codex/fixed-hud-lab`, based on `main`, with no audio branch
commits. Its build reproduces the same cartridge and measurements using the
main-branch helper modules.

The 480-presentation movement route records 13,625 calls. Mean active work is
16.528 ms and maximum is 29.289 ms. Of the 480 samples, 219 exceed the proposed
59,736-cycle one-refresh drawing budget and none exceeds 119,472 cycles. The
guest-time/state control check passes. Normal-speed means are 18.123/26.698 ms
for horizontal fine/crossing groups and 13.220/17.865 ms vertically. Presentation
still alternates between one and two 50 Hz refreshes: 381 and 99 samples.

The previous movement route measured 18.422 ms mean and 35.882 ms maximum. Both
runs use the same key schedule, but elapsed-tick movement visits different world
positions when cadence changes. Do not interpret this as a phase-matched causal
measurement of the wider HUD alone, a stable 30 FPS guarantee, or a complete
production-game budget. The existing physical-hardware/AI/audio limitations apply.

All 14 keyboard images, 225 matrix images and 305 continuous-route captures pass.
The independent contract also checks the fixed left mask in all eight phases.
All 418 lossless-video frames after oracle coverage starts match complete states;
there are no mixed frames or strict VRAM timing violations.

## Current RND and life-icon footer

The radar moves up eight pixels to y68..179 without changing height. The native
16x16 padded extra-life car mask is composited at y184 with an 11-pixel stride;
only transparent padding overlaps, preserving every original opaque pixel at
1:1 scale. At most four icons are displayed. `RND` and its right-aligned number
occupy y204..211, the last eight screen lines.

`hud.py` saturates presentation values at round 99, high score/score 999999 and
four life icons. Five synthetic unit tests cover overflow, values below limits,
right alignment, radar position and complete unscaled car silhouettes. The native
above-limit cartridge also passes 14 exact full-frame keyboard comparisons:
scores 1000000/1000001, round 100 and lives 9 display as 999999/999999, 99 and four
cars (`probe-ccl38m6q`; retained with cartridge in `footer-cap-evidence`).
The free-camera lab has build-time counters; it does not introduce or change
production gameplay counter hooks. Formatting runs offline. Runtime cost changes
come from the new pixel patterns and their transfers.

The extra glyphs need 46..87 HUD characters. Their allocation expands to slots
64..191 using space vacated by the old left compensation. Scene-edge dictionaries
move to 192..219 and 220..247; the radar marker moves to 248. All 4,096 HUD phase
transitions pass poisoned-memory reconstruction. The cartridge uses 213 ASCII16
banks (3,489,792 bytes), below the 256-bank mapper limit.

Default ROM SHA-256:
`e1d5a44c743b62241351c44959fd047a65f0fbe230f1b49a4f1006c6c40c64cc`.
The 480-presentation movement ledger (`profile-_xkiwshs`) records 13,994 routine
calls: mean active work 17.946 ms, maximum 31.660 ms. 290 samples exceed 59,736
cycles; none exceeds 119,472. The control run matches all states and total guest
time. As before, these are free-camera laboratory costs at nominal 50 Hz, not
a complete game-loop budget or a stable 30 FPS claim.

The default keyboard/matrix/continuous image checks pass, including all 64 fine
phases, fixed left mask and right-edge policy. All 449 lossless-video frames after
oracle coverage starts match complete states, without mixed frames or strict
VRAM timing violations. Rebuilding defaults restores the exact cartridge hash.

## Bounded event scheduling

A brief flag-capture pause is a candidate for deliberately scheduling work at a
perceptually meaningful moment. The laboratory has no flag-capture gameplay hook,
so this remains a proposal with **unmeasured cost and duration**.

For any such experiment, record the event/hook owner, prerequisite, cycles per
call and maximum calls, deadline, pause duration in refreshes and milliseconds,
and what resumes afterward. Keep input handling and game-state transitions
consistent, do not count repeated work twice when events overlap, and define a
bounded fallback if work exceeds its allowance. Separate urgent VBlank writes
from inactive-buffer preparation that can run elsewhere. Preserve real hardware
limits and the HUD.

Deliver a testable build and a comparison showing the pause and its processing
benefit. The user decides whether its visual and gameplay effect is acceptable.
Do not use an event pause to hide continuing per-frame overload. No pause or
additional quality reduction is introduced by the profiler.

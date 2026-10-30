# Component and raster timing, 2026-10-28

The focused workbook is `docs/measurements/timing/archive/component-timing/component-timing.xlsx`, with
inspectable inputs in the adjacent `summary.json`. This supplements the existing
cycle-budget workbook. It does not replace its earlier optimization evidence.

The initial measurement (retained in baseline-697232c9.json) used ROM SHA256
`697232c9bb3711fdf7087fd6240c0539b072315c5461bf32e0814e4acdf72338`,
openMSX 21.0, Panasonic FS-A1WSX_NR128, Z80 3,579,545 Hz, nominal 60 Hz,
HUD enabled and hardware sprite limits enabled. Physical refresh is
59.922743 Hz. The three-enemy active presentation rate is 27.543138 FPS.
These are emulated guest timings, not physical hardware measurements. The
workbook now contains the HUD/sprite ROM measured at29.508353 FPS over908 active
frames, compared with the preceding late-frame ROM at29.183373 FPS over898 active
frames. Changes compares those two passes; see FIRST-STAGE.md for hashes.
The detailed numbers below describe the retained initial measurement.

The first worksheet, Schedule, centralizes presenter plus logic dependencies,
actual publication cadence, foreground deadline misses and disjoint self costs
conditioned on late frames. The nominal target is 29.97 FPS; this machine's
measured 59.922743 Hz refresh yields 29.961372 FPS at two refreshes per frame.
Deadline analysis uses the previous actual VBlank publication edge and the
current wait_blank entry, with native VDP frame/tick counters. It joins CPU and
raster samples only after checking identical camera coordinates and native-tick
counts for every active interval. It does not sum unrelated per-call P95 costs.

## Reproduce the observations

Run from this experiment worktree, with its existing Python environment:

```sh
.venv/bin/python src/toolchain/screen4/component_profile.py --bundle references/experiments/stage-one-3-enemies --route
.venv/bin/python src/toolchain/screen4/component_actor_profile.py --bundle references/experiments/stage-one-3-enemies --population 1 --route
.venv/bin/python src/toolchain/screen4/component_actor_profile.py --bundle references/experiments/stage-one-3-enemies --population 2 --route
.venv/bin/python src/toolchain/screen4/component_actor_profile.py --bundle references/experiments/stage-one-3-enemies --route
.venv/bin/python src/screen4/raster_phase_profile.py
```

Each command prints its evidence directory. Pass those directories to
`component_report.py --profile <fine-profile> --raster <raster-run> --actors
<one-enemy-run> <two-enemy-run> <three-enemy-run> --out
outputs/component-timing/summary.json`. Run `component_workbook.mjs` with the
bundled artifact-tool runtime to author the workbook from that JSON.

The corrected initial fine profile is
`stage-one-3-enemies/baseline-697232c9/profile-route-p4u5xmtu`;
the raster run is `raster-phase-6yk72qf0`; actor runs are
`actor-components-697232c9/profile-route-88ba33qx`,
`actor-components-697232c9/profile-route-xg5rywy3` and
`actor-components-697232c9/profile-route-5tcizv0e`, all under ignored
`references/experiments/`. ROM copies, native data and detailed traces stay there.
The current fine profile is `stage-one-3-enemies/profile-route-v5upa8zj`;
its raster run is `raster-phase-617omwck`, with actors under
`event-components-299b5380`. The comparison fine profile is
`stage-one-3-enemies/baseline-12e32699/profile-route-xpxbz7q0`, raster
`raster-phase-hr0k7264`, actors `event-components-12e32699`.
Both fine profiles now explicitly track smoke-cache rebuilding, square/cell
patches, restoration and dirty marking, making their self-owner ranking
comparable. Both also include the separately
instrumented boundary uploader and dirty-name planner. Component aggregation
rejects requested owners that were not instrumented, rather than treating an
unmeasured routine as zero cost.

The current Schedule also retains isolated old/new worker costs for smoke,
metadata rebuilding and square overlays, with proof paths in Inputs. These
explain the optimization; they remain charged to their runtime parents. Do not
add them again. Boundary encoding preserves every decoded pixel while retaining
row color bytes across fine-X phases; its payload comparison is a transfer-size
diagnostic, not a matched FPS estimate. Current late publication is38/908 versus
54/898 before. Nominal29.97 FPS remains a target; P95 interval is34.595ms.
Current isolated comparisons focus on HUD transfers and sprite preparation,
including warm/animated/interior/clipped/sentinel cases. They are already charged
inside their runtime parents. The new allocation/program tradeoff is+864KiB ROM
and no new RAM. Page2 entry probes check immutable mapper-bank prefixes to avoid
counting compiled HUD instructions as native game routines.

The Raster sheet includes a calculated50Hz comparison. Its313 lines give19.47%
more cycles per refresh, with the same cycles per second. Two-refresh cadence
would be25.079FPS; near30 requires uneven presentation and adjusted native timing.
No50Hz ROM or PAL runtime measurement is claimed.

## Ownership and workload

- Component timing uses matched PC/SP entry/return spans, including tail calls
  and interrupt returns. An uninstrumented control retains the same observed
  guest state and timing, allowing at most 5.01 cycles of breakpoint observation
  jitter. The fine three-enemy profile covers 848 active frames.
- One/two-enemy diagnostics change only the active population count in RAM on
  the same ROM. They preserve initialized native descriptors, AI, movement,
  graphics and audio. Counts are checked at every recorded call and both frame
  endpoints. Their active populations cover 2,117 and 1,977 frames respectively;
  their routes differ as gameplay progresses. Their differences are not matched
  marginal estimates of the cost of adding one enemy.
- Player/enemy graphics mean actual `GS_PrepareActor` calls, including dirty
  uploads. The enemy totals sum observed calls in each frame. Shared sprite
  publication, actor conversion, collision passes and native motion remain
  separately identified. The original native movement dispatcher is a loop with
  tail transfers, so these probes do not claim a complete isolated per-car cost.
- Map timing combines disjoint ring preparation, overlays, terrain names/tiles
  and dirty planning. `hud_upload` tail-calls terrain/radar owners, so its
  inclusive time is not a pure HUD cost. Static HUD timing uses its self time
  plus the boundary packet and name helpers; dynamic HUD is measured separately.
- Music sequence, engine/effects and shared PSG register writes are separate.
  Parent audio time also includes divider, mapping and dispatch overhead.
- Horizontal/vertical groups use actual camera deltas and tile crossings during
  active gameplay. These are conditional drawing costs, not pure movement
  instruction costs or identical scene comparisons. Event workloads and elapsed
  native ticks can differ. Mixed-axis intervals are retained explicitly.
- Frame mean/p95/max are calculated from actual per-frame sums, including zero
  calls. Per-call distributions differ. Inclusive parents and children overlap;
  do not sum the workbook rows into a frame total. The Inputs ledger retains
  inclusive and self cycles, call counts, workload sizes and evidence paths.

## Scheduling and scanline coordinates

The loop runs `Game_Prepare -> render -> EI/HALT -> commit`. `Game_Frame`
consumes elapsed native ticks in the foreground, including input, audio and
game logic. The VBlank ISR acknowledges status and increments the clock; its
body costs 139 cycles and performs no game simulation. Preparation and transfers
to inactive tables continue during visible scanlines. Final publication is
synchronized to a fresh VBlank, with HUD and world sprite publication included.

Raster positions use the native `VDP_cycle_in_frame` / `VDP_frame_count`, not
absolute CPU time modulo a guessed epoch. Line zero is physical VSYNC; each
line is 1,368 VDP ticks = 228 CPU cycles. The visible picture starts at physical
line 32. On this R9=$80/R18=0 configuration, the VDP VR flag rises at line
244 + 33 2/3 cycles and falls at the following line 31 + 33 2/3 cycles. That
is 11,172 cycles / 3.121067 ms of physical vertical blank. Every recorded
endpoint agrees with the side-effect-free debug status2 VR read; native raster
durations agree with guest elapsed time. The calibration uses the openMSX
RELEASE_21_0 VDP source; copies and hashes are in the ignored raster run.

The 5,000-cycle usable reserve remains a planning assumption, not a measured
physical limit or a guaranteed VRAM throughput budget. Full refresh, 30 FPS
presentation interval, usable reserve and physical blank are distinct quantities.

Across 848 active frames, `Game_Frame` starts on physical lines 2..23 and crosses
the end of blank every time. Its mean span is 27,266 cycles: 1.817 ms inside
blank and 5.800 ms outside. Individual `Game_LogicTick` calls can start anywhere
from physical lines 1..224, at observed cycle offsets 0..227. These are varying
observations, not a fixed scanline hook.

All 848 atomic commits are wholly in blank. They start at line 245 + 4..8 cycles;
the mean is 4,322 cycles / 1.207 ms, the maximum 8,983 cycles / 2.510 ms. The
maximum exceeds the assumed 5,000-cycle reserve while remaining inside the
measured physical blank in this workload. No scheduling or graphics change was
made for this measurement.

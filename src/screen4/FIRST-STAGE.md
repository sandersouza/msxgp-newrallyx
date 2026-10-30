# SCREEN4 first playable stage

All work remains uncommitted on `codex/fixed-hud-lab`. Functional checkouts and
production build targets are unchanged. Discuss visual acceptance with the user;
no new graphics reduction or event pause was introduced in this performance pass.

Latest three-enemy test ROM: SHA256
`34aab943550df300e3258bd6bb43f853330eca48a7a06acbf8a4b1d8702cf46a`.
The four-set phase-cache pass measures **29.914200 active FPS**, **21.680576 ms**
mean CPU work and **16/913 late publications (1.752%)**, against 29.508353 FPS,
22.202671 ms and 38/908 (4.185%) on frozen `299b5380`. The same keyboard policy
has different samples/outcomes as cadence changes. The three-enemy route ends
at native game over, not stage completion. Stable zero-miss cadence is pending.

Four pattern/color sets now reuse exact fine-scroll phases independently from
the existing two name tables. The selected set always differs from the visible
set. This uses C027..C02D (7 new RAM bytes) and initializes 8,192 additional VRAM
bytes in the upper64KiB; the cartridge stays3,520KiB. All73 graphics/map payloads
match the preceding ROM. No rules, graphics or event-pause changes were made.

Exact checks:16,640 transitions/cold starts in all4 physical sets; full128KiB
VRAM guards;1,247 live render guards with1,231 exact phase hits.55 unit tests pass
with1 optional test skipped. The largest measured atomic commit is6,938 cycles,
entirely inside physical VBlank in the route. Logic remains foreground work over
variable visible scanlines; the139-cycle ISR only acknowledges/ticks.

Active intervals:13 one-refresh,884 two-refresh,16 three-refresh,0 four-refresh.
P95 presentation33.810ms; maximum51.287ms. Actual refresh59.922743Hz gives
29.961372FPS at two refreshes, separate from the nominal29.97FPS goal. Physical
VBlank11,172cycles;5,000cycles remains a planning reserve. The remaining late
self-cost leaders are smoke cache, terrain names/overlays and sprite preparation.

Reproduce the cache guards with `make test-phase-cache` (three-enemy default).
Workbooks: `docs/measurements/timing/archive/component-timing/component-timing.xlsx` and
`docs/measurements/timing/archive/first-stage/cycle-budget.xlsx`. Raw traces and ROM hashes are recorded
in their input/source sheets and `outputs/fixed-hud/phase-cache-proof.json`.

A register-based smoke-cache trial passed2,285 exact cases and helped synthetic
dense rows, but changed this route by only0.004ms mean work and left16 late
frames. It is retained only as ignored evidence, outside the delivered ROM.

## Run

From this worktree:

```sh
make run-first-stage             # Three real enemies with native AI
make run-first-stage ENEMIES=1   # Explicit one-enemy diagnostic
make run-first-stage ENEMIES=3   # Three real enemies with native AI
make run-first-stage ENEMIES=7   # Seven-enemy stress test
make build-first-stage ENEMIES=3 # Build without opening the emulator
make test-first-stage ENEMIES=3
make profile-first-stage ENEMIES=3
make test-render-queues
```

From another directory, prefix the target with:
`make -C /Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx`.
`EXPERIMENT_ENEMIES=3` is also accepted. Supported populations are 1, 3 and 7.
The first-stage default is three enemies. `run-experiments` now selects the
[complete native session](FULL-SESSION.md). Separate first-stage cartridges remain in
`references/experiments/stage-one{,-3-enemies,-7-enemies}/fixed-hud.rom`.
`run-hud-lab` retains the earlier free-camera experiment.

Arrow keys steer; Space releases smoke. Native collisions, death/restart, fuel
and extra-life rules remain enabled. After ten flags and the remaining-fuel
bonus, this prototype stops. Reset to play again; stage two is not implemented.
The 3/7 variants clone only the 24-byte enemy descriptors into valid road cells,
maintain their compiled population through parameter updates/restarts, and use
unchanged original AI. They are explicit first-stage workload variants, not
original later-stage population or difficulty implementations.

## Earlier measurements

Panasonic FS-A1WSX_NR128, Z80 3,579,545 Hz, nominal 60 Hz refresh (approximately
59.92 Hz), hardware sprite limit enabled, HUD and PSG enabled. Presentation and
elapsed-tick native simulation are different rates.

| Workload | Presentation FPS | Active-only FPS | Outcome |
| --- | ---: | ---: | --- |
| Native one-enemy complete keyboard route | 36.84 | 35.65 | Ten flags, one death/restart, fuel bonus, complete |
| Three-enemy keyboard navigation | 32.21 | 27.54 | Native lives exhausted; not complete |
| Three-enemy smoke stress, 480 presentations | 28.77 | 28.51 | Separate four-direction keyboard route |
| Seven-enemy smoke stress, 480 presentations | 24.01 | Not classified | Separate stress route; not complete |

Active-only intervals require both endpoints to have no death, bonus, stopped
or game-over state. Other aggregate FPS include native holds; do not interpret
32.21 FPS as stable 30 FPS during three-enemy action. The native complete route
improved from 35.43 to 36.84 FPS in this pass, active-only 34.10 to 35.65.
The earlier first optimization improved 23.45 to 35.43 FPS.

The new three-enemy pass improves active navigation from 26.07 to 27.54 FPS, and
active smoke stress from 26.07 to 28.51 FPS. The smoke aggregate falls because the
faster run contains far fewer death-hold intervals; active intervals improve.
The action-only CPU profile improves 26.08 to 27.54 FPS, mean work 28.42 to 25.23 ms
and P95 publication 65.96 to 50.07 ms. Rare active intervals still reach 68.08 ms;
stable 30 FPS has not been achieved. The one/seven-enemy rows retain the previous
measured cartridges; this pass rebuilds and validates the three-enemy ROM.

The warmed complete-route CPU profile measures 36.87 FPS. Mean active work is
18.85 ms, compared with 18.97 ms before this pass. Maximum observed publication
interval fell from 100.91 to 84.23 ms; P95 remains 34.17 ms. These are scoped
measurements, not a stable cadence or physical-hardware guarantee. Controllers
follow the same policy, but presentation changes alter input feedback timing.

## Changes and exact checks

New three-enemy action optimizations:

- Direct radar allocation retains all names/patterns/colors and saves 3,837
  cycles in the spread three-enemy synthetic case. 11,264 exact cases pass.
- The duplicate position projection is removed; 65,536 native cases compare
  complete caller-visible state. Smoke retirement is inlined with identical
  comparisons/notifications/zero writes, saving 928 cycles per 32-cell crossing;
  896 real Z80 cases pass, including legacy/unconfigured byte preservation.
- Two-row HUD-name transfers save 569 cycles per call; 8,960 cases preserve all
  RAM, full name VRAM and returned registers, including strict display-on tests.
- Full-height horizontal car clipping uses bounded unrolled AND copies;
  13,587 cases retain exact public RAM/cache/SAT/colors/pattern VRAM. Four cars
  with one clipped actor save 9,076 preparation cycles. Sentinel/vertical paths
  retain their previous implementation and the hardware limit remains enabled.
- Back tables lagging two/three tiles stream entering visible columns/rows.
  6,144 cases check 896 visible names, continuous reversals/diagonals, hidden
  changes, both buffers and restarts. Two-tile horizontal/vertical cases save
  roughly 16,455/21,995 cycles versus a full refill. Hidden VRAM may remain stale;
  entering rows are repaired before presentation, including positive single
  rows at relative 27. Larger jumps retain the full refill.
- Boundary transitions reuse exact ROM packets through the existing HUD worker;
  72 transitions and both buffers compare the full 128 KiB VRAM and restored
  phase bank in the actual cartridge, with zero strict timing violations.
  This uses 42 resident bytes and four extra ROM pages. Unused free-camera-only
  radar coordinate arrays are omitted from gameplay, freeing 1,798 resident bytes.

All four-atlas bytes, seven graphics payloads and 64 phase HUD files remain exact.
The earlier optimizations below remain in place:

The additional native boundary proofs use the preserved local baseline:

```sh
.venv/bin/python -B src/screen4/game_position_proof.py --bundle references/experiments/stage-one-3-enemies/baseline-ca9e6ae6
.venv/bin/python -B src/toolchain/screen4/test_game_smoke_fast.py --bundle references/experiments/stage-one-3-enemies/baseline-ca9e6ae6
.venv/bin/python -B src/toolchain/screen4/test_game_boundary_fast.py --emulator --bios references/msxbios --bundle references/experiments/stage-one-3-enemies
```

- Candidate smoke rows replace a full 1,024-byte native-code scan. The exact
  ordered sparse records match 2,285 differential assembled Z80 cases. A 3x3
  cloud costs 13,820 cycles versus 75,422; a never-used cache takes 75 cycles.
  A fully occupied artificial ring has 0.85% bookkeeping overhead.
- Per-back-table dirty bits and nonzero-byte queues publish changed names rather
  than invalidating every name after an effect mutation. A dense queue uses the
  sequential full refill. 1,352 cases / 2,704 buffer phases / 5,171 mark calls
  check exact RAM, VRAM, duplicate marks, all cells, wraps and register contracts.
- Fixed-count OUTI groups replace OTIR in HUD-name rows. All 8,960 assembled
  cases match. A second before/after comparison with display active and the
  strict VDP timing callback saves 840–980 cycles/call, mean 949.375, for 98 bytes.
- Existing ring, actor, sprite and 64-phase radar adapters remain. Their exact
  byte tests and generated radar mask tests are reproducible through
  `make test-performance-adapters`.

Seven terrain/palette/car/font/life/base-HUD payloads are byte-identical to the
previous accepted-graphics build. Existing experiment-only SCREEN4 scenery,
seven-pixel boundary and fixed eight-pixel left mask remain. The 2026-10-28
smoke/explosion row adaptation remains exactly the authorized version: smoke
37/576 changed pixels and explosion 23/576, both 24x24. Complete 16x16 cars and
all source dimensions remain unchanged.

## Real multi-car evidence

Independent 480-presentation traces record native descriptors, prepared cars
and the actual sprite attribute table, with normal keyboard inputs and no
native state writes. All requested enemies move and counts stay constant.
Three and seven entire enemies were simultaneously visible, including frames
without scanline overflow. The new three-enemy trace reaches nine candidates per
line, with overflow in nine of 480 presentations and 33 affected scanlines. These
are candidate counts; not every excess candidate necessarily contains visible
ink on its affected line. The retained seven-enemy trace reaches eleven candidates; five
of 480 presentations have hardware overflow, totaling twenty affected scanlines.
No sentinel whole-car culling occurs in either trace. Candidate counts do not
imply that all lines survive the real eight-sprite limit.

The seven-enemy trace observes smoke spin, two enemy-contact deaths, two native
restarts and a retained collected flag. The baseline three-enemy trace also
observes contact/restart; the faster final short three-enemy trace has no death.
No claim of identical temporal behavior is made across frame-indexed inputs.

## Evidence and cycle ledger

`docs/measurements/timing/archive/first-stage/cycle-budget.xlsx` and `summary.json` bind the exact ROM
hashes to raw profile paths, active-only calculations, inclusive/self costs,
calls/frame, mean/P95/max, waits and remaining budgets. `MultiCar`, `SmokeCache`
and `DirtyNames` distinguish separate workloads and synthetic bounds.
`performance_report.py` regenerates the JSON from retained measured evidence;
`workbook.mjs` regenerates the workbook with the bundled artifact-tool runtime.

`game_verify.py` checks visible terrain/effect priority, full HUD pixels and
SAT/glyphs, native car masks, smoke/explosion patterns, sprite port spacing and
VDP status during publication. The final one/three-enemy routes each validate
sixteen snapshots; three/seven smoke runs each validate four. All have zero
sprite/HUD writes or publication exits outside VBlank. The independent native
probe reproduces 1,200 ticks and all 120 intro PSG packets. Unit discovery runs
42 tests, with one explicitly optional emulator test skipped; the corresponding
CPU probes are run separately.

The primary budget/frames/routine tables now use three-enemy action intervals,
with both endpoints active. MultiCar retains separate aggregate figures and
active smoke figures. All routine calls, inclusive/self mean/P95/max and remaining
budgets use the matching interval denominator; parents and children overlap.
The profiler uses an immutable ROM copy and PC/SP-matched routine returns. A
control run checks identical camera/tick states and no more than five cycles of
boundary observation jitter. Inclusive parents/children must not be summed;
standalone IRQs and untracked loop overhead are reconciled separately.

One refresh is 59,736 CPU cycles; two refreshes are 119,472. Drawing preparation,
atomic publication, synchronization and usable VBlank budgets remain distinct.
The 5,000-cycle VBlank reserve is a planning assumption, not a measured hardware
limit. Native event holds are not newly inserted scheduling pauses. Continuous
scanout and physical hardware acceptance remain outside these state/VRAM checks.

## Event-cache pass, 2026-10-28

The preceding event-cache test ROM SHA256 is
`a5d318eb00169dc746dcb2e3b6fd042930411741c69a32e1d036c4bb918a71ed`.
`make run-experiments` now builds and launches three enemies by default;
`ENEMIES=1` remains an explicit diagnostic override.

Active three-enemy presentation improved from 27.543138 FPS / 25.229105 ms mean
CPU work to 28.890890 FPS / 23.336411 ms. The same controller/filter produced
848 before and 889 current active samples; native routes and sample counts
vary with presentation cadence. Interval P95 is 50.062229 ms, so this
does not establish stable 30 FPS. The full route still ends at native game over,
not demonstrated stage completion.

HUD fields are decoded independently when their native values change; unchanged
packed slots and SAT publication are skipped. Scroll/sentinel compensation stays
independent. No native scoring, HI, S/L, fuel cadence or audio behavior changed.
The radar still updates character dots and performs the same transfers; exact
uniform source metadata avoids unnecessary ROM cloning on eligible characters.
It adds 4,096 bytes inside existing phase pages and no extra ROM banks or RAM.

HUD proof covers 3,333 cases with identical complete SAT/pattern output, native
counters and RAM guards. Radar proof covers 11,264 cases with identical 1,601-byte
RAM results. Unit discovery passes 45 tests with one optional skip; natural240,
smoke480 and route1225 integrated checks pass with no publication outside VBlank.
The 480-frame population check observes three moving, fully visible enemies,
an enemy-contact death and restart. It reports no scanline overflow in that
specific scenario; hardware sprite limits remain enabled.

`docs/measurements/timing/archive/component-timing/component-timing.xlsx` includes the previous measured
baseline and current Schedule, Changes, Components, Movement, Raster and Inputs views.
The original cycle workbook at `docs/measurements/timing/archive/first-stage/cycle-budget.xlsx` is also
refreshed. All original graphics and 64 HUD phase payloads are byte-identical.
The native worker payload is unchanged apart from three linked CALL/JP operands
following their relocated resident symbols.

The scheduling target is nominal NTSC 29.97 FPS (33.366700 ms), tracked separately
from the measured two-refresh cadence of 29.961372 FPS (33.376309 ms). The first
event-cache pass reached 28.451348 FPS; edge analysis then identified 93/875
late frames dominated by boundary/static-HUD transfers. A 47-byte 16-OUTI burst
helper replaces inline OTIR in the optimized packet worker, preserving exact
data, HL/BC/DE contracts, mapper and IFF ownership, with no new RAM. Its 512-case
full-VRAM probe passes both tables, sizes1..255 and packet chains, with zero
strict timing callbacks. Lengths1..31 cost more; larger transfers win, and the
integrated profile is the acceptance gate rather than equal-weight estimates.

Current native VDP analysis finds 9 active presentations after one refresh,
810 after two, 65 after three and 5 after four. All 70 late frames crossed the
two-refresh foreground deadline. The remaining late cohort has mean shortfall
8.001 ms and maximum23.318 ms; cadence still falls short of stable29.97 FPS.
Helper timing is charged to its HUD/boundary owner; isolated helper costs must
not be added again to the frame budget.

## Late-frame pass, 2026-10-28

Compared with the a5d318eb event-cache baseline, active presentation improves
from 28.890890 to 29.183373 FPS; CPU work falls from 23.336411 to 22.802823 ms.
The controller and active-state filter are unchanged, but cadence changes native
routes/sample counts. Late publication falls from 70/889 (7.874%) to 54/898
(6.013%): nine intervals use one refresh, 835 two, 51 three and three four.
P95 interval is 49.632006 ms, maximum 67.972326 ms. The remaining late foreground
shortfall averages 7.284 ms and peaks at 20.806 ms. Stable 29.97 FPS is not achieved.

- Boundary atlases use stable character identities and row color pairs across
  the eight fine-X phases. Known-phase packets skip unchanged color bytes.
  All 385,024 decoded edge pixels across 64 phases and 47 sources match the prior
  ROM. 73 original graphics/map/native-raw files are byte-identical.
- Smoke records decode retained world Y once per physical row. 2,285 assembled
  cases preserve exact record order, count, native ring and occupancy metadata.
  A three-live-row fixture falls from 13,820 to 12,389 cycles; this is an isolated
  synthetic cost, not a per-frame saving.
- Ring metadata rebuilding uses 1,934 bytes of previously unused mapper-bank4
  ROM, with no extra RAM/banks. 8,960 synthetic cases preserve complete ring,
  pointers, boundary IDs and both VRAM name tables. The isolated one-tile rebuild
  saves 1,735 cycles; timing remains owned by Ring_Prepare.
- Three-by-three overlay loops preserve their counter registers once per
  square. 1,280 compiled cases compare 2,082,560 bytes exactly, including both dirty
  queues and native guards; accepted squares save 355 cycles each.

Natural240, smoke480 and route1234 integrated runs validate active VRAM, all
edge pixels, complete car masks, HUD and native terrain/effect priority. No
publication writes/endpoints occur outside VBlank; strict VRAM timing checks
pass. The route reaches native game over, not stage completion. Separate 480-frame
population checks observe all three moving/full cars, smoke reaction, contact
death and restart; no scanline overflow occurs in those specific scenarios.
Hardware sprite limits remain enabled. Unit discovery passes 47 tests with one
optional skip.

Current coarse profile: `profile-route-paoblkv5`; detailed profile:
`profile-route-27xt3b57`; raster: `raster-phase-hr0k7264`. The preceding baseline
was reprofiled with the same explicit smoke/patch/dirty subroutine boundaries in
`baseline-a5d318eb/profile-route-n3fxnq_0`. The Schedule ranking uses disjoint self
costs; helper and parent inclusive costs must not be added together. The main
remaining late owners are static HUD packets, world sprites, boundary packets
and ring preparation. Further scheduling changes must preserve the publication
dependency and native input/tick behavior.

## HUD transfers and sprite preparation, 2026-10-28

Compared with frozen12e32699, three-enemy action improves from29.183373 to
29.508353 FPS; CPU work falls from22.802823 to22.202671ms. Publication after
more than two refreshes falls from54/898 (6.013%) to38/908 (4.185%). There are
13 one-refresh,857 two-refresh,35 three-refresh and three four-refresh intervals.
P95 presentation interval falls from49.632006 to34.595179ms; maximum remains
67.972047ms. Native input/tick rules remain intact. The remaining38 misses mean
stable29.97 FPS has not been achieved.

HUD tiles that coexist receive distinct slots; identical glyphs retain stable
identities across phases. The offline graph uses50 of the existing64 slots.
An absent previous slot is explicitly unknown: a later active glyph is always
written even when the ROM fallback bytes match. Absent current slots need no
write; gap merges may overwrite them with exact current source bytes.
Each transition is compiled into a bounded ROM program with serialized VDP
address pairs, shared R14 setup and measured burst transfers. The resident
return remaps the current phase after leaving the program page.

Sprite preparation uses byte bounds for the same signed viewport range,
page-local cache/SAT addresses, fixed eight-slot dispatch and exact clipped
copy spans. Vertical/sentinel clipping clears its private destination and copies
only visible source rows; every complete visible car and original sentinels are
preserved. Pattern preparation stays in foreground; color/SAT publication stays
in fresh VBlank. Maximum observed commit is6908cycles, wholly in physical blank.

Validation covers3,147 synthetic sprite cases;8,320 native HUD transitions with
both back sets, unknown preceding inactive slots, cold starts, full VRAM guards
and active IRQs;999,424 exact HUD/flag-choice pixels; unchanged73 original asset
files and385,024 edge pixels. The compiled clipping helper is byte-identical to
the synthetic worker after resolving its three resident CALL/JP operands.
Unit discovery passes56 tests with one optional skip. Natural240, smoke480 and
route1244 active-VRAM checks pass; the route ends at native game over. Separate
480-frame natural/smoke observations verify three moving/full enemies, smoke
reaction, contact death and restart, with hardware sprite limits enabled.

The tradeoff is ROM:2,656 ->3,520KiB (+864KiB), no new RAM. No quality reduction,
event pause, HUD-off run or clock increase was introduced. Coarse profile is
`profile-route-ps495wx2`, fine profile `profile-route-v5upa8zj`, raster
`raster-phase-617omwck`; actor runs are under `event-components-299b5380`.
Page2 routine entry probes now verify mapper-bank identity: compiled HUD PCs
must not be mistaken for native logic or the phase name-store program.

At nominal50Hz the official313-line model gives71,364cycles per refresh versus
59,736 at262 lines (+19.47%), with the same3,579,545 CPUcycles per second.
Two-refresh presentation would be25.079FPS rather than29.961FPS. Near30FPS
would need uneven one/two-refresh intervals and native clock/audio adaptation.
These PAL numbers are calculated from openMSX timing constants, not a PAL game
measurement. The delivered ROM remains in nominal60Hz mode; the Raster worksheet
contains the source and calculated comparison.

# Fuel integration: reserve the measured work in the existing tile budget

Stage 06 v2/v3 passes the independent original component oracle (91 cases,
9,982 exact ticks) but fails the unchanged refresh gate: maximum main interval
20.538923 ms, against a 19.938 ms display period and 0.6 ms tolerance.
No subsequent gameplay subsystem is integrated while this gate fails.

Read-only v3 profiling identifies two added costs: the fuel tick reaches 1,829
elapsed CPU clocks when the original decimal decrement regenerates its gauge
shadow, versus 326 clocks for an ordinary tick; a changed HUD fuel pattern takes
3,508 clocks to upload. These measurements include interrupts and VDP waits,
and are not claims of pure routine CPU time. The unchanged tile budget reserves
neither cost. Fuel's frame publication also adds 432 clocks on normal frames.

The fix keeps the same visible maze, original pixels, simulation ticks and CPU
frequency. Reserve one guard copy for the adapter's recurring overhead, three
when the original consumption timer rolls over, and six on a changed fuel HUD
upload. Reset the cost markers per advancing frame, saturate tile reservations
at zero, and retain pending guard jobs. Existing score/radar/patch reservations
remain in effect. No new sprites, reduced tick rate, or relaxed timing gate.

The first reservation candidate v4 met refresh timing (maximum 20.247 ms) but
failed the cache proof on a collection frame: it needlessly reserved six patch
jobs when no optional car row existed. Only seven of nine flag tiles were drawn.
Reserve that patch cost only when a row was patched/restored in this frame or
is currently valid. Keep the full nine-tile collection update in the same frame;
do not weaken the cache oracle or hide its partially updated flag.

V5 passes standard driving and the complete all-flag/lucky route in both HUD
modes. Its first death image exposes four old rock pixels: all nine commands
finish before the footer, but the last command reaches the effect's final row
after the display has scanned it. Batch each three adjacent atlas tiles into
one 24x8 copy, splitting horizontally at the cache page boundary. The builder
verifies source contiguity. Keep the exact bitmap and torus coordinates; finish
the three-row effect together and charge its nine tile areas to the budget.
Terrain restoration still uses individual original atlas tiles.

Acceptance requires a fresh full driving/RGB proof with and without HUD, the
real all-flag route including the lucky countdown, pause, and original per-tick
component comparison. A separate raw cost trace measures both fuel paths.

Accepted v6: both HUD configurations pass 1,600 movement/cache states (37/39
full RGB), the ten-flag route (2,786 cache states / 12 RGB / 177 exact original
lucky ticks), and death/pause/reset (10 RGB). All 512 grouped-copy wrap/budget
cases pass. Main maximum is 20.247 ms standard and 20.334 ms all flags; maximum
GPU commands is 19. Live fuel-tick maximum is 1,878 elapsed clocks; fuel HUD
upload maximum is 3,530. Full suite: 291 tests pass. Original 91-case / 9,982-tick
fuel proof passes on the final ROM. Stage 00 still reproduces its original SHA.

Evidence is local and ignored under `references/build/issue11-r06-*`:
`v6-fuel-check`, `v6-cost-check`, `v6-death-copies-check`, and both HUD variants'
`v6-player-check`, `v6-all-flags-check`, `v6-death-check`. The unchanged scoring
component's 1,278-case proof is `issue11-r06-v5-score-check/report.json`.

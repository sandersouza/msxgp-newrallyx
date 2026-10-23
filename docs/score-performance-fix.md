# Stage 05: measure scoring and numeric HUD before proceeding

The first stage 05 candidate links the selected original flag-point loop,
digit-carry routine, high-score and score-awarded life accounting. It returns
before lucky fuel conversion, which is the stage 06 collection effect, and
replaces only the old bitmap life-rendering interface with a return.

Candidate `references/build/issue11-r05-v1/raster-scroll.rom` preserves all 1,600
movement/cache states but fails the unchanged timing gate at 22.533 ms on the
standard route. The accepted stage 04 control passes at 20.159 ms maximum.
Do not add fuel or enemies while this regression remains.

## Fix plan

1. Profile the unchanged candidate's scoring consumer, HUD numeric publication
   and scenery streaming independently. The earlier radar reservation does not
   yet account for live numeric content changes or native score-loop work.
2. Compare each linked arithmetic/high-score/bonus-life output with an independent
   original-ROM component oracle, including digit carries, threshold crossings,
   special-flag ordering and repeated events. Lucky fuel conversion remains an
   explicit pending stage 06 handoff, not an implemented scoring reward here.
3. Reserve measured numeric/scoring work in the shared frame budget. If the
   original repeated-increment loop itself cannot fit, use a bounded arithmetic
   adapter or a source-compatible incremental sequence and validate its outputs
   and timing explicitly. Never relax the frame deadline or overclock the CPU.
4. Repeat standard and all-flag keyboard/cache/RGB routes with HUD on/off, plus
   the existing death/reset regression. Promote a checkpoint only after they pass.

## Measured offender and bounded adaptation

V1 profiles show score-event elapsed cost 10,246 cycles for the first flag and
15,940 for the second, while HUD content with dirty radar/numbers reaches 19,199
cycles. Isolated source scoring cases reach 159,485 assembled MSX cycles. The
source loop repeatedly adds ten points and runs the high-score/life check for
every increment; a doubled tenth flag requires 200 such increments.

The adapter groups ten +10 operations into one +100 operation using the same
original digit-carry entry at `$2119`. It normalizes the tens digit as those ten
source calls do. Original `$2064` checks still run before the award, at every
reachable high-score/life boundary, and at the final value. Boundary packets are
reconstructed with the original carry routines so source glyph prefixes and the
unusual full-width overflow carry remain exact. No fuel bonus is manufactured;
the lucky request remains for stage 06.

Scoring runs after dirty terrain, with raster interrupts enabled, and reserves
the rest of that frame's guard work. Numeric HUD pairs also reserve four guard
jobs each. Common awards bypass boundary sorting, and an unchanged high score
does not republish its digits. The display, source coordinates and clock remain
unchanged. The one/two-tick resampler does not skip simulation ticks.

V4 passes 1,278 exact original-ROM cases, including carries, special/lucky request
bits, mid-group records, both life thresholds and already-awarded life bits.
Native score/high-score packets, life flags/counts and pending HUD digits match.
Maximum isolated adapter cost is 23,895 cycles; ordinary live first/second-flag
costs fall to at most 9,103 elapsed cycles, including interrupts. An intermediate
overflow mismatch was caught and fixed before acceptance; v2/v3 are not accepted.

The standard route passes 1,600 movement/cache states and 32 full RGB images
with HUD, and 1,600/35 without. The all-ten-flag route passes 2,642 cache states,
12 full RGB images and live point totals in each mode. Main maximum is
20.136 ms on the standard route and 20.030 ms on the all-flag route. Existing
death/pause/reset verification passes another 11 full RGB images. Timing gates
are unchanged. V5 has identical ROM bytes to V4 and corrects metadata/adds a
non-emitting profiling label; its fresh cost trace covers dirty terrain even on
scoring frames.

Status: accepted as `11-r05-score-v5` / `11-r05-no-hud-v5`. Fresh V5 trace passes
1,600 states and records every dirty-terrain call (maximum 14,310 elapsed cycles),
HUD content (19,241) and scoring (9,103) independently. The full suite passes
288 tests. Lucky fuel conversion remains explicitly pending in stage 06.

# Stage 04: collection work and dirty radar-cell scheduling

The accepted stage 03 baseline passes the unchanged 0.6 ms refresh tolerance.
The first stage 04 candidate fails it: main-start intervals reach 23.467 ms,
although the raster splits themselves remain within tolerance. Do not add score,
fuel or enemies until this regression is resolved.

## Reproduction and evidence

- Candidate: `references/build/issue11-r04-v1/raster-scroll.rom`.
- Same 1,600-frame driving route as stage 03, standard CPU and real VDP timing.
- Raw traces: `issue11-r04-v1-headless-check` and `issue11-r04-v1-profile-check`.
- Collections occur at frames 289, 1390 and 1456; Home resets at 1000.
  The worst intervals follow the latter collections, at 1392 and 1458.
- Initial collection consumer median: 965 elapsed cycles, maximum 4,151 cycles
  including interrupts. It scans six-byte records, even for misses.
- The old static-world verifier correctly first rejected the intentional flag
  removal at frame 289. Its oracle now tracks independently captured active
  flags, reconstructs empty terrain from the original board, and checks the
  corresponding visible radar publication separately. The timing gate is unchanged.

## Fix plan

1. Measure HUD content rebuilding and the dirty maze jobs separately on the
   unchanged failing ROM. Dynamic flag removal exercises previously idle radar
   dirty-cell rendering; determine its added cost before attributing the delay.
2. Replace the six-byte miss scan with the original compact two-byte address
   scan; access the flag's kind/position/HUD metadata only on a match.
3. Charge measured radar content work to the same frame's guard-tile budget,
   as already done for the player's optional bitmap row. Keep the terrain job
   queue bounded, including collection while turning or crossing cache seams.
4. Rerun identical movement/cache/RGB and timing checks, then original flag
   boundary/one-time collection tests and cache eviction/re-entry routes with
   HUD on and off. Retain the rejected candidate and all raw reports.

## Measurements and fixes in progress

The unchanged v1 profile confirms HUD content maximum 14,922 elapsed cycles
(4.17 ms), versus its normal 359 cycles. Nine dirty maze tiles take 14,326
elapsed cycles and are already charged to the copy budget. The compact source
address scan reduces the normal collection consumer from 965 to 667 cycles.

Radar cells now reserve six guard jobs each. Reservations saturate at zero;
an intermediate candidate exposed arithmetic underflow when a two-tick refresh,
radar work and the car-row patch coincided. The assembler's `IFDEF` tests defines,
not `EQU` labels; the meter therefore uses an explicit embedding define, with
its host counter initialized. Both failed candidates remain local evidence.

V5 passes the complete 1,600-state movement/cache proof and all 10,931 original
flag boundary/persistence cases, but still reaches a 20.742 ms main interval.
An attempted VBlank stop still reaches 20.794 ms: the already-issued indivisible
VDP transaction can finish too late. That attempt is not accepted.

The next candidate reduces only the invisible horizontal prefetch halo from
16 to eight tiles on each side (48 cached columns instead of 64), retaining the
512-pixel physical torus, full visible viewport, original pixels and coordinates.
Vertical scroll rows consequently need 25% fewer copies. A 20/16 job budget
(one/two logical ticks) has headroom above the resulting sustained row demand;
radar reservations remain bounded and saturating. No logical ticks or display
refreshes are skipped. Full visible-cache, long-route and RGB checks must prove
that the smaller halo keeps up before acceptance.

## Accepted result

V7 is accepted. Its unchanged 1,600-state driving/cache proof and full RGB
comparison pass with HUD (34 images) and without HUD (35). Main maximum is
20.159 ms, footer maximum 20.225 ms; steady GPU median/maximum is 16/20.
The all-ten-flag keyboard route passes another 2,642 cache states, 12 complete
RGB images and 3,139 original-Z80 collection observations in each HUD mode.
It revisits a collected flag after cache eviction, then verifies Home reset.
Main maximum on that route is 19.938 ms; footer maximum 20.438 ms. Original
boundary/persistence tests pass all 10,931 cases, and the death regression passes.
The original timing tolerance remains unchanged. Stage 00 still rebuilds to
`a89f20da...` byte for byte.

Accepted checkpoints: `11-r04-flags-v7` and `11-r04-no-hud-v7`. Local reports:
`references/build/issue11-r04-{v7,no-hud-v7}-{player,all-flags-v3}-check/`.
No score/fuel/enemy work was added while diagnosing the regression.

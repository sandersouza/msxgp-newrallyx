# Sprite priority rotation experiment

The user authorized classic sprite flicker and either 50 or 60 Hz. This
experiment keeps the VDP's real eight-sprite scanline limit and alternates
priority, preserving original 16x16 enemy masks and adjacent body/window color
planes. It does not increase that hardware limit or release sprite slots.

## Current controlled checkpoints

```sh
make run LATEST=1
make run CHECKPOINT=11-flicker-60-v6
make run CHECKPOINT=11-flicker-50-v6
```

Both cartridges start **paused**, with two enemies deliberately placed over
the radar. Native simulation is frozen while the SAT order alternates every
display refresh. Space resumes an **unaccepted moving prototype**; Home resets
the controlled placement. These placements are a diagnostic fixture, not the
original first-round initialization or a natural pursuit test.

The canonical phase retains the normal order. The alternate phase exchanges
radar slots 6..9 with the two complete enemy pairs in slots 19..22. The earliest
two radar bands retain fixed indices to meet their fetch deadline. Player and
fuel/life slots retain their indices for the raster hooks. Lower-priority radar
pixels can disappear on overloaded lines, and an enemy may temporarily lose
one color plane in the canonical phase.

Allocation is **24 slots, eight free** with HUD and two enemies. This is a
priority experiment; the earlier bitmap-player and bitmap-radar experiments
measure actual slot reductions separately.

Rebuild the controlled test with:

```sh
make build STAGE=9 SPRITE_FLICKER=1 FLICKER_STRESS=1 HZ=60
# Use HZ=50 for the comparison. Each successful build updates LATEST.
```

The normal build selector remains the accepted stage 08 at 50 Hz. Its restored
local checkpoints are `11-r08-restored-v1` and `11-r08-no-hud-restored-v1`.
Their ROM hashes exactly reproduce the accepted v25 HUD-on/off cartridges.
`make clean` removes all generated cartridges, checkpoint registrations and
test evidence. The user cleaned during this experiment; only these four final
cartridges were reconstructed. Older checkpoint names below other documents
are historical results and require rebuilding before use.

## Measured evidence

Both display runs use the standard 3,579,545 Hz CPU, real VDP command timing,
sprite limits enabled and no frame skipping. Neither overclocking nor disabled
sprite limits is used.

| Check | Result |
| --- | --- |
| Actual assembly permutation/color upload | 1,536 cases: all 256 scroll phases, three EC combinations and two SAT orders |
| Original enemy component | 2,643 exact state/visibility/contact cases |
| Two-enemy presentation | 3,856 cases / 7,712 actor comparisons against independent original masks |
| Controlled 60 Hz display | 120 refreshes, ten complete RGB comparisons; raster period 16.688 ms |
| Controlled 50 Hz display | 120 refreshes, ten complete RGB comparisons; raster period 19.937 ms |
| Continuous overflow | Nine candidate sprites on a line, real selection limit eight |
| Full two-plane enemy coverage | 100% / 65.625% of sampled actor scanlines, both rates |
| Repository tests | 303 passing |

The isolated upload takes a median 15,888.5 cycles (4.44 ms), maximum 15,961
cycles. VDP IRQ sources are disabled only in this component probe to isolate
the transaction from the independent footer SAT replacement. The complete
display tests retain normal interrupts and validate every raster phase with
the unchanged 0.6 ms tolerance. The cost is material; flicker is not free CPU.

Evidence is sealed under `references/build/`:

- `issue11-flicker-stress-60-final-v6-component/report.json`
- `issue11-flicker-stress-60-final-v6-presentation/report.json`
- `issue11-flicker-stress-60-final-v6-native/report.json`
- `issue11-flicker-stress-{50,60}-final-v6-display/report.json`

## Moving integration remains pending

Moving two-enemy candidates at both rates produced complete-image mismatches
and missed raster deadlines. A stage 08 control at 60 Hz also failed header
RGB, so a passing stationary 60 Hz display does not establish a playable 60 Hz
game. The accepted gameplay reference remains stage 08 at 50 Hz. Stage 09,
smoke and completion/start transitions remain open in issue 11.

Uploads now permit interrupts between chunks of at most 16 bytes, reduced to
eight bytes ahead of the 60 Hz header split. The VDP bank/address is selected
again after each interrupt opportunity. Pure RAM actor preparation also permits
interrupts. The paused fast path skips rebuilding identical actor/HUD RAM,
isolating the priority rotation from moving-game work. These changes establish
the controlled result; they do not establish moving-game acceptance.

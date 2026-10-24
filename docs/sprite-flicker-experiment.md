# Sprite priority rotation experiment

## Independent black outlines: rejected experiment

The user rejected v144 after observing slow gameplay, broken scenery and loss
of the upper car window. Both `LATEST` and the default run ROM are restored to
the accepted `11-r09-player-dot-50-v115`, with complete original car drawing
and sprite radar. V144 remains available only as failed experimental evidence.

The majority-color conversion below merged nonblack body and window colors;
it preserved opaque geometry but failed to preserve the drawing. The roughly
11.21 ms publication component also exceeded the available moving-frame
margin. Broken moving RGB was already reproducible before user evaluation.
Stationary overflow success must not be used to promote such a moving build.
Any further flicker test must retain the complete dependent two-plane car,
including its windows, and meet the moving cache/RGB/timing gates first.

The user rejected bitmap radar and requested sprite radar with colored car
bodies taking priority over flickering black outlines. Run:

```sh
make run CHECKPOINT=11-outline-flicker-60-v144
make build STAGE=9 OUTLINE_FLICKER=1 FLICKER_STRESS=1 HZ=60
```

ROM SHA-256: `02b6280aea0c96487bea0e7d1f7b8dd6a6a43750ed6cfeef4887006bd4bf48b6`.
The test starts paused with two enemies deliberately placed over the radar.
Space releases this artificial placement into an unaccepted moving path;
Home restores it. The accepted normal gameplay reference remains
`11-r09-player-dot-50-v115`. All new comparisons retain the HUD.

Original black car pixels were encoded by overlapping two CC color planes.
The experiment separates nonblack body ink from exactly the original black
ink. Each body row chooses its majority original blue/yellow color; enemies
translate these to their existing red/blue entries. This deliberately
simplifies mixed-color rows while retaining native 16x16 dimensions, black
ink geometry, world coordinates and original rules. No CC dependency remains.
Player row colors follow its sentinel-safe shifted mask.

Four priorities always place the three car bodies first. Contours alternate
priority with radar and reverse their order to share starvation. Fuel/life
keep slots14..16 for raster reuse. This controlled layout has twelve radar
map cells, three independent radar points, three fuel/life entries and six
car planes: 24 entries/eight free. The hardware still selects at most eight
sprites on one scanline and stores at most 32 entries overall.

Colors and attributes are assembled in RAM and uploaded to an inactive
table; only a completed table is selected during VBlank. SAT/color pairs
are at 0x1f600/0x1f400 and 0x1ee00/0x1ec00. Pattern storage stays at 0x1f800.
Footer and VBlank fuel/life uploads follow the selected table, preventing
partially published priority/color combinations during active scanout.

Evidence under `references/build/issue11-outline-flicker-*v144/`:

A portable copy of the reports, traces, sessions and captures is sealed at
`references/build/issue11-outline-evidence-v144/`. Its provenance records the
original manifests. Emulator home/userdata files are excluded because their
platform filenames (such as `C-BIOS_MSX2+`) are rejected by bundle path validation.
Original evidence remains unchanged; the curated manifest verifies successfully.

- 3,072 actual SAT/color/EC/commit transactions pass, covering all 256 scroll
  values, four priorities and twelve body poses. Native state and maze are unchanged.
- 120 controlled refreshes and ten full RGB captures pass at 60 Hz, with
  16.687875 ms median raster periods and real sprite limits enabled.
- Nine candidate sprites occur on overloaded lines. Both enemy bodies remain
  selected on 100% of sampled lines; full contours survive 82.8125% each.
- Original enemy/contact logic passes 2,643 states; 323 unit tests pass.
  The normal stage08 build still reproduces its accepted ROM hash.
- Publication costs 40,130 median cycles (about 11.21 ms), maximum 40,498.
  This cost does not establish moving-game performance acceptance.

The moving control `issue11-outline-flicker-moving-60-v143` fails full RGB at
capture10/state1, bbox(84,25,284,226). Navigating main intervals have a
33.376868 ms median and 50.067257 ms maximum across 307 consecutive samples.
The failed route remains at `issue11-outline-flicker-moving-route-v143/`.
Moving-cache/full RGB/raster acceptance is not inferred from the controlled
result. Stage09 and issue11 remain open.

## Earlier complete-pair experiment (historical)

The user authorized classic sprite flicker and either 50 or 60 Hz. This
experiment keeps the VDP's real eight-sprite scanline limit and alternates
priority, preserving original 16x16 enemy masks and adjacent body/window color
planes. It does not increase that hardware limit or release sprite slots.

## Current controlled checkpoints

```sh
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

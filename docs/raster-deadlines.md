# Stage 09 raster deadlines and raw-frame capture

The one-enemy 60 Hz experiment preserves the original 16.5 ms logical clock,
248-pixel maze viewport and original-size assets. It reserves nineteen SAT
slots, leaving thirteen free. Stage 08 remains the default and its ROM bytes
remain preserved. Additional enemy population, smoke and stage transitions are
separate acceptance steps.

## Wait decisions

A VBlank could occur between reading the frame counter and executing HALT.
Returning from that interrupt and then sleeping delayed the foreground until
another interrupt. A subsequent split wait could then wait for the following
refresh. The old control trace around frame 548 starts the next loop at screen
row 12 instead of the blank interval and produces a 30.173 ms interval.

Stage 09 now disables interrupts before each wait decision, then uses EI/HALT
as an atomic sleep. The raster ISR still runs normally. No logical ticks,
input samples or original actor rules are removed.

## Presentation work

- The header handler reserves the split at line 3, waits for the final font
  row, prepares the maze registers and enables the display at the line-nine
  hardware match. The bitmap maze still starts at y11.
- The first three radar attributes are uploaded before enemy drawing. The
  remaining attributes and fuel/footer shadows follow actor drawing. A ROM
  coordinate table covers all 256 vertical scroll phases.
- Radar cells are composed into bounded RAM payloads. Uploads may start only
  between physical lines 80 and 144, after the radar has scanned out. A late
  payload remains pending; published point/flag state advances next refresh.
- Numeric HUD work and flag-base composition also respect the early body
  window. Flag-base work is bounded to one cell and deferred on two-tick
  refreshes. Glyph writes service interrupts between complete rows and
  reselect their VRAM bank afterward.
- The forty-column cache retains both axes in one ownership window. Queues
  prioritize visible rows/columns, then wrap to their hidden guards. Each
  column still covers 32 rows and each row forty columns. Tile address
  preparation is interruptible; VDP control pairs remain atomic.
- GPU status polling leaves S2 selected. Raster entry explicitly selects S1
  or S0, and every polling entry reselects S2. This removes a redundant control
  transaction from each tile copy without changing the command or its pixels.

At forbidden player SAT Y=216, the complete normal 16x16 car is presented one
pixel upward. Stage 09 omits the bitmap last-row save/restore. Native world
coordinates, movement and collision remain unchanged. Earlier stage builds
retain their previous presentation.

## Complete raw frames

A raw screenshot uses openMSX's most recent completed paint frame. In openMSX
21.0, setting both frameskip limits to zero still leaves a host-deadline
selection path. A skipped render can therefore leave a screenshot one frame
behind even though the guest's registers, VRAM and clock are correct. The
[renderer implementation](https://github.com/openMSX/openMSX/blob/RELEASE_21_0/src/video/PixelRenderer.cc#L154)
and [raw screenshot implementation](https://github.com/openMSX/openMSX/blob/RELEASE_21_0/src/video/PostProcessor.cc#L150)
explain these separate responsibilities.

Rendered movement/contact verifiers now start a video-only recording at
cartridge startup. Recording forces complete raw frames even when the host
would omit painting one. CPU/VDP clocks, sprite limits, input schedules and RGB
comparisons are unchanged. The ignored proof directory retains `scanout.avi`.
Headless component checks do not require recording.

A diagnostic replay of the HUD-off v61 cartridge changes its stale post-Home
screenshot from a failure to an exact match across all nineteen images, while
`motion.bin`, `cache.bin`, `events.bin` and `ticks.bin` remain byte-identical.
Waiting an arbitrary extra two milliseconds did not fix the stale image and
was rejected. Official verifier reruns and accepted-reference regression
results are recorded with the checkpoint evidence.

## Evidence scope

HUD-on v61 passes 1,600 original movement/cache states and 44 full RGB images,
plus the natural contact/pause/death/restart/Home route with 493 cache states
and nineteen RGB images. Its maximum main interval is 17.284599 ms, inside
the unchanged 16.687875 ms period plus 0.6 ms tolerance. Pending radar work is
bounded to sixteen refreshes; the observed maximum is four. These results
validate the one-enemy experiment, not additional enemies or a completed #11.

ROMs, original-derived assets, recordings and captures remain ignored under
`references/`. Only authored tools, documentation and synthetic fixtures may
be committed.

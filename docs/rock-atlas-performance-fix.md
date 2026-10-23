# Stage 01: fix the first measured regression before adding collision

Candidate `11-r01-rocks-v1` adds two bitmap rocks from isolated original placement
outputs. Source selection passes 28,672 original Z80 redraw comparisons; the MSX
cartridge passes 53 full-map RGB captures and 19 focused edge/eviction/reversal
captures. No extra sprite slots are allocated.

The 1,600-state movement regression fails its existing timing gate at a main-loop
refresh interval of 20.821 ms, versus the 19.937 ms display period and unchanged
0.6 ms tolerance. Both rendered and separate headless real-VDP runs reproduce it.
Do not relax the threshold, skip the offending frame, or add collision/death yet.

The new scenery needs 37 unique tiles, exceeding the old 32-tile atlas row.
Version 1 adds per-tile index masking and second-row Y calculation to every
streamed tile. The focused fix is to store precomputed atlas source X/Y bytes in
the immutable world-ID banks, removing that calculation from the hot path.
This trades 32 KiB of cartridge space for simpler runtime addressing, while
retaining exact pixels, tile jobs, simulation, sprite ownership and VDP copies.
It requires no extra RAM and stays within the existing 1 MiB cartridge capacity.

Validation:

1. Keep v1 and the accepted stage 00 ROM immutable for comparison.
2. Independently test second-row atlas coordinates and bank-boundary addressing
   with synthetic fixtures.
3. Build v2; rerun the same movement, GPU-count, complete-map and focused rock
   scenarios. Verify original movement states and no extra rock sprites.
4. Compare identical input schedules and command counts. Publish exact timing
   and full-image results, including scene reloads separately from steady play.
5. Advance to collision only when the original timing and pixel gates pass.

The source-X/Y version removes the main-loop failure (maximum 19.960 ms in the
same replay) but exposes a footer IRQ interval of 20.570 ms, still beyond the
unchanged gate. A pending raster now receives service immediately before each
indivisible VDP status/command transaction; no control-port latch is open at this
point, and the renderer ISR preserves the mapper and tile registers. This splits
the interrupt-masked window without changing tile budgets or simulation.

Status: fixed and verified in `11-r01-rocks-v3`. Main-loop maximum interval is
20.052 ms and footer maximum is 20.445 ms, within the unchanged gates. The exact
1,600 movement records and per-frame GPU command counts match the stage 00
control (median/maximum 22 commands in steady frames). Full RGB verification:
33 moving-car images, 53 complete-map images and 19 focused rock images; the
HUD-off version also passes 1,600 states and 34 moving-car images. No extra rock
sprites and no VRAM timing violations. This was a rendering integration
regression, not original rock-collision logic, which is still absent.

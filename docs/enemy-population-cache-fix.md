# Population experiments: keep prefetch queues in one vertical cache window

The compact radar exposes two separate failures. A long SAT transaction delays
the header split; short atomic SAT packets and interruptible RAM preparation
remove that large first-row fault. A remaining 8x8 maze difference is unrelated
to native gameplay: original motion snapshots are byte-identical across the
failing candidate and the earlier control.

The visible-cache comparison first fails at frame 572, camera (566,722), local
row 150. Trace the underlying physical byte `$341b`: both builds overwrite it
at frame 522 with world tile (70,77), aliasing tile (70,109) in the 32-row ring.
The control rebuilds row 109 at frame 524. The candidate never queues that row.

On upward movement followed by an immediate downward reversal, a row job can
still be pending for the preceding tile. `previous_y` therefore remains 81,
while a new column is seeded from the camera's transient tile 80. That column
writes rows 77..108 and destroys row 109. On returning to tile 81, the row queue
sees its own unchanged anchor and does not repair row 109. Timing changes decide
whether this latent cache-ownership bug occurs.

Stage 09 fix plan:

1. Seed each column from the row queue's committed/queued `previous_y` anchor.
2. Use that same anchor for the vertical cache write bounds, updating it when
   a new row job is queued. Keep initial loading based on the camera.
3. Retain the 32-row ring, 48-column width, guards and complete viewport.
4. Rerun the exact reversal/contact route with full cache and RGB checks,
   then the standard route and component proofs before adding another enemy.

The stage 08 reference remains byte-identical. This change neither skips native
ticks nor relaxes graphics or raster acceptance. Compact-radar marker composition
has an independent actual-assembly proof of 16,416 clip/color/sentinel cases;
that component result alone does not establish moving gameplay acceptance.

The consistent-window candidate passes all 1,138 cache states, but short
non-interruptible uploads still shift the first maze rows. Reducing packets to
four bytes adds enough address/setup work to starve prefetch (frame 288).
The next transfer design preserves a software source/destination pair while
allowing interrupts between OTIR iterations. The ISR restores the interrupted
VRAM write pointer from actual HL progress after its own VRAM work. Validate
interrupted transfers explicitly, then repeat complete display/cache tests.

The transfer component passes 2,048 lengths/offset cases with 207 actual raster
interrupt overlaps, including VBlank, header and footer/guard phases. Source,
destination, stack, every destination byte and surrounding canaries match;
maze VRAM and native RAM remain unchanged. The control-port latch is protected
with DI, while source/destination/count preparation and OTIR permit interrupts.

The accepted one-enemy v61 continuation runs at 60 Hz with the original
16.5 ms simulation rate. It sends the first twelve radar attribute bytes before
actor work and the remaining coordinates afterward. Optional radar uploads use
the line 80..144 window; cache work closes at line 202. Atomic wait decisions
avoid a lost-interrupt/HALT race, and status polling removes a redundant control
transaction per tile. The cache uses forty columns with four horizontal guard
tiles; both queues draw visible tiles first, then wrap to their guards. See
[the raster and capture contract](raster-deadlines.md).

Both HUD modes now pass the natural contact/death/restart route (493 cache
states / nineteen RGB images) and the longer 1,600-state movement control
(44 HUD-on / 35 HUD-off RGB images), including the entire right edge. The
unchanged timing and pending-radar limits pass. Stage 08 retains scanline 196
and its exact ROM bytes. Two-enemy moving acceptance remains open; the new
[solid-run experiment](solid-cache-runs.md) addresses its measured cache cost.

Flag removal now selects one of four precomputed 32-byte base masks for each
radar cell. This board has at most two flags touching any cell, enforced during
the build. The 1,536-byte table occupies the unused second half of the existing
radar lookup bank; no extra bank, RAM, VRAM or sprites are required. Every one
of 1,024 flag subsets across all twelve cells passes actual-assembly comparison
against independent pixel geometry (12,288 cases). This avoids scanning and
plotting all twenty HUD flag slots on each cell rebuild.


## Two-enemy continuation: queue pressure and exact strips

The current two-enemy HUD-on experiments are still unaccepted. Making the
horizontal queue/window use the queued `previous_x` anchor, like the vertical
queue, does not by itself restore moving correctness. A trace shows a pending
row being overtaken by the actual viewport; RGB can fail before the end-of-loop
cache snapshot becomes wrong because a repair finishes after scanout.

The exact-strip path now preprocesses mixed 24x8 / 8x24 candidates into spare
bits of the existing source-address tables. Runtime skips ineligible strip
attempts; exact uniform spans keep HMMV. Flag owners are excluded. Source-X
bit2 marks horizontal candidates and source-Y bit0 marks vertical candidates;
both bits are removed before ordinary atlas copies. Solid-run comparisons ignore
the horizontal tag. No pixels, game rules, RAM, sprites or ROM banks are added
by these candidate bits. The strip atlases themselves use 7 KiB of spare VRAM
and three ROM banks, documented separately in the build metadata.

V105 at 50 Hz with a 36-column cache passes 411 actual strip/canary cases and
5,120 solid/canary cases, including neighboring candidate tags. It still fails
moving RGB, and the first end-of-loop cache failure is frame 447 at the right
edge. Its explicitly experimental checkpoint is `11-r09-strip-tags-50-v105`;
it does not replace the accepted `LATEST` two-enemy HUD-off cartridge.
The normal stage08 HUD-on/off builds still reproduce the original v25 hashes
with current source; all 308 tests passed before the two candidate-tag tests.

A tested native camera-multiplication replacement preserved all 2,643 original
states but increased median component cost from 16,998 to 17,084 cycles. It was
removed. Lower-frequency radar composition, a wider cache, merged scenery colors
and red enemy silhouettes also failed moving acceptance; none was promoted.

The next scheduling experiment produces radar payloads after terrain's raster
deadline, then publishes them in the next refresh's safe radar window. Initial
blank-screen preparation remains complete. It reserves an earlier terrain stop
for the bounded marker producer and preserves the existing sixteen-refresh
marker limit, original 16.5 ms simulation clock and full RGB/timing gates.
This experiment needs complete moving validation before acceptance.

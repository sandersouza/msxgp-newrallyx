# Bound compact-radar work per refresh

The current v115 checkpoint separates the player's 2x2 point into one
higher-priority hardware sprite. The twelve cells retain the dynamic flags,
frame and enemy markers; player movement no longer marks or renders cells.
Resident normal/shifted point masks avoid per-position pattern uploads. Four
SAT bytes follow the player each refresh, and three color bytes change only
when the original eight-native-tick white/black blink changes. The compact
coordinate table now contains sixteen entries per scroll phase (16 KiB).
The one-enemy 50 Hz contact and long-control routes pass; see
[checkpoint evidence](checkpoints.md). The preceding scheduling experiments
below explain the remaining cell queue, not a claim that multiple enemies with
HUD have passed. With two enemies the new marker can produce nine candidate
sprites on a seam scanline; the strict verifier rejects that configuration.

The twelve-cell renderer passes its exhaustive mask/color component tests,
but a natural movement frame can rebuild three cells in about 5.5 ms. Combined
with original resampling frames that execute two ticks, this delays radar
publication and removes the time needed for maze prefetch.

The display adapter will render at most two marker cells per ordinary refresh,
retain dirty cells and scan them in round-robin order. Two-tick refreshes queue
marker changes without drawing them; paused updates retain the two-cell budget,
while initial preparation can drain all cells. Flag-base rebuilds retain their existing separate bounded queue, and
marker composition skips cells already queued there to avoid duplicate work.
Numeric publication can wait until the next ordinary refresh when two native
ticks execute. Gameplay, collision and score values still update immediately.

This intentionally permits short radar-marker and numeric display latency.
Store the exact marker coordinates and flag subset published for each cell,
then compare full RGB against independent original geometry for those display
snapshots. Do not infer drawn state from the newest native positions or VRAM
output. Record dirty-cell backlog/age and verify it drains; do not claim an
unbounded queue is acceptable. Measure the complete cache and timing routes
before adding the next enemy.

The fixed positions and sentinel phases of the twelve radar and three fuel
entries now use a 15,360-byte ROM table covering all 256 vertical scroll values.
This removes repeated coordinate construction before every header. It costs
one ROM bank and no additional sprites, VRAM or runtime RAM; the cartridge
remains 1 MiB. The life footer retains its existing small RAM preparation.

Composition now writes a per-cell RAM payload. At the beginning of the following
refresh, before actor preparation, at most two ready payloads are uploaded. This
keeps pattern/color changes ahead of the first radar scanline instead of racing
an already scanned cell. Predicted two-tick frames retain ready work; initial
blank-screen preparation drains it completely. Published marker/flag snapshots
advance only after upload. Both composition and upload use round-robin cursors,
and the continuous queue trace includes dirty, flag-base and ready masks.

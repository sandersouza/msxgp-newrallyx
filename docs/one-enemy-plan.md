# Stage 08: one original enemy

Stage 07 is accepted; keep its checkpoint immutable. Add one enemy through
separately verifiable hardware adapters, never start the full arcade loop.

1. Move the existing command atlas from fixed ROM into the unused final 4 KiB
   of the player data bank. Map it only for atlas initialization. The same bytes
   occupy the same VRAM address; stages 00–07 must remain byte-identical. This
   frees fixed-bank space for the bounded host adapter without new RAM/banks.
2. Retain original enemy initialization, movement in `$0069`, facing animation
   in `$1ddf`, AI `$0cd6`, and original sprite registration/visibility. Keep the
   original six-entry virtual sprite list (player plus up to five enemies).
   Retain camera-coordinate update prefixes while returning before old bitmap
   redraw. Link the source RST-10 helper with a guarded bank-local trampoline.
   A component oracle must compare selected original state, visibility and
   collision boundaries before integrating presentation.
3. Render the first registered enemy with the same 16x16 masks as the player,
   using its original red/navy/black lookup through two mode-2 planes. Reserve
   palette indices 6/10 with black at their OR=14, translating scenery indices
   without changing RGB. Reuse previously unused pattern numbers 0..15. At the
   hardware-reserved SAT Y=216, permit a documented one-pixel upward presentation
   bias; world coordinates and collision rules remain unchanged. Measure sprite
   count/per-line occupancy and assert the original pixels at the declared draw
   coordinates. Publish the real enemy radar position instead of the fixture.
4. Use the original player/enemy collision comparison, feeding the established
   explosion/life state. Freeze AI while dead/paused/lucky, reinitialize enemies
   on life restart, and hide the colliding enemy. Verify near misses, a real
   keyboard collision, pause/restart, cache persistence/right edge and worst
   simultaneous HUD/flag/fuel work. Keep a renderer-only control if needed to
   distinguish logic from pattern/SAT publication costs.

Record the first timing/sprite failure, fix its measured cause, and rerun the
affected gates before adding a second enemy. Source post-flag parameter dispatch
must be scoped explicitly; do not silently mix an enemy-count/difficulty change
into a renderer performance measurement. The current rock-placement fixture
remains labelled until the final normal-stage transition component replaces it.

## Accepted stage 08

Checkpoint `11-r08-enemy-v24` (HUD) has SHA-256
`f6ab4d7fa99016385228cfc76fbf45f793ffa8061d6933cdfd9221bbfa566830`.
`11-r08-no-hud-v24` has SHA-256
`d54af864a8d6a6f354e0a21dde49068ab857192e135c51747f8ad75f7e585455`.
Evidence is sealed below `references/build/issue11-r08-*-v24*`; all original
data remain ignored. Exact enemy cases: 2,643. Exact presentation cases: 1,928.
Both keyboard runs verify 1,138 cache states, 28 complete RGB images, one contact,
40 paused refreshes and the exact 120-tick hold/restart. Standard render-only
controls verify 1,600 states and 38/36 images before applying intentional death.
Sprite allocation is 21/32, with continuous line peaks eight/four (HUD on/off).
All 302 tests pass and stage 07 remains byte-identical.

The declared MSX adapter clips one enemy sprite row at screen y11, where sprite
enable/prefetch crosses the header split; bitmap pixels there remain checked.
It retains every other source mask pixel and world/collision coordinate. The
existing SAT-Y=216 one-pixel bias remains. This is an explicit presentation
tradeoff, not an RGB comparison exclusion. See the performance report for the
measured regressions, repaired interrupt windows and real deadline scheduler.

The user clarified that the blue request applied to the radar, not the score
header. Stage 08 v25 restores the black score header and a square white radar
border, changing only graphic resources. The radar remains transparent: a solid
blue background at its current dimensions needs another sprite layer or work
during scrolling, violating the zero-additional-cost constraint. Executable
bytes, symbols and sprite allocation remain unchanged.

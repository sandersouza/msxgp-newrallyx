# Experimental cosmetics and optional test controls

Keep all changes in the full-session experimental build. Preserve the functional
13 audio build and the older first-stage cartridge. No gameplay asset reduction.

1. Capture the original arcade boot, including its timing, artifact/character
   progression and final matrix. Reproduce the original timeline (superseding
   the earlier1.5x request), with any-key skip in a cold startup path;
   boot resources must not consume active-frame CPU budget.
2. Use a centered4x5 FUEL label. Symmetric2x2 red endpoints, six1x1 yellow
   ticks and a2x3 red center align with the48px bar. Yellow ticks use the
   existing three fuel sprites without new sprite slots. Small white ROUND and
   its number use the same font. Select compact/classic through the HUD include
   contract; broader extraction is backlog-only in issue #32.
   Remaining fuel is anchored on the right. Blank leading score digits while
   keeping numeric values, saturation and event-based refresh intact.
3. Shift the complete cast presentation up8px. Center the single-line terminal
   caption `[5] insert coin - [1/2] start player(s)` at y186, without reversed
   text; only5 and1/2 blink. Copy the original arcade namco tile block without scaling:
   56x8 at100,200, centered with exactly four rows of bottom margin. Optional MSX logo
   include: uniform3:1 reduction,54x20, top/right margins8px.
4. Add a falling low-frequency body to the cached explosion while preserving
   smoke and engine. Verify PCM headroom and low-band energy; user accepts timbre.
5. TEST_MODE=0 by default; TEST_MODE=1 enables edge-triggered Enter next-round
   and = invulnerability. Walls stay solid, flags/fuel/score remain active.
   Ship distinct normal/test cartridges and test both build configurations.
6. Validate independent pixel/SAT contracts, numeric/fuel boundary cases,
   startup ordering/timing, test-key hold/release behavior and collision policy.
   Run the integrated suite and three-moving-enemy cycle profile. Refresh the
   ledger/workbook and export ROMs with hashes and clear build-mode metadata.
7. Keep the world S red and fixed; only its radar point blinks. Cover L-before-S
   collection with a stationary radar case. Restore native181B/1885 enemy stone
   reactions, using one spare navigation bit and no new RAM; compare404 fixtures
   with original arcade execution and verify64 navigation tag/exit pairs.

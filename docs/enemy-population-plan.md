# Stage 09: progressive enemy population

Keep the accepted stage 08 v25 ROM immutable, including its black score header,
square white radar border and fourteen radar sprites. Increase the diagnostic
population one car at a time; do not infer a whole-game speedup from logic-only
measurements. The original first normal round uses one enemy; larger counts
exercise the later-round pressure before transition integration.

1. Execute the selected original initializer, movement, facing, AI, visibility
   and collision routines with two enemies. Compare every native descriptor and
   virtual-slot pointer with the original Z80 component. Publish a clearly
   labelled logic-only checkpoint.
2. Add the second exact two-plane enemy presentation, including its real radar
   marker, independent clipping/cache state and collision visibility. Share
   preloaded facings and reserve separate victim patterns. Preserve the existing
   single-enemy source and stage 08 ROM.
3. Measure full RGB/cache output, original behavior and continuously count actual
   sprite Y coverage, including transparent rows. Keep the standard CPU, real VDP
   timing and unchanged raster gates. Identify the first population/phase that
   exceeds either CPU or eight-sprite-per-line limits.
4. If the two-plane presentation exceeds a limit, write down that failure before
   adapting graphics. The user's approved color-reduction fallback may preserve
   original 16x16 silhouettes/world coordinates with fewer planes. Do not omit
   an active enemy or silently disable hardware sprite limits.
5. Repeat after each accepted increment up to the original population needed by
   the bounded gameplay slice, then proceed to smoke and completion/start.

The renderer may unroll the authored single-enemy presentation for the first
two-car experiment. Explicit generation guards must fail on template drift;
native routines still execute once for the full population. This avoids adding
a per-pixel CPU renderer while measuring the incremental cost. Extra generated
cartridge data remains ignored under `references/`.

First result: the two-enemy selected-original component passes the same 2,643
state/contact cases as stage 08. This is independent component evidence, not
acceptance of a two-enemy playable cartridge. Evidence:
`references/build/issue11-r09-two-logic-v1-enemy-check/report.json`.

# Three-enemy active performance pass

Authorized scope: approach30FPS during action with three actual native enemies,
preserve the existing graphics, remain on codex/fixed-hud-lab, update the cycle
workbook and supply a runnable ROM. No commits, publication or new visual loss.

Baseline: ca9e6ae67f823404618cdcf237c134539c7e436050a642d0555b21baaebebd48,
30.96 aggregate and26.07 active-onlyFPS on the existing keyboard policy.
The immutable baseline bundle is stage-one-3-enemies/baseline-ca9e6ae6.

1. Split the largest measured owners into actionable work: native/host logic,
   name publication, radar and sprite preparation. Keep inclusive/self distinct.
2. Test exact optimizations independently against the assembled baseline; retain
   native ticks, AI, whole car graphics, fixed HUD and hardware sprite limits.
3. Integrate only measured wins, repeat the input-only navigation and smoke
   workload, active VRAM/VDP timing/publication and real multi-car verification.
4. Report active-onlyFPS, tails, calls/frame and remaining budgets with exact ROM
   hashes. Preserve previous evidence and rebuild the existing workbook/ROM.

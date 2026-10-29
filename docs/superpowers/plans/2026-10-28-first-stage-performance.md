# First-stage performance optimization

User scope: approach30FPS throughout stage one, preserve current graphics and
keep all work on`codex/fixed-hud-lab`. No commit, push, production checkout or
new graphical concessions are authorized.

1. Retain the current ROM and obtain a complete-route nested cycle ledger with
   a control run. Distinguish active movement, death hold, completion and waits.
2. Optimize independent measured hot paths: game-only ring/name publication,
   actor preparation, and repeated sparse-effect/radar processing.
3. Keep the exact terrain, palette, car drawings, HUD and authorized effect
   patterns. Compare active VRAM and native state against independent oracles.
4. Rebuild only this experiment; repeat complete keyboard stage, smoke/heavy
   cases, port spacing and publication-within-VBlank checks after integration.
5. Update full-route/per-routine evidence and workbook with workload scope,
   ROM hashes, inclusive/self costs, tails, synchronization and remaining limits.

Baseline actual ROM:47e0112b69428665588ebed838b4ea72fb490b1c2bcbad785250542b78348e88.
Baseline full route:1438presentations/61.291140913s,23.445476FPS,ten flags,one death.
No speedup will be inferred from a different death/hold distribution alone.

## Verified checkpoint

Complete-route profile captured before/after, with matched control runs. Native
keyboard route still collects all ten flags, loses one life, restarts, receives
remaining-fuel bonus and stops. Aggregate23.45→35.43FPS; active-only23.32→34.10FPS.
P95 presentation66.75→34.17ms, with rare100.91ms intervals still present.
Seven source graphic payloads remain byte-identical; independent entire-panel
pixel checks and exact actor/terrain/effect VRAM contracts pass. Ring8960cases,
actor1048cases, sprite1163cases and generated radar65536phase/mask cases pass.
Publication remains withinVBlank in the fullroute and stress probes. The original
free-camera ROM retains SHAe1d5a44c743b62241351c44959fd047a65f0fbe230f1b49a4f1006c6c40c64cc.

`make run-experiments` corrected to the playable stage; previous camera-only
commands are preserved under*-hud-lab targets. All changes remain uncommitted
on the experiment branch. No graphical concession or recurring pause added.

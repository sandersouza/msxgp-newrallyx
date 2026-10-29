# Event-driven display performance implementation plan

> **For agentic workers:** Use the scoped implementation and independent verification workflow. Keep all work uncommitted on `codex/fixed-hud-lab`.

**Goal:** Reduce the measured three-enemy active-frame cost toward nominal NTSC 29.97 FPS while preserving the current graphics and native game rules. Track the measured two-refresh cadence separately.

**Architecture:** Retain native event producers and introduce or improve display caches around their outputs. Keep scroll compensation independent of logical value changes. Measure each candidate against the frozen 697232c9 ROM and keep only verified savings.

**Tech stack:** Z80 assembly, Python synthetic/openMSX differential probes, artifact-tool cycle workbook.

**Authorization:** The user explicitly delegates selection and implementation of the supplied optimizations. No additional graphic reduction is authorized. Event pauses are not introduced by this pass.

## Constraints and decisions

- Preserve flag S/L semantics, bonus timing, high-score and extra-life side effects, restart behavior and input.
- Keep HUD enabled, SCREEN 4, complete original car graphics and real sprite limits.
- Round and score values may be cached on changes. Do not replace native high-score storage with an alias if original routines require a separate stable value; a display alias is safe only with proved comparison/lifecycle equivalence.
- Fuel presentation may be cached by visible value; preserve native consumption and rewards. Prefer exact quantization over reduced visible cadence when cheaper.
- Radar already uses character patterns for actor dots. Explore avoiding duplicate preparation/transfers for unchanged actor cells and phase/table state, including restoration of old dots and collected flags.
- PSG already skips unchanged registers; retain existing output unless an additional cache proves an end-to-end gain without altered audio.
- Keep a frozen ROM/source baseline under ignored references. No commit/push, no changes in functional branches.

## Tasks

- [x] HUD cache: 3,333 differential cases; field-specific decoding, packed-value filtering, narrow sentinel repair and unchanged-SAT skip. Original counters and graphics preserved.
- [x] Radar: repeated-phase/payload caches were considered but phase changes limited their benefit. Keep the measured stateless exact uniform-source fast path instead: 11,264 differential cases, no new RAM or transfer suppression.
- [x] Audit event and PSG paths. Original score/S/L/HI and bonus rules retained; music already uses prepared notes and changed-register output. No speculative new audio queue or fuel cadence reduction.
- [x] Integrated three-enemy build, natural240/smoke480/route1211 checks; no final-publication writes outside VBlank; all original graphics identical. Native worker changes outside resident code are only three relocated CALL/JP operands, verified against symbols.
- [x] Centralized native-VDP deadline ledger identifies 93/875 late frames in the first cache pass. Added a measured 47-byte burst transfer helper to the shared static-HUD/boundary packet worker; all512 isolated full-VRAM cases and the integrated route/control pass.
- [x] Final matched-control profile: 889 active frames, 28.890890 FPS, mean work23.336411ms. Baseline848 frames,27.543138FPS,25.229105ms. Current70/889 late publications; no claim of stable29.97 FPS. Updated component/cycle ledgers with nominal target29.97 and physical two-refresh cadence29.961372; deliver the ROM with `make run-experiments` defaulting to three enemies.

## Follow-up: late-frame critical path

- [x] Preserve a5d318eb ROM and authored adapter sources before edits.
- [x] Keep exact edge pixels while stabilizing boundary character/color identities.
- [x] Decode smoke world Y once per row and reduce overlay loop saves.
- [x] Move unrolled metadata stores into unused ROM; preserve all RAM/VRAM results.
- [x] Validate three moving enemies, smoke, contact death and restart with hardware sprite limits.
- [x] Refresh both workbooks and deliver test ROM12e32699 on the experiment branch.

Measured result: 28.890890 -> 29.183373 active FPS; 23.336411 -> 22.802823 ms
mean work; 70/889 -> 54/898 publications after more than two refreshes. This pass
does not achieve stable29.97 FPS. Exact paired probes and integrated active-VRAM
checks pass; no graphics reduction or inserted pause. The route ends at native
game over rather than demonstrated stage completion.

## Follow-up: HUD transfers and sprites

- [x] Preserve12e32699 and its adapter sources; retain graphics/native rules.
- [x] Compile exact HUD transfers; stable glyph identities fit50 existing slots.
- [x] Treat preceding inactive slots as unknown; prove all8320 transitions.
- [x] Accelerate signed bounds, caches, fixed slot dispatch and vertical/sentinel copies.
- [x] Prove3147 sprite cases and bind the compiled clipped helper to the cartridge.
- [x] Add mapper identity to Page2 profiling; refresh both cycle workbooks.
- [x] Generate299b5380 test ROM; record calculated50Hz cadence separately.

Measured active result:29.508353FPS,22.202671ms mean CPU work,38/908 late
publications. P95 interval34.595179ms; stable29.97FPS still pending. ROM grows
864KiB with no new RAM. No graphical concession or inserted pause.

## Review focus

Score carry across HI/extra-life thresholds; S/L rewards; changes during fuel bonus;
restart/game-over/stage lifecycle; sentinel Y shifts and invisible buffer reuse;
actor overlap/separation and flag erasure on radar; audio interruption and restart.

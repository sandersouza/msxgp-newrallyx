# SCREEN 4 First Stage Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the inline integration. Independent audio and sprite adapters have narrow delegated ownership.

**Goal:** Produce a playable, measured first-stage cartridge using the accepted fixed side HUD and existing native gameplay rules.

**Architecture:** Keep the laboratory cartridge and functional branches intact. Add a separate gameplay cartridge with the persistent SCREEN 4 ring, selected original Z80 routines, existing MSX enemy decisions, PSG adapter and complete native hardware sprites. Dynamic HUD values replace laboratory build inputs.

**Tech stack:** Python builders, sjasmplus, ASCII16 cartridge, V9958 SCREEN 4, openMSX, native contributor-ROM fixtures.

**Spec:** User request in this chat: reuse developed code for a playable first stage in the accepted new layout, aiming near 30 FPS.

## Constraints and review focus

- Work only in `codex/fixed-hud-lab`; no commit/push or edits in functional worktrees.
- Preserve source asset dimensions and game world/rules. Existing SCREEN 4 scenery conversion, fixed left mask and right-edge band remain laboratory-only approvals.
- Keep HUD enabled. RND saturates at 99, scores at 999999, life icons at four, without clamping native state.
- Keep real sprite limits and complete selected car drawings; document culling and pathological costs.
- Keep original/derived data under ignored references directories.
- Measure complete guest-time costs, not host elapsed time, and keep physical refresh/presentation/logic rates distinct.
- Check repeatable start/restart, no flag resurrection, special/lucky scoring, fuel/smoke, collision/death, clear/game-over and live PSG events.

## Tasks

- [x] Native state and asset bridge: validated seed, selected native code bank, geometry/navigation, flags/rocks, palette permutation preserving RGB, safe RAM allocation.
- [x] Gameplay clock/input: bounded elapsed native ticks, movement, MSX enemy AI, collision, smoke, score/fuel and life transitions using existing rules.
- [x] Dynamic presentation: side HUD sprite fields, flag/enemy/player radar, persistent tile repairs for flag/smoke/death changes, coherent sprite/background publication.
- [x] Separate build/run targets and first-stage playable cartridge; retain the original free-camera lab.
- [ ] Verify actual gameplay paths and native state transitions in openMSX, strict VRAM timing, full-frame motion, original actor pixels and PSG output.
- [ ] Measure natural/flag-heavy/enemy-heavy routes, update cycle ledger/workbook and report scoped results with remaining limits.

No step authorizes committing, merging or publishing.

## Execution checkpoint

- Native-only reproducible 1,200-tick execution and PSG register differential passed.
- Hardware car/HUD adapters have synthetic Z80/VRAM evidence; integrated synthetic-effect
  assembly fixture boots, moves, and retains its screenshots/RAM/VRAM/cycle records.
- First natural integration fixture measured 26.44 FPS over 89 intervals after radar/ring
  optimization. This is not final original-effect gameplay performance evidence.
- Active first-stage build is intentionally blocked by three-color original smoke and
  explosion rows. A concrete 23/576 and 37/576 pixel adaptation proposal was shown;
  the user's additional graphics authorization is pending. No adaptation is applied.
- Free-camera laboratory rebuilt independently; keyboard regression passed.

A longer 116-presentation moving route measured 28.96 FPS, mean 25.36 ms work and max 87.20 ms. Tail scheduling remains unresolved; final effect graphics are still pending. A scoped cycle workbook is exported under outputs/first-stage-fixture.

## 2026-10-28 authorized-effect checkpoint

User authorized smoke/explosion conversion only in this experiment, preserving
24x24 dimensions and final visual acceptance. Actual ROM built successfully.
Keyboard-only stage-one completion:1438presentations,61.291s,10flags,one death,
retained collected flags,restart and remaining-fuel bonus; Game_State=2.
Independent active-VRAM checks cover terrain/effects,HUD,and complete car masks.
Publication instrumentation reports0VDPdatawritesand0commitexitsoutsideVBlank
throughout this route. The short moving profile is29.21FPS; the entire phase is
23.45FPS. Stable30FPS,physicalhardware,and an all-frame pixel scanout oracle are
not complete. Test/run/profile targets and updated cycle workbook are available.

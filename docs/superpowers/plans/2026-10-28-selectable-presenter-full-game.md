# Selectable presenter and complete gameplay

User scope: retain original-size graphics and the measured fixed-HUD work,
reduce the remaining late frames, and reach the same session/mechanics scope as
enhancement/13-psg-audio without merging either branch into main now.

## Architecture and acceptance

- Keep the reference build independently reproducible from its exact Git
  revision. Its authored source may be staged in an ignored build workspace;
  contributor ROMs/assets are linked locally and never downloaded or committed.
- Keep experimental targets in a separate make fragment. Shared production
  build definitions remain compatible with the audio branch.
- Use shared native rules, session state and UI/audio producers through explicit
  interfaces. The fixed presenter owns its display tables, sprite preparation,
  caches, timing and mode transitions. Avoid a second persistent rules fork.
- Preserve the first-stage benchmark and its ROM before changing session scope.
  Measure active gameplay separately from UI, transitions, death and bonuses.
- Verify cast/select/start/game-over/challenge screens, credits, one/two-player
  turns, restart, round progression, S/L flags, bonus lives, input and audio.
- Keep both build choices and their ROM paths documented. A reference build
  passing does not establish experimental feature parity.

## Work

- [x] Freeze299b5380 and inventory parity against13-psg-audio.
- [x] Add independent source/build selection and conflict-conscious make layout.
- [x] Optimize the remaining late-frame critical path with exact output probes (38 ->16 late publications).
- [x] Integrate shared session/UI/audio and native round/mechanics adapters.
- [x] Verify controlled feature coverage and an active three-enemy sample in the emulator.
- [x] Refresh cycle/scheduling workbooks and deliver selected test ROMs.

User scope decision2026-10-28: close the optimization/ROM/workbooks now; full
gameplay integration was deferred, then explicitly authorized in the next request.
The full-session pass is now implemented; controlled coverage and timing limits
are recorded in experiments/fixed-hud/FULL-SESSION.md. Full-course performance
and final visual/audio acceptance are not established by the short sample.

No merge, commit or push is authorized by this plan. The user subsequently
authorized adapting55/576 pixels of24x24 stones only in this experiment.
Final visual and timing acceptance remains with the user.

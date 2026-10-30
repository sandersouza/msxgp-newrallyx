# Selectable cartridges and integration boundary

Both maintained presenters build from the current checkout after PR #33 was
merged on 2026-10-29. Earlier branch-isolation/merge-boundary records remain
historical evidence; those branch names are not build prerequisites.

| Command | Cartridge | Scope |
| --- | --- | --- |
| `make build` / `make run` | `references/experiments/full-session-64k/fixed-hud.rom` | Default64 KiB optimized SCREEN4 gameplay with shared SCREEN5 UI; emulator RAM=64 KiB |
| `make build MAPPER=1` / `make run MAPPER=1` | `references/experiments/full-session/fixed-hud.rom` | Preserved128 KiB mapper-RAM profile; emulator RAM=128 KiB |
| `make build TEST_MODE=1` / `make run TEST_MODE=1` | `references/experiments/full-session-test-64k/fixed-hud.rom` | Separate Enter/equals developer controls; solid walls; add `MAPPER=1` for128 KiB |
| `make build LEGACY=1` / `make run LEGACY=1` | `references/build/newrallyx.rom` | Maintained SCREEN 5 presenter built from `src/screen5/`; lowercase `legacy=1` is accepted |
| `make build-experiments` / `make run-experiments` | `references/experiments/full-session-64k/fixed-hud.rom` | Aliases of the default 64 KiB full session; `MAPPER=1` selects the 128 KiB counterpart |
| `make build-audio-reference` / `make run-audio-reference` | `references/experiments/audio-reference/newrallyx-audio.rom` | Independent production SCREEN5 presenter, audio and point inscriptions enabled |
| `make build-first-stage` / `make run-first-stage` | `references/experiments/stage-one-3-enemies/fixed-hud.rom` | Preserved isolated first-stage performance workload |
| `make run-hud-lab` | `references/experiments/fixed-hud/fixed-hud.rom` | Earlier free-camera renderer probe |

The shared integration source and default reference are pinned to
`6d562a791b0cc242119a31dd686ff8e93eb94fe0`. The reference SHA256 is
`e95a4a803c0ac3d0096b7021c877a56086d09d6ba8ed307dde7a8d039198537c`.
Its cast, selection and start were observed to work. The earlier startup report
for 9aca80a remains historical evidence, superseded by this selected revision.

`AUDIO_REFERENCE_REVISION=<local-git-ref>` changes only the independent reference
comparison. Updating the integration pin requires rebuilding and revalidating its
adapters. Only authored Git sources are exported to an ignored source view;
contributor inputs are linked locally and private build output stays under
`references/experiments/`. No ROM is downloaded or added to version control.

## Shared rules, separate presenters

The [64 KiB profile](../../docs/ram64-variant.md) is the default; `MAPPER=1`
selects the preserved128 KiB version. The functional64 KiB
storage adaptation is outside the frozen module-layout profile: do not relabel
its changed bytes/symbols as a structural-only modularization.
`make verify-module-layout` checks the frozen128 KiB counterpart, including its
matching test/classic/hardware-check configuration. Both cartridges use ASCII16.
The old `RAM_KB` flag is replaced by `MAPPER`; obsolete use fails with guidance.

The optimized build reuses the selected revision's UI, session/turn management,
four-way input policy, native round/object preparation and PSG worker. Generated
adapters replace hardware producers, not game rules. SCREEN5 menus run outside
active gameplay; returning to SCREEN4 rebuilds the four pattern sets, independent
name tables, flag caches, sprites and HUD state. Native difficulty and enemy
counts progress normally; `ENEMIES=3` is a first-stage diagnostic option only.

Authored optimized sources and targets remain under `src/screen4/`.
The root Makefile selects the default or legacy path and includes `targets.mk`.
Current `src/screen5/` helpers also feed generated optimized adapters; do not remove
them merely because their legacy presenter is optional. The earlier read-only
three-way Makefile probe and changed-path inventory are recorded in
`outputs/full-session/merge-boundary-proof.json` records the pre-merge layout,
not a validation of every future integration. Keep the pinned commit available
in local Git even after deleting its old branch. See
[the current source boundary](../../docs/architecture.md#build-ownership).

Unqualified `make run` rebuilds. `ROM=<path>`, `CHECKPOINT=<name>` and `LATEST=1`
select existing artifacts without rebuilding; LATEST belongs to the sealed
legacy build publisher. `ENEMIES=3`, `STAGE`, `FULL_GAME`, `AUDIO` and `HZ` are not
population/refresh overrides for the full optimized session: use the maintained
first-stage/legacy diagnostic paths as appropriate. The full optimized session
retains native population progression. Invalid `LEGACY=1 TEST_MODE=1` is rejected.

See [FULL-SESSION.md](FULL-SESSION.md) for coverage, memory requirements, timing
scope and remaining acceptance. The first-stage workbooks still refer to their
own cartridge; the maintained integrated workbook is [docs/cycle-budget.xlsx](../../docs/cycle-budget.xlsx).
Update it with `make timing-workbook` after matching timing measurements; older
workbooks remain under `docs/measurements/timing/archive/`.

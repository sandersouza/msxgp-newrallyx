# Selectable cartridges and integration boundary

Both presenters build from `codex/fixed-hud-lab` without modifying the functional
`enhancement/13-psg-audio` checkout. No commit, push or merge was performed.

| Command | Cartridge | Scope |
| --- | --- | --- |
| `make build-experiments` / `make run-experiments` | `references/experiments/full-session/fixed-hud.rom` | Shared sessions and native round progression with the optimized SCREEN4 presenter |
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

The optimized build reuses the selected revision's UI, session/turn management,
four-way input policy, native round/object preparation and PSG worker. Generated
adapters replace hardware producers, not game rules. SCREEN5 menus run outside
active gameplay; returning to SCREEN4 rebuilds the four pattern sets, independent
name tables, flag caches, sprites and HUD state. Native difficulty and enemy
counts progress normally; `ENEMIES=3` is a first-stage diagnostic option only.

Authored experiment sources and targets live under `experiments/fixed-hud/`.
Production `src/` and production build/run recipes remain untouched. The
Makefile has one optional include for the experiment fragment. The read-only
three-way Makefile probe and changed-path inventory are recorded in
`outputs/full-session/merge-boundary-proof.json`. This is a current text check;
future merges still need actual integration and runtime validation. Keeping the
pin reachable permits both builds after the branches are eventually merged.

See [FULL-SESSION.md](FULL-SESSION.md) for coverage, memory requirements, timing
scope and remaining acceptance. The first-stage workbooks still refer to their
own cartridge; the integrated ledger is `outputs/full-session/cycle-budget.xlsx`.

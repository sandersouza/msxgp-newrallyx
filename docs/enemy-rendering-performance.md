# Enemy rendering performance and fixed radar publication

This iteration addresses enemy-count scaling in every round, including stationary
challenge cars. It preserves original graphics, dimensions, colors, complete car
planes, source actor order, seven radar anchors, the HUD and real sprite limits.
It does not establish full-game speed parity with the arcade.

The qualified cartridge is SHA-256
`73657624a1d74f7fa595454886ce82f21259bd6b7535839ac0722950e5db625a`.
`make build` publishes this image at `references/build/newrallyx.rom` and
`latest.rom`; `make run` launches it. The sealed delivery bundle is
`references/build/default-62285febd96d4c8dbc70117afd0921ea/`.

## Changes and controlled costs

The complete-car adapter now accesses each 32-byte record through IX, replacing
repeated transfers to/from a shared scratch record. Pure preparation/radar code
runs in unused native-bank space, with a build guard against occupied bytes.
Five source virtual OAM pointers are decoded once when the population is at
least four. Visible pairs are packed in original actor order; hidden pairs
consume no SAT upload. Attribute writes are skipped only for an identical pose
at the same destination. Destination changes and hidden/reappearing actors
invalidate publication state before the single trailing terminator.

The benchmark invokes the same renderer with controlled one-to-seven actor
fixtures, 200 samples per count and motion mode. The HUD, gameplay raster IRQs,
3,579,545 Hz CPU, real VDP timing and sprite limits remain enabled. Five original
virtual OAM pointers determine visible actors; all seven descriptors/radar
anchors remain present. Costs include raster IRQ interruptions. The static and
moving columns describe presentation fixtures, not original AI execution.

| Actors | Static before / after (ms) | Change | Moving before / after (ms) | Change |
| --- | --- | --- | --- | --- |
| 1 | 1.72 / 1.36 | -20.9% | 1.72 / 1.58 | -7.9% |
| 2 | 3.51 / 2.77 | -21.1% | 3.51 / 3.22 | -8.4% |
| 3 | 5.71 / 4.68 | -18.0% | 5.71 / 5.49 | -4.0% |
| 4 | 7.53 / 6.72 | -10.7% | 7.53 / 7.62 | +1.2% |
| 5 | 9.44 / 7.97 | -15.6% | 9.44 / 9.23 | -2.3% |
| 6 | 11.40 / 8.54 | -25.1% | 11.42 / 9.80 | -14.2% |
| 7 | 12.91 / 9.25 | -28.4% | 12.97 / 10.39 | -19.9% |

Values are medians, not frame rates. IRQ phase affects medians: four moving
actors show a small median regression while their minimum and p95 costs improve
(6.83 to 6.22 ms; 8.40 to 7.83 ms). Report JSON retains minimum/median/p95
cycles for all 2,800 calls per cartridge. The baseline is the previously approved
`b180937f…` cartridge. No graphics reduction or HUD-off comparison was used.

## Radar timing and memory ownership

Foreground SAT writes previously raced the scroll latch under actor load.
The maze IRQ now publishes the player dot and twelve fixed radar sprites after
latching R23, in scan order before their fetches. Coordinates use that same
scroll value. The existing sentinel-216 phase masks remain intact.

An observational trace compares live SAT with expected coordinates immediately
before four radar band fetches and the earliest player-dot fetch. The prior
four-round trace found 2,116 mismatches in 42,365 body samples. The current
eight-round route found **zero in 123,198 body/dot samples**. These traces have
different lengths; they demonstrate the old defect and the current timing gate,
not a statistical matched-route improvement claim.

IRQ code occupies `$c5d2..$c637`, reclaimed from the former shared scratch area.
The terrain deadline flag moves to `$c67c`; leaving it at `$c5e8` would overwrite
an IRQ instruction. Static allocation tests reject that overlap. Natural-route
write watchpoints reject modifications to IRQ code during play, and component,
scene-reload and snapshot proofs compare code bytes with the sealed image.
Cold code leaves 204 bytes below the existing `$f380` stack top.

## Qualification and remaining work

All evidence is ignored under `references/build/`:

| Bundle | Result |
| --- | --- |
| `issue12-render-cost-baseline-v2`, `issue12-render-cost-v13` | Controlled scaling, 2,800 samples per cartridge; native RAM, terrain and stack unchanged |
| `issue12-perf-car-proof-v13` | 13,496 car cases, 8,085 visible; masks/colors/positions, clipping, cache reuse, compact destination changes and identical-pose reappearance; active raster IRQs |
| `issue12-perf-route-v13` | Eight natural rounds, real credit/start/steering/smoke, no guest-state writes; radar timing gate and IRQ-code write guard pass |
| `issue12-perf-evidence-v13` | 94 independent cache/smoke/HUD snapshots, 65 complete enemy images; code-byte canaries |
| `issue12-perf-preparation-v13`, `issue12-perf-rules-v13`, `issue12-perf-ai-v13` | 508 exact preparations, 1,728 phase boundaries, 7,680 three-call original AI comparisons including fine-coordinate and key-change guards |
| `issue12-perf-rounds-v13` | 254 seeded scene transitions, map/object/header checks and IRQ-code canaries |
| `issue12-perf-session-v13`, `issue12-perf-state-v13`, `issue12-perf-attract-v13` | Two-player session/deaths, partial-board restoration/HUD boundaries and original cast/autonomous demo |
| Authored tests | 357 synthetic tests pass |

The eight-round route used 22,641 refreshes, with 6,245 cache holds (27.58%), at
most four consecutive. Header reservation maximum was 7.289 ms. The adaptive
input driver takes different paths as timing changes, so this is not a fixed
whole-game comparison with the previous 25.97% route. Renderer savings do not
establish improved total gameplay speed. Terrain backpressure and native work
remain material performance targets. Issue #12 stays open.

Maximum observed enemy occupancy remains ten planes per scanline; hardware
culling still applies. SAT/VRAM/source-pixel checks do not prove complete loaded
RGB scanout. A four-scene SDL capture attempt advanced emulator state but saved
stale BIOS frontend images, so it is expressly excluded from visual acceptance.
Physical hardware and loaded motion still need qualification.

The bounded `FULL_GAME=0` cartridge remains byte-identical to Issue 11:
`9771e72b394f5a3c66018f638318caa5e4e060eed85c2dcc27d5f5328f5efc12`.

## Reproduce

Use fresh ignored output directories and existing contributor-supplied inputs.

```sh
make build
.venv/bin/python -B scripts/full_enemy_cost.py --rom references/build/default-62285febd96d4c8dbc70117afd0921ea/raster-scroll.rom --output references/build/my-enemy-cost
.venv/bin/python -B scripts/full_enemy_probe.py --rom references/build/default-62285febd96d4c8dbc70117afd0921ea/raster-scroll.rom --output references/build/my-car-proof
.venv/bin/python -B scripts/full_game_route.py --rom references/build/default-62285febd96d4c8dbc70117afd0921ea/raster-scroll.rom --output references/build/my-route --rounds 8 --avoid-enemies --radar-trace --require-stable-radar
.venv/bin/python -B scripts/full_game_evidence.py --rom references/build/default-62285febd96d4c8dbc70117afd0921ea/raster-scroll.rom --capture references/build/my-route --output references/build/my-evidence
make test
```

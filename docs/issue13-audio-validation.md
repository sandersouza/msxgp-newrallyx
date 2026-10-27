# Issue #13 audio validation

Date: 2026-10-27. Implementation and channel policy:
[audio contract](issue13-audio-interface.md).

## Delivered cartridge

The independent build in `references/build/issue13-psg-v27/` and the fresh
default build `default-293518f3afef49ff831380598dc50a39/` have identical ROM bytes:

`89a82c5c9b10c5bbbb97915eb269744f3181e530212f9ea3068a68bea7c2a518`.

`references/build/newrallyx.rom` and `latest.rom` contain that cartridge.
The default build enables PSG; F4 toggles physical output. The full HUD,
original scenery/colors, complete cars and real sprite limits remain enabled.

The reconstructed silent full game is byte-identical to the accepted baseline:
`a31e3b43ae05fae4accac1e6fae58c81c600acd1253b13b6590749e23c6c6953`.
The bounded Issue 11 stage12 rebuild also retains its accepted hash:
`9771e72b394f5a3c66018f638318caa5e4e060eed85c2dcc27d5f5328f5efc12`.

## Execution proofs

| Check | Evidence and scope |
| --- | --- |
| Original sequencer isolation | 6,437 original entry/exit cases and 116,378 ordered raw hardware writes agree after address projection; exact observed original stack-write bytes are treated separately. `issue13-sequencer-proof-v6` |
| Reference PSG kernel | 12,874 executions of the original relocated sequencer/converter, output on/muted; exact state and independently calculated PSG registers. `issue13-reference-kernel-v27` |
| Production playback | 19,800 executions across eleven seeded scenarios, output on/muted, BIOS/held-cache Page0 mappings, score loops, counter wrap, four-refresh/coalesced service, actual F4 holds/edges, all eight effects, flag/smoke adapters, game-over adapter, FIFO saturation/order and crash preemption. `issue13-runtime-proof-v27` |
| Live gameplay mute | 600 logical ticks with identical injected direction/smoke inputs, real keyboard credit/start and full HUD. Every selected native gameplay byte and smoke-placement count agrees with sound on/muted. `issue13-live-mute-v27` |
| Gameplay regressions | Six real normal-round entry collisions, four F5 phase advances with compact HUD, and a natural alternating two-player session pass. `issue13-startup-delivery`, `issue13-debug-delivery`, `issue13-session-delivery` |
| Source-pixel regression | 50 natural-route and six retained-seven cache/HUD/car snapshots match independent scenery, smoke, complete-car and numeric HUD oracles. `issue13-pixels-eight-v27`, `issue13-pixels-seven-v27` |

All 412 unit/integration tests pass in `issue13-tests-delivery-v3.log`.
One earlier full-suite attempt encountered an existing graphics-extractor race
while enumerating a disappearing system temporary file. Its four-test module
and the complete suite passed on rerun; no unrelated extractor change was made.

Component proofs preserve code, stack/index registers, VRAM, mapping and PSG
I/O latches. They run with display/IRQs disabled at forced 3.58 MHz and do not
qualify loaded performance or timbre. Live route measurements below keep real
raster interrupts and factory clock switching. Production playback is the
agreed two-voice/noise transcription; exact original-kernel equality is not an
exact-production-audio claim.

## Loaded gameplay

Machine: openMSX 21.0, FS-A1WSX reference with 128 KB mapper RAM/128 KB VRAM,
NTSC VDP, factory 5.37 MHz CPU switching, established VDP timing, real command
timing and sprite limits. All workloads keep the HUD enabled.

| Workload | Physical packet FPS | Late publication slots | Native ticks/s | Discarded ticks |
| --- | ---: | ---: | ---: | ---: |
| Natural eight rounds | 29.898..29.961 | 0..0.417% per round | 59.890..59.935 | 0 |
| Retained six, displayed round 6 | 29.420 | 3.666% | 59.935 | 0 |
| Retained seven, displayed round 1 | 29.629 | 2.231% | 59.933 | 0 |

Artifacts are `issue13-qualified-eight-v27`, `issue13-qualified-six-v27` and
`issue13-loaded7-v27`. The natural driver uses steering margin 9; controlled
populations use margin 8 and retain the requested count across parameter writes.
Both controlled routes complete their requested round. They are synthetic load,
rather than claims that the original first round normally has seven enemies.

The largest active packet interval is 51.247 ms. Audio worker wall time, including
actual raster IRQs, averages approximately 0.442..0.467 ms per call; observed
maxima are 2.154..2.668 ms. No effect FIFO overflow is observed in these routes.
Those wall times are not pure CPU instruction costs or hardware measurements.

The six-car route exceeds the earlier strict 3.5% diagnostic threshold; that
failed report remains at `issue13-loaded6-v27`. Delivery explicitly accepts a
small **4% controlled-load late-slot budget**, while retaining the 2.5% natural
budget, 68 ms maximum packet gap and zero discarded native ticks. This timing
concession does not reduce graphics or slow the simulation.

For context, the accepted silent six-car route records 29.537 FPS and 40 late
intervals over 47.162 active seconds. Audio records 29.420 FPS and the same 40
late intervals over 37.083 seconds. These adaptive routes take different paths;
the difference must not be presented as an exact isolated audio percentage cost.

The eight-round effects trace observes all 80 collected flags and 468 visible
smoke tiles: maximum sampled flag lag 99.517 ms, smoke lag 104.004 ms, no
unpublished smoke leaving view, unsafe/duplicate radar publication, persistent
enemy ghosts or unknown radar ink. The smoke deadline now expresses the existing
nominal 200 ms as **12 actual NTSC refreshes, 200.258 ms**. This corrects the
rounded time boundary; it does not alter rendering. Earlier `v22` data retains
the nominal-boundary rejection at 200.165 ms against the old 200.000 ms check.

## Reproduction

```sh
gnumake test
gnumake build
.venv/bin/python -B scripts/audio_runtime_probe.py --rom references/build/issue13-psg-v27/raster-scroll.rom --output references/build/my-runtime-proof
.venv/bin/python -B scripts/audio_gameplay_probe.py --rom references/build/issue13-psg-v27/raster-scroll.rom --output references/build/my-live-mute
.venv/bin/python -B scripts/full_game_route.py --rom references/build/issue13-psg-v27/raster-scroll.rom --rounds 1 --steering-margin 8 --fixture-enemies 6 --fixture-first-round 6 --avoid-enemies --allow-game-over --minimum-native-hz 59 --require-retained-native-ticks --maximum-packet-miss-percent 4 --maximum-packet-gap-ms 68 --radar-trace --require-stable-fuel --require-stable-player --output references/build/my-six-car-route
```

Use a fresh ignored output directory. Each successful acquisition/probe seals
its manifest. Original inputs and all derived scores, ROMs, traces and PCM stay
ignored. Only authored tooling, synthetic tests, assembly and docs are published.

## Remaining review

`issue13-loaded7-v27/audio.wav` is an actual approximately 20-second PSG recording
with nonzero PCM. It is available locally for listening. Register/PCM checks do
not establish pleasant timbre; human listening remains the final review item.
SCC is evaluated/deferred with PSG always available; no expansion support is
claimed. Physical hardware, other machines/clocks/PAL and play beyond the
previously qualified round range remain outside these measurements.

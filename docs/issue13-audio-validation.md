# Issue #13 audio validation

Date: 2026-10-27. Implementation and channel policy:
[audio contract](issue13-audio-interface.md).

## Delivered cartridge

The current tested build is `references/build/issue13-music-v34/`:

`d224b9b54af4e4b051ca1d0f793a8308899d3d50a9ac9752f0c8aca40ecda63b`.

`references/build/newrallyx.rom` and `latest.rom` contain that cartridge.
The default build enables PSG; F4 toggles physical output. The full HUD,
original scenery/colors, complete cars and real sprite limits remain enabled.

The reconstructed silent full game is byte-identical to the accepted baseline:
`a31e3b43ae05fae4accac1e6fae58c81c600acd1253b13b6590749e23c6c6953`.
The bounded Issue 11 stage12 rebuild also retains its accepted hash:
`9771e72b394f5a3c66018f638318caa5e4e060eed85c2dcc27d5f5328f5efc12`.

## Shared music-group ending correction (v34)

The user heard two successive two-voice tunes after Start. The original code
at 28C1..2906 starts melody IDs 18/19/20 together and stops the group when any
part ends. Their tables share tails: the parsed parts last 720/480/240 native
ticks. Dropping voice 20 from output must still retain its 240-tick stop.
The previous compiler used only the selected voices and therefore played 480
ticks, including an unintended extra phrase. The original unmodified sound-call
capture independently clears the Start request on call 241, after 240 musical
ticks. `audio_score_probe.py` rejects v33 and accepts v34 against that capture.

The corrected two-voice introduction lasts 120 score frames / 4.004 seconds in
the actual keyboard session. The analogous three-part completion group now
ends at 106 native ticks, rather than 114. No extra PSG channel, runtime work,
native velocity or graphics change is introduced.

Current checks: 414 tests (`issue13-music-tests-v34.log`), 27,000 production
cases (`issue13-music-runtime-v34`), original-duration proof
(`issue13-music-duration-v34`), quiet-UI/Start/F5 keyboard ordering
(`issue13-music-session-v34`) and 600 live mute-replay ticks
(`issue13-music-live-mute-v34`) pass. Eight natural rounds retain
29.943..29.961 packet FPS, at most 0.115% late slots and zero discarded ticks
(`issue13-music-eight-v34`). The retained-six route passes at 29.370 FPS and
3.861% late slots (`issue13-music-six-v34`).

The current retained-seven route completes but fails the existing 4% late-slot
gate at **4.263%**, 29.323 packet FPS, 67.865 ms maximum gap and 59.897 native
Hz, with zero discarded ticks (`issue13-music-seven-v34`). This timing gate
remains open; it is not a passing qualification. The unchanged runtime and
adaptive route differences do not establish a causal music CPU regression.
The earlier passing v33 seven-car result below is historical evidence.

## Earlier screen/clock corrections and evidence (v33)

The user reported music on insert-coin/player-select screens, the start cue
overlapping gameplay, and slower music/gameplay during vertical scrolling.
Two independent regressions were reproduced on v27: `audio_session_probe.py`
rejects music on the waiting screens, and `audio_runtime_probe.py` rejects an
odd-refresh score mismatch. Their failed evidence remains in
`issue13-session-audio-before` and `issue13-odd-clock-before`.

The worker previously divided elapsed refreshes by two and saved the current
refresh, discarding each odd remainder. It now advances the saved timestamp by
exactly the consumed even refreshes. Screen state gates melody selection even
when native request bits have not changed. The start cue plays once before
gameplay, not on scene reload. Silent scenes explicitly flush preceding output;
the sustained-noise fast path checks session/death state before returning.
The UI start cue also ignores a stale collision left by attract gameplay;
`issue13-stale-death-before` reproduces that override on the earlier candidate.
The session check runs only on a new death event, keeping it off the common
live-gameplay path.

| Current check | Result |
| --- | --- |
| Unit/integration suite | 413 pass, `issue13-timing-tests-v33.log` |
| Production scheduling | 27,000 cases, 15 scenarios including odd refreshes, quiet UI, stale death and live music/UI/start transitions; output on/muted and all previous isolation/queue gates. `issue13-runtime-v33` |
| Actual keyboard session | 121 quiet UI packets, 8.010 s start cue entirely before gameplay, background music after loading and F5 phase change. `issue13-session-audio-v33` |
| Live mute replay | 600 identical native ticks/smoke counts with output on/muted. `issue13-live-mute-v33` |
| Natural eight rounds | 29.943..29.961 packet FPS, 0..0.115% late slots, 59.900..59.927 native Hz, zero discarded ticks. `issue13-eight-v33` |
| Retained six, round 6 | 29.370 packet FPS, 3.861% late slots, 59.932 native Hz, zero discarded ticks. `issue13-six-v33` |
| Retained seven, round 1 | 29.560 packet FPS, 2.707% late slots, 59.825 native Hz, zero discarded ticks. `issue13-seven-v33` |

These use the same machine, graphics and unchanged 2.5% natural / 4% controlled
late-slot budgets described below. The largest packet gap is 67.894 ms in the
six-car workload, below the existing 68 ms limit. Preceding v30/v32 seven-car
candidates failed at 4.348%/4.263% late slots; their reports remain at
`issue13-seven-v30` and `issue13-seven-v32`. The final sustained-engine and
event-only session checks avoid unnecessary work. Adaptive routes differ, so these are workload gates,
not isolated causal CPU-percentage comparisons.

Axis-specific physical samples retain stopped frames within stable-direction
runs of at least 0.5 s. The earlier eight-round trace advanced the score at
26.494 frames/s vertically versus 29.350 horizontally. Current eight-round
samples measure **29.982 vertically / 29.975 horizontally**, with physical
packet rates **29.954 / 29.959** and native rates **59.664 / 59.795**. These
samples do not reproduce a sustained 5% vertical simulation slowdown. Short
window endpoint/batching error remains, especially in controlled loads; the
comparison does not assert equal travel distance through different maze paths.
No native velocity or graphical quality was changed to compensate for audio.

The final eight-round effects check observes 80 flag captures and 270 visible
smoke tiles: maximum sampled flag lag 120.824 ms, smoke lag 114.749 ms, no unsafe
or repeated radar publications, persistent enemy ghosts or unknown ink.
Current HUD/player/fuel latch checks pass with real sprite limits.

## Earlier execution proofs (v27)

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

## Earlier loaded gameplay (v27)

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
.venv/bin/python -B scripts/audio_runtime_probe.py --rom references/build/issue13-timing-v33/raster-scroll.rom --output references/build/my-runtime-proof
.venv/bin/python -B scripts/audio_session_probe.py --rom references/build/issue13-timing-v33/raster-scroll.rom --output references/build/my-session-proof
.venv/bin/python -B scripts/audio_gameplay_probe.py --rom references/build/issue13-timing-v33/raster-scroll.rom --output references/build/my-live-mute
.venv/bin/python -B scripts/full_game_route.py --rom references/build/issue13-timing-v33/raster-scroll.rom --rounds 1 --steering-margin 8 --fixture-enemies 6 --fixture-first-round 6 --avoid-enemies --allow-game-over --minimum-native-hz 59 --require-retained-native-ticks --maximum-packet-miss-percent 4 --maximum-packet-gap-ms 68 --radar-trace --require-stable-fuel --require-stable-player --output references/build/my-six-car-route
```

Use a fresh ignored output directory. Each successful acquisition/probe seals
its manifest. Original inputs and all derived scores, ROMs, traces and PCM stay
ignored. Only authored tooling, synthetic tests, assembly and docs are published.

## Remaining review

`issue13-music-seven-v34/audio.wav` is an actual approximately 20-second PSG recording
with nonzero PCM. It is available locally for listening. Register/PCM checks do
not establish pleasant timbre. Human listening and the current retained-seven
late-slot gate remain open review items.
SCC is evaluated/deferred with PSG always available; no expansion support is
claimed. Physical hardware, other machines/clocks/PAL and play beyond the
previously qualified round range remain outside these measurements.

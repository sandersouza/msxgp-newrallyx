# Issue #13 audio validation

Updated: 2026-10-28. Implementation and channel policy:
[audio contract](issue13-audio-interface.md).

## Delivered cartridge

The current tested build is `references/build/issue13-camera-v44/`, privately
delivered as `newrallyx-audio-v4 [ASCII16].rom`:

`1e2820bd9659c3439e2e8c59e8d5b7302d3f6f7adf23f7fec26a79999738f767`.

`references/build/newrallyx.rom` and `latest.rom` contain that cartridge.
The default build enables PSG; F4 toggles physical output. The full HUD,
original scenery/colors, complete cars and real sprite limits remain enabled.

The silent full game includes the same camera correction, with SHA-256
`4ef05638ac2dce771dddcc71bd98c50fb8d0adc93cb1148df1e93344dab59db4`.
The bounded Issue 11 stage12 rebuild also retains its accepted hash:
`9771e72b394f5a3c66018f638318caa5e4e060eed85c2dcc27d5f5328f5efc12`.

## Confirmed outside-maze flowers: bounded camera correction (v44)

The user identified the repeated flower field around score 005750 in the
retained 155-second v43 session as **one** reported defect. The camera always
centred the car, exposing padded flower tiles outside the map: X -88..656 and
Y -69..1155 in that replay. The scenery oracle legitimately reconstructed those
tiles, so its passing result missed this failure. A new visible-rectangle check
rejects 1,461 of the original 6,833 samples. Its valid origins are X 0..568 and
Y 0..1191 for an 816x1392 world and 248x201 viewport, retaining the original
24-pixel decorative border.

Camera plans now stop at those limits. The car moves on screen at an edge;
its real world pose remains available to radar and native collision logic.
Enemies project relative to the separate camera centre. Candidate, sealed
and displayed player projections travel with the complete VBlank packet, so
a delayed camera transaction cannot publish a newer car position. Initialization
and restart establish all three poses before terrain filling. Artwork, scale,
colors, HUD and original gameplay coordinates remain unchanged. The overlay
ends at 1FC1 (limit 2000); presentation code ends EBF6 (limit EC00). New camera
workspace is disjoint from the audio controls and smoke buffers.

| Check | Evidence under `references/build/` |
| --- | --- |
| Current suite | 424 tests pass; `issue13-camera-v44-tests-final.log` |
| Bounded initialization and publication | 363 seeded Z80 cases across every edge/centre threshold and three scroll values; a different unsealed candidate cannot replace the displayed pose; native/VRAM/mapping/stack/index canaries; `issue13-camera-bounds-v44` |
| Independent enemy projection | 13,496 full-car presentation cases with player world pose deliberately different from camera centre; `issue13-camera-enemies-separated-v44` |
| Reapplied human inputs | 255 keyboard events from the affected session applied to a fresh v44 cartridge; 5,052 terrain/bounds samples, 3,915,300 checked pixels and 5,407 mode/scroll latches pass; actual scanout and the 90-second screenshot retained; `issue13-camera-human-v44` |
| Eight natural rounds | 29.895..29.961 packet FPS, at most 0.437% late slots, native 59.901..59.928 Hz, zero discarded ticks/queue drops; 24,932 physical viewport samples inside bounds; 11,498 foreground samples / 8.89M pixels; player/radar/fuel/footer SAT gates pass; `issue13-camera-eight-v44` |
| Controlled seven enemies | Completes with 29.442 packet FPS, 3.44% late slots, 67.870 ms maximum gap, native 59.833 Hz and zero discarded ticks/queue drops; existing 4%/70 ms gates pass; 2,676 bounded viewport samples; `issue13-camera-seven-v44` |
| Session/restart/debug | Natural two-player deaths, alternation and game over pass in `issue13-camera-session-v44`; four real F5 advances and compact HUD pass in `issue13-camera-debug-v44` |
| Compatibility builds | Silent full game includes the correction; bounded Issue 11 stage12 retains its accepted hash; `issue13-camera-{silent,bounded}-v44` |

The fresh input run is **not** deterministic playback of a different cartridge:
the original replay remains untouched and fingerprint-protected. Different
camera/backpressure paths can change gameplay outcomes. These route measurements
do not isolate a causal audio CPU saving or qualify all possible workloads.
Physical motion checks now include the independently observed sealed car
projection; a stationary bounded camera with a moving car is not labelled a
frozen gameplay frame. Terrain remains an 8-pixel grid with dynamic exclusions,
not an every-pixel visual proof.

The repeated outside-map flower exposure is corrected in these workloads.
Other user-reported scrambling remains unlocalized; do not mark the complete
maze report resolved. Audio synthesis is unchanged from v43 and still awaits
listening acceptance. Keep #13 and PR #31 open; no merge or hardware/PAL/WebMSX
gameplay acceptance is claimed.

## Historical engine revision and transient-maze investigation (v43)

The user rejected the v41 engine and reported severe transient maze corruption
in openMSX. At v43, an affected live session was retained, but the visual fault
had not yet been localized or fixed. Passing cadence or
audio-register tests do not settle this report. No speculative renderer or
memory-mapping change is included.

The engine's coarse integer-speed selector was inconsistent with original
code at 266F..2685: the original selects the second engine note only when the
fractional speed byte equals `$20`. The current adapter follows that selection
and removes the invented intermediate pitch. The preceding approximation
replaced each complex waveform with its dominant harmonic and an ultrasonic
gate. Audible carrier/envelope combinations now produce pulse clusters and
sidebands; the chip runs both oscillators between parameter packets. Shapes
10/8 and per-heading ratios approximate the four original engine waveforms.
No game velocity, graphics, HUD or memory ownership is changed.

Actual 25-second PCM recordings with identical input fixtures are retained in
`issue13-engine-audition-before` (v41) and `issue13-engine-audition-v43`.
The new recording peaks at 17,840 / 32,767 without clipping. Up-heading normal
and second-state pitches measure 49.904 / 65.917 Hz against source targets
49.804 / 65.917 Hz. An isolated four-heading comparison of twelve normalized
harmonics against the original PROM measures squared distances
0.176 / 0.128 / 0.195 / 0.174, versus 1.570 / 1.221 / 1.555 / 1.747 for v41.
This proxy includes the corrected pitch selection as well as changed timbre;
it is not a perceptual score or a claim of matching waveforms. Human listening
acceptance remains open.

Current checks: 421 tests (`issue13-maze-replay-tests-final.log`), 27,000 playback
cases covering all four headings, wall/normal/second-note states and the
fractional boundary (`issue13-engine-runtime-final`), real keyboard UI/Start/F5
(`issue13-engine-session-v43`) and 600 live sound-on/muted ticks
(`issue13-engine-live-mute-v43`) pass. The eight-round full-HUD route retains
29.937..29.961 packet FPS, at most 0.160% late slots, no discarded ticks and no
audio queue drops (`issue13-engine-eight-v43`). Controlled six cars pass at
29.463 FPS / 3.218% late slots (`issue13-engine-six-v43`). Seven cars still
complete but **fail** the existing 4% gate at 4.3515%, 29.311 FPS / 67.864 ms
maximum gap (`issue13-engine-seven-v43`); see the passing v44 workload above.

The six-car audio ledger averages 2,039 CPU / 2,507 inclusive equivalent cycles
per worker-containing loop, with 1.001 calls/presented packet; self mean 160,
inclusive p95/max 6,940 / 8,768. These are 3.58 MHz-equivalent elapsed cycles
under factory clock switching, not raw turbo instruction counts. IRQ time is
excluded from CPU and retained in inclusive cost. Only subtracting audio leaves
117,432 of the nominal 119,472-cycle two-refresh packet; rendering, game logic,
waits and IRQs still consume that remainder. VBlank reserve remains unknown.
Do not add nested inclusive rows. Full ledgers remain in the private reports.

### Maze investigation coverage and capture

Sparse source-pixel checks on the delivered v41 ROM pass 48 natural and six
controlled-seven snapshots (`issue13-corruption-pixels-before`,
`issue13-corruption-seven-before`). New `--terrain-trace` observations compare
an 8-pixel grid across the entire visible cache against independently rebuilt
original scenery on every eligible foreground packet. Tests deliberately
corrupt a middle frame, then restore it; the verifier retains that failure.
Known published smoke/player-patch pixels and active scene/effect transitions
are excluded. This is not an every-pixel or continuous scanout proof.

On v41, the alternate eight-round route checks 9,512 eligible packets / 7.35M
pixels, a route with deaths/restarts checks 2,011 / 1.56M, and the controlled
six-car route also passes. None reproduces the report. Current v43 checks
10,113 packets / 7.82M pixels over eight rounds, plus 1,176 six-car packets.
When paired with `--radar-trace`, it also samples terrain at the physical maze
scroll latch using the actual hardware camera. The two-round v41 and v43
checks each pass 5,106 physical-latch samples / 3.95M pixels
(`issue13-maze-physical-before-v2`, `issue13-engine-physical-v43`); controlled
seven v43 passes 2,563 latch samples. These bounded workloads do not prove
that the user's transient fault is absent.

`scripts/maze_debug.py` enables openMSX reverse recording and binds F6 to save
the preceding replay, full machine state, screenshot, RAM, VRAM and VDP
registers, with the ROM hash. Its self-test uses real keyboard credit/Start,
reaches gameplay and rejects a blank screenshot. All captures remain ignored.
Loading its saved replay at the capture instant also reproduces RAM and VRAM
byte for byte; the restore is paused immediately to avoid comparing later ticks.
Capture the user's failure before identifying its cause or claiming a fix.

The user subsequently confirmed that the fault occurs in the first round of
the audio ROM with the top HUD, and looks scrambled rather than like another
intact maze. The separately running fixed-HUD experiment is not the reported
configuration and its captures do not qualify this defect.

Three deterministic keyboard stress routes (seeds 1/27/343) add abrupt turns,
reversals and smoke without guest-memory writes. All end at a legitimate first-
round game over rather than completing a phase; 2,280 eligible foreground
packets and 4,642 physical-latch samples pass scenery/HUD checks
(`issue13-maze-input-stress-final-*`). They did not reproduce the fault.

Normal `make run` now shares F6 capture with the debug launcher and saves the
replay/state automatically on a normal quit. The manual capture/replay-restore
self-test and automatic exit capture pass. A real 155.065-second session of
the current v43 audio ROM was retained this way. `full_replay_probe.py` checks
the selected cartridge fingerprint before replaying, injects no new gameplay
inputs or RAM writes, and checks scenery plus actual video-mode/scroll values.
The complete saved session passes 7,195 latch register checks and 6,833 eligible
terrain samples / 5,295,575 pixels (`issue13-human-replay-exit`). It also has no
adjacent active latch displacement over eight pixels in either circular axis.

`--record` retains actual raw scanout frames as well; this replay has 8,973
frames / 149.743 seconds from cartridge startup (`issue13-human-replay-scanout-v2`).
The user confirmed that the visual defect occurred in this recorded live
session. The passing native checks therefore do not detect or rule out the
reported fault. The visual interval still needs localization; raw replay output
and the original displayed window must be distinguished. The user subsequently
confirmed the repeated border flowers around score 005750 as one defect; the
v44 section above documents its correction and remaining limits. F6 retains both raw and
scaled/window screenshots, and its real emulator capture/restore self-test
passes. Retaining the video is not an every-pixel validation claim. The full suite
now passes 421 tests (`issue13-maze-replay-tests-final.log`).

## Historical listening-feedback adaptation (v41)

The two-voice/noise-only policy was rejected in listening review and is
superseded. Start and completion now play all three original parts together,
with gain balancing and note articulation. Credit, flags, extra life, low fuel,
fuel conversion and recovery use their original melodic contours on C. Only
smoke and the adapted crash require noise. C returns to music or engine after
an effect; A/B continue throughout. A repeating PSG envelope supplies a pitched
engine with coarse native speed and four heading-dependent harmonic choices.
The engine is hardware-driven between packets, without CPU sample synthesis.

Repeated active and waiting effects coalesce. This removed observed queue
overflows from the preceding candidate: natural eight rounds and both retained
populations now record zero drops. Crash cannot be interrupted by recovery.
The bounded Lucky-fuel adapter now emits the recovery request after restoring
the gauge; effect 9 is observed in natural gameplay, not only seeded fixtures.
No graphics, HUD or native velocity reduction accompanies this change.

| Current check | Result and artifact under `references/build/` |
| --- | --- |
| Unit/integration suite | 418 pass; `issue13-sound-tests-v41.log` |
| Production player | 27,000 executions, fifteen seeded scenarios, output on/muted, nine exact effect contours, concurrent third music voice, engine headings, FIFO/coalescing/priority; `issue13-sound-runtime-v41` |
| Reference kernel after shim relocation | 12,874 PSG/mute cases; `issue13-sound-reference-final` |
| Original Start ending | Original captured call 241 vs compiled 240 ticks / 120 frames; `issue13-sound-duration-final` |
| Actual keyboard session | 121 quiet UI packets, 4.004 s Start before gameplay, F5 without replay; `issue13-sound-session-v41` |
| Live mute replay | 600 identical native ticks and smoke counts; `issue13-sound-live-mute-v41` |
| Natural eight rounds | 29.942..29.961 packet FPS, 0..0.1241% late slots, 59.901..59.927 native Hz, zero discarded ticks; `issue13-sound-eight-v41` |
| Retained six / round 6 | 29.440 FPS, 3.3778% late slots, 67.893 ms maximum gap, zero discarded ticks; `issue13-sound-six-v41` |
| Retained seven / round 1 | Completes at 29.311 FPS, **fails** unchanged 4% late-slot gate at **4.3515%**; 67.867 ms maximum gap, 59.899 native Hz, zero discarded ticks; `issue13-sound-seven-v41` |

The seven-car timing qualification remains open. It was also open on v34;
these adaptive routes do not isolate a causal percentage cost for the new
arrangement. Do not replace its failure with earlier passing candidates.
Natural and six-car routes pass their existing 2.5% / 4% budgets. All runs use
openMSX 21, FS-A1WSX_NR128, NTSC, 128 KB mapper/VRAM, factory CPU switching
(5.37 MHz native instruction samples), full HUD and real sprite/command limits.

Natural-route checks retain all 80 flag removals and 270 visible smoke tiles:
maximum sampled flag lag 120.499 ms, smoke 114.668 ms, no unsafe/repeated radar
publication, persistent enemy ghosts or unknown ink. Axis samples measure
score progression at 29.958 Hz vertically / 29.970 horizontally and packet
rates 29.959 / 29.961. These bounded samples do not reproduce the reported
sustained vertical music slowdown; endpoint and route differences still apply.

### Recorded sound comparison

`audio_inventory.py --record` now captures actual MAME PCM while observing
real coin/start/smoke inputs. The private `issue13-sound-original-v35` capture
lasts 46.180 s. PROM spectral analysis identifies the original engine's
dominant heading harmonics as 3/1/3/5; the PSG approximation follows those
targets without embedding the waveform in production.

`audio_audition_probe.py` records actual PSG output for the same timed,
explicitly seeded events on both old and new ROMs. It is a controlled audition,
not natural gameplay. The 21.026 s before/after WAVs are in
`issue13-sound-audition-before-final` (delivered v34) and
`issue13-sound-audition-v41` (current). Current peak is 14,218 / 32,767, RMS
2,672; no clipping is observed. The isolated up-heading engine segments measure
49.904 / 57.359 / 65.917 Hz against original targets 49.804 / 57.130 / 65.917 Hz;
second-harmonic/fundamental amplitude ratios are approximately 0.62. This checks
pitched output rather than relying solely on register periods.

Original and PSG waveform shapes remain different. Pitch, three active voices,
event identity and absence of digital clipping do **not** establish enjoyable
or sufficiently arcade-like sound. User listening acceptance remains open.
No physical-hardware, PAL or WebMSX gameplay qualification is claimed.

### Audio cycle ledger

`full_game_route.py --profile` writes nested audio call costs to
`audio-cycles.tsv` and summarizes them in `report.json`. Values below are
3.58 MHz-equivalent elapsed cycles under factory clock switching, **not** raw
5.37 MHz instruction counts. CPU time excludes observed raster IRQs; inclusive
time retains them. Self costs subtract instrumented direct audio children;
platform helpers and tail jumps remain in their caller. Repeated calls are
aggregated per foreground loop. Never sum inclusive parent and child rows.

Current six-car means (same v41 ROM/workload above):

| Routine | Calls/presented packet | Inclusive mean | CPU mean | Self mean | Inclusive p95 / max |
| --- | ---: | ---: | ---: | ---: | ---: |
| `Audio_Work` | 1.001 | 2592 | 2098 | 163 | 5287 / 9536 |
| `Audio_RuntimeStep` | 0.972 | 2459 | 1993 | 240 | 5061 / 8630 |
| `Audio_MusicTick` | 0.972 | 603 | 518 | 247 | 739 / 6326 |
| `Audio_NoiseTick` | 0.972 | 404 | 310 | 297 | 633 / 6206 |
| `Audio_RenderMusic` | 0.972 | 712 | 576 | 576 | 1085 / 6541 |
| `Audio_ReadTone` | 2.047 | 275 | 228 | 228 | 304 / 5898 |

Worker mean CPU cost is approximately 0.586 ms; measured worker wall time
averages 0.725 ms, p95 1.449 ms, maximum 2.650 ms. Seven-car mean CPU cost is
2004 equivalent cycles; wall mean 0.710 ms / maximum 2.756 ms. Older v34's
fresh six-car baseline averages 1538 CPU-equivalent cycles
(`issue13-sound-baseline-six-profile`); route differences prevent treating this
as a fixed per-gameplay-frame causal delta.

One physical refresh is 16.688 ms / 59,736 equivalent cycles; a nominal
two-refresh packet is 33.376 ms / 119,472 cycles. Subtracting mean audio CPU
work alone leaves 117,373 cycles in the six-car ledger. This is **not free CPU
budget**: rendering, game logic, IRQs and waits still consume it. These results
do not establish a usable VBlank reserve; that field remains unknown rather
than assuming 5,000 cycles. Full routine means/tails/self costs remain in reports.

## Historical shared music-group ending correction (v34)

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

Historical checks: 414 tests (`issue13-music-tests-v34.log`), 27,000 production
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

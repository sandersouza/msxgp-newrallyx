# Issue #13 audio validation

Updated: 2026-10-28. Implementation and channel policy:
[audio contract](issue13-audio-interface.md).

## Delivered cartridge

The current tested build is `references/build/issue13-cast-v65/`, privately
delivered as `newrallyx-audio-v8 [ASCII16].rom`:

`e95a4a803c0ac3d0096b7021c877a56086d09d6ba8ed307dde7a8d039198537c`.

`references/build/newrallyx.rom` and `latest.rom` contain that cartridge.
The default build enables PSG; F4 toggles physical output. The full HUD,
original scenery/colors, complete cars and real sprite limits remain enabled.

The silent full game includes the same presentation/mechanics, with SHA-256
`4cef16a861f42752d3d258fb23f361f525c1eacad89cb308c9ffd99f7b08d9c3`.
The bounded Issue 11 stage12 rebuild also retains its accepted hash:
`9771e72b394f5a3c66018f638318caa5e4e060eed85c2dcc27d5f5328f5efc12`.

## Complete cast reveal rectangles (v65 / private v8)

The cast's initial bitmap left source fragments visible because the icon
rectangles missed the rightmost car column and the rock/smoke right edges.
The blue car's first row and red car's last row were also outside their own
rectangles. Correct the source origins without moving or resizing any drawing.
The smoke's 24-pixel original shape gets one background pixel of padding on
either side, producing an even 26-pixel copy width. Rock/red-car resources used
by the challenge card now include their complete original drawings too.

The expanded `full_arcade_ui_probe.py` checks 97 complete bitmap states against
an independent broad-body/row oracle: the blank body before any object appears,
then every icon and typed character. The old v63 ROM fails at state 0 with
premature pixels (`issue13-cast-before-v63`). V65 passes all 97 states, the final
original 1:1 bitmap, exact credit glyphs and the existing UI/audio/session
transition fixtures (`issue13-ui-v65`). Initial/partial/final screenshots were
inspected. The demo/death/coin cycle and all 20 point-label/erasure cases pass
again in `issue13-attract-v65` and `issue13-popup-v65`; five targeted session
resource tests pass in `issue13-cast-unit-v65.log`.

`issue13-cast-diff-v65` confines changed banks to the initial cast image and UI
resources (114/115/126). Native gameplay, terrain, HUD, car and audio banks are
byte-identical to v7. Credit-font and point-label pixel data are also unchanged.
The UI-bank point code is relocated after 24 bytes of extra smoke padding and
executed separately by the point-label proof. Prior gameplay timing results
remain scoped to the unchanged runtime; no new timing claim is inferred from
the cast screenshots. The silent variant is rebuilt with the same correction.

## Original credit font (v63 / private v7)

The authored lowercase credit alphabet is removed. Both `NAMCO` and `RETROWORK`
now use the original 8x8 uppercase tile masks, and the copyright mark comes from
original tile 0x18. No letter is redrawn or rescaled. The actual black-selection
screen is checked pixel by pixel directly against the contributor assets,
independently of the font generator (`issue13-ui-v63`); five targeted session
resource tests pass (`issue13-font-unit-v63.log`). The captured selection PNG
was inspected as well.

`issue13-original-font-diff-v63` verifies that all 102 changed cartridge bytes
are inside the UI font table or the two equal-length credit strings. Every
executable instruction and gameplay resource remains byte-identical to v62;
the preceding timing and gameplay evidence therefore remains scoped to that
unchanged runtime. The silent variant is rebuilt with the same original glyphs.

## Arcade presentation, lives, contact and optional points (v58)

### Startup-rule clarification (v61 / private v6)

The user explicitly clarified that normal startup cars must remain passable.
The v5 solid-startup assumption below is superseded. Normal waiting animation
states (`$88` and later) now skip contact until activation, while challenge cars
remain solid. The native smoke-spin marker keeps stunned active cars separate,
preserving their prior contact behavior. No movement, audio or presentation rule
is changed by this follow-up.

`issue13-startup-keys-v61` exercises real credit/start/F5/down inputs on eight
entries, without guest-state writes: six normal rounds each record ten actual
overlap ticks and a complete crossing while the enemy stays parked; challenge
rounds 3/7 collide before the car moves. `issue13-contact-v61` passes 60,218
executed contracts, including 22,680 cases spanning startup versus smoke spin,
normal versus challenge, activation and all seven actor slots.

The startup check runs only after coarse proximity rejection and reuses the
existing state test, keeping the ordinary active-car path unchanged. Final v61
qualification passes the same timing/terrain/HUD gates:

- Eight natural rounds: 29.904..29.961 packet FPS, at most 0.3731% late slots,
  native 59.903..59.943 Hz and zero discarded ticks. Eighty labels and 6,939,317
  terrain pixels checked; 19,938 physical viewports remain bounded; all player,
  radar, fuel and footer checks pass. `issue13-eight-v61`.
- Controlled seven enemies: 29.4188 FPS, 3.6829% late slots, 51.180 ms maximum gap,
  native 59.8839 Hz and no discarded ticks. Ten labels and 910,950 terrain pixels
  checked; all sprite/bounds gates pass. `issue13-seven-v61`.
- Actual keyboard UI/audio transitions, all 20 label/erasure cases, 27,000
  production audio cases and a natural two-player session pass again in
  `issue13-{ui,popup,runtime,session}-v61`. Silent cast/demo passes in
  `issue13-attract-silent-v61`; the 428-test suite is retained in
  `issue13-final-tests-v61.log`.

The v58 evidence and solid-startup assumption below remain historical.
V62 rebuilds the same cartridge bytes with corrected contact-policy build
metadata; its ROM matches all v61 qualification fingerprints exactly.

The orange original cast now reveals icons and types labels before the idle
demo. Demo death returns to it. A coin opens a separate black selection screen
with the requested `@ namco 1981 2ST` / `@ retrowork 2026` credits. Rejected 2P
selection preserves a single credit; accepted 1P/2P selection starts the three
original Start parts before gameplay. Challenge entry has its own screen and
the original melody 15 repeated twice. Video-only resume preserves parked
challenge velocities and both players' packets. Pause physically silences all
channels and freezes the musical cursor; settlement stops driving music.

Native bonus awards already changed the life count, but score publication did
not immediately refresh its HUD value. Both now agree at 20,000 and 80,000.
V58 treated the first `$88` startup pose as solid. That assumption is superseded
by the explicitly clarified pass-through policy documented above.

One authored 24x8 world-anchored point label uses the actual flag ordinal and
native multiplier. It needs no car/radar sprites. Compile it out with
`make build FLAG_POPUPS=0`. Painting/removal replaces optional guard prefetch
after the critical presentation packet. Erasure regenerates current owned
terrain with smoke capture/publication, rather than restoring saved pixels.
The first implementation exceeded the controlled-seven timing budget at 5.13%;
moving this work and retaining the common sprite-upload path brings the final
candidate back inside the unchanged 4%/70 ms limits. Explicit EI points after
command waits also remove an observed late footer interrupt during a capture.

| Check | Result / private artifact |
| --- | --- |
| Current suite | 428 tests pass; `issue13-arcade-tests-v58.log` |
| Cast/demo | Exact original final cast, staged reveal, autonomous demo/death and fresh coin/start; `issue13-attract-v58` |
| UI/audio transitions | Actual keyboard credit/rejected 2P/accepted 2P/Start/P/resume; exact black selection text; physical PSG silence and frozen cursor; controlled settlement/challenge preservation. Start 4.020 s; challenge 6.417 s versus 6.408 s source duration. `issue13-ui-v58` |
| Extra lives | Six actual Z80 exact/crossed 20k/80k and duplicate-award cases; native and immediate HUD agree; `issue13-bonus-v58` |
| Parked/active contact | 48,878 executed steering/motion/smoke/contact contracts, including 11,340 startup/contact cases over all seven actors, first `$88` pose and phase types; `issue13-contact-v58` |
| Production audio | 27,000 playback/effect/mute cases; `issue13-runtime-v58` |
| Flag label / erasure | All 20 ordinary/multiplier bitmaps, all four bitmap banks, both torus seams, stale-smoke scratch and replaced-owner canary under real IRQs; `issue13-popup-v58` |
| Interrupted uploads | 2,048 lengths/offsets, 284 actual IRQ overlaps across every armed full-game raster phase, exact bytes/canaries/return contract; `issue13-uploads-v58` |
| Eight natural rounds | 29.905..29.961 packet FPS, maximum 0.3731% late slots, 59.903..59.943 native Hz, zero discarded ticks or audio queue drops. 80 labels checked byte-for-byte; 6,939,317 foreground terrain pixels and 19,939 bounded physical viewports. All player/radar/fuel/footer gates pass. `issue13-eight-v58` |
| Controlled seven enemies | Completes at 29.4536 FPS, 3.3573% late slots, 67.746 ms maximum gap, 59.8613 native Hz, zero discarded ticks/drops. Ten labels and 913,251 terrain pixels checked; all sprite/bounds gates pass. `issue13-seven-v58` |
| Feature-off comparison | Same controlled-seven gates pass at 29.4180 FPS / 3.6829%; `issue13-seven-popups-off-v55`. Its `f32f80b9...` ROM is byte-identical to the final feature-off v58 rebuild. Routes diverge, so this is a feasibility comparison, not an isolated CPU-saving claim. |
| Session/debug | Actual two-player selection, six natural deaths, alternation/game over and original lives/round packets; `issue13-session-v58`. Four real F5 advances preserve the compact HUD; `issue13-debug-v58`. |
| Compatibility | Silent full-game cast/demo pass in `issue13-attract-silent-v58`; bounded stage12 retains the accepted hash above. |

The cadence trace now explicitly records UI state. Challenge interstitial time
is excluded from active simulation averages; long stalls within actual gameplay
remain included. Turn snapshots are observed at completed foreground boundaries,
not during a partially swapped inactive-player packet. Terrain sampling accepts
only exact active-label pixels inside the precise world rectangle; it still
rejects wrong or expired pixels. These oracle changes have synthetic regression
coverage and do not discard the failures that motivated the fixes.

Horizontal engine headings switch from triangle to decay envelopes; accepted
vertical carrier/envelope parameters are unchanged. Actual PSG PCM is retained
in `issue13-audition-v58`, alongside pre-change `issue13-audition-v50` and the
original MAME/PROM reference. The normalized sixth partial falls from 0.539/0.577
to 0.430/0.429 for right/left, close to source targets 0.418/0.500; full spectral
distance is approximately unchanged on the right and improves on the left.
The 25.031-second fixture is audible and unclipped (peak 18,989/32,767). This is
still an adaptation, not a claim of subjective arcade equivalence.

The completed workloads run in openMSX on the 128 KB Panasonic FS-A1WSX reference,
factory CPU switching, NTSC refresh, full HUD, unchanged original scenery/colors,
complete car drawings and real sprite limits. Physical hardware/PAL/WebMSX
gameplay and human listening acceptance remain unqualified. The older reported
unlocalized visual defects remain open; these bounded source-pixel/scanline
checks do not prove every displayed pixel correct. Keep issue #13 and PR #31 open
for that review rather than merging on performance averages alone.

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

### Rapid alternating-frame report and replay binding

The user clarified that several briefly alternating frames contained unrelated
looking graphics before returning to normal, and could not distinguish their
locations. This remains open; the camera correction alone does not establish
that every reported defect is resolved. The delivered v4 ROM bytes are unchanged.

An additional v43 audit retains full RAM, bitmap VRAM and video registers at
all 7,195 gameplay latches, without the previous death/flag/smoke frame
exclusions (`issue13-all-scanout-v43-bound2`). A 2,430-point raw-scanout grid
shows only two large differences from latch-time VRAM: partial blanking during
scene transitions at 58.261 and 93.189 seconds. Other differences peak at 35
points, including sprites. The independent scenery grid checks 5,576,125 pixels;
its bounded differences peak at eight during death effects. Excluding death
leaves two one-pixel flag-transition differences. These are diagnostic results,
not a passing all-pixel or effect-transition acceptance gate.

The scaled-window follow-up retains 7,491 screenshots. Its exploratory palette
grid compares 7,194 gameplay screenshots against nearby raw frames; at least
1,323 of 2,430 points remain after excluding blended OSD/scaler colors and
white/yellow overlay text. Maximum disagreement is 27 points after temporal
alignment. This capture path can return a previously displayed frame; comparison
against nearby frames does not establish presentation timing or every-pixel
correctness. No additional large scrambled frame has been localized here.
Artifacts remain private under `issue13-window-replay-v43`.

Replay diagnosis exposed a separate tooling defect: openMSX can warn and load
changed bytes from a recorded filename even when the selected analysis ROM
matches the replay's saved hash. Once `newrallyx.rom` advanced to v4, that path
was unsuitable for v43 playback. The probe now relocates matching cartridge
filenames in a private replay copy, preserves the required XML system ID and
state/input/timing payloads, verifies the actually loaded ROM's SHA-1, and
rejects changed-ROM warnings. The source replay remains untouched. The full
old replay passes the earlier bounded grid/latch checks with the v4 default
file still present (`issue13-human-replay-bound-v43`); that result still does
not resolve the user's visual report.

Normal and debug launches now retain a session-local `cartridge.rom` beside
their replay and record the source path/hash separately. Later builds cannot
replace the captured cartridge. The updated launcher passes real keyboard
capture, replay restoration and normal-quit capture
(`issue13-retained-cartridge-capture.log`). The current suite passes 426 tests
(`issue13-retained-replay-tests.log`). No additional game renderer, graphics,
audio or timing change accompanies this diagnostic correction.

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

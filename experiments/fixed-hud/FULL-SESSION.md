# Shared gameplay with the optimized SCREEN4 presenter

The default experiment now runs complete sessions using revision
`6d562a791b0cc242119a31dd686ff8e93eb94fe0` of the audio branch. Active gameplay
keeps the accepted 200/56 framing, original-size cars, six-digit capped scores,
ROUND capped99, up to four life icons and the larger radar/fuel panel.

## Build and test

```sh
make build-experiments       # Full optimized cartridge; also builds its pinned reference
make run-experiments         # Opens that cartridge, not the old first-stage ROM
make run-experiments TEST_MODE=1 # Separate test ROM: Return advances, = prevents deaths
make run-experiments HUD_VARIANT=classic # Separate previous RND/gauge variant
make run-experiments MSX_LOGO=0 # Separate title build with the logo module omitted
make test-experiments        # Units, seven graphics scenarios, steering, audio and clip matrix
make profile-experiments    # Native three-enemy directional sample and JSON/CSV ledger
make run-audio-reference     # Independent production SCREEN5 comparison
make run-first-stage ENEMIES=3 # Earlier three-enemy benchmark, unchanged
```

From another checkout, use
`make -C /Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx run-experiments`.
The full cartridge is `references/experiments/full-session/fixed-hud.rom`; the
delivered copy is `outputs/test-roms/newrallyx-screen4-full-game.rom`.
Each export also creates a byte-identical copy ending in ` [ASCII16].rom`.
Use that filename when loading through WebMSX AUTO: its
[documented filename hint](https://github.com/ppeccin/WebMSX/blob/master/doc/README.md#rom-format-or-mapper-type)
selects ASCII16 without a manual mapper change. This is file metadata, not a
universal internal cartridge signature; preserve the bracketed suffix. The
canonical ROM/hash and measured cycle budgets are unchanged. Normal, test,
classic and no-logo exports all include this copy, recorded as `webmsx_rom` in
their build manifest.
Use an MSX2+ V9958 with at least 128 KiB mapper RAM; the verified configuration is
Panasonic FS-A1WSX_NR128 in openMSX 21.0. Real sprite limits remain enabled.

Controls: 5 inserts a credit; 1/2 start one/two players. Arrows or joystick 1 steer;
Space/Ctrl or trigger A release smoke. P pauses, F4 toggles mute, F5 advances a
round without awarding completion points. The first stage uses its native one
enemy; RND4 uses three, with subsequent native population/difficulty progression.
The complete build deliberately has no fixed diagnostic population clamp.

TEST_MODE defaults to0. In TEST_MODE=1, Return advances once per key press and
equals toggles invulnerability against cars/rocks; walls remain solid. The
international equals key and the target Japanese Shift+equals matrix are both
tested. A held Return must be released and sampled again after a cold load to
produce another edge. The test copy is
`outputs/test-roms/newrallyx-screen4-full-game-test.rom`; its hash and flag are
recorded separately. Legacy F5 behavior is retained.

## HUD variants and cold startup

The default compact include uses the same authored4x5 font for centered FUEL,
white ROUND and its right-aligned number. Red endpoints are2x2, the red center
is2x3, and six yellow ticks are1x1. All marker pixels reflect around x=23.5;
the endpoints coincide exactly with the48px full bar. Fuel empties left to
right, using the existing three sprites. Scores hide leading zeroes, retain
one zero for zero, and keep the999999 display cap.

See [the HUD module contract](hud/README.md) for include selection, API,
memory/register ownership, hardware limits and verification. `classic` is the
preceding RND/gauge appearance, not a second version of the new symmetric
gauge. Its separate export has the suffix `-hud-classic`. Include selection is
assembly-time only. Broader modularization is deferred to
[issue #32](https://github.com/sandersouza/msxgp-newrallyx/issues/32), with a strict
zero-additional-resource/timing gate; it is not implemented by this delivery.

Cold startup inspects every refresh of the untouched arcade recording, then
replays71 lossless states on the original timeline (about12.53s, no1.5x speedup).
Hidden-page deltas and shared literals replace the previous ten full-screen
slides. State selection respects a conservative CPU/transfer budget and mapper
capacity; fast intermediate states may be omitted, as explicitly authorized.
This is temporal approximation, not frame-for-frame emulation. Original pixels
retain the established1:1 crop into256x212 and RGB333 mapping; active gameplay
assets are unchanged. The final matrix endpoint is detected per native refresh.

Any keyboard key skips startup. The cold UI IRQ scans all11 keyboard rows;
active-game IRQs never call that routine. Skip is checked between spans (at most
256 transferred bytes) and during waits/initial HMMV clearing. A held skip key is
consumed until every row releases, preventing accidental coin/start events.
The VDP status selector is restored, any initial command is stopped, and the
common seed/audio reset runs before the title. Boot descriptors useD300 RAM;
IM2 vectors/trampoline and theF380 stack remain intact. The existingD300..F2FF
cleanup restores native state before the UI.

`session_boot_verify.py` compares every selected published bitmap, every
post-clear publication deadline, PSG silence, overall duration and the complete
title against independent source pixels. `session_boot_skip_verify.py` exercises
all11 keyboard rows, initial fill/RAM-test/matrix skips and held coin/start/Return
keys through the real key matrix. This is emulator evidence; final visual
acceptance remains with the user. Boot elapsed cycles include waits and IRQs,
and must never be added to active-frame CPU costs.

Current long-route caveat: the16000-refresh keyboard stress reaches only four
distinct poses after refresh5000 and fails its movement-diversity gate. Repeating
the same probe on the preceding e6b442 ROM passes with292 later poses. The boot
changes startup timing; the cause of the newly exposed corner stall is not
isolated. Preserve both reports and do not infer full-course stability from
the unchanged short three-enemy profile or passing graphics contracts.

## Optional hardware-check module

`session-startup-options.inc` contains the single `INCLUDE "session-boot.inc"`.
Comment/remove that line and rebuild to omit the presentation. Alternatively:

```sh
make run-experiments HARDWARE_CHECK=1
make run-experiments HARDWARE_CHECK=0
```

The flag0 comparison has a separate `-no-check` bundle/export. Selection happens
at build time: omitted replay code, native-capture resources, descriptors and
cold-IRQ key gate consume no runtime dispatch. The shared startup-worker bank
remains because it also holds the independent compact-ROUND/test-key workers.
No active-game rendering, audio or graphics are changed by module selection.

The inline API contract in `session-boot.inc` documents entry/exit, registers,
RAM/VRAM and caller cleanup. Boot explicitly selects palette index0 (black) for
VDP R7. On exit it restores the normal BLACK index without exposing the boot
palette's light-yellow entry during native-state restoration. Pixel/keyboard
proofs check enabled mode; `session_boot_module_verify.py` also validates omitted
symbols/resources and real-keyboard start/HUD workers in the disabled build.

The complete cast moves up8px, preserving all96 original reveal bitmaps and
delays. One centered terminal line at y186 reads
`[5] insert coin - [1/2] start player(s)`, without reversed text. Only5 and1/2
blink. The approved `namco - retrowork` PNG is copied at1:1:162x10 at47,198,
horizontally centered with exactly four blank rows below it. The complete user wordmark is imported as a
fixed mask; no replacement glyphs are generated.

The optional MSX label is54x20 at194,8, using uniform3:1 sampling of the supplied
black/white logo. Removing its include removes its routine, bitmap and call.
[The title contract](TITLE.md) documents selection, resource ownership and the
independent original-pixel/full-title/on-off verification.

The world S stays red and fixed; only its radar point blinks. The stationary
L-before-S collection fixture exposes the old wrong active-flag guard at
radar-144; the corrected guard continues blinking S after L is gone.

Enemy stone reactions now use the original181B/1885 projection/recoil rules.
Cold loading tags stone cells with spare navigation bit4; route selection masks
to bits0..3, with no new navigation RAM or per-enemy scan over every stone.
Recoil uses the original one-pixel kinematics eight times, avoiding the ordinary
two-tick packet multiplier. The originalE0 recovery and50-tick immunity are
retained.404 controlled cases compare all32 descriptor bytes with unmodified
arcade execution;64 paired exit-mask cases prove that stone tags do not alter
navigation choices. The integrated oracle checks the entire tagged navigation
table on each stable snapshot. These fixtures do not claim a natural full course.

## Integration and visual scope

The original cast, credit/player selection, start cue, challenge and game-over
screens use the selected source's SCREEN5 producer. The challenge presentation
reveals its native-size items and types its text in 66 units over 276 physical
refreshes (about 4.6 seconds), followed by the native cue/final wait. Gameplay
returns to SCREEN4.
Original Z80 rules retain flags, S/L awards, fuel conversion, bonus lives, enemy
AI/contact, smoke, death/restart, turns, per-player state and high score. Award
inscriptions use their original pixels and size. The 2UP label is phase compensated.
The native demo starts after the original idle interval; inserting a credit exits
it. The source PSG worker replaces the smaller laboratory audio adapter.

The user approved 55/576 changed pixels per 24x24 stone only for this experiment
on 2026-10-28. This is the only newly authorized object reduction. Previous
scenery/edge/mask and smoke/explosion concessions remain scoped to the experiment.
Cars are complete; physical eight-sprites-per-line limits may cull whole sprite
layers when many cars share a line. Final visual/timing acceptance is the user's.

Four native world maps are combined with runtime native flag/stone placement.
Four additional RAM segments hold the world and normal/S-hidden flag caches.
The extra S-hidden segment costs 16 KiB; the minimum mapper remains 128 KiB.
Flag radar dots are built for 64 phases on scene load, then cleared in both
caches on capture. Capture generations and the blink bit are separate keys,
avoiding time-based generation wrap. Only actor radar characters change during
ordinary motion. Eight 16 KiB pattern/color sets now use the existing 128 KiB
VRAM: each has patterns at +0000..07FF and colors at +2000..27FF. The two name
tables move to 0800/0C00; original sprite patterns/colors/SAT remain in the gaps.
VDP R4, R3/R10 and R2 bases are checked independently by the graphics oracle.
Cold UI/round changes invalidate and prewarm all eight sets with the initial
phase while display is off, including the selected player's label. An exact
phase lookup precedes cost ranking of seven inactive candidates; the visible
set is always excluded. Cost ranking uses offline 256-cycle bins, not a timing
measurement. Cache metadata costs 76 additional RAM bytes in main Page0 RAM. Phase entries
own2820..2827, flag-loaded2860..2867, popup-loaded2880..2887, and lookup28C0..28FF.
Smoke candidate rows exclusively own2800..281F, and the sparse smoke list owns
0800..13FF. Assembly asserts the phase/row ranges do not overlap. The previous
2800 phase entries aliased the smoke row marks and corrupted the boundary/HUD.
The validated lookup now adds the phase table low byte rather than assuming zero. No extra RAM
segment is required. Cold prewarm time is recorded separately in `Events`.

Boundary transitions are compiled into ROM instruction streams with six-byte
gap merging, using the same bounded OUTI helper as the HUD. They transfer exact
changed bytes without the per-fragment interpreter. S-only radar blinking patches
one pattern byte when the phase and capture generation are otherwise unchanged.
Seven complete immutable car poses share previously unused sprite patterns
200..255. Other poses, all clipped cars and sentinel tails keep private buffers;
SAT order, inks, dimensions and physical sprite limits are unchanged. Ordinary
vertical clips write zero/live/zero runs once, with unrolled masked runs. The
existing sentinel implementation remains intact.

Keyboard/joystick hardware is sampled once per presentation instead of again
for each catch-up tick. The native simulation and corner-risk lifetime retain
their 60 Hz clock; held input is reused within that presentation. Input, pause,
smoke, F5, coin and four-way rollover are covered by the session regressions.

The expanded boundary atlas uses 160..207 plus 137..145; its second family retains
208..255. Static HUD slots stop at 136; flags use 146..155, 2UP uses 156..159,
actors use 64..71 and point inscriptions 92..94. Mapper helpers restore Page0 before
returning. Shared audio state occupies D150..D157/E9A0..E9EF, leaving DC00..DF7F
for native round objects. Cold/UI adapters execute from separate Page0 RAM.

The production corner guard is retained: save the 44 movement/camera bytes at
D200..D22B around risky turns, validate with native contact/wall routines, then
roll back an invalid corner while preserving the selected escape heading. Input
rollover grants eight protected ticks. The guard fields remain at C7E6..C7E9;
score, fuel, enemies and clocks are not rolled back. This closes the integration
omission that allowed rapid turns to enter scenery, but is not a complete
corner-escape solution: the latest long steering regression finds a persistent
stall and fails its movement-diversity condition. See coverage below.

The player radar point alternates white/black on physical clock bit 4, enemies
request red and flags remain yellow. Player drawing has final priority. SCREEN4
allows one foreground color per eight-pixel row: a flag/enemy collision preserves
yellow; a player overlap can share its flash color with other packed points.
Their masks/positions are retained. The S flag flashes on both radar and world;
world tiles 26/56 share the original pattern and dimensions. These changes add
no new graphical reduction, sprites or active bitmap copy.

## Challenge player speed

The original arcade parameters explicitly raise player speed while both enemy
cohorts are parked. A real first credit/start and seeded original initializers
in MAME0.289 return native forward targets672,688,704,704 for displayed rounds
3,7,11,15:2.625,2.6875,2.75,2.75 pixels per native tick. The prior port applied
its512/256=2px/tick player bandwidth cap to all of them.

The generated full-session native bank now bypasses that limiter only when both
native enemy speed parametersE025/E029 are zero. Native acceleration, steering,
fuel and simulation clocks remain responsible for movement. Fuel exhaustion
activates the cohorts and restores the ordinary cap. The shared production
source and first-stage adapter are not modified. A committed real-session RND3
snapshot reaches2.625px/tick against the same native target.

The64 actual-cartridge cases cover both velocity signs, ordinary lower speeds,
all four captured challenge targets and the fuel-exhaustion exit. The previous
b3d4a5 cartridge fails eight challenge target cases; its immutable report remains
under `references/experiments/full-session/speed-proof-*/`. The new cases pass.
The limiter fixture costs71cycles/parked call (0.020ms); ordinary cases average
281.083cycles, maximum340. These controlled entry-through-RET samples are in the
workbook Events tab, separate from integrated parent costs and active FPS.
Only native bank173 differs from b3d4a5; every graphics/audio bank is identical.
Original RAM, traces, source inputs and captured parameters stay ignored under
`references/experiments/arcade-challenge-speed/`.

## Audio corrections

Every blocking video, UI or round load first disables PSG tone/noise, zeroes all
three volumes, clears pending effects and invalidates the register cache. The
melody request and mute preference survive as needed by the next scene. The
game-over screen waits for its complete 248-frame score rather than returning to
the cast after 180 UI refreshes. Challenge gameplay explicitly re-arms its music.

The user approved revoicing the engine on2026-10-28 to allow independent gain
control. A new real-input MAME0.289 capture records4,000 original frames,
37 complete smoke bursts, and both motion axes without guest RAM/ROM writes,
forced sound calls, or muted music voices. The engine WSG phase step is544
(49.8046875Hz) for the observed motion cases. Moving PSG tones now use period2246
(49.804444Hz); idle remains49.937849Hz. Levels12/13 and physical-clock gain mixing
remain. Measured RMS reductions versus5451bd89 are14.02%,14.99%,16.37%.
The Namco changes engine wavetable with heading; one AY square channel cannot
reproduce those complex waveforms. This change calibrates pitch and leaves its
accepted square timbre as an explicit approximation, using C alone. No new
sample-rate interrupt or software PCM is introduced.

Challenge notes, linear volumes, accompaniment order and terminator pauses are
compiled from the contributor-supplied arcade sound routine executing in pinned
MAME 0.289. The original loop is 1,540 native ticks, compiled into 770 cached PSG
frames (1,033 bytes); the first accompaniment is 23/13, followed by 14/13. The
dictionary now uses181/256 entries, including cached crash pitches and levels. The source WSG trace hash is
`ed840e22443756b335458b88517fea5e0c927a892c903cc3eeaef1b9b08867cf`.
This is an isolated sound fixture, not a natural full arcade course; captures,
original RAM and compiled assets remain ignored under `references/`.

Collision now uses a cached noise attack/hold/release instead of the previous
long hardware decay: eight full-volume score frames, then a short stepped
release (25 score frames total, about0.83 seconds). C retains noise while B
adds a falling100..32Hz bass body and is restored to music afterwards;
consecutive collisions work. DC-removed, Hann-windowed PCM analysis over
30..200Hz measures4.47dB and3.96dB more low-band power than70d633 for two
consecutive crashes, with no PCM clipping. This measures added bass, not arcade
waveform equivalence or subjective acceptance.
The gated-noise direction follows the [MAME 0.289 arcade circuit model](https://github.com/mamedev/mame/blob/mame0289/src/mame/namco/nl_rallyx.cpp).
The isolated netlist PCM fixture produced an unusably quiet BANG signal and is
not treated as waveform equivalence evidence. AY noise/timbre remains an
approximation, requiring the user's auditory acceptance.

The actual smoke uses WSG waveform4: a16th-harmonic square carrier gated for
half of each waveform cycle. Its four observed phase steps are1456,1536,1632,1728
at15/15 volume. Two30Hz packets use pair-midpoint carrier/envelope periods51/45
and hardware saw shape8. The envelope approximates the original square gate;
this is a derived PSG approximation, not literal playback of the captured WAV.
Smoke briefly leases B alongside C for approximately66.75ms, preserving A and
restoring B to the current music note at effect end. The PSG has three tone
channels plus a shared noise generator, not four independent channels.
Two PCM fixtures measure2721/2363RMS over the same0.008..0.118s windows, without
clipping. Against the immediately previous8e3835 smoke these are comparable
levels; the previous four-frame noise decay has been replaced by the shorter
captured rising tone. Raw arcade audio, source WSG trace, H/V engine clips and
provenance stay in ignored `references/experiments/arcade-motion-audio/`.

## Verified coverage

The individually run checks include63 unit tests (62 pass, one optional skip),
seven emulator graphics scenarios, 64 captured-parameter speed cases, recorded audio and3,147 synthetic complete-
pattern/SAT/color clipping cases.592 stable active snapshots pass the independent
world, boundary, HUD/radar, numeric/life SAT and complete-car checks.63 cold
transitions assert silence. The new smoke scenario checks every one of300
committed frames with three native enemies and all eight fine-scroll phases in
both axes; the old8e3835 ROM fails at smoke-0047 on boundary column0,row6.
Continuous AVI forces real scanout; the pixel oracle evaluates committed VRAM
snapshots, not every physical scanout line. Evidence is indexed in
`outputs/full-session/verification.json`.

The current `make test-experiments` command also passes the16,000-refresh
steering run:7,425 native contact checks,6 games and292 distinct
poses after refresh5,000. It includes death holds and restarts, not16,000 active
presented frames.

**Historical open issue:** b3d4a5 stalled near native cell1639 and failed the
same route with only five later poses. That immutable failure is preserved.
The new route passes, but changed execution timing changes trajectories; this
speed correction is not a confirmed root-cause fix for every corner stall.

Death and round-transition boundary fixtures are explicitly marked in the
scenario source. The flag scenario invokes the actual contact handler with known
native cells, then lets normal scoring/fuel/round logic settle. These are
controlled feature tests, not a human-completed course. The 16,000-refresh run
includes death holds and restarts; it is not all active play. Joystick protocol is
shared and preserved by inspection; a physical controller has not been tested.

## Current integrated timing sample

Compact normal ROM SHA256:
`e6b4420f85217a380f4c20923965fc7da3d53c8c3a83837846ed8f3e4b112dae`.
Test-mode ROM SHA256:
`546b389c4ebba18c25fcb9e2447b1ca0c9ceb0c2a376a1f8a1101cac5a8888d5`.
Both are4,030,464 bytes. The ledger/workbook under
`outputs/full-session` is bound to the normal compact ROM. Test/classic/no-logo
checks have independent hashes; they do not establish matched FPS.

The356-interval directional sample contains238
active intervals with three moving native enemies:7.959029s,
29.903146 presented FPS,22.627519ms mean CPU
work excluding synchronization. There are237 two-refresh
intervals and one three-refresh interval. Late frame245 uses
35.586ms of work and misses readiness by
3.058ms. This is a short sample, not a full-course
29.97FPS claim or a matched marginal speedup over an archived trajectory.

Physical refresh is59.922743Hz; two-refresh cadence is29.961372FPS. The requested
29.97FPS is nominal. Observed VDP VR spans11,172 cycles;5,000 usable cycles is
still a planning assumption. Commit begins at physical line245, cycles36..40,
and costs2,550..6,923 cycles. Logic, audio, stone
checks and preparations run in foreground across visible scanlines and VBlank;
publication is synchronized. There is no fixed gameplay-logic scanline/cycle.
Endpoint VR checks and the uninstrumented control pass. No event pause is added.

HUD Prepare averages1,962 cycles/frame; HUD Commit averages
1,478. HUD Commit is already included in overall Commit. The workbook
records calls, inclusive/self costs, tails/maxima and observed raster positions;
never add inclusive parent and child costs.

The active stone-probe maximum is285 cycles, so this short workload contains no
full recoil. The separate404-case fixture reaches5,700 cycles for original
recoil. This does not prove sustained29.97FPS during repeated stone impacts.
UI-only logo draw costs23,007 cycles once per cast draw; unchanged footer ticks
cost53 cycles and a blink transfer peaks at10,596 inclusive cycles. UI/boot
costs include waits/IRQs as documented and are excluded from active FPS.

## Previous integrated timing sample (archived70d633)

ROM SHA256:
`70d6335163a702045b4a6da5cc3ac4eba1dd5e5b48e1aeda3cb628a81887a3c4`.
The archived ledger is `outputs/full-session/baseline-70d633/cycle-budget.xlsx`, with machine-readable
`cycle-ledger.json` and `routines.csv`. Its profile contains 356 intervals, of
which 246 have active endpoints, three native enemies, no death/bonus and RND4.
The active duration is8.225605 seconds:29.906615 presented FPS,22.954263ms mean
CPU work excluding synchronization, one late presentation (245 two-refresh,
one three-refresh). The immediate b3d4a5 baseline had the same1/246 late presentations
and29.906615FPS. Its mean work was22.936030ms; the new mean adds0.018233ms. The remaining frame is237, following a stopped interval/camera
reset; its work is43.771ms. All three enemies changed position. This is a short
directional sample, not evidence of29.97FPS throughout a phase or a matched
comparison to the old course. No event pause was added.

Refresh is 59.922743 Hz at 3,579,545 Hz / 59,736 cycles; two-refresh cadence is 29.961372 FPS.
The requested nominal 29.97 FPS remains separate. The observed physical VR interval
is 11,172 cycles; 5,000 usable cycles is still only a planning assumption. Commit
cost ranges 2,550..6,970 cycles, all 246 inside VR. Mean work leaves 10.412 ms relative
to the nominal target budget, but the tail and publication alignment still miss
deadlines. No recurring overload is hidden as an event pause.

Logic, PSG, sprite preparation and inactive-table drawing run in foreground
across visible scanlines and VBlank. Commit begins physical line 245, cycles 36..40,
after HALT. The active IRQ only acknowledges the VDP and advances the clock;
UI IRQs additionally latch keys. There is no fixed scanline/cycle for gameplay
logic. The workbook records the observed ranges and inclusive/self routine costs.
Every endpoint VR bit and span was checked against the native VDP clock; a second
run without routine breakpoints matched all camera/tick/actor states within five
cycles of boundary observation. `Events` separately records cold load/video,
audio stop, challenge reveal, cache prewarm and ten flag-capture invalidations,
with calls and inclusive/self mean, P95 and maximum costs. Audio stop costs
2,645 cycles (0.739 ms); clearing both flag caches costs 15,910 cycles (4.445 ms)
per capture. These event samples are excluded from active FPS; no extra capture
pause is inserted. Prewarm averages 438,976 cycles (122.635 ms), maximum 442,399
cycles (123.591 ms). Video restoration rises from 201.078 ms in the previous
sample to 421.469 ms; this cold transition tradeoff is excluded from active FPS.
The cartridge is 3,997,696 bytes (244 ASCII16 banks), 64 KiB larger than 5451bd89.
No physical hardware claim is made.

The previous integrated ledgers/workbooks/verification are preserved under
`outputs/full-session/baseline-b3d4a5/`, `baseline-8e3835/`, `baseline-5451bd/` and `baseline-d6c508/`. The input sequence
is the same, but execution timing changes the resulting trajectory and
active/death partition. The samples do not establish a matched marginal speedup.

The preserved first-stage ROM remains byte-identical with SHA256
`34aab943550df300e3258bd6bb43f853330eca48a7a06acbf8a4b1d8702cf46a`.
Its 29.914200 FPS result belongs to its own route and cannot be transferred to the
integrated game. Further tail-cost optimization and final visual/audio acceptance
remain open; the functional 13 branch and both build choices are intact.

## Last-flag melody before remaining-fuel conversion

The experiment now permits the existing three-voice complete score (original
parts8/9/10) in Round_State1. The older selector silenced all nonzero round
states. The original1B03 minimum-settle wait is followed by its1B0A sound-ready
condition: the port yields through GameSession_CompletionWait until the score
clears native request bit5. Only then may Completion_Begin consume fuel/award
points. The timer saturates at the minimum rather than wrapping while music
plays. Pausing freezes the score cursor and timer; silent attract mode bypasses
an unplayed request so it cannot deadlock. Conversion effects and cold-transition
silence retain their existing handlers.

This adapter is experimental only; src/completion.inc and the functional13 build
are unchanged. Settlement runs in the foreground from the already loaded cold
worker:33 additional code bytes use its existing RAM reservation. There is
no spin/HALT, new bank switch, RAM variable or VRAM transfer. The
active selector adds one taken-branch difference (5 cycles per call). Measured
music-wait calls cost103 inclusive cycles; the first converter call includes
Completion_Begin and must not be added again as a child cost.

arcade_clear_reference.py reproducibly captures the original2580 sound routine
with request28 and contributor RAM seed. Its termination call is107 at the
native60.606Hz cadence; the port plays53 two-refresh updates. The audio proof
compares all three note voices against the original trace, allowing integer-PSG
period quantization, and records actual PCM. The flags integration checks
normal/S/L last captures, unchanged fuel/score while music plays, conversion
order, and pause/resume with a frozen cursor/timer. These are controlled contact
fixtures, not a keyboard-only full-course or hardware-audio acceptance claim.

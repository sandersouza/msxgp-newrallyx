# Issue #13: buffered PSG music, tonal effects and engine

Tracking: [#13](https://github.com/sandersouza/msxgp-newrallyx/issues/13),
[PR #31](https://github.com/sandersouza/msxgp-newrallyx/pull/31).
The gameplay baseline is merged PR #30, commit `6b40449`.

## Agreed adaptation

The user selected fluid audio over arcade-exact synchronization. Subsequent
listening rejected the initial two-voice/noise-only approximation. The current
arrangement restores the third original part where present and gives melodic
effects their original note contours; the earlier channel policy is superseded.

- Start/completion use all three original parts, with balanced gains and short
  note articulation. Normal/challenge music has two parts; C is then available
  for the engine or effects. Namco wavetable instruments are adapted to PSG.
- C plays pitched effects, smoke noise or a combined tone/noise crash. Effects
  temporarily replace C's music/engine; A/B continue. An autonomous repeating
  hardware envelope produces the engine buzz between effect intervals.
- The build compiles contributor-supplied note tables into duration/period/volume
  packets. The MSX reads a new packet only at a note boundary.
- A physical-refresh clock services audio at approximately 30 Hz, after the
  car/camera packet is ready. The PSG continues oscillating between writes.
  Odd refresh remainders survive service, so three-refresh rendering intervals
  cannot slow the score. Its register latches sustain playback; the effect FIFO
  is software.
- **F4** changes output amplitudes only. Music, queue and gameplay continue.
  Music continues during pause. Attract gameplay is muted.

`make build` enables PSG. `make build AUDIO=0` reconstructs the accepted silent
full-game build. Bounded stages remain silent. The lower-level builder requires
`--full-game --audio` explicitly.

## Music and event contract

`scripts/msx/audio_score.py` reads validated original melody pointers, note/octave
values and durations. It arranges the background playlist, challenge accompaniment
choices, start, completion and game-over songs. Compilation samples boundaries every
two reference ticks; playback finishes when any original part ends, including
the third voice. Start uses all of the original 18/19/20 group, and completion
uses 8/9/10. Shared table tails must not extend either cue. All three parts
start together, rather than being serialized or alternated.
Background/challenge scores loop; one-shot songs clear their request.
Insert-coin and player-select screens have no music. Accepting Start plays the
one-shot introduction while the session waits, before loading/releasing gameplay.
Normal scene loads request background music only; phase changes do not replay
the start cue. UI/attract changes override stale native music requests, and a
silent scene explicitly replaces the previous PSG output.

Music and effects use 5,974 bytes of a private 6 KB ROM prefix. A 768-byte
dictionary stores period-low, period-high and volume planes. Each music packet
holds duration and three one-byte tone indices; effect packets hold duration,
tone index, noise period and C mixer bits. Expanded music goldens have nine
bytes per frame. Original song data is never checked in.

| Effect ID | Event | Source / arrangement |
| --- | --- | --- |
| 1 | Fuel award/conversion | Request bit 1 / original melody 11 |
| 2 | Smoke placement | Persistent placement counter / bit 4 / authored noise |
| 3 | Low-fuel warning | Request bit 5 / original melody 6 |
| 4 | Extra life | Request bit 0 / original melody 7 |
| 5 | Credit | Credit adapter / third request bit 7 / original melody 0 |
| 6 | Ordinary flag | Persistent count/kind / original melody 3 |
| 7 | Special/lucky/bonus flag | Flag kind / original melody 4 |
| 8 | Crash | Actual death / bit 7 / descending tone and noise |
| 9 | Fuel recovery | Third request bit 6 / original melody 1 |

Persistent flag/smoke counters retain events when transient request bits disappear
before service. Simultaneous requests coalesce by priority, with crash/capture
ahead of smoke/fuel. The eight-entry FIFO never blocks gameplay: saturation
increments its drop counter. Repeated active or already queued IDs coalesce;
higher-priority effects preempt lower ones. Crash always wins, including over
fuel recovery ID 9. Other pending effects wait for the active contour to finish.
Effect durations advance from elapsed physical-clock packets. The bounded fuel
adapter explicitly requests recovery after restoring the Lucky fuel gauge.

The engine derives idle/cruise/drive pitch from the original engine note table,
with four heading-dependent dominant-harmonic approximations. PSG shape 8
repeats a decaying envelope; period changes follow coarse native velocity and
wall state. An ultrasonic tone gate halves its audible gain. The measured
up-heading fundamentals are approximately 50, 57 and 66 Hz. A cached engine key
avoids steady-state recomputation. This approximates the original harmonic
character without per-sample CPU synthesis; it does not reproduce the PROM.

## Hardware and memory

Production executes from an ASCII16 ROM bank. Its packet/queue/cursor state uses
80 bytes in the selected core's unused `$e9a0..$e9ef` gap. The build rejects new
selected native address references there; instrumented gameplay rejects unexpected
writes. Commands at `$e9f4..$e9f6` remain separate. The worker leaves Page0 and
terrain-cache ownership untouched and returns the player ROM bank.

Raster IRQs remain enabled. Factory Panasonic turbo is used for CPU work; VDP
work retains its established clock policy. PSG register 7 preserves I/O direction
bits. The writer tracks registers 0..13 (including the envelope), and never
writes joystick registers 14/15.

An independent reference kernel uses another mapper segment, separate from the
terrain cache. Its original `$8a00..$8bff` sound workspace maps to
`$3800..$39ff`, avoiding presentation code at `$ea00..$ebfe`. This diagnostic
kernel is not the production scheduling path. Its shim now starts at RAM
`$1800` / ROM `$9800`, after the expanded score prefix; production starts at
ROM `$9b00`. Original reference sound tables at `$2580` remain intact.

The pinned MAME [Rally-X driver](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/mame/namco/rallyx.cpp)
connects three Namco voices and discrete BANG. Its
[WSG implementation](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/devices/sound/namco.cpp)
defines nominal frequency as `phase_step * 96000 / 2^20`.
The [AY data manual](https://pub.intvprime.com/ba4ef/ie/Programming/AY-3-8910-8912-Programmable-Sound-Generator-Data-Manual.pdf)
defines `PSG_clock / (16 * period)`; the MSX clock here is 1,789,772.5 Hz.
Nearest bounded divisors set pitch. The volume curve approximates linear source
amplitudes with nominal AY 3 dB steps, following the
[openMSX amplitude model](https://github.com/openMSX/openMSX/blob/master/src/sound/AY8910.cc).
Nominal oscillator frequency does not establish perceived pitch or analog timbre.

## Original reference acquisition

`scripts/audio_inventory.py --sequencer` observes MAME 0.289 with real
coin/start/smoke inputs. It never writes guest RAM/ROM, registers or PC. Outputs
include consecutive frame states, raw ordered command/WSG/BANG writes, sound-call
entry/exit snapshots, exact original stack-write addresses and the local PROM.
Lua retains tap userdata to prevent GC detaching observers. Reset RAM tests are
excluded from gameplay/request coverage.

Two fresh 7,200-frame acquisitions have identical frame/write/input files:
166,502 raw writes each, three simultaneous active voices, reset complete at
frame 757. BANG has 256 rising electrical edges across two write frames; this
does not mean 256 gameplay explosions. The original route is not a complete
arcade sound inventory. The production inventory above is the current adaptation.
Reference-kernel equality must not be described as exact production audio equality.

All traces, PROMs, disassembly, generated scores, cartridges and PCM remain under
ignored `references/`. Only authored code, synthetic fixtures and documentation ship.

## Validation and usage

See [measured evidence and remaining review](issue13-audio-validation.md).
The target is the FS-A1WSX reference configuration: 128 KB RAM mapper, 128 KB VRAM,
factory CPU switching, real sprite/command limits and full HUD. Physical hardware,
other clocks/PAL and perceptual timbre remain separate qualifications.

```sh
make build
make run
make build AUDIO=0
.venv/bin/python -B scripts/audio_inventory.py --sequencer --output references/build/my-audio-reference
.venv/bin/python -B scripts/audio_runtime_probe.py --rom references/build/my-audio-build/raster-scroll.rom --output references/build/my-audio-proof
.venv/bin/python -B scripts/audio_gameplay_probe.py --rom references/build/my-audio-build/raster-scroll.rom --output references/build/my-live-mute-proof
```

## Optional SCC decision

SCC is evaluated and deferred. Its
[32-byte waveform channels](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/devices/sound/k051649.cpp)
could represent converted Namco wave shapes more closely. That improves timbre;
the current three-voice/shared-C PSG arrangement addresses the base hardware target.
SCC would require explicit expansion-slot selection, safe Page2 switching while
executing elsewhere, restoration across raster IRQs, and testing with ASCII16
and the RAM mapper. No SCC detection, waveform writes or hardware support is
implemented or claimed. PSG always works without an expansion.

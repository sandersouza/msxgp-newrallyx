# Issue #13: buffered PSG music and noise effects

Tracking: [#13](https://github.com/sandersouza/msxgp-newrallyx/issues/13),
[PR #31](https://github.com/sandersouza/msxgp-newrallyx/pull/31).
The gameplay baseline is merged PR #30, commit `6b40449`.

## Agreed adaptation

The user selected fluid audio over arcade-exact synchronization: two basic music
voices, noise for other sounds, and short deferred effect publication.

- PSG tones A/B play two original melody parts. Third parts are omitted;
  Namco wavetable timbres become PSG square waves.
- Noise C plays effects independently. A quiet engine texture fills idle effect
  intervals; discrete effects preempt it.
- The build compiles contributor-supplied note tables into duration/period/volume
  packets. The MSX reads a new packet only at a note boundary.
- A physical-refresh clock services audio at approximately 30 Hz, after the
  car/camera packet is ready. The PSG continues oscillating between writes.
  Its register latches sustain playback; the effect FIFO is software.
- **F4** changes output amplitudes only. Music, queue and gameplay continue.
  Music continues during pause. Attract gameplay is muted.

`make build` enables PSG. `make build AUDIO=0` reconstructs the accepted silent
full-game build. Bounded stages remain silent. The lower-level builder requires
`--full-game --audio` explicitly.

## Music and event contract

`scripts/msx/audio_score.py` reads validated original melody pointers, note/octave
values and durations. It pairs the background playlist, challenge accompaniment
choices, start, completion and game-over songs. Compilation samples boundaries every
two reference ticks; a pair finishes when either selected part ends. These are
deliberate two-voice transcriptions, rather than exact three-voice priority mixing.
Background/challenge scores loop; one-shot songs clear their request.

The score uses 3,911 private ROM bytes. Each packet stores a duration, two tone
periods and packed volume nibbles. Original song data is never checked in.

| Noise ID | Event | Source |
| --- | --- | --- |
| 1 | Fuel award/conversion | Native request bit 1 |
| 2 | Smoke placement | Persistent placement counter / request bit 4 |
| 3 | Low-fuel warning | Native request bit 5 |
| 4 | Extra life | Native request bit 0 |
| 5 | Credit | Credit adapter / third request bit 7 |
| 6 | Ordinary flag | Persistent collected count and flag kind |
| 7 | Special/lucky/bonus flag | Flag kind / native request |
| 8 | Crash | Actual death transition / request bit 7 |

Persistent flag/smoke counters retain events when transient request bits disappear
before service. Simultaneous requests coalesce by priority, with crash/capture
ahead of smoke/fuel. The eight-entry FIFO never blocks gameplay: saturation
increments its drop counter; a crash preempts stale effects. One effect starts
per output packet without waiting for the preceding envelope to finish. These
are authored noise envelopes, rather than copies of wavetable/discrete effects.

## Hardware and memory

Production executes from an ASCII16 ROM bank. Its packet/queue/cursor state uses
80 bytes in the selected core's unused `$e9a0..$e9ef` gap. The build rejects new
selected native address references there; instrumented gameplay rejects unexpected
writes. Commands at `$e9f4..$e9f6` remain separate. The worker leaves Page0 and
terrain-cache ownership untouched and returns the player ROM bank.

Raster IRQs remain enabled. Factory Panasonic turbo is used for CPU work; VDP
work retains its established clock policy. PSG register 7 preserves I/O direction
bits. Audio never writes joystick registers 14/15.

An independent reference kernel uses another mapper segment, separate from the
terrain cache. Its original `$8a00..$8bff` sound workspace maps to
`$3800..$39ff`, avoiding presentation code at `$ea00..$ebfe`. This diagnostic
kernel is not the production scheduling path.

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
arcade sound inventory. The production inventory above is the agreed adaptation.
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
the accepted two-voice PSG transcription addresses the base hardware target.
SCC would require explicit expansion-slot selection, safe Page2 switching while
executing elsewhere, restoration across raster IRQs, and testing with ASCII16
and the RAM mapper. No SCC detection, waveform writes or hardware support is
implemented or claimed. PSG always works without an expansion.

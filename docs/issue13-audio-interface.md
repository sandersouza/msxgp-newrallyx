# Issue #13: original audio acquisition and integration boundary

Tracking: [#13](https://github.com/sandersouza/msxgp-newrallyx/issues/13).
The starting gameplay baseline is merged PR #30, commit `6b40449`.
This first increment supplies an executable reference acquisition and independent
WSG decoder. It does not yet enable sound in the MSX cartridge.

## Source and capture contract

The pinned MAME [Rally-X driver](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/mame/namco/rallyx.cpp)
connects three Namco wavetable voices and a separate discrete BANG input.
The [WSG register implementation](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/devices/sound/namco.cpp)
defines nibble writes, waveform selection and twenty-bit phase steps. For the
96 kHz clock, nominal cycle frequency is `step * 96000 / 2^20`; this is not a
claim about a waveform's dominant harmonic or perceived pitch.

`scripts/audio_inventory.py` validates the existing contributor ROMs, runs pinned
MAME 0.289 with real coin/start/smoke inputs, and captures:

| Output | Meaning |
| --- | --- |
| `frames.tsv` | Consecutive frame-end mode, round, credits, lives, flags, three request bytes and 32 hardware register shadows |
| `writes.tsv` | Every ordered request, WSG and sound-latch write: frame, PC, address, original byte and MAME time string |
| `inputs.tsv` | Actual input-port operations applied by the driver |
| `boot-ready` | Observed execution of the original post-reset entry; RAM-test values are excluded from gameplay/request coverage |
| `wave-prom.bin` | Local-only sound PROM region from the validated inputs |
| `report.json` / `manifest.json` | Observed coverage, input/tool hashes and sealed output integrity |

The taps do not replace write data. No guest RAM/ROM, registers or program
counter are edited. The raw trace retains high bits even though the WSG consumes
only nibbles. Lua retains tap userdata throughout the run so garbage collection
cannot silently detach the observers. Missing frames, malformed writes, missing
reset completion, Lua failures or absent audible WSG activity reject acquisition.

## First measured scope

Two fresh 7,200-frame runs have byte-identical `frames.tsv`, `writes.tsv` and
`inputs.tsv` (`references/build/issue13-original-audio-v2` and `-v3`). Each has
166,502 ordered writes; reset completes at frame 757. Three voices are active
together in the observed sequence. Nominal observed ranges are approximately
49.80..1605.47 Hz, 74.71..600.59 Hz and 65.92..900.88 Hz for voices 0..2.

BANG activity occurs in two write frames, with 256 rising electrical edges.
Those edges must not be interpreted as 256 gameplay explosions. The raw order
and subframe time strings remain available for evaluating an explosion adapter.

The route includes one real credit/start, default forward movement and periodic
smoke. It does not establish the entire music/effect inventory, challenge,
low-fuel, final-game-over or every bonus sound. Output audio is disabled during
register acquisition; no listening or analog-timbre qualification is claimed.
`tests/test_audio_reference.py` uses synthetic state only and checks all three
register layouts, nibble masks, frequency scale, malformed/gapped traces, raw
BANG ordering and exclusion of reset RAM tests from request coverage.

## Runtime constraints for the PSG increment

- The original sound sequencer entry is `$2580`, called by the arcade IRQ.
  Requests are at `$89f4..$89f6`; hardware writes are `$a100..$a11f`, plus
  BANG at `$a180` and sound-enable at `$a182`. These addresses come from the
  local disassembly and the captured write trace, not guessed gameplay events.
- The selected native adapter relocates original `$8000..$8fff` state into
  `$e000..$efff`. Its presentation code occupies `$ea00..$ebfe`
  (`src/full-presentation.inc`, `scripts/msx/full_memory.py`). The sequencer's
  original `$8a00..$8bff` workspace would overlap it. Restoring the sequencer
  without a separate state allocation would overwrite executable renderer code.
- Sound must advance from logical ticks, independently of presentation skips.
  Mute must suppress output while preserving sequencer progress and gameplay.
  Request-ready bits consumed by original gameplay require an explicit contract.
- PSG channel arbitration, volume/timbre approximation and BANG approximation
  still need implementation and listening. Register conversion alone cannot
  prove perceptual fidelity. Joystick-related PSG I/O state must be preserved.
- SCC is optional. The [SCC emulator implementation](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/devices/sound/k051649.cpp)
  provides a waveform-conversion reference, but an external cartridge requires
  explicit slot/mapper isolation. No SCC backend or hardware support is claimed.
- Sound-enabled/muted state equivalence and the full-HUD retained-six/seven
  rendering budgets must pass before enabling audio in the default ROM.

## Reproduction

```sh
.venv/bin/python -B scripts/audio_inventory.py --output references/build/my-audio-reference
.venv/bin/python -B -m unittest tests.test_audio_reference
```

All game-derived traces, PROMs and future audio captures stay under ignored
`references/`. Only authored acquisition/analysis code, synthetic tests and this
decision record are committed. The accepted default gameplay ROM remains the
silent `a31e3b43ae05fae4accac1e6fae58c81c600acd1253b13b6590749e23c6c6953`.

# Issue42: natural sound-clock validation and phase-cache cost

The512KiB continuation now compares sound at its own worker boundaries and
measures event-to-effect latency during real DOS1/Disk BASIC games. The observed
sound sequences agree with the cartridge after accounting for the existing
physical-clock engine gain. No audio clock, note, effect or volume rule is
changed. A separate generated phase-cache exit saves **nine cycles per normal
presented frame**, about2.5 microseconds on the measured Z80, without additional
RAM, stack, mapper traffic or presentation delay. This is not an FPS gain claim.

The supported744KiB ASCII8 ROM,64KiB cartridge requirement, both supported disk
ZIPs, MegaRAM and F10 remain intact. Only the experimental512KiB package changes.
No commit, push, merge or release. Physical/listening and universal acceptance
remain separate from these scoped automated/openMSX results.

## Why native-index PSG snapshots differed

`GameAudio_Tick` consumes physical clock time at30Hz, while game logic can run
multiple native steps before one presentation. Comparing PSG at `Game_Events`
can therefore observe a different sound update despite identical original game
state. The observer now records entry and matched PC/SP return of
`Audio_RuntimeStep`, cumulative elapsed sound steps per cold epoch, music/effect
state and actual PSG. It also captures the actual clock value loaded by
`Audio_EngineGain`, rather than assuming the worker-entry clock stayed fixed.
These are read-only hooks, with code-prefix guards against numeric BIOS aliases.

The remaining engine-volume variation is intentional existing behavior:

```text
phase = (physical_clock >> 1) & 31
drive: volume = 12 + (((phase * 5) & 31) < 5)
other: volume = 12 + (((phase * 7) & 31) < 7)
```

It approximates the calibrated RMS gain using PSG levels12/13. The sound source
explicitly keeps this free physical-clock phase across turns. Resetting it or
forcing audio onto native tick indices would change accepted sound behavior.

Two-player4096-tick runs in both DOS and BASIC each align **2047 sound-worker
steps** with the cartridge. Every music/effect/tone/envelope register agrees.
1977 complete14-register snapshots agree; the other70 differ only in R10's
existing12↔13 engine gain. All1853 observed gain calculations per candidate
match the original formula. Cursor, queue and sound state agree except the
corresponding engine-volume shadow/dirty bytes. The F10 run aligns2048 worker
steps with all14 registers equal throughout.

Two natural flag captures and three deaths occur at the same native indices
and physical clock ticks in the two-player runs. For each event, both worker
entry and completed PSG output occur after **two refresh-tick increments** in
the cartridge and candidate. This is a clock-quantized observation, not a claim
of exact33ms waveform onset. Restored captured flags are correctly excluded
from new capture events. Three player turns restore owners0→1→0→1 with load
kinds0/1/2/2. Original768-byte native states and host game/death/round samples
match at all4096 ticks in each DOS/BASIC/F10 case.

## Phase-cache optimization and measured bounds

Every selector path retains its input phase in B. The common lookup-store exit
can read B instead of reloading global `phase`. The sole ranking bank-selector
callee preserves B; source guards reject another B definition, implicit BC
writer or unknown callee. The input A=global-phase invariant is also checked
at runtime, including cold initialization. Two unreachable bytes after RET
retain **all symbol values** and downstream cold/UI/audio addresses.

The baseline builder reproduces the previous package's exact seals. All four
immutable hot-image hashes remain unchanged. The Page0 cold-worker payload
contains the shorter load and unreachable padding; no asset/palette/geometry,
cache policy, mapping, IRQ ownership or clock changes.

- 3000 identical target/front/keys/lookup/native contexts without an overlapping
  IRQ save exactly nine elapsed reference cycles each; selected slots agree
  for every matching input context, including IRQ-overlapped calls.
- Six360-presentation pairs cover DOS/BASIC at rounds5/10/13 with three/five/six
  enemies, HUD/audio and real sprite limits. All2160 camera/native/tick/PSG/
  active-state records match the exact preceding512KiB package. Every active
  work span, mean, P95 and maximum improves by nine cycles.
- Presentation uses the same refresh counts. Raw interval differences stay
  within nine cycles from synchronization phase; no extra refresh or FPS gain
  is claimed. Existing full-density overloads remain visible in the ledger.
- Independent maze, HUD, navigation and complete-car checks pass. Actual F10
  blocks24 contacts without deaths; the16→17 family wrap also preserves F10.
- Both real disk boots pass the existing857-sample full-PSG and recorded-PCM
  velocity/event fixture. These sound-only fixtures remain distinct from the
  natural latency checks and subjective listening.
- 508 general and94 component tests pass (one existing skip), plus the historical
  module-layout gate. Fresh64KiB cartridge,768KiB MegaRAM DOS/BASIC and legacy
  mapper DOS/BASIC checks pass; their artifact seals remain unchanged.

An earlier unpadded trial shifted downstream symbols and changed the BASIC
fixture's linkage/timing context. Its aggregate costs were not a clean matched
comparison. The retained version keeps every symbol fixed and matches all
six complete state sequences. The unpadded trial is not retained.

The alternate presentation-index keyboard schedule still shows approximately
0.24% larger mean interval against the cartridge after different trajectories.
Its first divergence follows an earlier candidate publication, as established
in the preceding report. That aggregate is retained, not treated as a matched
speed regression or erased by this small optimization. Broad course/hardware
acceptance and every sound/lifecycle combination remain open.

## Exact current evidence and reproduction

Current DAT:509773 bytes, SHA256
`f9251378356627f321524aef423cec272d24240de4fc49b0801556e712296414`.
Bridge:11756 bytes, SHA256
`40fc063fa685ec34538f064895015bbfa5c33b741d0444bdb5b17f80462e76d5`.
Disk file sizes are not a512KiB cartridge claim. Runtime still uses32 segments.

The [compact report](measurements/cartridge/issue42-512-audio-sync.json),
[source ledger](measurements/timing/mapper512-audio-sync.json) and separately
sealed [workbook](measurements/timing/mapper512-audio-sync.xlsx) retain exact
program/source identities, workload, costs, tails, synchronization, budget
assumptions and scope. Earlier workbooks keep their original hashes and meaning.
Function costs are inclusive; self cost is unmeasured. Never add child phase
cost to parent work. The5000-cycle usable-VBlank reserve remains an assumption.

```sh
.venv/bin/python -B scripts/mapper512_game.py
.venv/bin/python -B scripts/mapper512_sync_baseline.py
.venv/bin/python -B scripts/mapper512_tick_verify.py --bundle references/build/game-mapper512-sync-baseline --runtime references/build/game-mapper512-sync-baseline-runtime --mode dos --ticks 4096 --players 2 --audio-sync
.venv/bin/python -B scripts/mapper512_tick_verify.py --mode rom --ticks 4096 --players 2 --audio-sync
.venv/bin/python -B scripts/mapper512_tick_verify.py --mode dos --ticks 4096 --players 2 --audio-sync
.venv/bin/python -B scripts/mapper512_tick_verify.py --mode basic --ticks 4096 --players 2 --audio-sync
.venv/bin/python -B scripts/mapper512_tick_verify.py --mode rom --ticks 4096 --f10 --audio-sync
.venv/bin/python -B scripts/mapper512_tick_verify.py --mode basic --ticks 4096 --f10 --audio-sync
.venv/bin/python -B scripts/mapper512_game_verify.py --mode dos --round 5 --frames 360 --seed 4660
.venv/bin/python -B scripts/mapper512_game_verify.py --bundle references/build/game-mapper512-sync-baseline --runtime references/build/game-mapper512-sync-baseline-runtime --mode dos --round 5 --frames 360 --seed 4660
# Repeat both route commands for DOS/BASIC and rounds5/10/13; run16->17 F10 wrap.
.venv/bin/python -B scripts/mapper512_audio_verify.py --mode dos
.venv/bin/python -B scripts/mapper512_audio_verify.py --mode basic
.venv/bin/python -B src/toolchain/screen4/session_audio_verify.py --bundle references/build/game-compact-runtime
make test > references/build/issue42-audiosync-final-tests.log 2>&1
make verify-module-layout > references/build/issue42-audiosync-final-module.log 2>&1
.venv/bin/python -B scripts/mapper512_audio_sync_report.py
make timing-workbook TURBO=1 TIMING_LEDGER=docs/measurements/timing/mapper512-audio-sync.json TIMING_WORKBOOK_GENERATOR=scripts/mapper512_audio_sync_workbook.mjs
```

The aggregator also reads the baseline phase case and a cartridge PCM control
(`session_audio_verify.py --bundle references/build/game-compact-runtime`),
plus preservation results. Regenerate those observations before
aggregating a clean experiment; compact evidence replaces raw traces/PCM after
consolidation. No contributor payloads are committed.

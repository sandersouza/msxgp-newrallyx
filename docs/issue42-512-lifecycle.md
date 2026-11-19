# Issue42:512KiB lifecycle correction and test ROM

The owner's subsequent hardware clarification adds a mandatory
[fixed64KiB RAM, no-RAM-mapper gate](hardware-targets.md). The preserved64KiB
cartridge/MegaRAM checks below used a64KiB mapper. New fixed-RAM tests fail;
those earlier successes must not be relabeled as mapperless compatibility.
This blocks release/fallback-stable promotion while the hardware binding is corrected.

The experimental512KiB RAM backend now passes23 scoped lifecycle cases after
real DOS1, Disk BASIC and separate diagnostic-cartridge boots. Two graphical/
cold-lifetime defects were found and corrected. The normal744KiB ASCII8 ROM
for64KiB machines, MegaRAM edition and legacy mapper executables stay sealed.
No commit, push, merge or release was performed. This is not stable promotion
or unconditional performance, hardware or listening acceptance.

## Test artifact and controls

The latest RAM backend can be tested as an actual ROM file:

- `dist/experimental/mapper512/newrallyx-512-test.rom`
- ASCII8,524,288 bytes; **requires512KiB main RAM mapper and128KiB VRAM**.
- Reference emulator: Panasonic FS-A1WSX, MSX2+/V9958, Z80 at3,579,545Hz,
  real sprite limits. Select ASCII8 explicitly if auto-detection is uncertain.
- SHA256: `1afe41cd7363c918f5e62058a5d8d678298ec11b237c9bf26f4c0efda427978f`.
- Hold host F10 (MSX Shift+F5) through the ROM/RAM opening until the title,
  then release. Car/stone deaths are suppressed; walls stay solid. Reset clears
  invulnerability. Use5 for credit,1/2 for player selection, arrows and Space.

This is a **diagnostic carrier for the512KiB RAM backend**, not a512KiB ROM
qualified for64KiB main RAM. `dist/newrallyx.rom` remains the independent64KiB
cartridge target. The carrier packages the current RAM game and assets, but
replaces stopped filesystem reads with embedded-ROM transport. The DOS1/BASIC
tests separately execute real filesystem boots **without a cartridge**. Carrier
success does not establish disk I/O or general flashcart/expanded-slot support.

The512KiB disk candidate consists of `NRX512.COM/BIN/BAS/DAT` in
`references/build/game-mapper512-game/files/`. DAT is509,789 bytes, SHA256
`01e5307f0cbda0626df611289820c1ae9a3e6a5725f74cdd6029bdbec67333ef`.
Bridge is11,792 bytes, SHA256
`14b6440233d6c4aebc31d8675bd169ec99d34552a0e92ac03002ed1b7a47c385`.
Disk size is not the peak-RAM proof: the existing32 physical16KiB segments,
scattered OS/world shadows and stopped cache reuse remain the memory contract.

## Defects and fixes

### Fourth object template

`mapper512_game.py` extracted only27 object IDs per theme: three3x3 drawings.
Native flag kind4 selects a fourth drawing. It therefore read the next theme's
first nine IDs, or padding for the final theme, corrupting the special flag.
Longer lifecycle snapshots exposed six incorrect world IDs around that flag;
the independent scenery oracle rejected both initial/restarted games and a new
round. Previous short routes did not cover this visible area.

The cold table now retains all36 IDs per theme,144 bytes total, with bases
BD80/BDA4/BDC8/BDEC. It ends at BE10, below the existing BE40 live helper.
The36 additional constant bytes fit the already-reserved bridge region; no
new mapper segment, active copy or drawing instruction is added. Synthetic
tests distinguish all four kinds in all four themes and reject short sources.

### Challenge resume after cold terrain upload

The512KiB integration had lifted terrain uploads out of Video into BuildMap
so terrain and linked UI could share physical10. A challenge interstitial then
overwrote VRAM and resumed through Video without restoring terrain. The
independent pattern oracle rejected the first resumed gameplay snapshots.

`Mapper512_ResumeVideo` now occupies13 bytes of resident tail padding. It
clears readiness and `GameAuto_FlagsValid`, calls the stopped BuildMap and
tail-enters Video. This restores the unchanged terrain and same map/objects,
then rebuilds both flag caches. Clearing cache validity is essential: filesystem
I/O borrows physical4/5, and reusing their stale valid flag could execute OS
bytes as a flag packet. A terrain-only reload prototype without that invalidation
was rejected after the first resumed presentation.

No native round initializer runs on resume; flag placement is not rerolled.
The extra CALL consumes two cold stack bytes. No existing symbol address moves:
all1,817 previous names/values agree with the reproduced control. Decoded
resources differ only in13 resident bytes formerly FF padding and five cold
bootstrap bytes: three theme-base constants and the resume call operand.
All original active instructions, packet/source/native/audio resources remain
identical. The normal cartridge build is unaffected.

The observer's filesystem guard was also corrected: borrowed OS Page3 Cxxx
bytes cannot be interpreted as native game state. The guard now checks the
Cold_Read boundary while real main/game owners are still mapped. Reset rearms
startup observation instead of treating old state bytes as a running game.

## Validation and limits

The23-case matrix covers:

- DOS1 and Disk BASIC completion from rounds2,3,4,7,8,11,12,15,16, including
  every scenery family, four challenge interstitials and16→17 wrap.
- Natural one-player game over in DOS1, BASIC and the diagnostic ROM: three
  ordinary contact deaths, original lives, complete game-over cue, return to
  title, new credit/start and180 subsequent gameplay presentations.
- Machine reset after completion in all three formats, a fresh opening/title/
  game and180 presentations with F10 confirmed off.
- Diagnostic ROM completion through3→4 challenge as well as2→3. A separate
 360-presentation ROM run advances through all four families to13, then13→14.

Completion uses **ten controlled two-byte flag-cell contact probes** at the
real Flag_Update entry. It does not inject code, score, lives, clock, stage-
complete state or directly call a fake transition. Scoring, lucky fuel reward,
fanfares, settlement, fuel-to-score conversion, challenge and next-stage loading
execute through the normal game. This is a completion-boundary fixture, **not
a full keyboard-controlled course**. Game-over tests use keyboard-only natural
deaths, with the same explicit two-byte RNG seed as the other observers.

All506 stable snapshots pass the independent dynamic scenery, stone/navigation,
HUD/radar, complete-car pattern/color and SAT contract. Each initial opening
matches71 captured states and their original publication cadence. Strict VDP
timing callbacks remain enabled. Each final hot image matches its occupied-byte
mask. Actual music mode4 and nonzero PSG output are observed during settlement;
fuel/score stay unchanged until the music request clears. Observed settlement
is approximately1.77–1.80 seconds; remaining fuel reaches zero before loading
the next stage and is restored to15360 for that stage. Game-over cue finishes
before the return to title, about8.28 seconds in the reference route.

Both real disk boots also pass the existing857-sample full-PSG and recorded-PCM
sound-only fixture after the fixes. That fixture installs its documented sound
event stubs and is distinct from natural lifecycle/listening acceptance.

Fresh supported-format regression observers pass for the64KiB default ROM,
768KiB MegaRAM DOS/BASIC and legacy4MiB-main-mapper DOS/BASIC executables.
The cartridge and both ZIP hashes are unchanged.510 general tests and94
component tests pass (one component skipped). `make verify-module-layout`
retains the default ROM/symbol/layout gate. The historical pre-nine-cycle
package still reproduces its original hashes; a separate control reproduces
the immediately previous package with the nine-cycle optimization retained.

## Scoped performance evidence

Six fresh360-presentation routes retain HUD/audio and3/5/6 native enemies,
NTSC59.922743Hz refresh, base Z80 and actual sprite limits. Active work runs
from main-loop entry to wait_blank; cold/death/settlement intervals are excluded.

|Boot / round|Active frames|Mean work cycles|P95|Maximum|Presented FPS|
|---|---:|---:|---:|---:|---:|
|DOS5|173|93477.813|144447.667|185292.667|26.9314|
|DOS10|153|104444.449|159663.667|195424.667|25.6128|
|DOS13|163|113047.861|171364.667|244151.667|24.6087|
|BASIC5|173|93456.565|145653.667|185108.667|26.9314|
|BASIC10|153|104500.429|160070.000|195403.667|25.6128|
|BASIC13|163|113044.836|171381.667|244130.667|24.6087|

These are route aggregates, not matched-trajectory speedups. Compared with the
previous exact-artifact aggregate, DOS5 is unchanged. Three raw means increase
by6.429/7.867/10.141 cycles, while BASIC10 P95 increases393.333 cycles. Other
means/tails improve or stay unchanged. The ledger preserves all deltas and
their limitations; the earlier0.24% divergent-route concern is **not closed**.
The preserved hot instruction/resource bytes support that these fixes add no
recurring gameplay work, but do not establish unconditional pacing acceptance.

Cold transitions are deliberately allowed to take longer. Native next-round
entry through next playable frame takes roughly10.5 seconds within a family,
27.5–28.7 seconds including challenge/reconstruction and42.3–43.1 seconds when
replacing family resources in this directory-backed DOS fixture. These are
emulated cold durations, not physical-drive measurements.

The [ledger](measurements/timing/mapper512-lifecycle.json) and
[workbook](measurements/timing/mapper512-lifecycle.xlsx) separate inclusive
work, sound/IRQ overlap, calls per presentation, publication tail/waits and
remaining119472-cycle two-refresh budget. Usable VBlank remains unmeasured;
5000 cycles is only a planning reserve. The canonical cartridge workbook and
earlier experimental workbooks retain their own hashes and scopes.

## Source owners and reproduction

`mapper512_game.py` owns templates and the generated cold helper;
`mapper512_lifecycle_verify.py` owns the explicit fixtures and real lifecycle
observer. `mapper512_testrom.py`, `mapper512-testrom.asm` and
`mapper512-rom-bdos.inc` own only the diagnostic boot/provider. The carrier
bootstrap derives the active RAM slot before BIOS RAMAD initialization, checks
32 independent segments with reversible tags and installs the bounded bridge.
Its ROM-copy thunk lives only in the existing OS snapshot, at OS5:C500; game
C500 retains its normal flag-state lifetime. Register/IFF/mapping contracts are
inline and synchronized in `src/screen4/modules/contracts.json`.

With contributor inputs and the normal compact build already prepared:

```sh
.venv/bin/python -B scripts/mapper512_game.py
.venv/bin/python -B scripts/mapper512_testrom.py
.venv/bin/python -B scripts/mapper512_lifecycle_verify.py --matrix
.venv/bin/python -B scripts/mapper512_game_verify.py --mode rom512 --round 13 --frames 360 --f10 --transitions
.venv/bin/python -B scripts/mapper512_audio_verify.py --mode dos
.venv/bin/python -B scripts/mapper512_audio_verify.py --mode basic
.venv/bin/python -B scripts/mapper512_sync_baseline.py --keep-phase-target
```

For the six timing routes run `mapper512_game_verify.py --mode dos|basic
--round 5|10|13 --frames 360 --seed 4660 --profile-audio`, using one actual mode
and round per invocation. Repeat the five supported-format regression commands
below, then consolidate before cleaning:

```sh
.venv/bin/python -B scripts/compact_game_verify.py --mode rom --ram-kib 64
.venv/bin/python -B scripts/compact_game_verify.py --mode dos --size 768
.venv/bin/python -B scripts/compact_game_verify.py --mode basic --size 768
.venv/bin/python -B scripts/verify_disk.py --mode dos --ram-kib 4096
.venv/bin/python -B scripts/verify_disk.py --mode basic --ram-kib 4096
.venv/bin/python -B scripts/mapper512_lifecycle_report.py
make timing-workbook TURBO=1 TIMING_LEDGER=docs/measurements/timing/mapper512-lifecycle.json TIMING_WORKBOOK_GENERATOR=scripts/mapper512_lifecycle_workbook.mjs
```

The [compact result](measurements/cartridge/issue42-512-lifecycle.json) retains
artifact/observer hashes, lifecycle events,506 graphics checks, complete cost
distributions, supported-format results and limits. Raw builds, dumps, PCM,
logs and traces are disposable and removed after consolidation. DOS2/Nextor,
PAL50, physical hardware, subjective sound and complete natural-course
acceptance remain open. No release authorization is implied.

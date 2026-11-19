# Issue42: native512KiB disk boot and game transitions

The [validation continuation](issue42-512-validation.md) adds differential
natural player turns, F10 contacts and PSG/PCM fixtures, and isolates the first
causal divergence of the0.24% route. Runtime/package bytes remain identical.

The experimental DOS1 and Disk BASIC files now boot the actual game and execute
real stage transitions on an openMSX machine with **exactly512KiB mapper RAM,
without a cartridge**. This connects the previously separate native-game and
filesystem proofs. The supported744KiB ROM,768KiB MegaRAM package and legacy
mapper executable remain byte-identical. **No release, merge, push or commit.**

This is a functional integration milestone, not stable512KiB qualification.
The strict no-regression gate remains open: a presentation-clock route has a
0.24% larger mean interval after trajectories diverge, and isolated matched-state
work samples can be slower. Native-clock route means are equivalent or better;
that does not establish universal speed, audio or gameplay acceptance.

## Mechanism and source ownership

`scripts/mapper512_game.py` specializes the generated RAM runtime through
`mapper512_integrate.py`, packages resources and emits DOS/BASIC files.
`src/disk/mapper512-game-bridge.inc` binds the real loader to boot and cold game
callbacks. The shared bounded decoder, OS snapshot and world shadow remain in
`mapper512-cold.asm`. The default cold diagnostic still assembles to its exact
previous bytes. No default game source or published artifact is replaced.

All32 physical segments remain accounted for by the
[earlier memory layout](issue42-512-cold-io.md).32KiB OS and16KiB world shadow
persist in common declared holes. Packet banks20..29 never hold scattered OS
or shadow bytes. During opening, those cold packet owners temporarily become:

| Bank | Boot-only contents |
| --- | --- |
|20|Relinked boot workers, descriptors and atlas worker; original terrain prefix|
|21..23|Losslessly relocated tile dictionary and all71 frame streams|
|24|Original native player seed|
|25|Relinked cold/main workers and radar initializer|
|26|Original navigation tables|

The atlas uses exact original compressed records and dimensions. It copies the
current command stream, at most1730 bytes, to main0800 before changing its
dictionary bank. That scratch is game smoke-list storage only after boot; it
does not add active copies or a segment. Family asset installation restores
packet20..26 before the first playable frame.

The first integration failure exposed a relocation error: the linker emits
startup workers at file offset0 with logical address2900, while boot consumes
them from source9000. Packaging must shift the linked payload by4096 bytes,
including descriptors and atlas worker, while keeping the terrain prefix.
Synthetic relocation tests and independent opening pixels now cover that
ordering. Copying the linked file directly as a raw owner is rejected.

Before native4010, the bridge restores an actual BIOS Page3 image and BIOS
IM1/I. Native boot installs the relocated IM2 runtime before enabling IRQ.
The Page3D1E0/D1E9 gate selects bridge30 only during DI stopped calls and
restores resident6 before returning; all primary/alternate registers survive.
The gate has no active-frame caller or added hot-path dispatch.

The seed callback restoresE002..EFFF and retains the ongoing RNG. The assets
callback loads a new family when required, navigation to main3000 and terrain
to10. Existing eight terrain pattern/color uploads happen **before** final
world I/O. The world callback restores UI10, then map3 through the shadow,
then map2 last. EndBatch releases4/5 for normal flag-cache construction.
Object templates are fixed108 bytes at bridge7D80; original collision
permissions remain in ring31. This prevents terrain reads from evicting UI
code needed immediately after the first rendered game screen.

The filesystem temporarily owns BIOS IM1/I/R1=22. Callbacks save all14 PSG
registers and restore only changed values, including avoiding gratuitous
envelope retriggers; BIOS keyclick is suppressed in the borrowed OS context.
The native Video lifecycle owns final IM2 display/cache restoration. F10C0EE
survives every read and transition. Error exits remain stopped and require
reset; resuming invalid world/cache state is prohibited.

The observed family-change presentation interval is approximately42..43
emulated seconds in these directory-backed disk runs, including I/O, map/cache
rebuild and first publication. This is stopped preparation, not active gameplay;
the owner permits longer stage changes. It remains a practical optimization
opportunity and is not a physical-drive timing guarantee.

Detailed register/IFF/mapping/scratch contracts are synchronized in
[contracts.json](../src/screen4/modules/contracts.json).

## Evidence and limits

The [compact evidence](measurements/cartridge/issue42-512-native-game.json)
and [separate timing workbook](measurements/timing/mapper512-native-game.xlsx)
pin the exact bridge, resource file and four hot images. Current resource data
is509,771 bytes; bridge11,756 bytes including padding/object constants.
Those are disk-file sizes, not claims of a512KiB cartridge image. Runtime
mapper capacity is512KiB. The cartridge compatibility target remains64KiB.

- DOS/BASIC actual boot: all71 published opening states match contributor
  arcade captures plus the existing512KiB hardware-status overlay. Relative
  publication ticks are unchanged. PSG output volumes remain silent throughout
  opening. Both start playable games; BASIC holds F10 across boot to title.
- Real F5 transitions4→5,8→9,12→13 and16→17 exercise all four family
  boundaries including wrap. Pixel/HUD/car/navigation checks pass, F10 remains
  latched and cold epochs are excluded from active timing.
- Short native-clock routes at rounds5/10/13 cover three/five/six enemies;
  DOS/BASIC provide independent starts. Timing uses a diagnostic two-byte RNG
  seed for comparison; normal boot proofs have no debugger writes or payload
  injection. No code, OS context or game payload is injected in either class.
- 505 general and94 component tests pass (one existing skip), plus the
  zero-delta module-layout gate. Fresh64KiB cartridge,768KiB MegaRAM DOS/BASIC
  and legacy4MiB mapper DOS/BASIC checks pass.

The mean work costs on native-clock DOS routes decrease by approximately
0.70%,0.26% and1.21%. Mean presentation intervals are equivalent for rounds5
and10; round13 improves by about0.61%. Presentation remains workload-dependent,
roughly24.6..27.0 FPS here, separately from59.92Hz refresh. This is not a new
claim of30FPS throughout full-density play.

The alternate presentation-clock round5 schedule first diverges when the RAM
candidate publishes **earlier** at frame51. Its later route ends with a0.24%
larger mean interval, despite slightly lower mean work and lower tail/maximum
work. The later trajectories/cache histories are different. Same camera,
native actor bytes, ticks and PSG do not fully clone renderer/cache/IRQ phase;
isolated work deltas of both signs remain in the ledger. Do not hide these
cases or call the strict all-workload performance gate passed.

Game audio traces and silent opening are emulator observations, not listening
acceptance. Full natural flag completion, player switches, death/game-over,
reset/error recovery, PAL, DOS2/Nextor and physical hardware remain unqualified
for this new loader. The reference is a clean FS-A1WSX expanded-slot machine;
do not generalize its slot assumptions to every mapper. Directory-backed disk
timing is emulated. Longer stopped preparation is allowed by the owner, but
no active slowdown is approved.

## Reproduction

Contributor BIOS/OS/arcade inputs and canonical assets are required. Generated
game payloads stay ignored and must never be committed.

```sh
.venv/bin/python -B scripts/mapper512_game.py
.venv/bin/python -B scripts/mapper512_game_verify.py --mode dos --round 2
.venv/bin/python -B scripts/mapper512_game_verify.py --mode basic --round 2 --f10
.venv/bin/python -B scripts/mapper512_game_verify.py --mode dos --round 4 --frames 240 --f10 --transitions
# Repeat family boundaries8/12/16, both OS paths and rounds5/10/13.
.venv/bin/python -B scripts/mapper512_game_verify.py --mode dos --round 5 --frames 360 --seed 4660
.venv/bin/python -B scripts/mapper512_game_verify.py --mode dos --round 5 --frames 360 --seed 4660 --input-clock presentation
make test
make verify-module-layout
.venv/bin/python -B scripts/mapper512_game_report.py
make timing-workbook TURBO=1 TIMING_LEDGER=docs/measurements/timing/mapper512-native-game.json TIMING_WORKBOOK_GENERATOR=scripts/mapper512_game_workbook.mjs
```

The report also requires matching control runs from
`mapper512_integrated_verify.py --control`, the unchanged-format checks and
the regenerated default cold diagnostic. Retain compact results/hashes only;
discard raw sessions after consolidation. Next work is the remaining strict
performance/audio/lifecycle qualification before any promotion decision.

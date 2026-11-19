# Issue42:512KiB performance, audio and gameplay continuation

The [subsequent sound-clock validation](issue42-512-audio-sync.md) resolves the
observed natural-audio comparison boundary and records a measured nine-cycle
phase-selector reduction. This report retains the preceding package's scope.

The test ROM is still `dist/newrallyx.rom`:744KiB ASCII8, minimum64KiB main
RAM, SHA256 `44be6037d05ebf763283f14ef6deb6e4a8bd58b0a25fcc04c693d899c3704f00`.
It is the cartridge edition. The cartridge-free512KiB target is the separate
DOS1/Disk BASIC executable. Neither is newly released. The ROM, both supported
disk ZIPs and all four experimental512KiB executable files retain their bytes.

## The0.24% route

Reproducing the360-presentation round5 schedule gives the same0.24233% larger
active mean interval. This is not an isolated measurement of slower renderer
code: keyboard directions change by **presentation index** in this schedule.

Camera, native actor state and elapsed ticks match through frame51. At that
frame the candidate's work is113,483 cycles versus116,166.33 for the cartridge.
The candidate publishes in119,474 cycles, while the cartridge uses179,207.33:
approximately **one refresh earlier**. Frame52 then consumes two elapsed ticks
versus three and its camera/native state diverges. The51-frame prefix mean
work is95,703.58 versus96,578.56 cycles. Across360 presentations the elapsed
refresh totals are590 versus589; final cameras are(227,1059) versus(223,1059).
Later aggregates describe different routes and cache/event histories.

This identifies the causal boundary rather than explaining the result as a
uniform0.24% slowdown. It does **not** erase the aggregate result or establish
an unconditional no-regression verdict. Prior native-clock multi-population
results, isolated longer matched-state costs and all tail/maximum limits remain
in the [current experimental ledger](measurements/timing/mapper512-native-game.json).

A generic bank-helper shortcut also passed128,000 real-Z80 synthetic ABI cases:
all125 logical IDs ×256 AF flag combinations ×two IFF states ×two versions.
Registers, stack return, mapper selection and flags survive a cross-page
lookup; helper entry-through-RET falls136→116 elapsed reference cycles.
However, the full360-presentation route has identical active mean/P95/max work
and mean cadence. One nonactive interval saves40 cycles, with publication
phase differences within5 cycles. The generated active paths already use
direct mapping. **The shortcut was reverted completely**; no gameplay benefit
justifies retaining another runtime variant. Its authored synthetic probe is
`scripts/mapper512_mapper_verify.py`, not production code.

## Audio and natural lifecycle checks

The [compact results](measurements/cartridge/issue42-512-validation.json) pin
the exact resources, bridge, sources and observers. The separately scoped
[workbook](measurements/timing/mapper512-native-game.xlsx) includes these results.

| Check | Observed result |
| --- | --- |
|DOS1 and Disk BASIC sound fixtures|Each matches all857 samples of14 PSG registers against cartridge; recorded PCM engine, smoke, crash/retrigger, envelope and music assertions pass|
|DOS1 two-player natural run|All4,096 original768-byte native states and host game/death/round samples match cartridge; three natural deaths and player turns|
|Disk BASIC two-player natural run|Same4,096-state match, three deaths and turns; cold owners restore players0→1→0→1 with load kinds0/1/2/2|
|Disk BASIC real boot-held F10|All4,096 native states match the corresponding cartridge F10 run;24 hazardous contacts, zero deaths/turns; original wall-limited motion retained|
|General/component checks|505 +94 pass; one existing component skip|

The natural fixture uses held-up keyboard input and sets only the original
two-byte PRNG seed at first native initialization. It never overrides game
clocks or injects executable/OS/game payloads. Original state includes position,
motion, RNG, board/round, score and lives fields. Independent final maze, HUD,
navigation and complete-car checks also pass. This is a reproducible fixed-input
life/turn scenario, not every possible route or complete manual course.

The sound fixture is deliberately separate: it starts the real game through
the filesystem, then uses the existing synthetic velocity/event stubs and
physical-time schedule. It records emulator PCM and checks the actual output;
it is not natural-play or listening acceptance. The read-only code-prefix
guard prevents numeric BIOS/worker-PC aliases from arming it prematurely.

Natural PSG samples taken at native tick boundaries are **not all equal**:
3,847/4,096 match in the DOS two-player run,3,250/4,096 in BASIC, and
4,024/4,096 in the F10 run.
The original native state remains equal throughout. Audio follows physical
ticks and is processed at presentation/catch-up boundaries, so a native-index
snapshot is not a fully synchronized audio observation. These differences
remain in the evidence; natural event timing/listening still needs qualification.

F10 test setup must release the boot key and wait for the existing key gate
before inserting credit. A two-player start needs two credits. Fixture failures
with only one credit or an unreleased gate reproduced in the cartridge control
and were corrected in the driver. Disk BASIC key-buffer commands require Tcl
quoted carriage-return escapes. None of these fixes changes the game.

The strict all-workload speed/audio gate, varied routes/natural flag clears,
game-over/new-game/reset/error recovery, PAL/DOS2/Nextor and physical hardware
remain open. No accepted runtime change, commit, push, merge or release.

## Reproduction

Use the existing contributor ROM/BIOS/OS inputs and the project virtualenv:

```sh
.venv/bin/python -B scripts/mapper512_game.py
.venv/bin/python -B scripts/mapper512_audio_verify.py --mode dos
.venv/bin/python -B scripts/mapper512_audio_verify.py --mode basic
.venv/bin/python -B src/toolchain/screen4/session_audio_verify.py --bundle references/build/game-compact-runtime
.venv/bin/python -B scripts/mapper512_tick_verify.py --mode rom --ticks 4096 --players 2
.venv/bin/python -B scripts/mapper512_tick_verify.py --mode dos --ticks 4096 --players 2
.venv/bin/python -B scripts/mapper512_tick_verify.py --mode basic --ticks 4096 --players 2
.venv/bin/python -B scripts/mapper512_tick_verify.py --mode rom --ticks 4096 --f10
.venv/bin/python -B scripts/mapper512_tick_verify.py --mode basic --ticks 4096 --f10
.venv/bin/python -B scripts/mapper512_mapper_verify.py
make test
make verify-module-layout
```

Route commands are in the preceding native-loader report. The report aggregator
also expects the retained before/control scratch records and the discarded
shortcut experiment; rebuilding that historical experiment requires its
standalone probe source. Compact counts, hashes and workbooks are retained;
raw traces, PCM and disposable runtime bundles are removed after consolidation.

To recreate the rejected full-game case, temporarily use `fast_mapper_source`
from the standalone probe in `mapper512_game.adapt` for the generated
`Compact_Map16` through `Compact_MapPair` block before assembly. Build and run
the same360-presentation route, then remove that replacement and require the
four executable file seals and all four hot-image seals to match the baseline.
The substitution has no default build flag and is not a supported variant.

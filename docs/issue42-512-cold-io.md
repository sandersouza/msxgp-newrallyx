# Issue42:512KiB cold filesystem and memory lifetimes

Subsequent work connects this historical cold-only proof to
[native boot and real game transitions](issue42-512-native-game.md). The
qualification limits and artifact hashes of each experiment remain separate.

The next memory peak is now demonstrated on a real **512KiB openMSX mapper**:
DOS1 and Disk BASIC load all four production hot layouts and both world-map
halves from disk, including3→0 wrap, **without a cartridge or debugger payload
injection**.32KiB of OS state and a separate16KiB world shadow fit in declared
holes without adding a physical segment. This is a cold-I/O diagnostic, **not a
standalone game**. Native boot/opening/F10 and actual game callback integration
remain required; no release, commit, push or merge is performed.

Owner requirements remain strict: no active-speed/graphics/audio/gameplay
regression,64KiB cartridge compatibility, ROM/executable/MegaRAM and F10.
Extra preparation between stages is allowed. The supported744KiB ROM and both
executable packages remain byte-identical. Their canonical timing workbook
is unchanged; new evidence has a separately scoped
[ledger/workbook](measurements/timing/mapper512-cold-io.xlsx).

## Source owners and mechanism

`scripts/mapper512_integrate.py` now emits a declared occupancy mask for every
family, pinned to its exact program image. **All four active program images
remain identical** to the [preceding integration](issue42-512-integration.md).
`scripts/mapper512_cold.py` intersects the masks and allocates cold lifetimes;
`src/disk/mapper512-cold.asm` owns filesystem/decode/copy/OS transitions;
`mapper512-cold-loader.asm` installs it from DOS/BASIC. Tests and compact report
are owned by `scripts/mapper512_cold_verify.py`,
`scripts/mapper512_cold_report.py` and the synthetic tests. API/IRQ/mapping
contracts are synchronized in
[contracts.json](../src/screen4/modules/contracts.json).

There are63,937 common unowned bytes across all families. They are determined
from explicit source/code/ring fields, **never from searching forFF pixels**.
Working segments0..5 and opaque resident/native/audio/decor/UI segments6..10
are conservatively fully owned. Live source/code bytes, includingFF values,
cannot be reused. Mask hashes and all allocations are in the
[compact report](measurements/cartridge/issue42-512-cold-io.json).

| Lifetime | Physical ownership |
| --- | --- |
|OS Page0/Page3 snapshots,32KiB|Scattered common holes; persists during gameplay|
|Second world-half shadow,16KiB|Separate common holes, disjoint from OS/code|
|Cold bridge/directory|Bank30 offset1000..3E3F reserved;6,863 emitted bytes|
|Initial private stack|Bank30 CPU7D00; code must end below7C00|
|Compressed disk input|Borrow world segment2 while stopped|
|Decoded output|Borrow world segment3 while stopped|
|Live OS Page0/Page3|Borrow both flag-cache segments4/5 while stopped|
|Main/game state|Segments1/0 retained; no new segment or active-frame copy|

Banks20..29 are excluded from scattered storage, retaining a potential cold
bootstrap reuse option. That option is not a qualified boot atlas allocation.
The11840-byte bridge reservation also covers its initial stack and future
linking margin; the unused reservation is not counted as free elsewhere.

The first resource read restores OS state into4/5. Within a stopped batch the
OS and open file remain available there. Inputs use segment2 and decode fully
into3. Only after bounded decoding and a full16KiB checksum does the bridge
copy **the union of live fields** to its target. This preserves scattered OS,
world-shadow and bridge bytes even when replacing bank30 or another family.

Reading world3 scatters its full16KiB to the separate shadow before another
read overwrites scratch2/3. World2 must be the last read. `Cold_EndBatch`
closes the file, persists OS changes, restores world3 and releases4/5. The
original map bytes in **both halves** match after every family completion.
Flag caches still need reconstruction before gameplay. No resource is decoded
or fetched during active gameplay by this proof.

The ROM/RAM opening needs its own bootstrap lifetime: active packet-code
storage and boot-only resources need not coexist, but no unallocated boot
resource, OS context, initial cache or error recovery peak may be assumed.

## Real filesystem checks and corrections

The guest loads its installer and resources through the real disk-ROM/BDOS
filesystem path. The host supplies only local BIOS/OS files, contributor-derived
resources and observations. It does not inject OS snapshots, executable code
or game payloads through debugger writes. Directory-backed floppy timing is
emulated; this is not a physical-drive measurement.

The small397-byte installer alone relocates toC100. Keeping its complete bridge
there would overwrite the DOS1 kernel beginningD606. Bridge bytes remain in
TPA until copied into RAM Page1: DOS source below4000, BASIC source in original
Page2. Reversible mapper probes restore their touched tags; insufficient64 or
256KiB RAM is rejected before bridge installation. DOS2 is explicitly rejected
rather than borrowing allocator-owned segments without qualification.

Disk BASIC initially failed to open a file whose FCB was beside the bridge:
its disk ROM temporarily replaces Page1. The FCB now lives in borrowed OS
Page3C200..C224, headerC100..C107 and stackCF00, all below kernelD606. DOS uses
0005; BASIC usesF37D. Actual disk calls use OS IM1/I, then return DI with the
saved game I/SP, main1 and game0 restored. The cold fixture checks these
invariants after every read/finalization.

The final matrix has **16 filesystem cases**:

- DOS/BASIC candidate plus per-resource control:120 reads each, five batch
  finalizations,5,000 live-span checks and20 complete world-half comparisons.
- DOS/BASIC each reject missing, truncated and checksum-corrupt files without
  changing already installed hot fields. A later truncation after28 successful
  reads additionally checks error cleanup after a completed first family.
- DOS/BASIC reject64/256KiB and restore every probe tag.

Game main/Page3 state in these filesystem runs is **synthetic**. A C0EE marker
checks its lifetime but does not test actual F10 activation or invulnerability.
There is no native-game boot, gameplay or graphics/audio acceptance implied by
successful filesystem reads. Error returns leave world/flag workspaces invalid;
a real caller must recover or reset, never resume gameplay immediately.

## Measured cold optimization

The control restores/saves OS and opens/closes the file for each resource.
The candidate groups those operations per family. Both read the **same120
payloads**, reconstruct the same maps and pass the same output/state checks.
File open/close counts fall120→5; block-read calls fall240→125.

| Mode | Control total | Candidate total | Reduction |
| --- | --- | --- | --- |
|DOS1|1,058,952,975 reference cycles|655,131,581|38.13%|
|Disk BASIC|1,056,652,589|656,637,146|37.86%|

Totals include all Read intervals and the five **disjoint sibling** EndBatch
intervals. They exclude caller CALL/loop overhead; nested decode/BDOS costs
must not be added again. Work is elapsed guest time multiplied by3,579,545,
including BIOS/disk waits, not CPU instruction counts. Self costs and any
remaining gameplay/VBlank budget are unmeasured for these cold routines.

The five-family sequence still takes approximately183 seconds in this
conservative virtual-floppy experiment. Per-family costs, means/P95/max,
individual longer spans and the slightly longer deferred EndBatch/close are
retained in the ledger. This is **loading work**, not gameplay FPS or a final
user-facing loading-time promise. Physical storage, real boot work and owner
acceptance remain separate.

## Active gameplay with reserved storage occupied

To check that the declared holes really stay unused by rendering, a separate
full-game diagnostic fills **all48KiB reserved scatter locations with varied
non-padding bytes** and installs the actual bridge into its hole. The exact
augmented RAM-image hashes are recorded separately from the unchanged base
program-image hashes. This is deliberate host fixture injection, unlike the
filesystem runs; the two proofs must not be called one end-to-end run.

Three/five/six-enemy native-clock routes retain **465 matching state/PSG samples**
and their previous shorter work. HUD, original dynamic world, complete cars,
PSG snapshots, real IRQs, strict VDP timing and immutable-bank audits pass.
Four additional real boot-held-F10 runs cover4→5,8→9,12→13,16→17 with occupied
storage, preserving the latch and all four family boundaries. Native-game
state in these runs is real, but bootstrap and cold providers remain
cartridge/host-assisted. No new active instruction path is introduced.

This does not resolve the earlier0.24% slower presentation-clock route with
different trajectories, nor prove every route faster. Current canonical744KiB
timing stays authoritative. Waveform listening, broader natural lifecycle,
other CPUs/PAL and physical hardware are not newly accepted.

## Remaining integration

The next implementation must connect these services to the **actual boot and
stopped lifecycle**, preserving original opening/F10 behavior, map/flag order,
all assets and original rules. Game/BIOS VDP IRQ, PSG, input and clock handoff
need explicit ownership and end-to-end validation. Cold-only fixtures leave
BIOS video/IRQ service available; they do not prove the required handoff from
the game's SCREEN4 cold transition. General mapper/slot/DOS2 compatibility and
error recovery remain additional gates.

There is enough measured capacity to continue512KiB integration; these results
do not authorize promoting the diagnostic as a supported executable or
publishing a release. The supported744KiB/768KiB fallback remains intact.

## Reproduction and preserved editions

502 general tests/94 component tests pass (one component skipped), and the
historical module-layout proof passes. Fresh unchanged-edition startup/game
checks pass for64KiB cartridge,768KiB MegaRAM DOS/BASIC and legacy4MiB mapper
DOS/BASIC. Exact artifacts, source hashes, bridge/control hashes, occupied RAM
images and separate timing scopes are in the compact report.

With the contributor inputs and frozen F10-enabled compact build prepared:

```sh
.venv/bin/python -B scripts/mapper512_integrate.py
.venv/bin/python -B scripts/mapper512_cold.py
.venv/bin/python -B scripts/mapper512_cold.py --per-resource
.venv/bin/python -B scripts/mapper512_cold_verify.py --mode dos
.venv/bin/python -B scripts/mapper512_cold_verify.py --mode basic
# Repeat both modes with --per-resource for the matched control.
# In batch mode, repeat each --fault missing/truncated/checksum/late,
# and each --ram-kib 64 / --ram-kib 256 capacity case.
.venv/bin/python -B scripts/mapper512_integrated_verify.py --cold-storage --round 5 --frames 360 --input-clock native
.venv/bin/python -B scripts/mapper512_integrated_verify.py --control --round 5 --frames 360 --input-clock native
# Repeat for rounds10/13, then occupied F10 transitions for4/8/12/16:
.venv/bin/python -B scripts/mapper512_integrated_verify.py --cold-storage --round 4 --frames 240 --f10 --transitions
.venv/bin/python -B -m unittest discover -s tests -v > references/build/issue42-cold-tests.log 2>&1
.venv/bin/python -B -m unittest discover -s src/toolchain/screen4 -p 'test_*.py' -v > references/build/issue42-cold-components.log 2>&1
make verify-module-layout > references/build/issue42-cold-module.log 2>&1
# Refresh the five unchanged-edition checks listed in the preceding integration report.
.venv/bin/python -B scripts/mapper512_cold_report.py
make timing-workbook TIMING_LEDGER=docs/measurements/timing/mapper512-cold-io.json TIMING_WORKBOOK_GENERATOR=scripts/mapper512_cold_workbook.mjs
```

Raw payloads, bridge binaries, snapshots, emulator homes and logs stay ignored
and are removed after consolidation. Do not commit original-derived game or OS
bytes, or publish `NRXCOLD.*` as a game delivery.

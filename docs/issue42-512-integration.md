# Issue42: complete active-game integration in512KiB

Continuation: [real cold filesystem and memory lifetimes](issue42-512-cold-io.md)
proves DOS/BASIC I/O and48KiB scattered OS/world staging in the same mapper,
plus active gameplay with that storage occupied. Native boot and actual game
callback handoff remain pending; this report retains its earlier measurement scope.

The complete game's **active working set now runs in32 real16KiB main-mapper
segments**, with IRQs, original native logic, expanded flag caches, HUD, PSG and
complete cars. This is a measured integration milestone, **not a standalone
512KiB DOS/BASIC executable**. Initial bootstrap and stopped-stage resources
still come from the cartridge/host diagnostic provider. No release, merge,
commit or push is authorized or performed.

The owner permits longer preparation **between stages**, while retaining
gameplay speed, graphics, audio, rules,64KiB cartridge compatibility, both
delivery formats, MegaRAM and the F10 test mode. The public744KiB cartridge,
768KiB MegaRAM edition and legacy mapper executable remain byte-identical.

Source owners: `scripts/mapper512_integrate.py` builds the experimental relink;
`scripts/mapper512_integrated_verify.py` owns real-RAM takeover/observations;
`scripts/mapper512_integrated_report.py` seals the compact evidence. Original
inputs stay contributor-supplied and ignored. The
[preceding component report](issue42-stage-overlays.md) retains its earlier
hashes, costs and provisional accounting; its unqualified allocation totals
must not be relabeled as this implementation.

## Mechanism and memory ownership

Each family has a separately linked active layout. Only the current family's
eight edge records and65-byte victim-rank row per HUD phase are resident.
Absolute source operands are resolved before execution; eleven locally shared
packet-code windows retain complete executable suffix closures. No packet or
stage is decompressed during gameplay. External disk storage for other families
is possible, but its loader and scratch lifetimes remain unimplemented.

| Physical segments | Active owner |
| --- | --- |
|0|Page3 native state, stack, IRQ and dispatcher|
|1|Main Page0 helpers, metadata, navigation and active audio/decor/turbo workers|
|2–3|Expanded mutable world maps|
|4–5|Expanded on/off flag caches|
|6|Resident full-game code|
|7|Original native core|
|8|PSG worker|
|9|Decorations/labels/popups|
|10|UI/attract; cold raw resource slot only while stopped|
|11–18|64 packed HUD phase records|
|19|Current family's eight edge records|
|20–30|Eleven independently complete packet-code windows|
|31|Original ring worker and current terrain permissions|

All32 segments are owned. Segment31 is **not** cold scratch. Each diagnostic
`hot-image.bin` is524,288bytes, including six placeholder work segments that
must retain live state at takeover. These files are neither runnable ROMs nor
disk executables. Four alternative layouts do not imply2MiB simultaneously
resident or a new cartridge image. Exact image/runtime seals are in the
[integration ledger](measurements/cartridge/issue42-512-integrated.json).

The original35-byte IRQ moves to Page3D180..D1A2; the active path adds no IRQ
instructions or mapping. Nonactive key handling still requires residentPage1.
The Page3D1B0 dispatcher maps code in Page1 while source data remains in Page2,
then D1CA restores residentPage1. Nonempty packets emit the original14-byte VDP
header and returnEI; empty packets preserve entry IFF and emit no writes.
Runtime endsD1D1, beforeD200. Persistent HUD bank shadow isD10C. D110..D12F is
temporary takeover code; scoreD130/138, audioD150..157 and smokeD160..17F remain
separate. See the synchronized
[module contract](../src/screen4/modules/contracts.json).

Packed2KiB HUD records contain unchanged pixels, immediate names, guard code,
family rank and three-byte packet descriptors. Edge pixel/color arrays shift
by40bytes so both64-entry name arrays retain zero-aligned low bytes; this
avoids repeated per-row index adjustment. Declared occupancy masks reject
collisions even for liveFF bytes. Source-event comparison covers all4,384
production references, and executable-graph checks walk11,320 family entry
paths to their proper terminal. These static checks supplement real execution;
they do not mean every path ran inside a complete natural game.

Direct16KiB RAM mapping replaces paired8KiB cartridge writes. The existing
eight-slot cache policy is unrolled without changing visible-slot exclusion,
first exact match, first empty, strict-minimum ranking/tie behavior or capacity.
IX/IY saves are removed only because this implementation never touches them.
An independent oracle checks every executed selection and returned IX/IY/IFF.

## Integration corrections and rejected shortcuts

- Files named cold/startup include active workers. Overlaying Page01400..1FCF
  or2900..2F00 corrupts audio, decoration or turbo operation. They remain resident.
- Terrain permissions share the ring's declared free tail at9000..A5BF with
  the original32-byte row stride. No mainPage0 permission overlay is used.
- Prewarming now updates the HUD bank shadow for every phase. Otherwise a
  transition leaves phase63's bank installed for a later full HUD upload.
- Live smoke callbacksC7B0/C7B3 must be retargeted without resetting smoke.
  Their stale addresses caused mid-instruction calls after relinking.
- The sole active raw restart seed becomes eight resident bytes; HL=A02D is
  restored before original native reentry. Cold per-frame seed loading is rejected.
- An obsolete `hud_page` store has no reader in this presenter and destroyed
  the deferred packet-bank register. It is removed only in this relink.
- Numeric code-address aliases require physical-page guards on observations.
  A packet-code address must never be mistaken for a cold-loader entry.
- A cold epoch change excludes the **entire** transition from active timing,
  even when loading returns before the frame ends. Long preparation is not
  hidden inside gameplay statistics.

Suffix joins add packet-body cycles; the source-layout model also has some
three-cycle increases. They are not declared free or accepted merely because
the image fits. Direct mapping, unchanged IRQ paths and cache-selector savings
are measured together at full-game scope below. The earlier flat-body variant
keeps exact packet cycles but does not by itself close the complete memory map.

## Measured gameplay and limits

Private FS-A1WSX with **512KiB actual RAM**,128KiB VRAM, automatic Panasonic
CPU scopes, NTSC59.922743Hz refresh, enabled HUD/audio, real sprite limits and
strict VDP timing. Work is inclusive elapsed guest time from GameTurbo_Loop to
wait_blank, expressed in reference cycles or milliseconds; synchronization is
excluded. These are not accelerated CPU instruction counts. Period includes
wait and commit; self costs and a separate usable-VBlank budget are unmeasured.

Two direction/smoke schedules each run360 presentations at native rounds5/10/13
with three/five/six enemies. The initial schedule advances input by presentation
index. Changed cadence changes some trajectories: its three-enemy aggregate
presentation rate falls27.1324→27.0668FPS (0.24%), although work mean/P95/max
improve. This is retained as an unresolved route comparison, not omitted or
declared a universal speed gain.

The second schedule selects directions using the game's native-tick counter;
it changes only keyboard input, **never forces native ticks or alters rules**.
The existing once-per-presentation input sampling remains unchanged. Results:

| Enemies | Active frames control/RAM | Work mean, reference cycles | P95 | Maximum | Presented FPS control→RAM |
| --- | --- | --- | --- | --- | --- |
|3|173/173|94,143.96→93,480.58|146,774.33→145,641.67|186,354.00→185,138.67|26.9314→26.9314|
|5|152/153|105,171.67→104,429.02|160,764.67→159,618.67|213,820.67→195,337.67|25.4454→25.6128|
|6|162/163|114,431.10→113,069.73|172,884.67→171,285.67|261,367.00→244,152.67|24.4578→24.6087|

Route aggregates are not identical-state speedups. The native-clock runs have
**465 identical-state samples** (173/140/152); all have shorter work, and
matched mean/P95/max improve in each population. Matching requires the same
presentation index, camera, native actor-state bytesE088..E167, elapsed-tick
byte, enemy count and all14 PSG registers. It does not establish equality of
every native RAM byte or all gameplay. Both schedules and all unchanged/slower
cadence cases remain in the ledger and
[experimental workbook](measurements/timing/mapper512-integrated.xlsx).

Normal active runs perform **zero cold bank refills**, with real IRQs and no
strict VDP callback. Slot-write guards prohibit selecting cartridgePage1/Page2
after takeover. Native/audio/decor/source/code hot segments remain byte-exact
against their installed family image. Independent snapshots validate dynamic
world, fixed HUD, numeric/life SAT and complete car patterns.

Four additional240-presentation runs use **real boot-held F10 input**, release
at title and actual F5 transitions4→5,8→9,12→13,16→17. All four family boundaries
pass the independent graphics oracle, preserve the latch and expanded caches,
and retain239 active frames after excluding the transition. These are test-key
advances, not naturally earned clears. Host loading time is not a disk-time
measurement. The immutable public F10 qualification continues to cover the
car/rock death bypass and solid walls; these integration tests additionally
cover its RAM lifetime through takeover and family changes.

PSG register equality is scoped to matched samples and immutable audio code.
Waveform listening, every audio event, full-course lifecycle, alternating
players, attract/restart after takeover, PAL50, other CPUs and physical hardware
are not newly qualified. Neither a universal speedup nor complete512KiB
no-regression acceptance is claimed. The current supported744KiB/768KiB build
remains the fallback.

## Remaining independent loader work

Hot execution fits; **cold ownership is still a separate proof**. The current
diagnostic copies stopped raw resources into segment10, installs the current
family and host-reconstructs maps. A real loader must replace those services
with disk reads and bounded decoding, including initial boot presentation/F10,
DOS/BASIC entry, mapper/slot ownership, allocator lifetimes and error handling.

No extra segment can be assumed for OS context, DMA, directory or compressed
input. A possible next approach is to borrow cold flag-cache segments4/5 while
stopped, preserve OS snapshots in explicitly declared holes and rebuild caches
before gameplay resumes. This is a design direction, **not an allocated or
tested32KiB snapshot reservation**; changing families currently replaces whole
hot segments and would overwrite such holes. DOS/BASIC callback/IRQ mapping and
initialization peak must be proven before advertising512KiB disk support.

## Preservation and reproduction

495 general tests and94 component tests pass (one component skipped), as does
the historical zero-delta module-layout proof. Fresh independent startup/game
checks pass for the unchanged64KiB cartridge,768KiB MegaRAM DOS/BASIC and legacy
4MiB main-mapper DOS/BASIC executable. Their old capacity requirements remain
explicit. Public ROM SHA-256 remains
`44be6037d05ebf763283f14ef6deb6e4a8bd58b0a25fcc04c693d899c3704f00`.
ZIP hashes and current canonical timing ledger/workbook are preserved exactly.
Only the separately scoped experimental timing workbook is added.

With the frozen F10-enabled build and contributor inputs prepared:

```sh
.venv/bin/python -B scripts/mapper512_integrate.py
# Run each population with and without --control, and both input schedules.
.venv/bin/python -B scripts/mapper512_integrated_verify.py --round 5 --frames 360
.venv/bin/python -B scripts/mapper512_integrated_verify.py --round 5 --frames 360 --control
.venv/bin/python -B scripts/mapper512_integrated_verify.py --round 5 --frames 360 --input-clock native
.venv/bin/python -B scripts/mapper512_integrated_verify.py --round 5 --frames 360 --input-clock native --control
# Repeat the four commands for rounds10 and13.
.venv/bin/python -B scripts/mapper512_integrated_verify.py --round 4 --frames 240 --f10 --transitions
# Repeat for rounds8,12,16, covering1->2,2->3,3->0 families.
.venv/bin/python -B -m unittest discover -s tests -v > references/build/issue42-integrate-tests.log 2>&1
.venv/bin/python -B -m unittest discover -s src/toolchain/screen4 -p 'test_*.py' -v > references/build/issue42-integrate-components.log 2>&1
make verify-module-layout > references/build/issue42-integrate-module.log 2>&1
.venv/bin/python -B scripts/compact_game_verify.py --mode rom --ram-kib 64
.venv/bin/python -B scripts/compact_game_verify.py --mode dos --size 768
.venv/bin/python -B scripts/compact_game_verify.py --mode basic --size 768
.venv/bin/python -B scripts/verify_disk.py --mode dos --ram-kib 4096
.venv/bin/python -B scripts/verify_disk.py --mode basic --ram-kib 4096
.venv/bin/python -B scripts/mapper512_integrated_report.py
make timing-workbook TIMING_LEDGER=docs/measurements/timing/mapper512-integrated.json TIMING_WORKBOOK_GENERATOR=scripts/mapper512_workbook.mjs
```

The experimental writer preserves `docs/cycle-budget.xlsx` and its ledger,
recording separate RAM-image seals. Raw original-derived fixtures, snapshots,
logs and emulator homes stay ignored and are disposable after consolidation.

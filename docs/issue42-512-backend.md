# Issue42:512KiB RAM-mapper backend experiment

Historical scope: this report predates the optional boot F10 feature. Its
original ROM hashes and measurements remain unchanged; see the
[current artifact qualification](f10-invulnerability.md).

The owner subsequently allowed longer inter-stage preparation, preserving the
strict active-gameplay speed gate. The [cold-stage continuation](issue42-stage-overlays.md)
implements bounded edge replacement, faithful ranking reconstruction and
absolute packet variants. It retains the F10-enabled744KiB fallback and still
does not qualify a complete512KiB executable. This report's earlier costs and
hashes are unchanged.

The owner authorized a cartridge-free512KiB main-mapper attempt while retaining
the64KiB cartridge, disk and MegaRAM editions and current graphics/audio/rules/
performance. The744KiB ROM and768KiB MegaRAM target are the fallback for eventual
stabilization. **Do not publish a release yet.** This experiment did not change
or replace any public artifact and does not deliver a512KiB game executable.

## Implemented backend component

`scripts/mapper512_backend.py` packs each source record into2KiB instead of4KiB.
All160,041 live pixel/metadata bytes survive; no free area is inferred from
pixel values or FF runs. Eight records fit one16KiB source page, totaling12
source pages. Metadata pointer relocation remains a full-game integration task.

Packets execute from a separate16KiB Page1 mapper window; Page2 holds source
data. D/E supply the two source high-byte bases. Source loads become LD H,D/E,
bounded INC/DEC H and LD L,n; known post-copy pointers still remove redundant
loads. C becomes98, B retains the original long-reset/short-decrement result,
D/E/IX/IY survive and HL/AF/flags are scratch. Nonempty packets endEI; empty
packets preserve entry IFF. The caller owns source/code windows and the stack.

Shared instruction suffixes use direct JP within a single16KiB closure.
Every code window contains its entire reachable graph; no cross-bank jump,
interpreter or active decompression is concealed. A terminal JP is duplicated
instead of jumping to another JP, saving11 cycles without increasing storage.
Exact-count OUTI workers retain the existing19-cycle write spacing.

Three variants were measured:

- **Relative:** source-relative loads and inline short transfers. This reclaims
  the29-cycle short CALLs previously spent to reduce cartridge code.
- **Compact:** short transfers use suffix CALLs; repeated23-byte VDP setup
  headers use shared workers; instruction suffixes share code. Smallest storage.
- **Hoisted:** the common14-byte header moves into Page3 dispatch in its original
  order, immediately before the jump into Page1. It adds no header CALL cost.
  Short transfers remain inline; suffix sharing remains enabled.

The mechanisms and synthetic tests are authored source. Derived packet bytes,
fixtures and traces stay under ignored `references/build/game-mapper512/`.

## Execution and timing

Both compact and hoisted runs execute all4,384 production packet references,
each with baseline/relative/candidate bodies and both extreme pattern tables:
**26,304 executions per run,52,608 total**. Every case checks all128KiB VRAM,
BC/DE/HL/IX/IY/SP/IFF and the independently calculated instruction cost.
Strict VDP timing callbacks: **zero**.

These are real512KiB mapper-RAM component executions. The unchanged cartridge
boots the game through keyboard input; gameplay is then frozen. CPU slot writes
unmap the cartridge from Page1/Page2, and code/data fetches use the real mapper.
Host injection supplies diagnostic fixtures. This proves the packet mechanism,
**not** cartridge-free startup, a DOS loader, full-game audio or an integrated
512KiB resident image. VDP IRQ generation is disabled for isolated timing.

Machine: private FS-A1WSX reference with512KiB main RAM,128KiB VRAM, SCREEN4
display on, real VDP timing and fixed base Z80 at3,579,545Hz, openMSX22.0.
The measured immediate OUT cost is13 cycles including MSX I/O wait; the19-cycle
OUTI model is unchanged. Timing below is elapsed guest cycles, not FPS.
Baseline production packets also execute in RAM in the same fixture, isolating
the compiler changes; these are not whole-ROM gameplay measurements.

| Packet body | Mean | P95 | Maximum |
| --- | ---: | ---: | ---: |
|744KiB baseline|9,252.55|11,905|29,974|
|Relative|9,230.03|11,812|30,011|
|Compact + suffixes|9,310.72|11,978|30,062|
|Hoisted + suffixes|9,264.73|11,834|30,033|

The compact variant's paired body delta is+58.17 cycles on average,
P95+77/max+99. Of8,768 paired observations,8,576 are slower and192 unchanged
within the1-cycle observation threshold. Hoisted delta averages+12.19,
P95+74/max+151;6,116 are slower,214 unchanged and2,438 faster. Relative improves
mean/P95 but increases maximum. Mapping, D/E setup and Page1 return costs are
additional; no calls-per-presented-frame or gameplay FPS is inferred here.

These component regressions disqualify direct promotion. They do not prove an
integrated backend cannot offset the cost: replacing paired8KiB raw-bank
switches with direct16KiB mapping may save work elsewhere. That benefit has not
been measured in a complete game, and is not credited speculatively.

## Resident-memory accounting

Packed source pages, code windows and required working segments are distinct.
The full current expanded radar cache uses **six** working segments, including
two flag-cache segments; the64KiB cache strategy uses four. Silently selecting
the slower cache is not a free memory saving. Its performance would need a
same-machine comparison before adoption.

| Suffix variant | Code windows | Code bytes | Before cold resources,64KiB cache | Before cold resources,current expanded cache |
| --- | ---: | ---: | ---: | ---: |
|Compact|10|137,265|464KiB|496KiB|
|Hoisted|12|184,187|496KiB|528KiB|

This optimistic count keeps resident/native/audio owners0/71/73 uncompressed,
treats other owners as cold and assumes the8-byte restart seed can be cached.
Using the existing bank LZ format with length/checksum headers, the current
reference cold payloads require82,862 bytes:33,390 for other raw owners,
18,473 for the eight maps,29,065 for the lossless boot atlas and1,934 for the
ring worker. These are declared reference bytes/compressor results, not a linked
512KiB format or a mathematical minimum.

Even allowing every declared source/code hole to hold cold backing, compact
plus the expanded cache totals **538,434 bytes**,14,146 over512KiB, before new
dispatch/IRQ/decoder/directory/staging costs. Hoisted reaches579,166 bytes.
Compact with the64KiB cache provisionally reaches505,666 bytes, leaving18,622
bytes before those missing costs and any initialization-lifetime constraints;
it already has the body-cost regression above. File/ZIP compression alone does
not establish a resident fit.

Possible further work includes cold lifetime overlays, a smaller flag-cache
representation with measured timing, budget-aware sharing, and complete
native/audio16KiB mapping. It must also relocate or bridge the resident IRQ:
mapping packet code into Page1 removes the current IRQ handler's instruction
window. The isolated fixture disables VDP IRQ generation explicitly; it does
not establish the required whole-game interrupt safety. DOS/BASIC takeover,
compressed-data residency, boot/skip deadlines and cold-transition costs also
remain unresolved. No larger RAM requirement is disguised as512KiB support.

## Decision, preservation and reproduction

**Neither512KiB variant is promoted.** There is no evidence yet for a complete
512KiB game with unchanged performance. This is not a proof that every possible
backend is impossible. Keep744KiB/768KiB as the stable fallback and do not
trigger a merge/release based only on these component failures.

The exact public ROM remains
`b39e0c7f520872174e9a89cc46ddf4e1957179bc70ac3326c6450420866a878c`.
Both disk packages, default implementation hashes, symbol file and current
744KiB timing ledger/workbook remain unchanged. Their whole-game evidence stays
in [the768KiB qualification](issue42-768-optimization.md); it is not relabeled
as512KiB evidence. Fresh300-presentation startup/graphics checks pass for the
unchanged ROM on64/512KiB RAM and for MegaRAM768KiB DOS/BASIC; the unchanged
4MiB standard-mapper edition also passes DOS/BASIC again. The512KiB ROM snapshot
confirms main/map/flag working segments1/2/3/4/5 plus Page3segment0, all distinct.
These preservation checks are separate from the experimental component runs.
486 general and94 component tests pass (one component skipped), and frozen
module-layout verification passes.
No commit, push, merge or release was performed.

The compact [experiment ledger](measurements/cartridge/issue42-512-backend.json)
retains source hashes, timing distributions, cold accounting, preservation
checks and limits. No original data/fixtures are committed. Reproduce with the
existing supplied inputs/default source bundle and retained `dist/` seal. The
legacy disk ZIP includes file timestamps; rebuilding it creates a different
archive seal even when its executable game image remains unchanged.

```sh
.venv/bin/python -B scripts/mapper512_backend.py
.venv/bin/python -B scripts/mapper512_verify.py --variant compact
.venv/bin/python -B scripts/mapper512_verify.py --variant hoisted
.venv/bin/python -B scripts/compact_game_verify.py --mode rom
.venv/bin/python -B scripts/compact_game_verify.py --mode rom --ram-kib 512
.venv/bin/python -B scripts/compact_game_verify.py --mode dos --size 768
.venv/bin/python -B scripts/compact_game_verify.py --mode basic --size 768
.venv/bin/python -B scripts/verify_disk.py --mode dos
.venv/bin/python -B scripts/verify_disk.py --mode basic
make verify-module-layout > references/build/issue42-512-module-layout.log 2>&1
.venv/bin/python -B -m unittest discover -s tests -v > references/build/issue42-512-tests.log 2>&1
.venv/bin/python -B -m unittest discover -s src/toolchain/screen4 -p 'test_*.py' -v > references/build/issue42-512-components.log 2>&1
.venv/bin/python -B scripts/mapper512_report.py
```

After consolidation, delete diagnostic fixture payloads/traces and retain this
ledger/document. Physical hardware, PAL50 and subjective acceptance remain
separate from the component evidence.

# Issue41: minimum-ROM investigation — initial findings

**Historical inventory.** The [complete compact game and loader](issue41-compact-game.md)
supersede the implementation status below; retain these original measurements.


Issue: https://github.com/sandersouza/msxgp-newrallyx/issues/41
Status: In progress. This is a read-only inventory and storage-placement
probe, not an implemented cartridge reduction or runtime qualification.

## Revised hardware objective

The acceptance target is now **below 1 MiB (1,048,576 bytes)**, toward smaller
cartridge storage or MegaRAM loading, with the same fidelity/performance and
64 KiB cartridge RAM compatibility. A standalone16 KiB saving is not a useful
delivery for this objective. Do not promote that micro-reduction unless it
supports a demonstrated path to the smaller-capacity target.

For16 KiB-aligned ROMs, strictly below1 MiB means at most63 banks /1,032,192
bytes: at least62 banks /1,015,808 bytes must be removed from the baseline.
The current64 phase banks plus32 world-edge banks already occupy1,572,864
bytes. Therefore **cold-only compression/repacking cannot meet the target
while retaining the current direct bank layout**, even if all other content
could occupy zero additional banks. This is a layout-specific result, not
proof that a redesigned renderer cannot fit below1 MiB.

Next useful experiment: a compact representation of the hot phase/edge data,
with an explicit64 KiB RAM/128 KiB VRAM lifetime map, followed by worst-case
native3/5/6-enemy timing. Stop that approach if the exact image, sound or game
rules change, or cache misses/decompression degrade performance. Offline zlib's
360,016-byte result is an opportunity signal only; it is not an executable.

Additional exact-page sharing probes also miss the goal: unique8 KiB pages
still occupy1,982,464 bytes; unique4 KiB pages occupy1,929,216 bytes, before
dictionary metadata or runtime lookup. Thus simple page deduplication and the
16 KiB startup move are insufficient. A useful next design candidate is a
smaller-window banking layout (for example8 KiB) with compacted hot tables and
proved removal of obsolete fields, plus cold-only compression where feasible.
The present cost tables and transfer addresses extend into the upper half of
each16 KiB bank, so changing mapper labels alone cannot implement that design.
Worst-case per-window fit, additional bank writes and interrupt ownership must
be measured before choosing a new mapper or claiming a sub-1-MiB image.

### Why the arcade fits in a few kilobytes

The contributor set totals **21,600 bytes**:16,384 bytes of program,4,096 bytes
of graphics and1,120 bytes of PROMs/tables. Its video and sound electronics
perform work which is not stored as software/expanded tables in those files.
The [MAME driver](https://github.com/mamedev/mame/blob/master/src/mame/namco/rallyx.cpp)
documents the native Z80 map, scroll registers and Namco hardware.

The MSX implementation preserves native game rules but stores derived video
representations:64 fine-scroll combinations,4,096 HUD transition references,
32 edge banks across world layouts and375,166 bytes of compiled transfer code.
The cold startup stream occupies186,918 bytes inside existing bank gaps.
These categories overlap mixed banks and must not be summed as independent
allocated ownership. Most growth is the chosen speed/storage tradeoff in the
renderer and its bank layout, not original game content or audio samples.

ROM banking, system RAM mapper and MegaRAM are distinct interfaces. A small
ROM does not automatically run on every MegaRAM. A MegaRAM loader/backend
requires separate bank-switch, capacity and execution tests. Likewise the
existing disk executable's4 MiB system-mapper requirement is separate from
the ROM's64 KiB RAM requirement; reducing a ZIP alone changes neither.

## Reproduced baseline

`make build` reproduced the released **2,048,000-byte** image,125 complete
ASCII16 banks, SHA-256
`d73539eb988b6de198a214bcb5e03476df903dec82fe78a53cc30ea9308ea963`.
The local source base is `533b4f22e842a61694eba82090d0ad511557f28e`.
Existing uncommitted disk-edition work remains present and untouched.
Investigation branch: `enhancement/41-minimum-rom-investigation` (local).

The executable archive remains SHA-256
`d2ba12f51d0f275a987bcdd93d43b72b93f422ab3ba2f034599e40337234e389`.
No playable artifact, graphics, sound, game logic or timing was changed.
The64 KiB cartridge contract and both delivery forms remain mandatory.

Baseline checks: 470 general tests and 93 component tests pass; one component
test is explicitly skipped. No runtime candidate has been qualified yet.

## Inventory

[Machine-readable metadata](measurements/cartridge/issue41-inventory.json)
accounts for all125 banks exactly once. It decodes3,238 transfer programs
and validates14,709 relocation sites against generated metadata.

- Phase/HUD mixed banks:1,048,576 bytes (64 banks).
- World-edge mixed banks:524,288 bytes (32 banks).
- All other owners:475,136 bytes (29 banks).
- Complete duplicate banks: **zero**.
- Semantically duplicated transfer code:475 bytes; not enough to remove a
  bank by itself, and cross-bank reuse could add switching/call overhead.
- Repeated exact tile records:16,576 HUD bytes and30,144 world-boundary bytes.
  These are references within existing layouts, not additive removable banks.
- FF-like trailing runs total137,222 bytes and zero-like runs17,382 bytes.
  Neither is proof of unused space; reservations and consumers still matter.

The96 mixed graphics/transfer banks occupy76.8% of the image. Earlier #36
packing already shares literal data and stores cold streams in their holes.
Removing those streams would not remove separate replay banks again.

## Ranked candidates

| Priority | Candidate | Evidence | Remaining qualification |
| --- | --- | --- | --- |
|1|Move startup worker/descriptor bank124 into initial-terrain bank1|Full symbol-bounded prefix fits after the4,096 terrain bytes; potential one-bank saving:16,384 bytes|Audit every consumer, relink both formats, boot/skip/status/graphics tests and matched timing|
|2|Compress cold round maps/terrain into existing preparation lifetimes|Host zlib round-trips131,072 map bytes into5,923 bytes and65,536 terrain bytes into3,835 bytes|MSX decoder/metadata cost, exact64 KiB scratch lifetimes, map access, cold deadlines and actual bank elimination|
|3|Further packing across mixed HUD/edge banks|Largest allocated ownership; existing tables, fixed addresses and code have real consumers|Detailed address-level liveness and relocation constraints; no demonstrated net saving yet|
|4|Global tile sharing or generic hot-bank compression|Exact repeated tile bytes; per-bank host compression totals360,016 bytes for the whole image|Extra indirection/decompression/cache storage risks hot-path cost and64 KiB compatibility; unsuitable as a claimed ROM target|

Compression figures are offline storage observations, excluding target decoder,
metadata, alignment, decompression buffers and CPU cost. They are not executable
ROM sizes or proof that a smaller cartridge can retain current performance.

### Startup placement probe

`build.py` emits the initial4,096-byte terrain payload followed by FF fill in
bank1. Bank124 contains a1,536-byte startup-worker range and a356-byte
descriptor range at offset4,096. The probe retains the **complete4,452-byte
prefix**, including meaningful final FF bytes, and places it at bank1 offset
4,096. It verifies the terrain and both copied regions byte for byte.

This occupies bank1 offsets4,096..8,547 and fits within its16,384 bytes.
If all consumers can be rebound without added work, removing bank124 would
produce **2,031,616 bytes /124 banks**, a0.8% reduction. This is a storage-fit
projection; no linked candidate has yet achieved that size.

Required binding work includes `SESSION_BOOT_BANK`, the ROM source of the
startup-worker copy in `modules/session/boot.inc`, and the descriptor source
currently at9000 in `session-boot.inc`. Worker execution remains at2900 and
descriptor RAM remainsD300; changing immediate source addresses need not add
instructions, but unchanged runtime cost is still unverified.

The disk loader explicitly checks125 banks in two places. It must gain a
validated build-derived bank count before a124-bank cartridge can be offered
with a corresponding executable. Merely shrinking the ROM would break the
current disk delivery contract. Keep its separate expanded-RAM requirement
distinct from the cartridge's64 KiB requirement.

## Next gates

1. Prove all bank1/124 source ownership and references, including optional builds.
2. Link an ignored diagnostic candidate and independently compare decoded
   graphics, replay commands/deadlines, sound and native-state contracts.
3. Validate both64/128 KiB cartridge tiers, supported CPU modes, startup skip,
   all-round transitions and native3/5/6-enemy workloads with HUD/sprite limits.
4. Update disk bank-count handling and verify actual DOS/BASIC loading.
5. Only after runtime evidence, rank measured net savings and qualify a reduced
   artifact. No release update, commit or push is part of this initial audit.

There is no established global minimum yet. The subsequent
[compact backend experiment](issue41-compact-backend.md) allocates1,040,384
bytes and executes transfers, maps and replay components, with qualified
timing evidence. It is not a playable sub-1-MiB game. The current timing
workbook retains its original playable-ROM/workload identity.

## Reproduce

```sh
make build
.venv/bin/python -B scripts/rom_size_investigation.py
make test
shasum -a 256 dist/newrallyx.rom dist/disk/newrallyx-disk.zip
```

Source owners: `scripts/rom_size_investigation.py`, the reused
`src/toolchain/screen4/rom_audit.py` decoder and ownership contracts,
`build.py` terrain construction, `session_build.py` bank linking,
`modules/session/boot.inc` and `session-boot.inc` source bindings.
Historical context: `docs/issue36-size-reduction.md` and
`docs/issue36-rom-audit.md`. Only counts, offsets, hashes and reports are kept;
no original-derived payload is added to tracked files.

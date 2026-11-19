# Issue41: compact backend execution and complete allocation

**Historical component experiment.** Superseded by the
[complete game and MegaRAM loader](issue41-compact-game.md). Counts, hashes and
limits below describe the earlier experiment only.

Status: **1,040,384-byte storage allocation and executable component backend**.
This is not a playable sub-1-MiB game. Do not publish its diagnostic as a game
ROM. The released ROM and disk executable remain unchanged.

## Allocation

Source data at8000..9FFF and pooled transfer programs atA000..BFFF use separate
8 KiB windows. Two4 KiB records share each data page; source operands select
their respective half. No extra RAM cache is allocated.

| Owner | Allocation |
| --- | ---: |
|64 phase/HUD and32 edge records |393,216 bytes /48 pages |
|2,806 unique transfer programs |335,872 bytes /41 pages |
|18 retained16 KiB resident/native/audio/UI/terrain owners |294,912 bytes /36 pages |
|Additional cold space |16,384 bytes /2 pages |
|**Total** |**1,040,384 bytes /127 pages** |

This is8,192 bytes below1 MiB and1,007,616 bytes smaller than the released
2,048,000-byte image. A1 MiB mapper is the capacity target.512 KiB cannot hold
the729,088-byte hot allocation alone.

The following content uses declared field gaps/code tails and additional cold
space, rather than being added again to the allocation above:

- Ten16 KiB maps, including initial maps:23,164 compressed bytes plus linked
  fragment headers. All reconstruct exactly. The four **active terrain banks
  remain raw**; they are not assumed cold-only.
- All71 original linked boot states:194,374 encoded bytes and575 chains.
  Literal spans split at128 bytes to use small gaps. The original uses186,918
  bytes and51 chains, so the compact replay adds work.
- The1,934-byte shared name-ring worker and an explicit1,024-byte reservation
  for adaptation. The latter is not proof the eventual backend fits.

The entire4,452-byte bank124 prefix moves into initial-terrain bank1 after its
4,096 live bytes. Worker/descriptor bytes remain exact, but their source
consumers are not rebound. Other retained bank bodies remain unchanged apart
from that insertion into initial-terrain padding. No FF/zero scan establishes
free space: only declared owner fields and generator reservations do.

Records include names, patterns/colors, counts, the505-byte immediate name
program, relocated pointers, cost rows and radar return. Edge records retain
both LUTs and source sets. Every pointer selects its actual pooled code page.

**Unresolved:** phase-local legacy/R18 atlases are omitted under an unproven
liveness hypothesis. Raw-bank consumers still contain old logical IDs; actual
adaptation code is not installed in the reserved space. The allocation image
is intentionally non-bootable, local and ignored.

## Guest execution and timing

The diagnostic replaces the resident game header with a harness, while using
the complete127-page allocation. Guest instructions map the data page, read
its pointer, map the code page and execute. The host supplies case selection
and checks results, rather than supplying graphics or decompressed maps.

openMSX21.0; Panasonic FS-A1WSX; **64 KiB main RAM**; base3,579,545 Hz Z80;
V9958/128 KiB VRAM; real VDP timing and hardware sprite limits:

| Check | Original ASCII16 control | Compact ASCII8 |1 MiB MegaRAM |
| --- | ---: | ---: | ---: |
|Transfers, full16 KiB VRAM comparison |4,384 pass |4,384 pass |4,384 pass |
|Guest-decoded maps, exact16 KiB RAM comparison |N/A |10 pass |10 pass |
|Boot states, cumulative64 KiB VRAM comparison |71 pass |71 pass |71 pass |

Transfer bodies have **zero measured cycle delta for all4,384 references** on
both compact backends. SCREEN4 display is disabled for this measurement; no
game IRQ/audio workload runs. Inclusive transfer mean10,104.45, p95 13,015,
maximum32,920 base cycles; with diagnostic dispatch mean10,206.45, maximum
33,022. Do not add inclusive parent/child values. Actual phase selection,
field binding and native/audio bank-pair switches remain unmeasured. These
figures do not establish preserved whole-frame performance.

The cold map decoder writes into the existing Page0 map segment: no extra
16 KiB segment or buffer. Decoder/setup occupy376 bytes including diagnostic
padding. C022..C024 scratch and AF/BC/DE/HL/IX/IY/IFF ownership still require
game-lifetime integration. Mean739,828.1, maximum881,573 cycles per map
(about207/246 ms); direct LDIR copy is roughly344,000 cycles. Additional cold
load latency remains unaccepted. Register-held source/length reduced the
first decoder's1,015,630.3-cycle mean by about27%.

Boot drawing uses SCREEN5 with display enabled after the first state and
alternating hidden pages. Mean additional cost is1,144.14 cycles;29 states are
slower, maximum additional40,395 cycles. All draws fit their original tick
gaps in this isolated test, with26,600 cycles minimum remaining. **IRQ,
keyboard scanning, publication and integrated cold scheduling are excluded**;
this is not startup-deadline/input acceptance.

Important setup findings and rejected test mechanisms:

- DOS RAMAD bytes are uninitialized at this cartridge entry. BIOS ENASLT
  cannot replace its executing Page0 and retain its return path. Resident
  Page1 code clones the functioning Page3 primary/subslot instead.
- Register-PC changes inside an emulator breakpoint skip the breakpoint at
  the new PC. A guest jump trampoline plus arming-count assertions prevents
  accidentally checking the first map repeatedly.
- MegaRAM CHGMOD setup precedes selection of its executing Page1 bank.

Exact diagnostic hashes, CPU/video configuration, inclusive mean/p95/maximum
and unchanged/slower counts are in the JSON ledger. The existing current-ROM
cycle-budget.xlsx retains its round5 workload, rather than being relabeled
with isolated component measurements. `make timing-workbook` passed; its
previous workbook and original ledger were archived by the existing workflow.

## Preserved deliveries and MegaRAM limits

The current release was rebuilt and rechecked for300 natural first-round
three-enemy presentations, with HUD/audio, directional input and smoke:

| Released path | Main RAM mapper | Presented FPS in this workload |
| --- | ---: | ---: |
|ASCII16 ROM |64 KiB |32.225 |
|MSX-DOS executable |4 MiB |31.994 |
|Disk BASIC executable |4 MiB |31.994 |

These are unchanged-release regression observations, not compact-game or
matched3/5/6-enemy performance. PSG activity was observed; listening and
physical hardware acceptance remain separate.

ROM SHA256: d73539eb988b6de198a214bcb5e03476df903dec82fe78a53cc30ea9308ea963.
Disk ZIP SHA256: d2ba12f51d0f275a987bcdd93d43b72b93f422ab3ba2f034599e40337234e389.
Rebuilt executable/data payloads match the published archive. ZIP metadata
timestamps differ on rebuild; the exact published archive was restored after
comparing its contents. No release changed.

MegaRAM tests use a separate1 MiB device plus64 KiB main RAM. Guest switching
and port8E modes work for transfers, maps and replay. The512 KiB negative
control correctly detects aliasing. The emulator debugger supplies the image:
**there is no disk-to-MegaRAM game loader yet**. Physical devices, expanded
slots and mapper variants remain unqualified. Protocol source:
[openMSX MSXMegaRam implementation](https://github.com/openMSX/openMSX/blob/master/src/memory/MSXMegaRam.cc).

## Remaining gates and reproduction

1. Prove omitted atlas liveness; bind phase offsets, full uploads, names/guards,
   costs, flags/radar, optional consumers, native/audio pairs and IRQ ownership.
2. Install real adaptation code/metadata in audited lifetimes. Rebind boot
   sources; measure whole boot/skip/status and cold-round scheduling.
3. Link a playable ASCII8 ROM, adapt executable bank count/format and implement
   disk-to-MegaRAM loading. Current disk files still require4 MiB system RAM.
4. Run visible matched NTSC/PAL3/5/6-enemy timing and all-round, two-player,
   transition, CPU and64/128 KiB regressions. Update the current timing
   ledger/workbook with that playable candidate before qualification.

```sh
make build
.venv/bin/python -B scripts/renderer_window_probe.py
.venv/bin/python -B scripts/renderer_backend_verify.py
.venv/bin/python -B scripts/megaram_window_probe.py
make test
.venv/bin/python -B scripts/disk_package.py
.venv/bin/python -B scripts/verify_disk.py --mode rom --ram-kib 64
.venv/bin/python -B scripts/verify_disk.py --mode dos
.venv/bin/python -B scripts/verify_disk.py --mode basic
```

Contributor arcade/BIOS/DOS inputs remain necessary.470 general and94 component
tests pass, one component skip. Optional8 KiB cold packing in rom_pack.py has
a synthetic regression; default16 KiB output reproduces the original ROM hash.

Sources: scripts/renderer_{window_probe,image_build,backend_verify}.py,
scripts/megaram_window_probe.py, tests/fixtures/issue41-map-decoder.inc and the
synthetic MegaRAM fixture; src/toolchain/screen4/rom_pack.py. Compact evidence:
docs/measurements/cartridge/issue41-{allocation,backend-execution,
baseline-validation,megaram-probe,window-probe}.json. Original-derived images,
cases and sessions are disposable/ignored and removed after summaries.

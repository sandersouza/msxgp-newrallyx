# Issue41: split-window renderer experiment

Current playable result: [complete compact game and loader](issue41-compact-game.md).


Historical window-model stage. For the subsequent complete allocation and
executing guest backend, see [issue41-compact-backend.md](issue41-compact-backend.md).

Status at this stage: storage and transfer-equivalence prototype. No new playable backend
or release. The goal remains below1 MiB with unchanged fidelity/performance,
64 KiB system RAM for the cartridge and both cartridge/disk deliveries.

## Mechanism and results

Current phase/edge banks mix graphics sources, transfer code, metadata and
cold replay. A first8 KiB model moved useful fields together and relocated
transfer source operands. Only69 of96 windows fit; the largest needs10,117
bytes. Reserving extra windows for overflow still allocates1,007,616 hot bytes
before native logic/audio/UI, so that arrangement is rejected for the goal.

The second model separates source data at8000..9FFF from executable transfer
code atA000..BFFF. Programs can share exact instructions across different
data windows. Keeping one8 KiB data page per phase/edge still uses1,081,344
hot bytes, so that variant is also rejected.

The third model pairs two4 KiB data records in each8 KiB lower window. Their
source operands select the correct half; the upper window holds pooled code.
The resulting hot allocation is:

| Component | Allocation |
| --- | ---: |
|64 HUD/phase and32 world-edge data records |393,216 bytes /48 pages |
|2,806 unique compiled code bodies |335,872 bytes /41 pages |
|**Hot-window total** |**729,088 bytes /89 pages** |

The code bodies themselves occupy331,664 bytes. All4,384 original HUD/edge
transition references pass the independent decoder's normalized instruction,
source-payload and estimated instruction-cycle comparisons after relocation.
The probe changes only LD HL source operands in those code bodies. It does
not claim unchanged costs for the caller, mapper writes or the full frame.

Compare this with1,572,864 bytes allocated to the current mixed96 banks.
The difference is843,776 bytes, but excludes content formerly mixed into bank
holes. This is not a whole-ROM saving: cold replay, the shared1,934-byte ring
worker, native logic, audio, UI, maps, terrain and initial loading still need
allocation and valid consumers. Adding all existing other banks unchanged
would total1,204,224 bytes, already above1 MiB, before allocating displaced
cold streams. Thus **no sub-1-MiB executable has been demonstrated**.

Only319,487 bytes remain below the target after hot allocation. The next
allocator must account for every cold/active owner and the decoder overhead;
generic host compression numbers cannot stand in for that proof. Round maps
are copied into existing mapper segments at cold load, whereas terrain banks
are selected by GameSession_MapTerrain and must not be assumed cold-only.

## Unresolved runtime contracts

- The model omits phase-local legacy/R18 atlases under a liveness hypothesis.
  All consumers and optional paths still require proof before removal.
- Callers currently use fixed addresses for counts, name/radar programs,
  pointer tables and cost rows. Pairing records needs phase-dependent binding;
  any extra instructions must be budgeted and measured.
- The existing ASCII16 bank write cannot independently map the two windows.
  A candidate ASCII8/MegaRAM backend needs explicit lower/upper ownership.
- Native and audio workers still span16 KiB; mapping both halves can add work.
  IRQs and resident transfer helpers must preserve the foreground mappings.
- No extra16 KiB RAM cache is assumed: the64 KiB profile already owns its four
  segments. Data remains ROM-resident in this model.
- Full uploads, startup, cold replay, sprites, flags/radar, all rounds, two-player
  transitions and the disk loader are not yet implemented for the new layout.

## MegaRAM probe

A synthetic guest test passed in openMSX21.0 with **64 KiB main mapper RAM**
and a separately configured **1 MiB MegaRAM**. It switches banks0/42/64/127,
checks independent lower/upper8 KiB windows and uses IN/OUT port8E to alternate
write-enable and bank-selection modes. A512 KiB negative control correctly
fails when bank64 aliases bank0.

This establishes an emulator-level bank/write-mode mechanism only. It is not
a game loader, game performance, physical MegaRAM compatibility or release
acceptance. The ordinary512 KiB MegaRAM cannot hold this model's729,088-byte
hot allocation alone. The1 MiB configuration is a capacity hypothesis for the
target design, not a claim about every installed cartridge.

Protocol source: [openMSX MSXMegaRam implementation](https://github.com/openMSX/openMSX/blob/master/src/memory/MSXMegaRam.cc),
including the original hardware notes attributed to Adriano da Cunha. The test
uses a private extension definition and does not edit installed configurations.

## Evidence and reproduction

```sh
make build
.venv/bin/python -B scripts/renderer_window_probe.py
.venv/bin/python -B scripts/megaram_window_probe.py
make test
shasum -a 256 dist/newrallyx.rom dist/disk/newrallyx-disk.zip
```

Compact results: `docs/measurements/cartridge/issue41-window-probe.json` and
`docs/measurements/cartridge/issue41-megaram-probe.json`. Source owners:
`scripts/renderer_window_probe.py`, `scripts/megaram_window_probe.py`, the
synthetic `tests/fixtures/issue41-megaram-smoke.asm`, and the independently reused
transfer decoder in `src/toolchain/screen4/rom_audit.py`.

470 general tests and93 component tests pass, with one component skip.
ROM and executable archive hashes remain unchanged. No new full-frame timing
measurement exists, so the current timing workbook is not relabeled.

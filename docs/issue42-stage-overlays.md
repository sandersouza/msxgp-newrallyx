# Issue42: cold-stage preparation toward512KiB

Continuation: [full-game RAM-active integration](issue42-512-integration.md)
now fits the active working set in32 real segments and measures live IRQ,
HUD/audio and F10 transitions. Its independent disk loader/cold peak remain
unqualified. This historical component report retains its original scope.

Issue: https://github.com/sandersouza/msxgp-newrallyx/issues/42

The owner now permits longer **inter-stage preparation**, while active gameplay
speed, graphics, audio, rules,64KiB cartridge support and both executable formats
remain strict. This does not permit recurring drawing stalls, slower turns,
flag-event pauses or active decompression. **No release or merge.**

The current fallback includes the subsequently requested boot F10 test mode:
744KiB ASCII8 SHA-256
`44be6037d05ebf763283f14ef6deb6e4a8bd58b0a25fcc04c693d899c3704f00`.
The [preceding backend report](issue42-512-backend.md) retains its earlier hash
and results. Neither this continuation nor its prospective byte totals qualify
a complete512KiB cartridge-free executable.

## Implemented components

`mapper512_backend.py::absolute_programs` resolves source operands during cold
linking instead of supplying D/E source bases while drawing. It preserves the
current optimized load/count choices and moves the same14-byte VDP header to
the caller, in the original order. Two links separate storage from execution:

| New packet variant | Executions | Paired mean/P95/max body delta | Decision |
| --- | ---: | --- | --- |
| Absolute, contiguous |26,304|0 /0 /0 cycles within observation jitter|Body cost preserved; complete memory/dispatch/gameplay still open|
| Absolute, shared suffixes |26,304|+25.83 /+44 /+66 cycles|Not promoted on storage savings|

Each run covers4,384 production references, baseline/relative/candidate and
both extreme pattern tables. All128KiB VRAM, BC/DE/HL/IX/IY/SP/IFF pass;
strict VDP callbacks are zero. Contiguous baseline/candidate body mean/P95/max
are9,252.55 /11,905 /29,974 cycles. D/E are preserved, not source inputs.
These are isolated real-RAM body costs, not gameplay FPS or complete dispatch
costs. Full-game mapper/native/audio savings are not credited speculatively.

`src/disk/mapper512-stage.asm` implements a bounded212-byte cold decoder. Only
the eight edge-source records of the current family occupy its16KiB destination;
the earlier all-family source allocation was64KiB. All four compressed families
remain available in15,371 bytes plus16 directory bytes. Thus the **48KiB active
source reduction is not a48KiB net-memory or ROM saving**.

The real512KiB RAM fixture performs32 successful replacements covering all16
family transition pairs, plus eight malformed-input rejections. It preserves
retained backing, every unrelated RAM bank, protected Page3 state and VRAM.
Cold preparation mean/P95/max is283.84 /289.33 /289.33ms on base Z80. This is
additional decoder work, not the complete game's transition duration.

The optional source packer also keeps only the current family's65-byte victim
ranking per HUD phase, reclaiming12,480 active bytes. Simply retaining compressed
copies of every ranking was rejected: that backing alone costs15,047 bytes.
`mapper512_rank.py` instead factors the **existing** HUD/edge cost model into an
8,896-byte basis, with low/high HUD bytes stored separately for compression.
Its bounded LZ backing costs8,467 bytes including its bank header.

`src/disk/mapper512-ranking.asm` reconstructs all4,160 ranking bytes for one
family in stopped-game preparation. All16,640 original ranking bytes across
four families match exactly, including the unknown-cache entry, rounding and
254 clamp. The173-byte helper costs417.59 /417.60 /417.60ms mean/P95/max.
Pixel offsets do not change. Source metadata pointers and the game selector
still need relinking; these helpers are not called by the public game.

## Memory and integration gate

The [compact ledger](measurements/cartridge/issue42-stage-overlays.json) counts
six expanded-cache work segments, the existing three opaque resident/native/
audio owners, source bytes, code windows, exact-transfer workers, new cold
helpers, compressed edge/ranking backing, maps, ring and other raw owners.

The all-family absolute-suffix plan reaches527,982 prospective live bytes.
Discarding only bank1's boot-only tail after replay, while retaining its4KiB
terrain, would lower that to524,089 bytes, just199 below512KiB. **That is not a
fit:** fragment placement, metadata/directory/IRQ/dispatch and active UI/decor/
terrain-permission residency remain unresolved. Boot-atlas disposal, renderer
creation peaks and OS/takeover lifetimes also remain unqualified. Those missing
owners must not be hidden in the199-byte margin.

The all-family contiguous plan, whose packet bodies preserve timing, still
requires573,629 prospective bytes even with that boot-tail lifetime proposal.
Per-family code graphs are smaller, but their reconstruction backing is not
implemented; their table rows explicitly exclude it and cannot claim a fit.
No slower cache tier, reduced graphics or lower update frequency is used.

The destructive fixtures bootstrap from the unchanged cartridge, then the CPU
unmaps cartridge Page1/Page2. Host-injected inputs are explicit. VDP IRQ
generation is disabled and the cold helpers return DI; their diagnostic C700/
CA00 addresses overwrite game state. Installing them in production requires
valid memory lifetimes, IRQ/clock/audio handling and the complete DOS/BASIC
loader. A longer transition does not waive these requirements.

The next integration gate is a complete native16KiB mapping/IRQ/metadata path,
then identical-state three/five/six-enemy gameplay profiles with HUD/audio and
real sprite limits. Only those measurements can accept or reject any net speed
tradeoff. No body-only timing or ZIP size substitutes for that test.

## Preservation and reproduction

The F10-enabled744KiB ROM, MegaRAM768KiB DOS/BASIC ZIP and legacy4MiB main-mapper
DOS/BASIC ZIP remain byte-identical. Fresh300-presentation startup/graphics
checks pass for cartridge64/512KiB and MegaRAM DOS/BASIC; the legacy executable
also passes both entry modes. These are preservation smoke checks, not active
performance comparisons.491 general tests and94 component tests pass (one
component skipped), as does the historical module-layout check.

The current [gameplay workbook](cycle-budget.xlsx) and its ledger retain the
exact F10 ROM hash and workload. New stopped-game/component timings belong to
this ledger, not to a relabeled gameplay workbook. Physical hardware, PAL50,
subjective listening and owner play acceptance remain separate.

```sh
.venv/bin/python -B scripts/mapper512_verify.py --variant absolute
.venv/bin/python -B scripts/mapper512_verify.py --variant absolute-flat
.venv/bin/python -B scripts/mapper512_stage_verify.py
.venv/bin/python -B -m unittest discover -s tests -v > references/build/issue42-stage-tests.log 2>&1
.venv/bin/python -B -m unittest discover -s src/toolchain/screen4 -p 'test_*.py' -v > references/build/issue42-stage-components.log 2>&1
make verify-module-layout > references/build/issue42-stage-module-layout.log 2>&1
.venv/bin/python -B scripts/compact_game_verify.py --mode rom
.venv/bin/python -B scripts/compact_game_verify.py --mode rom --ram-kib 512
.venv/bin/python -B scripts/compact_game_verify.py --mode dos --size 768
.venv/bin/python -B scripts/compact_game_verify.py --mode basic --size 768
.venv/bin/python -B scripts/verify_disk.py --mode dos
.venv/bin/python -B scripts/verify_disk.py --mode basic
.venv/bin/python -B scripts/mapper512_stage_report.py
```

Keep contributor inputs and compact reports/workbooks. Delete raw generated
fixtures, traces, screenshots and temporary builds after consolidation.

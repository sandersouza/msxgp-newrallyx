# Original Z80 execution and native integration boundaries

Issue [#10](https://github.com/sandersouza/msxgp-newrallyx/issues/10) investigates
native reuse; it does not integrate the complete game. The recommended first
experiment retains original program addresses in page-0 RAM and original video
state in page-2 RAM, with checked hardware adapters. The user-selected minimum is
**128 KB RAM mapper and 128 KB VRAM**, at standard CPU speed. More mapper RAM may
be used when useful; supporting 64 KB RAM is no longer a design constraint.
The existing movement-only relocation is not a full-game linker.

### Reference machine

The run, player, HUD and raster verification launchers create a session-local
`Panasonic_FS-A1WSX_NR128` configuration with a 128 KB main RAM mapper.
[`mapper_reference.tcl`](../scripts/msx/mapper_reference.tcl) derives it from the
installed machine XML, updates RAM capacity and mapper readback bits, and verifies
that at least one mapper exposes 131,072 bytes. Installed openMSX files and global
settings are unchanged. Other selected machines must also meet this minimum.

The local test in `references/build/mapper-128-check/` confirmed a 131,072-byte
mapper, independent storage in segments 4–7, and successful boot of the existing
renderer after ten emulated seconds. This is a memory/boot check, not a timing
validation of the future full native runtime.

Extra 16 KB segments are available for preloaded assets, snapshots and staging
buffers. They do not expose more than four CPU pages at once, remove the
BIOS/native-address conflict, or make original-ROM writes safe in a writable copy.
Mapper switching and permanently reachable IRQ code still require a measured
integration design.

## Reproduce the local evidence

Supply the supported unpacked ROM set in `references/roms/nrallyx/` and use the
project `.venv`, z80dasm 1.2.0 and MAME 0.289. No ROM download is performed.

```sh
.venv/bin/python -B scripts/z80_analysis.py --capture --output references/analysis/reference-a
.venv/bin/python -B scripts/z80_analysis.py --capture --output references/analysis/reference-b
.venv/bin/python -B scripts/z80_analysis.py --output references/analysis/reference-a --compare references/analysis/reference-b
make test
```

Without `--capture`, the tool generates a program image, address index, linear
disassembly and source provenance only. Each destination must be fresh, ignored,
inside `references/analysis/`, and contain no symlink or tracked file. Partial
failed acquisitions remain there for diagnosis; only completed outputs have a
sealed manifest. Do not commit any generated output.

The loader validates all 13 supplied ROMs against the existing pinned inventory,
applies its split program loads, and rejects overlap, missing coverage and wrong
hashes before analysis. The four program files are **not** simply concatenated.
The reconstructed 16 KB program SHA-256 is
`d6943e556fcd6ffc32bcc1cc4abbec2249c16a2059a3cdc0ba9c942dbb765d4c`.
Source integrity is validated again after capture. Hook span hashes are separately
pinned in [`z80_hooks.json`](../scripts/z80_hooks.json); a mismatch is an error,
never a reason to apply offsets to another revision.

## Evidence and its limits

The October 21, 2026 reference runs are local directories
`references/analysis/issue-10-reference-c/` and `issue-10-reference-d/`.
Both begin with a fresh MAME configuration and observed soft reset, use
[`gameplay-inputs.json`](../scripts/scenes/gameplay-inputs.json), and run 3,200
arcade frames (52.8 emulated seconds). Coin is pressed at 1800, Start at 1860,
smoke at 2400, and Up at 2600; releases remain in the replay file.

The comparison found **1,417 byte-identical deterministic payloads**, including
1,402 state snapshots, program/disassembly/index, replay, frame/access records,
seven instruction traces and the derived summary. Logs, emulator configuration,
absolute acquisition paths and manifests are intentionally excluded. This proves
reference acquisition repeatability; it is not a native-MSX differential test.

Each snapshot is 6,536 bytes: 4,096 bytes from `$8000..$8fff`, 2,048 from
`$9800..$9fff`, then 392 observed write-shadow bytes for `$a000..$a187`. Unwritten
shadow positions are zero placeholders, not readable hardware values. Samples
are taken at the existing scene-capture vblank-before-IRQ phase, before applying
that frame's input changes. `frames.tsv` records PC, SP, IM, I and IFF1 at this
phase; it does not claim these are instruction-by-instruction stack extrema.

Write taps cover the entire program address space, including writes caused by
indexed, indirect and block instructions. Hardware reads and I/O accesses are
also recorded. `pc_reported` is MAME's PC during the access, often the following
instruction; **never use that field directly as a patch address**. Actual
instruction starts come from the debugger traces. Trace windows are frames
0–2, 654–658, 756–760, 1015–1017, 1860–1862, 2300–2302 and 2400–2402.
They contain 79,025 executed instructions at 2,217 distinct addresses. Linear
disassembly also decodes tables as instructions and is exploratory only.

The observation covers reset, diagnosis, attract, coin/start, initial driving,
smoke and steering. It does not establish coverage of later rounds, service mode,
two-player turns or every indirect target. Sound generation and native MSX
execution are outside this acquisition. BIOS files are present locally, but this
tool neither loads nor modifies them.

## Execution, interrupts and cadence

| Boundary | Verified behavior | Consequence |
| --- | --- | --- |
| Reset `$0000` → `$3800` | Startup uses a ROM-resident return-address script; the initial SP is `$384c` | Do not interpret all startup stack reads as writable stack use |
| Diagnostic `$38cc` | IM 2, I=`$3f`, output vector `$fe`; frame samples enter IM 2 at 656 and return to IM 0 at 758 | Arcade initialization cannot own the MSX interrupt mode |
| Game vector `$0030` → `$01f0` | Port 0 selects `$f7`, an IM-0 RST-30 opcode; handler saves HL/DE/BC/AF/IX/IY | MSX VDP IRQs cannot be substituted for the arcade vector unchanged |
| `$01f0..$0471` | IRQ acknowledges via `$a181`, samples controls, publishes video state, restores saved registers and enables interrupts before return | Candidate logical-tick/presentation boundary; preserve the interrupted PC and stack |
| `$0c2c` | Resets SP to `$8400` and dispatches state work; 18 visits in trace 2300–2302 and 12 in 2400–2402 | Not a returning subroutine and not one update per display frame |
| `$0069` | Movement/descriptor update; two calls in each two-frame gameplay trace | Reuse existing movement oracle, but retain the full interrupt-driven scheduler for broader integration |

The pinned [MAME machine configuration](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/mame/namco/rallyx.cpp)
specifies a 3.072 MHz CPU and 6.144 MHz pixel clock with 384×264 timing:
one tick every 16.5 ms, or approximately 60.606 Hz. Port-0 observations are four
`$f7` writes and one `$fe` write over the complete segment. Sampled SP ranges
from `$384e` to `$8400`; gameplay stack storage descends below `$8400` into the
video-state address region. Reserve that overlap rather than treating the entire
4 KB video buffer as exclusively graphical data.

## Memory and hardware map

The table follows the pinned driver's implemented map, rather than extending its
schematic decode notes into unverified mirrors. See `summary.json` for all
observed address/PC pairs and `program.asm` for local instruction annotations.

| Arcade address | Meaning | Native handling |
| --- | --- | --- |
| `$0000..$3fff` | Program and tables, including data read through SP | Preserve addresses in RAM only after handling writes into original ROM |
| `$8000..$8fff` | Video state, descriptors, game variables and stack overlap | Ordinary RAM writes; renderer reads a committed snapshot or dirty comparison |
| `$9800..$9fff` | Work RAM | Ordinary RAM; retain all 2 KB until narrower ownership is proven |
| `$a000` read / `$a000..$a00f` write | P1 / radar attributes | Separate input snapshot from radar shadow; they cannot share a single RAM byte |
| `$a080` read / write | P2 / watchdog | Redirect reads to input snapshot; writes may remain inert shadow stores |
| `$a100` read / `$a100..$a11f` write | DIP / Namco sound registers | Separate DIP reads from sound shadow; silent integration preserves sequencing |
| `$a130`, `$a140` | Scroll X/Y | Ordinary shadow stores consumed by renderer, not MSX port writes |
| `$a170` | Driver no-op, unexplained WR3 signal | Inert shadow; original electrical purpose unresolved |
| `$a180..$a187` | Explosion, IRQ mask, sound enable, flip, lamps, lockout, coin counter | Shadow writes; adapter handles IRQ ownership and visible flip explicitly |
| I/O port `$00` | Arcade IRQ vector latch | Suppress/translate; do not send it to MSX hardware |

The capture observed 1,385,247 video writes, 70,166 work-RAM writes, 202,457
hardware writes, 360 writes outside the implemented map, and **two attempted ROM
writes**. The latter occur at frames 1016 and 1272: `$040f` increments through a
null pointer into `$0000`; the arcade discards the store. There is no writable-ROM
self-modification demonstrated. Copying the program into RAM would nevertheless
change behavior here. A checked stub must reproduce the discarded write's flag
effects and subsequent ROM read while keeping program RAM unchanged.

The 360 unmapped writes come from startup block clearing beyond `$a187`.
They must remain harmless in the native layout; reserve `$a188..$a1ff` as shadow
padding rather than placing host state there. No CPU I/O reads were observed.
Observed input read sites include startup/attract and gameplay paths, not just
coin handling. The complete per-PC inventory is local in `summary.json`.
Pointers at `$899e` and indexed/indirect input paths require special care: a
direct-load search alone is insufficient. No claim of exhaustiveness is made
for paths outside the bounded replay.

The current stage/player tools independently identify authored table metadata:
`$2505` wall-shape records, `$2529` wall lookup, `$2531..$2539` neighbor masks,
`$253a..$2551` player animation, `$2552` object tiles and `$3000..$30df` first-stage
wall bitmap. These are data addresses, not hook boundaries. Keep tables with the
original program image; do not relocate apparent address-shaped constants without
checking their consumers. Later-stage table coverage remains unresolved.

Observed hardware read instruction starts, after checking local disassembly
against the reported access PCs, are `$045b`, `$0505`, `$0567`, `$0826`, `$082d`,
`$0f6a`, `$1072`, `$16c8`, `$16d5`, `$38df` and `$3904`. The `$0f6a` and `$1072`
reads are indirect. A concrete input allocation is P1/P2/DIP at `$a200..$a202`,
outside the startup clear padding. Redirect direct input operands and the
original input-pointer producers, preserving active-low values; do not redirect
watchdog, radar or sound writes sharing the original read addresses.

## Candidate hooks and contracts

The authored hash inventory contains addresses, lengths and SHA-256 digests,
without original bytes. The capture requires both span endpoints to be observed
instruction starts and verifies the pinned digest. These spans are **candidates**,
not applied patches; the future patcher must also validate the complete program
hash, relocation ownership, continuation address and available stub space.

| Address / span | Contract and proposed adapter |
| --- | --- |
| `$3800` / 3 | Reset-only script entry; SP is repurposed, no normal CALL/RET ABI. Select boot policy before entering; cannot resume from an arbitrary script point |
| `$01f0` / 3 | Interrupt entry before the register save. A jump trampoline must replay displaced saves, preserve all original registers/flags, and retain the interrupt return address |
| `$0468` / 4 | Video/state publication boundary before IY/IX restoration. Displaced restores consume four stack bytes; adapter preserves all state, then continues to `$046c`. Host must own EI/mode changes later in the epilogue |
| `$0c2c` / 3 | Nonreturning main dispatch; intentionally destroys the current stack. Do not enter by CALL expecting a return; renderer context belongs on a separate host stack |
| `$0069` / 3 | Watchdog store before movement. Suppression must preserve A and flags; existing movement harness supplies a separate caller ABI |
| `$16b3` / 4 | Coin-sampling entry, balanced register saves/restores on return. Preserve displaced saves; do not bypass original edge/debounce state |
| `$16c8`, `$16d5`, `$045b` / 3 each | P1, P2 and DIP reads. Operand redirection preserves flags and puts the same active-low input value in A; all other read sites must also be adapted |
| `$38cc` / 2 | Diagnostic IM2 switch. Too short for an in-place three-byte jump; only a checked equal-length substitution or larger separately validated span is eligible |
| `$040f` / 5 | ROM-write suppression plus following read/address setup. Stub must preserve original flags, A, HL result and discarded-write semantics, then continue at `$0414` |

Do not assume every candidate supports CALL: interrupted code has no function
ABI, `$0c2c` resets SP, and `$0468` is in a restore sequence. For normal helper
hooks preserve AF/BC/DE/HL/IX/IY, alternate registers if touched, original stack
contents and interrupt state unless the contract explicitly delegates ownership.
Reject mismatched input or incomplete trace evidence with a nonzero exit and
retain diagnostics. Never apply a partial patch set. Native stub timing, maximum
stack depth and IRQ latency require measurement in #11.

## Concrete MSX mapping proposal

| MSX CPU range | Proposed owner | Change from current renderer |
| --- | --- | --- |
| `$0000..$3fff` | Original program/tables copied to physical RAM page 0, with checked patches | BIOS is switched out after initialization; no BIOS calls while native mapping is active |
| `$4000..$7fff` | Renderer code copied into a dedicated RAM segment | Preserve its linked addresses; keep this segment selected during interrupts |
| `$8000..$bfff` | RAM page 2: original video/work state and hardware/input shadows | Replace the renderer's current asset bank window; original RAM addresses remain valid |
| `$c000..$ffff` | Host buffers, ISR, IM2 table, host stack and scratch | Preserve existing `$c000..$c472`, `$d000..$d100`, `$d2d2` and stack reservations; retire isolated movement RAM `$e000..$efff` only when the full runtime replaces it |

Reserve four 16 KB mapper segments for the original program, renderer code,
original game state and host RAM. The remaining four segments of the 128 KB
minimum provide 64 KB for the active asset working set and staging. Segment IDs
must be allocated/detected at boot rather than assuming every machine owns the
same IDs. More RAM can extend the preload/cache allocation. BIOS ROM at zero
and unchanged native ROM at zero cannot coexist in the same selected page.
At boot, use BIOS slot services while BIOS is still visible to initialize video,
locate RAM pages and copy the program; select page-0/page-2 RAM last. Save slot
state for a controlled exit/reset path. Hardware-specific slot selection needs
an openMSX test on the agreed Panasonic FS-A1WSX configuration.

Preload the required asset working set from the cartridge into the extra mapper
segments during initialization. During rendering, temporarily map an asset
segment into page 2 while native execution is suspended; restore the game-state
segment before resuming original logic. IRQ code must use the fixed renderer/host
pages and committed host-side state throughout that interval. This avoids making
page-1 cartridge-bank trampolines the default resource-access design.

The current cartridge is 1 MB; 128 KB RAM does not imply that every cartridge bank
can be preloaded. Inventory and measure the active stage/HUD working set against
the 64 KB preload allocation, retaining a bounded cartridge refill path or using
more mapper RAM where needed. The current page-2 streaming code must be adapted
to mapper segment selection. Combined switching/copy costs remain to be measured.

Latch outputs use bit 0; sound registers use their hardware nibble semantics.
The acquisition records full write-bus values, so the adapter must apply these
masks rather than confusing raw shadows with decoded hardware state.

Preserve ordinary game writes and compare the 4 KB video/16-byte radar shadows at
publication. Decode map mutations, sprites, radar, score, lives and fuel into the
existing [HUD API](hud.md) and [renderer ownership contract](raster-scroll.md#runtime-integration-contract).
Retain 1:1 asset dimensions and original world coordinates. Hardware shadows do
not automatically perform VDP writes, and hooking one drawing routine does not
capture every mutation. A full 4 KB comparison costs memory reads every logical
tick; dirty tracking or targeted conversion may reduce that cost only after
coverage is established.

For IRQ adaptation, keep the host VDP handler separate, acknowledge VDP status,
schedule native ticks at 16.5 ms, and enter the original game IRQ body through a
checked trampoline. Native IM0/IM2 setup, vector writes and EI/DI windows must be
adapted to the host's raster deadlines. Do not let a nested MSX IRQ reuse the
arcade stack without a measured stack/latency proof. Keep the game IRQ mask as
logical state; writing shadow `$a181` cannot acknowledge the VDP.

The raw budget is 50,688 arcade clocks per logical tick versus approximately
59,062 MSX clocks at 3,579,545 Hz in 16.5 ms. This is an upper bound, not spare
CPU time: it includes arcade waits, while MSX opcode waits, rendering, bank
copies, adapters and interrupts add cost. At 50 Hz, some display refreshes need
two logical ticks. Existing movement-only renderer timing does not establish
full-game feasibility. CPU layout fits; combined runtime performance remains a
measured gate for #11. Prefer selective routine reuse if the retained-address
experiment misses raster deadlines; do not expand operand relocation blindly.

## Initial integration and differential replay

For #11, first implement silent boot/coin/start and the initial single-player
normal stage with original movement, wall collision, enemies, flags, smoke,
score/fuel/lives and restart/death behavior. Limit initial validation to the
existing 3,200-frame replay; later rounds, challenge stages and audio stay outside
that first evidence set. Any required state transition not reached by this replay
needs an additional replay before claiming coverage.

Compare after each completed native game IRQ, at the phase corresponding to the
next arcade pre-IRQ snapshot. Compare semantic fields first: mode/turn bytes
`$8020..$8023`, player descriptor `$8068..$8077`, velocity/fractional fields,
camera `$804c..$8051`, scheduler/animation counters, actor descriptors/pointers,
score/high-score/lives/fuel via the existing `hud_contract.native_values`, all
4 KB video state, work RAM, radar attributes and scroll/flip/sound shadows.
Start with complete memory comparisons and document exclusions for stack,
host-adapter data and values known to be dead; never hide unexplained divergence
by masking a whole region. The current captured frame-2300 HUD is score 0,
high-score 20000, lives display 2, fuel display 30; at 3200 fuel display is 25.
These are sanity observations, not a replacement for byte/state comparisons.

Preserve active-low controls and original coin/start edge handling; feed identical
logical-tick inputs independently of 50/60 Hz presentation. Freeze/publish renderer
state only at the agreed boundary. Measure native tick duration, both one- and
two-tick refreshes, bank-copy overhead, VDP deadlines and audio-muted invariance.
Stop integration on ROM mutation, source/hash mismatch, unexpected IRQ mode,
unmapped writes into host state, unexplained state differences or missed raster
deadlines. Full gameplay, hardware validation and native performance are still
pending; this analysis supplies reproducible boundaries and concrete blockers.

## Local validation

`make test` passed all 157 tests, including three mapper-configuration tests and
six synthetic tests for split loads,
invalid programs, checksum/boundary guards, destination safety and replay
divergence. `git diff --check` passed. The final acquisition in
`references/analysis/issue-10-final check/` also matches reference D across all
1,417 deterministic payloads, exercising output paths containing spaces. ROM
integrity checks passed after each acquisition; tracked `references/` content
consists only of `.gitkeep` files. The memory map and native mapping proposal await
review; no full native cartridge, combined performance result or hardware test is
part of this analysis.

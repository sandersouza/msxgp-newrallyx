# Issue42:744KiB cartridge and768KiB MegaRAM target

Historical scope: this report predates the optional boot F10 feature. Its
original ROM hashes and measurements remain unchanged; see the
[current artifact qualification](f10-invulnerability.md).

Issue: https://github.com/sandersouza/msxgp-newrallyx/issues/42

The current local ASCII8 cartridge is **761,856 bytes (744KiB)**, down from
999,424 bytes (976KiB): **232KiB saved**, leaving24KiB below768KiB. It still
requires64KiB main RAM and128KiB VRAM. The executable MegaRAM image has the
same programmed size; its DOS1 and Disk BASIC loaders now require768KiB
MegaRAM plus64KiB main RAM. **No commit, push or release was published.**

The preceding map/RNG results remain historical in
[map optimization](issue42-map-optimization.md). This continuation preserves
their rules and map cache while reducing transfers and the cold opening.

## Mechanisms and ownership

`scripts/compact_transfer.py` specializes each compiled packet's fixed length.
The resident head contains191 OUTI instructions and a JP into a64-OUTI tail in
main Page0. Calls enter the appropriate suffix. Long transfers returnB=0;
short suffixes retain the original B decrement. HL advances by exactlyN,
C/DE/IX/IY/SP/IFF survive, and AF is scratch where the old long helper allowed
it. Ordered control/data source events and final HL/B are independently checked
for all4,384 references. No source pixels, destination order or write spacing
change. Known post-copy HL permits redundant loads to disappear or become
LD H,n/LD L,n. A short CALL costs29 more cycles than inline OUTI; it is selected
only against savings earned elsewhere in the same packet. No packet has a
negative modeled gain. Unique code falls331,664→256,788 bytes.

The real linked kernel was measured for all lengths2..255, both IFF states and
both VRAM table sets:1,016 cases compare all128KiB VRAM and the register/stack
contract, with zero strict VDP access callbacks. The isolated measurement
disables VDP IRQ generation; whole-game IRQ/ABI observers run separately.
The measured MSX OUTI cost is19 cycles. Both old/new models were corrected
from18; equalN terms cancel, preserving optimization decisions and ROM bytes.
The test drains the VDP write pipeline before inspecting VRAM; an immediate
debugger read after RET can otherwise observe a pending last byte.

`scripts/compact_boot_atlas.py` encodes the same71 selected SCREEN5 states as
8x8 tiles with uniform, two-color, four-color or literal lossless records.
Current data:1,391 canonical tiles,1,600 slots including six repeated strips,
16,703 unique tile bytes,4,800 pointer bytes,1,152 LUT bytes and13,720 command
bytes. Hidden-page delta streams use skip/run commands. Repeated strips permit
rectangular HMMM transfers instead of one command per identical tile. Status
overlay cells are explicitly redrawn on page reuse. Host reconstruction checks
all frames independently before allocation.

The boot-only worker occupies existing main Page03000..3FFF navigation RAM,
installed beneath the existing initial HMMV clear; first map construction
overwrites it. State/command scratch isD5B0..D5D4, bitmapD600..D6FF, cleared
before native game/audio. Atlas VRAM pages2/3 remain separate from display/back
pages0/1. Completed GPU writes precede publication; R15 returns0, IX/IY survive,
and boot returnsEI. Prefetch consumes existing hold time with one refresh kept
in reserve. There is no extra RAM segment or active-frame decoder. The public
contract is synchronized in `src/screen4/modules/contracts.json`.

Allocation puts code, tile records, maps and descriptors into **declared** free
ranges. It does not infer reusable space from FF runs. Navigation, eight map
halves and hot map access remain unchanged. Main workers end07C0<07E0;
resident code/palette ends7FE1<8000. These narrow margins have linker assertions.
Native logic, audio and UI owners71/73/121 are byte-identical16KiB blocks in
the976KiB baseline,744KiB cartridge and MegaRAM image.

Rejected approaches are retained as learning: per-tile HMMM plus lazy decoding
missed opening deadlines; prefetch alone still missed dense late states. Repeat
strips/run commands fixed the problem. A skip-block temporary originally
overwrote run length; the synthetic sparse-row test now covers that interaction.
No slower experimental boot is exported.

## Performance and fidelity evidence

Reference units are guest elapsed seconds×3,579,545Hz, including IRQ/VDP waits.
They are not mixed-clock CPU instruction counts. Refresh is59.922743Hz,
separate from gameplay/presentation. HUD, production PSG, complete cars and
real sprite limits remain enabled. The same controlled1234hex initializer seed,
input policy and native populations are used on both ROMs.

| WSX64 enemies | Presented FPS before→after | Mean work cycles before→after | P95 before→after | Maximum before→after |
| --- | ---: | ---: | ---: | ---: |
|3|29.966→30.029|75,584.7→75,371.3|110,912.3→108,438.7|127,613.3→125,776.3|
|5|28.872→28.872|87,902.2→87,663.0|129,908.7→128,821.0|172,802→171,045|
|6|28.701→28.817|90,221.5→89,690.1|133,091.7→131,894|171,082→170,165|

These whole-route aggregates do **not** imply identical trajectories or a
universal speedup. Faster scheduling changes a few elapsed-tick counts, and
input switches tied to presentation indices then occur at different physical
times. Full state/tick/input/PSG records match at277/356,356/356 and191/356
presentation indices, respectively. Restricting to matching active states gives
158/238/97 paired samples. Their mean/P95/maximum work do not regress; the
six-enemy paired P95 is unchanged. Ten three-enemy paired samples have longer
work spans, maximum2,738.334 cycles (0.765ms), with no additional refresh and
period differences within6 reference cycles. They remain in the report.

Causal evidence comes from nonnegative per-packet budgets and the real kernel
measurement. Separately,256 consecutive native ticks under held keyboard input
match the previous ROM, new ROM and MegaRAM byte-for-byte for original
E000..E2FF RAM,14 PSG registers and game/death/round state. This avoids treating
different presentation indices as different game rules. It is a controlled
first-round fixture, not a complete-course acceptance test. Cartridge and
MegaRAM presentation traces match each other for all356 rows at each population.

Ten current profiles cover both formats on WSX64 at3/5/6 enemies and the
cartridge on Sony64 base-Z80, WSX128, ST256 and GT512. Each includes actual
CPU/cache selection and an uninstrumented control. All four additional matched
baseline/current platform pairs have nonregressing aggregate mean/P95/maximum;
WSX128/ST/GT cadence is unchanged within observation jitter. A profiler fix
checks actual native entry bytes: with independent8KiB windows, a native lower
half alone cannot identify the upper owner. Numeric PC aliases must not become
false native calls.

All eight cartridge and five MegaRAM session scenarios pass independent
world/HUD/car checks. Dedicated checks cover16,000-refresh steering, rocks,
speed, sprites and PCM/PSG. All71 opening states retain exact pixels and
publication ticks; maximum timing error is0.001118ms. Fourteen skip/key cases
pass with maximum15.944ms latency. Natural start delays/repeats still reproduce
the original placement model and variation.482 general and94 component tests
pass, with one component skipped. Frozen module-layout verification passes;
that source-organization check is distinct from this functional renderer change.

The current [cycle ledger](measurements/timing/cycle-ledger.json) and
[workbook](cycle-budget.xlsx) bind these measurements to the744KiB hash.
The prior976KiB workbook/ledger retain their original identities in the archive.
Inclusive parents contain child costs; never add them together. The5,000-cycle
VBlank reserve remains a planning assumption, not a measured hardware limit.

## MegaRAM capacity and512KiB standard mapper feasibility

The loader derives its capacity tier from programmed8KiB pages. Current93 pages
round to768KiB (96 banks); disk decoding pads to94 banks. Probing banks0/64/95
detects a512KiB alias. An arithmetic midpoint48 would incorrectly miss it:
bank95 aliases31, independent of0/48. Probe tags are restored before any load.
The [openMSX MegaRAM implementation](https://github.com/openMSX/openMSX/blob/master/src/memory/MSXMegaRam.cc)
supports non-power-of-two8KiB capacity multiples; validation uses a ROM-free
768KiB extension rather than assuming1MiB hardware. DOS1/BASIC, expanded-slot
startup and exact loaded-image comparison pass.512KiB, missing input, wrong
page count and corrupt distance are rejected with the tested memory unchanged.
This establishes emulator behavior; no particular physical MegaRAM model or
768KiB cartridge board has been qualified.

**512KiB standard main RAM mapper is not supported by this candidate.** The
retained standard-mapper executable still needs4MiB. ZIP size187,548 bytes does
not establish resident-memory use: the current game image is744KiB, and main
work RAM is additional. The two hot source/code windows use independent8KiB
banking; a standard mapper changes16KiB pages. Current unique transfer code is
256,788 bytes and live paired source metadata/pixels160,041 bytes, before
native/audio/UI, maps, boot, alignment and main work RAM. The present744KiB
layout cannot simply be loaded into512KiB.

A smaller RAM edition would need a separate16KiB mapping backend plus a
bounded resident working set, likely reusing cold phase resources or streaming
from disk at transitions. It must account for DOS/loader lifetime, compressed
storage, decoded resources, work RAM and audio/transition deadlines. Further
code/dictionary compression is only useful if its decode cost is cold or a
measured hot-path benefit. This is a feasibility direction, not an implemented
loader, a proven512KiB fit or permission to slow gameplay. No graphics/audio
removal or weaker enemy/HUD update policy was used to reach744KiB.

## Local artifacts and reproduction

| Artifact | SHA-256 |
| --- | --- |
|`dist/newrallyx.rom`|`b39e0c7f520872174e9a89cc46ddf4e1957179bc70ac3326c6450420866a878c`|
|MegaRAM761,856-byte image|`f149f34816d99db21e46b4a2b3a6d17d769ffd49c515b906613131d0c5f255fb`|
|`dist/compact/megaram/newrallyx-megaram.zip`|`1372ca645f3ac5ba59b406f2f6e73cc00d221c52c2984c333d042070bd68ef66`|
|`dist/disk/newrallyx-disk.zip`|`1be5d140e9f89032adfd9954ddbbe97f794c5eade663e3039440ddaa4400bc8f`|

Both ZIP CRCs pass. The earlier4MiB standard-mapper executable passes DOS1 and
BASIC again; its game image is unchanged. Its ZIP changes because the manifest
now identifies the744KiB companion cartridge and the source overlay is current;
the original package builder also retains ZIP file timestamps. All builds use supplied ignored
arcade inputs. Synthetic tests contain no original bytes. Source hashes,
component results, loader cases and detailed timing comparisons are in
[the qualification record](measurements/cartridge/issue42-768-qualified.json).
These are automated/openMSX results, not physical-hardware, PAL50, subjective
listening or owner acceptance. Release publication still requires approval.

```sh
make build
make build-megaram
make build-disk
.venv/bin/python -B scripts/exact_transfer_verify.py
.venv/bin/python -B scripts/compact_game_verify.py --mode rom
.venv/bin/python -B scripts/compact_game_verify.py --mode dos --size 768
.venv/bin/python -B scripts/compact_game_verify.py --mode basic --size 768
```

For a matched baseline, build `scripts/compact_game_build.py --baseline-renderer`, freeze only
its top-level ROM/symbol/resource files into the ignored
`references/build/game-issue42-976-baseline`, then restore with `make build`.
The diagnostic must reproduce230c3883…; default builds reproduceb39e0c7f….
`--baseline-maps` still reproduces the earlier984KiB fixture.

Run `session_profile.py --bundle <bundle>` with `NRX_PROFILE_SEED=0x1234`;
use `(NRX_PROFILE_ROUND,NRX_PROFILE_ENEMIES)` of `(5,3)`, `(10,5)`, `(13,6)`.
Repeat both formats on WSX64 and the cartridge on Sony64/WSX128/ST256/GT512;
set `NRX_REFERENCE_MACHINE` and `NRX_REFERENCE_RAM_KIB` explicitly. Run the
eight/five `session_verify.py` scenarios, component/boot/skip/RNG probes and
loader cases listed in the qualification record. Then run:

```sh
.venv/bin/python -B scripts/compact_tick_verify.py
.venv/bin/python -B scripts/issue42_rng_verify.py --output references/build/issue42-744-rng.json
.venv/bin/python -B scripts/compact_768_report.py
make timing-workbook TURBO=1 TIMING_LEDGER=references/validation/issue42-768/cycle-ledger-enriched.json
```

Raw builds, traces, PCM and session captures are disposable after consolidation;
retain compact results and historical workbooks, not experiment archives.

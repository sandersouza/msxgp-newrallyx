# Issue42: smaller and faster cold map constructors

Issue: https://github.com/sandersouza/msxgp-newrallyx/issues/42

The owner authorized further map optimization while preserving graphics, audio,
gameplay, performance,64 KiB cartridge operation and both executable paths.
**Local candidate only: no commit, push or release publication.** Publication
still requires owner approval. The preceding RNG correction remains enabled.

## Mechanism and net size

The eight expanded16 KiB map halves retain exactly the same tile IDs. Their
1,003 shared constructors still write eight reverse-order words with PUSH HL:
the first word always loads HL; a repeated word reuses it; a one-byte change
uses LD H,n or LD L,n. The tail JP relocation now uses the declared constructor
length, with a terminal-opcode assertion, instead of assuming35 bytes.

Contiguous1024x3-byte descriptor tables now consume declared free ranges before
reserving new pages. Constructor placement and boot-replay packing follow.
No hole is inferred from a run of zero/FF bytes. The runtime dispatch, number
of word stores, map access during scrolling, mapper-write count, RAM/VRAM,
saved-SP scratch and DI/display-off ownership remain unchanged. No additional
branch, wrapper, buffer or active-frame work is introduced. Constructors use
only LD HL/LD H/LD L/PUSH HL/JP; BC/DE/flags/IX/IY are unchanged by these bodies.
SP and main Page0 are restored before any CALL/RET or interrupt enable.

| Storage | Before | Candidate |
| --- | ---: | ---: |
| Programmed ASCII8/MegaRAM image | 1,007,616 bytes /123 pages | **999,424 bytes /122 pages (976 KiB)** |
| Constructor bodies | 35,105 bytes | **26,084 bytes** |
| Map descriptors | 24,576 bytes | 24,576 bytes |
| Boot replay encoding after repacking | 191,345 bytes /531 chains | 191,941 bytes /574 chains |

The net cartridge reduction is **8,192 bytes**, not the9,021 live constructor
bytes. Remaining padding and boot repacking account for the difference. The
image is48 KiB below1 MiB. MegaRAM ZIP compression grows slightly because the
packed byte layout changes; ZIP size is not the programmed-ROM size.

Removing only duplicate word loads saved live bytes without dropping a ROM
page. Repacking the contiguous tables was also necessary. Per-chunk run-length
descriptors were rejected after counting the actual corpus: a four-byte run
entry would increase descriptor storage to31,808 bytes. Rebuilding tiles during
scrolling was not introduced; it would add recurring work to solve a storage
problem. Further cold procedural generation remains a separately measured option.

## Measured behavior

Baseline is the RNG-corrected984 KiB cartridge, SHA-256
`d1a1f9cf3fa98940acf2d234b127f224da79f5aaed37fc19e999718134e7c23f`.
The diagnostic `--baseline-maps` mode independently reproduces that exact hash
from the current sources/contributor inputs; it cannot publish the default ROM.

- Every map half is checked byte-for-byte on the host and through read-only
  observations of actual physical mapper RAM. All eight logical map owners,
  IX/IY preservation and the callers' observed IFF=0 are covered. Current game
  callers prepare maps with display/VDP IRQ off; this is not an IFF=1/NMI test.
- Each16 KiB copy formerly cost304,540 reference cycles. The candidate costs
  **270,173..295,424 cycles** across the eight map halves: approximately
  **3.0%..11.3% less copy work**, with no slower half.
- Thirteen matched complete loads, native rounds2..14 and all four layouts:
  mean5,206,094 →5,169,337 cycles; P95/maximum5,276,246 →5,216,514.
  Mean improves about10.27 ms; maximum improves about16.69 ms.
- Video synchronization is explicit: eight transitions save a refresh and
  five use the same refresh count. Four raw inclusive durations are11 or18
  cycles longer (at most5.03 microseconds), within the existing33-cycle VDP
  polling loop. Beam observations show no additional refresh; self work falls
  in all thirteen cases. These raw longer cases are retained in the report,
  rather than represented as universal duration improvements.
- Active three/five/six-enemy workloads remain about **29.966 /28.872 /28.701
  presented FPS**, at **59.922743 Hz refresh**. For each population,356 camera,
  enemy, tick, state-classification and14-register PSG records match baseline,
  ASCII8 and MegaRAM. Mean/P95/max work are unchanged within0.01 reference
  cycle, and cadence differences are below0.00002 FPS. **No gameplay FPS
  increase is claimed.** Existing overloads remain visible.
- Boot retains71 states, software publication ticks, pixel checks, initial
  clear and publication phase. Recorded total duration differs by one reference
  cycle; title/logo/footer costs are unchanged within observation precision.

Cycles mean elapsed guest seconds times3,579,545 Hz, including IRQ/VDP waits;
they are not mixed-clock instruction counts. Complete-load inclusive costs
contain their children: do not add them to copy/video/self measurements.

## Qualification and artifacts

Ten current profiles cover ASCII8/MegaRAM WSX64 with3/5/6 enemies, ASCII8
WSX128, Sony64 base-Z80 fallback, ST256 and GT512. Eight cartridge scenarios
and five MegaRAM scenarios pass their graphics/HUD/car oracle. Natural and
repeated Start timing still gives original-valid varied flags. Dedicated checks
cover16,000-refresh keyboard steering, PCM/PSG, rocks, speed, boot/skip and
sprites. MegaRAM DOS1/BASIC startup, expanded slots,512 KiB capacity rejection
and corrupt backreference rejection pass. The earlier4 MiB system-mapper
executable passes DOS1/BASIC again; its game image is byte-identical to the
preceding candidate.478 general and94 component tests pass, with one component
test skipped. Module-layout verification keeps its historical configuration.

| Local artifact | SHA-256 |
| --- | --- |
| `dist/newrallyx.rom` | `230c388345a44226ce6536e17204d37a96714b0f03c126d9e072115a394274bc` |
| MegaRAM999,424-byte programmed image | `992d12f6b99303194f8d3b2f8df910b0d0b52b6d1c21f02e062c46c689750472` |
| `dist/compact/megaram/newrallyx-megaram.zip` | `ac55855084fe8881121209f91a3b3920634ef0d456fe08c414d4bf645511dfac` |
| `dist/disk/newrallyx-disk.zip` | `3753e3360d71b602a0ab55da2575cf84738d541bc6384a2fe73ed8f574823550` |

The cartridge needs64 KiB main RAM; the compact executable needs1 MiB MegaRAM
plus64 KiB main RAM; the earlier executable still needs4 MiB main mapper RAM.
All require the project's MSX2+/128 KiB VRAM target. These are automated/
openMSX results, not physical-hardware, PAL50 or subjective listening acceptance.

Exact-hash evidence is in `docs/measurements/cartridge/issue42-map-qualified.json`.
The current timing ledger/workbook use the new cartridge hash. Earlier workbooks
and their ledgers retain their own ROM hashes in the timing archive.

## Reproduction

With supplied arcade inputs, build the diagnostic baseline first, copy its
top-level ROM/symbol/resource files into ignored
`references/build/game-issue42-map-baseline`, then restore the optimized build:

```sh
make build
.venv/bin/python -B scripts/compact_game_build.py --baseline-maps
# Freeze the diagnostic bundle as described above before restoring normal output.
make build
make build-megaram
make build-disk
.venv/bin/python -B scripts/issue42_rng_verify.py --output docs/measurements/cartridge/issue42-map-rng.json
NRX_PROFILE_SEED=0x1234 .venv/bin/python -B src/toolchain/screen4/session_profile.py --bundle references/build/game-compact-runtime
NRX_VERIFY_SEED=0x1234 .venv/bin/python -B src/toolchain/screen4/session_verify.py --bundle references/build/game-compact-runtime --scenario integration --headless --contracts
.venv/bin/python -B scripts/issue42_rng_report.py --maps
make timing-workbook TURBO=1 TIMING_LEDGER=references/validation/issue42-map/cycle-ledger-enriched.json
```

The report requires the baseline/current3/5/6 profiles with initializer seed
1234 hex, the four additional CPU/RAM profiles, both backends' scenarios,
component and loader checks. F5/death/contact/seed injections remain explicitly
identified fixtures, not natural full-course acceptance. The baseline/default
build logs, baseline reproduction metadata and test log are retained only until
their compact results are summarized. Raw generated maps, ROMs, traces, PCM and
emulator sessions are disposable ignored data; contributor inputs are preserved.

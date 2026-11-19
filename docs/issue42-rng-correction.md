# Issue42: corrected global RNG lifecycle

Issue: https://github.com/sandersouza/msxgp-newrallyx/issues/42

This report preserves the984 KiB RNG-correction candidate. The subsequent
[976 KiB map-optimization candidate](issue42-map-optimization.md) has separate
exact-hash evidence and retains this correction.

The owner authorized correction/optimization after the original-code research.
This is a **local candidate**, with no commit, push or release publication.
Publication still requires owner approval. The original-code findings and the
accepted-build diagnostic remain in [the research report](issue42-arcade-maze-flags.md).

## Change and ownership

The first-board repetition came from two independent resets: copying a captured
4 KiB player image over the RNG word and explicitly assigning seed1 before the
native first-round initializer. The renderer was not the cause.

- Boot now selects the RNG word from the contributor program's original3A52
  table using default DSW=C3: service off, easy, one coin/credit. No host random
  source, refresh-counter seed or substitute PRNG is introduced.
- New-game restoration copies E002..EFFF, preserving the machine-wide RNG at
  E000..E001. Native player-turn snapshots already exclude that word.
- The fixed-seed assignment becomes six NOP bytes in its existing cold slot.
  Keeping the slot preserves native entry addresses and branch distances.
- Foreground UI catches up original8F24 once per elapsed refresh, reusing
  input_tick until gameplay video initialization resets that clock. There is
  no additional persistent RAM, IRQ work, active-frame call or bank traffic in
  the renderer. Existing gameplay RNG advancement and pause policy are retained.
- Terrain maps, drawing caches, graphics, sound assets, native placement/rejection
  rules, scoring, collision and difficulty routines are retained.

The UI catch-up loop temporarily owns native Page2, clobbers AF/BC/DE/HL,
preserves IX/IY/IFF and uses two loop-scratch stack bytes plus eight for the
original PRNG call and saved pairs (excluding the unchanged IRQ envelope). IRQ never changes
that mapping or RNG state. Full wraparound of the16-bit clock is handled by
modular subtraction. The loop runs only during blocking UI, not active drawing.
The inline contracts, module registry and module guide describe this lifetime.

## Exact local artifacts

| Artifact | Size / requirements | SHA-256 |
| --- | --- | --- |
| `dist/newrallyx.rom` | **1,007,616 bytes =984 KiB**, ASCII8,64 KiB main RAM | `d1a1f9cf3fa98940acf2d234b127f224da79f5aaed37fc19e999718134e7c23f` |
| MegaRAM programmed image | **1,007,616 bytes**,1 MiB MegaRAM plus64 KiB main RAM | `5909b0455c76f0c1b0df2441579b8b6fb4ef443e0189723cf8e5806abb3fdd3e` |
| `dist/compact/megaram/newrallyx-megaram.zip` | MSX-DOS1 / Disk BASIC,276,508 compressed bytes | `010c1d406b9d8444997f6deae08008f6cb81f095f5cc33a02d6870a1ff941e47` |
| `dist/disk/newrallyx-disk.zip` | Earlier system-mapper executable retained;4 MiB main mapper,339,739 compressed bytes | `72b3c35224c97a43dd0549de53659a45e8751f0e2f558f8f824640a8cad8d5ea` |

There is **no programmed ROM-size saving in this correction**, and no extra
ROM page. Both programmed images remain40 KiB below1 MiB. ZIP size is not a
cartridge saving. The cartridge's64 KiB requirement must not be confused with
the earlier executable's4 MiB mapper requirement.

## Natural variation and lifecycle

WSX/openMSX,64 KiB main RAM, real keyboard credit/start, HUD/audio and hardware
sprite limits enabled. Natural runs have read-only observers.

| Start delay | RNG before native preparation, decimal | Result |
| --- | --- | --- |
| 0 seconds | 18640 | First original-valid flag set |
| 0.5 seconds | 39388 | Another original-valid flag set |
| 2 seconds | 58885 | A third original-valid flag set |
| Repeat0 seconds | 18640 | Exactly reproduces the first set |

Every observed foreground-menu RNG advance matches the independently modeled
original function. Boot starts at the original default-DIP seed, and the RNG
word survives the new-game copy and retired reset slot. All placements match
the original flag/rock model and pass the independent world/HUD/complete-car
oracle. A separately labeled injected1234-hex seed also passes that comparison.
Not every distinct timing must yield unique flags; original rejection sampling
can converge to the same accepted candidates.

Read-only lifecycle observers additionally cover new games, thirteen board loads,
all four normal layouts, attract exit/restart, second-player first-board setup
and restoration of an existing player's board. Restoration retains exactly the
same RNG word; the global stream is not swapped with player state. The two-player,
flag-contact and F5 transition fixtures include declared guest-state injections;
they are not natural full-course/death acceptance. The earlier64-case original
matrix remains evidence of the unmodified native initializer and logical board.

## Matched performance, audio and compatibility

Performance fixtures explicitly supply the same original initializer RNG
1234 hex before each board in the accepted ASCII8 baseline, candidate ASCII8
and candidate MegaRAM images. This separates intentional first-board variation
from performance. No guest program bytes are patched. Each profile has a
matching run without routine breakpoints; camera/tick/control timing checks pass.

| Native enemies | Presented FPS, baseline → candidate | Mean / P95 / max work, candidate reference cycles |
| --- | --- | --- |
| 3 | 29.965998 →29.965998 | 75,584.699 /110,912.333 /127,613.333 |
| 5 | 28.872420 →28.872420 | 87,902.158 /129,908.667 /172,802.000 |
| 6 | 28.700850 →28.700855 | 90,221.457 /133,091.667 /171,082.000 |

All356 records per population match camera, enemy packets, elapsed ticks,
active/death classification and all14 PSG registers across all three images.
Mean/P95/maximum work is unchanged within0.01 reference cycle; presentation
differences are below0.00002 FPS. **No active-play speedup is claimed.** Existing
overloads and death intervals are retained and reported. Refresh is59.922743 Hz,
distinct from presented gameplay FPS; figures are elapsed guest time times
3,579,545 Hz, not mixed-clock instruction counts.

Thirteen matched cold loads through native rounds2..14 also show no regression:
maximum5,276,246 reference cycles in both builds. The first load is520 cycles
shorter; the other twelve differ only by measurement rounding. Inclusive cold
times contain their children, IRQs, waits, display and audio setup; do not add
them to child costs. A tiny cold difference is not a rendering optimization.

Qualification includes the ten-profile ASCII8/MegaRAM matrix (WSX64 three/five/
six enemies, ASCII8 WSX128, Sony64 base-Z80 fallback, ST256 and GT512), eight
cartridge scenarios, five MegaRAM scenarios,16,000-refresh keyboard steering,
audio/PCM, speed, rocks, boot/skip and sprite checks. MegaRAM audio/PCM runs
through its actual DOS filesystem loader. Loader checks cover DOS1, Disk BASIC,
expanded slots,512 KiB rejection and corrupt backreference rejection. Earlier
4 MiB system-mapper DOS1 and BASIC paths also boot and run the candidate logic.

These are automated/emulator results. Physical hardware, PAL50 and subjective
listening/perception remain unqualified. They do not replace owner acceptance.
Detailed exact-hash results: `docs/measurements/cartridge/issue42-qualified-candidate.json`.
The current timing ledger/workbook use the candidate hash; the prior workbook
and original source ledger are archived with their original hashes.

## Reproduction and scope

```sh
make build
.venv/bin/python -B scripts/issue42_rng_verify.py
make build-megaram
make build-disk
NRX_PROFILE_SEED=0x1234 .venv/bin/python -B src/toolchain/screen4/session_profile.py --bundle references/build/game-compact-runtime
# Repeat with NRX_PROFILE_ROUND/NRX_PROFILE_ENEMIES=10/5 and13/6 and the MegaRAM bundle;
# use NRX_REFERENCE_MACHINE / NRX_REFERENCE_RAM_KIB for the CPU matrix.
NRX_VERIFY_SEED=0x1234 .venv/bin/python -B src/toolchain/screen4/session_verify.py --bundle references/build/game-compact-runtime --scenario integration --headless --contracts
.venv/bin/python -B scripts/issue42_rng_report.py
make timing-workbook TURBO=1 TIMING_LEDGER=references/validation/issue42/cycle-ledger-enriched.json
```

The report also requires the documented lifecycle/component/loader cases and
an accepted-b568 build in ignored `references/build/game-issue42-baseline`.
Recreate that baseline from its accepted source overlay with contributor ROMs;
never relabel a candidate as the baseline. Raw traces, PCM, snapshots, assembly
and ROM fixtures are disposable ignored data; durable reports retain hashes,
counts, scope and reproduction commands.

Further map-storage optimization remains separate. Generating terrain on each
scroll would introduce new recurring work without fixing the confirmed bug.
Cold generation might save stored map constructors, but its complete layout,
code/table size and transition cost still need measurement. Keep the existing
cache unless a separately authorized candidate meets every preservation gate.

# Issue 41: complete compact game and MegaRAM loader

The complete default game occupies **1,007,616 programmed bytes**: 123 pages
of 8 KiB, **40,960 bytes below 1 MiB**. It saves 1,040,384 bytes (50.8%) against
the accepted 2,048,000-byte cartridge. This supersedes the earlier component-only
experiment. A 1 MiB cartridge/MegaRAM is viable; 512 KiB is not demonstrated.
This is a measured feasible size, not a proof of the theoretical minimum.

## Deliveries

| Artifact | Requirement / identity |
| --- | --- |
| `dist/newrallyx.rom` | ASCII8; MSX2+/V9958, **64 KiB main RAM**, 128 KiB VRAM |
| Cartridge SHA-256 | `b5684933f5dcae72d5552b51cbca64a28458fa980795334d6491ce3f55c66e4a` |
| `dist/compact/megaram/newrallyx-megaram.zip` | MSX-DOS1/Disk BASIC; **1 MiB MegaRAM plus 64 KiB main RAM** |
| MegaRAM image SHA-256 | `dbdfb5e2bcf9602f2809bc3e0f2035eecc5d2c3d11d25638a14f5cfe5fd6e8e8` |
| MegaRAM data | 405,941 bytes; 1,007,616 live bytes, 1,015,808 including final page padding |
| Preserved `dist/disk/newrallyx-disk.zip` | Earlier **4 MiB standard system-mapper** executable, without MegaRAM |

The old executable's COM/BIN/BAS/DAT reproduce byte-for-byte; its published
ZIP is unchanged. It is a separate legacy delivery. New packages include no
BIOS, operating system or contributor arcade input files. Expanded main RAM
still selects the existing faster cache; supported Panasonic machines retain
CPU acceleration. No graphics, sound assets, game rules or input policy were
reduced.

Normal `make build` creates an ignored 16 KiB source link, then publishes the
complete compact game at the normal path with matching metadata. `make run`
uses mapper metadata only when the image hash matches. `MAPPER` still selects
emulated RAM, never cartridge bytes or names. Named diagnostic configurations
retain their prior layout; the compact backend is the default playable build.

## Allocation and mechanism

The arcade CPU uses dedicated tile/sprite hardware. This port spends ROM on
phase-specific source tables, precompiled VRAM transfers, repeated data and
bank reservations to avoid recurring rendering work. Arcade program size alone
also excludes separate graphics resources. The large image predominantly held
generated presentation data/code, rather than additional game rules.

| Final owner | Programmed bytes |
| --- | ---: |
| 15 raw 16 KiB resident/native/audio/UI/terrain owners | 245,760 |
| 64 phase/HUD and 32 edge records, paired in 8 KiB pages | 393,216 |
| 2,806 exact pooled transfer bodies, 41 pages | 335,872 |
| Eight map descriptor tables, four pages | 32,768 |
| **Total** | **1,007,616** |

Constructors, replay, the name-ring worker and binding code also occupy audited
gaps inside these owners. Gaps come from declared fields/reservations, never
scanning for zero/FF bytes. Initial maps/edges superseded by the full session
are retired; unexpected logical IDs trap. Initial terrain and all four active
terrain banks remain. Uniform metadata is shared only after exact equality
checks. Every source glyph and ordered name/guard store survives.

Lower 8000..9FFF holds phase data; upper A000..BFFF selects transfer code.
Raw owners map as a pair. `Compact_Map16` preserves registers/flags/IFF, using
eight stack bytes including CALL. Hot known pairs use LD-only immediates,
preserving logical A/flags. Phase binding restores its lower window across
nested calls and tail-enters its continuation. No extra RAM segment or frame
buffer exists. Main-Page0 workers end at 071E, below state at 07E0;
`Compact_Base` owns 07E6. Foreground-only radar code owns C110..C24F, installed
once; its source-high operand changes with phase binding, never in the IRQ.

Eight maps use 1,003 unique sixteen-byte chunks. Each 35-byte constructor is
eight reverse LD-HL/PUSH-HL pairs followed by a resident JP. Display/VDP IRQ
source are off; DI protects the temporary Page0 data stack. SP reaches 0000
and is restored from C100..C101 **before any CALL/RET**. Main Page0, IX/IY and
incoming IFF are restored; AF/BC/DE/HL are scratch. This scratch is disjoint
from radar/native state. Host reconstruction checks the final linked image;
guest observers compare all 16,384 destination bytes and caller ownership.
Observed cold callers have IFF=0; enabled-IFF ordering has static review, not
natural enabled-caller coverage.

The MegaRAM loader discovers primary/expanded slots, restores aliased probe
bytes, and rejects insufficient capacity. It decompresses directly into the
chip using a 512-byte disk buffer, bounded output/match distance and block
checksums. Every DOS read/close/error path restores the original Page2 RAM
slot. CHGMOD runs before MegaRAM owns Page1. Takeover selects resident pages
and read-only banking. Guest code performs all later switching; the debugger
never uploads the image.

## Measured preservation

openMSX 21.0, WSX with **64 KiB main RAM**, actual factory CPU scopes, real VDP
timing, complete HUD/audio and hardware sprite limits. Refresh is
**59.922743 Hz**, distinct from gameplay presentation. Each workload records
356 intervals, with 237/238 active intervals after excluding death/stopped
endpoints. Native rounds 5/10/13 supply three/five/six enemies through F5.

| Enemies | Baseline / compact FPS | Mean work, before → after | P95 work, before → after | Maximum work, before → after |
| ---: | --- | ---: | ---: | ---: |
| 3 | 29.966 / 29.966 | 75,838 → 75,557 | 111,036 → 110,912 | 127,439 → 127,315 |
| 5 | 28.872 / 28.872 | 88,177 → 87,868 | 130,172 → 129,909 | 173,091 → 173,064 |
| 6 | 28.701 / 28.701 | 90,412 → 90,136 | 133,388 → 133,092 | 170,968 → 170,803 |

Costs are elapsed seconds times 3,579,545 reference Hz, including waits;
they are not mixed-clock R800 instruction counts. Both compact formats agree
within observation jitter. All 356 rows per population match baseline camera,
enemy descriptors, elapsed ticks, active flags and **all 14 PSG registers**.
Each profile also matches its run without routine breakpoints. Existing tails
remain visible; this does not claim sustained 30 FPS in every scene.

Map-copy time falls from **376,939 to 304,540 reference cycles** (19.2%), measured
at entry and exact return. All eight maps pass in both compact formats. The
workbook records inclusive/self costs, calls/frame, waits, raster endpoints
and drawing margin. Never add inclusive parents and children. The 5,000-cycle
VBlank reserve remains an unverified planning assumption.

Additional checks:

- Original startup pixels/timeline, complete title/footer and 14 keyboard-skip
  cases; no new deadline, silence or VRAM-timing violation.
- All four layouts through round 14, challenge, attract, two-player, flags,
  all-phase radar/blink, smoke and controls. MegaRAM runs include complete
  integration, two-player, flags, radar and controls after real DOS loading.
- Real 16,000-active-refresh steering/rollover/smoke stress, with 3,288 later
  distinct poses; original-ROM speed/rebound fixtures; complete car/SAT/color
  fixtures. Three-voice PSG/music/effects, engine pitch/direction and clear
  sequence fixtures accompany the game PSG-state comparisons.
- Sony HB-F1XDJ 64 KiB fallback, WSX 64/128 and stock ST 256/GT 512 KiB
  mapper/CPU/ABI checks. The current workbook has ten scoped profiles;
  older larger matrices retain their original hashes.
- DOS1 and Disk BASIC loading, primary and expanded slot 1-2, whole-image
  equality before takeover and immutability after gameplay. 512 KiB capacity,
  missing file, damaged count and invalid match reject safely; these early
  rejection cases leave the chip unchanged.

## Rejected approaches and stability

The earlier 1,040,384-byte non-bootable component allocation remains historical
in `issue41-compact-backend.md`. LZ maps cost about 740,000 cycles and were
rejected for cold latency. Generic hot mapper calls and a missed duplicate
turbo loop regressed active timing; immediate pairs and shared name loads
removed those regressions. Individual generic pair switches still cost more
than one old mapper store; overall mean/P95/maximum above are the acceptance
evidence, rather than a claim that every instruction path improved.

Long steering exposed the existing Z80 LD A,I interrupt P/V race: an IRQ at
that instruction could return the CPU scope with IFF disabled. The compact
build conditionally repeats a false sample before saving it. This relies on
the runtime's **sole periodic, acknowledged VDP IRQ**: an enabled false sample
has just serviced VBlank, leaving ample time for the second read. Initially
disabled callers cannot receive that IRQ. This is not a generic multi-source
or NMI primitive. Five bytes and ten common-path base cycles are included in
final timing. The rejected `37fd2f85…` image is superseded by the hashes above.

## Reproduction and limits

Contributor arcade/BIOS/DOS inputs remain required; tools download none.
The final suite passes 476 general and 94 component tests, with one component
skip. The preserved module extraction passes its complete ROM/symbol gate.

```sh
make build
make build-megaram
make test
make verify-module-layout
.venv/bin/python -B scripts/compact_game_verify.py --mode rom
make verify-megaram
.venv/bin/python -B src/toolchain/screen4/session_verify.py --bundle references/build/game-compact-runtime --headless --scenario integration --contracts
.venv/bin/python -B src/toolchain/screen4/session_verify.py --bundle references/build/game-compact-megaram-runtime --headless --scenario integration --contracts
```

Run `session_profile.py --bundle <bundle>` with `NRX_PROFILE_ROUND=5/10/13`
and `NRX_PROFILE_ENEMIES=3/5/6` for baseline, ASCII8 and MegaRAM bundles.
MegaRAM profiles load through DOS. Run the four documented fallback/expanded
three-enemy cases and named regression/component scripts. Then
`scripts/compact_game_report.py` rejects missing/mismatched evidence and writes
the enriched ledger. Publish it using:

```sh
make timing-workbook TIMING_LEDGER=references/validation/compact-game/cycle-ledger-enriched.json
```

Durable evidence: `docs/measurements/cartridge/issue41-compact-game.json` and
the current cycle ledger/workbook. Source owners:
`scripts/compact_game_{build,verify,report}.py`, `scripts/compact_map_contract.py`,
`scripts/renderer_{image_build,window_probe}.py`, `scripts/megaram_package.py`
and `src/disk/megaram-loader.asm`. Raw payloads, PCM, video and traces remain
ignored/disposable. Physical MegaRAM variants, subjective listening/perceptual
acceptance and PAL 50 Hz output remain unqualified; measured output is NTSC.

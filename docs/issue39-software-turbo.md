# Automatic mapper and CPU selection (issue39)

The default is now `MAPPER=auto TURBO=1`: one SCREEN4 cartridge with a64KiB
mapper-RAM minimum, automatic expanded radar cache and automatic supported
Panasonic CPU scopes. Physical machines are unavailable, as confirmed by the
user on2026-10-30. Emulator checks, generated audio checks and user perceptual
acceptance are separate; this document does not certify physical hardware.

The user reaffirmed two mandatory constraints on2026-10-30: the ROM must remain
within the2MiB cartridge limit (2,097,152 bytes), and the default must continue
to run on unexpanded64KiB machines. There is no4MiB fallback. Both current
forced images and the automatic image remain2,048,000 bytes; automatic selection
does not increase the minimum RAM requirement. The publication gate enforces
the2MiB ceiling before replacement.

## One-cartridge mapper selection

`GameAuto_Init` probes the currently mapped RAM device before cold allocations.
It executes a position-independent worker from Page3D500 while cycling all256
Page0 mapper values. It saves one byte at offset3FF0 for each value, writes
distinct markers, counts independent banks, then restores bytes in reverse
order and restores FC. Reverse restoration handles aliased banks correctly;
port readback alone is never treated as proof of RAM. This supports the standard
8-bit mapper range up to4096KiB. The displayed size is this mapper's capacity,
not a sum of RAM across slots. The existing requirement for mapper-compatible
64KiB RAM still applies.

Four independent16KiB banks select the active-screen64KiB radar cache. Eight
or more select the existing expanded cache, using six distinct banks including
main Page0, Page3, two map segments and two flag-cache segments. Additional RAM
does not create larger caches. Both retain original graphics and game rules.
Boot patches the64KiB API entry bytes to resident expanded implementations;
the64KiB path executes directly, without a new per-frame capacity check.

| Location / API | Ownership and lifetime |
| --- | --- |
| `0000..07DF`, `GameAuto_Workers` | Main Page0 RAM; boot detector, text formatter and low-memory helpers, plus expanded-cache builder. Loaded from unused cold-bank padding. AF/BC/DE/HL/IX scratch at initialization; interrupts disabled by caller. |
| `07E0..07E4` | Detected capacity, expanded flag, mapper mask and cache-valid flag. Persistent in main Page0; no overlap with existing1000+ workers. |
| `D500..D5FF`, `D600..D6FF` | Temporary probe code and saved bytes during cold boot; later reused by the existing boot bitmap scratch. No extra RAM reservation. |
| Expanded flag functions | Resident ROM, since they switch Page0 to flag-cache banks. Shared flag-key/collected helpers retain the original main-Page0 contract. |
| `GameAuto_FlagsValid` | Invalidated by `ColdLoad`; set after rebuilding the128KiB cache. Challenge-screen return reuses the current cache, preserving captured flags. |
| `GameAuto_PaintStatus` | First ROM-OK descriptor only; base Z80, owns AF/BC/DE/HL/IX and Page2 cartridge bank. Uses original8x8 font and boot palette. No active-game calls. |
| Cold-bank offsets1000/1800 | Worker image and generated font occupy previously unused padding in the same16KiB ROM bank. No added bank or cartridge bytes. |

`TEST_MODE=1` places the foreground-only `GameSession_InputTick` helper in the
spare low-Page0 worker space to accommodate its added input/death checks in
resident ROM. Its body and calling contract are unchanged; production retains
the original resident address. Both diagnostic controls pass on64/128KiB.

CPU detection finishes before the hardware-check display. Under original
`ROM OK`, the new rows are `MAPPER <size>K` and `TURBO ON/OFF`. ON means an
acceleration backend was detected for the two CPU-only gameplay scopes; it does
not mean that boot, VDP access or audio runs accelerated. The text uses original
arcade glyphs at1:1 scale. The boot encoder explicitly erases the dynamic text
before either hidden page is reused. The pixel oracle allows only these two
authorized rectangles to differ from the original boot frames.

```sh
make build                         # one automatic cartridge
make run                           # same cartridge,64KiB reference
make run MAPPER=1                  # same cartridge,128KiB reference
NRX_REFERENCE_MACHINE=Panasonic_FS-A1GT make run # stock512KiB
make run TURBO=0                   # automatic RAM selection, base-CPU diagnostic
```

`MAPPER=0`, `MAPPER=1` and the default select identical build inputs, output
paths and ROM bytes. This option only chooses64/128KiB reference RAM for
openMSX. Historical
forced cache builds are available through the internal builder environment
documented in [the cache strategy](ram64-variant.md), not through `MAPPER`.

The current automatic measurements are recorded separately in
`docs/measurements/timing/issue39-auto-mapper.json`. Earlier forced-image
measurements below retain their own hashes and workloads; they do not qualify
the new automatic ROM.

## Current delivery artwork

The optimized1-bit `assets/msxlogo.bmp` is now imported at54x20, scale1, at194,8.
Current ROM SHA256 is `d73539eb988b6de198a214bcb5e03476df903dec82fe78a53cc30ea9308ea963`,
still2,048,000 bytes. Current-ROM boot/title pixels, real-keyboard start/graphics
contracts and the WSX64 three-enemy profile pass. The profile retains exactly
the prior29.966FPS and work distribution. The updated ledger/workbook is sourced
from `docs/measurements/timing/msx-logo-bmp.json`. This is an artwork update,
not a rerun of the complete hardware matrix below; that matrix keeps its original
ROM hash and measured scope.

## Automatic-hardware validation baseline before the logo update

The default cartridge is **2,048,000 bytes** (49,152 bytes below2MiB), SHA256
`3bd41357067589c1c0a65722426c0c4f3f24fdac1941b6dcbd27e56e83393cf4`.
All33 three/five/six-enemy profiles,88 session checks,20 long/component checks,
seven boot pixel/timing checks and five additional mapper-capacity checks pass.
Capacity coverage is64,128,256,512,1024,2048 and4096KiB, including stockST/GT
and the Sony64KiB base-CPU control. The probe bytes and original FC mapping are
verified before allocation, and all allocated segments must be distinct.
The two authorized status rows are pixel-checked against the actual detected
values; the rest of the boot sequence retains its independent original oracle.

General tests:448 pass. SCREEN4 components:92 run, one existing skip. Optional
`TURBO=0`, `HARDWARE_CHECK=0` and `TEST_MODE=1` builds also compile within the
same image size; boot/status, real-keyboard start/integration or diagnostic
controls are checked as appropriate. The frozen128KiB non-turbo ROM and all
1,589 symbols still pass `make verify-module-layout`; this is a separate gate
from automatic-ROM qualification.

| WSX native enemies | 64KiB FPS | 128KiB FPS | 64/128 mean work ms | 64/128 p95 ms | 64/128 max ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 3 | 29.966 | 30.029 | 21.187 / 21.013 | 31.020 / 29.603 | 35.602 / 34.407 |
| 5 | 28.872 | 28.872 | 24.634 / 24.440 | 36.365 / 35.471 | 48.356 / 47.190 |
| 6 | 28.701 | 28.993 | 25.258 / 24.886 | 37.264 / 35.611 | 47.762 / 46.604 |

Across the nineFX/WX/WSX comparisons, extra RAM reduces mean work by0.58–2.79%
and p95 by2.46–5.49%. The five-enemy WSX sample has unchanged presentation FPS;
reduced work need not cross a refresh boundary. In64KiB FX/WX/WSX and Sony
workloads, work/cadence matches the earlier forced64KiB image within recorded
floating-point precision. ST/GT automatically use the expanded tier on stock
RAM; they do not emulate a64KiB machine merely because the reference request
was64. Comparisons retain actual capacity and selected tier in the ledger.
These short same-input workloads can differ in trajectory/active partition;
they are not a guarantee of a fixed FPS gain throughout a human game.

The two-player test originally wrote a completed-death state asynchronously
between the turbo wrapper's guard and its logic call. That synthetic race is
retained privately as rejected evidence. The fixture now injects only at a
base-CPU presentation boundary, and all11 machine/reference combinations pass.
No production code was changed to accommodate the fixture.

Reproduce complete automatic matrices with `turbo_matrix.py`, passing
`--bundle references/build/game --turbo 1` and a
separate new `--output` directory under `references/` for each matrix:

- `--kind profile`: all default machines and reference capacities.
- `--kind regression`: all default machines and reference capacities.
- `--kind long --machine Panasonic_FS-A1WSX --machine Panasonic_FS-A1ST`.
- `--kind boot --machine Panasonic_FS-A1WSX --machine Panasonic_FS-A1ST --machine Panasonic_FS-A1GT --machine Sony_HB-F1XV`.
- `--kind boot --machine Panasonic_FS-A1WSX --ram 256 --ram 512 --ram 1024 --ram 2048 --ram 4096`.

Publish with `auto_report.py`, passing these five `result.json` files as
`--profile`, `--regression`, `--long`, `--boot` and `--capacity`, plus
`--factory references/issue39/factory-probe-v5/result.json`,
`--bundle references/build/game` and
`--output docs/measurements/timing/issue39-auto-mapper.json`. Reproduce the
factory input with `src/toolchain/msx/turbo_probe.py --output <new-reference-path>`
when needed. Then run `make timing-workbook`. The report rejects missing,
failed, duplicate or superseded-ROM evidence. The workbook includes actual
mapper capacities, cache tiers, CPU modes, per-routine inclusive/self costs,
frame waits/margins and prior-workbook archival under original hashes.

## Linked implementation before this change

Both SCREEN4 full-session RAM profiles generate native motion/AI adapters from
`src/screen5`, but `game_core.py` truncates `full-native-motion.inc` before
`Full_CacheInitNative`. The legacy `Full_TurboNative` detector is beyond that
boundary. The SCREEN4 cold audio module supplies `Full_TurboOn/Off` as `RET` stubs.
The legacy `full-terrain-cache.inc` backend is not linked into these cartridges.
Existing SCREEN4 timing qualification consequently covered base-clock Z80.

`z80_freq_locked=true` in openMSX means machine-selected clock, including factory
turbo. Setting it false would enable a synthetic frequency override. The new
qualification keeps it true and checks actual CPU/controller state and elapsed
instruction time. Emulator throttle and Ren-sha autofire are unrelated.

## Machine and RAM matrix

| Machine | Default64KiB reference request | MAPPER=1 reference request | Accelerated scope |
| --- | --- | --- | --- |
| FS-A1FX | Stock64KiB | Explicit private NR128 reference expansion | Factory Z80 5,369,318Hz |
| FS-A1WX | Stock64KiB | Explicit private NR128 reference expansion | Factory Z80 5,369,318Hz |
| FS-A1WSX | Private NR64 matching stock64KiB | Explicit private NR128 reference expansion | Factory Z80 5,369,318Hz |
| FS-A1ST | Stock256KiB | Stock256KiB | BIOS R800 ROM |
| FS-A1GT | Stock512KiB | Stock512KiB | BIOS R800 ROM |
| Sony HB-F1XV control | Stock64KiB | Not qualified on stock RAM | Original base Z80 loop |

The synthetic cartridge also measures R800 DRAM. It keeps BIOS Page0 visible and
calls CHGCPU/GETCPU. R800 ROM and DRAM accelerate the measured external cartridge
loop similarly; the faster internal-RAM loop is a separate workload. Runtime
uses R800 ROM and does not create or reserve a BIOS DRAM shadow.

## Backend and lifetime contracts

The adapter in `src/toolchain/screen4/session_turbo.py` emits a separate loop and frame
driver from the already transformed production source. It does not maintain a
second copy of native game rules. Boot selects the loop once. Unsupported
hardware executes the original loop without an additional per-frame branch,
call, controller write or CPU-mode check.

Only ordinary active `Game_LogicTick` and `Game_Actors` are accelerated. Round,
death and menu transitions bypass the logic scope. Input sampling, PSG work,
sprite generation/uploads, background/radar/HUD transfers, VDP commands, HALT
and VBlank publication retain base Z80 timing. HUD, complete cars, hardware sprite
limits, original graphics, native tick clocks and game rules remain enabled.

| Entry / state | Contract |
| --- | --- |
| `GameTurbo_Init` | Cold boot after startup workers are copied. AF/BC/DE/HL scratch; caller owns disabled interrupts. Initializes exactly one backend and base mode. |
| `GameTurbo_Enter/Leave` | Main Page0 selected, IM2 initialized, no nesting. Preserve AF/BC/DE/HL/IX/IY/I, SP and incoming IFF. Change CPU mode only for the explicit computation scope. |
| Panasonic | Select device8, verify complemented ID F7 and capability bit2 clear. Change bit0 of the captured status; retain other bits. Do not touch SRAM/configuration ports. Unsupported detection restores the previous readable selector and does not write41. |
| turboR | Require MSXVER3 and captured BIOS primary0/subslot0. CHGCPU0180 is called only with BIOS Page0 mapped, from the Page3 bridge. Preserve the complete current primary-slot byte and restore it before returning. RAM-mapper registers and Page2 cartridge ownership do not change. |
| IRQ | Active IM2 ISR preserves its normal registers and acknowledges VDP status0. It may run on the accelerated CPU; it performs no foreground transfer or PSG/input work in an active session. I/O/ABI checks observe this distinction. |
| `D2E0..D2F7` | Position-independent BIOS bridge within the unused SCREEN4 tail of the existing D2 reservation; below state bytes. No overlap with D2D2 IM2 jump or AI state ending at D2CB. |
| `D2F8..D2FE` | Backend kind, captured BIOS information/status and active flag. Survive native resets and D300..F2FF boot scratch clearing; reinitialized on cartridge boot. |
| `2900..2BFF`, startup suffix below3000 | Backend and generated drivers reuse padded startup-worker space in main Page0. Assembly bounds enforce the original reservations. No new RAM segment, ROM bank, VRAM allocation or gameplay buffer. |
| Menu / reset / exit | Every computation scope returns to Z80. Menus, cold transitions and game over use base mode. No return-to-BASIC/service exit is provided by this cartridge; system reset returns control to firmware. |

CHGCPU leaves the selected CPU in BIOS IM1. The authored bridge explicitly
restores IM2 before incoming IFF can be reenabled. Early R800 measurements made
before this correction are rejected. A long128KiB R800 route also reproduced a
wall entry with the old narrow corner-snapshot band. The turbo adapter uses the
existing64KiB six-unit conservative band in both profiles; the non-turbo128KiB
module-extraction baseline remains unchanged.

## Earlier forced-image reproduction and evidence

The completed matrix contains 66 paired profile runs, 88 session checks,
40 paired long/component checks and 11 observed base-CPU startup checks. All
pass for the recorded forced images. The synthetic factory probe qualifies
all five targets and the non-turbo control. General tests: 448 passed;
SCREEN4 components: 90 run, one existing skip. The preserved non-turbo128KiB
ROM and complete symbol map still match the frozen extraction baseline.

Across the 30 Panasonic workload pairs, mean elapsed work decreases by
7.16% to 15.36%; p95 improves in every pair. The maximum increases in five
pairs: FX/WX64 with five enemies (0.66%), WSX64 with five enemies (0.01%),
and ST/GT128 with three enemies (11.80%). Those tail regressions remain part
of the historical comparison. The Sony control retains the
same mean work, p95, maxima and late-frame fractions within floating-point
precision.

| 64KiB machine | Native enemies | Base FPS | Turbo FPS | Base late % | Turbo late % |
| --- | ---: | ---: | ---: | ---: | ---: |
| WSX | 3 | 29.468 | 29.966 | 3.36 | 1.27 |
| WSX | 5 | 27.997 | 28.872 | 14.04 | 7.56 |
| WSX | 6 | 27.431 | 28.701 | 17.65 | 8.82 |
| ST | 3 | 29.468 | 30.607 | 3.36 | 1.69 |
| ST | 5 | 27.997 | 28.872 | 14.04 | 7.56 |
| ST | 6 | 27.431 | 29.111 | 17.65 | 5.88 |

Timing changes trajectories and the active/death partition, so active sample
counts can differ. These are same-input/population workload comparisons,
not matched-state marginal speedups. Occasional one-refresh presentations can
raise the average above the two-refresh target; the native logic/audio clocks
remain tied to physical ticks. User timing and audio acceptance is pending.

The retained three-enemy baseline ranks native logic and actor preparation as
the substantial CPU-only scopes; VDP name transfers remain a large cost and
stay at base timing. In the ST64 three-enemy sample, scope entry plus exit costs
about1.18ms per presentation, including about0.92ms in the BIOS bridge.
The bridge is a child cost, not an additional amount to add to1.18ms.
R800 ROM versus DRAM gives no useful external-cartridge-loop advantage in the
synthetic sample, so no DRAM-mode transition is added to the active game.

Both images remain **2,048,000 bytes**:

- 64KiB TURBO=1 SHA256: `fce6b95c249400cc21e5a6c77b0353c2671dd584f247eceb4aa9e9c6874c6d6f`.
- 128KiB TURBO=1 SHA256: `5c5bfbda65104798a23034f3e13767a1fdad0f8838cb60856965abb3b4c07df1`.

The maintained workbook selects the WSX64 three-enemy candidate as its primary
ROM and includes the full machine/profile matrix. The prior workbook and its
original ledger are archived under their original hashes.

```sh
NRX_RAM_AUTO=0 NRX_RAM_KIB=64 NRX_TURBO=1 .venv/bin/python -B src/toolchain/screen4/build.py --full-session
NRX_RAM_AUTO=0 NRX_RAM_KIB=128 NRX_TURBO=1 .venv/bin/python -B src/toolchain/screen4/build.py --full-session
make verify-module-layout TURBO=0 MAPPER=1
.venv/bin/python -B src/toolchain/msx/turbo_probe.py --output references/issue39/factory
.venv/bin/python -B src/toolchain/screen4/turbo_matrix.py --output references/issue39/paired
.venv/bin/python -B src/toolchain/screen4/turbo_matrix.py --kind regression --output references/issue39/regression
.venv/bin/python -B src/toolchain/screen4/turbo_matrix.py --kind long --machine Panasonic_FS-A1WSX --machine Panasonic_FS-A1ST --output references/issue39/long
```

The profile matrix pairs base/factory modes on the same machine/RAM profile at
native rounds5/10/13 (three/five/six enemies), using keyboard coin/start/F5 and
directional input. It retains an observer control run, ROM/symbol snapshots,
real VDP endpoints, inclusive/self costs, calls/presentation, means/p95/max,
waits, remaining budget and late cadence. CPU/controller, register/IFF/IM and
slot/mapper guards must pass. BIOS/cache numeric PC aliases are rejected before
synthetic fixture injection. Event fixtures are explicitly separate from
natural directional and16000-refresh steering/smoke workloads.

All durations use elapsed emulated time. Historical `*_cycles` fields in mixed
clock/R800 ledgers mean seconds times3,579,545 reference Hz; they are not actual
R800 instruction cycles. Workbook comparisons use milliseconds. Inclusive
parents and children overlap and must not be summed. Physical refresh,
presentation rate, drawing phase and VBlank budgets remain separate; the
5,000-reference-cycle usable-VBlank reserve is still a planning assumption.

The frozen module gate continues checking the preserved non-turbo128KiB
counterpart. It does not certify intentional CPU/motion changes in TURBO=1.
Never regenerate its baseline merely to approve this experiment.

The factory-clock observer control permits at most six reference cycles of
per-frame boundary jitter. The six-enemy WSX case reproduced a six-cycle
boundary difference with identical guest-state records and zero total drift.
The existing state/total-drift checks remain; TURBO=0 retains its five-cycle
per-frame gate. These are observation bounds, not additional gameplay pauses.

No BIOS, game ROM, extracted payload or disassembly is committed. Reproduction
uses the contributor-supplied inputs under ignored `references/`. See
`docs/measurements/timing/issue39-cpu-matrix.json` and the maintained workbook for
the final ROM-bound matrix. Failed/superseded private runs are excluded.

## Technical sources

- [openMSX21.0 Panasonic controller](https://github.com/openMSX/openMSX/blob/RELEASE_21_0/src/MSXMatsushita.cc): factory clocks, capability and VDP waits.
- [openMSX21.0 S1990](https://github.com/openMSX/openMSX/blob/RELEASE_21_0/src/MSXS1990.cc): CPU versus DRAM controller state.
- [openMSX21.0 machine definitions](https://github.com/openMSX/openMSX/tree/RELEASE_21_0/share/machines): stock RAM/slot configurations.
- [MSX Assembly Page I/O reference](https://map.grauw.nl/resources/msx_io_ports.php): switched I/O and slot/controller ownership.

# Fixed64KiB cartridge and MegaRAM binding

Issue: <https://github.com/sandersouza/msxgp-newrallyx/issues/42>.
Promotion: the owner selected the exact hashes below for stable1.0.2 on
2026-11-18. The following measurements retain their original pre-release scope;
see `.github/releases/1.0.2.md` for the publication decision and final downloads.
Owner requirement: MSX2+,128KiB VRAM,64KiB main RAM **without a RAM mapper**
for cartridge and MegaRAM; sufficient standard mapper remains mandatory for
the BIN/COM main-mapper editions. Local test candidate only; no release.

## Failure and correction

The [earlier gate](measurements/cartridge/issue42-plain64-gate.json) correctly
failed: the mapper-backed constructor filled Page0 after writing FC, destroying
live code when that port could not select another RAM segment. Successful
MegaRAM loading and a64KiB mapper were insufficient compatibility evidence.

The fixed binding retains the original complete mutable32KiB world in physical
RAM4000..BFFF under the cartridge windows. Small Page0 foreground accessors
temporarily expose both RAM halves and restore the cartridge before returning
to ROM. Coordinates, ring wrapping, theme object IDs and the pooled eight-word
PUSH constructors are unchanged. Cold construction reads the opposite ROM half,
restores SP before calls/returns and never adds active decompression or streaming.
The source owner is `scripts/fixedram_backend.py`; the three authored
`src/screen4/session-fixedram-*.inc` files state the ABI, IRQ and lifetime rules.
`modules/contracts.json::generated_backends.fixedram_game` records their contract.

The boot replay has ended before the first real credit/start cold load.
Its2900..2A31 RAM becomes permanent foreground accessors, below live turbo
code2B25. Cold workers0800..09D3 share the later smoke-list lifetime and are
reinstalled before **every** stopped cold load. Existing navigation3000..37FF,
flag records3800..3FFF, radarC110..C24F and all native state stay owned as before.
The exact original IRQ body is installed at permanently visible Page3C250..C272.
Neither a RAM segment nor an extra video buffer is allocated.

Slot selection supports separate RAM/cartridge primary slots, unexpanded RAM,
and RAM3.0/cart3.3 in the same primary. Shared-primary writes are patched once
to the secondary-slot register; unexpanded RAM never writes FFFF. Expanded
machines bind their existing world segments under Page1/Page2 and retain the
optional flag cache and supported CPU acceleration. Fixed RAM ignores FD/FE.
The hardware caption now reports `RAM 0064K` instead of mistaking one probe
window for16KiB total RAM. Game art, colors, clocks and rules are unchanged.

Two rejected prototypes exposed lifetime hazards. Keeping permanent accessors
at0800 let active smoke records overwrite them. Keeping the IRQ in Page0 let
expanded flag caches hide it and produced measured flag-upload spikes. The
accepted binding separates stopped smoke scratch, ended boot RAM and permanent
Page3 IRQ ownership. Both failures must remain excluded by future changes.

## Current artifacts

|Artifact|Size / requirement|SHA-256|
|---|---|---|
|`dist/newrallyx.rom` and `dist/experimental/fixedram/newrallyx.rom`|744KiB ASCII8;64KiB fixed RAM, no RAM mapper|`c82e85db4d47bbc2c72797de0982998642f952208aeecfd1edbd1b8de2a87160`|
|MegaRAM programmed image|744KiB;768KiB MegaRAM and64KiB fixed RAM|`c3736f2cc167638a7e90e4919c6d12f6268be3ca4c6cbc9ccd710a5360d84fd6`|

Normal `make build` now uses this binding; `make build-megaram` also writes the
local DOS1/Disk BASIC MegaRAM package. This is artifact generation, not release
publication. All ten sealed main-mapper executable/resource/carrier files remain
byte-identical. The legacy ZIP is rebuilt with current provenance/source overlay
and timestamps; archive identity is distinct from runtime identity.
`mapper512_reference.py` explicitly pins that
experiment's original mapper source rather than reading the moving default ROM.
The512KiB carrier still requires512KiB standard mapper RAM and is not this
fixed-RAM cartridge. F10 remains Shift+F5 on the MSX matrix: hold through the
opening until title, release before credit/start; cars/rocks cannot kill,
walls remain solid, reset clears the latch.

## Measured result

[Compact evidence](measurements/cartridge/issue42-fixedram64.json) retains exact
artifact/source hashes, command matrix, state matching and scoped results.
The emulator asserts **zero RAM mapper devices** and65,536 bytes of fixed RAM.

-35 automated/emulator commands pass: ten performance profiles, seven session
  scenarios, five component scenarios, all three300-presentation delivery
  paths, F10, slot topologies, insufficient-MegaRAM rejection and three natural
  game-over/new-game runs. Three natural deaths lead to title and a new credit/
  start with180 further presentations; no injected life, score, clock or seed.
- All ten performance comparisons match356 camera/native actor/input/tick/
  full14-register PSG rows. Every paired active frame costs the same or less
  than the previous mapper-backed build, within0.01 reference-cycle tolerance.
-4096 native steps independently match768 bytes of original state, full PSG
  and host game/death/round state in cartridge and MegaRAM. This uses a stated
  two-byte seed fixture and real keyboard startup, not a natural RNG claim.
- An additional16,000-refresh keyboard/turn/smoke run passes, including natural
  deaths/restarts and3,345 distinct poses after refresh5,000. Its observer uses
  the relocated live IRQ; the first attempt watched the retired ROM IRQ and
  timed out without counting frames. MegaRAM BASIC also passes with unexpanded
  RAM in primary2, beyond the batch's shared-primary test.
- Opening71-state graphics/timing/silence, PSG/PCM component, smoke, stones,
  challenge, flag completion, radar, controls, two-player, attract and clipping
  checks pass. DOS/BASIC main-mapper launch checks pass without payload changes.
-512 general tests and94 component tests pass, with one component skipped.
  The default frozen module byte/symbol layout check also passes; the functional
  fixed binding is outside that source-only modularization comparison.

WSX fixed64 active costs below apply equally to ASCII8 and MegaRAM. Units are
elapsed seconds times3,579,545 reference Hz, including CPU/VDP/IRQ costs, not
mixed-clock R800 instruction cycles. Refresh remains59.922743Hz.

|Native enemies|Previous mean / P95 / max|Current mean / P95 / max|Presented FPS|
|---|---|---|---|
|3|75371.287 /108438.667 /125776.333|75246.882 /108358.667 /125776.333|30.029363|
|5|87663.045 /128821 /171045|87391.881 /128743 /170965|28.872426|
|6|89690.069 /131894 /170165|89600.338 /131814 /170085|28.816839|

Many frames are unchanged; the three-enemy maximum is unchanged. Additional
mapper128, stock Sony64 and turboR ST256/GT512 comparisons also have no slower
paired active frames. Existing overloads and heavy-scene tails are not hidden.
The current [cycle workbook](cycle-budget.xlsx) and its source ledger retain
calls/frame, inclusive/self costs, synchronization waits, raster endpoints and
remaining budget. Parent/child inclusive costs must not be added. The previous
44be6037 workbook/ledger remain archived under their original hash.

This evidence is openMSX22 NTSC testing, not physical hardware, PAL50, every
natural course or subjective audio acceptance. The earlier512KiB experiment's
divergent-route0.24% question remains separate. No release, merge, commit or push.
Automated references use a null host sound driver: PSG and PCM recording stay
emulated, but tests do not play sound through the user's speakers.

## Reproduce

Supply contributor arcade/BIOS inputs and the existing private DOS test inputs.
The previous mapper control is `references/build/game-compact-runtime`; rebuild
it explicitly with `compact_game_build.py` without `--fixed-ram` when absent.
Keep its old MegaRAM package in `references/cache/fixedram-controls/megaram`
before replacing the default package. No original payload belongs in Git.

```sh
make build-megaram
.venv/bin/python -B scripts/fixedram_qualify.py
.venv/bin/python -B scripts/fixedram_tick_verify.py
NRX_REFERENCE_RAM_KIND=plain .venv/bin/python -B src/toolchain/screen4/session_steering_verify.py --bundle references/build/game-fixedram-runtime --frames 16000
.venv/bin/python -B scripts/compact_game_verify.py --fixed-ram --ram-kind plain --mode basic --size 768 --topology unexpanded
.venv/bin/python -B scripts/mapper512_game.py
.venv/bin/python -B scripts/mapper512_game_verify.py --mode dos --frames 180 --f10
.venv/bin/python -B scripts/mapper512_game_verify.py --mode basic --frames 180
.venv/bin/python -B scripts/verify_disk.py --mode dos
.venv/bin/python -B scripts/verify_disk.py --mode basic
make test
make verify-module-layout
```

For consolidation, retain the named logs/seals consumed by
`scripts/fixedram_report.py`, run it, then regenerate the current workbook with
`make timing-workbook TIMING_LEDGER=references/validation/fixedram/cycle-ledger-enriched.json`.
The report intentionally rejects missing current-hash or unmatched-state proof.
After consolidating, remove disposable traces, RAM/VRAM dumps and recordings;
keep compact JSON/workbooks and the test artifacts.

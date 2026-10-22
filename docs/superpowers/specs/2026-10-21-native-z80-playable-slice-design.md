# Original-Z80 playable slice for MSX2+

Status: written specification approved by the user in the issue #11 chat on
2026-10-21, following approval of the architectural direction. This document does
not claim that native boot, combined timing or gameplay equivalence has passed.

Issue: https://github.com/sandersouza/msxgp-newrallyx/issues/11

## Outcome and boundaries

### User-approved acceptance amendment — 2026-10-21

The user selected the playable-port criterion after reviewing the measured
foreground timing difference: retain the original logic and rules, document
temporal differences, and validate behavior, controls and performance. Complete
byte equality with arcade post-IRQ RAM is therefore a diagnostic, not a gate
blocking graphics. Do not describe a failing strict replay as equivalent.

Reset integrity, guarded patches, register/stack safety, source/BIOS integrity,
1:1 graphics, original rules and the standard-speed 128 KB target still apply.
Game ticks retain the exact 16.5 ms rational cadence; do not drop ticks or alter
movement constants. Record foreground progress and visible/input latency
honestly. Validate coin/start, original steering/collision/enemies/smoke,
collection/score/fuel and death/restart on the port itself. Rendering acceptance
still requires coherent presentation, all active actors and measured raster/frame
budgets. This amendment supersedes the strict-RAM prerequisite in the sections
below; it does not authorize publishing or closing an incomplete port.

Produce a locally playable, silent cartridge using the original New Rally-X
program and the existing SCREEN 5 backend. Cover boot, coin, single-player start
and the initial normal stage: original steering/wall collision, enemies, smoke,
flag collection, score, fuel, collision/death and restart. Preserve all actors
active in the bounded replay; displaying one enemy does not justify suppressing
the remaining enemies or their interactions.

Use the existing 3,200-frame reset/input replay as the first differential case.
Add deterministic cases for required transitions it does not exercise. Later
rounds, challenge stages, two-player turns, synthesized sound and physical
hardware certification are excluded. Unsupported paths must be documented and
must not be represented as validated gameplay.

Target standard-speed MSX2+ with **at least 128 KB RAM mapper and 128 KB VRAM**.
The earlier 64 KB figure in #11 is superseded by the #10 decision and README.
The reference machine is the session-local `Panasonic_FS-A1WSX_NR128` variant.
Do not modify installed emulator configurations or download ROMs/BIOS files.

Keep original 8x8 tiles and 16x16 sprites at 1:1 scale. Present a 256x212 screen
with the existing reduced maze viewport and rearranged HUD/radar. Logical world
coordinates, movement constants, AI, collection and collision rules remain
original. Any visible clipping or presentation latency is reported separately
from game-state equivalence.

## Evidence available before implementation

- Dependencies #1, #2, #6, #9 and #10 are closed; the checkout includes the #9
  and #10 delivery merges.
- `make test` passed 157 tests before this work.
- All 13 contributor ROM files validate against `scripts/graphics/nrallyx.json`;
  all 11 candidate hook digests in `scripts/z80_hooks.json` match.
- The managed assembler and local BIOS directory exist. This is not a new BIOS
  boot verification.
- `docs/z80-native-analysis.md` records 1,402 repeatable arcade snapshots,
  observed hardware accesses, candidate hook contracts and mapper boot evidence.
- `docs/raster-scroll.md` defines current VRAM, bank, RAM and raster ownership.
  Its renderer currently assumes immutable stage tiles and uses all 32 hardware
  sprite slots: 30 for the HUD/masks and two for the player.

## Selected architecture and alternatives

Retain original program addresses in writable RAM and adapt hardware boundaries
with guarded patches. Reuse the current renderer's geometry, tile atlas, camera,
HUD API and verification infrastructure. Suspend original execution before
temporarily mapping graphics resources into its state page.

Selective routine reuse is the fallback if measured native execution cannot
coexist with raster deadlines. It would require a separate decision and a
revised equivalence contract; do not silently switch to a new gameplay scheduler.
Broad operand relocation is rejected for this delivery because pointers, data
tables, stack-based startup and indirect accesses make it harder to validate.

## Memory, loading and ownership

| CPU range | Runtime owner | Required contract |
| --- | --- | --- |
| `$0000..$3fff` | Original program/tables in RAM | Preserve addresses; apply only complete, validated patches |
| `$4000..$7fff` | Resident renderer/adapter in RAM | Code and IRQ targets remain available while game or assets are mapped |
| `$8000..$bfff` | Original state segment | Preserve `$8000..$8fff`, `$9800..$9fff` and hardware shadows |
| `$c000..$ffff` | Host state, buffers, vectors and host stack | Separate from original stack and startup shadow writes |

Allocate four distinct 16 KB mapper segments for those owners and four further
segments for the active asset working set/staging. Discover the RAM slot and
mapper segments during BIOS-visible initialization; never assume physical
segment numbers. Copy resident code and original data before switching BIOS and
cartridge windows out. No BIOS calls are allowed with the native mapping active.
Retain the initial slot/mapper state for the documented reset/exit policy.

Reserve the existing host areas `$c000..$c472`, `$d000..$d100`, `$d2d2` and stack
starting at `$f380` until the linker inventory replaces them explicitly. Retire
the isolated movement copy at `$e000..$efff` in the native path; do not execute
the current movement-only adapter alongside the complete original program.
Keep game stack overlap below `$8400` intact; video RAM is not wholly disposable.

Reserve `$a188..$a1ff` for the observed startup clear padding. Place input
snapshots at `$a200..$a202` for P1/P2/DIP, outside that padding. Host data must not
occupy any original writable range.

Inventory the active tile IDs, fonts, HUD and actor resources against the 64 KB
asset allocation before choosing their final packing. The entire current 1 MB
cartridge cannot be preloaded. Prefer the existing VRAM atlas and compact RAM
metadata over copying unused cartridge banks. If the bounded working set does
not fit, demonstrate a safe measured cartridge refill path or stop for a revised
memory decision; do not raise the 128 KB minimum implicitly.

During resource access, suspend native execution, switch only the asset window,
use host-owned committed state in interrupts, restore the game segment and then
resume. Map changes and VDP control packets are atomic. Generate and validate a
linker/allocation report; reject overlaps and resident-code overflow at build.

## Guarded program adaptation and reset

Validate the complete supported program image, source ROM inventory and every
patch span before producing any patched payload. Extend the candidate inventory
with authored hashes/addresses/contracts for newly needed sites. Require
whole-instruction boundaries, nonoverlapping writes, valid continuations and
allocated stub destinations. Fail the build on a mismatch; never partially patch
an image or modify source files.

Cabinet diagnostics are not a useful MSX RAM/ROM test. Select a reset-only,
trace-verified transition into original game initialization after the cabinet
diagnostic, preserving its required initialization effects. Prove the resulting
first comparable state against a fresh arcade reset before accepting that boot
adapter. Do not jump into an arbitrary startup script point, treat its ROM-based
stack as writable, or substitute a captured mid-game snapshot for boot.

Adapt native interrupt-mode changes, vector-port writes and interrupt ownership.
The `$38cc` two-byte candidate cannot hold a three-byte jump. At `$040f`, emulate
discarded writes to original ROM while preserving flags, the subsequent read and
continuation state. Merely copying ROM into RAM changes attract-mode behavior.
Keep the program image unchanged after intentional boot-time patching; reject
unexpected runtime mutation in validation.

## Interrupts, scheduling and hardware shadows

The host owns MSX IM2, VDP acknowledgement, raster changes and the host stack.
Original game IRQ entry is `$01f0`, with publication/restoration at `$0468`;
`$0c2c` resets SP and is **not** a callable tick. Resume original foreground
execution with its original PC/SP, and deliver logical game IRQs through a
checked trampoline that preserves the interrupted context and displaced code.

Host IRQ entry must preserve main and alternate registers, original stack
contents and game interrupt semantics before using a separate host stack.
Prevent nested game IRQ execution. Original EI/DI/mode operations and the game
IRQ mask need an explicit compatibility contract; host interrupt availability
cannot depend on unmeasured arcade critical sections. Record stack high-water
marks and worst-case interrupt latency. Reject stack corruption or unbounded
latency before adding rendering load.

Use a time accumulator for **one logical tick per 16.5 ms**, independent of 50/60
Hz display refresh. Derive elapsed time from measured MSX/VDP cycles, preserving
the remainder; do not round the arcade rate to 60 Hz. At 50 Hz, support measured
two-update refreshes. Apply replay input by logical tick and publish coherent
state only at the agreed boundary. Never slow simulation, drop logical ticks or
change movement constants to conceal a missed deadline.

Separate reads from overlapping hardware writes: input/DIP consumers read the
dedicated snapshots; radar, watchdog and sound writes retain independent shadows.
Adapt direct reads and the observed indirect input-pointer producers. Preserve
active-low encoding and original coin/start edge/debounce behavior. Watchdog and
sound are inert host interfaces; retain game-visible RAM and latch effects.
Decode latch bit 0 and sound-register nibbles when interpreting hardware state.
An arcade port `$00` write must never reach unrelated MSX hardware.

## Live presentation

Translate a committed original-state snapshot at each logical publication;
renderer code must never consume partially updated game RAM. Begin with complete
video/work/shadow comparisons for correctness. Optimize dirty detection only
after equivalence and timing measurements establish what can be omitted.

Replace diagnostic HUD/radar producers with actual score, high score, lives,
fuel, actor positions and remaining flags through the existing HUD API. Use
original descriptors/scroll state to derive camera and actor coordinates; do not
read the movement-only `$e000` copy. Keep the original game state read-only from
the renderer.

Provide a mutable source layer for flag/terrain changes and update resident ring
cache tiles when their source changes. Restore actor backgrounds from this live
source, including overlap, smoke, death and scrolling. Never redraw a collected
flag from the immutable initial map.

The current 32-slot SAT allocation leaves no slots for added enemies/smoke.
Use SCREEN 5 bitmap composition for additional gameplay actors while retaining
the current player/HUD sprite path initially. Keep original actor pixels,
transparency, flips and ordering. Dirty rectangles must include old and new
bounds and restore/redraw all overlapping actors. Validate that this composition
fits both the palette and VDP budget; any necessary SAT or palette redesign must
preserve the same presentation contract and receive a revised allocation report.

Preserve the existing header/footer raster deadlines. Keep arbitrary game work
out of the pre-header-split section. Camera scroll and sprite compensation update
every refresh; slower numeric/radar content cadence must not alter game logic.
Add controls for coin/start, steering and smoke: keyboard `5`, `1`, arrows and
Space respectively; joystick 1 direction and trigger A provide steering/smoke.
Coin/start use keyboard controls. Document reset behavior and remove conflicting
diagnostic pause/inspection bindings from the native path.

## Differential evidence and timing gates

First validate silent native boot/coin/start with rendering disabled, then add
presentation. Use identical reset, DIP/seed and logical-input schedules. Define
the first comparison boundary explicitly; #10 snapshots are pre-IRQ samples,
so matching filenames or display-frame counts alone is insufficient. Extend the
reference acquisition if exact phase alignment needs new snapshots.

Compare complete 4 KB video state, 2 KB work RAM and hardware shadows, plus named
semantic fields: mode/turn, player and enemy descriptors, direction, velocity,
fractional movement, camera, flags, score/high score, lives, fuel and transitions.
Any excluded byte requires an exact address, reason and evidence; never mask an
entire region to hide unexplained divergence. Report the first differing tick,
address/field and expected/actual values. Validate source and patched-image hashes
before and after replay.

Measure original foreground/IRQ work, host adaptation, state translation,
resource switching/copies, actor drawing, tile/HUD work and host ISR costs
separately. Report worst cases for one- and two-update refreshes at 50 Hz, plus
60 Hz cadence checks. The raw approximately 59,062 MSX clocks per 16.5 ms is not
an available rendering budget. Include MSX wait states and VDP busy time.

Acceptance requires zero unexplained state divergence, no missed header/footer
or VBlank deadlines, and no accumulated logical-tick backlog throughout each
declared scenario. Missing a budget is a feasibility result requiring a decision,
not permission to claim a playable, equivalent delivery.

## Verification and delivery

Keep authored tools, assembly, metadata, documentation and synthetic fixtures in
Git. Keep original/modified program bytes, extracted assets, generated ROMs,
traces, snapshots and captures ignored under `references/`. Never put original
instruction listings/bytes in authored fixtures or this specification.

Use synthetic tests for patch refusal/atomicity, allocation conflicts, input
mapping, cadence arithmetic, state comparison and dirty-region restoration.
Use contributor ROMs with MAME and openMSX for instruction/register/stack
behavior, reset alignment, actual input/play, pixel reconstruction and timing.
Synthetic mocks cannot establish boot, equivalence or performance.

Expose explicit native build/run/verify commands during development; retain the
current diagnostic as a reproducible reference until native acceptance passes.
Only then publish the native cartridge through the default build/run path.
Failed builds must not replace a previously valid default ROM.

Delivery evidence must list commands, tool/machine versions, ROM/source hashes,
tested controls/scenarios, divergence results, timing maxima and unsupported
paths. Link authored reports from the issue; keep proprietary evidence local.
Update the local issue draft and published tracking at implementation/review
boundaries. Do not commit, push, open a PR or close #11 without the applicable
user authorization and delivery/review conditions.

## Review checklist

- The 128 KB baseline supersedes the stale 64 KB issue assumption.
- Boot initializes original state; no saved gameplay snapshot substitutes for it.
- Original foreground scheduling and game IRQ semantics remain part of the port.
- Resource switching cannot expose an asset bank as game RAM to an IRQ.
- Live map mutations and added actors have explicit renderer ownership.
- Comparison phase, exceptions and performance failures remain observable.
- Full acceptance includes collection, smoke and death/restart evidence beyond
  the initial replay whenever needed.

After user review of this written specification, prepare the implementation
plan with task-level interfaces, tests and local integration gates. No runtime
implementation is included in this specification stage.

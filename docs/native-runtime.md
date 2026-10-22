# Native reset and runtime validation

Issue #20 is in progress. Original reset, foreground logic and game IRQs now
execute, including coin acceptance and collision transfers. The sections below
record earlier validation checkpoints; their historical strict-equality gates
are superseded by the approved playable-port criterion. Strict comparison still
fails and remains available as a diagnostic, with no byte exclusions.

The local evaluation cartridge `references/build/native-review-2026-10-22/native.rom`
adds live scenery, six bitmap actors, HUD and radar. It is a 128 KiB ASCII16
cartridge for the isolated 128 KiB mapper/VRAM MSX2+ reference machine, PAL/50 Hz,
standard-speed Z80. It does not replace the default cartridge. Rendering and
foreground throughput still fail performance acceptance; actual scanout RGB,
joystick directions and complete gameplay scenarios remain unverified. Sound
is outside issue #11's scope. Reset the machine to exit.

```sh
.venv/bin/python -B scripts/native_runtime.py run \
  --rom references/build/native-review-2026-10-22/native.rom \
  --output references/build/native-review-session
```

Use a fresh output directory. Keyboard controls are `5` coin, `1` start,
arrows steer and Space smoke. The assembled keyboard adapter passes 72 matrix
cases, including simultaneous keys and PPI/PSG output preservation. Joystick
port 1 directions/trigger A are implemented but not yet independently verified.

The preceding complete graphics capture (`issue22-video-check-52`) passes all
128 prepared frames: 5,145,600 scene pixels and 384,000 radar pixels, frozen tile
descriptors, original RAM/register preservation and restored mappings. Median
frame latency is 101.86 ms, maximum 3433.54 ms; those figures do not meet the
playable-port gate. Prepared VRAM is separate from physical scanout evidence.
The exact evaluation cartridge completes 128 replay ticks with exact cold reset
and all 72 keyboard cases (`native-review-2026-10-22-check`). The full Python suite
passes 248 tests. These checks do not establish gameplay acceptance.

## Proven reset boundary

`native_reset.patch_reset` pins the complete original program SHA-256 and both
modified spans. Every span endpoint and continuation must appear in a sealed
original execution trace. A linear disassembly is insufficient evidence.

The reset proof retains the original cold RAM initialization, including its
diagnostic RAM-pattern and scratch-buffer effects. It replaces the cabinet
interrupt-mode/wait transition with `Native_ResetFinalize`, runs the original
display initialization fragment and rejoins the original hardware-clear/game
entry sequence. No captured state or hand-coded RAM pattern is linked.

The original checksum success branch is adapted because the checksum covers
the intentionally patched program. Complete source integrity is checked before
patching, and the mapper copy is checked against the complete patched image.
This does not accept another source revision or silently ignore a source hash.

At original initialization entry, the openMSX proof compares all 6,536 captured
bytes: 4,096 video, 2,048 work RAM and 392 output shadows. There are **zero
excluded bytes**, including stale original stack bytes. PC/SP must be
`$0003/$8400`; host IM2/I remain `2/$d0`, with interrupts disabled. This proves
the reset boundary, not subsequent game-state equivalence.

## IRQ context and discarded writes

The host IRQ immediately saves the interrupted SP and switches to its reserved
`$c580..$c6ff` stack before pushing any registers. The CPU's two-byte interrupt
return PC remains on the interrupted stack. Main and alternate registers,
including flags, IX/IY and SP, are restored. The software save occupies 20 bytes;
a lower stack canary detects an overwrite. No BIOS calls or mapper changes
occur inside this handler.

The synthetic runtime probe exercises an interrupt with SP at `$8400`, as well
as 256 asset-map/IRQ/restore iterations and an actual machine reset. Mapping
guards reject unsafe and nested requests. Watchpoints on executed stores mark
the game-stack test: a breakpoint at the instruction following HALT can also
fire while the CPU remains halted and is not an execution-count oracle.

`Native_IncrementRead` preserves the original discarded-write behavior for a
program-window target: calculate INC flags, discard the write and read the
unchanged byte. RAM targets retain normal INC/readback behavior. The emulator
checks all 256 values, both incoming carry values and both memory regions:
1,024 cases, including S/Z/H/PV/N/C and undocumented result flag bits.
The original game hook is not installed by the synthetic microprobe.

## Original acquisition and nonreturning IRQs

Fresh MAME acquisitions record initialization, first foreground entry and every
game IRQ. EI/DI code locations come from execution breakpoints, not memory
reads. Memory observation callbacks reject debugger accesses with disabled side
effects; tracing/disassembly must not produce duplicate events.

Coin acceptance contains a real nonreturning IRQ transition. It discards the
previous stack and resumes another foreground path. The harness records the
transfer and its publication separately from the normal IRQ epilogue. A normal
return must never be invented for this path. Snapshot phases distinguish
`initialization-entry`, `pre-game-irq`, `post-game-irq` and
`post-game-irq-transfer`; phase mismatches cannot compare equal.

The 3,200-frame replay contains 2,440 game IRQ events: 2,439 normal returns and
one transfer. Two fresh acquisitions produced identical 2,442 snapshots and
boundary records. Fifteen EI/DI locations were actually executed in that replay;
this observation does not prove coverage of every possible game path.

## Reproduction

Use the managed assembler, MAME 0.289/openMSX 21.0 and contributor-supplied ROMs
and BIOS. Choose fresh ignored output directories for each invocation.

```python
from pathlib import Path
from scripts.msx.native_build import build_probe
from scripts.msx.native_probe import verify_probe
from scripts.msx.native_verify import capture_reference, verify_reset

root = Path.cwd()
assembler = root / '.tools/sjasmplus/1.24.0/sjasmplus'
bios = root / 'references/msxbios'
reference = capture_reference(root, root / 'references/analysis/native-reference')

reset_rom = build_probe(root, root / 'references/build/native-reset', assembler,
                       probe='reset', reset_reference=reference)
verify_reset(root, reset_rom, root / 'references/build/native-reset-proof',
             bios, reference)

runtime_rom = build_probe(root, root / 'references/build/native-microprobe',
                         assembler, probe='runtime', hz=50)
verify_probe(root, runtime_rom, root / 'references/build/native-microproof', bios)
```

Local evidence from 2026-10-21:

- Original reference: `references/analysis/issue20-reference-9/` (complete
  instruction trace and sealed provenance). Earlier equivalent snapshots:
  `issue20-reference-7/` and `issue20-reference-8/`.
- Reset: `references/build/issue20-reset-probe-2/` and
  `references/build/issue20-reset-proof-3/`.
- Runtime microprobe: `references/build/issue20-increment-probe-3/`, with
  proofs `issue20-increment-proof-4/`, `issue20-increment-proof-host5/` and
  `issue20-increment-proof-60/`. Each verifies 258 host IRQs, 256 mapping
  iterations, one game-window stack test and all 1,024 increment cases. The
  displaced host inventory is `[5,0,1,2,3,4,6,7]`.

All program images, traces, captured state and cartridges remain ignored under
`references/`. Evidence manifests bind their payloads and tool/source identities;
failed acquisitions are not sealed as passing proofs.

Reset-only checkpoint validation: 50 native tests and the complete 210-test suite
pass. Independent review identified malformed-reference checks that now have
regression coverage: initialization SP, foreground IFF, control records and
semantic validation when consuming a sealed reference. The reviewed reset
proof was rebuilt and repeated after those checks were added.

## Logical dispatcher and original execution candidate

The `irq` probe now executes the 32-bit rational clock in Z80 code for 100,000
host frames. At 50 Hz it produces 120,827 ticks/remainder 112,437,405; at 60 Hz,
101,140 ticks/remainder 39,017,100. A 64-case matrix exercises normal dispatch,
virtual DI, an already busy game IRQ, suspension, mapped assets and the game
interrupt mask. Foreground checkpoints drain the retained queue without
advancing the clock themselves. Host VBlanks can arrive during a game IRQ;
claim and publication are distinct events, and the observer does not mistake
an interrupted four-byte counter update for committed publication.

Three independent synthetic cases verify logical waits: a blocked host VBlank
cannot release the wait, three queued ticks complete without another VBlank,
and empty polling does not invent a tick. Main/alternate registers, flags and
SP are compared around every case. These cases pass at 50/60 Hz and with host
segment 5. The actual machine-reset repetition and the earlier 1,024 discarded
INC cases remain part of these probes.

The separate `logic` build uses guarded metadata in `native_logic_hooks.json`.
Displaced source instructions are included only in ignored generated assembly;
no original instructions or data are embedded in the authored metadata. The
candidate executes the original reset, foreground and `$01f0` game IRQ. Direct
and indirect control reads use `$a200..$a202`; virtual EI/DI preserves host IM2
ownership. An already queued tick is considered after the original instruction
following EI. Normal publication restores the saved foreground context; the
coin transfer retains its original abandoned-stack behavior and publishes at
SP `$8400`.

An original HALT must await a logical game interrupt, rather than any physical
host VBlank. The observed three-HALT text delay and counted HALT loop therefore
use a logical wait adapter. Five observed busy-wait loops also poll the queue.
These are guarded, trace-bounded patches, not replacement gameplay routines.
Coverage is bounded to the recorded replay; unexecuted code paths are not
certified by these observations.

Empty software polls use an exact one-byte nonempty cache of the four-byte
queue. Host-only queue mutations update this cache with physical IRQs disabled;
the fast foreground path preserves AF and avoids a full context switch. An IRQ
that arrives during an empty poll can leave work for the next service point;
it cannot discard a tick. The synthetic observer checks the cache against all
four queue bytes, including the borrow from `$0100` to `$00ff`.

`native_verify.acquire` replays the reference's raw active-low input samples at
logical IRQ entry. It requires the complete requested snapshot set, monotonic
publication, strict completion fields, an exact reset snapshot and unchanged
mapped program/resident code at both ends. The sealed report explicitly says
`acquisition_only=true` and `equivalence=false`. Completion is not a differential
pass, and these candidates do not replace the default cartridge.

## Remaining #20 gate

Original coin/start execution is acquired, but full state equivalence still
fails. The first strict mismatch already occurs in publication 1, including
startup progress and changed stack residue. Further differences involve live
foreground state, so excluding stack bytes alone cannot make this replay pass.
No exclusion has been approved or applied. The interrupted foreground instruction
phase and its throughput still need alignment with the arcade reference.

Complete the phase-aligned state and foreground/IRQ timing gate before graphics
integration. A completed input replay or accepted coin/start alone does not
satisfy this gate. Original payloads, generated trampolines, snapshots and
diagnostic bundles remain ignored under `references/`.

Latest evidence: `issue20-cache-borrow-proof-50`, `issue20-cache-borrow-proof-60`
and `issue20-cache-borrow-proof-host5` under `references/build/` contain complete
synthetic proofs (324 host IRQs and actual reset each). Original acquisitions
are `issue20-row-poll-proof-50` and `issue20-row-poll-proof-60`, bound to
`references/analysis/issue20-reference-11`. Both complete 2,440 game IRQ events
with one coin transfer and an empty final queue, without modifying the mapped
program/resident. Maximum pending queues are 3 and 1 respectively; worst
measured IRQ entry-to-publication intervals are 23,491 and 23,535 MSX clocks.
These intervals include adaptations and any intervening host ISR, not rendering.
The observed minimum game SP is `$83d6` (42 bytes below `$8400`), which only
establishes stack use for this replay.

The reference executes the player-update EI site `$10de` 5,607 times; native
50/60 Hz acquisitions execute it 5,017/4,967 times. This is evidence that matching
input/tick counts alone has not aligned foreground progress. Snapshot 1 fails
the strict complete-byte comparison; later differences also involve live state,
beyond stack residue.
The latter observations do not authorize a stack mask or a later comparison
start. State equivalence remains a failed gate, and #20 remains in progress.

Mask-write telemetry (`masks.tsv`) identified the scenario-generation loop as
a long stretch with the game mask enabled but too few foreground service
points. A guarded poll at the row-end watchdog write `$0920` reduced the 50 Hz
maximum queue from 13 to 3 ticks. It preserves the original row computation and
watchdog shadow. Maximum measured intervals between game IRQ entries are
24.826 ms (50 Hz) and 21.506 ms (60 Hz); these are acquisition observations,
not a passed latency/phase gate. The new arcade acquisition's snapshots are
byte-identical to reference 10, and its game IRQ frames are consecutive.

All native harnesses explicitly set `z80_freq_locked false` as well as
`z80_freq 3579545`. [openMSX's clock documentation](https://openmsx.org/manual/commands.html#z80_freq)
explains that the frequency value does not override the machine clock while
the lock is enabled. Acquisitions verify this setting at entry/completion and
require `clock.json`; a locked or nonstandard clock is rejected. Fixed-clock
repetitions of the preceding candidates produced identical snapshots/counts,
so the old lock omission did not cause the observed state divergence. The
original reset gate also passes with the enforced clock (`issue20-fixed-reset-proof`).

## Profiled coordinate-loop experiment

Setting `args.profile=(start_tick, end_tick)` for `acquire(root, args)` collects elapsed clocks per PC
over at most 64 logical ticks. The observer exports no opcode bytes and does not
modify CPU state. Its clock totals must reconcile with the selected window;
malformed, duplicate or out-of-range PC records fail validation. Interrupt
acceptance can share an instruction's measured interval, so this is not a pure
opcode timing table. In the baseline ticks 1600–1616, 92.36% of elapsed clocks
fell at page-0 PCs, including patched entry instructions. The remaining 7.64%
is not a complete estimate of adaptation overhead. All 1,616 snapshots in this
profiled prefix match the unprofiled acquisition byte for byte.

The profile identified the signed coordinate-reduction loop at `$18b1`. An
optional Z80 adapter uses the sign already set by ADD/SUB and retains the same
subtract-until-negative arithmetic and original epilogue. It changes no movement
constant or gameplay rule. It is disabled by default: `build_probe` requires
explicit `optimize=True` in logic mode. At the coordinate-only checkpoint, a
rebuild with the option disabled was byte-identical to the preceding row-poll
candidate; subsequent CPU bootstrap changes are documented below.

`function_probe=True` additionally runs a differential microprobe before cold
initialization. The oracle is the unpatched, relocatable 16-byte function from
the validated local contributor program; no original bytes are checked in.
All 65,536 A/L pairs and both incoming carry values compare complete AF and HL
outputs (131,072 cases). At both refresh rates, the oracle takes 19,677,184 MSX
clocks including calls, versus 16,089,088 for the adapter: 18.23% fewer clocks
for this function across the exhaustive input set. The original cold reset
still matches all 6,536 bytes afterward. This local function result does not
prove full gameplay equivalence.

Evidence is under `references/build/`: `issue20-coordinate-proof-3` and
`issue20-coordinate-proof-60` contain the exhaustive proof and timing;
`issue20-coordinate-reviewed-{50,60}` contain repeated full 2,440-tick
acquisitions and reconciled profiles. Repeated optimized acquisitions have
identical snapshots. Player-update counts rise to 5,124/5,056 from the baseline
5,017/4,967, versus arcade 5,607. Maximum queues remain 3/1 and finish empty;
whole-state comparison still fails. The experiment has not been promoted to
the baseline or default cartridge, and #20 remains in progress.

Coordinate-experiment validation: 58 native checks and 218 full-suite tests pass. Independent
review found no Important/Critical defects in the optional adapter, independent
oracle, input enumeration or evidence checks. Original payloads and all generated
probe/capture data remain ignored.

## Fresh-launch CPU context

Register telemetry exposed inherited MSX BIOS context: IX/IY and the alternate
register bank differed even though the initialization RAM snapshot matched.
Bootstrap now initializes all ten general register pairs before original reset:
main AF=`$0040`, BC/DE/HL=0, IX/IY=`$ffff`, alternate AF/BC/DE/HL=0. These are
the fresh-device values in the
[pinned MAME Z80 implementation](https://raw.githubusercontent.com/mamedev/mame/f34f02505e32c1993c6a782b6814232cbfc74e36/src/devices/cpu/z80/z80.cpp),
not values copied from a game snapshot. This contract applies to fresh launch;
MAME soft reset itself retains general registers. Host I/IM remain host-owned.

Acquisition checks every pair at original reset entry and requires
`boot-registers.json`; missing, malformed, boolean or BIOS-derived values fail.
Read-only `registers.tsv` records initialization and first IRQ boundaries in both
emulators. Reference 12 repeats all 2,442 reference-11 snapshots byte for byte.
At game initialization, IX/IY and alternate pairs now match; main A still differs.

`issue20-cpu-boot-{50,60}` and `issue20-cpu-replay-{50,60}` contain the latest
explicit optimized candidates and complete acquisitions. Both retain exact
6,536-byte reset state, unchanged mapped code and contributor inputs, one coin
transfer, 2,440 publications, maximum queues 3/1 and empty final queues. Minimum
SP is `$83d6`; maximum IRQ-entry-to-publication clocks are 23,679/23,535.
Player-update counts are 5,123/5,056 versus reference 5,607. Strict comparison
still fails at publication 1: first addresses `$83e6`/`$83ea` at 50/60 Hz.
No exclusion or delayed comparison boundary is applied. Coordinate optimization
remains disabled by default; graphics and #20 completion remain gated.

Current validation: 59 native checks and 219 full-suite tests pass
(`full-suite-task4-cpu-boot.log`, 34.283 seconds). Independent review found no
Important/Critical defects in register setup or evidence checks and confirmed
the fresh-launch/soft-reset distinction. No commit, push, PR or issue closure.

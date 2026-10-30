# Engineering lessons from the port

This is a reusable technical synthesis, not an archive of attempts. Source links
identify the implementation; linked measurement documents preserve the original
workloads/hashes. Raw experiments were deleted at the user's request. Reported
machine results are emulator results; human visual/audio acceptance and physical
hardware qualification remain distinct.

## Preserve rules; adapt hardware boundaries

Keep native coordinates, flag/rock placement and game-state semantics separate
from the MSX viewport and hardware representation. Preserve original-size tiles,
fonts and complete car drawings. The smaller viewport changes presentation, not
world geometry. The original56x8 wordmark is an input asset, not replaceable text.

The current build combines generators with a verified pinned session source
view; it is not a straight assembly of one source tree. Inspect
[`game_build.py`](../src/toolchain/screen4/game_build.py),
[`session_build.py`](../src/toolchain/screen4/session_build.py) and
[`build_profiles.py`](../src/toolchain/screen4/build_profiles.py). Text transforms work in
the generated view and fail on changed anchors. Silent partial substitutions
would produce plausible but incorrectly bound cartridges.

Reuse the hardware mechanism when its contract fits. Supply another game's
native adapter instead of adding runtime branches to a general callback system.
An assembly INCLUDE boundary can be free; a runtime abstraction is not.

## Spend ROM bytes without adding foreground work

The accepted size reduction reused byte-verified pattern/color tables as transfer
sources and placed code/cold replay into protected bank gaps. It retained the
same hot instruction sequences, instead of introducing runtime decompression.
Equal bank hashes or FF tails identify candidates, not proof of dead storage.
All consumers and addressed ranges still need auditing.

See [`hud_programs.py`](../src/toolchain/screen4/hud_programs.py),
[`rom_pack.py`](../src/toolchain/screen4/rom_pack.py),
[`cartridge_size.py`](../src/toolchain/msx/cartridge_size.py) and the
[recorded reduction](issue36-size-reduction.md). The image became125 ASCII16
banks,2,048,000 bytes. The current hard ceiling is2MiB, with no4MiB fallback.
Publication validates alignment/size before replacing the last good cartridge.

## RAM capacity is an aliasing problem

A successful OUT to a mapper port does not prove another physical bank exists.
The original low-memory failure could alias graphics storage onto the stack.
Readback bits alone are therefore insufficient as a capacity probe.

[`session-auto.inc`](../src/screen4/session-auto.inc) executes its probe from
Page3 while surveying Page0. It saves bytes, writes distinct markers, counts
independent banks and restores writes in reverse order. Reverse order unwinds
aliases correctly; both original bytes and FC mapping must survive the probe.
Cold allocation then excludes main Page0 and Page3/stack from private segments.
The mechanism assumes the supported standard mapper geometry; it is not a
general search for RAM across every slot.

The64KiB path caches only the needed radar state rather than reserving the
expanded profile's banks. With128KiB or more, the cartridge selects the expanded
flag cache once. Writable public entries are patched to resident implementations
because those implementations switch Page0. See
[`session_auto.py`](../src/toolchain/screen4/session_auto.py),
[`session_ram64.py`](../src/toolchain/screen4/session_ram64.py),
[`session-ram64-flags.inc`](../src/screen4/session-ram64-flags.inc) and
[RAM/cache contracts](ram64-variant.md).

Cache validity belongs to a lifetime, not merely an address. New rounds invalidate
the expanded cache; a challenge UI return must reuse the current collected-flag
state. SCREEN5 UI owns VRAM, so the low-memory VRAM cache must be rebuilt after
returning to SCREEN4. Additional RAM does not authorize larger caches or changed
game rules.

## A displayed buffer is never a cache victim

The packed SCREEN4 presenter has eight16KiB pattern sets. Phase selection first
tries an exact inactive match or an unused set, then ranks inactive candidates
using precomputed transfer costs. Even an exact phase match does not allow
writing the visible set. Cold prewarming trades bounded startup work for smaller
first-turn costs; repeating it during active play would create recurring stalls.

Owners: [`session-phase.inc`](../src/screen4/session-phase.inc),
[`session-banks.inc`](../src/screen4/modules/renderer/session-banks.inc),
[`game-main.inc`](../src/screen4/game-main.inc) and the
[renderer contracts](../src/screen4/modules/README.md). Native descriptors, sprite
attributes, camera and terrain must publish as a coherent snapshot. Keep the
real sprite-per-scanline limit enabled; culling is a hardware constraint, not
permission to truncate car art.

## CPU turbo requires a boundary, not a blanket clock change

Only selected logic/actor computation runs accelerated. VDP/PSG/input work,
menus, cold transitions and synchronization retain base timing. Boot detects a
backend once; unsupported hardware takes the original loop without a recurring
capability branch. `TURBO ON` describes available scoped acceleration, not a
permanently accelerated machine. Ren-sha/autofire and emulator throttle are not
CPU capability evidence.

On turboR, calling0180 blindly is unsafe when Page0 is RAM. The bridge executes
from Page3, exposes the qualified BIOS slot, calls CHGCPU and restores mapping.
CHGCPU leaves IM1, so restore IM2 before restoring the caller's interrupt state.
Preserve register/IFF/stack ownership; unconditional EI would break a DI caller.
See [`session_turbo.py`](../src/toolchain/screen4/session_turbo.py),
[`session-turbo.inc`](../src/screen4/session-turbo.inc) and the
[CPU/mapper measurements](issue39-software-turbo.md).

The emulator compares observed CPU/controller state and elapsed execution time;
a status flag alone is not acceleration proof. ROM/DRAM modes have different
memory assumptions. An R800 gain in internal RAM does not imply the same gain
for an external cartridge, and switching/BIOS overhead must be included.

## Timing measurements need ownership and units

Physical refresh, game ticks and presented frames are separate rates. Distinguish
the full refresh, drawing phase, usable blanking interval and synchronization
wait. The5,000-cycle VBlank reserve remains a planning assumption, not a measured
universal hardware limit. A faster CPU need not increase FPS if work still lands
on the same publication boundary.

Inclusive costs contain children. Self costs subtract tracked children, and
untracked work remains visible. Never sum parent and child inclusive totals.
Mixed-clock ledgers use elapsed guest time; legacy cycle fields expressed as
seconds times3,579,545 reference Hz are not actual R800 instruction counts.
Keep mean, p95, maximum, late-frame fraction, calls/presentation and waits with
the exact ROM hash and population. Compare identical workloads without claiming
they followed identical trajectories when timing altered the active partition.

Owners: [`session_profile_adapter.py`](../src/toolchain/screen4/session_profile_adapter.py),
[`session_report.py`](../src/toolchain/screen4/session_report.py),
[timing ledgers](measurements/timing/README.md). Old SCREEN5 renderer measurements
and later SCREEN4 measurements are different workloads, not interchangeable FPS
claims. Launching an emulator is not a benchmark or whole-game acceptance.

## Native audio and transitions are state protocols

Silence the real PSG and invalidate cached register/effect debt before blocking
map/video work. Preserve the native request that controls completion. Round
settlement waits for both its minimum interval and the melody-ready condition;
an arbitrary fixed delay can cut music or start fuel conversion early. Yield
through normal ticks rather than adding HALT/spin inside the completion helper.

See [`stop-completion.inc`](../src/screen4/modules/audio/stop-completion.inc) and
[the audio contract](issue13-audio-interface.md). The first-stage and full-session
audio implementations share some label names but have different event/bank
ABIs. Include the correct binding, never both by name alone.

Motion rollback also has a lifetime. Snapshot before a doubled native step can
enter a corner-risk band; heading changes can change the contact cell. The
conservative guard in [`session_ram64.py`](../src/toolchain/screen4/session_ram64.py) and
[`input/motion.inc`](../src/screen4/modules/input/motion.inc) retains the documented
margin. A narrower predicate failed a long route; a short directional sample
cannot justify removing that guard.

## Dynamic boot overlays require page history

Offline boot pixels do not include runtime mapper/turbo text. Track which hidden
page received that overlay and force the text rectangle to be rewritten before
reusing it. Comparing only consecutive reference images leaves stale digits on
the other page. Use original glyphs and verify all pixels outside the authorized
rectangles against the original oracle. Owners:
[`session_boot.py`](../src/toolchain/screen4/session_boot.py),
[`session-auto-status.inc`](../src/screen4/session-auto-status.inc) and
[`test_session_boot.py`](../src/toolchain/screen4/test_session_boot.py).

## Tests and retained evidence can be wrong too

Synthetic writes must occur at a defined stable boundary. The two-player fixture
once forced a completed death between a turbo guard and its logic call, creating
a transition the real state machine would not make there. Moving the fixture
to a base-CPU frame boundary fixed the test; production code was not weakened
to accommodate it. Numeric PC aliases in banked RAM/ROM also require mapping
guards before injecting state or counting calls.

Record failed hypotheses and the corrected invariant. Keep concise test results,
source/ROM hashes and reproduction commands, then delete dumps, videos and build
copies. Moving80GB to an archive does not solve a disk budget. Source exports
must link only approved input roots, never recursively import all of references/.
The current policy and deletion record are in [artifact-layout.md](artifact-layout.md)
and [artifact-retention.json](artifact-retention.json).

## Other documented investigations

These notes preserve additional work without retaining its raw experiments.
Read each note's date, presenter and ROM hash before applying its conclusions
to the current cartridge; a historical optimization is not current acceptance.

| Investigation | Maintained knowledge | Reuse question |
| --- | --- | --- |
| Bitmap/blitter alternatives | [Bitmap experiments](bitmap-blitter-experiments.md), [tile-mode feasibility](tile-mode-feasibility.md) | Does the target's transfer/setup budget justify that representation? |
| Exact scenery transfer | [Solid cache runs](solid-cache-runs.md), [rock atlas](rock-atlas-performance-fix.md) | Which immutable spans can be reused without changing original art? |
| Actor count and hardware limits | [Enemy rendering](enemy-rendering-performance.md), [sprite flicker](sprite-flicker-experiment.md) | What belongs to hardware culling versus game logic/population? |
| Radar scheduling | [Radar work budget](radar-work-budget.md), [radar motion](issue12-radar-motion.md) | Which producer/consumer state must publish together? |
| Event presentation | [Death pipeline](death-presentation-pipeline.md), [effect publication](issue12-effects-publication.md) | Which bounded transition owns deferred work and scratch? |
| Score/fuel work | [Score updates](score-performance-fix.md), [fuel updates](fuel-performance-fix.md) | Which work is event-driven instead of repeated on every frame? |
| Native comparison | [Runtime contracts](native-runtime-contracts.md), [acquisition](native-runtime.md) | Are snapshots at the same logical boundary, including nonreturning IRQ paths? |

The comments and contracts in current source remain the authority for linked
behavior. Consult a historical note for its reasoning, not as an alternate
unversioned specification of the current memory layout.

## Exercise the missing-input path

A successful warm build does not prove that another developer can reproduce it.
Prepare from only the contributor ROM set, with `assets/arcade` and disposable
source caches absent, then compare the resulting ROM hash against the warm
baseline. This exposed a missing `Path` import in the original rock acquisition
branch, which cached bundles had hidden. The preparation contract now runs before
both presenters and blocks the linker/launcher on invalid inputs. Synthetic
first-acquisition tests complement the actual headless-MAME regeneration check.
See [build preparation](../src/toolchain/graphics/prepare.py) and
[first-build instructions](building.md).

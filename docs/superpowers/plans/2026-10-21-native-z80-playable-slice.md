# Original-Z80 Playable Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution in the current chat. Steps use checkbox (`- [ ]`) syntax for tracking. The user requested staged execution using sub-issues #17–#23 of #11; no implementer subagents are planned.

**Goal:** Build and verify a silent, locally playable original-Z80 first-stage segment on a standard-speed MSX2+.

**Architecture:** Preserve original program/state addresses in RAM and adapt guarded hardware boundaries. Keep host interrupts, stack and renderer resident; borrow the game-state window for preloaded assets only while native execution is suspended. Establish reset and state equivalence before connecting mutable scenery and gameplay actors.

**Tech Stack:** Existing Python 3.14/Pillow environment, sjasmplus 1.24.0, Z80 assembly, MAME 0.289 Lua and openMSX Tcl; no new product dependency.

**Spec:** [Approved design](../specs/2026-10-21-native-z80-playable-slice-design.md).

## Global Constraints

Acceptance amendment approved by the user on 2026-10-21: prioritize the playable
port with original logic/rules, documented temporal differences, and behavioral,
control and performance validation. Strict arcade RAM comparison remains a
diagnostic and must keep reporting its actual failures. It no longer blocks
Task 6. Safety, 1:1 graphics, source integrity, exact logical cadence and measured
rendering budgets remain required. See the amendment in the approved design.

- Standard-speed MSX2+, **at least 128 KB RAM mapper and 128 KB VRAM**; session-local `Panasonic_FS-A1WSX_NR128` reference machine.
- Original 8x8 tiles and 16x16 sprites at 1:1 scale; 256x212 output; original world coordinates and game rules.
- One logical tick per 16.5 ms, independently of 50/60 Hz display refresh; no dropped ticks or speed compensation.
- Original program `$0000..$3fff`, renderer `$4000..$7fff`, original state `$8000..$bfff`, host `$c000..$ffff`.
- P1/P2/DIP snapshots `$a200..$a202`; reserve startup padding `$a188..$a1ff` and original stack overlap below `$8400`.
- Four 16 KB runtime mapper segments plus four 16 KB asset/staging segments. Discover ownership; never hardcode physical segment IDs.
- Contributor ROMs/BIOS only. All original/derived payloads and captures remain ignored under `references/`; authored fixtures contain synthetic data only.
- No commit, push, PR, merge or issue closure is authorized by this plan. Replace skill-template commit steps with local review checkpoints.
- Keep the current diagnostic available until the native path passes acceptance. A failing build cannot replace a valid default cartridge.

## Review Focus

- A valid hook digest with the wrong full program, an operand boundary, or a later invalid patch must reject the entire patch set (Task 1).
- A resource mapping interrupted at an inconvenient time must never expose asset data as game RAM or corrupt either stack (Tasks 3–4).
- Input edge timing and long-running 50/60 Hz remainder accumulation must not drift or duplicate coin/start events (Tasks 2 and 4).
- A removed flag underneath overlapping moving actors must remain removed after scrolling, clipping and background restoration (Task 6).
- Missing/truncated/phase-shifted evidence, a missed raster event or a failed build must fail clearly rather than appear equivalent/published (Tasks 2, 5 and 7).

## File and interface map

New Python modules under `src/toolchain/msx/` have these responsibilities:

| File | Responsibility |
| --- | --- |
| `native_patch.py` | Pure whole-program and transactional patch validation |
| `native_layout.py` | CPU allocations, mapper asset packing and generated layout metadata |
| `native_contract.py` | Pure input, cadence, snapshot and difference contracts |
| `native_build.py` | Local native cartridge preparation, assembly and sealed output |
| `native_verify.py` | Isolated emulator acquisition, comparison and acceptance reports |
| `native_scene.py` | Read-only native-state presentation model and independent pixel oracle |

New assembly units are `src/native.asm` (boot/resident entry),
`src/native-loader.inc` (slots/mapper/preload), `src/native-runtime.inc`
(original context, input, game IRQ and publication), `src/native-video.inc`
(live map/actors), and `src/native-state.inc` (host allocations and event IDs).
Use existing HUD/raster includes; do not copy the entire diagnostic into a second
unmaintainable renderer. Modify `src/stage-one-stream.inc` to expose live tile
source/cache invalidation while retaining its diagnostic producer.

`src/toolchain/msx/native_verify.tcl` and `src/toolchain/msx/native_reference.lua` are authored
emulator harnesses. `src/toolchain/legacy/native_runtime.py` exposes native CLI commands.
Keep generated configs, symbols, bytes and raw reports in fresh ignored outputs.

## Task 1: Guarded patching and complete allocation validation

**Files:** Create `src/toolchain/msx/native_patch.py`, `src/toolchain/msx/native_layout.py`,
`tests/test_native_patch.py`, `tests/test_native_layout.py`; extend
`src/toolchain/legacy/z80_hooks.json` only when new spans have actual reference evidence.

**Interfaces:**
- `Patch(address: int, expected_sha256: str, replacement: bytes, continuation: int)` is a frozen record. Replacement length equals the guarded span length.
- `apply_patches(image: bytes, expected_sha256: str, patches: tuple[Patch, ...], boundaries: frozenset[int]) -> bytes` returns a new complete image or raises `ValueError`.
- `Region(name: str, start: int, end: int)` uses half-open CPU ranges.
- `validate_layout(regions: tuple[Region, ...]) -> None` rejects invalid, duplicate or overlapping allocations.
- `pack_assets(resources: dict[str, bytes], capacity: int = 65536) -> tuple[bytes, dict[str, tuple[int, int]]]` returns four padded 16 KB segments and resource offset/length metadata; reject overflow, do not truncate.

- [x] Write synthetic tests for full-image hash rejection, guarded-span mismatch, partial-instruction endpoints, overlapping patches, invalid continuations, length changes and a failing second patch. Assert the input remains byte-identical after success and failure; assert a valid synthetic CALL replacement changes only the approved span.
- [x] Write allocation tests for half-open adjacency versus overlap, host/game ownership conflicts, duplicate names, a resident image exceeding `$8000`, exactly 65,536 asset bytes and overflow by one byte.
- [x] Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_native_*.py' -v`; confirm the new tests fail before implementation.
- [x] Implement the pure contracts. Reuse `program_image`, ROM validation and existing guard behavior; do not infer that a linear disassembly proves all executed boundaries. Require continuation addresses to be evidenced original boundaries; validate stub destinations through the layout contract.
- [x] Re-run those tests to PASS. Review a local allocation/patch report generated from validated contributor inputs; commit no original bytes or instruction text.

Local evidence: 19 new synthetic checks and the full 176-test suite passed.
Identity-patch validation covered all 11 candidate hooks/11 reserved regions;
source inputs unchanged. See `docs/native-patching.md`. #17 remains open pending
review/delivery; no native gameplay or final linked asset-fit claim is made.

## Task 2: Exact clock, inputs and differential-record contracts

**Files:** Create `src/toolchain/msx/native_contract.py`, `tests/test_native_contract.py`.

**Interfaces:**
- `advance_clock(remainder: int, elapsed_cycles: int) -> tuple[int, int]` returns `(due_ticks, remainder)` with `total = remainder + elapsed_cycles * 2000` and division by `3579545 * 33`; reject negative values and a remainder outside the divisor.
- `input_bytes(pressed: frozenset[str], dip: int) -> bytes` returns exactly P1/P2/DIP active-low bytes. Names are `coin`, `start`, `up`, `down`, `left`, `right`, `smoke`; derive coin/start/smoke wiring from the pinned driver and capture evidence, not guessed masks. Preserve simultaneous direction bits.
- `Snapshot(tick: int, phase: str, video: bytes, work: bytes, shadows: bytes)` requires lengths 4096, 2048 and 392. Phase is `pre-game-irq` or `post-game-irq`; comparisons require an explicitly aligned phase.
- `Exclusion(address: int, reason: str, evidence: str)` permits only one documented byte at a time; reject duplicates, empty reasons and out-of-snapshot addresses.
- `first_difference(expected: Snapshot, actual: Snapshot, exclusions: tuple[Exclusion, ...] = ()) -> dict | None` returns the first mismatch with tick, region, address, expected and actual; reject mismatched phase/tick or malformed records.

- [x] Write tests proving 100,000 frames at both `313*228` and `262*228` cycles produce exactly `floor(total_cycles*2000/(3579545*33))` ticks and the exact remainder. Assert both one- and two-tick 50 Hz refreshes occur; no floating-point resampling.
- [x] Test idle/direction combinations, coin/start press and release sequences, invalid key/DIP values, and independence of the sound/radar shadows from input bytes.
- [x] Test first-difference addresses in all three regions, including `$9800` and `$a000`, exact single-byte exclusions, missing/truncated snapshots and tick/phase mismatch. Identical snapshots must return `None`.
- [x] Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_native_*.py' -v`; observe failure, implement contracts, then re-run to PASS. Check native assembler arithmetic can reproduce the same clock vectors without overflow; allocate sufficient accumulator width in Task 3.

Local evidence: 14 new contract tests, 33 native checks and the full 190-test
suite passed. The sjasmplus constant/arithmetic probe passed without warnings;
reserve a 32-bit accumulator in Task 3. Actual native arithmetic execution and
acquisition phase proof remain Tasks 4–5 gates. See `docs/native-runtime-contracts.md`.

## Task 3: Native cartridge loader and isolated memory proof

**Files:** Create `src/toolchain/msx/native_build.py`, `src/native.asm`,
`src/native-loader.inc`, `src/native-state.inc`, `tests/test_native_build.py`,
`tests/fixtures/native-loader.asm`;
reuse `src/toolchain/msx/emulator.py`, `mapper_reference.tcl` and storage helpers.

**Interfaces:**
- `build(root: Path, args: argparse.Namespace) -> Path` accepts `output`, `assets`, `captures`, `normal`, `overlap`, `assembler`, `hz`, `logic_only`; produces `native.rom`, generated includes, symbols, allocation/patch metadata and a sealed manifest in a fresh `references/build/` directory.
- `Native_Boot` performs BIOS-visible setup/copy/preload, discovers mapper segments and RAM slots, switches to resident mapping, then enters `Native_Reset` (Task 4).
- `Native_MapAssets` / `Native_RestoreGame` are host-only calls. The first requires suspended native execution; both preserve interrupt-visible resident mappings.
- Generated `native-layout.inc` is the sole source for new allocations. Existing HUD/vector/stack reservations remain protected. Export event and symbol addresses for verification; do not hardcode them in the harness.

- [x] Add failure tests for unsafe/existing/symlink/tracked output, unsupported ROMs and asset overflow before publication. Reuse current path protection rather than introducing weaker rules. Assert no missing-input build publishes a valid-looking manifest or replaces the current default ROM.
- [x] Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_native_*.py' -v`; observe failure and implement build orchestration using Tasks 1–2. Initially build `tests/fixtures/native-loader.asm`, which includes the real loader and supplies a synthetic `Native_Reset` probe entry; it needs no Task 4 runtime or original gameplay bytes. Do not publish that fixture as a native gameplay build.
- [x] Assemble the synthetic loader and execute it in isolated openMSX: verify eight independent 16 KB segments, page-0 RAM with BIOS hidden, page-1 resident code, page-2 state restoration, asset reads and unchanged page-3 canaries/stack. Fail clearly with less than 128 KB mapper.
- [x] Repeatedly switch asset/state segments with host IRQs active; verify complete register/stack/segment restoration. Record initial slot state and test the selected reset restoration path. Inventory real resources and prove they fit the four asset segments.
- [x] Re-run Task 3 tests to PASS; review assembly/map/symbol and real machine evidence. Do not proceed on loader, capacity or overlap failure.

Local evidence: `docs/native-loader.md`; positive proofs at 50/60 Hz and with
relocated host segment 5, stock 64 KB refusal, 256 switches/257 IRQs and actual
machine reset per positive run. The 48,596-byte inventory fits four asset
segments; unchanged original program bytes are loaded but not executed. All
stage-3 builds are explicitly loader probes until Task 4 supplies original reset.

## Task 4: Original reset, foreground execution and logical IRQs

**Files:** Create `src/native-runtime.inc`, `src/toolchain/msx/native_reference.lua`,
`src/toolchain/msx/native_verify.tcl`, `src/toolchain/msx/native_verify.py`,
`tests/test_native_runtime.py`; extend `native_build.py` and guarded metadata.

**Interfaces:**
- `Native_Reset` initializes host scheduling/inputs and enters a trace-verified reset-only original initialization path. No captured game snapshot is linked into the ROM.
- `Native_HostIRQ` acknowledges host sources on the separate host stack; preserves all native main/alternate registers and interrupted PC/SP.
- `Native_GameIRQ` enters the guarded `$01f0` path and reaches `Native_Publish` via the verified `$0468` adapter; restores original foreground context. `$0c2c` is never treated as returning.
- `Native_Publish` emits a monotonically numbered logical-tick event after completing the game IRQ and freezes the state publication consumed by presentation. A separate busy flag prevents nested game IRQs.
- `acquire(root: Path, args: argparse.Namespace) -> Path` accepts a sealed native `rom`, `output`, local `bios`, `machine`, `openmsx`, `reference`, `replay`, `frames`, `hz`, `headless`; produces snapshots/events/input logs, runtime hashes and explicit completion markers.

- [ ] Add synthetic assembly/harness cases with known main/alternate register patterns, original/host stack canaries, game IRQ mask changes, EI/DI transitions, due-tick backlog and reset/input edges. Exercise an IRQ during asset suspension. Assert preservation and that a suspended native IRQ is deferred rather than executed against assets.
- [ ] Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_native_*.py' -v`; observe failure, then implement adapters and harness generation. Use assembler-backed or emulator checks for register behavior; Python mocks alone do not prove it.
- [ ] Inspect fresh local reset/execution evidence to select the post-cabinet-diagnostic transition and its required initialization effects. Add guarded spans for every new reset/IM/vector/input/ROM-write adapter. Verify full-program integrity and indirect input reads. Prove `$040f` discarded-write flags/read semantics with synthetic emulator cases.
- [ ] Boot the real logic-only cartridge from reset, insert coin and start through the original debounce path. Record stack high-water marks, worst host IRQ latency, native foreground/IRQ cycles and masked IRQ behavior; assert BIOS calls cease after native mapping.
- [ ] Capture arcade evidence at matching logical boundaries. First prove reset/coin/start state equivalence, then the initial stage. Any nonreturning path, diagnostic dependency or unexplained divergence stops progression to graphics.

**2026-10-21 local checkpoint:** Reset-only source initialization now matches
all 6,536 reference bytes with no exclusions. The separate host IRQ stack and
1,024 discarded-write flag/readback cases pass real synthetic emulator probes
at 50/60 Hz and with host segment 5. Fresh original execution proves a coin
IRQ transfer that never reaches the normal epilogue; it requires an explicit
transfer/publication adapter, not restoration of the abandoned foreground.
`Snapshot` now distinguishes initialization and IRQ-transfer publication.
Original game IRQ delivery, virtual EI/DI, direct/indirect inputs, logical
HALT/busy waits and normal/transfer publication are now installed in an explicit
candidate. Real synthetic proofs cover 100,000-frame cadence, 64 gates, backlog
drain and three wait/poll cases at 50/60 Hz and displaced host segment 5.
Complete original-input acquisitions finish 2,440 IRQs at both refresh rates,
but strict state comparison fails from publication 1 and later live foreground
progress also differs. No exclusions or comparison-boundary relaxation have
been applied. Source/resident copies remain intact; 56 native checks and 216
full-suite tests pass. See `docs/native-runtime.md` for measurements and ignored
evidence paths. Task 4 remains in progress; its equivalence gate is not complete.

Further checkpoint: fixed-clock acquisition now verifies the openMSX frequency
lock is disabled. Byte-identical repetitions ruled out the former lock omission
as the divergence cause. Mask telemetry localized queue growth during scenario
generation; a guarded row-end poll and exact nonempty-cache fast path reduced
the 50 Hz maximum queue from 13 to 3, with 60 Hz still 1. Full 2,440-tick acquisitions
complete and synthetic 50/60 Hz/host-5 proofs check queue-cache borrow 256→255.
Foreground player-update counts improve to 5,017/4,967 versus arcade 5,607; exact
phase/state and latency acceptance remain open, with no exclusions applied.

Latest checkpoint: a bounded read-only profiler led to an optional coordinate
loop adapter, disabled by default. Its independent original-function oracle
passes 131,072 A/L/carry cases with identical AF/HL and 18.23% fewer function
clocks at both refresh rates. Fresh-launch register setup removes inherited
BIOS IX/IY/alternate state using the reference CPU startup contract, without
seeding game RAM. Real boot telemetry verifies all ten register pairs. Latest
optimized 2,440-tick captures at 50/60 Hz retain exact reset, intact code,
maximum queues 3/1 and empty final queues; player updates are 5,123/5,056 versus
source 5,607. Strict state still differs from publication 1. No exclusions,
boundary relaxation or default promotion. Current validation: 59 native checks,
219 full-suite tests; independent review reports no Important/Critical defects.
See `docs/native-runtime.md` for evidence and the fresh-launch reset limitation.

## Task 5: Reproducible replay, comparison and phase proof

**Files:** Extend `native_reference.lua`, `native_verify.tcl`,
`native_verify.py`; create `tests/test_native_verify.py`.

**Interfaces:**
- `verify(root: Path, args: argparse.Namespace) -> dict` runs acquisition/comparison and returns the report only after explicit completion, hash, snapshot and timing checks. A failure writes local diagnostics and raises `ValueError` or the subprocess failure; CLI exits nonzero.
- Evidence records have schema version, machine/tool/source/program hashes, tick and phase, input schedule identity, completion count, snapshot lengths and exact exclusions. `comparison.json` reports first divergence or zero differences; it cannot omit absent frames.
- The reference harness consumes the same validated replay events as MSX at the documented logical boundary. Existing pre-IRQ data is reused only after proving its alignment with the new port samples.

- [ ] Add synthetic tests for missing final marker, missing/extra/tampered snapshot, mismatched reset/DIP/replay/hash, emulator timeout, wrong phase and one excluded byte beside a real divergence. Assert a partial run cannot produce a passing report.
- [ ] Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_native_*.py' -v`; observe failure and implement strict evidence loading/comparison using Task 2 and current sealing helpers.
- [ ] Run two fresh arcade acquisitions and prove deterministic payload equality. Run the logic-only MSX port with the existing 3,200-frame schedule. Compare 4 KB video, 2 KB work RAM, hardware shadows and named semantic fields after phase alignment; document every excluded byte individually.
- [ ] Exercise both 50 and 60 Hz display modes with identical logical input schedules. Compare logical results, not equal display-frame numbers. Verify coin/start are applied once, mute does not change state and source/patched-program/BIOS hashes remain unchanged.
- [ ] Re-run Task 5 tests to PASS and record actual replay counts, mismatch results, stack and timing evidence. Do not connect live rendering until this logic gate passes.

## Task 6: Mutable scenery, actor composition and live HUD

**Files:** Create `src/toolchain/msx/native_scene.py`, `src/native-video.inc`,
`tests/test_native_scene.py`; modify `src/stage-one-stream.inc`,
`native_build.py`, `native-runtime.inc` and `native_verify.py`; reuse HUD API.

**Interfaces:**
- `scene_from_snapshot(snapshot: Snapshot) -> dict` returns immutable logical camera, native actor descriptors and HUD/radar values; reuse `hud_contract.native_values(snapshot.video)` for HUD semantics. Reject invalid required pointers; do not invent live values from diagnostic fixtures.
- `dirty_regions(previous: tuple[tuple[int, int, int, int], ...], current: tuple[tuple[int, int, int, int], ...], viewport: tuple[int, int, int, int]) -> tuple[tuple[int, int, int, int], ...]` uses half-open world rectangles, clips to viewport and retains old/new restoration bounds. Preserve coverage when merging overlaps.
- `compose_scene(world: bytes, width: int, height: int, actors: tuple[dict, ...], camera: tuple[int, int], palette: bytes) -> PIL.Image.Image` is the independent pixel oracle; actor records include world bounds, original indexed pixels, transparent pen, flips and draw order.
- `Native_PrepareFrame` reads only published host state; `Native_DrawFrame` restores dirty regions from the live map, draws bitmap actors and updates existing player/HUD presentation. The stage streamer gets a live tile-read/invalidate entry rather than accessing immutable original map data directly.

- [ ] Write synthetic pixel tests for old/new bounds, partially offscreen actors, both flips, transparency versus opaque black, overlapping enemies/smoke and scrolling. Assert every restored pixel equals a fresh full composition.
- [ ] Test collecting a flag under two overlapping actors, moving them away, scrolling out and back: the flag must never reappear. Test malformed pointers and unchanged game-state input buffers.
- [ ] Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_native_*.py' -v`; observe failure and implement the oracle/live-map contracts, then the Z80 presentation adapter.
- [ ] Link actual resources within the proven asset/VRAM allocations. Validate palette fit and bitmap command costs before accepting additional actors; do not silently omit enemies, smoke or death frames. Keep raster IRQ/VDP packets atomic during resource switches.
- [ ] Run RGB/cache comparisons against committed native state for normal movement, actor overlap, flags, smoke and death; verify HUD/radar reflect actual state. Repeat Task 5 differential verification with rendering enabled and game RAM unchanged by presentation.
- [ ] Re-run relevant existing scene/player/HUD/raster tests and the new tests. Record original pixel dimensions, clipping/latency policy and real VDP timing results.

## Task 7: Commands, acceptance scenarios and delivery evidence

**Files:** Create `src/toolchain/legacy/native_runtime.py`, `docs/native-playable-slice.md`,
`tests/test_native_cli.py`; modify `scripts/project.py`, `Makefile`, `README.md`,
`.github/issues/native-z80-playable-slice.md` and `native_verify.py`.

**Interfaces and reproducible entry points:**
- `python -B src/toolchain/legacy/native_runtime.py build --output <fresh-build-dir> --hz {50,60} [--logic-only]` uses existing repository defaults for local assets/assembler; explicit path overrides follow the existing renderer CLI conventions.
- `python -B src/toolchain/legacy/native_runtime.py run --rom <sealed-bundle>/native.rom --output <fresh-run-dir>` reuses the isolated emulator launcher; keyboard `5` coin, `1` start, arrows steer, Space smoke; joystick 1 direction/trigger A steer/smoke.
- `python -B src/toolchain/legacy/native_runtime.py verify --rom <sealed-bundle>/native.rom --reference <reference-dir> --replay <input-json> --frames 3200 --output <fresh-verify-dir> [--headless]` executes Task 5 and render/timing gates. Validate required paths/options; headless runs cannot claim RGB verification.
- All commands default to contributor BIOS under `references/msxbios/` and the session-local reference machine; expose explicit BIOS/machine overrides.

- [ ] Test CLI error status, unsafe paths, unsupported Hz, missing ROM/BIOS/reference and headless report limits. Test that native publication is atomic and any failed build leaves the old default byte-identical. Observe failures before implementing wiring.
- [ ] Implement CLI/make integration; keep a named diagnostic build/run entry. Switch default build/run to native only after the following acceptance checks pass.
- [ ] Run 3,200-frame differential/render verification on the reference machine. Add replay events and measured coverage for any missing flag collection, enemy interaction, smoke, fuel/score change, collision/death and restart. Require evidence of each transition, not just that a replay ran.
- [ ] Report maximum cycles/time separately for original foreground/IRQ, translation, mapping/copies, actor/tile/HUD work and ISR. Verify header/footer/VBlank event counts/deadlines, real VDP command timing and zero accumulated update backlog, including two-update refreshes. A missed gate stops default publication and requires a recorded feasibility decision.
- [ ] Run `make test`, relevant real emulator checks, `git diff --check`, contributor input hash verification, and `git check-ignore` for generated payloads. Inspect `git ls-files references` and the complete diff to confirm no game payloads or original instruction bytes are tracked.
- [ ] Document actual commands/results, controls, machine/tool versions, exact state exclusions, scenarios and unsupported paths. Align the local issue draft and GitHub issue/project with 128 KB, work status and evidence using file-backed bodies. Keep #11 open/In review while delivery or review is pending.

## Execution and review checkpoints

At implementation start, move only #11 to the project's In Progress status and
associate the existing local branch `enhancement/11-native-z80-playable-slice`
with the issue using supported GitHub tracking. Keep priority P2 and milestone
unassigned. GitHub mutations follow the authoritative vault guidelines; no
long prose is embedded in shell commands.

Tasks run in order. Complete each task's synthetic checks and required real
integration evidence before checking it off; a written API or mocked test is not
a passing native-runtime gate. Update this plan with actual measurements and
evidence paths, keeping proprietary outputs ignored. Do not speculate that the
40-hour estimate or combined performance is confirmed by this plan.

Review checkpoints are patch/allocation safety (Task 1), native mapping (Task 3),
reset/IRQ/phase equivalence (Tasks 4–5), live pixels/performance (Task 6) and the
complete acceptance matrix (Task 7). If memory, equivalence or raster feasibility
fails, record the smallest reproducer and return for a focused architecture
decision rather than expanding scope or hiding the failure.

The written specification is approved. On 2026-10-21 the user requested these
stages as sub-issues and staged execution. Native execution in the current chat
is the recommended approach; begin #17 and advance in order. No commit, push or
PR is authorized. Track stages with #17, #18, #19, #20, #21, #22 and #23.

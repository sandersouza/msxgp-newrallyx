# Arcade Scene Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Capture real gameplay, reconstruct exact 288x224 references, and produce 256x212 layout proposals with SCREEN 4/5 constraint reports for issue #6.

**Architecture:** Lua records a coherent gameplay state and native reference; Python validates the bundle, composes indexed layers and compares RGB pixels. Layout and analysis consume that same state, with no changes to game logic or original asset dimensions.

**Tech Stack:** Existing Python 3.14/Pillow 13.0.0 environment, unittest, MAME 0.289 Lua API and Git output checks; no new runtime dependencies.

**Spec:** [Approved design](../specs/2026-10-20-arcade-scene-design.md).

## Global Constraints

- Source pin: `mame0289`, commit `f34f02505e32c1993c6a782b6814232cbfc74e36`.
- Native visible rectangle: X=[0,288), Y=[16,240), giving a 288x224 image.
- Preserve asset sizes, world coordinates, simulation state and original CPU execution.
- Compare all 288x224 RGB pixels with zero tolerance by default.
- Capture schema version 1; record hashes, source, frame identities, callback phase and inputs.
- Unknown initial register values or unsupported APIs invalidate the capture.
- Keep raw state, screenshots, replay data and derived images local under ignored references paths.
- Reject unsafe paths, symlinks, tracked or unignored destinations and existing output by default.
- Original plan: layout and SCREEN 4/5 selection required later user review.
  The user has since selected compact as the approved default; SCREEN-mode
  selection remains open. See the decision addendum in the design spec.
- Do not download ROMs, commit game data, push or publish without authorization.
- Keep work in this chat and dedicated branch `enhancement/6-arcade-scene-composition`.
- Move issue #6 to In Progress only when implementation starts; preserve unrelated project fields.

## Review Focus

1. Reset or a lost write tap must invalidate cached registers rather than capture stale scroll (Task 2).
2. A valid bundle paired with a different asset export must fail provenance validation (Task 1).
3. A one-frame state/image mismatch in a moving scene must fail exact comparison (Task 4).
4. HUD packing must fail if a required block is missing, cropped or overlaps another block (Task 5).
5. Transparent/clipped source objects and multicolor layers must not yield misleading hardware-entry counts (Task 6).

## File map and shared types

Create package `scripts/scenes/`, CLI `scripts/arcade_scene.py`, recorder
`scripts/scenes/capture.lua`, tests `tests/test_scene_*.py` and synthetic fixture
helpers `tests/scene_fixtures.py`. Keep extraction APIs unchanged. Add Make targets
and a focused `docs/arcade-scenes.md` guide.

- `bundle.py`: `Assets`, `Capture`, `load_assets(path: Path) -> Assets`,
  `load_capture(path: Path, assets: Assets) -> Capture`.
- `storage.py`: `publish_bundle(root: Path, destination: Path, writer: Callable[[Path], None]) -> None`.
- `render.py`: `Frame`, `Object`, `render(capture: Capture, assets: Assets) -> Frame`.
  `Frame` carries a 288x224 RGB image, final and background indirect-index
  buffers, shadow flags, priority buffer and decoded objects. Each `Object`
  carries kind, ID, native rectangle and per-pixel source color/opacity.
- `compare.py`: `compare(reference: Image.Image, actual: Image.Image) -> dict`.
- `layout.py`: `Layout`, `Preview`, `compose(frame: Frame, capture: Capture, layout: Layout) -> Preview`.
  `Preview` carries the image, background indices, transformed objects and transforms.
- `analyze.py`: `analyze(preview: Preview, assets: Assets) -> dict`.

### Task 1: Validated bundles and safe publication

**Files:** Create `scripts/scenes/__init__.py`, `bundle.py`, `storage.py`,
`tests/scene_fixtures.py`, `tests/test_scene_bundle.py`, `tests/test_scene_storage.py`.
Reuse metadata validation and synthetic Git-repository conventions from existing graphics code.

**Interfaces:** Implement `Assets`, `Capture`, `load_assets`, `load_capture` and
`publish_bundle` from the file map. No rendering or emulator dependency.

- [x] Write synthetic tests asserting video length 4096, radar length 16,
  unsigned register ranges, visible rectangle [0,16,288,240], source pin,
  schema version, required phase/frame identities and complete manifest hashes.
  Invalid versions, bool-as-integer fields, missing/extra payloads, bad hashes,
  foreign asset manifest and path traversal must raise `ValueError`.
- [x] Write storage tests asserting existing destinations remain byte-identical;
  symlink ancestors, case aliases of tracked paths and unignored paths fail;
  writer failure leaves no published bundle; concurrent publication is refused.
- [x] Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_scene_*.py'`;
  confirm new tests fail because the new modules are absent.
- [x] Implement the types and validation. Load source pens and palette from
  verified #1 exports. Restrict publication to this checkout's `references/scenes/`,
  stage on the same filesystem, write manifests last and publish without replacement.
  Reuse existing validation conventions without importing private extractor helpers
  or weakening its asset-only output contract.
- [x] Run the new tests; require all pass. No overwrite option in this initial workflow.

### Task 2: Coherent gameplay recorder

**Files:** Create `scripts/scenes/capture.lua`, `scripts/scenes/record.py`,
`tests/test_scene_record.py`; start `docs/arcade-scenes.md`.

**Interfaces:** `record.capture_gameplay(root: Path, assets: Path, output: Path,
replay: Path, frames: list[int]) -> None` launches MAME and publishes validated
case bundles via Task 1. Replay JSON uses frame numbers and named input-field values.

- [x] Inspect pinned Lua/screen/video/scheduler source and installed API for
  share reads, write taps, reset, input fields, frame callbacks and native bitmap
  extraction. Record exact source symbols establishing state/render ordering.
  Keep downloaded public implementation sources, if needed, under references.
- [x] Write launcher tests with a fake emulator: reject wrong versions, missing
  completion evidence, unknown register flags, differing state/bitmap frame IDs
  and reset without register reinitialization; preserve failed-run evidence locally.
- [x] Run the recorder tests and confirm expected failures before implementation.
- [x] Implement Lua share reads, retained write taps and input replay before relevant
  game execution. Do not modify ROM, video RAM or emulated CPU control. Obtain raw
  native pixels without filters and convert through existing Pillow in Python if needed.
  If autoboot starts too late for initialization, use the supported startup/plugin
  lifecycle rather than assuming missing registers are zero.
- [x] Demonstrate coherence using actual callback ordering and moving frames;
  store frame IDs, phase, register initialization and reset generation. If the
  installed API cannot establish coherence, stop production capture and report
  the concrete limitation before considering a patched MAME build.
- [x] Run fake-emulator tests; capture a fresh local gameplay bundle using input
  replay or a documented explicit trigger. Confirm unchanged source ROM hashes.

### Task 3: Indexed native renderer

**Files:** Create `scripts/scenes/render.py`, `tests/test_scene_render.py`.

**Interfaces:** Implement `Object`, `Frame`, `render(Capture, Assets) -> Frame`.
Consume Task 1 data; preserve separate background, priority and object data for analysis.

- [x] Add synthetic tests with hand-computed pixels for asymmetric flips, tile
  category, 256-pixel wrapping, foreground row stride 32/repetition, scroll offset
  3, visible Y origin 16 and normal/flipped foreground clips.
- [x] Add sprite/dot tests: descending sprite offsets 0x1e..0x14 by 2,
  sprite X high bit, Y=241-register, lookup-index-zero transparency, category
  occlusion and overlapping sprite priority; dot offsets 0x14..0x1f,
  X high bit inversion, Y=253-register, XOR-7 code and both shadow passes.
  Pin shadow RGB rounding from verified MAME behavior, including repeated overlap.
- [x] Run renderer tests and confirm missing implementation failures.
- [x] Implement rendering from the pinned `rallyx_v.cpp`, tilemap and drawgfx
  semantics. Resolve global flip behavior from source and tests; retain source
  object identity even when all pixels are offscreen or transparent.
- [x] Run renderer tests; require exact expected pixel/index/priority values.

### Task 4: Exact comparison and gameplay evidence

**Files:** Create `scripts/scenes/compare.py`, `scripts/arcade_scene.py`,
`tests/test_scene_compare.py`, `tests/test_arcade_scene.py`; extend usage guide.

**Interfaces:** `compare` returns mismatch count, half-open mismatch bounds,
maximum channel difference and fixed maze/HUD regional counts. CLI subcommands
`capture` and `reconstruct` use Task 1 publication and Task 2/3 APIs.

- [x] Write tests: identical images give count 0 and null bounds; one changed
  RGB pixel gives count 1, exact bounds and channel difference; wrong dimensions
  fail; CLI exits nonzero on any mismatch and retains diagnostic output.
- [x] Run tests to confirm failure, then implement exact RGB comparison and
  reconstruction/diff PNGs plus sorted JSON reports with no timestamps or absolute paths.
- [x] Run tests; locally capture normal gameplay and a distinct moving overlap/smoke
  scene. Inspect both reference and reconstruction. Record actual exercised features;
  repeat gameplay/replay selection if visible smoke or overlap is missing.
- [x] Require zero differences over all 288x224 pixels for both cases. Diagnose
  errors at the state, addressing, priority or palette layer; introduce no tolerance.
- [x] Pair moving-frame N's image with N+1's contributing state in a separate
  negative-control run. Require comparison failure and record its mismatch count.
- [x] Reconstruct each unchanged bundle twice into separate destinations; require
  identical image pixels and report bytes. Record exact replay/capture commands
  and local hashes, without publishing captured data.

### Task 5: Layout proposals with explicit transforms

**Files:** Create `scripts/scenes/layout.py`, `tests/test_scene_layout.py`;
extend CLI with `preview`; document layout source/destination rectangles.

**Interfaces:** Implement `Layout`, `Preview`, `compose(Frame, Capture, Layout)`.
Layout is a versioned JSON declaration with named required HUD blocks, maze
source/camera, source/destination rectangles and output [256,212].

- [x] Inspect real captures to identify score, fuel, lives, round and radar blocks;
  record every required block and exact native source rectangle in local layout metadata.
- [x] Test source/destination widths and heights are equal; missing required block,
  destination overlap, offscreen block or cropping of required information fails.
  Test negative camera positions, clipping, object alignment and unchanged input state.
- [x] Run layout tests to confirm failure; implement transforms and composition
  without resizing. Preserve background indices and transformed objects in `Preview`.
- [x] Build candidate A: maze [0,192)x[0,212), information [192,256)x[0,212),
  repacking semantic blocks rather than dropping rows. Build candidate B using a
  wider maze with individually relocated HUD blocks. Derive its exact packing
  from measured blocks; report infeasibility if a lossless packing cannot fit.
- [x] Run tests and produce previews from both gameplay bundles. Inspect full
  information coverage; emit rectangles, clipping, camera/world mapping and
  `proposal` status for the initial alternatives. The subsequent explicit user
  selection gives compact `approved` status and makes it the CLI/Make default.

### Task 6: SCREEN 4/5 constraint reports

**Files:** Create `scripts/scenes/analyze.py`, `tests/test_scene_analyze.py`;
extend CLI with `analyze` and document report assumptions.

**Interfaces:** `analyze(Preview, Assets) -> dict` returns whole/region/scanline
palette use, SCREEN 4 row violations, SCREEN 5 palette demand and sprite estimates.

- [x] Write synthetic tests: two background colors in an aligned 8-pixel row pass;
  three fail; object overlays do not become background violations; repeated RGB
  values retain distinct source-index counts; 17 distinct RGB values exceed SCREEN 5's budget.
- [x] Test a two-color 16x16 source object requires two entries under the explicit
  color-separated model, nine live entries exceed the eight-per-line limit,
  transparent objects require zero active layers, and clipped objects preserve
  bounding-box versus visible-pixel counts. Include dots and a shadow effect that
  cannot be represented by an ordinary opaque sprite color.
- [x] Run tests to confirm failure; implement per-row background analysis and
  explicit color-separated 16x16 entry estimates, total entry demand and scanline
  occupancy. State color-combination, reserved transparency, padding, clipping and
  software-effect assumptions. Label estimates separately from source object counts.
- [x] Run tests and reports for both scenes/layouts; identify actual palette and
  row/scanline failures, untested cases and effects needing software rendering.
  Do not select a final palette, screen mode or claim measured feasibility.

### Task 7: Usage, tracking and final verification

**Files:** Modify `Makefile`, `README.md`, `docs/arcade-scenes.md`; update this
plan's checkboxes with verified progress and unresolved conditions.

- [x] Add Make targets wrapping the documented capture/reconstruct/preview/analyze
  CLI arguments. Keep outputs fresh by default and retain existing targets.
- [x] Document capture schema and commands, synchronization source evidence,
  ROM/asset provenance, negative control, comparison counts, layout transforms,
  tested feature coverage and the subsequent MSX prototype handoff.
- [x] Run `.venv/bin/python -B -m unittest discover -s tests -v`; require the
  existing 65 tests plus new tests to pass. Run `git diff --check`.
- [x] Repeat documented end-to-end commands with fresh destinations; compare
  stable reconstruction/report outputs and revalidate all 13 source ROM hashes.
- [x] Inspect `git status --short`, `git ls-files references` and ignore checks
  for every generated bundle; ensure only permitted tools/docs/synthetic data
  are candidates for delivery. Existing `.gitkeep` files do not authorize game data.
- [x] Review changes against every issue acceptance criterion. Record any missing
  smoke/overlap, synchronization or exact comparison evidence as incomplete.
- [x] Report local delivery and validation to the user. Keep the issue open while
  required delivery/review is pending. Commit, push or PR creation happens only
  when authorized; use Markdown body files for any authorized GitHub prose.

## Plan self-review

The seven tasks cover all approved design sections and issue acceptance criteria.
Shared signatures and data ownership are listed above; each review-focus failure
has an owning test task. Synchronization, zero-difference gameplay evidence and
lossless HUD packing are explicit gates, not assumptions of success. No task
requires original game data in fixtures or authorizes implementation of a backlog
follow-up. The user approved this plan and direct execution. Local implementation
and the independent review fix pass are complete: 104 tests pass; five native
frames have zero mismatches; repeated capture/analysis files are byte-identical.
See `docs/arcade-scenes.md` for evidence and remaining renderer decisions.
No commit, push, PR or merge was authorized. Preserve the branch and user edits.

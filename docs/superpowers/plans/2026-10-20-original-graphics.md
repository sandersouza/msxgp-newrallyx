# Original Graphics Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution, or superpowers:subagent-driven-development if the user chooses delegated execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the supported contributor-supplied `nrallyx` set into reproducible, inspectable original graphics without tracking game data.

**Architecture:** Validate a pinned ROM inventory into immutable byte buffers, decode indices and palette data with pure functions, then publish a complete export through a guarded staging directory. A small CLI connects the modules and reports actionable failures.

**Tech Stack:** Python 3.14, Pillow 13.0.0, standard-library unittest, Git, MAME 0.289 for optional local integration and required visual acceptance.

**Spec:** [Approved design](../specs/2026-10-20-original-graphics-design.md).

## Global Constraints

- Support one unpacked `nrallyx` set; no ROM downloads, ZIP handling, sound extraction, disassembly, map reconstruction, scene renderer or MSX conversion.
- Use Python 3.14 and existing `Pillow==13.0.0` from `requirements.txt`; add no runtime dependency.
- Pin MAME `mame0289`, commit `f34f02505e32c1993c6a782b6814232cbfc74e36`.
- Preserve 256 8x8 characters, 64 16x16 sprites and eight 4x4 dots, including empty/duplicate IDs and source pen values 0..3.
- Enumerate all 64 tile/sprite color codes; distinguish lookup-dependent transparency from RGB black.
- Game-derived output must remain strictly below the repository's ignored `references/assets/`; captures remain under ignored `references/`.
- No timestamps or absolute paths in reproducible payloads; identical inputs, tool and recorded runtime versions must produce identical bytes.
- Use synthetic fixtures only in committed tests and documentation images.
- Implement on `feat/1-extract-assets`; preserve unrelated changes; no commit, push, PR or issue closure without authorization.
- Use English for code, documentation and GitHub content; Brazilian Portuguese in conversation.

## Review Focus

1. Invocation from another working directory or paths containing spaces: resolve CLI paths against the caller, output policy against the repository (Task 4).
2. Missing/broken Git or a force-tracked file inside an ignored tree: refuse publication rather than assume ignore coverage (Task 3).
3. Modified old output, extra nested files or forged manifest paths: refuse overwrite without touching existing contents (Task 3).
4. Input bytes changed after validation: decode retained buffers rather than reread source files (Tasks 1 and 4).
5. Interrupted publication or stale lock: preserve recoverable output/backup and report a precise recovery path (Task 3).

## Files and interfaces

Create `scripts/graphics/__init__.py` for package imports and version constants
`TOOL_VERSION = "1.0.0"`, `SCHEMA_VERSION = 1`.
The modules and test files below are new. Modify README only to link usage;
reuse existing dependencies and ignore rules unless validation proves a gap.

Shared JSON-compatible dictionaries use the field names fixed below. Internal
test metadata is passed to library functions; the CLI always loads its bundled
manifest and exposes no bypass. Errors use `ValueError` for invalid data or policy
and `OSError` for filesystem failures; the CLI catches both.

### Task 1: Pinned inventory and validated immutable input

**Files:** `scripts/graphics/nrallyx.json`, `scripts/graphics/roms.py`,
`scripts/graphics/__init__.py`, `tests/test_graphics_roms.py`.

**Interfaces produced:**

- `load_metadata() -> dict`: read the adjacent bundled JSON manifest.
- `validate_roms(input_dir: Path, metadata: dict) -> dict[str, bytes]`:
  return original filename to validated bytes for all required ROMs.
- `input_records(roms: dict[str, bytes]) -> list[dict]`: sorted records with
  `name`, `size`, `crc32` (eight lowercase hex digits), `sha1` (40 lowercase hex digits).

Metadata fields: `schema_version`, `set`, `source` (`tag`, `commit`, `paths`),
`roms` (records containing `name`, `size`, `crc32`, `sha1`, `region`, `loads`).
Each load records `file_offset`, `region_offset`, `size`, including CPU continuations.

- [x] **Step 1:** Add synthetic inventory tests. For payload `b"123456789"`, assert
  CRC32 `cbf43926` and SHA-1 `f7c3bc1d808e04732adf679965ccc34ca7ae3441`.
  Assert matching input returns those exact bytes; missing file, wrong size,
  same-size corruption, wrong revision, symlink and directory fail with filename
  and actionable expected values. Assert unrelated extra files are accepted.
- [x] **Step 2:** Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_graphics_roms.py' -v`;
  observe missing-interface failures before implementing.
- [x] **Step 3:** Implement the interfaces, bounded reads based on declared sizes,
  source-directory checks and read-only validation. Validate manifest field types,
  safe filenames and hash syntax before using it.
- [x] **Step 4:** Inspect the approved spec's pinned upstream sources locally under
  ignored `references/` and build the 13-entry metadata manifest. Cross-check its
  filenames, physical sizes, hashes and offsets against `ROM_START(nrallyx)` and
  `mame -listxml nrallyx`; no source ROM bytes enter the JSON.
- [x] **Step 5:** Assert modifying a synthetic file after validation does not change
  the returned bytes or their input records. Run the targeted tests to PASS, then
  `.venv/bin/python -B -m unittest discover -s tests -v` to check regressions.

### Task 2: Indexed decoding, palette and transparency

**Files:** `scripts/graphics/decode.py`, `tests/test_graphics_decode.py`.

**Consumes:** Task 1 metadata and validated buffers.
**Interfaces produced:**

- `decode_graphics(gfx1: bytes, gfx2: bytes) -> dict[str, bytes]`: keys `tiles`,
  `sprites`, `dots`; flattened ID/row/column source pens.
- `decode_palette(palette_prom: bytes, lookup_prom: bytes) -> dict`: fields
  `raw_palette`, `raw_lookup`, `rgb` (32 RGB triples), `lookup` (256 effective
  indirect indices), `variants` (64 four-index lists), `sprite_alpha` (64 four-byte
  alpha lists), `dot_indices` (16..19), `dot_alpha` ([255,255,255,0]).
- `flip_pixels(pixels: bytes, width: int, height: int, flip_x: bool, flip_y: bool) -> bytes`:
  deterministic reflection for inspection/tests; canonical exports stay unflipped.
- `graphics_metadata() -> dict`: schema, source layouts, flips, counts, dimensions,
  atlas columns, index encoding and ID-to-slot positions from the approved spec.

- [x] **Step 1:** Inspect pinned `drawgfx.cpp` plane significance and MSB bit
  addressing, `rallyx.cpp` layouts, `rallyx_v.cpp` flips/lookup/transparency and
  `resnet.cpp`/header rounding. Keep upstream source copies ignored. Derive tiny
  expected pixel matrices independently of the implementation.
- [x] **Step 2:** Add tests using zero regions and individually set source bits.
  Assert output lengths 16384, 16384 and 128; test each plane, sprite quadrants,
  first/last IDs, graphic boundaries and all three asymmetric reflections.
  Assert malformed input lengths fail rather than truncate or wrap.
- [x] **Step 3:** Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_graphics_decode.py' -v`;
  observe missing decoder behavior. Implement the exact layouts and flip function;
  run the pixel tests to PASS.
- [x] **Step 4:** Add synthetic PROM tests with independently calculated resistor
  network/rounding expectations for zero, each color bit and all-bits-set entries.
  Assert all 32 colors and 64 lookup variants, lookup low-nibble masking, opaque
  tiles, lookup-dependent sprite alpha and dot pen-3 alpha. Include a lookup that
  maps a nonzero source pen to indirect zero, and a nonzero indirect color whose
  RGB happens to be black; only the former is logically transparent for sprites.
- [x] **Step 5:** Observe those palette tests fail, implement `decode_palette` and
  `graphics_metadata`, then rerun the targeted tests and full unittest suite to PASS.
  Document the exact resistor model; do not substitute approximate classic RGB weights.

### Task 3: Deterministic export and guarded publication

**Files:** `scripts/graphics/export.py`, `tests/test_graphics_export.py`,
`tests/graphics_fixtures.py` (shared synthetic buffers and temporary Git repository).

**Consumes:** Task 1 `input_records`; Task 2 decoded pixels, palette and metadata;
package version constants.
**Interfaces produced:**

- `write_payload(directory: Path, pixels: dict[str, bytes], palette: dict, graphics: dict, inputs: list[dict], source: dict) -> dict`:
  write payloads and final manifest, return parsed manifest.
- `publish_output(repo_root: Path, input_dir: Path, output_dir: Path, overwrite: bool, writer: Callable[[Path], dict]) -> dict`:
  enforce path/ignore/overwrite policy, call writer in staging, publish and return manifest.

Manifest fields: `tool` (`name`, `version`), `schema_version`, `source`,
`runtime` (`python`, `pillow`), `parameters` (set name, layout and atlas conventions),
`inputs`, `outputs` (sorted records of relative POSIX `path`, `size`, `sha256`).
Use tool name `newrallyx-graphics`; reject unknown versions during overwrite.

- [x] **Step 1:** Add synthetic export tests asserting all filenames in the spec,
  binary byte order, P-mode source index preservation, atlas slot coordinates,
  PNG sizes 128x128/128x128/32x4, 64 tile and 64 sprite variants, alpha rules,
  sorted JSON, relative paths and manifest hashes. Assert two exports are byte
  identical and no source-derived metadata is omitted.
- [x] **Step 2:** Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_graphics_export.py' -v`
  and observe missing export behavior. Implement fixed image encoding and JSON
  serialization, then hash all payloads and write `manifest.json` last.
- [x] **Step 3:** Add temporary-Git-repository tests for outside/root/`..`/overlapping
  output paths, symbolic links, nonexistent/non-directory ancestors, missing Git,
  tracked generated paths, uncovered ignore paths and existing directories.
  Assert rejection leaves no output and preserves input bytes.
- [x] **Step 4:** Observe failures, implement strict path validation, Git ignore and
  tracked-file checks, exclusive destination lock, sibling staging and publication.
  Use Git argument arrays with `--`/NUL-safe paths; reject empty CLI paths before
  conversion to `Path`. Validate existing components without following symlinks.
- [x] **Step 5:** Add overwrite tests: valid complete output succeeds only with the
  flag; modified hashes, extra files, nested files, symlinks, unsafe manifest paths,
  malformed JSON, missing payloads and stale lock fail without deleting data.
  Inject writer and rename errors to assert staging cleanup, old-output restoration
  and lock release. A concurrent lock must prevent invoking the writer.
- [x] **Step 6:** Observe failures, implement recognized-output verification and
  backup/rollback. Validate manifest paths and inventory before accessing payloads.
  Report stale lock/backup location with recovery advice; never delete unknown
  locks or backups automatically. If backup cleanup fails after installation,
  preserve both outputs and report the installed output and backup clearly.
- [x] **Step 7:** Run export tests and full unittest suite to PASS. Verify temporary
  fixtures contain synthetic bytes only and subprocesses do not depend on ROMs.

### Task 4: CLI and end-to-end synthetic behavior

**Files:** `scripts/extract_graphics.py`, `tests/test_extract_graphics.py`.

**Consumes:** All preceding interfaces.
**Produces:** `main(argv: list[str] | None = None) -> int` and executable script
entry point, with required `--input`, `--output` and optional `--overwrite`.

- [x] **Step 1:** Add subprocess tests for `--help`, missing arguments, empty paths,
  missing/corrupt input and unsafe output. Assert nonzero exit, actionable stderr,
  no traceback for expected failures and no completed output after rejection.
  Assert help documents the pinned set and overwrite restriction.
- [x] **Step 2:** Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_extract_graphics.py' -v`
  and observe failures; implement parsing, version/ dependency diagnostics, validation,
  decoding and publication. Resolve repository root from the script location.
  Assemble graphics buffers from validated ROM regions; never reopen source ROMs.
- [x] **Step 3:** Add successful orchestration tests calling `main` with synthetic
  metadata injected only through the Python test seam. Use real decoder/exporter
  behavior, temporary Git roots and real synthetic files. Assert output manifest
  and pixel values, overwrite behavior and unchanged input hashes. Patch bundled
  metadata/root resolution only; never mock the decoder or publication result.
- [x] **Step 4:** Add cases invoked from another working directory and paths with
  spaces. Mutate synthetic source files after validation and assert the output
  remains tied to the validated buffer and manifest hashes. Observe failing
  assertions, implement any missing orchestration, then run CLI tests and full suite.

### Task 5: Real-set validation, documentation and issue tracking

**Files:** Create `docs/graphics-extraction.md`; modify `README.md`;
update ignored `.github/issues/extract-original-graphics.md` and published issue
progress using file-based bodies. Keep captures and generated assets ignored.

**Consumes:** Completed CLI; approved spec and issue acceptance checklist.
**Produces:** Reproducible validation commands/results and accurate pending criteria.

- [x] **Step 1:** At implementation start, move only issue #1's project item to
  In progress and align its local/published body. Read existing project field IDs
  and values first; retain P2, size, estimate and unassigned milestone. Do this
  when execution begins, rather than waiting until Task 5's other work.
- [x] **Step 2:** Record input hashes, run the documented CLI into
  `references/assets/nrallyx`, then separately into
  `references/assets/nrallyx-repeat`. Use another fresh ignored destination if
  either already exists. Compare every file including the manifest byte-for-byte;
  verify recorded SHA-256 and unchanged input hashes. Record actual results.
- [x] **Step 3:** Open MAME 0.289 with the supplied ROM directory and inspect its
  graphics viewer. Compare tile IDs 0, 1, 127, 255; sprite IDs 0, 1, 31, 63;
  dot IDs 0..7; tile/sprite color codes 0, 1, 31, 63 and one lookup-sensitive
  transparent case. Include an asymmetric nonempty ID if the fixed choices do
  not provide one. Record observed orientation, palette and alpha agreement,
  exact added IDs/color codes and discrepancies. Captures stay ignored. Distinguish
  visual comparison from automated index checks and note viewer alpha limitations.
- [x] **Step 4:** Write usage, minimal venv/dependency installation, supported inventory,
  schema, source citations, error/overwrite/recovery behavior, limits and optional
  integration procedure. Include actual commands and evidence, never fabricated
  screenshots or success claims. Link the document from README. If visual access
  fails, retain the unchecked visual criterion and explain the blocker.
- [x] **Step 5:** Run `.venv/bin/python -B -m unittest discover -s tests -v`,
  `.venv/bin/python -B scripts/extract_graphics.py --help` and `git diff --check`.
  Run `git check-ignore` on ROMs, generated payloads, staging/backup/lock paths
  and captures; check `git ls-files` and the complete diff for original data.
  Record results and any untested cases in the development document.
- [x] **Step 6:** Review the whole change against each issue criterion; fix uncovered
  defects with failing synthetic regression tests first. Move only issue #1 to
  In review while delivery/review remains pending; synchronize the local draft
  and published body from a Markdown file. Leave PR and closure criteria unchecked
  until authorized delivery exists. Report changed files, validation and blockers
  in Portuguese; do not commit or push.

## Plan self-review

- Spec coverage: Tasks 1/2 cover supported inputs and source fidelity; Task 3
  covers schema, determinism and safety; Task 4 covers CLI; Task 5 covers local
  integration, visual acceptance, documentation and tracking.
- Interface consistency: buffers and dictionaries cross module boundaries;
  filenames, fields and call signatures are defined above their consumers.
- Review Focus cases are assigned to explicit tests in Tasks 1, 3 and 4.
- Tests remain synthetic; real-ROM validation is local and separately reported.
- No implementation, test run, integration or visual success is asserted by this plan.
- Written plan approved in this chat; user authorized native execution with `siga`. All 28 steps completed; final suite: 65 tests pass. Independent review findings were addressed with regression checks. Commit/push/PR remain pending authorization.

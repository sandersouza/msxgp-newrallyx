# Repository maintenance and reproducibility

Issue: [#34](https://github.com/sandersouza/msxgp-newrallyx/issues/34).
The current architecture is mapped in [architecture.md](architecture.md).
This pass organizes navigation/output retention and relocates the complete
SCREEN 4 component to `src/screen4/` without rewriting runtime logic.
Zero-overhead module extraction remains issue #32.

## Baseline before cleanup

Checkout: `1695c5a461c9714aa98c17dbcd032d68d7746d60`, after PR #33 and the original
56x8 wordmark restoration. All three builds succeeded with the contributor's
existing ROM/BIOS/assets and Python environment on 2026-10-29, with HUD enabled.

| Build command | SHA-256 |
| --- | --- |
| `make build` | `98ce0135b628a1837a3d6df2910f572e466b4bffe465344238f4c44a9015346a` |
| `make build TEST_MODE=1` | `9f61724047bb444a6ea7fe9e87a53f0138436f8f1a84ee3b18a3d55bc713e53b` |
| `make build LEGACY=1` | `e95a4a803c0ac3d0096b7021c877a56086d09d6ba8ed307dde7a8d039198537c` |

Local baseline ROMs, build logs, manifests and profile evidence are retained in
ignored `references/issue34/baseline/`. These hashes identify artifacts, not
complete gameplay or physical-hardware acceptance. The earlier PR #33 optimized
hash `41de7830...` predates the final original-wordmark restoration; do not mix
its pixel evidence with the current title.

## Dependency inventory and decisions

Regenerate the [file inventory](repository-inventory.json) after reviewing changes:

```sh
.venv/bin/python -B scripts/repository_inventory.py
```

The inventory includes tracked and visible new files, Python AST imports,
candidate assembly INCLUDE references and conservative filename mentions from
source/build/documentation. Duplicate basenames intentionally retain every
candidate. Conditional and historical branches remain visible. Dynamic imports,
generated source transformations, subprocesses and imported symbols still need
manual review; a missing reference never proves a file is dead.

| Family | Classification and owner | Decision |
| --- | --- | --- |
| `src/screen5/` | Shared/legacy runtime and maintained bounded-stage sources; legacy assembler plus selected SCREEN 4 consumers | Keep; a SCREEN 4 default does not make SCREEN 5 sources obsolete. |
| `scripts/msx/`, `scripts/scenes/`, `scripts/graphics/`, environment/bootstrap | Build dependencies and input/reference adapters | Keep; includes source generators and pinned-source dependencies. |
| `src/screen4/` build helpers and includes | Default runtime/generators plus maintained first-stage/free-camera paths | Keep authored paths; clarify ownership and compatibility aliases. |
| `tests/`, `test_*.py`, verifiers and probe CLIs | Maintained regressions and bounded reproductions | Keep; a CLI need not have an import caller. |
| `docs/`, laboratory reports and workbooks | Current contracts plus dated historical evidence | Keep; mark obsolete status claims as historical instead of deleting measurements. |
| `outputs/` | Generated payloads, reports, workbooks and private emulator state | Untrack all 854 formerly versioned files (723,138,273 bytes); keep local originals, a private archive and exact-hash provenance. |
| `docs/measurements/audio/` | Three historical JSON inputs used by the maintained audio verifier | Retain outside generated output so a fresh checkout keeps the same comparisons. |
| Original ROMs/BIOS/extracted imagery/disassembly | Protected contributor inputs | Keep ignored under `references/`; never download, publish or remove local evidence during cleanup. |

No authored runtime/tool file is discarded based only on filename searches. The
inventory is also the starting map for issue #32. Further obsolete-code removal
requires identifying conditional/generated callers and retained reproductions.

The complete 155-file SCREEN 4 component moved from `experiments/fixed-hud/` to
`src/screen4/`. Its generators, assembly/includes, sibling imports, tests and
documentation remain together at the same path depth. Root discovery, the
pinned source revision, artifact paths and Make aliases are preserved. Only
source-path consumers and documentation are adapted; no runtime assembly logic
or bank layout is intentionally changed. The root Makefile imports the
component's `targets.mk` at its new path, retaining the optional-include behavior
used by isolated legacy, setup and clean test fixtures.
[screen4-migration.json](screen4-migration.json) records every old/new path and
before/after digest; the pre-migration checkout is archived locally under
`references/issue34/migration/`. Top-level `experiments/` is removed.

## Generated-output retention

The contributor explicitly requested that the entire generated `outputs/`
directory be removed from version control and ignored. Local copies, generators,
hashes, reports and historical measurements are preserved. [retired-artifacts.json](retired-artifacts.json)
records each reviewed path, size, SHA-256, original Git blob and probe-family
generator where identified. No local file was deleted and no shared Git history was rewritten.
An independent exact-payload archive is retained locally at
`references/issue34/retained-outputs.tar.gz` so subsequent probe runs cannot
erase the historical bytes.

The 64 MiB `radar-synthetic/expected.bin` is generated by
`test_game_radar.py::verify_emulator`: 64 phases x 1,024 masks x 1,024 name-RAM
bytes. The driver writes its programs, expected data and synthetic cartridge
before openMSX consumes them. It does not require a committed binary fixture:

```sh
.venv/bin/python -B src/screen4/test_game_radar.py --emulator --bios references/msxbios
```

Known probe generators are listed per artifact in the manifest using their
historical source paths. Resolve those paths through `screen4-migration.json`
to the maintained `src/screen4/` location. Use their help and
retained result JSON/Tcl/assembly to select the original options and revision.
The current generator may produce a different optimized worker than a historical
before/after measurement. Keep the existing cycle/results records and workbooks;
do not present fresh output as a reproduction of an older ROM without comparing
its hashes and workload.

Historical component-report tools can inspect exact retired payloads locally.
On a fresh checkout with the original Git objects available:

```sh
.venv/bin/python -B scripts/restore_probe_artifacts.py --check --group radar-synthetic
.venv/bin/python -B scripts/restore_probe_artifacts.py --group radar-synthetic
```

The first command is read-only. The second restores only missing files from
local Git blobs, verifies size/SHA-256, and never overwrites existing evidence or
uses the network. Omit `--group` for the full manifest. A nonzero status reports
missing/different local artifacts; preserve different files before deciding to
restore. A shallow clone may lack the blobs: use the retained local archive or
regenerate fresh evidence instead. Restoration is optional for normal builds.

The single `/outputs/` ignore rule covers cartridges, synthetic payloads,
reports, workbooks and emulator state. They remain local and can be regenerated
or recovered from their recorded Git objects. Three audio-baseline JSONs moved
unchanged to `docs/measurements/audio/`; `session_audio_verify.py` reads them
there, preserving its existing optional historical comparisons. Authored tools,
compact provenance and maintenance documentation stay versioned.
Existing public history is a separate audit;
this working-tree cleanup does not remove previously published objects.

## Cycle ledgers and workbooks

Run the full-session profiler on the exact selected cartridge:

```sh
make build
.venv/bin/python -B src/screen4/session_profile.py --bundle references/experiments/full-session
.venv/bin/python -B src/screen4/session_report.py --bundle references/experiments/full-session --out references/issue34/current-ledger
```

`session_profile.py` wraps the established PC/SP profiler through
`session_profile_adapter.py`. Real keyboard/F5 input advances to native round 5;
the fixture requires three enemies. The report rejects stationary-enemy samples
and verifies its ROM hash. `last-profile.txt` identifies the ignored raw capture.
Use `--profile <capture>` on `session_report.py` to bind a report explicitly.
An uninstrumented control run checks state/tick alignment and observation jitter.

Record checkout and cartridge hashes, openMSX/machine, CPU mode, video registers,
HUD/audio/sprite-limit state, active intervals, enemy movement, directional
workload and duration. Keep active play separate from death/bonus/paused/cold UI.
For each routine retain calls per presentation, inclusive/self costs, mean,
p95/maximum and synchronization waits. Inclusive parents overlap their children;
never sum both. Cold/startup and flag-event ledgers have separate workload scopes.

The calibrated fixed-base-clock sample uses 262 x 228 = 59,736 cycles per refresh
and 3,579,545 Hz, approximately 59.923 Hz refresh and 29.962 Hz for exactly two
refreshes per presentation. The report computes usable blank endpoints from the
measured VDP registers/status; a full refresh, drawing phase and usable VBlank
are distinct budgets. Its 5,000-cycle reserve is a planning assumption, not a
measured hardware ceiling. Check late intervals and ready margins as well as FPS.
Launcher factory-turbo behavior is a different configuration; do not transfer
fixed-clock figures to it without measurement.

For the maintained workbook, run `session_report.py --out outputs/full-session`
after validating the intended raw capture, then use the existing Node workbook
generator in an environment where `@oai/artifact-tool` resolves:

```sh
node src/screen4/session_workbook.mjs outputs/full-session/cycle-ledger.json references/issue34/cycle-budget.xlsx
```

The two positional arguments are the input ledger and output workbook; choose a
new output path before replacing a historical file. The package is supplied by
the artifact-authoring environment, not by the Python/game setup. Older
first-stage workbooks have different ROMs and workloads;
they cannot substitute for the integrated report. Preserve the previous ledger
before replacing it. This cleanup retains all existing workbooks unchanged.

## Verification boundary

Use `make test` for general unit contracts, `make test-experiments` for the full
optimized integration, and a separate controls/graphics run against the test-mode
bundle. Legacy tests and reconstruction remain independent. The integration
target covers boot/module, keyboard controls, start, two-player sessions, flags,
attract, radar, smoke, enemy rocks, challenge speed, a 16,000-refresh steering
route, audio and clipping. Keep failed or skipped cases explicit.

Compare rebuilt ROMs with the baseline hashes above. Byte identity establishes
unchanged cartridge code/data, bank size and allocated RAM/VRAM/stack requirements
for the same inputs/options; it does not establish whole-game acceptance. A
matched three-moving-enemy profile is still a bounded emulator workload. Human
graphics, PSG timbre, full-course behavior and real-hardware acceptance remain
with the contributor and must not be inferred from a build or test launch.

### Cleanup validation — 2026-10-29

- All three builds were repeated after cleanup and compared byte-for-byte with
  the baseline cartridges above: identical.
- 438 general unit tests passed, including the new inventory/restore safeguards.
- `make test-experiments` passed. Its 69 laboratory unit cases include one
  intentional skip: the assembled multi-enemy initializer requires the explicit
  `--emulator` option. The integrated emulator scenarios and 16,000-refresh
  keyboard route also passed; the route retained 3,465 later poses.
- The separate TEST_MODE=1 real-keyboard controls and independent graphics
  contracts passed against its own ROM hash, including Return/equals and solid
  walls. Normal-mode launch selection remains covered by the general tests.
- Baseline and post-cleanup profiles used the same optimized ROM, openMSX 21.0,
  Panasonic FS-A1WSX_NR128, fixed 3,579,545 Hz CPU, three moving native enemies,
  HUD/audio and real sprite limits. Both captured 238 active presentation
  intervals over 7.959028 seconds: 29.903149 presented FPS at 59.922743 Hz refresh,
  with 237 two-refresh intervals and one three-refresh interval. Work costs were
  identical: mean 81,013.563 cycles, p95 109,983, maximum 127,375. The three enemy
  pose counts were 12/11/14. This is a short directional workload, not a full phase.

The before/after raw captures, JSON/CSV ledgers and logs remain under ignored
`references/issue34/`. Retired payload existence/hashes were checked against the
retirement manifest. No cartridge runtime source changed. The cleanup delivery
does not close issue #13 or approve human graphics/audio/hardware
acceptance.

### SCREEN 4 source migration — 2026-10-29

Baseline checkout: `fa0f63006da6edec79fc0b868372940cc8439326`. All 155 component
files moved to `src/screen4/`; all 41 assembly/include/Tcl files remained
byte-identical. The path/hash ledger and compact verification results are in
[screen4-migration.json](screen4-migration.json).

- Rebuilt normal, TEST_MODE=1, legacy, three-enemy first-stage and free-camera HUD
  cartridges. All five are byte-identical to their pre-migration references.
- 439 general unit tests passed. The existing optional Make include was retained
  after isolated legacy/setup/clean fixtures exposed that compatibility need.
- `make test-experiments` passed through the new source paths: 69 laboratory unit
  cases with the same one explicit-emulator skip, all integrated scenarios,
  16,000-refresh steering, audio, stone/speed and clipping checks. TEST_MODE=1
  keyboard/graphics contracts also passed separately.
- Checked 17 public Make target command plans and the legacy/test/HUD/logo/boot,
  explicit ROM, checkpoint and latest selections. Every referenced Python source
  resolves under its maintained path. Direct Python CLIs now use `src/screen4/`;
  historical Make aliases and ignored artifact paths remain unchanged.
- Repeated the matched three-moving-enemy profile after migration. The active
  statistics match the baseline above exactly, including 238 active intervals,
  29.903149 presented FPS, one three-refresh interval and the same work-cost
  distribution. This remains the same bounded fixed-clock emulator workload.

The old top-level `experiments/` directory is gone. Local ROMs, raw evidence and
the pre-migration source archive remain under ignored `references/issue34/`.
No new graphical, timing, gameplay or sound concession is introduced by the move.

### SCREEN 5 source layout

The 73 former top-level `src/` assembly/include files now live in `src/screen5/`.
Their bytes and staged assembly basenames are unchanged. Legacy/native builders
in `scripts/msx/` and direct SCREEN 4 helper consumers use the nested path.
Shared Python tools remain in `scripts/`, with their existing public commands.

`game_core.prepare()` defaults to `src/screen5/`. Its explicit `source_directory`
argument allows complete-session integration to select the original flat `src/`
in the manifest-verified pinned source view. `session_build.reference()` still
verifies that historical source and resource bundle. The cached export is not
edited or silently upgraded, and a missing current folder does not fall back to
historical files. A source-only regression compares generated adapters from both
explicit layouts and verifies that an unselected flat tree fails.

[screen5-migration.json](screen5-migration.json) records the source hashes and
validation for this subsequent step. The SCREEN 4 migration ledger remains a
record of its earlier snapshot. Pre-step working changes and legacy source
bytes are backed up under `references/issue34/screen5-migration/`.

Validation passed: all 73 legacy and 41 SCREEN 4 assembly/include/Tcl files keep
their prior bytes; normal, test-mode, legacy, three-enemy first-stage and HUD-lab
ROMs are byte-identical to the pre-step artifacts. The 439 general tests and
integrated emulator suite passed, including 70 component unit cases with the
same one explicit-emulator skip, the 16,000-refresh steering route, audio and
sprites. Test-mode keyboard/graphics contracts passed separately. The matched
fixed-clock three-moving-enemy profile has exactly the same active statistics:
238 intervals over 7.959028 seconds, 29.903149 presented FPS, one three-refresh
interval and unchanged work/tail costs. Its scope remains a short directional
emulator workload; whole-course and physical-hardware acceptance are separate.

### Script audit and retirement

`scripts/` is still needed by both presenters. It contains environment setup,
contributor-input extraction/capture, shared build generators, legacy/native
builders, launch/checkpoint/replay support, and bounded verification entry points.
An unimported CLI can still be a maintained tool: documented `python -m` commands,
source-oracle comparisons and standalone audio/game-rule probes remain valid.

The current dependency audit checks Python imports (including modules imported
from packages), filename/module mentions, Make/source/test command consumers and
maintained documentation. [scripts-audit.json](scripts-audit.json) records the
inspection and explicit retention decision. Audit/migration ledgers are not
treated as operational callers by the repository inventory.

Four unpublished study CLIs were retired: `full_cache_forecast_probe.py`,
`full_cache_metadata_probe.py`, `full_camera_bounds_probe.py` and
`full_enemy_cost.py`. None had an importer, build/test/command consumer or
maintained reproduction procedure. Their current legacy symbols still exist;
this retirement does not claim that the old probes are broken or that a different
workload is an equivalent replacement. Their complete source is archived locally
in `references/issue34/retired-scripts.tar.gz`, with size, SHA-256 and original Git
blob recorded in the audit ledger. Existing raw measurement evidence is retained.

Unique AI, bonus-life, popup and original-sound comparisons were kept even where
they have no import caller. `maze_debug.py` was also kept: its explicit capture/
replay round-trip self-test is distinct from normal launching. No regression
suite or build mode was deleted merely because SCREEN 4 is now the default.

After retirement, 208 of the original 212 files under `scripts/` remain (including
Python modules, Lua/Tcl adapters, shell provisioning and metadata). The 439 general
unit tests and 70 component cases passed with the same one documented skip.
Normal, test-mode, legacy, three-enemy first-stage and HUD-lab builds were repeated;
all five ROMs are byte-identical to the pre-cleanup artifacts. Maintained source
files parse, public Make command plans resolve, and no remaining code/command
consumer references the retired filenames or modules. Raw checks are retained
under `references/issue34/scripts-cleanup/`.

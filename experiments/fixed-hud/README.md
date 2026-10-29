# Fixed side HUD hardware-scroll laboratory

`make run` and its compatibility alias `make run-experiments` open the complete
integrated SCREEN 4 game from this checkout. From another directory use
`make -C <checkout> run`; select the intended checkout explicitly. Arrow keys
steer; Space releases smoke. `make run LEGACY=1` selects the maintained SCREEN 5
build from current sources. The historical laboratory directory name is retained
because its modules, tests and compatibility commands are still used.
See [FULL-SESSION.md](FULL-SESSION.md) for current scope, tests and timing.
See [the architecture](../../docs/architecture.md) and
[maintenance procedure](../../docs/maintenance.md) for ownership and retention.
The previous benchmark is retained as `make run-first-stage` and documented in
[FIRST-STAGE.md](FIRST-STAGE.md).
The free-camera renderer documented below is retained as `run-hud-lab`.
The independently reproducible production renderer from the audio branch is
available with `make run-audio-reference`. See
[BUILD-PROFILES.md](BUILD-PROFILES.md) for selection and the shared-source boundary.

## Earlier free-camera laboratory

Working experimental engine and cartridge for the requested stage-one layout.
The 200/56 framing, persistent hardware-scroll ring, fixed character HUD and
clock-driven controls pass the emulator probes below. Presentation timing is
qualified in the measured-limits section; this is a laboratory renderer.
All generated graphics, original-derived binaries, ROMs and emulator evidence are
local under ignored `references/experiments/fixed-hud/`. No production source or
build target is changed. The user authorized SCREEN 4 scenery color reduction
for this experiment only. The wider-HUD revision additionally has explicit user
authorization for a fixed eight-pixel mask at the extreme left of the scene.

## Reproduce

From the repository root, using the existing environment and pinned assembler:

```sh
make run-hud-lab
```

This rebuilds the fixed-HUD cartridge and opens it in an isolated openMSX window.
Use the arrow keys to move and hold Shift for twice the speed.

```sh
make build-hud-lab  # Build the ROM without opening the emulator.
make test-hud-lab   # Run keyboard, phase/boundary, continuous and video checks.
```

The stable artifact is `references/experiments/fixed-hud/fixed-hud.rom`.
The experiment targets do not publish the production ROM or change `latest.rom`.
Verification requires the existing openMSX/BIOS setup and FFmpeg for video decoding.

Individual commands used by these targets:

```sh
.venv/bin/python experiments/fixed-hud/build.py
.venv/bin/python experiments/fixed-hud/verify.py
.venv/bin/python experiments/fixed-hud/analyze.py
.venv/bin/python experiments/fixed-hud/verify.py --matrix
.venv/bin/python experiments/fixed-hud/analyze.py
.venv/bin/python experiments/fixed-hud/edge_contract.py
.venv/bin/python experiments/fixed-hud/verify.py --continuous
.venv/bin/python experiments/fixed-hud/analyze.py
.venv/bin/python experiments/fixed-hud/scanout.py
.venv/bin/python scripts/project.py run --rom references/experiments/fixed-hud/fixed-hud.rom
```

Analyzers exit 1 if their scoped RGB acceptance fails. Their `complete` field
means that probe passed, not that the entire engine goal is complete.
Each verifier run gets a fresh evidence directory; `last-probe.txt` selects it.
Both analyzers accept an explicit evidence-directory argument. Metadata binds
evidence to the exact ROM SHA-256 and rejects evidence for a different cartridge.
Arrow keys move the camera by one world pixel per VBlank; Shift doubles that
rate. A minimal IM2 interrupt clock counts physical refreshes during rendering.
The next input update applies all elapsed ticks, so a missed presentation does
not slow the camera or defeat Shift's actual 2x velocity. This can produce steps
of 2/4 pixels after a two-refresh rendering interval, rather than losing time.
This is a free camera, not the game's car movement/collision implementation.
The radar dot projects the camera center into the original stage's dimensions.

HUD counters are laboratory build inputs, with presentation-only saturation.
The defaults show HI=020000, score=000000, RND=1 and four extra-life cars. For an
above-limit demonstration, build/run with:

```sh
make run-hud-lab HUD_HIGH_SCORE=1000000 HUD_SCORE=1000001 HUD_ROUND=100 HUD_LIVES=9
```

The display shows 999999, 999999, 99 and four cars. This fixture does not add
gameplay score/life hooks or clamp the game's internal counters. `hud.py` owns the
display contract; `test_hud.py` uses synthetic inputs only. All generated original
life masks remain local under ignored `references/`.

## Technique being tested

- Reuse the contributor ROM extraction and validated native first-stage MAME
  acquisition; no new original ROM is downloaded. `prepare.py` revalidates the
  acquisition and checks 28,672 tile selections against native redraws.
- SCREEN 4's two-color scanline codec changes 6,300 of 1,135,872 scenery pixels
  (0.5546%) in this untouched-stage fixture. Dimensions stay 1:1. This fixture
  does not add the separate two-rock test used in earlier feasibility work.
- Hardware R26/R27 traverse a persistent 32x32 name-table ring. For nonzero
  fine X, R26 selects the next column and R27 shifts right by `8-fineX`;
  phase zero uses the original column and R27=0. R18 stays zero. R23 handles
  vertical scrolling. The R25 left mask hides x=0..7 in every phase, including
  the eighth-pixel reset; the remaining scene pixels x=8..199 retain their world
  coordinates. This fixed left mask is authorized only for this experiment.
- The HUD now uses all 48 pixels from x=208..255, with six-digit scores, a
  48-pixel fuel bar and a 48-pixel blue radar panel. Radar world positions span
  32 horizontal pixels, compared with 24 previously. Glyphs remain 8x8.
  The wrapped first name-table column supplies the seventh compensated HUD cell;
  the left hardware mask hides that column. No right inset is needed.
- The radar occupies y=68..179, eight pixels above its previous position and at
  the same height. Up to four native life-car drawings sit below it at y=184;
  only their transparent 16x16 source padding overlaps. No opaque car pixel is
  clipped or rescaled. `RND` occupies y=204..211 with its number flush right.
  Presentation saturates rounds at 99, both scores at 999999 and life icons at 4.
  The actual game counters/rules are not changed.
- The toolchain generates 64 inverse HUD phases. A dictionary of 46–87 tiles
  needs 736–1,392 bytes for a full pattern/color upload. Normally, precompiled
  transition packets send changed spans instead. All 4,096 previous/current
  phase combinations are checked against poisoned unused character slots.
  Packet allocation remains bounded to 213 ASCII16 ROM banks (3,489,792 cartridge
  bytes); `transition-cost.json` records current packet/fallback counts. Spans merge small
  gaps to avoid expensive repeated VDP address setup. R14 changes once per packet
  region. Six HUD names per visible tile row are compiled as Z80 word stores.
  HUD characters use slots 64..191; the two scenery-edge atlases use 192..219
  and 220..247, and the moving radar dot uses 248. The retired left atlas is not
  uploaded. This allocation keeps the complete life drawings within SCREEN 4.
- The HUD occupies x=200..255: 56 pixels (21.875%), with an eight-pixel left inset.
  HUD content stays at x=208 and original 8x8 glyph dimensions are unchanged.
  The scene's logical window remains x=0..199, with x=0..7 masked. World and
  camera rules are unchanged; the previous left-edge atlas is no longer uploaded.
- Pattern/color register masks share one character dictionary across all four
  screen quarters. Two independent VRAM table sets allow inactive uploads and
  register changes during vertical blanking.
- The previous compositor introduced phase-dependent scene colors beside the
  HUD, particularly in phases 5–7. The original oracle reproduced that defect
  and therefore incorrectly accepted its appearance. The user reported the
  visible strip and authorized a localized edge simplification on 2026-10-27.
- `edge.py` defines a fixed screen-space band x=193..199. Every pixel in that
  band uses its original source tile row's most frequent color, with ties going
  to its first source pixel. This rule applies in all eight phases, including
  zero. The separate left-edge rule is the fixed hardware mask described above.
  The wider black gutter x=200..207 separates scenery from HUD content. A mixed
  character now has one scene color and black; radar/glyph colors cannot enter
  it. Tile 24 gets the simplified tail and tile 25 gets the scene/black split.
  Two static ROM atlases replace the dynamic boundary cache entirely.
  This authorized seven-pixel simplification is additional to the whole-world
  0.5546% conversion. The independently authorized left mask is additional to
  both scenery adaptations and is checked separately in every phase.
- `ring.inc` keeps original world IDs in a 1 KiB RAM ring, separate from the
  character overrides sent to the two VRAM name tables. A normal coarse crossing
  loads two/three incoming columns and/or one incoming row: at most 128 original
  IDs per movement update. Each back table remembers its coarse origin. It gets
  the row/column restoration needed since its previous use, followed by the HUD
  overrides, rather than a rebuilt 1 KiB window. Full refills handle cold start
  and explicit camera teleports. They do not occur in the continuous keyboard
  route after initialization.
  Fine changes replace HUD names/patterns across 28 rows, enough for 212 visible
  lines plus seven fine-scroll lines. No overscan crop conceals a missing row.
  Static edge dictionaries cover every phase and are retained while fine X stays resident
  in a back table. Register/address transactions are interrupt-safe; the VBlank
  handler only acknowledges S0 and advances its clock.
  The program uploads new ROM/RAM data to VRAM. It does not
  relocate existing VRAM bitmap blocks, issue VDP copy commands, or use sprites.

## Current evidence

Cartridge SHA-256:
`e1d5a44c743b62241351c44959fd047a65f0fbe230f1b49a4f1006c6c40c64cc`.
All comparisons cover complete 320x240 images, including every border pixel,
with exact RGB equality against an independent composition/adaptation oracle.

| Probe | Evidence directory under `references/experiments/fixed-hud/` | Result |
| --- | --- | --- |
| Keyboard, 84 updates | `probe-2kbeip1b` | 14 images pass; 1/2 pixels per VBlank verified |
| Phase/boundary matrix | `probe-423m98ui` | 225 images pass; all 64 fine phases, map edges and eighth-pixel reset |
| Independent edge contract | same matrix directory | Zero wrong pixels in the seven-pixel band and eight-pixel black gutter, in phases 0–7 and the next coarse position |
| Continuous keyboard route | `probe-9f3c_gr1` | 305 captures pass; diagonals, reversals, fast movement and pause |
| Physical-frame video | same continuous directory | All 449 recorded frames after oracle coverage starts pass; 290 distinct presentations; no unmatched/mixed frame |
| Saturation inputs | `probe-ccl38m6q` / `footer-cap-evidence` | 14 full-frame images pass with input scores 1000000/1000001, round 100 and lives 9 displayed as 999999/999999, 99 and four complete cars |

Continuous capture callbacks can observe the current or immediately preceding
presentation depending on their position in blanking. The analyzer tests only
those two complete states and enforces monotonic presentation. The lossless-video
check separately examines **every** recorded physical frame after the initial
boot/unlisted first movement states, against independently generated complete
states. It does not use a crop, fuzzy match, or a favorable screenshot selection.

Every emulator probe enables the strict too-fast-VRAM-access callback and watches
VDP writes. The continuous route recorded 445,246 VRAM data writes, 8,282 register
writes, zero commands, no sprite enable and no indirect command writes after the
first completed update. These counts cover that bounded keyboard route,
not all possible gameplay. Tests run on openMSX's Panasonic FS-A1WSX machine with
the standard 3.579545 MHz Z80 and real VDP timing. Physical hardware is untested.

## Measured limits

The footer/lives movement ledger (`profile-_xkiwshs`) measures 480 presentations:
17.946 ms mean active work and 31.660 ms maximum. A control run without routine
breakpoints matches camera/tick states and total time. The previous layout's
movement ledger measured 18.422/35.882 ms, but elapsed-tick input means the same
key sequence can visit different positions as cadence changes. These observations
do not isolate the cost of changing the HUD. The older figures below are retained
as historical baseline results for the R18 layout.

The reproducible [cycle ledger and performance policy](PERFORMANCE.md) adds
per-routine inclusive/self costs, frame budgets, a control run, and an editable
workbook exporter. Run `gnumake profile-hud-lab` to refresh its raw evidence.
Use `gnumake profile-movement-experiments` for separate horizontal/vertical,
normal/Shift, camera-tile crossing and fine-phase measurements.

### Historical R18 baseline

The continuous route averages 31.03 ms between software presentations and reaches
39.88 ms: 138 one-refresh and 173 two-refresh intervals. Main rendering work
averages 20.01 ms and reaches 36.28 ms. The scene-preparation segment, including
camera decoding and ring maintenance, averages 2.01 ms in that route. The simple
keyboard/hold probe averages 12.67 ms of main work and 22.58 ms per presentation.
These workloads visit different positions; do not treat them as comparable
whole-game benchmarks or a guarantee for arbitrary future assets.

The continuous route performs zero complete world-cache rebuilds, at most 128
incoming world IDs per update, and one cold refill of the second name table.
There are no bitmap copies or software VRAM block relocation. Remaining CPU work
comes mainly from the compensated HUD and its uploads. Presentation varies
between nominal 25 and 50 Hz; the engine does not promise stable 50 Hz. The
separate VBlank clock keeps normal/Shift world velocity correct across those
intervals. Further HUD optimization could improve presentation smoothness.

Direct matrix teleports can take three refreshes (59.81 ms) and refill the cache;
these are injected diagnostic jumps, not arrow-key movement. Physical hardware
and integration with the production game/AI/audio have not been tested here.

Hardware references: Yamaha [V9938 application manual, R18 display adjust](https://map.grauw.nl/resources/video/v9938/v9938.pdf)
and [V9958 technical data book](https://map.grauw.nl/resources/video/yamaha_v9958_ocr.pdf).


## Playable stage-one cartridge

The separate gameplay prototype reuses the native core, hardware car sprites,
PSG audio and live side HUD. Run `gnumake run-first-stage`, or reproduce the
keyboard-only full-stage checks with `gnumake test-first-stage`. See
[FIRST-STAGE.md](FIRST-STAGE.md) for the scoped graphics authorization, controls,
completion behavior, measured performance and remaining limits.

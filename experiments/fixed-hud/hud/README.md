# Fixed HUD module contract

This is the experimental full-session SCREEN4 HUD. Interface extraction is
limited to the HUD already requested by the user. Broader rendering, scrolling,
viewport, transfer and profiling extraction is deferred to
[issue #32](https://github.com/sandersouza/msxgp-newrallyx/issues/32).

## Compile-time selection

```sh
make run-experiments HUD_VARIANT=compact
make run-experiments HUD_VARIANT=classic
make run-experiments TEST_MODE=1 HUD_VARIANT=compact
```

`compact.inc` selects the small4x5 white ROUND label and number, symmetric gauge,
2x2 red endpoints, six1x1 yellow ticks and a2x3 red center. Endpoints cover
columns0..1 and46..47 of the full48px bar. Yellow coordinates6,12,18,29,35,41
and all red pixels reflect exactly around x=23.5. Remaining fuel is anchored
right, so empty space advances from left to right.

`classic.inc` retains the preceding small FUEL/native8x8 RND presentation,
including the preceding gauge marks. It is an explicit visual rollback variant;
it does not claim to have the new symmetric gauge. Retaining its former marks
also preserves the existing41-character static HUD allocation. Both variants
use the same API and native game rules. Classic files have a separate
`-hud-classic` bundle/export suffix, so comparison does not replace compact ROMs.

The selected include defines style constants, includes `native-inputs.inc`, and
includes the generated implementation. These directives assemble directly;
selection adds no runtime dispatch, data copies or wrapper calls. The font
experiment itself has its own code/data cost and is included in the measured
HUD parent routine. The old first-stage and functional audio builds keep their
previous producer and assets.

`hud_module.py` reads the constants in the selected include for the static
compositor and emulator oracle. `session_cosmetics.py` generates the full-session
implementation from the existing cached HUD worker. No original game data is
stored in these sources. New4x5 glyphs are authored in `hud_module.py`; native
score digits and complete life masks remain contributor-local1:1 assets.

## Public API

| Entry | Context | Responsibility |
|---|---|---|
| `GameHUD_Init` | DI, display off, main Page0 RAM selected | Invalidate source/value caches; upload colors and two immutable complete life patterns. |
| `GameHUD_Prepare` | Foreground, main Page0 RAM selected | Read changed fields; decode saturated display keys; prepare dirty patterns and scroll-compensated SAT in RAM. No VRAM writes. |
| `GameHUD_Commit` | DI, caller-owned blanking/publication window | Upload dirty32-byte pattern groups and changed56-byte SAT. Skip unchanged transfers. |

Call `Init -> (Prepare -> Commit)*`. Do not call Prepare again before committing
its result. `cy` must describe the next published R23 epoch. Caller owns mapper
selection, palette compatibility, VDP mode and synchronization. These routines
are not reentrant. AF/flags, BC, DE, HL and IY are caller-saved; IX is preserved.
No heap, runtime module loader, extra sprite slot or new per-frame staging area
is introduced by include selection.

The input adapter declares read-only symbols for native high score, score,
round, lives and fuel. Scores are eight native digits in4,5,6,7,0,1,2,3 order;
display clamps at999999 and hides leading zeroes, keeping a single zero. Round
uses the full-session display accessor, native bias and99 display cap. Lives
display at most four complete icons. Fuel uses floor(min(value,60)*48/60).
These are display limits; they do not rewrite native score or progression.
Another game must supply a compatible adapter/decoder, not assume these native
encodings or addresses. Bosconian reuse is a future candidate, not validated.

## Resource ownership and hardware limits

| Resource | Ownership |
|---|---|
| RAM2000..21BF | Fourteen32-byte prepared patterns. |
| RAM2200..2237 | Fourteen4-byte SAT records. |
| RAM2240..225B | Value/sentinel keys. |
| RAM2260..22CD | Existing preparation scratch, source snapshots and SAT offsets. |
| RAM2C00 onward | Compact round worker/font loaded with the cold startup program; exact end in `lab.sym`, below3000. This is the styling worker, not a module dispatch cost. |
| VRAM2C80..2E3F | HUD sprite patterns144..199. |
| VRAM1800..18DF | HUD sprite colors. |
| VRAM1A00..1A37 | SAT slots0..13; world sprites follow at14..31. |
| Static characters96..136 | Forty-one allocated slots shared by selected static HUD phases. Existing terrain/edge allocation is preserved. |

The palette, sprite OR rules, physical eight-sprite scanline limit and
sentinel216 handling remain enabled. Sentinel compensation shifts complete
patterns without clipping opaque source pixels. Yellow ticks use the existing
three fuel sprites; static red/yellow/black in one character row would violate
SCREEN4's two-color-per-row contract. No new graphical reduction is applied.

## Verification and timing

```sh
make test-experiments
make test-experiments TEST_MODE=1
make profile-experiments
```

The independent oracle checks every stable HUD background pixel, SAT record and
dynamic pattern, together with world/boundary pixels. Unit cases cover all61
fuel values, display saturation, gauge reflection and compact text placement.
`classic` is separately built and checked through the same oracle.

Use the ROM-bound cycle ledger/workbook under `outputs/full-session` for current
costs. Prepare is foreground work and Commit is part of synchronized
publication; neither implies that all logic fits inside VBlank. Inclusive HUD
costs already contain the font worker; do not add them together. The short
three-enemy profile is not a full-course or physical-hardware qualification.

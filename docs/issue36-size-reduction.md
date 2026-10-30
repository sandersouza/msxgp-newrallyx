# Lossless cartridge size reduction

Issue: [#36](https://github.com/sandersouza/msxgp-newrallyx/issues/36).
Implemented and verified locally on 2026-10-29, following the
[graphics storage audit](issue36-rom-audit.md). No new graphics, gameplay,
audio or presentation concession is introduced.

This retained before/after comparison uses the 128 KiB profile, now selected
with `MAPPER=1`. The current default 64 KiB image retains the same reduced size
and has separate [RAM-profile validation](ram-profile-validation.md).

## Result

| Default full-session SCREEN 4 | Banks of 16,384 bytes | Image bytes |
| --- | ---: | ---: |
| Before | 255 | 4,177,920 |
| Same-bank table aliases and code packing | 137 | 2,244,608 |
| Cold replay packed into remaining holes | **125** | **2,048,000** |
| Reduction | **130** | **2,129,920 (50.98%)** |

The complete programmed image is 1.953125 MiB, with **49,152 bytes (three
banks) of growth room below 2 MiB**. This is the actual generated ROM size,
not a compressed download or a storage estimate.

Before SHA-256:
`98ce0135b628a1837a3d6df2910f572e466b4bffe465344238f4c44a9015346a`.
After SHA-256:
`b80c7b72ace0ee0e9686127a156249d3cceaa3292ddea767ad1497950badbfb1`.
The baseline is preserved locally in ignored
`references/issue36/baseline/full-session/`. Repeated default builds produce the
same reduced hash. The investigation started from `435180f`; implementation
follows the audit commit `153300d`. The evidence snapshot records source hashes
for the uncommitted implementation.

Build with `make build`; run with `make run`. Exported test cartridges remain
under `outputs/test-roms/`, including the `[ASCII16]` filename hint for WebMSX.
`TEST_MODE=1`, `HUD_VARIANT=classic` and `HARDWARE_CHECK=0` also build at
2,048,000 bytes. The independently maintained `LEGACY=1` ROM remains
2,097,152 bytes and byte-identical to its previous baseline.

## Storage changes

`hud_programs.compile_packet` can now point its `LD HL` operands directly at
byte-verified raw pattern/color tables. It emits the same instruction sequence,
transfer spans and resident calls as before, without embedding another literal
copy. A mismatched, ambiguous or out-of-bank source is a build error.

`rom_pack.py` places HUD code into gaps in the current phase bank and boundary
code into the corresponding world-edge bank. It protects the existing tables,
padding, name/radar code, pointer fields, complete cost blocks and the actual
assembled ring-worker footprint. Code is packed largest-first with deterministic
tie breaking. A full bank fails the build instead of selecting a slower path.
The extra small phase-local copies bring code storage to 375,166 bytes, while
eliminating 118 dedicated transfer banks. Original atlases and initial boundary
packets remain available; no unproven dead-data deletion is needed.

The startup replay uses the same opcodes and command spans. Existing bank/address
chains and same-bank literal references now place its bytes in the remaining
graphics-bank gaps. The encoded stream grows from 182,392 to 186,591 bytes due
to changed literal reuse and fragmentation, with 52 fragments and 51 chains
instead of 11. Removing its 12 dedicated banks still saves 196,608 image bytes.
This is cold-only work; no new gameplay decoder, RAM buffer, VRAM allocation or
active-transfer instruction is introduced.

Bank constants and tables are generated from the compact layout before linking.
All 14,709 compiled CALL/JP operand sites are checked by the audit. The count
increases because shared empty transfers are duplicated locally. The applied
ownership ledger accounts for all 125 banks exactly once; transfer-family byte
counts refer to overlapping shared banks and must not be summed as ownership.

## Size gate and artifact publication

`scripts/msx/cartridge_size.py` exposes the preferred **2,097,152-byte** target
and the hard **4,194,304-byte** ceiling. The build records exact bytes, hash,
bank count and both headrooms in `cartridge-size.json`. Complete 16 KiB banks
are required. Above 4 MiB is rejected before replacing the existing ROM;
successful writes use a temporary sibling followed by atomic replacement.
The same check guards relinking and both exported cartridge filenames.

Synthetic boundary tests cover exactly 2 MiB, exactly 4 MiB, misalignment and
overflow. A rejected export leaves the previous ROM and size report unchanged.
Exceeding the preferred target remains visible in the report; using a fallback
above 2 MiB would still require the issue's measured justification and review.

## Verification

The [evidence snapshot](measurements/cartridge/issue36-size-reduction.json)
contains only metadata, hashes and measurements. Generated ROMs, captures and
raw emulator evidence remain ignored locally.

- Independent ROM decoding compared all **4,096 HUD and 288 boundary
  transitions**, their actual source bytes/destinations, normalized instruction
  bytes and cycle estimates. It also compared every boot destination, payload,
  command order and deadline across **71 states / 25,434 commands**. All round
  maps/terrain, raw graphics fields, native/player/audio/navigation banks and
  static UI/decor banks remain byte-identical after bank relocation.
- Native openMSX HUD execution passed **33,280 cases**: every directed phase
  transition and cold start in all eight physical pattern sets. Full 128 KiB
  VRAM guards, mapper restoration, interrupt ownership and strict VDP access
  checks passed; interrupts were exercised 5,758 times.
- Boot pixels, native publication ticks, title/footer and 14 real-keyboard skip
  cases passed. Maximum measured skip latency was 13.78 ms. The hardware-check
  omission build passed start/graphics contracts with shared workers retained.
- `make test-experiments` passed controls, start, integration, two-player,
  flags, attract, radar, smoke, rocks, speed, 16,000-refresh steering, audio and
  sprite contracts. Test-mode controls and classic-HUD start/graphics also passed.
- The general suite passed **446 tests**; the final component suite ran **83
  tests, with 82 passing and one explicit emulator-dependent skip**. The native
  emulator checks above ran separately.

Matched performance uses openMSX 21.0, Panasonic FS-A1WSX with a 128 KiB mapper,
standard Z80 at 3,579,545 Hz, hardware sprite limits, HUD and PSG enabled. The
same real keyboard route advances to native round 5, layout 1, with three moving
enemies. Both ROMs have 356 measured intervals and 238 active-play intervals.
All exposed player/camera/enemy/input/tick records match; total duration matches
within 0.01 CPU cycle, allowing the profiler's existing five-cycle per-interval
observation jitter. Each run also matches its uninstrumented control.

| Active-play measurement | Before | After |
| --- | ---: | ---: |
| Presented gameplay FPS | 29.90315 | 29.90315 |
| Mean foreground work, CPU cycles | 81,013.56 | 81,013.56 |
| P95 foreground work, CPU cycles | 109,983 | 109,983 |
| Maximum foreground work, CPU cycles | 127,375 | 127,375 |
| Intervals taking more than two refreshes | 1 / 238 | 1 / 238 |

Video refresh is separately **59.92274 Hz**, or 59,736 CPU cycles. Two refreshes
provide 119,472 full-frame cycles; mean work leaves about 38,458 cycles, while
the existing worst-case work exceeds that budget by about 7,903 cycles. The
ledger records per-routine calls, inclusive/self mean/tail/maximum costs and
waits without adding parent and child costs. The observed VDP VR span is 11,172
cycles; a 5,000-cycle usable reserve remains a planning assumption. This change
preserves the measured timing, including the existing tail limitation.

This is a short deterministic active-play sample and extensive automated
regression, not complete human-course or physical-cartridge acceptance. ASCII16
mapping and the 128 KiB system mapper were verified in openMSX. The reduced image
fits a 2 MiB storage capacity; flash padding, board/register implementation and
physical hardware compatibility remain to be verified on the intended cartridge.

## Reproduce the checks

```sh
make build
.venv/bin/python -B src/screen4/rom_audit.py --output references/issue36/packed-audit.json
.venv/bin/python -B src/screen4/rom_pack_verify.py --before references/issue36/baseline/full-session --after references/experiments/full-session --output references/issue36/packed-equivalence.json
.venv/bin/python -B src/screen4/test_hud_programs.py --bundle references/experiments/full-session --out references/issue36/hud-native-proof
make test-experiments
.venv/bin/python -B src/screen4/session_profile.py --bundle references/experiments/full-session
.venv/bin/python -B src/screen4/session_report.py --bundle references/experiments/full-session --out references/issue36/packed-ledger
```

The independent before/after comparison requires the preserved baseline bundle;
it is not distributed. A contributor can rebuild the pre-reduction source at
`153300d` with their local game inputs. Keep the baseline and reduced profiles
in separate directories. The baseline audit remains a dated investigation;
the new audit recognizes the applied shared-bank layout.

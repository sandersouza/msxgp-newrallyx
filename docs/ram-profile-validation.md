# RAM-profile optimization and validation

The 64 KiB cartridge is now the default. `make run` builds and launches it with
64 KiB of emulator RAM; `make run MAPPER=1` selects the preserved version
requiring at least 128 KiB of mapper RAM. Both remain buildable, with separate
bundles/exports and **2,048,000-byte** images. Both require 128 KiB VRAM and ASCII16.

Accepted graphics, palette, complete cars, HUD, maps and PSG resources are
unchanged: all **84 resource files** listed in the original trial match both
final profiles. The 128 KiB cartridge and its frozen module symbols remain
identical. See [storage/API contracts and hashes](ram64-variant.md) and the
[validation record](measurements/hardware/ram-profile-validation.json).

## Accepted changes

- Replace the 64 KiB refill `INIR` loop with 242 paced `INI` instructions in an
  existing startup-worker reservation. Preserve VDP timing and all read bytes.
- Infer metadata pointer pages from H, removing ten redundant stores per refill.
  Skip captured-mask scanning until capture, reusing an unused bank-variable alias.
- Remove redundant record selection, counter reset and return wrappers. Copy
  complete actor/flag glyphs directly between existing Page0 buffers; use the
  existing paced upload worker and eight-bit byte-count calculation.
- Unroll exact 20+24-byte motion snapshot/restore copies. A shared BC=44 counter
  still returns zero. Existing buffers, IFF ownership, stack and IX/IY are retained.
- Widen the 64 KiB pre-motion snapshot margin conservatively on both axes, so a
  doubled native step cannot enter the contact-risk band before a snapshot exists.

No new ROM bank, mapper segment, VRAM buffer, active IRQ work, synchronization
wait or graphical reduction was introduced. Default cold code ends at `1F4E`;
the read worker ends at `2E61`, within existing reservations. Cold cache prewarm
increased **448 cycles / 0.125 ms** in the controlled fixture, outside active play.

Long steering rejected an otherwise pixel-correct cache prototype: its changed
timing exposed a corner where the old snapshot predicate did not anticipate
contact. A narrower axis-specific predicate also failed a replay and was
discarded. The final ROM uses the conservative margin; the 128 KiB baseline is
preserved. Failed prototype hashes/traces stay under ignored
`references/issue36/ram-optimization/` and are excluded from current evidence.

## Measured comparison

CPU 3,579,545 Hz; physical refresh **59.922743 Hz**, distinct from presentation
rate. HUD, audio and real sprite limits remain enabled. Actual keyboard
coin/start/F5 input reaches asserted native populations: round5 has three
enemies, round10 five, round13 six. The harness never overrides population.

| Native enemies | Previous 64 KiB FPS | Current 64 KiB FPS | Preserved `MAPPER=1` FPS |
| --- | ---: | ---: | ---: |
| 3 | 29.1025 | **29.4677** | 29.9031 |
| 5 | 27.6772 | **27.8407** | 28.4995 |
| 6 | 26.5929 | **26.7927** | 27.6605 |

The three-enemy sample has 238 active intervals per profile. Previous/current
64 KiB three-refresh intervals decrease **14 to 8**; mean work decreases
**84,939.86 to 83,783.00 cycles**. The 128 KiB sample has one late interval.
Heavier samples have different active/death partitions: five enemies
236/236/175 active intervals and six enemies 150/152/156, respectively.
Identical scripts do not imply frame-identical trajectories when timing changes;
these compare workloads, not isolated marginal instruction savings. All sample
paths, counts, mean/p95/max costs and hashes are in the
[comparison ledger](measurements/timing/ram-profile-comparison.json).

Not every observed maximum improves: six-enemy worst work rises from 48.237 to
49.954 ms, while p95 falls from 44.635 to 43.291 ms. The current peak includes a
large dirty-sprite preparation; the 128 KiB trace reaches the same position with
the same 107,067-cycle logic/preparation span. Its shorter render span confirms
that the 64 KiB cache still has a measurable cost. The prior 64 KiB trace is at
a different position/step on that presentation. All three samples use only
two/three-refresh intervals; this is not a claim of universally lower tail cost.

| Controlled component | Before cycles | After cycles | Saved time at 3,579,545 Hz |
| --- | ---: | ---: | ---: |
| Cache cold-path fixture, mean | 11,727.93 | 10,272.46 | 406.61 us |
| Cache reload fixture, mean | 8,576.41 | 6,480.80 | 585.44 us |
| Cache warm-path fixture, mean | 4,242.75 | 4,151.53 | 25.48 us |
| Motion snapshot, shared risk=8 path | 1,141 | 920 | 61.74 us |
| Motion restore, shared risk=8 path | 1,269 | 1,048 | 61.74 us |
| Actor/flag glyph clone | 987 | 470 | 144.43 us |

Cache fixtures include common setup, CALL/RET and IRQ; motion costs are
entry-through-RET with IRQ disabled. These synthetic costs are not per-frame
reductions. Inclusive parents overlap children: never add their costs.
The [versioned workbook](cycle-budget.xlsx) includes `RAM profiles`, current
three-enemy frame/routine/raster/event ledgers, and ROM-bound verification.
Physical VBlank, drawing-phase work, full-frame budget and the unverified
5,000-cycle planning reserve stay separate. Earlier workbooks retain their
original hashes/workloads under `docs/measurements/timing/archive/`.

## Test battery

- General suite: **448 passed**. SCREEN4 component suite: **89 passed, one
  skipped**. Both full-session emulator batteries pass on the final hashes:
  startup/module/skip, controls, challenge resume, two-player turns, flags/radar,
  attract, smoke, enemy-rock behavior, challenge speed, PSG and full-car clipping.
- Current 64 KiB core scenarios contribute **592 selected graphics snapshots**
  checked against the independent world/HUD/full-car oracle; controls and
  optional variants have separate proofs. These include controlled fixtures
  and keyboard-driven scenarios, not 592 natural play sessions.
- Cache differential: **524,288 comparisons** against the retained old ROM:
  two layouts x 64 phases x 1,024 active masks x two blink states x cold/warm
  paths, cycling all eight CPU records. Every used glyph byte, active name
  program and all 1,024 name-RAM bytes match, with strict real VDP callbacks.
  Synthetic positions/masks are explicitly identified.
- Direct actor/flag cloning: **640 combinations** per ROM, covering eight CPU
  records, ten flag glyphs and eight actor slots. Check the entire 512-byte
  destination buffer, unchanged 2,048-byte source, SP and IX/IY. Caller-clobbered
  BC is restored by the real caller. The isolated cost includes RET, IRQ disabled;
  no per-frame frequency or integrated FPS benefit is inferred from this fixture.
- Motion matrix: **9,604 cases**, zero unprotected reachable corners within the
  conservative six-unit bound, **9,034 actual restores**. Check all 44 bytes,
  preserved heading/velocity/centering, counter wrap, source data, SP, BC and
  IX/IY. Old unprotected cases are retained as baseline evidence, not a passing proof.
- Final 64 KiB ROM passes **16,000 and 32,000-refresh steering replays**, seeds
  12345/98765, on stock unexpanded FS-A1FX in openMSX. The 128 KiB battery
  includes its own 16,000-refresh replay.
- Both profiles pass ordinary/S/L last-flag orders and paused clear, test
  controls, classic HUD controls/start/radar, no-check start and no-logo boot.
  All ten full-session build combinations retain the same image size.
  Frozen 128 KiB module profiles retain exact bytes/symbols.

## Reproduce and remaining acceptance

```sh
make build
make test-experiments
make build MAPPER=1
make test-experiments MAPPER=1
make verify-module-layout MAPPER=1
make profile-experiments
NRX_PROFILE_ROUND=10 NRX_PROFILE_ENEMIES=5 NRX_PROFILE_FRAMES=240 make profile-experiments
NRX_PROFILE_ROUND=13 NRX_PROFILE_ENEMIES=6 NRX_PROFILE_FRAMES=240 make profile-experiments
# Restore the canonical three-enemy sample before publishing the workbook:
make profile-experiments
make timing-workbook
```

`session_flag_cache_verify.py`, `session_flag_clone_verify.py` and
`session_motion_verify.py` expose bundle/baseline/layout options via `--help`.
Original data, ROMs and snapshots remain
ignored under `references/`. Workbooks and authored metadata stay under `docs/`.

The user's play observation found no major slowdown or stutter; it is not a
complete-course verdict. Automated results are from openMSX, not the physical
multicart. Heavy native rounds still fall below 30 presented FPS; the 64 KiB
sample remains slower than 128 KiB. Full-course, physical hardware and human
audio/perceptual acceptance remain open. Further optimization needs paired
evidence; no universal no-regression or all-microseconds-exhausted claim is made.

# Loaded-round performance and player pacing

The full-game build now uses **60 Hz display output** and smaller native/terrain
bursts to reduce gameplay stuttering. The original logical tick remains 16.5 ms.
Two natural eight-round routes pass the native-rate, physical-camera and fixed
sprite gates, with **under 2% of active foreground loops exceeding 40 ms** in
every measured round. Original scenery, colors, complete cars, fuel, the full
HUD and real V9958 sprite limits remain enabled.

Qualified ROM SHA-256:
`5dcebd21cc0b687e032d9a1357c7049ff45d35811f642811a3c782a26b327071`.
`make build` publishes this image at `references/build/newrallyx.rom` and
`latest.rom`; `make run` launches it. The independent rebuild is
`references/build/issue12-stutter-qualified-v127/`, byte-identical to the v125
cartridge used by both natural routes. Bounded stages retain their 50 Hz default;
`make build HZ=50` explicitly selects a full-game 50 Hz diagnostic.

## Changes

- Count all native ticks in each foreground loop. The post-copy tail stops once
  two ticks have run. A reserved post-header tick can still bring a header-idle
  loop to three; the previous maximum was six. Elapsed-time debt remains bounded.
- At 60 Hz, allow two ordinary terrain commands on a light loop, one after two
  native ticks, and four for an incomplete exposed edge. Required edges retain
  priority over optional prefetch. The explicit 50 Hz path keeps its one/eight
  command budgets.
- At each actual maze latch, move vertical scroll halfway toward the latest
  snapshot, rounded up and capped at four pixels. This avoids consuming a whole
  snapshot and waiting for the next one. Player, fuel, radar and footer still use
  the same actual R23; scene initialization still snaps immediately.
- Batch complete 24x24 flower cells outside the world, using the existing signed
  flower phase table. Preserve exact pixels and fall back at physical seams,
  objects, smoke or explosions. Remember rejected cells only within one stream
  call, so adjacent tiles do not repeat an identical batch eligibility scan.
- Check ownership before replacement safety, since a cache hit copies nothing.
  Validate each row in contiguous pieces at the torus seam, retaining the invalid
  X sentinel and every coordinate-pair comparison.

No native enemy AI, movement rules, asset dimensions or sprite drawings changed.
Factory Panasonic turbo remains limited to pure CPU work; VDP I/O uses 3.58 MHz.

## Measured pacing

The same host steering margin five was used for the old v106 baseline and the
primary current route. Routes adapt to enemy positions and timing, so this is
not an identical-path benchmark. Active stalls remain in the cadence denominator.

| Round | Enemies | Previous p95 loop, ms | Current p95 loop, ms | Previous loops over 40 ms | Current loops over 40 ms |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 37.44 | 31.22 | 2.85% | 0.00% |
| 2 | 2 | 38.18 | 31.94 | 3.29% | 0.06% |
| 3, challenge | 7 static | 40.56 | 34.30 | 5.81% | 0.21% |
| 4 | 3 | 40.02 | 34.84 | 5.06% | 0.68% |
| 5 | 3 | 42.48 | 33.82 | 7.30% | 0.35% |
| 6 | 4 | 47.45 | 36.06 | 16.67% | 1.04% |

Baseline: sealed `issue12-stutter-baseline-v107`, using the accepted v106 ROM.
The new analyzer computes the over-40-ms counts from its unchanged cadence TSV.
Current: sealed `issue12-stutter-route-v125`.

| Round | Native ticks/s | Complete foreground snapshots/s | Visible vertical updates/s | p95 loop, ms | Loops over 40 ms |
| --- | --- | --- | --- | --- | --- |
| 1 | 60.585 | 49.85 | 53.54 | 31.22 | 0.00% |
| 2 | 60.507 | 46.11 | 48.44 | 31.94 | 0.06% |
| 3, challenge | 59.802 | 43.63 | 48.81 | 34.30 | 0.21% |
| 4 | 60.312 | 41.63 | 45.46 | 34.84 | 0.68% |
| 5 | 60.003 | 41.70 | 46.53 | 33.82 | 0.35% |
| 6 | 59.526 | 38.70 | 44.49 | 36.06 | 1.04% |
| 7, challenge | 60.131 | 41.84 | 50.09 | 33.70 | 0.38% |
| 8 | 57.938 | 38.24 | 45.08 | 36.75 | 0.91% |

The independent margin-seven route, `issue12-stutter-route-m7-v125`, measures
57.916–60.608 native ticks/s, 45.65–53.22 vertical updates/s, p95 loops at most
37.63 ms and at most 1.88% over 40 ms. Both routes pass minimum 57 native ticks/s,
minimum 40 vertical updates/s, maximum four-pixel scroll steps, p95 at most 39 ms
and at most 3% over 40 ms. These gates apply to sufficiently long active samples.

These are separate clocks, **not a 60 FPS claim**. Physical output is about
59.92 Hz. Moving enemies and horizontal camera preparation still follow the
foreground loop, 36.95–49.85 snapshots/s across both routes. Vertical cadence
counts changes during adjacent monotonic native Y movement and excludes stops,
turns and native stalls; overall native cadence retains active stalls.

There is a measured speed tradeoff: the primary route drops 192 ticks across
eight rounds and its lowest complete five-second window is 52.29 ticks/s; the
secondary drops 239 and reaches 55.03. The old six-round route dropped 28 and
reached 58.87. Round averages remain within about 4.5% of the original tick rate,
but the new policy does not establish full-speed execution in every short window.
Individual active loops still reach 52.53 ms. A 45-Hz vertical-update target is
also not met in every round. Occasional stutters, later moving populations above
four cars, complete loaded RGB/culling readability and physical hardware remain
review limits. Real hardware culling is retained.

Strict scheduling deadlines that reduced native speed to 45–54 Hz were rejected.
A third catch-up tick under large debt improved some rates but exceeded the
stutter gate on one route, so it is not part of the qualified cartridge.

## Verification

All bundles below are ignored local evidence. Natural routes contain real
credit/start, steering and smoke inputs, without guest-state writes.

| Evidence | Result |
| --- | --- |
| `issue12-stutter-route-v125`, `issue12-stutter-route-m7-v125` | Two naturally completed eight-round routes; all selected cadence, pacing, ownership and fixed-sprite gates pass |
| Primary fixed-sprite observer | Zero errors in 18,336 player, 18,692 fuel, 18,681 footer and 93,460 radar samples |
| Secondary fixed-sprite observer | Zero errors in 18,224 player, 18,446 fuel, 18,436 footer and 92,230 radar samples |
| Both physical camera traces | 32,685 adjacent active refreshes, maximum four-pixel step; displayed tile ownership checked |
| `issue12-stutter-evidence-v127` | 50 independent natural cache, smoke, complete-car and eight-digit HUD snapshots pass |
| `issue12-stutter-cars-v127` | 13,496 complete-car facing/clipping cases pass with real IRQs |
| `issue12-stutter-rows-v127` | 66,560 executed ownership-row cases: all global X values, torus seams, invalid sentinel and every X/Y corruption position |
| `issue12-stutter-scroll-v127`, `issue12-stutter-clock-v127` | 65,792 circular-scroll/initial-latch cases and 384 elapsed-clock cases pass |
| Matching `session`, `state`, `attract` bundles at v127 | Two-player lifecycle, partial-board restoration and autonomous attract pass |
| `issue12-stutter-scenes-v127` | 254 explicitly seeded map/object/header transitions pass; separate from natural completion |
| Authored checks | 368 tests pass; bounded Issue 11 ROM remains byte-identical |

The secondary route records eight seconds of actual sixth-round scanout:
479 frames at 320x240 over 7.994 seconds. Sampled frames retain player centering,
the full fuel gauge, radar and original pixels; this is separate from complete
human gameplay acceptance. Header reservation maximum is 4.350 ms. Recordings
and derived review files remain ignored.

## Previous v106 correction

The preceding cartridge fixed the player's vertical displacement under enemy
load by publishing its complete SAT pair in the maze IRQ against actual R23,
together with fuel and radar. It reproduced 335 incorrect player pairs in 4,009
samples on the older v83 ROM. Its accepted 50 Hz image was
`c51e8aef26e0ab445d713bfeea2187452f21479abc2c44fdc2b3ce5b8ca83bb8`.
Two six-round routes qualified native cadence and fixed-sprite coherence, but
the user still observed too much gameplay stuttering. That feedback motivated
the current loop-duration and over-40-ms gates.


## Previous v75 cadence and concessions

The external route uses real keyboard credit/start, steering and smoke inputs;
it never writes guest state. Native tick counters are divided by actual emulated
elapsed time during active play. Long active stalls stay in the denominator.
Death, loading and bonus conversion are separate states. Physical VBlank counts,
foreground loops, cache holds, clock debt and dropped ticks are recorded
separately. An adaptive route changes with timing, so it is not a fixed sequence
for exact before/after percentage claims.

| Displayed round | Enemies | Native ticks/s | Presentation loops/s | Lowest complete 5 s window, ticks/s |
| --- | --- | --- | --- | --- |
| 1 | 1 | 60.583 | 37.72 | 60.51 |
| 2 | 2 | 60.598 | 32.09 | 60.52 |
| 3, challenge | 7 | 60.580 | 32.94 | 60.00 |
| 4 | 3 | 60.517 | 32.89 | 59.40 |
| 5 | 3 | 60.574 | 30.67 | 60.43 |
| 6 | 4 | 60.573 | 29.97 | 59.63 |
| 7, challenge | 7 | 60.171 | 33.47 | 58.48 |
| 8 | 4 | 60.498 | 31.10 | 60.34 |

These values come from sealed `issue12-perf-qualified-route-v75/report.json`.
The run passed a minimum **57 native ticks/s in every measured round**. Maximum
individual active loop durations were 51–65 ms. Ten ticks were dropped at the
bounded debt limit in round 7; other measured rounds dropped none. Independent
scene evidence counts 243 cache holds in 10,421 foreground loops (2.33%), at most
four consecutive. These are loop counts, not physical refreshes. Brief stutters
remain; the reference run no longer has sustained enemy-count-dependent game
speed loss.

The prior v13 implementation measured approximately 55/45/37/39 native ticks/s
in its first four loaded rounds. A current forced-3.58 MHz diagnostic still
measures approximately 51–60 ticks/s over eight rounds. Routes differ, and the
current 60-tick result **depends on the reference machine's factory turbo**.
Unsupported MSX machines keep their base clock; equivalent throughput there
has not been established.

## Scheduling, terrain and enemy work

VBlank elapsed time owns the native clock instead of each foreground loop.
The scheduler retains at most twelve pending ticks and executes at most six
per loop, using both the post-copy tail and otherwise idle header synchronization
time. Native clocks remain together. A bounded camera/native separation prevents
unlimited catch-up ahead of the displayed world.

A temporary page0 RAM overlay uses a spare segment of the existing 128 KB mapper.
Code occupies `$1000..$16b3`; 4,096 bytes at `$2000..$2fff` tag each torus tile
with its exact world coordinates. Slot/subslot/mapper configuration is restored
before BIOS-facing paths. Stream jobs skip owned tiles, finish the nearest
incomplete hidden border first, and discard stale jobs which could alias the
visible viewport. The camera advances only after every newly exposed tile is
owned. Runtime observers check every visible tile at each camera validation,
overlay code bytes and mapper restoration.

Clean 24x24 original cells use one exact HMMM copy, or HMMV only when every source
pixel has the same color. Exact 8x48 strips also combine eligible column work.
Object ownership, native smoke, published smoke and explosion state reject unsafe
batching. Conservative native smoke-row flags skip per-tile checks only when
they prove an area empty; independent snapshots reject a hidden nonempty row.

Enemy preparation reuses world/radar coordinates only for unchanged native
coordinates. Already visible, unclipped complete masks reuse preparation when
their source pose remains identical. Other cases take the complete adapter.
Direct IX records, source-order SAT compaction and a single terminator retain
the previous iteration's renderer improvements. Zero-velocity motion avoids
redundant fractional arithmetic only within the original normalized range;
the original cell-pointer writer still runs. Stationary seven-car AI reuses
results from actual original calls under checked input/smoke/stun/startup guards.
All other states execute original logic.

## Factory clock and raster ownership

The game detects Panasonic switched device 8 and its turbo-available bit. Pure
CPU scopes use the factory **5,369,318 Hz** mode. VDP transactions and raster IRQs
use **3,579,545 Hz**; IRQ return restores an interrupted pure-CPU scope. The
controller's turbo VDP wait behavior makes leaving turbo enabled during graphics
work counterproductive. No clock is synthesized or forced on unsupported hardware.
See the primary [openMSX Panasonic controller implementation](https://github.com/openMSX/openMSX/blob/RELEASE_21_0/src/MSXMatsushita.cc).

The launcher follows machine-selected frequency. In openMSX,
`z80_freq_locked true` uses the machine clock, while `false` forces the user's
frequency value. Earlier pure-CPU experiments inadvertently ran at forced base
frequency despite the controller's turbo status bit. Their throughput is excluded
from factory-clock qualification. The current route records actual CPU frequency
and instruction duration, checks native motion at 5.37 MHz, and checks every
observed sprite upload, command wait and radar IRQ at 3.58 MHz. See the primary
[CPU frequency selection code](https://github.com/openMSX/openMSX/blob/RELEASE_21_0/src/cpu/CPUCore.cc).

The maze IRQ publishes the player dot and twelve radar body sprites after the
R23 scroll latch, in scan order before their fetches. The eight-round run passed
**74,798 live pre-fetch checks with zero mismatches**, including the player dot.
Header reservation maximum was 7.285 ms over 14,960 reservations. IRQ code-write
guards, cold-code canaries and exact scene/source-pixel checks also pass. The
cold-code/stack gap is 132 bytes; allocator guards retain the 128-byte minimum.

## Qualification and remaining review

All original inputs and generated evidence remain ignored under `references/`.

| Evidence bundle | Verified result |
| --- | --- |
| `issue12-perf-qualified-route-v75` | Eight natural rounds; cadence, radar, header, tile ownership, mapper and code guards |
| `issue12-perf-qualified-evidence-v75` | 41 independent cache/smoke/HUD snapshots and 34 complete enemy images |
| `issue12-perf-factory-cars-v73` | 13,496 complete-car cases with active raster IRQs, clipping/cache/destination/reappearance checks |
| `issue12-perf-smokerows-ai-v71` | 7,680 three-call original AI comparisons, including valid-but-empty smoke rows and key mutations |
| `issue12-perf-factory-motion-v73` | 7,680 three-call original motion comparisons, including all fine-byte values and guarded fallbacks |
| `issue12-perf-factory-clock-v73` | 384 executed elapsed-time clock cases: wrap, carries, pause and bounded debt/drop accounting |
| `issue12-perf-factory-preparation-v74`, `issue12-perf-factory-rules-v74` | 508 exact original preparations and 1,728 original phase boundaries |
| `issue12-perf-factory-rounds-v73` | 254 explicitly seeded scene transitions, maps/objects/headers and code canaries |
| `issue12-perf-factory-session-v74`, `issue12-perf-factory-state-v74`, `issue12-perf-factory-attract-v74` | Real two-player sessions/deaths, partial-board restoration/HUD boundaries and original cast/autonomous attract |
| Authored tests | 365 synthetic tests pass; original inputs remain outside the test fixtures |

Seeded/component proofs are distinct from naturally completed rounds. Maximum
observed enemy occupancy remains ten planes per scanline; real hardware culling
persists. SAT/VRAM/source-pixel proofs do not establish complete loaded RGB
scanout or physical-hardware acceptance. Those review gates remain open under
#12/#27; they do not justify declaring the whole issue complete. Audio stays silent.

The bounded `FULL_GAME=0` cartridge remains byte-identical to Issue 11:
`9771e72b394f5a3c66018f638318caa5e4e060eed85c2dcc27d5f5328f5efc12`.

## Reproduce

Use fresh ignored output directories and contributor-supplied ROMs/BIOS.

```sh
make build
make run
.venv/bin/python -B scripts/raster_scroll.py build --stage 12 --full-game --hz 60 --output references/build/my-build
ROM=references/build/my-build/raster-scroll.rom
.venv/bin/python -B scripts/full_game_route.py --rom "$ROM" --output references/build/my-route --rounds 8 --avoid-enemies --steering-margin 5 --profile --record-round 6 --radar-trace --require-stable-radar --require-stable-fuel --require-stable-player --maximum-scroll-step 4 --minimum-native-hz 57 --minimum-vertical-update-hz 40 --maximum-p95-loop-ms 39 --maximum-over40-percent 3
.venv/bin/python -B scripts/full_game_evidence.py --rom "$ROM" --capture references/build/my-route --output references/build/my-evidence
.venv/bin/python -B scripts/full_scroll_probe.py --rom "$ROM" --output references/build/my-scroll
.venv/bin/python -B scripts/full_terrain_probe.py --rom "$ROM" --output references/build/my-rows
make test
```

`--fixed-base-clock` is an explicit route diagnostic; keep the HUD enabled.
The controlled renderer-only benchmark remains a separate tool and its old
v13 medians do not describe the current whole-game cadence.

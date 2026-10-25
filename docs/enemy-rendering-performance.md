# Loaded-round performance and player pacing

The current cartridge fixes the player's vertical displacement under enemy
load. Its complete SAT pair is published by the maze IRQ against the actual
R23 latch, together with fuel and radar. The foreground prepares patterns and
attributes but no longer uploads a player Y from a newer camera plan.

Two natural six-round routes pass the native-rate, player/fuel/radar coherence
and physical-camera pacing gates. The primary route sustains **59.89–60.61
native ticks/s**, including a seven-enemy challenge. The original tick is
16.5 ms (60.606 ticks/s). Complete cars, scenery pixels/colors, the full HUD
and real V9958 sprite limits remain enabled.

Qualified ROM SHA-256:
`c51e8aef26e0ab445d713bfeea2187452f21479abc2c44fdc2b3ce5b8ca83bb8`.
`make build` publishes this image at `references/build/newrallyx.rom` and
`latest.rom`; `make run` launches it. The independently rebuilt qualification
bundle is `references/build/issue12-player-pacing-v106/`.

## What the previous checks missed

The v83 fuel correction left the player on a different publication clock from
the camera. A new observer reproduces **335 incorrect player SAT pairs in 4,009
pre-fetch samples** on that ROM. Native logic near 60 ticks/s did not establish
visible smoothness: actual vertical updates measured only **29.67–31.24/s** in
its first two rounds, despite the six-pixel scroll-step limit.

The camera now spends at most two pixels of ordinary vertical debt per physical
refresh, or four beyond eight pixels of debt. This spreads batched movement over
refreshes instead of draining a snapshot and then waiting. Scene initialization
still snaps immediately. The native position and gameplay rules are unchanged;
the existing sixteen-pixel native/presentation guard bounds catch-up. Both
planned and displayed terrain ownership remain protected.

Late foreground loops can use a maze interval which has already opened, and do
not consume a new VBlank at the later split checkpoint. Ordinary terrain work
uses one exact command; an incomplete newly exposed border can use up to eight.
The native tail checks for due work before repeating the terrain edge probe.
Descriptor selection also uses the reference machine's factory turbo, returning
to 3.58 MHz before sprite I/O. No scenery or car quality was reduced.

## Current measured cadence

| Displayed round | Enemies | Native ticks/s | Complete foreground snapshots/s | Visible vertical updates/s |
| --- | --- | --- | --- | --- |
| 1 | 1 | 60.612 | 47.31 | 43.24 |
| 2 | 2 | 60.557 | 45.08 | 44.19 |
| 3, challenge | 7 | 59.891 | 39.20 | 41.79 |
| 4 | 3 | 60.565 | 41.38 | 43.91 |
| 5 | 3 | 60.561 | 38.71 | 42.73 |
| 6 | 4 | 60.134 | 34.63 | 40.90 |

These are three different measurements, not 60 FPS. Vertical cadence counts
actual R23 changes in five adjacent active physical frames containing at least
two monotonic native Y changes. It excludes stops, turns and native stalls;
the separate native-rate denominator retains active stalls. Physical refresh is
50 Hz. Moving enemy snapshots and horizontal camera preparation still follow
the foreground rate. Brief uneven frames remain, including active loops up to
66.7 ms. Twenty-eight ticks were dropped at the bounded debt limit; the lowest
complete five-second native window was 58.87 Hz on the primary route.

The second six-round route uses steering margin seven instead of five and
measures 59.70–60.57 native ticks/s and 40.27–44.19 vertical updates/s. Routes
adapt to timing and enemies, so this is not a fixed-path percentage comparison.
The default-margin attempt lost all lives during round four and is retained as
partial evidence, not six-round completion.

Current qualification, all under ignored `references/build/`:

| Evidence | Result |
| --- | --- |
| `issue12-player-pacing-qualified-m5-v106` | Six natural rounds; native minimum 57 Hz and physical vertical-update minimum 40 Hz gates pass |
| Same route, fixed sprites | Zero errors in 12,316 player, 12,614 fuel, 12,610 footer and 63,092 radar samples |
| Same route, camera | 10,989 adjacent active physical frames; maximum step four pixels; actual displayed terrain ownership checked |
| `issue12-player-pacing-qualified-m7-v106` | Independent six-round route passes the same gates |
| `issue12-player-pacing-latch-v106` | 65,792 adaptive circular-scroll/initial-latch cases; native RAM, VRAM and stack unchanged |
| `issue12-player-pacing-evidence-v106`, `issue12-player-pacing-cars-v106` | 46 independent natural source-pixel/HUD/car snapshots; 13,496 complete-car cases with IRQs |
| `issue12-player-pacing-scenes-v106`, `issue12-player-pacing-clock-v106` | 254 seeded map/object/header transitions; 384 elapsed-clock cases |
| Matching `session`, `state`, `attract` bundles at v106 | Two-player lifecycle, partial-board restoration and attract pass |
| Authored tests | 368 pass; bounded Issue 11 ROM remains byte-identical |

Header reservation maximum is 7.598 ms. `--record-round 2` records eight seconds
of actual scanout for direct inspection; it does not change the guest clock or
write guest state. Full loaded-round RGB/culling readability and physical
hardware remain review gates. The measurements below describe the historical
v75 iteration; v83 separately restored fuel but did not qualify player centering.

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
.venv/bin/python -B scripts/raster_scroll.py build --stage 12 --full-game --output references/build/my-build
ROM=references/build/my-build/raster-scroll.rom
.venv/bin/python -B scripts/full_game_route.py --rom "$ROM" --output references/build/my-route --rounds 6 --avoid-enemies --steering-margin 5 --profile --record-round 2 --radar-trace --require-stable-radar --require-stable-fuel --require-stable-player --maximum-scroll-step 4 --minimum-native-hz 57 --minimum-vertical-update-hz 40
.venv/bin/python -B scripts/full_game_evidence.py --rom "$ROM" --capture references/build/my-route --output references/build/my-evidence
.venv/bin/python -B scripts/full_scroll_probe.py --rom "$ROM" --output references/build/my-scroll
make test
```

`--fixed-base-clock` is an explicit route diagnostic; keep the HUD enabled.
The controlled renderer-only benchmark remains a separate tool and its old
v13 medians do not describe the current whole-game cadence.

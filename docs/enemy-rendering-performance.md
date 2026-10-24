# Loaded-round performance and fixed radar publication

The current cartridge sustains **60.48–60.61 native ticks/s over six naturally
completed rounds** on the reference Panasonic, including a seven-enemy challenge.
The original tick is 16.5 ms (60.606 ticks/s). Complete car
drawings, scenery pixels/colors, the HUD and real V9958 sprite limits remain
enabled. Presentation averages **25.74–35.19 foreground loops/s**; these are
separate measurements and do not establish 60 FPS.

Qualified ROM SHA-256:
`cfe9f0060d2fac4c3b40afe8359e108b556b64bee68eb912964e49c9e26a5f66`.
`make build` publishes this image at `references/build/newrallyx.rom` and
`latest.rom`; `make run` launches it. The independently rebuilt qualification
bundle is `references/build/issue12-fuel-scroll-v83/`.

## Fuel restoration and vertical pacing regression

The previous v75 qualification missed two presentation regressions. Moving radar
publication into its IRQ omitted the three fuel SAT entries; the footer reused
their slots and left the bar absent. The new pre-fetch observer found **7,882
incorrect fuel samples out of 7,882** on that image. Elapsed-time simulation also
accumulated presentation debt and produced vertical steps up to **21 pixels**.
The earlier native-rate and scene-pixel checks did not cover these two properties.

The maze IRQ now restores all three fuel slots against the actual R23 latch on
every refresh. Vertical presentation follows the prepared world by at most six
pixels per physical refresh, with circular wrap and an immediate scene reset.
The computation runs before the header's narrow register-latching window. Radar,
fuel, footer coordinates and raster comparators use the same latched scroll.
Native simulation retains its elapsed-time clock. Terrain safety protects both
planned and latched views; horizontal turns also prepare the corner columns at
the older visible Y before publishing the new X.

Current qualification, all under ignored `references/build/`:

| Evidence | Result |
| --- | --- |
| `issue12-fuel-scroll-qualified-v83` | Six natural rounds at 60.48–60.61 native ticks/s; minimum 57 Hz gate passes |
| Same route, fixed HUD | Zero errors in 14,218 fuel, 14,211 footer and 71,094 radar body/dot samples |
| Same route, camera | 12,884 adjacent active physical frames; maximum vertical step 6 pixels, zero larger steps; actual latched viewport ownership checked |
| `issue12-fuel-scroll-latch-v83` | All 65,536 circular byte transitions and 256 initial latches; native RAM, VRAM and stack unchanged |
| `issue12-fuel-scroll-evidence-v83` | 39 independent scene/HUD/car snapshots |
| `issue12-fuel-scroll-cars-v83` | 13,496 complete-car presentation cases with active IRQs |
| `issue12-fuel-scroll-scenes-v83` | 254 explicitly seeded map/object/header transitions |
| `issue12-fuel-scroll-session-v83`, `issue12-fuel-scroll-state-v83`, `issue12-fuel-scroll-attract-v83` | Two-player sessions, board restoration and attract pass |
| Authored tests | 366 pass; the bounded Issue 11 ROM remains byte-identical |

Header reservation maximum is 7.459 ms. Longer input-driver attempts reached the
second challenge but lost all lives; they are not counted as eight completed
rounds. Timed HUD callbacks exclude scene reloads, including callbacks scheduled
just before loading began. Rendered RGB and physical hardware remain separate
review gates. The measurements below describe the preceding v75 iteration.

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
ROM=references/build/issue12-fuel-scroll-v83/raster-scroll.rom
.venv/bin/python -B scripts/full_game_route.py --rom "$ROM" --output references/build/my-route --rounds 6 --avoid-enemies --steering-margin 5 --profile --radar-trace --require-stable-radar --require-stable-fuel --maximum-scroll-step 6 --minimum-native-hz 57
.venv/bin/python -B scripts/full_game_evidence.py --rom "$ROM" --capture references/build/my-route --output references/build/my-evidence
.venv/bin/python -B scripts/full_scroll_probe.py --rom "$ROM" --output references/build/my-scroll
make test
```

`--fixed-base-clock` is an explicit route diagnostic; keep the HUD enabled.
The controlled renderer-only benchmark remains a separate tool and its old
v13 medians do not describe the current whole-game cadence.

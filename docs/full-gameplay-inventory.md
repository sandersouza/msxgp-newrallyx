# Complete silent gameplay: implementation and qualification

Tracking: [#12](https://github.com/sandersouza/msxgp-newrallyx/issues/12),
[#26](https://github.com/sandersouza/msxgp-newrallyx/issues/26),
[#27](https://github.com/sandersouza/msxgp-newrallyx/issues/27),
[#28](https://github.com/sandersouza/msxgp-newrallyx/issues/28),
[#29](https://github.com/sandersouza/msxgp-newrallyx/issues/29).

This branch integrates the remaining gameplay/session paths into the selected
original-routine adapter. It replaces the bounded first-round endpoint with
original normal/challenge progression. It remains a hardware adapter, rather
than the complete original foreground/IRQ loop. Loaded-scene performance and
rendered scanout require review before closing #12 or asserting full-match fidelity.

## Build and controls

```sh
make build
make run
# Rebuild the preserved bounded Issue 11 reference:
make build FULL_GAME=0
```

The full variant uses stage12, a 2 MiB ASCII16 cartridge, 117 populated banks,
a 48-column terrain cache and the complete HUD. Factory Panasonic turbo is
detected for pure CPU work; VDP access and raster IRQs retain 3,579,545 Hz.
Other machines retain their base clock. Current performance qualification is
in [Issue #12 performance analysis](issue12-performance-analysis.md). The user
approved 30 FPS presentation, near-60 Hz game clocks and MSX-specific enemy
behavior. Complete packets and actual camera cadence are measured separately.
It requires the existing 128 KB main RAM mapper / 128 KB VRAM baseline.
The former issue estimate's 64 KB RAM assumption was incorrect; this is not
a newly introduced requirement. Validation uses openMSX 21.0, a session-local
FS-A1WSX configuration and real VDP command/sprite limits at 60 Hz. Bounded
stages retain 50 Hz; short native-rate dips remain documented in the performance evidence.

| Input | Behavior |
| --- | --- |
| 5 | Add one credit, saturating at 255 |
| 1 | Start one player for one credit |
| 2 | Start alternating two-player play for two credits |
| Arrows / joystick1 | Four-way steering for the selected player |
| Space / Ctrl / triggerA | Original smoke action and fuel charge |
| P | Development pause |
| Home | Development reset |

The original acquired DIP byte is `$c3`: one credit per game, three initial
cars / easy difficulty and 20,000/80,000 bonus thresholds. Cabinet input is upright.
The adapter retains that acquired rule/parameter seed; no runtime DIP/service
menu or cocktail control rotation is offered. Both turns use the same controls.

Direct diagnostic builds retain their earlier defaults. To build the complete
variant explicitly, use:

```sh
.venv/bin/python -B scripts/raster_scroll.py build --stage 12 --full-game --hz 60 --output references/build/my-full-game
```

Outputs must be fresh and ignored. Supply original ROMs, graphics, reference
scenes and compatible BIOS locally as described in README/setup. No tool obtains
game ROMs or BIOS. Builds automatically acquire the original cast reference from
local ROMs into an immutable ignored bundle.

## State and hardware ownership

The original counter starts at 2 for displayed round 1. Original challenge
initialization occurs when the counter is divisible by four: displayed rounds
3, 7, 11 and so on. Source preparation `$08bf..$08d4` increments the round,
dispatches parameters, places rocks/flags and advances the original PRNG.
The adapter returns before arcade hardware writes, then rebuilds map/object
ownership, renderer banks, HUD and native player/enemy state.

All four original terrain pages are linked. A packed 896-byte owner map keeps
the original 1,792 cell identifiers; flags and rocks overlay placement-independent
terrain. Collected flags remain absent across scrolling and life/turn reloads.
The PRNG advances on every native tick, alongside the original phase clock.
Challenge cars activate through the source parameter/countdown rules. A failed
challenge advances to the next round as at source `$191c`; an ordinary death
restores the same partially collected board.

The selected player uses canonical P1 addresses. A 120-byte shadow stores the
inactive score packet, lives, round, bonus bits, collected count, object tables,
active flags and pending-new-board state. A turn swap restores that player's
native parameters **before** selecting its renderer banks. Fuel and current-life
point ordinal reset; score, collected flags and round survive. A first turn
prepares a fresh board. Shared game over waits until neither player has cars.

Seven original enemy descriptors remain active according to native population.
Their full two-plane masks, original colors, facings, clipping, colliding-car
identity and radar coordinates remain represented. MSX viewport/world contact
replace arcade OAM registration and the former five-pointer contact list.
One shared renderer accesses seven prepared/SAT/cache records directly through
IX. Visible complete sprite pairs retain original actor order, followed by one
end marker; hiding an earlier actor cannot terminate
the sprite table before a later visible actor. Conservative offscreen rejection
skips presentation work while preserving exact world/radar positions.

MSX pursuit decides once at a new cell centre using reciprocal exits. Enemies
coast between centres and use the original fractional integrator every other
native tick with doubled distance. Player speed is capped at two pixels per
native tick, enemies at 1.875; lower source speeds and challenge activation
remain effective. Original phase, fuel and startup/spin clocks continue near
60 Hz. Twelve shared complete-mask slots bound VBlank replacements to two.
The executed MSX contracts replace original-AI equivalence as the relevant
enemy proof; historical original-AI comparisons apply only to older cartridges.

The score/high-score header displays the lowest seven native digits using original
8x8 glyphs, aligned to the maze viewport. It includes the selected player and two
round digits, replaced by an authored 16x8 infinity sign above 99. The title also
shows seven high-score digits. Credits display one digit, capped at nine; the
native counter still supports 255. Spare-car presentation caps at nine
without changing native lives. Fuel retains original units and publication in
the maze IRQ against the actual scroll latch.
Collected flags now prioritize their radar-cell publication in safe video
intervals. Fresh smoke jobs precede retired-row repairs without increasing the
stream budget. See [effect publication evidence](issue12-effects-publication.md)
for native-to-display lag checks and the loaded-scene timing comparison.
Enemy markers crossing or straddling cells now prioritize erasing their
previous footprint. [Radar motion evidence](issue12-radar-motion.md) checks
actor identity across cells and rejects accumulated or unowned pattern ink.
The scenery palette reuses a spare third black entry for the later orange;
both dependent car-plane blacks and every other existing entry remain intact.
Every required source tile/cast color must map through the established RGB333
conversion or the build fails. No new color merge or graphic reduction is used.

The original complete cast appears at 1:1 in a 224x212 region centered in the
256x212 display; its drawings and NAMCO line remain intact. Custom compact
credit/instruction fields occupy free rows. After 900 no-credit UI refreshes, the
adapter runs original guide steering in attract mode; completion, death, 900
presentation iterations or credit returns to the title. Human start always
initializes a fresh game.
The acquired original full-game mode is 2; the selected human adapter uses 1,
while attract uses 0. These are explicit different state owners.

Original sound shadows/rule requests remain local state, without an audio
backend. The original fuel-bonus sound-busy wait is replaced by the existing
bounded silent converter. Arcade rendering, intro/READY presentation waits and
the long source attract scheduler are replaced by the MSX scene/session adapter.
Audio remains silent; this does not establish original elapsed wall-clock timing.

## Original delivery evidence and practical limits

This section preserves historical original-delivery evidence. Current packet,
enemy, scanout and cadence qualification is in the performance analysis above.

All generated evidence below is local and ignored under `references/build/`.
The original delivery candidate, retained as the performance baseline, has SHA-256:

`b180937fac5ebf0d66f8d98c129e5fbeb26d2e98bd2e7bc463f3bb3dac1bf983`

It is retained in `default-de4ca124d2384584b1cb1051490619c1/`. The current
`make build` candidate and its separate performance qualification are documented
in [enemy rendering performance](enemy-rendering-performance.md).

| Evidence | Result and boundary |
| --- | --- |
| `issue12-round-inventory-v13` | Real original start plus 254 seeded preparations; four maps, 63 challenge entries, up to seven enemies/twelve rocks, 13 scenery RGB colors |
| `issue12-final-round-proof-v3` | 508 source/native preparations, two PRNG seeds; all 4,096 state bytes after declared pointer/page relocation, all object lookups, stack/canaries and unchanged VRAM |
| `issue12-final-phase-proof-v3` | 1,728 exact source/native phase/fuel/activation boundary cases |
| `issue12-final-ai-proof-v3` | 7,680 three-call original/native AI cases, guards/key changes, four maps; stack/VRAM/player shadow/IRQ unchanged |
| `issue12-final-enemy-proof-v3` | 13,496 seven-car presentation cases plus the hidden/hidden/visible SAT and independent radar-mask regressions; source masks, OR colors, positions, facings, clipping and cache reuse |
| `issue12-final-route-v3` | Eight naturally completed rounds using real credit/start/steering/smoke inputs; no guest-state writes; 20,752 refreshes |
| `issue12-final-evidence-v3` | 85 independent natural cache/smoke/HUD snapshots, 84 complete enemy images, SAT traversal/Y/X and source masks checked |
| `issue12-final-scenes-v4` | 254 explicitly seeded completion endpoints; dynamic original geometry/object pixels and full headers across every acquired round |
| `issue12-original-session-v3` | Unmodified original input ports: reject zero/one-credit 2P start, accept two credits, six natural turns/deaths and no remaining lives |
| `issue12-final-session-v4` | Real MSX credit/start, six alternating natural deaths and shared game over; selected player/lives/round agree with the original turn boundaries |
| `issue12-final-state-v3` | Explicit partial-board fixtures on different maps; both restores, challenge failure, score/lives retention and 14 HUD boundaries including eight digits and displayed round 255 |
| `issue12-final-attract-v3` | Real title/demo/title, cast pixels, credit interruption and fresh human start, without guest-state writes |
| Authored tests | 354 synthetic tests, independent of original game data |

Natural-route header reservations stay within the measured bound: 23,115
reservations, maximum 6.401 ms. The route uses an external BFS input driver;
reading the current board/enemy positions to choose keys is not a game-state
patch. Seeded transitions and component fixtures are expressly separate from
natural completion and do not prove a human played 254 consecutive rounds.

The eight-round route held simulation on **5,390 / 20,752 refreshes (25.97%)**,
with at most five consecutive holds. Holds freeze all native clocks together
while the cache drains, avoiding stale scenery. This is a noticeable loaded-scene
slowdown, beyond a claim of nearly exact arcade speed. Four-round routes have
different loads; do not compare their percentages as a fixed benchmark.
The implementation is ready for review, but acceptance of this performance
concession remains open. It is not silently treated as a small delay.

Observed enemy occupancy reaches ten planes on one scanline, before adding
player/HUD candidates. Real eight-sprite scanline limits remain enabled, so
lower-priority cars/parts can be culled. There is no new simplification or
priority-flicker scheme. Pixel/table proofs preserve complete drawings; they
do not imply every candidate survives actual scanout.

The overnight environment could execute the headless renderer, while the SDL
frontend stopped advancing with the desktop asleep. Consequently the final
loaded build has **VRAM/SAT/source-pixel proofs, not new RGB scanout or physical
hardware qualification**. Earlier first-round RGB evidence remains scoped to
its own cartridge. Actual visual review of loaded motion/culling is outstanding.

The acquired source range is displayed rounds 1..254 (internal 2..255).
Displayed 255 is tested only as HUD presentation. Counter wrap into internal
zero reaches source parameter bytes outside the normal bounded table and is
not qualified or replaced with invented progression rules.

Assembly asserts enforce bank limits. `full-memory.json` checks additional RAM
regions for overlap, keeps actor hot code below `$c700`, preserves input
`$e3f0` and the IM2 jump, and retains 204 bytes between cold code and the
`$f380` stack top. This is a static workspace bound, not an exhaustive dynamic
stack-depth proof. Native component proofs also check their stack/canaries.

The bounded build remains byte-identical to approved Issue 11 v260:
`9771e72b394f5a3c66018f638318caa5e4e060eed85c2dcc27d5f5328f5efc12`.

## Reproduce qualification

Use fresh ignored outputs. Replace `$ROM` with the complete sealed cartridge path.

```sh
.venv/bin/python -B scripts/gameplay_inventory.py --last-round 254 --output references/build/my-inventory
.venv/bin/python -B scripts/round_preparation.py --last-round 254 --rom "$ROM" --reference references/build/my-inventory --output references/build/my-preparation-proof
.venv/bin/python -B scripts/full_rules_probe.py --rom "$ROM" --reference references/build/my-inventory --output references/build/my-phase-proof
.venv/bin/python -B scripts/full_msx_enemy_probe.py --rom "$ROM" --output references/build/my-msx-enemy-proof
.venv/bin/python -B scripts/full_enemy_probe.py --rom "$ROM" --output references/build/my-car-proof
.venv/bin/python -B scripts/full_game_route.py --rom "$ROM" --rounds 8 --avoid-enemies --output references/build/my-route
.venv/bin/python -B scripts/full_game_evidence.py --rom "$ROM" --capture references/build/my-route --output references/build/my-route-pixels
.venv/bin/python -B scripts/full_game_probe.py --rom "$ROM" --headless --rounds 254 --output references/build/my-scenes
.venv/bin/python -B scripts/session_inventory.py --output references/build/my-original-session
.venv/bin/python -B scripts/full_session_probe.py --rom "$ROM" --reference references/build/my-original-session --output references/build/my-two-player
.venv/bin/python -B scripts/full_state_probe.py --rom "$ROM" --reference references/build/my-inventory --output references/build/my-player-state
.venv/bin/python -B scripts/full_attract_probe.py --rom "$ROM" --output references/build/my-attract
make test
git diff --check
```

The phase/state probes default to the pinned original inventory
`references/build/issue12-round-inventory-v13`; pass `--reference` to use
another matching inventory. The session probe defaults to
`references/build/issue12-original-session-v3`; its `--reference` selects an
original session acquisition. Original comparisons pin MAME 0.289 and verify
source/manifests. Sealed outputs must not be modified/resealed to hide failures.

Only authored code, tools, documentation and synthetic fixtures are delivered.
ROMs, BIOS, extracted graphics, original state packets and generated cartridges
remain ignored. Source hashes and sealed inputs must remain unchanged.

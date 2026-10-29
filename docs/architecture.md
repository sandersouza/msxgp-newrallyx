# Current port architecture

This describes the tree stabilized after PR #33 and the original-wordmark
restoration in `1695c5a`. It is an ownership map, not a new module API. Include
extraction and reusable zero-overhead APIs belong to [issue #32](https://github.com/sandersouza/msxgp-newrallyx/issues/32).
See [maintenance](maintenance.md) for the file inventory, baseline hashes and
verification scope. The remaining visual/audio acceptance stays with issue #13.

## Build ownership

| Layer | Authored owners | Contract |
| --- | --- | --- |
| Public selection | `Makefile`, `experiments/fixed-hud/targets.mk` | Default SCREEN 4; `LEGACY=1`/`legacy=1` selects SCREEN 5; test mode belongs to SCREEN 4. |
| Optimized cartridge | `experiments/fixed-hud/build.py`, `prepare.py`, `game_build.py`, `game_core.py`, `session_build.py` | Prepare resources, transform selected source adapters in an ignored assembly directory, assemble and export ASCII16. |
| Pinned shared session/UI source | `experiments/fixed-hud/build_profiles.py` | Verify/export local Git revision `6d562a791b0cc242119a31dd686ff8e93eb94fe0`; link contributor inputs locally and build a separate reference. |
| Maintained legacy cartridge | `scripts/project.py`, `scripts/msx/raster_scroll.py`, `src/raster-scroll.asm` | Build the current `src/` tree in a fresh sealed directory; publish `references/build/newrallyx.rom` only on success. |
| Launch and reference validation | `scripts/msx/emulator.py`, `scripts/scenes/`, `scripts/graphics/` | Verify manifests/inputs, use isolated openMSX state and contributor BIOS; never download game data. |

The optimized build is not simply `src/` assembled in SCREEN 4. It combines
current shared helpers, a verified pinned session source view, generated adapters
and authored `game-*.inc`/`session-*.inc` files. Both trees are required. In
particular, `game_core.py` reads current `src/` motion/enemy/helper sources, while
`session_build.py` obtains pinned session resources through `reference()`.
Changing only `AUDIO_REFERENCE_REVISION` changes the independent comparison;
the integration pin also lives in `session_build.py`. Update both deliberately,
with adapter and gameplay validation, when changing that contract.

`build_profiles.py` verifies cached authored exports against `git archive` and
rejects local modifications. Its build metadata identifies a manifest-verified
bundle; selection does not depend on the newest directory. Do not remove the
pinned commit just because its former branch was deleted. Local Git history is
a build dependency. Contributor inputs remain under ignored `references/`.

## Native rules and hardware adapters

The source generators retain selected original Z80 routines and relocated game
state from contributor ROMs. Host adapters supply MSX input, collision/navigation
data, rendering and PSG publication. The complete build adds native round/map
selection, difficulty and population progression, challenge rounds, smoke,
scores, fuel conversion, death/restart, alternating player turns and attract mode.
This is adapted original logic; it does not execute the arcade hardware unchanged.

The optimized foreground is based on `lab.asm`, transformed by
`game_build.renderer_source()` and `session_build.renderer_source()`. The resulting
assembly directory and symbol tables are generated outputs, not independent
authored sources. Edit the owner or generator, then rebuild; edits to a generated
include can otherwise disappear silently on the next build.

`game-core.inc` owns the shared gameplay frame boundary. `game-main.inc` collects
world/object changes for rendering. `session-resident.inc` owns mapper-safe
session entry points; `session-cold.inc` prepares rounds outside active rendering;
`session-input.inc` publishes four-way keyboard/joystick input and the safe corner
fallback. `src/full-native-motion.inc` and `src/full-msx-enemies.inc` are shared
movement/enemy sources. Graphics publication consumes a coherent prepared state,
including both camera axes and complete car drawings.

## Optimized display and scheduling

The accepted SCREEN 4 layout has a 200-pixel scenery region and a 56-pixel side
HUD in a 256x212 display, retaining the established masks and color codec.
World coordinates and source art dimensions remain unchanged. The earlier
248x201 viewport belongs to the SCREEN 5 path.

The scrolling ring uses generated pattern/color data and separately prepared
name tables. `game-ring.inc`, `game-phase-cache.inc`, `game-name-stream.inc`,
`game-boundary-fast.inc` and `game-packet-fast.inc` handle ring/phase changes and
publication. R23 changes display addressing; it does not relocate pattern/color
tables. The generator and boundary atlases compensate explicitly. A hardware
register change alone cannot replace that work.

`game-hud.inc` and the selected `hud/` include prepare value-dependent patterns,
SAT data and dirty state. The default compact HUD uses six displayed score
digits, the compact ROUND/FUEL style and the established larger fuel/radar
panels. `HUD_VARIANT=classic` retains the preceding styling in a separate bundle.
The [HUD contract](../experiments/fixed-hud/hud/README.md) specifies initialization,
clobbers, dirty preparation, publication and exact resource ranges.

Radar actor updates use `game-radar-fast.inc`; session flag/name/color hooks and
the S-blink caches are prepared separately. `game-dirty.inc` and
`game-smoke-cache.inc` combine changed terrain, flags, smoke and effect overlays.
`game-sprites.inc`, `game-sprite-mask-fast.inc` and the session clipping adapter
prepare and publish complete car patterns/attributes. The real V9958 limits
remain enabled: at most 32 sprites in the table and eight per scanline. Population
overlap may cause hardware culling; a passing synthetic clip matrix does not
establish complete-game perceptual acceptance.

The refresh clock and presented-frame rate are different quantities. Active
preparation, synchronization waits and commit costs have separate profiler rows.
Keep input/native timing coherent across a delayed presentation; do not conceal
recurrent overload in a flag-event pause. See the [cycle procedure](maintenance.md#cycle-ledgers-and-workbooks).

## Memory, banking and interrupts

These are ownership landmarks, not a complete allocator specification. Exact
bank numbers, range ends and optional-module sizes come from each generated
`session-build.json`, `game-resources.json`, `config.inc` and `assembly/lab.sym`.

| Resource | Owner and constraint |
| --- | --- |
| ASCII16 ROM | Resident code starts at 4000; worker/resource banks are selected through 7000. `session_build.py` checks 16 KiB page capacity and bank range. Helpers must restore the mapping required by their caller/IRQ. |
| Page 0 RAM mapper | Session cold code, maps and flag/radar caches use private segments allocated by `GameSession_ColdBoot`. Resident mapping helpers restore the foreground segment before returning. Requires at least 128 KiB mapper RAM. |
| C000 state | Renderer/clock/ring state originates in `lab.asm`; gameplay/session state is declared in `game-core.inc`, `game-main.inc` and `session-resident.inc`. Generated transformations can adjust layout; use the final symbols. |
| E000 native state | Relocated original seed/game state; boot and round preparation restore it before native execution. |
| D300 startup scratch | Hardware-check descriptors and transient bitmap state. `GameSession_Boot` clears D300..F2FF before restoring native/audio state. |
| Stack and IM2 | Boot uses SP=F380. Keep the generated IM2 vector/trampoline and live stack clear of cold workers and bitmap scratch. |
| HUD RAM/VRAM | Fixed preparation buffers, HUD patterns/colors and SAT reservations are enumerated in the HUD contract. World sprites follow the HUD slots. |
| SCREEN 4 VRAM | Ring name/pattern/color sets and sprite tables are rebuilt coherently when returning from SCREEN 5 UI. Requires 128 KiB VRAM; use generated packet/layout reports rather than assuming free VRAM. |

IRQ code must preserve live foreground registers and bank/mapper assumptions.
Active rendering IRQs and cold UI key scanning have different owners; the
11-row startup skip scanner is not called on active-game IRQs. VDP transactions
and register snapshots retain their required atomic sections. Review the final
generated IRQ and symbols whenever changing source transformations.

## Audio, menus and startup

`game-audio.inc` and the session audio adapters reuse compiled original score
parts with PSG music/effect adaptation. `src/full-audio*.inc` and
`scripts/msx/audio*.py` remain shared/legacy dependencies. Deferred publication
keeps audio work separate from the car/camera commit. Start/completion and
driving use different channel allocation; emulated waveform/event contracts do
not replace human timbre and transition acceptance.

Menus/cast/turn transitions use SCREEN 5 outside active SCREEN 4 play.
`session-ui.inc` links pinned UI data with current challenge/title/turn adapters.
`session-startup-options.inc` selects the optional hardware-check replay;
`session-ui-options.inc` selects the optional MSX logo. `HARDWARE_CHECK=0` and
`MSX_LOGO=0` create separate outputs. Omitted presentation modules have no
active-frame dispatch cost; padding can keep total cartridge size unchanged.

The current wordmark is the original 56x8 arcade tile block at (100,200), with
four blank rows below it. The contributor-supplied MSX logo is a separate optional
source. [TITLE.md](../experiments/fixed-hud/TITLE.md) and
[FULL-SESSION.md](../experiments/fixed-hud/FULL-SESSION.md) describe the exact pixel,
skip/input, startup and cleanup contracts. Older 162x10 artwork and corner-stall
reports are historical and must remain bound to their own ROMs.

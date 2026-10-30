# Issue #12: parked contact, score spacing and debug round advance

Current/default ROM SHA-256:
`e03679715eeeafd4c76c53f7541413ca6acc8116cc1f4d08c3ef937e4ea31448`.

## Changes and reproduction

The report concerns parked cars in normal rounds. Challenge contact already
works and keeps its established inclusive ten-pixel bound. A direct central
approach in normal round one also collides on the preceding ROM before the
enemy moves; this follow-up does not claim an unconditional missing collision
handler. The reproducible gap is visible body overlap outside the ten-pixel
rectangle: the original straight car masks still share five opaque pixels at
an axis separation of fourteen pixels.

Normal startup descriptors (`state >= $89`, internal round not divisible by
four) now use an inclusive fourteen-pixel rectangle on each axis. Active/stunned
actors and challenge retain ten. This is an axis-aligned gameplay bound, not
per-pixel collision. The coarse prefilter accepts differences of two cells:
opposite fine coordinates in -23..23 can place touching cars across that seam.
All seven actors remain checked independently of visibility and AI activity.
The extended executed contact contract fails against the preceding ROM and
passes against the current cartridge.

The seven visible score digits begin at X=32 after `HI:` and X=136 after
`1UP:`/`2UP:`. There is no blank character between colon and number. The writer
still skips the hidden eighth source digit; labels, round, viewport and native
counters retain their existing behavior.

**F5** immediately invokes the existing original next-round preparation once
per press. It resumes pause, preserves score, high score, lives, credits,
selected player and the inactive board, and awards no completion/fuel bonus.
It is ignored on title/demo/game-over and during a death/life transition.
The held-key byte survives scene reloads; UI polling prevents a held title key
from leaking into a new game. Ordinary gameplay polls the key in resident code
and maps the session bank only for a new press.

## Qualification

Validation uses openMSX 21.0, Panasonic FS-A1WSX, 128 KB main mapper/VRAM,
factory CPU mode, real VDP timing and sprite limits, original graphics and HUD.

- 392 authored tests pass. Executed Z80 contracts cover 33,327 active contact
  cases, 11,340 startup/challenge cases and 4,211 steering/smoke/speed/motion cases.
  Stack, protected native RAM and VRAM remain unchanged by isolated adapters.
- Real credit/start/F5/P matrix inputs execute four advances, including challenge
  entry/exit and paused advancement. Held keys do not repeat; a held title F5
  does not advance a new game. Packet/state preservation and complete header
  pixels are checked at each next-round return, without guest-state writes.
- Fourteen HUD boundary cases, seven credit limits, partial-board restoration,
  challenge failure, two-player sessions and attract pass on this ROM.
- Two natural rounds complete with 29.89..29.96 FPS, 0..0.23% missed slots.
  The controlled six-enemy round-six setup completes at 29.15 FPS / 2.78%
  missed slots; native restart restores four actors. The original seven-car
  challenge setup completes at 29.89 FPS / 0.23%. Maximum packet gaps remain
  below 67 ms. The existing 2.5% ordinary / 3.5% loaded limits are retained.
- Radar enemy-pattern checks find zero duplicate or unowned-ink samples in
  the natural and six-enemy routes. Flag/smoke publication and fixed
  radar/fuel/player checks pass, with 17 independent cache/HUD/car snapshots.
  Actual round-two scanout is recorded and its captured image inspected.
- The independent default rebuild matches the qualified ROM. The bounded
  Issue 11 image remains byte-identical to its approved reference.

Evidence is local and ignored under `references/build/issue12-parked-*-v229`
and `issue12-debug-controls-v229`. Natural keyboard routes and explicit
component/population fixtures remain distinct. These checks do not requalify
the earlier eight-round matrix or physical hardware; occasional camera waits
and real scanline culling remain review items.

```sh
gnumake build
ROM=references/build/latest.rom
.venv/bin/python -B scripts/full_debug_probe.py --rom "$ROM" --output references/build/my-debug-key
.venv/bin/python -B scripts/full_msx_enemy_probe.py --rom "$ROM" --output references/build/my-parked-contact
.venv/bin/python -B scripts/full_state_probe.py --rom "$ROM" --output references/build/my-compact-hud
.venv/bin/python -B src/toolchain/legacy/full_game_route.py --rom "$ROM" --output references/build/my-parked-route --rounds 2 --steering-margin 8 --avoid-enemies --effects-trace --radar-trace --require-stable-radar --require-stable-fuel --require-stable-player --maximum-scroll-step 8 --maximum-packet-miss-percent 2.5 --maximum-packet-gap-ms 67
```

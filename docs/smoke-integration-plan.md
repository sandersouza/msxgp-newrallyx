# Issue11: selected original smoke integration

## Current validated integration

Stage12 includes smoke with the full original-color maze, complete car sprites
and normal HUD/radar. See [session delivery and measurements](completion-integration-plan.md).
The preserved Stage10 `11-r10-coherent-v207` rock fixture passes repeated firing,
death/restart/Home:1,812 complete cache states,59 full RGB images and1,984 exact
source calls. Native clocks hold briefly near cache exhaustion (41 observed
refreshes,2.26%, maximum3 consecutively), preserving scenery instead of exposing
unfinished tiles. This explicit timing concession replaces the failed quality
and scheduler experiments. No extra smoke sprites, color reduction or active
flicker experiment is required. Original source components and canaries remain
strict; exact-cadence diagnostics remain failing. Older checkpoint records below
are historical rather than the current latest selection.

Continue from the accepted one-enemy first-round reference. The two-enemy
checkpoint remains explicitly selectable; population stress does not
change the original first-round count. HUD stays enabled, complete original
cars and normal sprite radar remain, and sprite-line culling is allowed.

1. Link and independently execute original activation `$0f64`, tile helpers
   `$100f/$101e/$1031`, stun detection in `$0cd6`, and recovery `$0185`.
   **Passed:** 1,254 original/MSX comparisons: 598 activation/resource/geometry,
   648 recovery and eight AI cases. Each compares both complete 1,024-byte
   code/attribute rings as well as fuel, request and enemy state. Maximum
   component elapsed cost is 6,699 cycles, including initialization in AI
   vectors. This does not claim natural smoke timing or bitmap publication.
2. Adapt the original code/attribute rings to `$e400/$ec00`. Populate placement
   permission on demand from original terrain, respecting collected flags and
   existing smoke. Clear outgoing ring rows/columns as the viewport moves;
   retain original world coordinates and eight-pixel tile alignment.
3. Present the original nine 8x8 tiles in the existing bitmap command atlas.
   Queue affected 3x3 regions for creation and recovery, charge work to the
   existing stream budget, and preserve terrain when the cache reloads.
   Allocate no smoke sprites. Record actual published cells separately for
   independent complete-cache/RGB checks. Keep the IRQ stub at `$d2d2` intact.
4. Connect **Ctrl** to the original active-low smoke input, retaining Space
   pause and Home reset. The original debounce, three-placement request and
   whole-fuel deductions remain source code. Recovery clears the consumed
   cloud after the original stun counter; do not invent a universal smoke TTL.
5. Exercise real keyboard activation, blocked placement, consumption, enemy
   stun/recovery, pause, camera/cache eviction, death/restart and Home, then
   measure moving performance and publish the next test checkpoint. Keep
   native component equality separate from renderer timing acceptance.

Component build: `references/build/issue11-smoke-component-v155`, SHA-256
`19a858e6394ce0fdde0cc0294bd5c350f03dbece981d7bd1329b3bf55a8c2c5e`.
Its metadata explicitly says smoke is not yet active from the keyboard.
Proof: `references/build/issue11-smoke-proof-v157/report.json`.
Unchanged gameplay regression:
`references/build/issue11-smoke-component-route-v158/report.json` passes
1,138 complete-cache states, 28 full RGB images, source contact/death/restart
and the unchanged timing gate. These are baseline checks without smoke input.

For the retained camera ABI, at the end of a native tick:
`worldX - camera04d - physicalX == 28 (mod256)` and
`worldY + camera04f + physicalY + 8 == 80 (mod256)`.
Thus code-ring column/row correspond to `(worldTileX-3,worldTileY-10) mod32`.
Placement uses the current native world descriptors after `$0069`: it advances
both the world and fine camera offsets. The pre-movement origin is retained
only for retiring outgoing ring rows and columns. Smoke follows the source
order after movement and before the new steering/visibility dispatch.

## Delivered keyboard checkpoint

`11-r10-smoke-v171` is the preserved pre-completion smoke checkpoint. Run
`make run LATEST=1`, or rebuild with `make build STAGE=10`. Arrows steer,
**Ctrl** releases smoke, Space pauses and Home resets. HUD is enabled, original
complete car planes and normal sprite radar remain, and smoke adds zero SAT
entries (20 used, 12 free). The cartridge hash is
`1a95221238b3ddd501e82d74d6572f696d42b3e463fc45d8d6eb010a79d4c829`.

The ROM is byte-identical to measured v170. Its keyboard-only route passes
1,452 complete visible-cache states, 47 full RGB images and exact independent
MAME replay of all 1,712 observed smoke calls. That includes three placements,
32 independently checked cardinal placement/permission attempts, 136 native
stun ticks, recovery, 40 paused refreshes, reversal/cache eviction and Home.
Publication row counts match every captured cache state. No guest game-state
writes are used by this route.

Components separately pass 1,254 original activation/recovery/AI cases,
490 original flag/cloud overlap cases, 40 publication-row canaries and 480
queue wrap/dedup/full cases. Repeated creation/removal of the same cloud
coalesces to its latest 3x3 repaint, preventing obsolete FIFO work from
accumulating. Full queues of distinct regions report an explicit overflow;
they do not silently discard work. The unit suite passes 328 tests.

Main-start intervals: median 19.936612 ms, p95 20.560993 ms, maximum
28.146873 ms. There are 156 intervals outside the unchanged 0.6 ms tolerance;
`performance_accepted` remains false. These are main-loop cadence deviations,
not 156 lost display refreshes: the three measured raster publication phases
have zero missed refreshes (maximum 20.403990 ms). Worst repeated firing,
death/restart with active smoke and combined population stress still require
their own focused runs. This delivers playable smoke, not completion of #11.

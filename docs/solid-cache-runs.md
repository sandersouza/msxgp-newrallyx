# Exact solid cache runs for stage 09

Two enemies exceed the moving cache budget in both full-color and single-plane
60 Hz candidates. The presentation components pass 3,856 cases, but the long
control first finds stale terrain around frame 221. At frame 220 the selected
native enemy adapter grows from 4,133 to 7,054 elapsed cycles and presentation
preparation from 1,793 to 3,558. Individual 8x8 terrain commands commonly cost
985 CPU cycles. The row queue consequently falls behind the moving viewport.
Color reduction alone does not fix this. Interleaving radar publication with
cache copies also fails (frame 218); that experiment has been removed. A 50 Hz
comparison fails later at frame 295 and is not an accepted checkpoint.

The implementation combines adjacent, already-solid terrain tiles into one
HMMV rectangle. Host preprocessing tags only exact single-color 8x8 tiles;
textured terrain and flag-owned tiles retain exact atlas copies. Runtime
grouping stops at a changed color, texture, flag owner, queue wrap, world edge
or physical 256-pixel page boundary. Each command covers at most four tiles,
bounding the final indivisible GPU operation. Death presentation disables grouping.
Every pixel, world coordinate and asset dimension remains unchanged. No sprites,
ROM banks or full-screen redraw are added.

The accepted HUD-off continuation is `11-r09-two-no-hud-v80`. It passes all
4,608 executed command/canary cases, the natural 493-state route / nineteen RGB,
the 1,600-state control / 38 RGB and the unchanged raster timing gate. Its cache
guard closes at line 196. Removing unused HUD entries leaves six SAT slots;
enemy attributes precede player uploads to preserve top-edge scanout. Earlier
`Stage_HideHUD` masked IRQs across its full upload, delaying a header match past
line six and causing a 32.6 ms wait. Its stage 09 upload is now interruptible;
the compact HUD-off layout eliminates that transaction entirely.

Two-enemy HUD-on acceptance remains open. Radar composition under queue pressure
must preserve both terrain deadlines and the sixteen-refresh marker limit.
A diagnostic with one logic step per display frame also failed the cache gate;
that experiment was removed. Delivered references retain the original 16.5 ms
tick. Stage 08 HUD-on/off still reproduce their accepted ROM hashes.

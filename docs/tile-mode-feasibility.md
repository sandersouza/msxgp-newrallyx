# SCREEN 4 scenery feasibility experiment

Two-enemy SCREEN 5 candidates still miss complete moving cache/RGB deadlines.
The accepted two-enemy HUD-off and one-enemy HUD-on cartridges remain immutable;
`LATEST` is not changed by this experiment.

The original first-stage bitmap contains 37 distinct 8x8 tiles. Of 141,984 tile
scanlines, 114,927 use one color, 22,121 use two, 4,922 use three and fourteen
use four. Keeping the two most frequent colors per tile scanline changes at
least 6,410 of 1,135,872 world pixels (0.564324%). This measurement includes the
explicit two-rock fixture. It is a whole-world count, not a claim about every
visible scene or gameplay speed.

The user authorizes reducing scenery colors when needed for playable speed.
This experiment retains 8x8 tiles, original object/asset dimensions, world
coordinates, collision data, native movement and the full 248x201 maze viewport.
The selected two-color row replaces minority colors with the nearest retained
palette color. Player/HUD sprite graphics and the black score header stay in
their original color formats. No additional sprites are allocated.

First checkpoint: the fast stage00/01 driving fixture, with no arcade
foreground, enemy AI or additional game systems. Compare full RGB against an
independent decoder of the declared color adaptation, complete visible VRAM
cache/right edge, original keyboard movement and unchanged raster timing gates.
Measure actual name-table writes and compare the old bitmap renderer before
porting any gameplay system.

VRAM experiment layout: four repeated 2 KiB pattern groups at 0x0000..0x1fff,
four color groups at 0x4000..0x5fff, left/right 32x32 name tables at 0x2000 and
0xa000, existing SCREEN 5 score header at 0x10000 and existing sprite tables
near 0x1f400. A scenery update writes one name-table byte rather than copying
an 8x8 bitmap. All four pattern/color groups are initialized for 212-line
output and vertical wrap. The header raster switches SCREEN 5 to SCREEN 4 for
the maze; sprite mode 2 remains available.

Primary hardware references: Yamaha's [V9938 technical data book, GRAPHIC 2/3
and table registers](https://device.report/m/9a2cd04c658e6be4100ce95edce667cb1f5253529704e563942476793b662f62)
and [V9958 technical data book, horizontal scrolling and SP2/PNT address
selection](https://map.grauw.nl/resources/video/yamaha_v9958_ocr.pdf).

Checkpoint `11-screen4-rocks-50-v1` passes 1,600 original movement/cache states
and 26 complete RGB images at 50 Hz, with zero GPU commands during steady
frames. Its color conversion changes 6,410 of 1,135,872 scenery pixels
(0.5643%), retaining original dimensions and object positions. Run with
`make run CHECKPOINT=11-screen4-rocks-50-v1`. This is a stage01 feasibility
prototype, not acceptance of stage09 or completion of issue11. Further gameplay
integration is pending; the user's independent player radar request took
priority after this renderer fixture passed.

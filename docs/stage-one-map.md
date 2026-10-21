# Original first-stage map

The default keyboard ROM contains the complete original first-stage static map,
not a repeated screen capture. The original layout is 32x56 cells; every cell
contains 3x3 original 8x8 tiles. The maze therefore occupies **768x1344 pixels**,
without scaling, tile replacement or rearrangement. A 24-pixel flower border
surrounds it, producing an **816x1392** navigable image. The border uses the
arcade's own out-of-map flower selector, not a newly drawn asset.

## Build and inspect

```sh
make build
make run
```

Use arrows, including diagonals, for one-pixel camera movement. The camera stops
at the map boundaries. Space pauses; Home reloads the selected starting point.
Keys 1–5 select the normal starting area, top left, top right, bottom left and
bottom right. These shortcuts reload the same map with the display blanked.
They do not select different stages. See [all HUD controls](raster-scroll.md#default-build-and-controls).

The visible maze is 240x201 pixels. Its top-left camera position is bounded by
`0 <= x <= 576` and `0 <= y <= 1191`. Initial position is `(264,1032)` in the
bordered image. Arcade coordinates are obtained by subtracting `(24,24)`;
this offset does not change the original maze geometry. The normal starting
area places the arcade's initial vehicle area near the viewport center.

Each sealed `references/build/default-*/` bundle includes:

| File | Purpose |
| --- | --- |
| `stage-one.png` | Complete 816x1392 image for visual inspection |
| `stage-one.json` | Dimensions, coordinate offset, landmarks and native comparison count |
| `stage-tilemap.bin` | Original tile codes/attributes in bordered map order |
| `stage-world.bin` | Full decoded map using the shared MSX palette |
| `stage-landmarks.bin` | Five little-endian camera-coordinate pairs |
| `stage-radar-x.bin`, `stage-radar-y.bin` | Camera-center projection tables, keeping division out of the raster deadline |
| `bank-*.bin` | Packed map tiles, HUD fonts and resources used by the cartridge |
| `build.json`, `manifest.json` | Input/source/output provenance and hashes |

These contain original-derived data and remain ignored. `make clean` removes
builds, including the large map preview; original ROMs, assets and the native
map-acquisition cache remain intact.

## Exact reconstruction and native check

[`stage_one.py`](../scripts/msx/stage_one.py) validates the contributor's complete
supported `nrallyx` ROM set before reading any tables. It reconstructs the
32x56 layout from the original program's first-stage bitmap and neighbor masks,
then checks it against untouched first-stage game RAM. Original tile selection
uses the ROM's wall-shape, object and flower tables. Tile attributes retain
horizontal/vertical flips and palette selection. The existing SCREEN 5 color
conversion applies; positions, silhouettes and pixel dimensions are unchanged.

The initial static board contains eight ordinary flags, one special S flag and
one lucky L flag, with no rocks. Their positions come from a deterministic fresh original-game replay,
including the original initialization of object placement. The background does
not include moving cars, smoke or shadows: those are separate arcade objects.

On first build, [`stage_one_capture.lua`](../scripts/msx/stage_one_capture.lua)
launches MAME 0.289 with isolated settings, inserts a coin and starts a one-player
game through real input fields. It captures video RAM and board RAM at frame
2200. The first-stage snapshot is taken **before** installing a separate RAM
harness for verification. No original program ROM is patched.

For the independent selector check, that harness calls the original Z80
full-window redraw routine on 28 overlapping 32x32-tile windows spanning the
entire maze and its exterior. All **28,672 tile code/attribute pairs** must match
the Python reconstruction, including all ten flags, wall junctions and flowers.
The check executes the original renderer; it does not merely compare two Python
implementations of the same formulas. The captured board and generated native
windows are sealed in `references/stage-one/native-v1/` and verified before reuse.
This cache is original-derived data and must never be committed.

A fresh acquisition needs the contributor ROMs and MAME 0.289. Builds also need
the existing extracted assets and verified HUD/capture input bundles described
in the [README](../README.md). No ROM or BIOS is downloaded. Incomplete or changed
cache payloads fail validation rather than being silently accepted.

## Streaming and integration boundary

The renderer stores the map as packed scanlines in an ASCII16 cartridge. Each
pixel row has a 1024-pixel padded stride (512 bytes); 32 pixel rows, or four tile
rows, fit per 16 KB bank. Tile columns read eight strided four-byte segments;
inspection loads individual tiles from their strided rows. There are 44 map banks,
two HUD font/resource banks, two player code/resource banks, two tile-ID banks and a fixed code
bank; padding makes the cartridge **1 MB**. ROM bank 0 stays mapped at
0x4000–0x7FFF. Writes to 0x7000 select the bank at 0x8000–0xBFFF.

VRAM pages 0 and 1 form a **512x256** pixel ring, containing different adjacent
parts of the map. R26/R27 scroll across both pages; R23 wraps vertically within
the ring. World coordinates remain 16-bit and bounded. The low hardware scroll
coordinates wrap independently; wrapping VRAM does not wrap the game world.

The cache covers 64x32 tiles. Relative to the camera's tile coordinate, it starts
16 tiles to the left and three tiles above. On an eight-pixel boundary crossing,
the renderer queues the newly entering far row/column. After the header split,
it uploads at most four column tiles and eight row tiles per refresh. Each job
finishes within eight one-pixel movement refreshes, in hidden guard space.
The visible maze is never shifted by a full-screen CPU copy or an HMMM command.
Initial loading and landmark jumps refill the complete cache while blanked.
Driving uses the [28-tile VRAM atlas and HMMM guard streamer](player.md#cache-and-raster-scheduling)
to sustain the native car speed; inspection retains its CPU tile-upload budget.

In inspection mode the radar player marker represents the **viewport center**, projected
onto the full bordered map. White fixed points follow the captured stage flags;
the red enemy remains a captured display fixture. [Driving mode](player.md)
connects the original player's movement, wall collisions and animation, and the
radar follows that player. Flag collection, Fuel consumption, scoring and enemy
AI remain future integration work. The [HUD API](hud.md) accepts live state and provides a
read-only native-RAM adapter; the demonstration supplies these fixtures through
that same interface. Keyboard movement is camera inspection and can pass
through walls; it does not change original game rules.

See [renderer integration and timing](raster-scroll.md#runtime-integration-contract)
for raster ownership, memory and update deadlines.

"""SCREEN 4 right-edge policy, explicitly authorized for this laboratory.

The last seven screen-space scenery pixels use their source tile row's dominant
color. Ties retain the first source pixel's color. This applies in every phase,
including zero; the edge does not switch palettes at the eighth pixel.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from collections import Counter

SCENE_WIDTH = 200
HUD_CONTENT_X = 208
EDGE_WIDTH = 7


def edge_tiles(source, phase, black=11):
    """Return original tile 24 with a simplified tail, and mixed tile 25.

    Each result uses at most two colors per eight-pixel row. The mixed tile
    contains only one scenery color and black, never colors from HUD content.
    """
    tail=bytearray(source)
    mixed=bytearray([black])*64
    for y in range(8):
        row=source[y*8:y*8+8]
        dominant=Counter(row).most_common(1)[0][0]
        for x in range(8):
            screen_x=192-phase+x
            if screen_x>=SCENE_WIDTH-EDGE_WIDTH:
                tail[y*8+x]=dominant
            if x<phase:
                mixed[y*8+x]=dominant
    return bytes(tail),bytes(mixed)

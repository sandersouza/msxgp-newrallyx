"""Deterministic extra native enemies for isolated first-stage test ROMs.

Mode zero leaves the native population alone. Modes three and seven clone only
the 24-byte live descriptor, then place extra cars on contributor-ROM roads.
Generated coordinates and source bytes remain in ignored build directories.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib
import json
from pathlib import Path

from src.toolchain.msx.enemy_navigation import original_maps

COUNTS = (0, 3, 7)
CELL_PIXELS = 24
DESCRIPTOR_BYTES = 24
DESCRIPTOR_STRIDE = 32


def initial_cells(program):
    """Read the validated original player/enemy initializer immediates."""
    if len(program) != 16384:
        raise ValueError('Incomplete contributor program')
    if (program[0xc9b:0xc9e] != bytes.fromhex('dd3608')
            or program[0xc9f:0xca2] != bytes.fromhex('dd360a')
            or program[0xab5:0xabb] != bytes.fromhex('06051120000e')
            or program[0x1d:0x20] != bytes.fromhex('dd3688')):
        raise ValueError('Native initial-cell boundaries changed')
    enemy = program[0xab5:0xaf5]
    signature = bytes.fromhex('dd360a')
    if enemy.count(signature) != 1:
        raise ValueError('Native enemy Y initializer boundary changed')
    y = enemy[enemy.index(signature)+3]
    # For the native first-stage count of one, RST10 recentres the first car.
    # Its general loop X is used after a test restart while count is 3/7.
    return (program[0xc9e], program[0xca2]), (program[0x20], y)


def world(cell):
    return tuple(36+CELL_PIXELS*v for v in cell)


def squared_distance(a, b):
    return sum((av-bv)**2 for av, bv in zip(a, b))


def spawn_plan(program):
    """Choose spread road centres inside the initial complete-car viewport.

    The three-car build uses the same first two extra cells as the seven-car
    build. No random state, rules, graphics, or contributor data is embedded in
    this source. Forty-eight pixels separates every initial pair of enemies;
    every extra car starts strictly more than 48 pixels from the player.
    """
    player, first_enemy = initial_cells(program)
    restart_first_enemy = (program[0xabb], first_enemy[1])
    navigation = original_maps(program)[:2048]
    px, py = world(player)
    camera = (min(608, max(0, px-104)), min(1180, max(0, py-105)))
    if any(not (0 <= x < 32 and 0 <= y < 56 and navigation[y*32+x])
           for x, y in (player, first_enemy, restart_first_enemy)):
        raise ValueError('Native initial car does not occupy a first-stage road')
    candidates = []
    for y in range(56):
        for x in range(32):
            cell = (x, y)
            wx, wy = world(cell)
            # Full 16x16 car, within the 8..199 playfield and 0..211 rows.
            sx, sy = wx-8-camera[0], wy-8-camera[1]
            if (navigation[y*32+x] and 8 <= sx <= 184 and 0 <= sy <= 196
                    and squared_distance((wx, wy), (px, py)) > 48**2):
                candidates.append(cell)
    # The test keeps the original first descriptor after Enemy_Init, including
    # its native count-dependent spawn on restart. Avoid both possible cells.
    placed = list(dict.fromkeys((first_enemy, restart_first_enemy)))
    extra = []
    for dx, dy in ((-3, -2), (3, -2), (-3, 2), (3, 2), (0, -4), (0, 4)):
        target = (player[0]+dx, player[1]+dy)
        available = [cell for cell in candidates if all(
            squared_distance(cell, used) >= 2**2 for used in placed)]
        if not available:
            raise ValueError('Not enough separated visible roads for seven native cars')
        cell = min(available, key=lambda item: (
            squared_distance(item, target), item[1], item[0]))
        placed.append(cell)
        extra.append(cell)
    return dict(player_cell=player, original_enemy_cell=first_enemy,
                original_enemy_restart_cell=restart_first_enemy,
                camera=camera, extra_cells=extra)


def prepare(root, out, program, enemies=0):
    """Write the generated table and return the public build metadata."""
    if enemies not in COUNTS:
        raise ValueError(f'Test population must be one of {COUNTS}')
    root, out = Path(root), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    metadata = dict(test_enemies=enemies, native_population_override=bool(enemies),
                    descriptor_bytes=DESCRIPTOR_BYTES,
                    descriptor_stride=DESCRIPTOR_STRIDE,
                    private_ram_bytes=0,
                    native_source_sha256=hashlib.sha256(program).hexdigest(),
                    scope='Isolated first-stage test; original AI, motion, smoke and contact; HUD and hardware sprite limit remain enabled')
    payload = b''
    if enemies:
        plan = spawn_plan(program)
        player = world(plan['player_cell'])
        cells = plan['extra_cells'][:enemies-1]
        payload = bytes(value for cell in cells for value in cell)
        metadata.update(player_cell=plan['player_cell'], player_world=player,
                        original_enemy_cell=plan['original_enemy_cell'],
                        original_enemy_world=world(plan['original_enemy_cell']),
                        original_enemy_restart_cell=plan['original_enemy_restart_cell'],
                        original_enemy_restart_world=world(plan['original_enemy_restart_cell']),
                        initial_camera=plan['camera'],
                        extra_spawns=[dict(cell=cell, world=world(cell),
                            player_distance_pixels=squared_distance(world(cell), player)**0.5,
                            sprite_position=[world(cell)[i]-8-plan['camera'][i] for i in range(2)])
                            for cell in cells],
                        minimum_enemy_separation_pixels=min(
                            squared_distance(world(a), world(b))**0.5
                            for n, a in enumerate([plan['original_enemy_cell'], *cells])
                            for b in [plan['original_enemy_cell'], *cells][n+1:]),
                        valid_roads=True,
                        extra_cars_initially_wholly_inside_playfield=True)
    (out/'game-multi-spawns.bin').write_bytes(payload)
    (out/'game-multi.json').write_text(json.dumps(metadata, indent=2)+'\n')
    return metadata

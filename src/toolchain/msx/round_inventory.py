"""Acquire original round preparation without claiming full-match replay coverage."""
import csv
import os
import subprocess

from src.toolchain.graphics.roms import input_records, load_metadata, validate_roms
from src.toolchain.scenes.bundle import digest, load_assets
from src.toolchain.scenes.storage import json_write, require_ignored, seal
from src.toolchain.scenes.record import lua_literal
from .build import destination
from .flags import records
from .stage_one import acquire, cells_from_rom, tile, TILE_COLUMNS, TILE_ROWS


def analyze(program, video, work, assets):
    """Cross-check original initialized cells and enumerate actual scenery colors."""
    if len(video) != 4096 or len(work) != 2048:
        raise ValueError('Incomplete original round snapshot')
    page, wall, flower = (video[a] for a in (0x28f, 0x2b1, 0x2d6))
    if page not in range(0x30, 0x34):
        raise ValueError('Unexpected original terrain page')
    cells = work[:1792]
    geometry = cells_from_rom(program, page)
    for i, (actual, expected) in enumerate(zip(cells, geometry)):
        if actual in (1, 2, 3, 4):
            if expected:
                raise ValueError(f'Original object overlaps terrain at cell {i}')
        elif actual != expected:
            raise ValueError(f'Original terrain mismatch at cell {i}')
    flags = records(video, cells)
    if [cells.count(kind) for kind in (1, 4, 2)] != [8, 1, 1]:
        raise ValueError('Original flag count differs from placement tables')
    count = video[0x251]
    if cells.count(3) != count:
        raise ValueError('Original rock count differs from parameter dispatch')
    pointer = int.from_bytes(video[0x996:0x998], 'little')-0x8000
    rocks = []
    if count:
        if not 0 <= pointer <= len(video)-count*2:
            raise ValueError('Invalid original rock table')
        for at in range(pointer, pointer+count*2, 2):
            cell = int.from_bytes(video[at:at+2], 'little')-0x9800
            if cell in rocks or not 0 <= cell < len(cells) or cells[cell] != 3:
                raise ValueError('Original rock pointer does not match cell map')
            rocks.append(cell)
    pairs = {tile(program, cells, x-3, y-3, wall, flower)
             for y in range(TILE_ROWS) for x in range(TILE_COLUMNS)}
    colors = set()
    for code, attr in pairs:
        for pen in set(assets.pixels['tiles'][code*64:(code+1)*64]):
            colors.add(assets.palette['lookup'][(attr & 63)*4+pen])
    return dict(round_byte=video[0x1b0], displayed_round=video[0x1b0]-1,
                terrain_page=page, wall_color=wall, flower=flower,
                enemy_parameter=video[0x24e], rocks=count, rock_cells=rocks, flags=flags,
                scenery_color_indices=sorted(colors),
                scenery_rgb=sorted({tuple(assets.palette['rgb'][i]) for i in colors}),
                unique_tiles=len(pairs), checked_cells=len(cells))


def run(root, args):
    # Validate all contributor inputs before invoking MAME. acquire also verifies
    # the existing first-round cache and pinned program hash inputs.
    program, _ = acquire(root)
    roms = validate_roms(root/'references/roms/nrallyx', load_metadata())
    source = input_records(roms)
    assets = load_assets(root/args.assets)
    out = destination(root, args.output)
    require_ignored(root, [out/'case-000-video.bin'])
    out.mkdir(parents=True)
    rounds = list(range(2, args.last_round+2))
    config = out/'config.lua'
    config.write_text('return '+lua_literal(dict(output=str(out.resolve()),
                                               rounds=rounds, random=[1, 0]))+'\n')
    script = root/'src/toolchain/msx/round_inventory.lua'
    version = subprocess.check_output([args.mame, '-version'], text=True).strip()
    if not version.startswith('0.289 '):
        raise ValueError('Round acquisition requires MAME 0.289')
    command = [args.mame, 'nrallyx', '-noreadconfig', '-noplugins', '-nocheat',
               '-rompath', str(root/'references/roms'), '-video', 'none', '-sound', 'none',
               '-nothrottle', '-noautosave', '-noautoframeskip', '-frameskip', '0',
               '-skip_gameinfo', '-debug', '-debugger', 'none',
               '-autoboot_delay', '0', '-autoboot_script', str(script),
               '-cfg_directory', str(out/'cfg'), '-nvram_directory', str(out/'nvram'),
               '-seconds_to_run', str(40+34*len(rounds))]
    with (out/'mame.log').open('w') as log:
        subprocess.run(command, check=True, timeout=180, stdout=log, stderr=subprocess.STDOUT,
                       env=dict(os.environ, ROUND_INVENTORY_CONFIG=str(config.resolve())))
    if not (out/'complete').is_file():
        raise ValueError(f'Incomplete original round acquisition: {out}/mame.log')
    with (out/'events.tsv').open() as stream:
        events = list(csv.DictReader(stream, delimiter='\t'))
    if [int(e['round_byte']) for e in events] != [2]+rounds:
        raise ValueError('Missing, duplicate or reordered round initialization cases')
    results = []
    for index, event in enumerate(events):
        result = analyze(program, (out/f'case-{index:03d}-video.bin').read_bytes(),
                         (out/f'case-{index:03d}-work.bin').read_bytes(), assets)
        result.update(case=index, real_credit_start=index == 0,
                      challenge_intro=bool(int(event['challenge_intro'])),
                      preparation_frames=int(event['elapsed_frames']))
        if result['challenge_intro'] != (result['round_byte'] % 4 == 0):
            raise ValueError('Original challenge dispatch differs from observed round class')
        results.append(result)
    if source != input_records(validate_roms(root/'references/roms/nrallyx', load_metadata())):
        raise ValueError('Contributor ROM inputs changed')
    json_write(out/'report.json', dict(schema_version=1, emulator=version, roms=source,
        source_sha256=digest(script), cases=results,
        scope='One real credit/start; explicitly seeded original round preparation. '
              'No natural round completion, full-match, two-player or MSX integration claim.',
        random_seed=[1, 0], seeded_sound_ready=1, scenery_only=True))
    require_ignored(root, [p for p in out.rglob('*') if p.is_file()]); seal(out)
    print(f'{len(results)} original round preparations checked: {out}/report.json')
    return out

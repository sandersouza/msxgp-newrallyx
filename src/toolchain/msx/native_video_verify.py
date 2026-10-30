"""Offline prepared-page evidence gates; scanout and gameplay remain separate."""
import csv
import json
import math
from pathlib import Path
import statistics

from .native_contract import Snapshot
from .native_scene import verify_scene_cache, verify_radar_cache, radar_from_snapshot, project_radar, radar_visible
from .native_scene import verify_presentation


def hardware_actor_inputs(bundle):
    """Read pending HUD colors and the palette from the bound cartridge."""
    from .native_probe import symbols
    syms = symbols(bundle/'native.sym')
    rom = (bundle/'native.rom').read_bytes()
    at = syms['sprite_colors']-0x4000+224
    fuel = rom[at:at+48]
    at = syms['life_colors']-0x4000
    return dict(palette=(bundle/'native-palette.bin').read_bytes(),
                hud_enabled=json.loads((bundle/'build.json').read_text()).get('hud_enabled', True),
                fuel=fuel, life=rom[at:at+48])


def verify_hardware_actors(snapshot, data, page, sprites, lookup, translation, resources):
    """Compare actual SAT/patterns against fresh original actor pixels."""
    from PIL import ImageChops
    from .native_scanout import compose
    from .native_sprites import compile_actors, published_actors
    hud, vram = data['hud'], data['vram']
    actual = published_actors(hud, vram, page)
    expected = compile_actors(snapshot, sprites, lookup, translation, hud,
                              hud_enabled=resources.get('hud_enabled', True))
    if not expected['supported']:
        raise ValueError('Hardware actor frame required the bitmap fallback')
    args = (vram, hud, page, resources['palette'], resources['fuel'], resources['life'])
    reference, rendered = compose(*args, actor_sprites=expected), compose(*args, actor_sprites=actual)
    diff = ImageChops.difference(reference, rendered)
    return sum(pixel != (0, 0, 0) for pixel in diff.get_flattened_data())

REGISTERS = ['AF', 'BC', 'DE', 'HL', 'IX', 'IY', 'AF2', 'BC2', 'DE2', 'HL2', 'SP']
FRAME_FIELDS = {'frame', 'tick', 'cycles', 'phase', 'time', 'hud_cycles',
                'tile_cycles', 'restore_cycles', 'actor_cycles', 'input_tick', 'latency_cycles'}


def _rows(path):
    try:
        with path.open() as stream:
            return list(csv.DictReader(stream, delimiter='\t'))
    except OSError as error:
        raise ValueError(f'Missing video evidence: {path.name}') from error


def _integer(row, key):
    value = row.get(key, '')
    if not isinstance(value, str) or not value.isdecimal():
        raise ValueError(f'Invalid video {key}')
    return int(value)


def _time(row):
    try:
        value = float(row['time'])
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError('Invalid video timestamp') from error
    if not math.isfinite(value) or value < 0:
        raise ValueError('Invalid video timestamp')
    return value


def verify_video_frames(output: Path, tiles: bytes, sprites: bytes,
                        lookup: bytes, translation: bytes, *, radar=False, hardware=None,
                        presentation=False, hud_enabled=True, actors_enabled=True, edge_clear=True,
                        aligned_gutter=False) -> dict:
    """Verify every completed page against its captured input, with no exclusions.

    This consumes raw acquisition before sealing, or an already sealed capture.
    The caller owns bundle/ROM provenance and the separate raster/behavior gates.
    A currently unfinished next job is permitted; no missing completed frame is.
    """
    try:
        execution = json.loads((output/'execution.json').read_text())
        context = json.loads((output/'presentation-context.json').read_text())
    except (OSError, ValueError) as error:
        raise ValueError('Missing video completion/context evidence') from error
    if (execution.get('complete') is not True or type(execution.get('ticks')) is not int
            or execution['ticks'] < 1):
        raise ValueError('Incomplete video execution')
    if (context.get('complete') is not True or context.get('registers') != REGISTERS
            or type(context.get('game_ram_bytes')) is not int or context['game_ram_bytes'] != 6536
            or type(context.get('calls')) is not int or type(context.get('steps')) is not int
            or not context['calls'] >= context['steps'] > 0):
        raise ValueError('Incomplete presentation context proof')
    rows = _rows(output/'video.tsv')
    if not rows:
        raise ValueError('Missing completed video frames')
    suffixes = ('state', 'host', 'cache', 'dirty', 'vram') + (('hud',) if radar else ())
    expected = {f'video-frame-{n:05d}-{suffix}.bin'
                for n in range(1, len(rows)+1)
                for suffix in suffixes}
    if {p.name for p in output.glob('video-frame-*')} != expected:
        raise ValueError('Incomplete video frame inventory')
    previous_input, previous_finish, previous_time = -6, -1, -1
    different = pixels = descriptor_changes = radar_differences = radar_pixels = radar_state_changes = 0
    failures, latencies, active_cycles = [], [], []
    actor_differences = actor_pixels = actor_frames = fallback_frames = 0
    gutter_pixels = gutter_differences = fuel_errors = hidden_fuel_frames = 0
    completed = {}
    for n, row in enumerate(rows, 1):
        if set(row) != FRAME_FIELDS | ({'radar_cycles'} if radar else set()):
            raise ValueError('Invalid video frame fields')
        values = {key: _integer(row, key) for key in row if key != 'time'}
        now = _time(row)
        if (values['frame'] != n or not previous_input+6 <= values['input_tick'] <= values['tick']
                or not previous_finish <= values['tick'] <= execution['ticks']
                or values['phase'] not in range(4) or now <= previous_time
                or values['cycles'] != sum(values[k] for k in
                    ('hud_cycles', 'tile_cycles', 'restore_cycles', 'actor_cycles') + (('radar_cycles',) if radar else ()))
                or values['latency_cycles'] < values['cycles']):
            raise ValueError('Invalid video frame sequence/accounting')
        prefix = f'video-frame-{n:05d}'
        data = {suffix: (output/f'{prefix}-{suffix}.bin').read_bytes()
                for suffix in suffixes}
        if any(len(data[key]) != size for key, size in
               (('state', 6536), ('host', 2176), ('cache', 4096), ('dirty', 128), ('vram', 131072))):
            raise ValueError('Truncated video frame payload')
        if radar and len(data['hud']) != 1140:
            raise ValueError('Truncated native HUD evidence')
        host, cache, state = data['host'], data['cache'], data['state']
        page = host[0x16]
        if (page not in (0, 1) or host[0x10] != 1 or host[0x18] != 0x1f+page*32
                or host[0x1d] != 0 or any(host[0x600:0x680])):
            raise ValueError('Incomplete or inconsistent ready bitmap page')
        snapshot = Snapshot(values['input_tick'], 'post-game-irq',
                            state[:4096], state[4096:6144], state[6144:])
        if presentation:
            if not radar:
                raise ValueError('Presentation policy requires HUD evidence')
            policy = verify_presentation(snapshot, data['vram'], data['hud'], page,
                                         hud_enabled=hud_enabled, edge_clear=edge_clear,
                                         aligned_gutter=aligned_gutter)
            gutter_pixels += policy['gutter_pixels']
            gutter_differences += policy['gutter_differences']
            fuel_errors += policy['fuel_attribute_errors']
            hidden_fuel_frames += not policy['fuel_visible']
        hardware_active = False
        if hardware is not None:
            if not radar or data['hud'][0x176] not in (0, 1):
                raise ValueError('Invalid hardware actor frame mode')
            hardware_active = bool(data['hud'][0x176])
            if hardware_active:
                actor_differences += verify_hardware_actors(snapshot, data, page, sprites, lookup, translation, hardware)
                actor_pixels += 320*240
                actor_frames += 1
            else:
                if data['hud'][0x175] != 0:
                    raise ValueError('Bitmap fallback left hardware actors enabled')
                fallback_frames += 1
        report = verify_scene_cache(snapshot, data['vram'], page, tiles, sprites, lookup, translation,
                                    radar=radar and hud_enabled, bitmap_actors=actors_enabled and not hardware_active)
        if radar and hud_enabled:
            radar_report = verify_radar_cache(snapshot, data['vram'], page, tiles, sprites, lookup, translation,
                                              bitmap_actors=actors_enabled and not hardware_active,
                                              right_gutter=presentation and edge_clear,
                                              aligned_gutter=aligned_gutter)
            radar_differences += radar_report['different_pixels']
            radar_pixels += radar_report['compared_pixels']
            points = radar_from_snapshot(snapshot)
            radar_state_changes += host[0x54] != int(radar_visible(snapshot))
            flags = points['flags'] if radar_visible(snapshot) else (None,)*10
            expected_flags = bytes(value for point in flags for value in project_radar(point))
            expected_enemies = bytes(value for point in points['enemies'] for value in project_radar(point))
            radar_state_changes += sum(a != b for a, b in zip(data['hud'][0x350:0x364], expected_flags))
            radar_state_changes += sum(a != b for a, b in zip(cache[0x660:0x670], expected_enemies))
            radar_state_changes += sum(a != b for a, b in zip(data['hud'][0xc0:0xc2], project_radar(points['player'])))
        pixels += report['compared_pixels']
        different += report['different_pixels']
        first_row = ((snapshot.shadows[0x140]+22) & 255)//8
        changes = sum((state[0x400+i] != host[0x180+i]
                       or state[0xc00+i] != cache[0x800+i])
                      for y in range(26) for x in range(32)
                      for i in [((first_row+y) & 31)*32+x])
        descriptor_changes += changes
        if (report['different_pixels'] or changes) and len(failures) < 8:
            failures.append(dict(frame=n, input_tick=values['input_tick'],
                                 completed_tick=values['tick'], descriptor_changes=changes,
                                 different_pixels=report['different_pixels'],
                                 first_difference=report['first_difference']))
        completed[values['input_tick']] = values
        latencies.append(values['latency_cycles'])
        active_cycles.append(values['cycles'])
        previous_input, previous_finish, previous_time = values['input_tick'], values['tick'], now
    steps = _rows(output/'video-steps.tsv')
    previous_time = -1
    maximum_step = 0
    step_totals = {}
    for row in steps:
        if set(row) != {'input_tick', 'tick', 'stage', 'cycles', 'time'}:
            raise ValueError('Invalid video step fields')
        values = {key: _integer(row, key) for key in row if key != 'time'}
        now = _time(row)
        if (not values['input_tick'] <= values['tick'] <= execution['ticks']
                or values['stage'] not in range(6 if radar else 5) or now < previous_time):
            raise ValueError('Invalid video step sequence')
        maximum_step = max(maximum_step, values['cycles'])
        total = step_totals.setdefault(values['input_tick'], [0]*(6 if radar else 5))
        total[values['stage']] += values['cycles']
        previous_time = now
    if len(steps) != context['steps'] or any(
            sum(step_totals.get(tick, [])) != row['cycles'] for tick, row in completed.items()):
        raise ValueError('Video frame/context step totals disagree')
    return dict(schema_version=1, prepared_frames=len(rows),
                hud_enabled=hud_enabled,
                actors_enabled=actors_enabled,
                prepared_bitmaps_verified=different == descriptor_changes == radar_differences == radar_state_changes == actor_differences == gutter_differences == fuel_errors == 0,
                gutter_compared_pixels=gutter_pixels, gutter_different_pixels=gutter_differences,
                fuel_attribute_errors=fuel_errors, hidden_fuel_frames=hidden_fuel_frames,
                hardware_actor_rgb_differences=actor_differences, hardware_actor_rgb_pixels=actor_pixels,
                hardware_actor_frames=actor_frames, bitmap_fallback_frames=fallback_frames,
                compared_pixels=pixels, different_pixels=different,
                descriptor_changes=descriptor_changes, first_failures=failures,
                radar_compared_pixels=radar_pixels, radar_different_pixels=radar_differences,
                radar_state_changes=radar_state_changes,
                presentation_context=context,
                max_step_cycles=maximum_step, max_step_ms=maximum_step/3579.545,
                median_active_cycles=statistics.median(active_cycles),
                max_active_cycles=max(active_cycles),
                median_latency_ms=statistics.median(latencies)/3579.545,
                max_latency_ms=max(latencies)/3579.545,
                rendered_rgb_verified=False, gameplay_verified=False)

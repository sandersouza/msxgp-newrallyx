"""Real VDP scanout of actor sprite fixtures, separate from runtime integration."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageChops

from src.toolchain.scenes.bundle import digest, load_assets, verify_manifest
from src.toolchain.scenes.storage import json_write, require_ignored, seal
from .build import destination as build_destination
from .native_contract import Snapshot
from .native_probe import symbols
from .emulator import reference_machine, tcl
from .native_scene import radar_bitmap, radar_visible
from .native_scanout import compose
from .native_sprites import compile_actors, ACTOR_PATTERN_VRAM
from .native_video_verify import verify_video_frames


def verify_actor_sprites(root, rom, capture, output, bios, *, frames,
                        openmsx='openmsx', machine='Panasonic_FS-A1WSX'):
    root, rom, capture, bios = map(lambda p: Path(p).resolve(), (root, rom, capture, bios))
    verify_manifest(rom.parent)
    verify_manifest(capture)
    runtime = json.loads((capture/'runtime.json').read_text())
    if runtime.get('candidate_manifest_sha256') != digest(rom.parent/'manifest.json'):
        raise ValueError('Sprite fixture source belongs to another candidate')
    if not frames or len(set(frames)) != len(frames) or any(type(n) is not int or n < 1 for n in frames):
        raise ValueError('Require distinct positive prepared-frame numbers')
    assets = load_assets(root/'assets/arcade/nrallyx')
    palette = (rom.parent/'native-palette.bin').read_bytes()
    # Translation is bound to the source palette and actual cartridge palette.
    from .screen5 import rgb333
    rgb = [(palette[n] >> 4, palette[n+1], palette[n] & 7) for n in range(0, 32, 2)]
    translation = bytes(0 if n == 0 else 11 if n == 1 else rgb.index(rgb333(color))
                        for n, color in enumerate(assets.palette['rgb'][:16]))
    prepared = verify_video_frames(capture, assets.pixels['tiles'], assets.pixels['sprites'],
                                  bytes(assets.palette['lookup']), translation, radar=True)
    if not prepared['prepared_bitmaps_verified']:
        raise ValueError('Sprite fixtures require exact prepared-page evidence')
    syms = symbols(rom.parent/'native.sym')
    cartridge = rom.read_bytes()
    at = syms['sprite_colors']-0x4000+224
    fuel = cartridge[at:at+48]
    at = syms['life_colors']-0x4000
    life = cartridge[at:at+48]
    output = build_destination(root, Path(output))
    session = build_destination(root, output.with_name(output.name+'-session'))
    require_ignored(root, [output/'fixture-vram.bin'])
    output.mkdir(parents=True)
    session.mkdir(parents=True)
    fixtures, plans = [], []
    for number in frames:
        prefix = capture/f'video-frame-{number:05d}'
        raw = Path(str(prefix)+'-state.bin').read_bytes()
        snap = Snapshot(0, 'post-game-irq', raw[:4096], raw[4096:6144], raw[6144:])
        hud = Path(str(prefix)+'-hud.bin').read_bytes()
        host = Path(str(prefix)+'-host.bin').read_bytes()
        vram = Path(str(prefix)+'-vram.bin').read_bytes()
        actors = compile_actors(snap, assets.pixels['sprites'], bytes(assets.palette['lookup']), translation, hud)
        if not actors['supported']:
            raise ValueError(f'Unsupported actor fixture {number}: {actors["reason"]}')
        page = host[0x16]
        expected = compose(vram, hud, page, palette, fuel, life)
        background = bytearray(vram)
        start = page*32768
        background[start:start+32768] = vram[65536:98304]
        if radar_visible(snap):
            (ox, oy), _ = radar_bitmap(snap)
            for y in range(60):
                for x in range(50):
                    wx, wy = (ox+x) & 255, (oy+y) & 255
                    at, shift = start+wy*128+wx//2, 0 if wx & 1 else 4
                    background[at] = (background[at] & ~(15 << shift)) | (vram[at] & (15 << shift))
        simulated = compose(background, hud, page, palette, fuel, life, actor_sprites=actors)
        if ImageChops.difference(simulated, expected).getbbox() is not None:
            raise ValueError(f'Actor fixture {number} changes source pixels')
        sat = hud[0x100:0x144]+actors['attributes']+bytes((216,))
        background[0x1f600:0x1f600+len(sat)] = sat
        background[0x1f510:0x1f510+len(actors['colors'])] = actors['colors']
        background[ACTOR_PATTERN_VRAM:ACTOR_PATTERN_VRAM+len(actors['patterns'])] = actors['patterns']
        target = output/f'frame-{number:05d}'
        Path(str(target)+'-vram.bin').write_bytes(background)
        Path(str(target)+'-hud.bin').write_bytes(hud)
        expected.save(str(target)+'-expected.png')
        fixtures.append('{'+f'{tcl(target)} {page} {hud[0x1a]} {hud[0x1b]} {hud[0x1c]}'+'}')
        plans.append(dict(frame=number, slots=actors['slots'], peak=actors['peak']))
    script = root/'src/toolchain/msx/native_sprite_probe.tcl'
    shutil.copyfile(script, output/'probe.tcl')
    lines = ['set save_settings_on_exit false', 'set sound_driver null', 'set vsync off',
             'set renderer SDLGL-PP', 'set pause_on_lost_focus false', 'set pause false',
             'set minframeskip 0', 'set maxframeskip 0', 'set gamma 1', 'set brightness 0',
             'set contrast 0', 'set blur 0', 'set noise 0', 'set scanline 0',
             'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
             f'filepool add -path {tcl(bios)} -types system_rom -position 1',
             reference_machine(root, machine), 'set firmwareswitch off', 'set throttle on',
             'set speed 100', 'set z80_freq 3579545', 'set z80_freq_locked false',
             f'cart {tcl(rom)} -romtype ASCII16', 'reset', f'set ns_out {tcl(output)}',
             f'set ns_actor_patterns_address {ACTOR_PATTERN_VRAM}',
             'set ns_symbols [dict create '+' '.join(f'{k} {v}' for k, v in syms.items())+']',
             'set ns_fixtures {'+' '.join(fixtures)+'}', f'source {tcl(output/"probe.tcl")}']
    (output/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem; exit 2}\n')
    env = dict(os.environ, OPENMSX_HOME=str(session/'home'), OPENMSX_USER_DATA=str(session/'userdata'))
    with (output/'emulator.log').open('w') as log:
        subprocess.run([openmsx, '-script', str(output/'session.tcl')], env=env, stdout=log,
                       stderr=subprocess.STDOUT, timeout=180, check=True)
    execution = json.loads((output/'execution.json').read_text())
    if (execution.get('complete') is not True or execution.get('fixtures') != len(frames)
            or execution.get('original_game_ram_unchanged') is not True):
        raise ValueError('Incomplete hardware actor fixture execution')
    for plan in plans:
        target = output/f'frame-{plan["frame"]:05d}'
        fixture = Path(str(target)+'-vram.bin').read_bytes()
        slots = plan['slots']
        exact = (Path(str(target)+'-sat.bin').read_bytes()[68:69+slots*4] ==
                 fixture[0x1f644:0x1f645+slots*4]
                 and Path(str(target)+'-colors.bin').read_bytes()[:slots*16] ==
                 fixture[0x1f510:0x1f510+slots*16]
                 and Path(str(target)+'-patterns.bin').read_bytes()[:slots*32] ==
                 fixture[ACTOR_PATTERN_VRAM:ACTOR_PATTERN_VRAM+slots*32])
        if not exact:
            raise ValueError('Hardware actor fixture VRAM changed')
        with Image.open(str(target)+'-actual.png') as actual, Image.open(str(target)+'-expected.png') as expected:
            if actual.size != (320, 240):
                raise ValueError('Unexpected hardware actor capture dimensions')
            diff = ImageChops.difference(actual.convert('RGB'), expected.convert('RGB'))
            plan.update(different_pixels=sum(p != (0, 0, 0) for p in diff.get_flattened_data()), bounds=diff.getbbox())
    report = dict(scope='isolated hardware sprite fixtures; runtime compiler not enabled',
                  rom_sha256=digest(rom), capture_manifest_sha256=digest(capture/'manifest.json'),
                  probe_sha256=digest(Path(__file__)),
                  rendered_rgb_verified=all(p['different_pixels'] == 0 for p in plans),
                  compared_pixels=len(plans)*320*240, fixtures=plans, execution=execution,
                  gameplay_verified=False, assembled_sprite_compiler_verified=False)
    json_write(output/'verification.json', report)
    seal(output)
    return report

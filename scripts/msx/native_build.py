"""Build isolated loader/runtime probes and explicit original-logic candidates."""
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata

from .build import destination
from .inputs import video_timing
from .native_layout import Region, pack_assets, validate_layout
from scripts.graphics.roms import load_metadata, validate_roms, input_records
from scripts.scenes.bundle import digest, load_assets, read_json, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal
from scripts.z80_analysis import program_image, hook_specs
from .native_reset import patch_reset, PROGRAM_SHA256
from .native_verify import analyze_reference
from .native_logic import patch_logic, trampoline_source, coordinate_deltas


PROJECT = Path(__file__).resolve().parents[2]
ALLOCATIONS = (
    Region('program', 0, 0x4000), Region('resident', 0x4000, 0x8000),
    Region('game', 0x8000, 0xc000), Region('existing-host', 0xc000, 0xc473),
    Region('loader-state', 0xc500, 0xc580), Region('irq-stack', 0xc580, 0xc700),
    Region('discovery-tag', 0xc700, 0xc702),
    Region('vectors', 0xd000, 0xd101), Region('vector-jump', 0xd2d2, 0xd2d5),
    Region('loader-code', 0xd400, 0xe000), Region('software-irq-stack', 0xf000, 0xf200),
    Region('host-stack', 0xf200, 0xf380),
)


def _output(root, output):
    output = destination(root, output if output.is_absolute() else root / output)
    if output == root.resolve() / 'references/build':
        raise ValueError('Choose a fresh child of references/build')
    relative = unicodedata.normalize('NFC', output.relative_to(root.resolve()).as_posix()).casefold()
    tracked = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).decode().split('\0')
    folded = [unicodedata.normalize('NFC', name).casefold() for name in tracked if name]
    if any(name == relative or name.startswith(relative + '/') for name in folded):
        raise ValueError('Native output aliases tracked files')
    require_ignored(root, [output / 'native.rom', output / 'manifest.json'])
    return output


def build_probe(root: Path, output: Path, assembler: Path, hz: int = 50,
                program: bytes | None = None, resources: dict[str, bytes] | None = None,
                probe: str = 'loader', reset_reference: Path | None = None,
                optimize: bool = False, function_probe: bool = False,
                fine_irq: bool = False, video_reference: Path | None = None,
                assets_path: Path | None = None,
                execution_references: tuple[Path, ...] = ()) -> Path:
    """Exercise isolated loader/runtime/reset contracts without publishing gameplay.

    The reset/logic modes bind guarded original code to sealed execution
    evidence. Runtime mode is synthetic. Coordinate optimization is optional;
    its exhaustive function probe runs before original cold initialization.
    These builds never replace the default cartridge.
    """
    root = root.resolve()
    video = video_reference is not None
    if video and (probe != 'logic' or fine_irq or function_probe or assets_path is None):
        raise ValueError('Video requires explicit logic mode, assets and the VBlank clock')
    if (type(optimize) is not bool or type(function_probe) is not bool
            or type(fine_irq) is not bool or (fine_irq and probe != 'logic')
            or (optimize and probe != 'logic') or (function_probe and not optimize)):
        raise ValueError('Coordinate optimization/proof requires explicit logic mode')
    output = _output(root, output)
    if probe not in ('loader', 'runtime', 'irq', 'reset', 'logic') or (probe != 'loader' and program is not None):
        raise ValueError('Choose loader, synthetic runtime or original reset proof')
    reset_inputs, reset_boundaries = None, frozenset()
    if probe in ('reset','logic'):
        if reset_reference is None:
            raise ValueError('Reset proof requires sealed original execution evidence')
        verify_manifest(reset_reference)
        analyze_reference(reset_reference)
        if read_json(reset_reference / 'provenance.json').get('program_sha256') != PROGRAM_SHA256:
            raise ValueError('Unsupported reset execution evidence')
        roms = validate_roms(root / 'references/roms/nrallyx', load_metadata())
        reset_inputs = input_records(roms)
        program = program_image(roms, load_metadata())
        for evidence in (reset_reference,) + tuple(execution_references):
            verify_manifest(evidence)
            analyze_reference(evidence)
            if (read_json(evidence / 'provenance.json').get('program_sha256') != PROGRAM_SHA256
                    or read_json(evidence / 'provenance.json').get('inputs') != reset_inputs):
                raise ValueError('Supplemental execution must use the same complete source ROMs')
            with (evidence / 'execution.trace').open() as trace:
                reset_boundaries |= frozenset(int(line[:4],16) for line in trace
                    if re.match(r'^[0-9A-F]{4}: ', line))
    timing = video_timing(hz)
    if not assembler.is_file():
        raise ValueError('Managed sjasmplus is missing')
    if program is None:
        program = (bytes(range(256)) + bytes(16128)) if probe in ('runtime','irq') else bytes(16384)
    if type(program) is not bytes or len(program) != 16384:
        raise ValueError('Native program must contain exactly 16384 immutable bytes')
    video_meta = None
    if video:
        from .native_video import resources as video_resources
        resources, video_meta = video_resources(video_reference, assets_path)
    if resources is None:
        resources = {f'bank-{n}': bytes((0x40 + n,)) * 16384 for n in range(4)}
    assets, index = pack_assets(resources)
    allocations = ALLOCATIONS + ((Region('video-state', 0xc780, 0xc800),
        Region('tile-dirty-bits', 0xc800, 0xc880),
        Region('display-page-0-dirty', 0xc880, 0xc900),
        Region('display-page-1-dirty', 0xcd00, 0xcd80),
        Region('render-job-dirty', 0xcd80, 0xce00),
        Region('tile-code-cache', 0xc900, 0xcd00),
        Region('video-cache', 0xe000, 0xf000)) if video else ())
    validate_layout(allocations)
    output.mkdir(parents=True)
    (output / 'native-program.bin').write_bytes(program)
    if probe == 'logic':
        (output / 'native-source.bin').write_bytes(program)
        (output / 'logic-trampolines.inc').write_text(trampoline_source())
        if optimize:
            (output / 'native-coordinate.bin').write_bytes(coordinate_deltas())
        if video:
            from .native_video_hooks import trampolines
            (output / 'video-trampolines.inc').write_text(trampolines())
            _video_sources(output, video_reference, video_meta)
    (output / 'native-assets.bin').write_bytes(assets)
    config = dict(NATIVE_STATE=0xc500, NATIVE_TAG=0xc700,
                  NATIVE_LOADER=0xd400, NATIVE_LOADER_LIMIT=0xe000, NATIVE_STACK=0xf380,
                  NATIVE_IRQ_BOTTOM=0xc580, NATIVE_IRQ_STACK=0xc700,
                  NATIVE_R9=timing['vdp_r9'])
    config['NATIVE_RUNTIME_PROBE'] = int(probe in ('runtime','irq'))
    config['NATIVE_IRQ_PROBE'] = int(probe == 'irq')
    config['NATIVE_SCHEDULER'] = int(probe in ('irq','logic'))
    config['NATIVE_LOGIC'] = int(probe == 'logic')
    config['NATIVE_COORDINATE_OPT'] = int(optimize)
    config['NATIVE_FINE_IRQ'] = int(fine_irq)
    config['NATIVE_VIDEO'] = int(video)
    config['NATIVE_FINE_DEADLINE'] = int(fine_irq)
    config['NATIVE_FRAME_LINES'] = timing['lines']
    config['NATIVE_FUNCTION_PROBE'] = int(function_probe)
    config['NATIVE_FOREGROUND_RESUME'] = 0xc2f if probe == 'logic' else 0x120
    config['NATIVE_FRAME_LO'] = (timing['cpu_cycles']*2000) & 65535
    config['NATIVE_FRAME_HI'] = (timing['cpu_cycles']*2000) >> 16
    config['NATIVE_DIVISOR_LO'] = (3579545*33) & 65535
    config['NATIVE_DIVISOR_HI'] = (3579545*33) >> 16
    config['NATIVE_ORIGINAL_RESET_PROBE'] = int(probe in ('reset','logic'))
    (output / 'native-layout.inc').write_text(''.join(f'{key} EQU ${value:04x}\n' for key, value in config.items()))
    for name in ('native.asm', 'native-loader.inc', 'native-state.inc'):
        shutil.copyfile(PROJECT / 'src' / name, output / name)
    if probe in ('runtime', 'irq', 'reset', 'logic'):
        shutil.copyfile(PROJECT / 'src/native-runtime.inc', output / 'native-runtime.inc')
    if probe in ('irq','logic'):
        shutil.copyfile(PROJECT / 'src/native-scheduler.inc', output / 'native-scheduler.inc')
    if probe == 'irq':
        shutil.copyfile(PROJECT / 'tests/fixtures/native-irq.inc', output / 'native-irq.inc')
    if function_probe:
        shutil.copyfile(PROJECT / 'tests/fixtures/native-function.inc', output / 'native-function.inc')
        if fine_irq:
            shutil.copyfile(PROJECT / 'tests/fixtures/native-deadline.inc', output / 'native-deadline.inc')
    fixture = 'native-reset.asm' if probe in ('reset','logic') else 'native-loader.asm'
    shutil.copyfile(PROJECT / 'tests/fixtures' / fixture, output / 'loader-probe.asm')
    command = [str(assembler.resolve()), '--nologo', '--sym=native.sym',
               '--lst=native.lst', 'loader-probe.asm']
    result = subprocess.run(command, cwd=output, capture_output=True, text=True)
    if probe in ('reset','logic') and not result.returncode:
        (output / 'assembly-before-patching.log').write_text(result.stdout + result.stderr)
        syms = dict((name,int(value,16)) for name,value in re.findall(
            r'^(\w+): EQU 0x([0-9A-Fa-f]+)', (output/'native.sym').read_text(), re.M))
        program = (patch_logic(program,syms,reset_boundaries,optimize=optimize,video=video) if probe == 'logic'
                   else patch_reset(program, syms['Native_ResetFinalize'], reset_boundaries))
        (output / 'native-program.bin').write_bytes(program)
        result = subprocess.run(command, cwd=output, capture_output=True, text=True)
    (output / 'assembly.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError(f'Native loader assembly failed; see {output}/assembly.log: {result.stdout}{result.stderr}')
    rom = output / 'native.rom'
    if rom.stat().st_size != 131072:
        raise ValueError('Unexpected native loader cartridge size')
    json_write(output / 'layout.json', dict(allocations=[vars(r) for r in allocations],
        asset_capacity=65536, assets=index, clock_bytes=4,
        mapped_workspaces=([dict(role='asset-3', offset=0x2000, size=2048,
                                 capture_alias=0x2000, render_alias=0xa000)] if video else [])))
    json_write(output / 'build.json', dict(schema_version=1, mode=probe+'-probe', gameplay=False,
        coordinate_optimization=optimize,function_probe=function_probe,fine_irq=fine_irq,
        fine_clock='scanline-deadline' if fine_irq else None,
        video_candidate=video,
        presentation_logical_ticks=6 if video else None,
        presentation_cache='complete visible 26 tile rows; inactive bitmap page' if video else None,
        program_sha256=digest(output / 'native-program.bin'), timing=timing,
        reset_policy='machine reset; no return into a partially restored BIOS',
        minimum_ram=131072, source='synthetic or caller-validated payloads'))
    if probe in ('reset','logic'):
        if input_records(validate_roms(root/'references/roms/nrallyx', load_metadata())) != reset_inputs:
            raise ValueError('Contributor inputs changed during reset proof build')
        report = read_json(output / 'build.json')
        report.update(inputs=reset_inputs, source_program_sha256=PROGRAM_SHA256,
                      supplemental_execution_manifests=[digest(p / 'manifest.json') for p in execution_references],
                      reference_manifest_sha256=digest(reset_reference / 'manifest.json'),
                      source='validated contributor ROMs; '+('unverified logic candidate' if probe == 'logic' else 'reset fragment only'))
        if probe == 'logic':
            from .native_logic import profile
            entries = [(h['address'], h['length']) for h in profile()['hooks']
                       if h['kind'] not in ('nop', 'input', 'coordinate-table')]
            if video:
                from .native_video_hooks import HOOKS
                entries += [(a, n) for a, n, _, _ in HOOKS]
            report['guarded_entry_spans'] = entries
        json_write(output / 'build.json', report)
    require_ignored(root, [p for p in output.rglob('*') if p.is_file()])
    seal(output)
    return rom


def _video_sources(output, renderer, meta):
    """Adapt the shared HUD to RAM-mapper data and the reserved page-3 header."""
    config = (renderer / 'config.inc').read_text()
    config = re.sub(r'^HUD_BANK EQU .*$', 'HUD_BANK EQU 2', config, flags=re.M)
    config = re.sub(r'^HUD_DATA_BANK EQU .*$', 'HUD_DATA_BANK EQU 3', config, flags=re.M)
    (output / 'native-video-config.inc').write_text(config)
    for name in ('native-video.inc', 'native-input.inc', 'native-actors.inc', 'native-presentation.inc', 'native-solid.inc', 'native-radar.inc', 'native-hud-io.inc'):
        shutil.copyfile(PROJECT / 'src' / name, output / name)
    for name in ('hud.inc', 'hud-api.inc', 'hud-native.inc', 'hud-assets.inc', 'hud-state.inc', 'hud-raster.inc'):
        source = (PROJECT / 'src' / name).read_text()
        source = source.replace('ld ($7000),a', 'call Native_HUDMapAssets')
        source = source.replace('vdp_write 14,4', 'vdp_write 14,6')
        source = source.replace('ld a,4\n    call register', 'ld a,6\n    call register')
        if name == 'hud.inc':
            start = source.index('    ld b,14\n    ld a,7\n    call register', source.index('update_lives:'))
            end = source.index('\npoint_attribute:', start)
            source = source[:start] + '    ret\n' + source[end:]
        if name == 'hud-raster.inc':
            source = source.replace('ld hl,life_sat', 'ld hl,Native_LifeSAT')
        elif name in ('hud.inc', 'hud-api.inc'):
            source = source.replace('call register', 'call Native_HUDRegister')
            source = re.sub(r'vdp_write 14,([^\n]+)', r'ld a,\1\n    call Native_HUDSetBank', source)
            source = source.replace('out ($99),a', 'call Native_HUDAddressByte')
            source = source.replace('out ($98),a', 'call Native_HUDByte')
            source = source.replace('    otir', '    call Native_HUDOTIR')
            source = source.replace('call upload', 'call Native_HUDInitUpload')
        (output / name).write_text(source)
    for name in ('sprite-patterns.bin', 'sprite-colors.bin', 'sprite-attributes.bin',
                 'radar-patterns.bin', 'life-digits.bin', 'hud-fuel-scale.bin',
                 'hud-project-x.bin', 'hud-project-y.bin'):
        shutil.copyfile(renderer / name, output / name)
    (output / 'native-palette.bin').write_bytes(meta['palette'])
    (output / 'native-lookup.bin').write_bytes(meta['lookup'])
    (output / 'native-tile-masks.bin').write_bytes(meta['tile_masks'])
    (output / 'native-black-masks.bin').write_bytes(meta['black_masks'])


def _pack_pens(data):
    if len(data) % 4 or any(p > 3 for p in data):
        raise ValueError('Invalid 2-bit original pen indices')
    return bytes((data[i] << 6) | (data[i+1] << 4) | (data[i+2] << 2) | data[i+3]
                 for i in range(0, len(data), 4))


def resource_inventory(reference: Path, assets_path: Path) -> dict[str, bytes]:
    """Retain all original pen graphics plus the current stage/HUD working set."""
    verify_manifest(reference)
    assets = load_assets(assets_path)
    config = (reference / 'config.inc').read_text()
    def bank(name):
        match = re.search(rf'^{name} EQU (\d+)$', config, re.M)
        if not match:
            raise ValueError(f'Missing renderer resource bank: {name}')
        return int(match[1])
    first = bank('STAGE_ID_BANK')
    ids = b''.join((reference / f'bank-{n}.bin').read_bytes() for n in (first, first + 1))
    if len(ids) != 32768:
        raise ValueError('Unexpected stage ID resource size')
    resources = {f'original-{name}-2bpp': _pack_pens(data) for name, data in assets.pixels.items()}
    resources.update({
        'stage-ids': b''.join(ids[row*128:row*128+102] for row in range(174)),
        'hud-font': (reference / f'bank-{bank("HUD_BANK")}.bin').read_bytes()[:13824],
        'hud-patterns': (reference / f'bank-{bank("HUD_DATA_BANK")}.bin').read_bytes()[:4928],
        'original-lookup': bytes(assets.palette['lookup']),
        'original-rgb': bytes(v for rgb in assets.palette['rgb'] for v in rgb),
    })
    for name in ('palette', 'stage-atlas', 'sprite-patterns', 'sprite-colors', 'life-digits',
                 'hud-fuel-scale', 'hud-project-x', 'hud-project-y'):
        resources[name] = (reference / f'{name}.bin').read_bytes()
    pack_assets(resources)  # Refuse capacity overflow before creating an output.
    return resources


def build(root: Path, args) -> Path:
    """Validate local original payloads, then run only the declared loader proof."""
    root = root.resolve()
    _output(root, args.output)
    roms_path = root / 'references/roms/nrallyx'
    metadata = load_metadata()
    roms = validate_roms(roms_path, metadata)
    before = input_records(roms)
    program = program_image(roms, metadata)
    hook_specs(program)
    reference = getattr(args, 'reference', None)
    if reference is None:
        default = root / 'references/build/newrallyx.rom'
        if not default.is_file():
            raise ValueError('Supply a sealed renderer --reference bundle')
        fingerprint = digest(default)
        candidates = sorted(p.parent for p in (root / 'references/build').glob('default-*/raster-scroll.rom')
                            if digest(p) == fingerprint)
        if not candidates:
            raise ValueError('No sealed renderer bundle matches the default ROM; supply --reference')
        reference = candidates[0]
    resources = resource_inventory(Path(reference), args.assets)
    rom = build_probe(root, args.output, args.assembler, args.hz, program, resources)
    if input_records(validate_roms(roms_path, metadata)) != before:
        (rom.parent / 'manifest.json').unlink()
        raise ValueError('Contributor source ROMs changed during loader build')
    report = read_json(rom.parent / 'build.json')
    report.update(source='validated contributor ROMs; loader fixture, not gameplay', inputs=before,
                  reference_manifest_sha256=digest(Path(reference) / 'manifest.json'),
                  asset_manifest_sha256=digest(args.assets / 'manifest.json'))
    json_write(rom.parent / 'build.json', report)
    seal(rom.parent)
    return rom

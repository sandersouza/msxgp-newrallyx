"""Verified graphics inputs and V9958 timing for the first-stage renderer."""
from PIL import Image
from .screen5 import convert
from src.toolchain.scenes.bundle import read_json, verify_manifest

CPU_HZ = 3579545


def load_huds(normal, overlap):
    images = []
    for path in (normal, overlap):
        verify_manifest(path)
        layout = read_json(path/'layout.json')
        if (layout.get('status') != 'approved' or layout.get('name') != 'compact'
                or layout.get('maze') != dict(source=[12,6,212,218], destination=[0,0,200,212])
                or read_json(path/'comparison.json').get('mismatches') != 0):
            raise ValueError('Require approved compact bundles with exact reference reconstruction')
        with Image.open(path/'preview.png') as image:
            images.append(image.convert('RGB'))
    palette, scenes, colors = convert(images)
    huds = []
    for bitmap, _, _ in scenes:
        huds.append(bytes(v for y in range(212) for b in bitmap[y*128+100:(y+1)*128]
                          for v in (b >> 4, b & 15)))
    return palette, huds, colors


def background_zero(palette, pixels, *, index=11):
    """Permute two palette entries; never merge colors or change displayed RGB."""
    translation = bytes(index if i==0 else 0 if i==index else i for i in range(256))
    result = bytearray(palette)
    result[:2],result[2*index:2*index+2] = result[2*index:2*index+2],result[:2]
    return bytes(result),[bytes(data).translate(translation) for data in pixels]


def video_timing(hz):
    """V9958 non-interlaced timing at the selected machine's fixed clock."""
    if hz not in (50,60):
        raise ValueError('Refresh mode must be 50 or 60 Hz')
    lines = 313 if hz==50 else 262
    cycles = lines*228
    return dict(nominal_hz=hz,vdp_r9=0x82 if hz==50 else 0x80,
                lines=lines,cpu_cycles=cycles,frame_seconds=cycles/CPU_HZ)


def native_clock(hz, logic_hz=None):
    """Keep original ticks by default; permit an explicit slower test clock."""
    period=.0165 if logic_hz is None else 1/logic_hz
    frame=video_timing(hz)['frame_seconds']
    if not frame/2<period<=frame or period<.0165:
        raise ValueError('Native test clock must fit one or two ticks per refresh and cannot exceed the original speed')
    return dict(tick_seconds=period,rate=round((frame/period-1)*65536),
                original_tick_seconds=.0165,speed_ratio=.0165/period,
                adapted=logic_hz is not None)


def sources(args):
    palette, huds, colors = load_huds(args.normal, args.overlap)
    palette, huds = background_zero(palette, huds)
    # Captures supply validated enemy fixtures; geometry comes from stage_one.
    scenes = [dict(number=number, path=args.captures/f'frame-{number:05d}')
              for number in (2200, 2410, 2411, 2760, 2761)]
    return palette, huds, colors, scenes

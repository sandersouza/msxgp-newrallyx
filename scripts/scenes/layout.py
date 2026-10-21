"""Compact reference-input geometry and composition."""
from dataclasses import dataclass
from PIL import Image
from .render import Frame, Object

SOURCES = dict(score=[224,0,288,32],fuel=[224,56,288,72],
               radar=[224,80,288,192],lives=[224,192,288,208],round=[224,208,288,224])


@dataclass
class Layout:
    name: str
    maze: dict
    blocks: dict


@dataclass
class Preview:
    image: Image.Image
    background: bytes
    indices: bytes
    shadow: bytes
    objects: list[Object]
    transforms: dict


def compact_layout():
    """Reference-input geometry consumed by the current renderer build."""
    destinations = dict(score=[200,0,256,32],fuel=[200,40,256,56],
                        radar=[200,64,256,176],lives=[200,180,256,196],round=[200,196,256,212])
    return Layout('compact',dict(source=[12,6,212,218],destination=[0,0,200,212]),
                  {name:dict(source=source.copy(),destination=destinations[name])
                   for name,source in SOURCES.items()})


def compose(frame: Frame, capture, assets) -> Preview:
    """Build the reference input without changing the captured game state."""
    if capture.state['registers']['flip']:
        raise ValueError('Compact inputs require upright cabinet captures')
    from .compact import compose_compact
    return compose_compact(frame,capture,compact_layout(),assets)

"""Exact native RGB comparison with deterministic diagnostic regions."""
from PIL import Image, ImageChops


def compare(reference: Image.Image, actual: Image.Image) -> dict:
    if reference.size != (288,224) or actual.size != reference.size:
        raise ValueError('Comparison requires two native 288x224 images')
    difference=ImageChops.difference(reference.convert('RGB'),actual.convert('RGB'))
    raw=difference.tobytes()
    mismatches=0; regions=dict(maze=0,hud=0)
    for index in range(288*224):
        if any(raw[index*3:index*3+3]):
            mismatches+=1
            regions['maze' if index%288<224 else 'hud']+=1
    bounds=difference.getbbox()
    return dict(region=[0,0,288,224],tolerance=0,mismatches=mismatches,
        bounds=list(bounds) if bounds else None,max_channel_difference=max(raw),regions=regions)

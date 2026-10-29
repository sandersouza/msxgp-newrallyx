"""Preview an additional SCREEN4 concession without changing active builds."""
import json
from pathlib import Path
from PIL import Image,ImageDraw
from game_build import inputs
from prepare import ROOT
from scripts.msx import death
from scripts.msx.raster_scroll import palette_rgb


from effect_codec import adapt as propose


def main():
    program,video,cells,pairs,assets=inputs(ROOT)
    # palette from the accepted laboratory, before car-specific index permutation.
    palette=(ROOT/'references/experiments/fixed-hud/palette.bin').read_bytes()
    rgb=palette_rgb(palette)
    sources={'Explosion':death.pixels(death.acquire(ROOT)[0],assets,palette),
             'Smoke':death.pixels([(program[0xfec]+i,program[0xff4]) for i in range(9)],assets,palette)}
    image=Image.new('RGB',(260,275),(30,30,30));draw=ImageDraw.Draw(image)
    draw.text((10,5),'Original',fill='white');draw.text((140,5),'SCREEN4 proposal',fill='white')
    report={}
    for i,(name,tiles) in enumerate(sources.items()):
        adapted,changed=propose(tiles,palette)
        report[name.lower()]=dict(changed_pixels=changed,total_pixels=576,
                                 percentage=100*changed/576,dimensions=[24,24])
        draw.text((10,25+i*125),f'{name}: {changed}/576 pixels',fill='white')
        for j,source in enumerate((tiles,adapted)):
            bitmap=Image.new('RGB',(24,24))
            bitmap.putdata([rgb[source[(y//8)*3+x//8][(y%8)*8+x%8]] for y in range(24) for x in range(24)])
            image.paste(bitmap.resize((96,96),Image.Resampling.NEAREST),(10+j*130,45+i*125))
    out=ROOT/'references/experiments/stage-one-effect-proposal'
    out.mkdir(parents=True,exist_ok=True)
    image.save(out/'effects-proposal.png')
    (out/'proposal.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    print(out/'effects-proposal.png')

if __name__=='__main__':main()

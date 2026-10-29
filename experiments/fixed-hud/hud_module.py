"""Selected HUD include metadata and original authored4x5 glyphs (no game assets)."""
import os,re
from pathlib import Path
FONT={
 'F':(15,8,14,8,8),'U':(9,9,9,9,6),'E':(15,8,14,8,15),'L':(8,8,8,8,15),
 'R':(14,9,14,10,9),'O':(6,9,9,9,6),'N':(9,13,15,11,9),'D':(14,9,9,9,14),
 '0':(6,9,9,9,6),'1':(2,6,2,2,7),'2':(14,1,6,8,15),'3':(14,1,6,1,14),
 '4':(9,9,15,1,1),'5':(15,8,14,1,14),'6':(7,8,14,9,6),'7':(15,1,2,4,4),
 '8':(6,9,6,9,6),'9':(6,9,7,1,14),' ':(0,0,0,0,0)}
YELLOW_TICKS=(6,12,18,29,35,41)
CLASSIC_YELLOW_TICKS=(9,14,18,29,34,39)
CLASSIC_RED_MARKS={(0,58),(1,58),(23,57),(23,58),(46,58),(47,58)}
RED_MARKS={(x,y) for x in (0,1,46,47) for y in (57,58)}|{(x,y) for x in (23,24) for y in (56,57,58)}

def selected(name=None):
    name=name or os.environ.get('NRX_HUD_VARIANT','compact')
    if name not in ('classic','compact'):raise ValueError('HUD_VARIANT must be classic or compact')
    source=Path(__file__).with_name('hud')/f'{name}.inc'
    small=bool(int(re.search(r'HUD_SMALL_ROUND EQU (\d)',source.read_text())[1]))
    return dict(name=name,include=f'hud/{name}.inc',small_round=small,symmetric_gauge=int(re.search(r'HUD_GAUGE_VERSION EQU (\d)',source.read_text())[1])==2)

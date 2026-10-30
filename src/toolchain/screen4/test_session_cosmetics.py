"""Full-session display contracts; older laboratory defaults stay unchanged."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import unittest
from game_hud import display_keys,prepare_reference,sprite_pattern
from hud import compose_hud
from hud_module import FONT,RED_MARKS,YELLOW_TICKS,selected

def native(value):
    d=bytes(map(int,f'{value:08d}'));return d[4:]+d[:4]

class Cosmetics(unittest.TestCase):
    def test_scores_hide_only_leading_zeroes_and_keep_saturation(self):
        for value,wanted in ((0,[0xaa,0xaa,0xa0]),(7,[0xaa,0xaa,0xa7]),(17,[0xaa,0xaa,0x17]),
             (100,[0xaa,0xa1,0]),(20000,[0xa2,0,0]),(999999,[0x99]*3),(1000000,[0x99]*3)):
            self.assertEqual(display_keys(native(value),native(value),2,5,60,arcade=True)[:6],wanted*2)
        self.assertEqual(display_keys(native(0),native(0),2,5,60)[:6],[0]*6)

    def test_fuel_remaining_is_anchored_right_and_ticks_survive_empty(self):
        digits=bytes(88);life=bytes(64)
        for fuel in range(61):
            keys=display_keys(native(0),native(0),2,1,fuel,arcade=True)
            sat,pg=prepare_reference(digits,life,keys,0,arcade=True)
            self.assertEqual(list(sat[44::4]),[56]*3)
            points=set()
            for slot in range(11,14):
                p=pg[slot*32:(slot+1)*32]
                for y in range(16):
                    for x in range(16):
                        if p[(x//8)*16+y]&(128>>(x%8)):points.add(((slot-11)*16+x,57+y))
            width=fuel*48//60
            expected={(x,y) for y in range(60,64) for x in range(48-width,48)}
            expected|={(x,58) for x in YELLOW_TICKS}
            self.assertEqual(points,expected)

    def test_small_centered_fuel_and_red_gauge_marks(self):
        image=compose_hud(lambda c:bytes([1])*64,bytes(256),[],dict(black=0,white=1,yellow=2,blue=3,red=4,cyan=5,green=6),arcade=True)
        green={(x,y) for y in range(48,56) for x in range(48) if image[y*48+x]==6}
        self.assertEqual((min(x for x,y in green),max(x for x,y in green)),(14,32))
        self.assertEqual((min(y for x,y in green),max(y for x,y in green)),(48,52))
        red={(x,y) for y in range(56,60) for x in range(48) if image[y*48+x]==4}
        self.assertEqual(red,RED_MARKS)

    def test_gauge_symmetry_edges_and_compact_round(self):
        self.assertEqual(RED_MARKS,{(47-x,y) for x,y in RED_MARKS})
        # Uniform ideal centers are0.5+5.75*k; nearest integer yellow dots
        # give balanced5.5/6/6/5.5 gaps on each side of the2px center.
        self.assertTrue(all(abs(x-(.5+5.75*k))<=.25 for k,x in zip((1,2,3,5,6,7),YELLOW_TICKS)))
        self.assertEqual(set(YELLOW_TICKS),{47-x for x in YELLOW_TICKS})
        self.assertEqual({x for x,y in RED_MARKS if y==56},{23,24})
        for name,small in (('classic',False),('compact',True)):
            self.assertEqual(selected(name)['small_round'],small)
        for rnd in (1,9,10,99,100):
            image=compose_hud(lambda c:bytes(64),bytes(256),[],dict(black=0,white=1,yellow=2,blue=3,red=4,cyan=5,green=6),arcade=True,small_round=True,round_number=rnd)
            expected={(i*5+x,204+y) for i,c in enumerate('ROUND') for y,row in enumerate(FONT[c]) for x in range(4) if row&(8>>x)}
            value=str(min(rnd,99));left=48-(len(value)*5-1)
            expected|={(left+i*5+x,204+y) for i,c in enumerate(value) for y,row in enumerate(FONT[c]) for x in range(4) if row&(8>>x)}
            self.assertEqual({(x,y) for y in range(204,212) for x in range(48) if image[y*48+x]==1},expected)

if __name__=='__main__' :unittest.main()

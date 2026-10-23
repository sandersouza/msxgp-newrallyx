"""Synthetic life-boundary fixtures, linker guards and keyboard-route isolation."""
import unittest
from scripts.msx.lives_verify import cases_for
from scripts.msx.lives_route_verify import paths_for
from scripts.msx.player import relocate


class LivesTests(unittest.TestCase):
    def test_oracle_covers_final_life_ordinal_reset_and_fractional_refill(self):
        cases=cases_for()
        self.assertEqual({c[0] for c in cases},{1,2,3,9})
        self.assertTrue(any(c[1]!=c[2] for c in cases))
        self.assertEqual({c[3]+10*c[4] for c in cases},{0,1,599,600})

    def test_linker_stops_before_graphics_two_player_and_game_over_dispatchers(self):
        rom=bytearray(16384)
        rom[0x18e1:0x18e4]=bytes((0x2a,0x88,0x89))
        linked,patches=relocate(bytes(rom),'ld hl,(08988h) ;18e1 2a 88 89 ',lives=True)
        self.assertEqual(linked[0x18e1:0x18e4],bytes((0x2a,0x88,0xe9)))
        self.assertTrue(all(linked[a]==0xc9 for a in (0x908,0x18e8,0x73d,0x1bcd)))
        self.assertEqual(linked[0x18e9],255)

    def test_routes_reach_each_intended_flag_before_the_rock_and_avoid_other_flags(self):
        positions=[(2+i,10+i) for i in range(8)]+[(27,7),(13,28)]
        records=[dict(address=0x9800+y*32+x,kind=1 if i<8 else 4 if i==8 else 2)
                 for i,(x,y) in enumerate(positions)]
        board=bytearray(32*56);rock=(15,49);board[rock[1]*32+rock[0]]=3
        paths,special,normal=paths_for(board,records,rock)
        for i,p in enumerate(paths):
            self.assertEqual((p[0],p[-1]),((15,50),rock))
            self.assertNotIn(rock,p[:-1])
            self.assertTrue(all(abs(x-a)+abs(y-b)==1 for (a,b),(x,y) in zip(p,p[1:])))
            allowed={special} if i==0 else {special,normal}
            self.assertTrue(all(positions[j] not in p for j in range(10) if j not in allowed))
        self.assertIn(positions[special],paths[0]);self.assertIn(positions[normal],paths[1])

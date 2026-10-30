"""Display boundaries for the compact full-game HUD, using synthetic glyphs."""
import unittest
from tests.test_raster_scroll import fixture
from src.toolchain.msx.raster_scroll import header,index_for,player_label_patterns
from src.toolchain.msx.full_hud import (HEADER_LEFT,ROUND_X,score_text,round_text,
    credit_digit,infinity_pixels)


class FullHUDTests(unittest.TestCase):
    def test_visible_digits_and_display_only_limits(self):
        self.assertEqual(score_text(12345678),'2345678')
        self.assertEqual(score_text(0),'0000000')
        self.assertEqual([credit_digit(v) for v in (0,1,9,10,99,255)],[0,1,9,9,9,9])
        self.assertEqual(round_text(99),'99')
        self.assertEqual(round_text(100),'\u221e ')
        self.assertEqual(round_text(255),'\u221e ')

    def test_score_updates_stay_inside_seven_cells_and_viewport_alignment(self):
        palette,assets=fixture();base=header(assets,palette,full_game=True)
        black=index_for(palette,(0,0,0))
        self.assertEqual(HEADER_LEFT,8)
        for y in range(8):self.assertEqual(base[y*256:y*256+HEADER_LEFT],bytes([black])*8)
        for field,bounds in [('score',(136,192)),('high',(32,88))]:
            changed=header(assets,palette,full_game=True,**{field:1234567})
            xs=[i%256 for i,(a,b) in enumerate(zip(base,changed)) if a!=b]
            self.assertTrue(xs)
            self.assertTrue(all(bounds[0]<=x<bounds[1] for x in xs))
        self.assertEqual(header(assets,palette,score=12345678,full_game=True),
                         header(assets,palette,score=2345678,full_game=True))
        self.assertEqual(len(player_label_patterns(assets,palette,full_game=True)),64)

    def test_number_cells_immediately_follow_the_label_colons(self):
        from src.toolchain.msx.full_hud import HIGH_FIELD_X,SCORE_FIELD_X,PLAYER_LABEL_X
        self.assertEqual(HIGH_FIELD_X+8,HEADER_LEFT+len('HI:')*8)
        self.assertEqual(SCORE_FIELD_X+8,PLAYER_LABEL_X+len('1UP:')*8)

    def test_infinity_fills_the_two_round_cells_at_the_viewport_right_edge(self):
        palette,assets=fixture();image=header(assets,palette,full_game=True,round_=100)
        self.assertEqual(image,header(assets,palette,full_game=True,round_=255))
        white=index_for(palette,(222,222,222));black=index_for(palette,(0,0,0))
        pixels=bytes(image[y*256+ROUND_X+x] for y in range(8) for x in range(16))
        self.assertEqual(pixels,bytes(white if v else black for v in infinity_pixels()))
        self.assertNotEqual(image,header(assets,palette,full_game=True,round_=99))

import unittest
from scripts.msx.outline_flicker import resources,order
from scripts.msx.sprite_flicker import selected


class OutlineFlickerTests(unittest.TestCase):
    def test_black_ink_is_independent_without_losing_or_adding_opaque_pixels(self):
        image=bytes((0,3,9,11)[(x+2*y)%4] for y in range(16) for x in range(16))
        masks,colors=resources(image*12)
        for pose in range(12):
            for shift in (0,1):
                at=pose*128+shift*64
                for y in range(16):
                    for x in range(16):
                        p=image[(y-shift)*16+x] if y>=shift else 0
                        address=(x//8)*16+y;bit=128>>(x%8)
                        self.assertEqual(bool(masks[at+address]&bit),p in (3,9))
                        self.assertEqual(bool(masks[at+32+address]&bit),p==11)
        self.assertEqual(colors,bytes([35])*192)

    def test_bodies_survive_all_scroll_phases_even_when_outlines_and_radar_overflow(self):
        for phase in range(4):
            indices=order(phase)
            self.assertEqual(indices[:3],[17,19,21])
            self.assertEqual(indices[14:17],[14,15,16])
            self.assertEqual(sorted(indices),list(range(24)))
            for scroll in range(256):
                ay=(scroll+63)&255
                if ay==216:ay-=1
                attrs=bytes(v for index in indices for v in (ay,index*8,0,0))
                chosen,count=selected(attrs,scroll,64)
                self.assertEqual(count,24)
                self.assertTrue({0,1,2}<=set(s for s,dy in chosen))
            if not phase&1:self.assertTrue(all(indices.index(i)<indices.index(0) for i in (18,20,22)))

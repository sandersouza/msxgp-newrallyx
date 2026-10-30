import random
import unittest
from src.toolchain.msx.shared_sprite_cache import assign
from src.toolchain.msx.player import projected_masks


class SharedSpriteCacheTests(unittest.TestCase):
    def test_later_matching_requests_survive_earlier_new_masks(self):
        keys=list(range(12));result=assign(keys,set(range(7)),[20,21,22,23,24,5,6])
        self.assertEqual(result['slots'][-2:],[5,6])
        self.assertLessEqual(len(result['vblank']),2)

    def test_vblank_never_needs_more_than_two_complete_masks(self):
        rng=random.Random(12030)
        keys=list(range(12))
        for _ in range(3000):
            front=set(rng.sample(range(12),rng.randrange(8)))
            requests=[rng.randrange(30) for _ in range(rng.randrange(8))]
            result=assign(keys,front,requests)
            self.assertLessEqual(len(result['vblank']),2)
            self.assertTrue(result['preload'].isdisjoint(front))
            self.assertEqual([result['keys'][i] for i in result['slots']],requests)
            keys=result['keys']

    def test_zero_ec_projection_preserves_every_visible_source_pixel(self):
        rng=random.Random(16)
        masks=bytes(rng.randrange(256) for _ in range(64))
        for x in range(-7,16):
            clip=max(0,8-x);data=projected_masks(masks,clip)
            for plane in range(2):
                for y in range(16):
                    def bit(blob,p):
                        return (blob[plane*32+(p//8)*16+y]>>(7-p%8))&1
                    expected={x+p for p in range(16) if x+p>=8 and bit(masks,p)}
                    actual={max(0,x)+p for p in range(16) if bit(data,p)}
                    self.assertEqual(actual,expected)

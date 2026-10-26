"""Synthetic topology and gameplay contracts for the MSX navigation policy."""
import unittest
from scripts.msx.enemy_navigation import exits,choose,DIRECTIONS


class EnemyNavigationTests(unittest.TestCase):
    def test_all_small_wall_patterns_have_only_reciprocal_open_exits(self):
        for mask in range(512):
            walls=bytes(bool(mask&(1<<i)) for i in range(9));grid=exits(walls,3,3)
            for y in range(3):
                for x in range(3):
                    for d,(dx,dy) in enumerate(DIRECTIONS):
                        nx,ny=x+dx,y+dy
                        expected=not walls[y*3+x] and 0<=nx<3 and 0<=ny<3 and not walls[ny*3+nx]
                        self.assertEqual(bool(grid[y*3+x]&(1<<d)),expected)
                        if expected:self.assertTrue(grid[ny*3+nx]&(1<<((d+2)&3)))

    def test_steering_never_selects_a_wall_or_an_unnecessary_reversal(self):
        for mask in range(1,16):
            for heading in range(4):
                for dx,dy in ((7,2),(-7,2),(2,7),(2,-7),(0,0),(-7,-7)):
                    for actor in range(7):
                        d=choose(mask,heading,dx,dy,actor)
                        self.assertTrue(mask&(1<<d))
                        if mask&~(1<<((heading+2)&3)):self.assertNotEqual(d,(heading+2)&3)

    def test_dead_end_and_distinct_axis_preferences(self):
        self.assertEqual(choose(4,0,5,5,0),2)
        self.assertEqual(choose(15,1,7,3,0),1)
        self.assertEqual(choose(15,1,7,3,1),2)
        self.assertIsNone(choose(0,0,1,1,0))


if __name__=='__main__':unittest.main()

import unittest
from PIL import Image
from src.toolchain.scenes.compare import compare


class CompareTests(unittest.TestCase):
    def test_equal_and_one_pixel(self):
        reference=Image.new('RGB',(288,224))
        result=compare(reference,reference.copy())
        self.assertEqual(result['mismatches'],0)
        self.assertIsNone(result['bounds'])
        changed=reference.copy(); changed.putpixel((230,10),(2,8,1))
        result=compare(reference,changed)
        self.assertEqual(result['mismatches'],1)
        self.assertEqual(result['bounds'],[230,10,231,11])
        self.assertEqual(result['max_channel_difference'],8)
        self.assertEqual(result['regions'],{'maze':0,'hud':1})

    def test_wrong_size_rejected(self):
        with self.assertRaises(ValueError):
            compare(Image.new('RGB',(288,224)),Image.new('RGB',(288,223)))

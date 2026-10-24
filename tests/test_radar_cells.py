"""Independent capture checks for explicitly quantized radar markers."""
import unittest
from scripts.msx.radar_cells import published_cells


class RadarMarkerCaptureTests(unittest.TestCase):
    def fixture(self):
        ram=bytearray(12288)
        for at,point in ((0x93,(3,9)),(0x95,(255,255)),(0x638,(46,31))):
            ram[at:at+2]=bytes(point)
        ram[0xf00:0xf06]=bytes((2,8,255,255,46,30))
        style=dict(radar_marker_quantum=2,radar_marker_state_address=0xcf60,
                   radar_flag_state_address=0xcfa8)
        return ram,style

    def test_snap_bound_and_hidden_sentinel_are_checked_against_canonical_points(self):
        ram,style=self.fixture()
        self.assertEqual(len(published_cells(ram,[],style)),12)
        ram[0xf02]=254
        with self.assertRaisesRegex(ValueError,'quantization bound'):
            published_cells(ram,[],style)

    def test_wrong_snap_direction_is_rejected_even_when_published_cells_are_valid(self):
        ram,style=self.fixture();ram[0xf01]=10
        with self.assertRaisesRegex(ValueError,'quantization bound'):
            published_cells(ram,[],style)

    def test_legacy_capture_contract_remains_unchanged(self):
        ram,style=self.fixture();style.pop('radar_marker_quantum')
        ram[0xf00:0xf06]=bytes(6)
        self.assertEqual(len(published_cells(ram,[],style)),12)

    def test_separate_player_never_enters_the_composite_cells(self):
        ram,style=self.fixture();style['radar_player_sprite']=True
        for cell in range(12):ram[0xf60+cell*6:0xf62+cell*6]=b'\xff\xff'
        self.assertEqual(len(published_cells(ram,[],style)),12)
        ram[0xf60:0xf62]=bytes((2,8))
        with self.assertRaisesRegex(ValueError,'Separate player leaked'):
            published_cells(ram,[],style)

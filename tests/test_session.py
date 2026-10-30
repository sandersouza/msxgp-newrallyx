"""Synthetic coverage for original-size session font and bank reservations."""
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from src.toolchain.msx.session import resources,CODE_OFFSET
from src.toolchain.msx.screen5 import packed


class SessionResourceTests(unittest.TestCase):
    def test_lucky_restore_oracle_rejects_a_gauge_starved_after_native_refill(self):
        from src.toolchain.msx.completion_route_verify import verify_fuel_restoration
        with TemporaryDirectory() as folder:
            path=Path(folder)/'fuel.tsv'
            rows=['0 0.0 3 0 0 0 0 3']
            rows += [f'{i} 0.1 0 53 2 29 0 3' for i in range(1,98)]
            path.write_text('\n'.join(rows))
            with self.assertRaisesRegex(ValueError,'promptly'):
                verify_fuel_restoration(path)
            rows[2]='2 0.2 0 53 2 29 29 0'
            path.write_text('\n'.join(rows))
            self.assertEqual(verify_fuel_restoration(path)['latency_refreshes'],1)

    def test_blink_oracle_requires_both_s_phases_and_steady_ordinary_flags(self):
        from src.toolchain.msx.hud_alerts_verify import verify_blink
        flags=[(3,3),(20,3)]
        rows=[]
        for age in range(1,129):
            masks=bytearray(12);masks[0]=1-(age//32&1);masks[1]=1
            rows.append((str(age),str(age),masks.hex()))
        self.assertGreater(verify_blink(rows,[(0,0)],flags,0,32),16)
        broken=list(rows)
        masks=bytearray.fromhex(broken[60][2]);masks[1]=0
        broken[60]=(*broken[60][:2],masks.hex())
        with self.assertRaisesRegex(ValueError,'ordinary'):
            verify_blink(broken,[(0,0)],flags,0,32)
        with self.assertRaisesRegex(ValueError,'budget'):
            verify_blink([(age,clock,'010100000000000000000000') for age,clock,_ in rows],[(0,0)],flags,0,32)

    def test_header_trace_rejects_the_lucky_bonus_missed_frame(self):
        from src.toolchain.msx.completion_route_verify import verify_header_reservations
        with TemporaryDirectory() as folder:
            path=Path(folder)/'raster.tsv'
            path.write_text('2 50 navigate 19.3203 0 0\n4 50 navigate 19.3466 0 0\n')
            with self.assertRaisesRegex(ValueError,'missed'):
                verify_header_reservations(path,.0199366)
            path.write_text('2 50 navigate 19.3203 0 0\n4 50 navigate 19.3267 0 0\n')
            result=verify_header_reservations(path,.0199366)
            self.assertEqual(result['refreshes'],1)
            self.assertAlmostEqual(result['maximum_ms'],6.4)

    def test_digit_font_preserves_all_original_pixels_at_one_to_one_scale(self):
        pixels=bytes(int((x+2*y)%8==code%8) for code in range(256) for y in range(8) for x in range(8))
        lookup=[0]*256;lookup[38*4+1]=15
        assets=SimpleNamespace(pixels={'tiles':pixels},palette={'lookup':lookup})
        first,second=resources(assets,2,15)
        self.assertEqual((len(first),len(second)),(16384,16384))
        for digit in range(10):
            expected=packed(bytes(15 if p else 2 for p in pixels[digit*64:(digit+1)*64]))
            self.assertEqual(second[0x3600+digit*32:0x3620+digit*32],expected)
        self.assertEqual(second[CODE_OFFSET:],bytes([255])*(16384-CODE_OFFSET))

    def test_menu_background_and_three_status_rows_fit_reserved_original_size(self):
        assets=SimpleNamespace(pixels={'tiles':bytes(256*64)},palette={'lookup':[0]*256})
        first,second=resources(assets,3,15)
        self.assertEqual(first+second[:0x2a00],bytes([0x33])*(256*212//2))
        self.assertEqual(second[0x2a00:0x3600],bytes([0x33])*(3*256*8//2))

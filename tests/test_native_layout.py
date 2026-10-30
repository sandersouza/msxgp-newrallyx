"""CPU and asset capacity checks use synthetic data only."""
import unittest

from src.toolchain.msx.native_layout import Region, pack_assets, validate_layout


class NativeLayoutTests(unittest.TestCase):
    def test_adjacent_allocations_and_page_end_are_valid(self):
        validate_layout((Region('program', 0, 0x4000),
                         Region('renderer', 0x4000, 0x8000),
                         Region('video', 0x8000, 0x9000),
                         Region('host', 0xc000, 0xc473),
                         Region('buffer', 0xc473, 0xc500),
                         Region('stack', 0xf380, 0x10000)))

    def test_overlap_with_game_or_host_reservations_is_rejected(self):
        for protected, proposed in (
                (Region('video', 0x8000, 0x9000), Region('scratch', 0x83ff, 0x8401)),
                (Region('host', 0xc000, 0xc473), Region('buffer', 0xc472, 0xc500)),
                (Region('vectors', 0xd000, 0xd101), Region('new', 0xd100, 0xd102))):
            with self.subTest(proposed=proposed), self.assertRaisesRegex(ValueError, 'overlap'):
                validate_layout((proposed, protected))

    def test_duplicate_names_and_invalid_ranges_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'name'):
            validate_layout((Region('same', 0x4000, 0x4010),
                             Region('same', 0xc000, 0xc010)))
        for region in (Region('', 0, 1), Region('x', -1, 1), Region('x', 0, 0),
                       Region('x', 4, 3), Region('x', 0xffff, 0x10001),
                       Region('x', True, 2)):
            with self.subTest(region=region), self.assertRaises(ValueError):
                validate_layout((region,))

    def test_resident_renderer_cannot_spill_into_game_window(self):
        with self.assertRaisesRegex(ValueError, 'page'):
            validate_layout((Region('renderer', 0x4000, 0x8001),))

    def test_asset_order_is_deterministic_and_padding_is_zero(self):
        packed, index = pack_assets({'z': b'XYZ', 'a': b'AB'})
        self.assertEqual(index, {'a': (0, 2), 'z': (2, 3)})
        self.assertEqual(packed, b'ABXYZ' + bytes(65531))
        self.assertEqual(pack_assets({'a': b'AB', 'z': b'XYZ'}), (packed, index))

    def test_exact_capacity_and_empty_resources_are_safe(self):
        data = b'x' * 65536
        self.assertEqual(pack_assets({'full': data}), (data, {'full': (0, 65536)}))
        self.assertEqual(pack_assets({}), (bytes(65536), {}))

    def test_overflow_is_rejected_without_truncating_inputs(self):
        resources = {'full': b'x' * 65536, 'extra': b'y'}
        before = resources.copy()
        with self.assertRaisesRegex(ValueError, 'capacity'):
            pack_assets(resources)
        self.assertEqual(resources, before)

    def test_asset_capacity_is_bounded_to_whole_mapper_segments(self):
        for capacity in (0, -1, 16383, 65537, 81920, True):
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                pack_assets({}, capacity)
        self.assertEqual(pack_assets({'x': b'a'}, 16384),
                         (b'a' + bytes(16383), {'x': (0, 1)}))

    def test_invalid_resource_names_or_payloads_are_rejected(self):
        for resources in ({'': b'x'}, {4: b'x'}, {'x': 'data'}, {'x': bytearray(b'x')}):
            with self.subTest(resources=resources), self.assertRaises(ValueError):
                pack_assets(resources)


if __name__ == '__main__':
    unittest.main()

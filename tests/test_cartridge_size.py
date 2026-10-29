"""Synthetic accounting guards; no proprietary cartridge fixture is required."""
import hashlib
import unittest

from scripts.msx.cartridge_size import inventory, PREFERRED_BYTES, MAXIMUM_BYTES


class CartridgeSizeTests(unittest.TestCase):
    def test_partial_bank_is_accounted_without_assuming_padding(self):
        result = inventory(b'abcde', bank_bytes=4)
        self.assertEqual(result['accounted_bytes'], 5)
        self.assertEqual(result['bank_count'], 2)
        self.assertEqual(result['partial_last_bank_bytes'], 1)
        self.assertEqual(result['banks'][1]['offset'], 4)
        self.assertFalse(result['banks'][1]['complete'])
        self.assertEqual(result['sha256'], hashlib.sha256(b'abcde').hexdigest())

    def test_only_exact_complete_banks_are_duplicate_candidates(self):
        result = inventory(b'abcdabcdabc', bank_bytes=4)
        self.assertEqual(result['duplicate_complete_bank_bytes'], 4)
        self.assertEqual(result['duplicate_groups'][0]['canonical'], 0)
        self.assertEqual(result['duplicate_groups'][0]['duplicates'], [1])
        self.assertEqual(result['accounted_bytes'], 11)

    def test_fill_tails_are_reported_without_truncating_data(self):
        result = inventory(b'x\xff\xff\xffy\0\0\0', bank_bytes=4)
        self.assertEqual(result['ff_tail_candidate_bytes'], 3)
        self.assertEqual(result['zero_tail_candidate_bytes'], 3)
        self.assertEqual(result['bytes'], 8)
        self.assertEqual(result['accounted_bytes'], 8)

    def test_capacity_boundaries_are_exact_binary_units(self):
        for size in (PREFERRED_BYTES, MAXIMUM_BYTES, MAXIMUM_BYTES+1):
            with self.subTest(size=size):
                result = inventory(bytes(size))
                self.assertEqual(result['within_preferred'], size<=PREFERRED_BYTES)
                self.assertEqual(result['within_maximum'], size<=MAXIMUM_BYTES)
                self.assertEqual(result['maximum_headroom_bytes'], MAXIMUM_BYTES-size)

    def test_invalid_bank_sizes_are_rejected(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                inventory(b'AB', bank_bytes=value)


if __name__ == '__main__':
    unittest.main()

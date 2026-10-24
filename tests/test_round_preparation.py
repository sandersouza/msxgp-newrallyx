"""Synthetic pointer and optional-linker contracts for round preparation."""
import unittest

from scripts.msx.player import relocate
from scripts.msx.round_prepare_verify import relocated_seed


class RoundPreparationTests(unittest.TestCase):
    def seed(self):
        seed = bytearray(4096)
        for at in range(0x988,0x99e,2):
            seed[at:at+2] = (0x8100+at%16).to_bytes(2,'little')
        for at in (0x1b3,0x1b9,0x2d2):
            seed[at:at+2] = (0x2300).to_bytes(2,'little')
        seed[0x28f] = 0x31
        seed[0x99e:0x9a0] = (0xa000).to_bytes(2,'little')
        seed[0x1c8:0x1ca] = (0x9876).to_bytes(2,'little')
        return seed

    def test_relocates_declared_pointers_and_preserves_object_identifiers(self):
        seed = self.seed(); native = relocated_seed(seed)
        self.assertEqual(native[0x988:0x98a], (0xe108).to_bytes(2,'little'))
        self.assertEqual(native[0x1b3:0x1b5], (0xa300).to_bytes(2,'little'))
        self.assertEqual(native[0x28f], 0xb1)
        self.assertEqual(native[0x99e:0x9a0], seed[0x99e:0x9a0])
        self.assertEqual(native[0x1c8:0x1ca], seed[0x1c8:0x1ca])

    def test_rejects_wrong_pointer_domains_and_truncated_seed(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            relocated_seed(bytes(12))
        seed = self.seed(); seed[0x988:0x98a] = (0xa000).to_bytes(2,'little')
        with self.assertRaisesRegex(ValueError, 'RAM pointer'):
            relocated_seed(seed)
        seed = self.seed(); seed[0x2d2:0x2d4] = (0x9000).to_bytes(2,'little')
        with self.assertRaisesRegex(ValueError, 'ROM pointer'):
            relocated_seed(seed)

    def test_round_component_is_opt_in_and_guards_hardware_boundary(self):
        program = bytearray(16384)
        program[0x1b2f:0x1b34] = bytes((0xf6,0x30,0x32,0x8f,0x82))
        program[0x08d4:0x08d9] = bytes((0x3e,3,0x32,0x81,0xa1))
        program[0x13da:0x13dd] = bytes((0x11,0x17,0x14))
        program[0x3100] = 0x77
        listing = 'ld de,01417h ;13da 11 17 14 '
        plain,_ = relocate(program, listing, parameters=True)
        linked,patches = relocate(program, listing, parameters=True, round_preparation=True)
        self.assertEqual((plain[0x08d4],plain[0x3100]), (255,255))
        self.assertEqual((linked[0x08d4],linked[0x3100]), (0xc9,0x77))
        self.assertEqual(linked[0x13da:0x13dd], bytes((0x11,0x17,0x94)))
        self.assertTrue(any(p.get('kind')=='round-preparation-return-before-hardware' for p in patches))
        program[0x08d4] = 0
        with self.assertRaisesRegex(ValueError, 'hardware boundary'):
            relocate(program, listing, parameters=True, round_preparation=True)

    def test_component_requires_parameter_routine(self):
        with self.assertRaisesRegex(ValueError, 'parameter dispatch'):
            relocate(bytes(16384), '', round_preparation=True)


if __name__ == '__main__':
    unittest.main()

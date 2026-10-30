"""Synthetic instruction operands for the isolated original sound overlay."""
import unittest

from src.toolchain.msx.audio_native import map_address, relocate


class AudioNativeTests(unittest.TestCase):
    def test_sound_workspace_and_hardware_do_not_alias_presentation_code(self):
        self.assertEqual(map_address(0x8a00), 0x3800)
        self.assertEqual(map_address(0x8bff), 0x39ff)
        self.assertEqual(map_address(0x89f4), 0xe9f4)
        self.assertEqual(map_address(0x8069), 0xe069)
        self.assertEqual(map_address(0xa11f), 0x3a1f)
        self.assertEqual(map_address(0xa180), 0x3a20)
        self.assertEqual(map_address(0x2b58), 0x2b58)
        with self.assertRaises(ValueError):
            map_address(0xa181)

    def test_relocation_leaves_control_flow_and_frequency_constants_unchanged(self):
        program = bytearray(16384)
        rows = [(0x2580, bytes.fromhex('3a008a'), 'ld a,(08a00h)'),
                (0x2583, bytes.fromhex('218069'), 'ld hl,06980h'),
                (0x2586, bytes.fromhex('cd172b'), 'call 02b17h')]
        for at, data, _ in rows:
            program[at:at+len(data)] = data
        image, changes = relocate(bytes(program), rows, complete=False)
        self.assertEqual(image[0x2580:0x2583], bytes.fromhex('3a0038'))
        self.assertEqual(image[0x2583:0x2589], program[0x2583:0x2589])
        self.assertEqual(len(changes), 1)

    def test_indexed_byte_operands_are_not_sixteen_bit_addresses(self):
        program = bytearray(16384)
        program[0x2580:0x2584] = bytes.fromhex('dd36008a')
        image, changes = relocate(bytes(program), [(0x2580, bytes.fromhex('dd36008a'),
                                                   'ld (ix+0),08ah')], complete=False)
        self.assertEqual(image[0x2580:0x2584], program[0x2580:0x2584])
        self.assertFalse(changes)

    def test_mismatched_bytes_missing_code_and_external_calls_are_rejected(self):
        program = bytes(16384)
        for rows in [[(0x2580, b'\x01', 'ld bc,0')],
                     [(0x2580, b'\x00', 'nop')]]:
            with self.assertRaises(ValueError):
                relocate(program, rows)
        p = bytearray(program)
        p[0x2580:0x2583] = bytes.fromhex('cd0010')
        with self.assertRaises(ValueError):
            relocate(bytes(p), [(0x2580, bytes.fromhex('cd0010'), 'call 01000h')], complete=False)


if __name__ == '__main__':
    unittest.main()

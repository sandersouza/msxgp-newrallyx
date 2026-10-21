"""Synthetic checks for the native patch trust boundary."""
import hashlib
import unittest

from scripts.msx.native_patch import Patch, apply_patches


def digest(data):
    return hashlib.sha256(data).hexdigest()


class NativePatchTests(unittest.TestCase):
    def setUp(self):
        # Synthetic instructions only: CALL $0006; NOP; NOP; NOP; RET.
        self.image = bytes.fromhex('cd0600000000c9') + bytes(16384 - 7)
        self.boundaries = frozenset((0, 3, 4, 5, 6, 7))
        self.patch = Patch(0, digest(self.image[:3]), bytes.fromhex('c30600'), 3)

    def apply(self, patches=None, **changes):
        args = dict(image=self.image, expected_sha256=digest(self.image),
                    patches=(self.patch,) if patches is None else patches,
                    boundaries=self.boundaries)
        args.update(changes)
        return apply_patches(**args)

    def test_valid_patch_changes_only_guarded_span(self):
        result = self.apply()
        self.assertEqual(result, bytes.fromhex('c30600') + self.image[3:])
        self.assertEqual(self.image[:7], bytes.fromhex('cd0600000000c9'))

    def test_full_image_mismatch_is_rejected_even_with_valid_span(self):
        changed = self.image[:-1] + b'\x01'
        with self.assertRaisesRegex(ValueError, 'program'):
            self.apply(image=changed)

    def test_wrong_span_digest_and_changed_length_are_rejected(self):
        for patch in (Patch(0, digest(b'bad'), b'abc', 3),
                      Patch(0, digest(self.image[:3]), b'xy', 3)):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.apply((patch,))

    def test_instruction_operands_cannot_be_patch_endpoints(self):
        for first, last in ((1, 3), (0, 2)):
            patch = Patch(first, digest(self.image[first:last]), b'x' * (last-first), 3)
            with self.subTest(first=first, last=last), self.assertRaisesRegex(ValueError, 'instruction'):
                self.apply((patch,))

    def test_overlapping_and_duplicate_patches_are_rejected(self):
        overlap = Patch(0, digest(self.image[:4]), b'abcd', 4)
        for second in (self.patch, overlap):
            with self.subTest(second=second), self.assertRaisesRegex(ValueError, 'overlap'):
                self.apply((self.patch, second))

    def test_adjacent_patches_use_original_bytes_for_all_guards(self):
        second = Patch(3, digest(b'\x00'), b'\x76', 4)
        self.assertEqual(self.apply((second, self.patch)),
                         bytes.fromhex('c30600760000c9') + bytes(16384 - 7))

    def test_invalid_later_patch_cannot_change_mutable_source(self):
        source = bytearray(self.image)
        second = Patch(3, digest(b'\xff'), b'\x76', 4)
        with self.assertRaises(ValueError):
            self.apply((self.patch, second), image=source)
        self.assertEqual(source, self.image)
        self.assertEqual(self.apply(image=source)[:3], bytes.fromhex('c30600'))
        self.assertEqual(source, self.image)

    def test_invalid_continuations_are_rejected(self):
        for continuation in (-1, 1, 2, 16384, True):
            patch = Patch(0, digest(self.image[:3]), b'abc', continuation)
            with self.subTest(continuation=continuation), self.assertRaises(ValueError):
                self.apply((patch,))

    def test_invalid_spans_and_program_sizes_are_rejected(self):
        for first, replacement in ((-1, b'a'), (0, b''), (16383, b'ab'), (True, b'a')):
            patch = Patch(first, digest(b''), replacement, 3)
            with self.subTest(first=first), self.assertRaises(ValueError):
                self.apply((patch,))
        for image in (b'', bytes(16383), bytes(16385)):
            with self.subTest(size=len(image)), self.assertRaises(ValueError):
                self.apply((), image=image, expected_sha256=digest(image))

    def test_empty_patch_set_still_checks_program_identity(self):
        self.assertEqual(self.apply(()), self.image)
        with self.assertRaises(ValueError):
            self.apply((), expected_sha256='invalid')


if __name__ == '__main__':
    unittest.main()

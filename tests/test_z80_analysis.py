import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.z80_analysis import program_image, guarded_hook, destination, compare_references, hook_specs


class ProgramAnalysisTests(unittest.TestCase):
    def test_split_loads_follow_region_addresses(self):
        roms = {'a': bytes([1])*0x800 + bytes([3])*0x800,
                'b': bytes([2])*0x800 + bytes([4])*0x800,
                'tail': bytes([5])*0x2000}
        def record(name, loads):
            return dict(name=name, region='maincpu', loads=[
                dict(file_offset=src, region_offset=dst, size=size) for src,dst,size in loads])
        metadata = dict(roms=[record('a', [(0,0,0x800),(0x800,0x1000,0x800)]),
                              record('b', [(0,0x800,0x800),(0x800,0x1800,0x800)]),
                              record('tail', [(0,0x2000,0x2000)])])
        image = program_image(roms, metadata)
        self.assertEqual([image[a] for a in range(0,0x4000,0x800)], [1,2,3,4,5,5,5,5])
        metadata['roms'][1]['loads'][0]['region_offset'] = 0
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            program_image(roms, metadata)

    def test_incomplete_and_truncated_programs_are_rejected(self):
        record = dict(name='x', region='maincpu', loads=[
            dict(file_offset=0, region_offset=0, size=0x4000)])
        with self.assertRaises(ValueError):
            program_image({'x': b'abc'}, dict(roms=[record]))
        with self.assertRaisesRegex(ValueError, 'cover exactly'):
            program_image({}, dict(roms=[]))

    def test_hook_rejects_wrong_bytes_and_operand_boundaries(self):
        image = bytes([0xcd,0x10,0x00,0xc9])  # Synthetic CALL and RET.
        checksum = hashlib.sha256(image[:3]).hexdigest()
        self.assertEqual(guarded_hook(image,0,checksum,3,{0,3,4})['length'],3)
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            guarded_hook(b'xxxx',0,checksum,3,{0,3,4})
        with self.assertRaisesRegex(ValueError, 'complete observed'):
            guarded_hook(image,1,checksum,2,{0,3,4})

    def test_destination_rejects_existing_outside_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root/'references/analysis/existing').mkdir(parents=True)
            (root/'references/analysis/link').symlink_to(root/'references/analysis/existing')
            for output in (root/'outside', root/'references/analysis/existing',
                           root/'references/analysis/link/new', root/'references/analysis'):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    destination(root,output)

    def test_hook_inventory_rejects_unrecognized_program(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported bytes'):
            hook_specs(bytes(16384))

    def test_comparison_detects_state_divergence_and_missing_frames(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary)/'a', Path(temporary)/'b'
            first.mkdir(); second.mkdir()
            names = ['program.bin','program.asm','linear-index.json','provenance.json',
                     'accesses.tsv','frames.tsv','replay.json','summary.json',
                     'state-01799.bin','reset.trace']
            for folder in (first,second):
                for name in names:
                    (folder/name).write_bytes(b'synthetic evidence')
            self.assertEqual(compare_references(first,second),10)
            (second/'state-01799.bin').write_bytes(b'different state')
            with self.assertRaisesRegex(ValueError, 'diverged: state-01799'):
                compare_references(first,second)
            (second/'state-01799.bin').unlink()
            with self.assertRaisesRegex(ValueError, 'inventory differs'):
                compare_references(first,second)


if __name__ == '__main__':
    unittest.main()

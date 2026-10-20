import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from PIL import Image
from scripts.graphics import export
from graphics_fixtures import synthetic_payload, temporary_repo


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.root, self.inputs, self.output = temporary_repo(self)
        self.pixels, self.palette, self.graphics = synthetic_payload()

    def writer(self, directory):
        return export.write_payload(directory, self.pixels, self.palette,
                                    self.graphics, [], {'commit': 'synthetic'})

    def publish(self, overwrite=False, output=None, writer=None):
        return export.publish_output(self.root, self.inputs, output or self.output,
                                     overwrite, writer or self.writer)

    def test_all_outputs_indices_positions_colors_and_hashes(self):
        manifest = self.publish()
        self.assertEqual(len(manifest['outputs']), 137)
        self.assertEqual((self.output/'tiles/indices.bin').read_bytes(), self.pixels['tiles'])
        with Image.open(self.output/'tiles/atlas-indexed.png') as atlas:
            self.assertEqual(atlas.mode, 'P')
            self.assertEqual(atlas.size, (128,128))
            self.assertEqual(atlas.getpixel((0,0)), 2)
            self.assertEqual(atlas.getpixel((8,0)), 0)
        with Image.open(self.output/'sprites/color-00.png') as atlas:
            self.assertEqual(atlas.getpixel((0,0)), (0,0,0,255))
            self.assertEqual(atlas.getpixel((1,0)), (0,0,0,0))
        with Image.open(self.output/'tiles/color-00.png') as atlas:
            self.assertEqual(atlas.getpixel((1,0)), (0,0,0,255))
        with Image.open(self.output/'dots/color-00.png') as atlas:
            self.assertEqual(atlas.size, (32,4))
        self.assertTrue((self.output/'tiles/color-63.png').is_file())
        self.assertTrue((self.output/'sprites/color-63.png').is_file())
        for entry in manifest['outputs']:
            data = (self.output/entry['path']).read_bytes()
            self.assertEqual(len(data), entry['size'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
        self.assertNotIn(str(self.root), (self.output/'manifest.json').read_text())

    def test_repeatability_and_explicit_overwrite(self):
        self.publish()
        before = {str(p.relative_to(self.output)): p.read_bytes()
                  for p in self.output.rglob('*') if p.is_file()}
        with self.assertRaises(ValueError):
            self.publish()
        self.publish(overwrite=True)
        other = self.output.with_name('repeat')
        self.publish(output=other)
        for name, data in before.items():
            self.assertEqual((self.output/name).read_bytes(), data)
            self.assertEqual((other/name).read_bytes(), data)

    def test_unsafe_paths_are_rejected(self):
        link = self.root/'references/assets/link'
        link.symlink_to(self.inputs, target_is_directory=True)
        nondir = self.root/'references/assets/file'
        nondir.write_bytes(b'keep')
        for output in (self.root/'outside', self.root/'references/assets',
                       self.root/'references/assets/../assets/bad',
                       self.inputs/'nested', link/'child', nondir/'child'):
            with self.subTest(output=str(output)):
                with self.assertRaises(ValueError):
                    self.publish(output=output)
        self.assertEqual(nondir.read_bytes(), b'keep')

    def test_ignore_coverage_and_tracked_files_required(self):
        (self.root/'.gitignore').write_text('')
        with self.assertRaises(ValueError):
            self.publish()
        (self.root/'.gitignore').write_text('/references/**\n')
        self.output.mkdir()
        (self.output/'keep').write_bytes(b'original')
        subprocess.run(['git','-C',str(self.root),'add','-f','--',
                        str(self.output/'keep')], check=True)
        with self.assertRaisesRegex(ValueError, 'tracked'):
            self.publish(overwrite=True)
        with patch('scripts.graphics.export.subprocess.run', side_effect=FileNotFoundError('git')):
            with self.assertRaisesRegex(ValueError, 'Git'):
                self.publish()

    def test_modified_unknown_and_forged_output_preserved(self):
        self.publish()
        extra = self.output/'extra/nested'
        extra.parent.mkdir()
        extra.write_bytes(b'keep')
        with self.assertRaises(ValueError):
            self.publish(overwrite=True)
        self.assertEqual(extra.read_bytes(), b'keep')
        extra.unlink()
        extra.parent.rmdir()
        binary = self.output/'tiles/indices.bin'
        original = binary.read_bytes()
        binary.write_bytes(b'x')
        with self.assertRaises(ValueError):
            self.publish(overwrite=True)
        binary.write_bytes(original)
        manifest_path = self.output/'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['outputs'][0]['path'] = '../../outside'
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            self.publish(overwrite=True)

    def test_failed_writer_leaves_no_complete_output_or_lock(self):
        def fail(directory):
            (directory/'partial').write_bytes(b'x')
            raise OSError('synthetic disk failure')
        with self.assertRaises(OSError):
            self.publish(writer=fail)
        self.assertEqual(list(self.output.parent.iterdir()), [])
        self.publish()  # lock was released

    def test_lock_blocks_second_writer(self):
        def writer(directory):
            with self.assertRaisesRegex(ValueError, 'lock'):
                self.publish()
            return self.writer(directory)
        self.publish(writer=writer)

    def test_install_rename_failure_restores_old_output(self):
        self.publish()
        before = (self.output/'manifest.json').read_bytes()
        rename = Path.rename
        def fail_install(path, target):
            if '.staging-' in path.name:
                raise OSError('synthetic rename failure')
            return rename(path, target)
        with patch.object(Path, 'rename', fail_install):
            with self.assertRaises(OSError):
                self.publish(overwrite=True)
        self.assertEqual((self.output/'manifest.json').read_bytes(), before)
        self.assertEqual(list(self.output.parent.iterdir()), [self.output])

    def test_case_alias_cannot_overwrite_tracked_files_or_overlap_input(self):
        upper = self.output.with_name('UPPER')
        lower = self.output.with_name('upper')
        self.publish(output=upper)
        if not lower.exists() or not lower.samefile(upper):
            self.skipTest('Requires a case-insensitive filesystem')
        manifest = upper/'manifest.json'
        before = manifest.read_bytes()
        subprocess.run(['git','-C',str(self.root),'add','-f','--',str(manifest)], check=True)
        with self.assertRaisesRegex(ValueError, 'tracked'):
            self.publish(overwrite=True, output=lower)
        self.assertEqual(manifest.read_bytes(), before)
        subprocess.run(['git','-C',str(self.root),'rm','--cached','-q','--',str(manifest)],check=True)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            export.publish_output(self.root, upper, lower/'nested', False, self.writer)
        self.assertFalse((upper/'nested').exists())

    def test_stale_lock_reports_backup_recovery_without_modification(self):
        lock = self.output.with_name('.synthetic.lock')
        backup = self.output.with_name('.synthetic.backup-interrupted')
        lock.write_text('pid=dead\n')
        backup.mkdir()
        (backup/'evidence').write_bytes(b'keep')
        with self.assertRaises(ValueError) as caught:
            self.publish()
        self.assertIn(str(backup), str(caught.exception))
        self.assertIn(str(self.output), str(caught.exception))
        self.assertIn('restore', str(caught.exception).lower())
        self.assertEqual((backup/'evidence').read_bytes(),b'keep')
        self.assertTrue(lock.exists())


if __name__ == '__main__':
    unittest.main()

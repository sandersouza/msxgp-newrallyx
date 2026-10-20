import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from scripts import extract_graphics as cli
from scripts.graphics.roms import input_records
from graphics_fixtures import temporary_repo

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/extract_graphics.py'


class CliTests(unittest.TestCase):
    def setUp(self):
        self.root, self.inputs, self.output = temporary_repo(self)

    def test_help_and_invalid_arguments(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--help'],
                                capture_output=True, text=True, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        for term in ('nrallyx','--input','--output','--overwrite'):
            self.assertIn(term, result.stdout)
        for args in ([], ['--input','','--output',str(self.output)],
                     ['--input',str(self.inputs),'--output','']):
            result = subprocess.run([sys.executable,str(SCRIPT),*args],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('Traceback', result.stderr)
        self.assertFalse(self.output.exists())

    def synthetic_metadata(self):
        buffers = {'gfx': bytes(4096), 'dots': bytes(256),
                   'palette': bytes(32), 'lookup': bytes(range(256))}
        records = input_records(buffers)
        regions = {'gfx':'gfx1','dots':'gfx2','palette':'proms','lookup':'proms'}
        for record in records:
            name = record['name']
            (self.inputs/name).write_bytes(buffers[name])
            record.update(region=regions[name], loads=[dict(file_offset=0,
                region_offset=32 if name == 'lookup' else 0, size=record['size'])])
        return dict(roms=records, source={'commit':'synthetic'})

    def test_real_orchestration_and_retained_validated_buffers(self):
        metadata = self.synthetic_metadata()
        before = input_records({p.name:p.read_bytes() for p in self.inputs.iterdir()})
        with patch.object(cli,'REPO_ROOT',self.root), patch.object(cli,'load_metadata',return_value=metadata):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(['--input',str(self.inputs),'--output',str(self.output)]),0)
        manifest = json.loads((self.output/'manifest.json').read_text())
        self.assertEqual(manifest['inputs'], before)
        self.assertEqual((self.output/'tiles/indices.bin').read_bytes(),bytes(16384))
        self.assertEqual(input_records({p.name:p.read_bytes() for p in self.inputs.iterdir()}), before)

        validate = cli.validate_roms
        def mutate_after_validation(directory, inventory):
            buffers = validate(directory, inventory)
            (directory/'gfx').write_bytes(bytes([255])*4096)
            return buffers
        with patch.object(cli,'REPO_ROOT',self.root), patch.object(cli,'load_metadata',return_value=metadata), \
             patch.object(cli,'validate_roms',side_effect=mutate_after_validation):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(['--input',str(self.inputs), '--output',str(self.output), '--overwrite']),0)
        self.assertEqual(json.loads((self.output/'manifest.json').read_text())['inputs'], before)
        self.assertEqual((self.output/'tiles/indices.bin').read_bytes(),bytes(16384))

    def test_relative_paths_from_other_directory_and_spaces(self):
        metadata = self.synthetic_metadata()
        with patch.object(cli,'REPO_ROOT',self.root), patch.object(cli,'load_metadata',return_value=metadata), \
             contextlib.chdir(self.root), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['--input','references/roms/synthetic',
                '--output','references/assets/with spaces']),0)
        self.assertTrue((self.output.parent/'with spaces/manifest.json').is_file())

    def test_corrupt_input_fails_without_complete_output(self):
        metadata = self.synthetic_metadata()
        (self.inputs/'gfx').write_bytes(bytes([255])*4096)
        stderr = io.StringIO()
        with patch.object(cli,'REPO_ROOT',self.root), patch.object(cli,'load_metadata',return_value=metadata), \
             contextlib.redirect_stderr(stderr):
            self.assertNotEqual(cli.main(['--input',str(self.inputs),'--output',str(self.output)]),0)
        self.assertIn('gfx',stderr.getvalue())
        self.assertIn('expected',stderr.getvalue())
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()

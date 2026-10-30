import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from src.toolchain.legacy.restore_probe_artifacts import restore


class RestoreProbeArtifactsTest(unittest.TestCase):
    def test_restore_from_local_object_and_preserve_changed_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            data = b'Synthetic probe data\x00'
            blob = subprocess.check_output(['git', 'hash-object', '-w', '--stdin'], input=data, cwd=root).decode().strip()
            entry = dict(path='outputs/fixed-hud/radar-synthetic/expected.bin', bytes=len(data),
                         sha256=hashlib.sha256(data).hexdigest(), git_blob=blob)
            self.assertEqual(restore(root, [entry], check=True)['missing'], 1)
            self.assertFalse((root/entry['path']).exists())
            self.assertEqual(restore(root, [entry])['restored'], 1)
            self.assertEqual((root/entry['path']).read_bytes(), data)
            (root/entry['path']).write_bytes(b'Contributor evidence')
            self.assertEqual(restore(root, [entry])['different'], 1)
            self.assertEqual((root/entry['path']).read_bytes(), b'Contributor evidence')

    def test_reject_outside_paths_before_loading_git_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in ('../evidence.bin', '/tmp/evidence.bin', 'src/evidence.bin'):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    restore(Path(directory), [dict(path=path)])


if __name__ == '__main__':
    unittest.main()

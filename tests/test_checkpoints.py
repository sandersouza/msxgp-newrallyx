"""Keep named test cartridges reproducible without original game data."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import project
from scripts import native_runtime
from scripts.msx.checkpoints import inventory, publish, resolve, publish_latest, resolve_latest, LATEST_ROM
from scripts.scenes.storage import seal


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root/'.gitignore').write_text('/references/**\n')
        bundle = self.root/'references/build/synthetic'
        bundle.mkdir(parents=True)
        self.rom = bundle/'native.rom'
        self.rom.write_bytes(b'AB synthetic cartridge')
        seal(bundle)

    def publish(self):
        return publish(self.root, '11-01-test', self.rom, 'Synthetic test', 'diagnostic')

    def test_published_name_launches_exact_rom_and_is_idempotent(self):
        self.publish()
        self.publish()
        rom, entry = resolve(self.root, '11-01-test')
        self.assertEqual(rom, self.rom)
        self.assertEqual(entry['kind'], 'diagnostic')
        with patch.object(project, 'run_emulator') as emulator:
            project.run(self.root, checkpoint='11-01-test')
        self.assertEqual(emulator.call_args.args[1].rom, self.rom)

    def test_name_cannot_be_rebound_to_different_evidence(self):
        self.publish()
        self.rom.write_bytes(b'AB changed cartridge')
        seal(self.rom.parent)
        with self.assertRaisesRegex(ValueError, 'already published'):
            self.publish()
        with self.assertRaisesRegex(ValueError, 'evidence changed'):
            resolve(self.root, '11-01-test')

    def test_unknown_name_never_launches_default(self):
        with patch.object(project, 'run_emulator') as emulator:
            with self.assertRaisesRegex(ValueError, 'Unknown checkpoint'):
                project.run(self.root, checkpoint='missing')
        emulator.assert_not_called()

    def test_invalid_registry_entry_reports_error(self):
        path = self.publish()
        data = json.loads(path.read_text())
        data['checkpoints']['11-01-test'] = []
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Invalid local checkpoint registry'):
            inventory(self.root)

    def test_latest_retargets_without_changing_named_checkpoint(self):
        self.publish()
        latest = publish_latest(self.root, self.rom)
        self.assertTrue(latest.is_symlink())
        self.assertEqual(latest, self.root/LATEST_ROM)
        second = self.rom.parent.with_name('second')
        second.mkdir()
        other = second/'native.rom'
        other.write_bytes(b'AB newer synthetic cartridge')
        seal(second)
        publish_latest(self.root, other)
        self.assertEqual(resolve_latest(self.root), other)
        self.assertEqual(resolve(self.root, '11-01-test')[0], self.rom)
        with patch.object(project, 'run_emulator') as emulator:
            project.run(self.root, latest=True)
        self.assertEqual(emulator.call_args.args[1].rom, other)

    def test_invalid_new_latest_preserves_previous_and_missing_never_falls_back(self):
        with patch.object(project, 'run_emulator') as emulator:
            with self.assertRaisesRegex(ValueError, 'Latest cartridge missing'):
                project.run(self.root, latest=True)
        emulator.assert_not_called()
        publish_latest(self.root, self.rom)
        invalid = self.rom.parent.with_name('invalid')
        invalid.mkdir()
        other = invalid/'native.rom'
        other.write_bytes(b'AB unsealed candidate')
        with self.assertRaises(ValueError):
            publish_latest(self.root, other)
        self.assertEqual(resolve_latest(self.root), self.rom)

    def test_historical_full_runtime_cli_cannot_replace_active_incremental_latest(self):
        output = self.root/'references/build/output'
        with patch.object(native_runtime, 'ROOT', self.root), \
                patch.object(native_runtime, 'build_probe', return_value=self.rom):
            self.assertEqual(native_runtime.main([
                'build-probe', '--mode', 'runtime', '--output', str(output)]), 0)
            self.assertFalse((self.root/LATEST_ROM).exists())
            self.assertEqual(native_runtime.main([
                'build-probe', '--mode', 'logic', '--output', str(output),
                '--video-reference', str(self.rom.parent), '--no-hud']), 0)
            self.assertFalse((self.root/LATEST_ROM).exists())


if __name__ == '__main__':
    unittest.main()

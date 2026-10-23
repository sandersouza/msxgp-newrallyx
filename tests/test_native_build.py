"""Loader build safety and synthetic cartridge assembly without game data."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.msx.native_build import build, build_probe
from scripts.scenes.bundle import verify_manifest
from scripts.graphics.roms import load_metadata


ROOT = Path(__file__).resolve().parents[1]
ASSEMBLER = ROOT / '.tools/sjasmplus/1.24.0/sjasmplus'


class NativeBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('/references/**\n')
        self.output = self.root / 'references/build/probe'

    def probe(self, **changes):
        args = dict(root=self.root, output=self.output, assembler=ASSEMBLER, hz=50)
        args.update(changes)
        return build_probe(**args)

    def test_unsafe_existing_symlink_and_tracked_outputs_are_rejected(self):
        existing = self.root / 'references/build/existing'
        existing.mkdir(parents=True)
        link = self.root / 'link'
        link.symlink_to(self.root, target_is_directory=True)
        tracked = self.root / 'references/build/tracked/data'
        tracked.parent.mkdir(parents=True)
        tracked.write_bytes(b'authored fixture')
        subprocess.run(['git', '-C', str(self.root), 'add', '-f', str(tracked)], check=True)
        for output in (self.root / 'elsewhere', existing, self.root / 'references/build',
                       link / 'references/build/new', tracked.parent):
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.probe(output=output)

    def test_invalid_payloads_fail_before_any_output_is_created(self):
        for changes in (dict(resources={'big': bytes(65537)}), dict(program=bytes(16383)),
                        dict(hz=55), dict(assembler=self.root / 'missing'),
                        dict(probe='unknown'), dict(probe='reset'),
                        dict(optimize=1),dict(optimize=True),dict(function_probe=True),
                        dict(probe='logic',function_probe=True),dict(function_probe='yes'),
                        dict(fine_irq=True),dict(fine_irq=1),dict(probe='runtime',fine_irq=True),
                        dict(probe='runtime', program=bytes(16384)),
                        dict(hud_enabled=False), dict(hud_enabled=1),
                        dict(actors_enabled=False), dict(actors_enabled=1),
                        dict(freeze_presentation=True), dict(freeze_presentation=1),
                        dict(render_in_game_irq=False), dict(render_in_game_irq=1),
                        dict(edge_clear=False), dict(edge_clear=1),
                        dict(tick_foreground=True), dict(tick_foreground=1),
                        dict(actor_cache=True), dict(actor_cache=1)):
            with self.subTest(changes=list(changes)), self.assertRaises((ValueError, OSError)):
                self.probe(**changes)
            self.assertFalse(self.output.exists())

    def test_missing_original_inputs_never_publish_or_replace_default(self):
        default = self.root / 'references/build/newrallyx.rom'
        default.parent.mkdir(parents=True)
        default.write_bytes(b'previous valid cartridge placeholder')
        args = argparse.Namespace(output=self.output, assets=self.root / 'missing',
                                  assembler=ASSEMBLER, hz=50, logic_only=True)
        with self.assertRaises((ValueError, OSError)):
            build(self.root, args)
        self.assertFalse(self.output.exists())
        self.assertEqual(default.read_bytes(), b'previous valid cartridge placeholder')

    def test_corrupt_rom_inventory_is_refused_before_publication(self):
        inputs = self.root / 'references/roms/nrallyx'
        inputs.mkdir(parents=True)
        for record in load_metadata()['roms']:
            (inputs / record['name']).write_bytes(bytes(record['size']))
        args = argparse.Namespace(output=self.output, assets=self.root / 'missing',
                                  assembler=ASSEMBLER, hz=50, logic_only=True)
        with self.assertRaisesRegex(ValueError, 'Corrupt or unsupported ROM'):
            build(self.root, args)
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(ASSEMBLER.is_file(), 'Managed sjasmplus not installed')
    def test_irq_scheduler_probe_is_synthetic_and_links_the_real_dispatcher(self):
        import json
        rom = self.probe(probe='irq')
        report = json.loads((rom.parent/'build.json').read_text())
        self.assertEqual(report['mode'],'irq-probe')
        self.assertFalse(report['gameplay'])
        syms = (rom.parent/'native.sym').read_text()
        for label in ('Native_AdvanceClock:', 'Native_SelectIRQ:', 'Native_PublishRuntime:'):
            self.assertIn(label,syms)

    @unittest.skipUnless(ASSEMBLER.is_file(), 'Managed sjasmplus not installed')
    def test_runtime_microprobe_is_explicit_and_uses_only_synthetic_program(self):
        import json
        rom = self.probe(probe='runtime')
        report = json.loads((rom.parent/'build.json').read_text())
        self.assertEqual(report['mode'], 'runtime-probe')
        self.assertFalse(report['gameplay'])
        self.assertEqual(rom.read_bytes()[16384:16640], bytes(range(256)))
        self.assertIn('Native_IncrementRead:', (rom.parent/'native.sym').read_text())

    @unittest.skipUnless(ASSEMBLER.is_file(), 'Managed sjasmplus not installed')
    def test_synthetic_probe_is_sealed_and_explicitly_not_gameplay(self):
        rom = self.probe()
        manifest = verify_manifest(rom.parent)
        self.assertGreater(len(manifest['outputs']), 5)
        raw = rom.read_bytes()
        self.assertEqual(len(raw), 131072)
        self.assertEqual(raw[:2], b'AB')
        self.assertEqual(raw[16384:32768], bytes(16384))
        for index in range(4):
            self.assertEqual(raw[(index+2)*16384:(index+3)*16384], bytes((0x40+index,))*16384)
        import json
        report = json.loads((rom.parent / 'build.json').read_text())
        self.assertEqual(report['mode'], 'loader-probe')
        self.assertFalse(report['gameplay'])
        self.assertFalse((self.root / 'references/build/newrallyx.rom').exists())


if __name__ == '__main__':
    unittest.main()

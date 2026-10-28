import gzip
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.full_replay_probe import verify_replay_rom,replay_keyboard


class ReplayCartridgeTests(unittest.TestCase):
    def test_reapplication_extracts_only_valid_keyboard_timings(self):
        with TemporaryDirectory() as directory:
            replay=Path(directory)/'input.omr'
            replay.write_bytes(gzip.compress(b'<serial><replay><events>'
                b'<item type="KeyMatrixState"><StateChange><time><time>3436363200</time></time></StateChange>'
                b'<row>0</row><press>32</press><release>0</release></item>'
                b'<item type="MSXCommandEvent"><tokens><item>ignored</item></tokens></item>'
                b'</events><currentTime><time>6872726400</time></currentTime></replay></serial>'))
            self.assertEqual(replay_keyboard(replay),(2.0,[(1.0,0,32,0)]))

    def test_a_replay_cannot_qualify_a_different_cartridge(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);rom=root/'game.rom';replay=root/'input.omr'
            rom.write_bytes(b'authored synthetic cartridge')
            fingerprint=hashlib.sha1(rom.read_bytes()).hexdigest()
            replay.write_bytes(gzip.compress(f'<serial><rom><resolvedSha1>{fingerprint}</resolvedSha1></rom></serial>'.encode()))
            verify_replay_rom(replay,rom)
            rom.write_bytes(b'different synthetic cartridge')
            with self.assertRaisesRegex(ValueError,'cartridge fingerprint'):
                verify_replay_rom(replay,rom)

import gzip
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.full_replay_probe import verify_replay_rom


class ReplayCartridgeTests(unittest.TestCase):
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

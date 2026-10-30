import gzip
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

from src.toolchain.legacy.full_replay_probe import verify_replay_rom,replay_keyboard,bind_replay_rom
from src.toolchain.msx.emulator import retain_cartridge


class ReplayCartridgeTests(unittest.TestCase):
    def test_later_builds_cannot_change_the_retained_session_cartridge(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);source=root/'latest.rom';session=root/'session';session.mkdir()
            source.write_bytes(b'first synthetic build')
            retained=retain_cartridge(source,session)
            source.write_bytes(b'later synthetic build')
            self.assertEqual(retained.read_bytes(),b'first synthetic build')
            with self.assertRaisesRegex(ValueError,'already exists'):
                retain_cartridge(source,session)

    def test_replay_paths_bind_the_selected_rom_without_changing_state_or_source(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);rom=root/'sealed.rom';replay=root/'input.omr';target=root/'bound.omr'
            rom.write_bytes(b'authored synthetic cartridge')
            fingerprint=hashlib.sha1(rom.read_bytes()).hexdigest()
            prolog='<?xml version="1.0" ?>\n<!DOCTYPE openmsx-serialize SYSTEM "synthetic.dtd">\n'
            original=gzip.compress((prolog+'<serial><replay><snapshots><item><rom>'
                '<filename>/mutable/latest.rom</filename><resolvedFilename>/mutable/latest.rom</resolvedFilename>'
                f'<resolvedSha1>{fingerprint}</resolvedSha1></rom>'
                '<rom><filename>bios.rom</filename><resolvedSha1>different</resolvedSha1></rom>'
                '<state>synthetic native state</state></item></snapshots>'
                '<events>synthetic inputs</events><currentTime>1234</currentTime></replay></serial>').encode())
            replay.write_bytes(original)
            result=bind_replay_rom(replay,rom,target)
            saved=ET.fromstring(gzip.decompress(target.read_bytes()))
            self.assertTrue(gzip.decompress(target.read_bytes()).startswith(prolog.encode()))
            self.assertEqual(result['cartridge_references'],1)
            self.assertEqual(saved.findtext('.//rom/filename'),str(rom.resolve()))
            self.assertEqual(saved.findtext('.//rom/resolvedFilename'),str(rom.resolve()))
            self.assertEqual(saved.findtext('.//state'),'synthetic native state')
            self.assertEqual(saved.findtext('.//events'),'synthetic inputs')
            self.assertEqual(saved.findtext('.//currentTime'),'1234')
            self.assertEqual(saved.findall('.//rom')[1].findtext('filename'),'bios.rom')
            self.assertEqual(replay.read_bytes(),original)

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

"""Synthetic complete replays must fail closed on phase, identity or missing data."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.msx.native_compare import compare_series, compare_acquisition
from scripts.msx.native_contract import Snapshot, Exclusion
from scripts.msx.native_reset import PROGRAM_SHA256
from scripts.scenes.storage import seal
from scripts.scenes.bundle import digest


class NativeComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def state(self,tick=0,phase='initialization-entry',video=None):
        return Snapshot(tick,phase,video or bytes(4096),bytes(2048),bytes(392))

    def test_compare_rejects_missing_extra_misnumbered_and_misphased_snapshots(self):
        good = (self.state(),self.state(1,'post-game-irq'))
        self.assertTrue(compare_series(good,good)['state_equivalence'])
        for bad in (good[:1],good+good[-1:],
                    (good[0],self.state(2,'post-game-irq')),
                    (good[0],self.state(1,'post-game-irq-transfer'))):
            with self.assertRaises(ValueError): compare_series(good,bad)
        with self.assertRaises(ValueError): compare_series((),())

    def test_one_documented_exclusion_cannot_conceal_adjacent_live_difference(self):
        good = (self.state(),self.state(1,'post-game-irq'))
        bad = (good[0],self.state(1,'post-game-irq',b'\x01\x02'+bytes(4094)))
        report = compare_series(good,bad,(Exclusion(0x8000,'Synthetic adapter byte','synthetic proof'),))
        self.assertFalse(report['state_equivalence'])
        self.assertEqual(report['first_difference']['address'],0x8001)

    def bundles(self):
        b,c,r = (self.root/name for name in ('bundle','capture','reference'))
        for p in (b,c,r): p.mkdir()
        inputs = [dict(name='synthetic',sha256='0'*64,size=1)]
        def write(p,data): p.write_text(json.dumps(data))
        for p in (r/'initialization.bin',r/'foreground-entry.bin',r/'state-00001.bin',
                  c/'initialization.bin',c/'state-00001.bin'): p.write_bytes(bytes(6536))
        (r/'complete').write_text('ok\n')
        write(r/'execution.json',dict(schema_version=1,boot_frame=10,ticks=1,
              controls=[dict(address=60,kind='ei',count=1)]))
        write(r/'provenance.json',dict(program_sha256=PROGRAM_SHA256,inputs=inputs))
        (r/'boundaries.tsv').write_text(
            'tick\tframe\tphase\tpc\tsp\tim\ti\tiff1\ttime\n'
            '0\t10\tinitialization-entry\t0003\t8400\t2\t3f\t0\t0000.100,000,000\n'
            '0\t11\tforeground-entry\t0c2c\t8400\t0\t3f\t1\t0000.110,000,000\n'
            '0\t12\tpre-game-irq\t01f0\t83fc\t0\t3f\t0\t0000.120,000,000\n'
            '1\t12\tpost-game-irq\t0471\t83fc\t0\t3f\t1\t0000.121,000,000\n')
        (r/'inputs.tsv').write_text('tick\tframe\tp1\tp2\tdip\n0\t12\tff\tff\tc3\n')
        seal(r)
        (b/'native-program.bin').write_bytes(bytes(16384))
        (b/'native.rom').write_bytes(b'R'*16384)
        write(b/'build.json',dict(mode='logic-probe',source_program_sha256=PROGRAM_SHA256,
              program_sha256=digest(b/'native-program.bin'),inputs=inputs,
              reference_manifest_sha256=digest(r/'manifest.json')))
        seal(b)
        for phase in ('initial','final'):
            (c/f'{phase}-program.bin').write_bytes(bytes(16384))
            (c/f'{phase}-resident.bin').write_bytes(b'R'*16384)
        write(c/'clock.json',dict(z80_freq=3579545,z80_freq_locked=False))
        write(c/'boot-registers.json',dict(AF=64,BC=0,DE=0,HL=0,IX=65535,IY=65535,AF2=0,BC2=0,DE2=0,HL2=0))
        write(c/'execution.json',dict(schema_version=1,complete=True,ticks=1,stack_min=33750))
        write(c/'runtime.json',dict(acquisition_only=True,equivalence=False,prefix_only=False,
              requested_ticks=1,reference_ticks=1,inputs=inputs,
              candidate_manifest_sha256=digest(b/'manifest.json'),reference_manifest_sha256=digest(r/'manifest.json')))
        (c/'inputs.tcl').write_text('set nr_inputs {{255 255 195}}\n')
        (c/'events.tsv').write_text('tick\tphase\tpc\tsp\tpending\tcycles\ttime\n'
            '0\tpre-game-irq\t496\t33788\t0\t0\t1.0\n'
            '1\tpost-game-irq\t17408\t33788\t0\t3579\t1.001\n')
        seal(c)
        return b,c,r

    def test_complete_equal_fixture_produces_sealed_passing_report(self):
        b,c,r = self.bundles()
        # Exercise the pure evidence path without requiring a contributor checkout.
        from unittest.mock import patch
        out = self.root/'report'
        with patch('scripts.msx.native_compare.destination',return_value=out), \
             patch('scripts.msx.native_compare.require_ignored'):
            self.assertTrue(compare_acquisition(self.root,b,c,r,out)['state_equivalence'])
        self.assertTrue((out/'manifest.json').is_file())

    def test_partial_or_resealed_wrong_inputs_phase_stack_time_cannot_pass(self):
        b,c,r = self.bundles()
        original = {name:(c/name).read_bytes() for name in ('runtime.json','events.tsv','inputs.tcl','state-00001.bin')}
        runtime = json.loads(original['runtime.json'])
        cases = [('runtime.json',json.dumps(dict(runtime,prefix_only=True)).encode()),
                 ('runtime.json',json.dumps(dict(runtime,reference_manifest_sha256='0'*64)).encode()),
                 ('events.tsv',original['events.tsv'].replace(b'post-game-irq\t',b'post-game-irq-transfer\t')),
                 ('events.tsv',original['events.tsv'].replace(b'17408\t33788',b'17408\t33786')),
                 ('events.tsv',original['events.tsv'].replace(b'1.001',b'1.01')),
                 ('inputs.tcl',b'set nr_inputs {{127 255 195}}\n'),
                 ('state-00001.bin',bytes(6535))]
        for name,bad in cases:
            with self.subTest(name=name):
                (c/name).write_bytes(bad);seal(c)
                with self.assertRaises(ValueError):
                    compare_acquisition(self.root,b,c,r,self.root/'must-not-pass')
                (c/name).write_bytes(original[name]);seal(c)

    def test_tampered_or_missing_snapshot_is_rejected_before_comparison(self):
        b,c,r = self.bundles()
        p = c/'state-00001.bin'
        p.write_bytes(b'X'+bytes(6535))
        with self.assertRaises(ValueError): compare_acquisition(self.root,b,c,r,self.root/'no-report')
        p.unlink()
        with self.assertRaises(ValueError): compare_acquisition(self.root,b,c,r,self.root/'no-report')

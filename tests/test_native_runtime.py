"""Runtime acquisitions must reject unsafe inputs before launching emulation."""
from pathlib import Path
import subprocess
import json
import tempfile
import unittest

from src.toolchain.msx.native_verify import capture_reference, control_hits, analyze_reference, analyze_reset, load_input_levels, analyze_acquisition, analyze_function, analyze_profile, analyze_boot_registers
from src.toolchain.msx.native_reset import patch_reset
from src.toolchain.msx.native_contract import Snapshot, first_difference
from src.toolchain.scenes.storage import seal
from src.toolchain.scenes.bundle import digest
from src.toolchain.msx.native_logic import patch_logic, coordinate_deltas


class NativeRuntimeReferenceTests(unittest.TestCase):
    def test_coordinate_deltas_cover_signed_boundary_and_modulo_wrap(self):
        table = coordinate_deltas()
        self.assertEqual(len(table),256)
        self.assertEqual([table[n] for n in (0,92,93,220,221,255)],
                         [0,4,254,254,255,0])
    def test_boot_registers_reject_bios_context_missing_pairs_and_boolean_zero(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            good = dict(AF=0x40,BC=0,DE=0,HL=0,IX=0xffff,IY=0xffff,
                        AF2=0,BC2=0,DE2=0,HL2=0)
            path = out/'boot-registers.json'
            path.write_text(json.dumps(good))
            self.assertEqual(analyze_boot_registers(out),good)
            for bad in (dict(good,IX=0x4010),dict(good,AF2=0xf4a0),
                        dict(good,BC=False),{k:v for k,v in good.items() if k!='HL2'}):
                path.write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError,'boot register'):
                    analyze_boot_registers(out)

    def test_coordinate_proof_requires_complete_equal_outputs_and_measured_improvement(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            good = dict(cases=131072,complete=True,compared=['AF','HL','BC','DE'],reference_cycles=20000000,optimized_cycles=15000000)
            (out/'function.json').write_text(json.dumps(good))
            self.assertEqual(analyze_function(out),good)
            for key,value in (('cases',65536),('cases',True),('complete',False),
                              ('compared',['AF','HL']),('optimized_cycles',20000000),
                              ('optimized_cycles',0),('reference_cycles',True)):
                (out/'function.json').write_text(json.dumps(dict(good,**{key:value})))
                with self.assertRaises(ValueError): analyze_function(out)

    def test_profile_reconciles_every_clock_and_rejects_wrong_or_duplicate_addresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            (out/'profile-window.tsv').write_text('start\tend\tcycles\n1600\t1616\t80\n')
            good = 'pc\tcycles\n4096\t30\n16384\t50\n'
            (out/'profile.tsv').write_text(good)
            self.assertEqual(analyze_profile(out,(1600,1616))['cycles'],80)
            with self.assertRaises(ValueError): analyze_profile(out,(1601,1616))
            for bad in (good.replace('50','49'),good.replace('16384','4096'),
                        good.replace('16384','65536'),good.replace('30','-1'),
                        good.replace('50','50.0'),good.splitlines(True)[0]):
                (out/'profile.tsv').write_text(bad)
                with self.assertRaises(ValueError): analyze_profile(out,(1600,1616))

    def test_raw_acquisition_requires_exact_code_reset_completion_and_snapshot_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle,output,reference = (root/name for name in ('bundle','output','reference'))
            for path in (bundle,output,reference): path.mkdir()
            (bundle/'native-program.bin').write_bytes(bytes(16384))
            (bundle/'native.rom').write_bytes(b'R'*16384)
            for phase in ('initial','final'):
                (output/f'{phase}-program.bin').write_bytes(bytes(16384))
                (output/f'{phase}-resident.bin').write_bytes(b'R'*16384)
            for path in (reference/'initialization.bin',output/'initialization.bin',output/'state-00001.bin'):
                path.write_bytes(bytes(6536))
            good = dict(schema_version=1,complete=True,ticks=1,stack_min=0x83d6)
            (output/'clock.json').write_text('{"z80_freq":3579545,"z80_freq_locked":false}')
            (output/'execution.json').write_text(json.dumps(good))
            (output/'events.tsv').write_text('tick\tphase\tpc\tsp\tpending\tcycles\ttime\n'
                '0\tpre-game-irq\t496\t33788\t0\t0\t1.0\n'
                '1\tpost-game-irq\t17408\t33788\t0\t3579\t1.001\n')
            self.assertEqual(analyze_acquisition(bundle,output,reference,1),good)
            (output/'clock.json').write_text('{"z80_freq":3579545,"z80_freq_locked":true}')
            with self.assertRaisesRegex(ValueError,'clock'):
                analyze_acquisition(bundle,output,reference,1)
            (output/'clock.json').write_text('{"z80_freq":3579545,"z80_freq_locked":false}')
            for key,value in (('ticks',True),('complete',False),('stack_min',0x7fff),('schema_version',True)):
                (output/'execution.json').write_text(json.dumps(dict(good,**{key:value})))
                with self.assertRaises(ValueError): analyze_acquisition(bundle,output,reference,1)
            (output/'execution.json').write_text(json.dumps(good))
            for name in ('initial-program.bin','final-resident.bin','initialization.bin','state-00001.bin'):
                path = output/name
                original = path.read_bytes()
                path.write_bytes(original[:-1])
                with self.assertRaises(ValueError): analyze_acquisition(bundle,output,reference,1)
                path.write_bytes(original)
            (output/'state-00002.bin').write_bytes(bytes(6536))
            with self.assertRaises(ValueError): analyze_acquisition(bundle,output,reference,1)

    def test_input_replay_requires_exact_pre_irq_rows_and_byte_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            (out/'boundaries.tsv').write_text('tick\tframe\tphase\n0\t10\tpre-game-irq\n1\t11\tpre-game-irq\n')
            rows = 'tick\tframe\tp1\tp2\tdip\n0\t10\tff\tff\tc3\n1\t11\t7f\tff\tc3\n'
            (out/'inputs.tsv').write_text(rows)
            self.assertEqual(load_input_levels(out),[(255,255,195),(127,255,195)])
            for bad in (rows.replace('1\t11','1\t12'),rows.replace('7f','100'),rows.splitlines(True)[:-1]):
                (out/'inputs.tsv').write_text(''.join(bad) if isinstance(bad,list) else bad)
                with self.assertRaises(ValueError):
                    load_input_levels(out)
    def test_gameplay_adapter_rejects_unpinned_program_before_using_symbols(self):
        with self.assertRaisesRegex(ValueError,'program'):
            patch_logic(bytes(16384),{},frozenset())
    def test_reset_proof_rejects_false_completion_payload_changes_and_real_state_differences(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, output, reference = (root/n for n in ('bundle','output','reference'))
            for path in (bundle,output,reference): path.mkdir()
            (reference/'initialization.bin').write_bytes(bytes(6536))
            (reference/'foreground-entry.bin').write_bytes(bytes(6536))
            (reference/'state-00001.bin').write_bytes(bytes(6536))
            (reference/'complete').write_text('ok\n')
            (reference/'execution.json').write_text(json.dumps(dict(schema_version=1,
                boot_frame=10,ticks=1,controls=[dict(address=60,kind='ei',count=1)])))
            (reference/'boundaries.tsv').write_text(
                'tick\tframe\tphase\tpc\tsp\tim\ti\tiff1\ttime\n'
                '0\t10\tinitialization-entry\t0003\t8400\t2\t3f\t0\t0000.100,000,000\n'
                '0\t11\tforeground-entry\t0c2c\t8400\t0\t3f\t1\t0000.110,000,000\n'
                '0\t12\tpre-game-irq\t01f0\t83fc\t0\t3f\t0\t0000.120,000,000\n'
                '1\t12\tpost-game-irq\t0471\t83fc\t0\t3f\t1\t0000.121,000,000\n')
            seal(reference)
            (bundle/'native-program.bin').write_bytes(bytes(16384))
            (bundle/'native.rom').write_bytes(b'R'*16384)
            (bundle/'build.json').write_text(json.dumps(dict(mode='reset-probe',
                reference_manifest_sha256=digest(reference/'manifest.json'))))
            seal(bundle)
            expected = dict(schema_version=1,pc=3,sp=0x8400,im=2,i=0xd0,iff=0,complete=True)
            (output/'program.bin').write_bytes(bytes(16384))
            (output/'resident.bin').write_bytes(b'R'*16384)
            (output/'initialization.bin').write_bytes(bytes(6536))
            (output/'execution.json').write_text(json.dumps(expected))
            self.assertIsNone(analyze_reset(bundle,output,reference)['first_difference'])
            boundary = (reference/'boundaries.tsv').read_text()
            (reference/'boundaries.tsv').write_text(boundary.replace('0003\t8400','0003\t0000'))
            seal(reference)
            with self.assertRaisesRegex(ValueError,'boundary'):
                analyze_reset(bundle,output,reference)
            (reference/'boundaries.tsv').write_text(boundary)
            seal(reference)
            for key,value in (('schema_version',True),('complete',1),('pc',4),('sp',0x83fe),('iff',1)):
                (output/'execution.json').write_text(json.dumps(expected|{key:value}))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    analyze_reset(bundle,output,reference)
            (output/'execution.json').write_text(json.dumps(expected))
            changed = bytearray(6536)
            changed[4096] = 1
            (output/'initialization.bin').write_bytes(changed)
            with self.assertRaisesRegex(ValueError,'diverged'):
                analyze_reset(bundle,output,reference)
            difference = json.loads((output/'verification.json').read_text())['first_difference']
            self.assertEqual(difference['address'],0x9800)
            (output/'initialization.bin').write_bytes(bytes(6536))
            (output/'program.bin').write_bytes(b'x'+bytes(16383))
            with self.assertRaisesRegex(ValueError,'mapped'):
                analyze_reset(bundle,output,reference)

    def test_initialization_and_irq_transfer_have_distinct_snapshot_phases(self):
        args = dict(tick=0, video=bytes(4096), work=bytes(2048), shadows=bytes(392))
        initial = Snapshot(phase='initialization-entry', **args)
        transferred = Snapshot(phase='post-game-irq-transfer', **args)
        self.assertIsNone(first_difference(initial, initial))
        with self.assertRaisesRegex(ValueError, 'phase'):
            first_difference(initial, transferred)

    def test_reset_adapter_refuses_unpinned_programs_and_nonresident_targets(self):
        for target in (True, -1, 0x3fff, 0x8000, 0xd400):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'resident'):
                patch_reset(bytes(16384), target, frozenset())
        with self.assertRaisesRegex(ValueError, 'program'):
            patch_reset(bytes(16384), 0x4500, frozenset((0x38cc,0x38d0,0x397e,0x3980)))
    def test_reference_requires_complete_ordered_boundary_and_snapshot_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            (out/'complete').write_text('ok\n')
            (out/'execution.json').write_text(json.dumps(dict(
                schema_version=1, boot_frame=10, ticks=1,
                controls=[dict(address=60,kind='ei',count=1)])))
            header = 'tick\tframe\tphase\tpc\tsp\tim\ti\tiff1\ttime\n'
            rows = ('0\t10\tinitialization-entry\t0003\t8400\t2\t3f\t0\t0000.100,000,000\n'
                    '0\t11\tforeground-entry\t0c2c\t83fe\t0\t3f\t1\t0000.110,000,000\n'
                    '0\t12\tpre-game-irq\t01f0\t83fc\t0\t3f\t0\t0000.120,000,000\n'
                    '1\t12\tpost-game-irq\t0471\t83fc\t0\t3f\t1\t0000.121,000,000\n')
            (out/'boundaries.tsv').write_text(header+rows)
            for name in ('initialization.bin', 'foreground-entry.bin', 'state-00001.bin'):
                (out/name).write_bytes(bytes(6536))
            self.assertEqual(analyze_reference(out)['ticks'], 1)
            execution = json.loads((out/'execution.json').read_text())
            for controls in ([], None, [dict(address=True,kind='ei',count=1)],
                             [dict(address=60,kind='ei',count=False)]):
                (out/'execution.json').write_text(json.dumps(execution|dict(controls=controls)))
                with self.subTest(controls=controls), self.assertRaises(ValueError):
                    analyze_reference(out)
            (out/'execution.json').write_text(json.dumps(execution))
            for name in ('initialization.bin', 'foreground-entry.bin', 'state-00001.bin'):
                (out/name).write_bytes(bytes(6535))
                with self.subTest(name=name), self.assertRaises(ValueError):
                    analyze_reference(out)
                (out/name).write_bytes(bytes(6536))
            for bad in (rows.replace('post-game-irq', 'pre-game-irq'),
                        rows.replace('0003\t8400', '0003\t0000'),
                        rows.replace('83fe\t0\t3f\t1', '83fe\t0\t3f\t999'),
                        rows.replace('1\t12\tpost-', '2\t12\tpost-'),
                        rows.replace('0471', '0468'),
                        rows.replace('0000.121', '0000.119')):
                (out/'boundaries.tsv').write_text(header+bad)
                with self.subTest(rows=bad), self.assertRaises(ValueError):
                    analyze_reference(out)
            (out/'boundaries.tsv').write_text(header+rows)
            transferred = rows.replace(
                '1\t12\tpost-game-irq\t0471\t83fc\t0\t3f\t1\t0000.121,000,000\n',
                '0\t12\tgame-irq-transfer\t075a\t83e0\t0\t3f\t0\t0000.121,000,000\n'
                '1\t12\tpost-game-irq-transfer\t0769\t8400\t0\t3f\t0\t0000.122,000,000\n')
            (out/'boundaries.tsv').write_text(header+transferred)
            self.assertEqual(analyze_reference(out)['irq_transfers'], 1)
            (out/'boundaries.tsv').write_text(header+transferred.replace('075a', '075d'))
            with self.assertRaises(ValueError):
                analyze_reference(out)
            collided = rows.replace(
                '1\t12\tpost-game-irq\t0471\t83fc\t0\t3f\t1\t0000.121,000,000\n',
                '0\t12\tgame-irq-collision\t03b9\t83f0\t0\t3f\t0\t0000.121,000,000\n'
                '1\t12\tpost-game-irq-collision\t18c1\t83f0\t0\t3f\t1\t0000.122,000,000\n')
            (out/'boundaries.tsv').write_text(header+collided)
            self.assertEqual(analyze_reference(out)['irq_transfers'], 1)
            for bad in (collided.replace('18c1\t83f0', '18c1\t8400'),
                        collided.replace('18c1\t83f0\t0\t3f\t1', '18c1\t83f0\t0\t3f\t0')):
                (out/'boundaries.tsv').write_text(header+bad)
                with self.assertRaises(ValueError): analyze_reference(out)
            (out/'boundaries.tsv').write_text(header+rows)
            (out/'state-00002.bin').write_bytes(bytes(6536))
            with self.assertRaises(ValueError):
                analyze_reference(out)

    def test_only_debugger_execution_markers_count_as_control_instructions(self):
        image = bytearray(16384)
        image[0x100] = 0xf3
        image[0x200] = 0xfb
        log = 'data read 0200\nNATIVE_CONTROL 0100\nNATIVE_CONTROL 0100\nNATIVE_CONTROL 0200\n'
        self.assertEqual(control_hits(log, bytes(image)), [
            dict(address=0x100, kind='di', count=2),
            dict(address=0x200, kind='ei', count=1)])
        for bad in ('NATIVE_CONTROL 0300\n', 'NATIVE_CONTROL 10000\n',
                    'NATIVE_CONTROL xyz\n', ''):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                control_hits(bad, bytes(image))

    def test_bad_reference_destinations_and_frame_counts_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / '.gitignore').write_text('/references/**\n')
            for output, frames in ((root/'outside', 3200),
                                   (root/'references/analysis/ref', 0),
                                   (root/'references/analysis/ref', 800),
                                   (root/'references/analysis/ref', True)):
                with self.subTest(output=output, frames=frames), self.assertRaises(ValueError):
                    capture_reference(root, output, frames=frames)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()

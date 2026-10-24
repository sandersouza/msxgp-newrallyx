"""A loader proof cannot pass from a completion flag alone."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.msx.native_probe import analyze_probe, analyze_increment, analyze_schedule, analyze_waits
from scripts.msx.native_contract import advance_clock
from scripts.scenes.storage import seal


class NativeProbeEvidenceTests(unittest.TestCase):
    def test_wait_proof_requires_blocked_host_wake_queued_ticks_and_empty_poll(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'waits.tsv'
            good = 'case\tticks\tframes\tpending\n0\t1\t2\t1\n1\t4\t2\t255\n2\t4\t2\t0\n'
            path.write_text(good)
            self.assertEqual(analyze_waits(path),3)
            for bad in (good.replace('0\t1\t2','0\t1\t1'),
                        good.replace('1\t4\t2','1\t3\t2'),
                        good.replace('2\t4\t2','2\t5\t2'),
                        good.replace('255','256'),
                        good.rsplit('2\t4\t2',1)[0]):
                path.write_text(bad)
                with self.assertRaises(ValueError):
                    analyze_waits(path)

    def test_schedule_requires_each_gate_case_and_exact_clock_pending_and_tick_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'schedule.tsv'
            rows = ['case\tgate\tpending\tticks\tremainder']
            remainder = pending = ticks = 0
            for n in range(64):
                due,remainder = advance_clock(remainder,71364)
                pending += due
                if n%6 == 0:
                    pending -= 1
                    ticks += 1
                rows.append(f'{n}\t{n%6}\t{pending}\t{ticks}\t{remainder}')
            path.write_text('\n'.join(rows)+'\n')
            state = bytearray(128)
            state[80:84] = (112437405).to_bytes(4,'little')
            state[84:88] = (120827).to_bytes(4,'little')
            drain = ['case\tevent\tpending\tticks\tremainder']
            for _ in range(pending+1):
                if pending:
                    pending -= 1
                    drain.append(f'{len(drain)-1}\tclaim\t{pending}\t{ticks}\t{remainder}')
                    ticks += 1
                    drain.append(f'{len(drain)-1}\tpublish\t{pending}\t{ticks}\t{remainder}')
                drain.append(f'{len(drain)-1}\tcheckpoint\t{pending}\t{ticks}\t{remainder}')
            drain_path = path.with_name('drain.tsv')
            drain_path.write_text('\n'.join(drain)+'\n')
            state[48:52] = remainder.to_bytes(4,'little')
            state[72:76] = ticks.to_bytes(4,'little')
            result = analyze_schedule(path,bytes(state),71364)
            self.assertEqual(result['cases'],64)
            self.assertEqual(result['completed_ticks'],11)
            state[70] = 1
            with self.assertRaises(ValueError):
                analyze_schedule(path,bytes(state),71364)
            state[70] = 0
            drain_path.write_text('\n'.join(drain[:-1])+'\n')
            with self.assertRaises(ValueError):
                analyze_schedule(path,bytes(state),71364)
            drain_path.write_text('\n'.join(drain)+'\n')
            for bad in (rows[:-1], rows[:2]+rows[1:],
                        [r.replace('1\t1\t1\t1\t','1\t1\t0\t1\t') for r in rows]):
                path.write_text('\n'.join(bad)+'\n')
                with self.subTest(rows=len(bad)), self.assertRaises(ValueError):
                    analyze_schedule(path,bytes(state),71364)
            path.write_text('\n'.join(rows)+'\n')
            state[80] ^= 1
            with self.assertRaises(ValueError):
                analyze_schedule(path,bytes(state),71364)

    def test_increment_proof_checks_every_value_carry_and_memory_region(self):
        # Independent flag-bit specification; includes undocumented result bits.
        evidence = bytearray()
        for ram in (False, True):
            for carry in (0, 1):
                for value in range(256):
                    result = (value+1) % 256
                    flags = carry | (result & 0xa8)
                    if result == 0: flags |= 0x40
                    if value % 16 == 15: flags |= 0x10
                    if value == 127: flags |= 4
                    observed = result if ram else value
                    evidence.extend((observed, flags, observed, 0x98 if ram else 0))
        self.assertEqual(analyze_increment(bytes(evidence)), 1024)
        for offset in (0, 1, 2, 3, 2047, 4095):
            changed = evidence.copy()
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                analyze_increment(bytes(changed))
        with self.assertRaises(ValueError):
            analyze_increment(bytes(evidence[:-1]))

    def evidence(self, root):
        bundle, output = root / 'bundle', root / 'output'
        bundle.mkdir()
        output.mkdir()
        program, resident = b'\x12' * 16384, b'A' * 16384
        assets = b''.join(bytes((n,)) * 16384 for n in (0x40, 0x41, 0x42, 0x43))
        (bundle / 'native-program.bin').write_bytes(program)
        (bundle / 'native-assets.bin').write_bytes(assets)
        (bundle / 'native.rom').write_bytes(resident)
        (bundle / 'build.json').write_text('{"mode":"loader-probe"}')
        (bundle / 'native.sym').write_text('NATIVE_STACK: EQU 0x0000F380\nNATIVE_STATE: EQU 0x0000C500\nNATIVE_TAG: EQU 0x0000C700\n')
        seal(bundle)
        state = bytearray(64)
        state[0] = 2
        state[8:16] = bytes(range(8))
        state[16:18] = b'\x00\xff'
        state[32] = 8
        state[52] = 3
        state[54:57] = b'\xa5\x5a\x02'
        game = bytearray(16384)
        game[0x2200:0x2203] = b'\xff\xff\xc3'
        physical = bytearray(131072)
        physical[0x500:0x540] = state
        physical[0x700:0x702] = b'\x00\xff'
        physical[0x580:0x582] = b'\xa5\x5a'
        physical[16384:] = resident + program + game + assets
        (output / 'host-state.bin').write_bytes(state)
        (output / 'mapper.bin').write_bytes(physical)
        (output / 'visible.bin').write_bytes(program + resident + game)
        (output / 'execution.json').write_text(json.dumps(
            dict(status=2, iterations=256, irqs=256, sp=0xf380, resets=1)))
        return bundle, output

    def test_irq_stack_canary_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle, output = self.evidence(Path(temporary))
            physical = bytearray((output/'mapper.bin').read_bytes())
            physical[0x580] ^= 1
            (output/'mapper.bin').write_bytes(physical)
            with self.assertRaisesRegex(ValueError, 'IRQ stack'):
                analyze_probe(bundle, output)

    def test_copied_payload_mismatch_is_rejected_after_valid_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle, output = self.evidence(Path(temporary))
            self.assertTrue(analyze_probe(bundle, output)['payloads_verified'])
            physical = bytearray((output / 'mapper.bin').read_bytes())
            physical[32768] = 0x13
            (output / 'mapper.bin').write_bytes(physical)
            with self.assertRaisesRegex(ValueError, 'copy'):
                analyze_probe(bundle, output)

    def test_incomplete_physical_segment_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle, output = self.evidence(Path(temporary))
            with (output / 'mapper.bin').open('ab') as stream:
                stream.write(b'\x00')
            with self.assertRaisesRegex(ValueError, 'memory'):
                analyze_probe(bundle, output)

    def test_missing_or_partial_proof_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            for report in ({}, [], dict(status=2, iterations=255, irqs=256, sp=0xf380, resets=1),
                           dict(status=2, iterations=256, irqs=0, sp=0xf380, resets=1),
                           dict(status=2, iterations=256, irqs=256, sp=0xf37e, resets=1),
                           dict(status=2, iterations=256, irqs='256', sp=0xf380, resets=1)):
                (output / 'execution.json').write_text(json.dumps(report))
                with self.subTest(report=report), self.assertRaises(ValueError):
                    analyze_probe(output / 'missing-bundle', output)


if __name__ == '__main__':
    unittest.main()

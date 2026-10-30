import csv
from pathlib import Path
import tempfile
import unittest

from src.toolchain.msx.native_inputs import analyze_keyboard, analyze_joystick


class PhysicalInputEvidenceTests(unittest.TestCase):
    def rows(self):
        cases = ((0, 0, 255), (0, 32, 127), (0, 2, 191), (8, 32, 223),
                 (8, 64, 239), (8, 16, 251), (8, 128, 247), (8, 1, 253), (8, 177, 209))
        return [dict(case=n, row=r, mask=m, prior=p, expected=e, actual=e,
                     ppi_before=0xa8, ppi_after=0xa8, psg_after=p, p2=255, dip=195)
                for n, (r, m, e, p) in enumerate((r, m, e, p) for r, m, e in cases
                    for p in (0, 1, 2, 3, 16, 64, 128, 255))]

    def write(self, path, rows):
        with path.open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=self.rows()[0], delimiter='\t')
            writer.writeheader()
            writer.writerows(rows)

    def test_complete_matrix_proof_keeps_joystick_and_gameplay_unverified(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'inputs.tsv'
            self.write(path, self.rows())
            result = analyze_keyboard(path)
            self.assertEqual(result['keyboard_cases'], 72)
            self.assertTrue(result['keyboard_matrix_verified'])
            self.assertFalse(result['joystick_directions_verified'])
            self.assertFalse(result['gameplay_verified'])

    def test_incomplete_wrong_mapping_and_unrestored_outputs_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'inputs.tsv'
            self.write(path, self.rows()[:-1])
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                analyze_keyboard(path)
            for field in ('actual', 'psg_after', 'ppi_after', 'p2', 'dip', 'expected'):
                rows = self.rows()
                rows[0][field] ^= 1
                self.write(path, rows)
                with self.assertRaisesRegex(ValueError, 'failed'):
                    analyze_keyboard(path)

    def test_joystick_evidence_rejects_swapped_axes_and_output_changes(self):
        levels = ((63, 255), (62, 223), (61, 239), (59, 251), (55, 247),
                  (47, 253), (31, 255), (0, 193), (63, 255))
        cases = [(level, expected, prior) for level, expected in levels
                 for prior in (0, 1, 2, 3, 16, 64, 128, 255)]
        rows = [dict(case=n, joystick_level=level, expected=expected, psg_before=prior,
                     ppi_before=prior ^ 0xa0, actual=expected, ppi_after=prior ^ 0xa0,
                     psg_after=prior) for n, (level, expected, prior) in enumerate(cases)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'joystick.tsv'
            def write(data):
                with path.open('w') as stream:
                    writer = csv.DictWriter(stream, fieldnames=rows[0], delimiter='\t')
                    writer.writeheader()
                    writer.writerows(data)
            write(rows)
            report = analyze_joystick(path)
            self.assertTrue(report['joystick_directions_verified'])
            self.assertFalse(report['physical_controller_verified'])
            self.assertFalse(report['gameplay_verified'])
            write(rows[:-1])
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                analyze_joystick(path)
            for field in ('joystick_level', 'expected', 'actual', 'ppi_after', 'psg_after'):
                data = [dict(row) for row in rows]
                data[8][field] ^= 1
                write(data)
                with self.assertRaisesRegex(ValueError, 'failed'):
                    analyze_joystick(path)


if __name__ == '__main__':
    unittest.main()

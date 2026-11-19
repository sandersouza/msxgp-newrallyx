"""Assemble authored workers with synthetic symbols; no arcade payloads."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from compact_game_build import symbols


@unittest.skipUnless((ROOT/'.tools/sjasmplus/1.24.0/sjasmplus').exists(),'assembler unavailable')
class FixedRamLifetimes(unittest.TestCase):
    def test_active_workers_survive_full_smoke_list_and_end_before_live_turbo(self):
        # The maximal sparse smoke list owns0800..13FF during active play.
        # Cold constructors may share it; no hot accessor/IRQ/state byte may.
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            aliases={'GameSession_MapSegments':0xc0d1,'GameAuto_MemoryKiB':0x7e0,
                     'GameAuto_FormatStatus':0x100,'clock_ticks':0xc022,'Session_State':0xc7d0,
                     'GameSession_LatchKeys':0x5000,'ring_y':0xc031,'ring_x':0xc030,
                     'ring_length':0xc032,'ring_rest':0xc036,'maprow':0xc008,
                     'Game_PatchOne':0x5010,'Compact_Banks':0x7000,'Compact_Maps':0x7100,
                     'PLAIN_REG0':0x6000,'PLAIN_REG1':0x6800,'PLAIN_REG2':0x7000,'PLAIN_REG3':0x7800}
            source='\n'.join(f'{n} EQU {v}' for n,v in aliases.items())
            source+='\n OUTPUT "workers.bin"\n ORG $0800\n'
            source+=f' INCLUDE "{ROOT}/src/screen4/session-fixedram-cold.inc"\nColdEnd:\n ORG $2900\n'
            source+=f' INCLUDE "{ROOT}/src/screen4/session-fixedram-hot.inc"\nHotEnd:\n ORG $c250\n INCLUDE "{ROOT}/src/screen4/session-fixedram-irq.inc"\nIRQEnd:\n'
            (out/'workers.asm').write_text(source)
            p=subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),'--nologo','--sym=workers.sym','workers.asm'],cwd=out,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,(p.stdout+p.stderr)[-1800:])
            s=symbols(out/'workers.sym')
            self.assertLessEqual(s['ColdEnd'],0x1400)
            self.assertLessEqual(s['HotEnd'],0x2b00)
            self.assertTrue(0xc250<=s['GamePlain_IRQ']<s['IRQEnd']<=0xc400)
            for n in ['GamePlain_Ram','GamePlain_Rom','GamePlain_LoadRun',
                      'GamePlain_LoadColumns','GamePlain_Address','GamePlain_RestoreOne',
                      'GamePlain_RamValue','GamePlain_RomValue']:
                self.assertTrue(0x2900<=s[n]<s['HotEnd'],n)
            for n in ['GamePlain_Init','GamePlain_CopyMap','GamePlain_MapContinue','GamePlain_PatchObject']:
                self.assertTrue(0x800<=s[n]<s['ColdEnd'],n)

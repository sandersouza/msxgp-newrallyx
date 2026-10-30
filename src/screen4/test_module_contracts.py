"""Binary/map drift guards and independently includable synthetic mechanisms."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from module_contracts import (HERE, symbols, symbol_digest, validate_registry, verify_image)


class ContractGuards(unittest.TestCase):
    def test_symbol_layout_ignores_listing_order_but_detects_address_changes(self):
        a=symbols('start: EQU 0x4000\nstate: EQU 0xc000\n')
        b=symbols('state: EQU 0xC000\nstart: EQU 0x4000\n')
        self.assertEqual(symbol_digest(a),symbol_digest(b))
        b['state']+=1
        self.assertNotEqual(symbol_digest(a),symbol_digest(b))
        with self.assertRaises(ValueError):symbols('')
        with self.assertRaises(ValueError):symbols('x: EQU 0x0000\nx: EQU 0x0001\n')

    def test_same_size_opcode_change_and_non_emitted_alias_drift_are_rejected(self):
        data=b'\x00\xc9';table={'entry':0x4000,'scratch':0xc000}
        baseline=dict(bytes=2,sha256=hashlib.sha256(data).hexdigest(),symbol_count=2,
                      symbols_sha256=symbol_digest(table))
        verify_image(data,table,baseline)
        with self.assertRaises(ValueError):verify_image(b'\x76\xc9',table,baseline)
        with self.assertRaises(ValueError):verify_image(data,dict(table,scratch=0xc001),baseline)

    def test_registry_requires_real_entries_complete_abi_and_known_profiles(self):
        registry=json.loads((HERE/'modules/contracts.json').read_text())
        validate_registry(registry)
        for field,value in (('entry','modules/missing.inc'),('profiles',['missing']),('inputs','')):
            broken=json.loads(json.dumps(registry));broken['modules'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate_registry(broken)


class StandaloneMechanisms(unittest.TestCase):
    assembler=HERE.parents[1]/'.tools/sjasmplus/1.24.0/sjasmplus'

    def assemble(self,text,directory,name):
        source=directory/(name+'.asm');source.write_text(text)
        result=subprocess.run([str(self.assembler),'--nologo',str(source)],cwd=directory,
                              capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return (directory/(name+'.bin')).read_bytes()

    def test_transfer_facade_has_identical_bytes_and_no_native_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            def source(name,include):return f' OUTPUT "{name}.bin"\n ORG $4000\n INCLUDE "{include}"\n'
            facade=self.assemble(source('facade',HERE/'modules/vdp/transfers.inc'),directory,'facade')
            direct=self.assemble(source('direct',HERE/'game-packet-fast.inc'),directory,'direct')
            self.assertEqual(facade,direct)
            self.assertGreater(len(facade),0)

    def test_mapper_can_use_host_ram_aliases_without_linking_native_game(self):
        with tempfile.TemporaryDirectory() as temporary:
            text=f''' OUTPUT "mapper.bin"
 ORG $4000
GameSession_MainSegment EQU $d010
GameSession_MapSegments EQU $d020
 INCLUDE "{HERE/'modules/mapper/page0.inc'}"
'''
            raw=self.assemble(text,Path(temporary),'mapper')
            self.assertIn(b'\x3a\x10\xd0',raw)
            self.assertLess(len(raw),256)


if __name__=='__main__':
    unittest.main()

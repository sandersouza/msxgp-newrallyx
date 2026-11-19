"""Synthetic relocation checks; never embed contributor game/OS data."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mapper512_game import boot_owner,repack_atlas,reuse_phase_target,object_templates,OBJECT_BASES


class NativeBootLayout(unittest.TestCase):
    phase='GameSession_PhaseSelect:\n    ld b,a\n    call Mapper512_SelectBank\n.selected:\n    ld a,(phase)\n    or $c0\n    ret\n'

    def test_four_object_kinds_are_complete_and_theme_stride_matches(self):
        themes=[]
        for theme in range(4):
            raw=bytearray(16384)
            for kind in range(4):raw[0x2800+kind*9:0x2800+(kind+1)*9]=bytes([theme*4+kind])*9
            themes.append(bytes(raw))
        packed=object_templates(themes)
        self.assertEqual(len(packed),144)
        for theme in range(4):
            for kind in range(4):
                at=OBJECT_BASES[theme]-OBJECT_BASES[0]+kind*9
                self.assertEqual(packed[at:at+9],bytes([theme*4+kind])*9)
        self.assertLessEqual(OBJECT_BASES[-1]+36,0xbe40)

    def test_object_template_source_must_cover_every_kind_and_theme(self):
        for themes in [[],[bytes(16384)]*3,[bytes(0x2823)]*4]:
            with self.assertRaises(ValueError):object_templates(themes)

    def test_phase_target_contract_rejects_explicit_and_implicit_b_writers(self):
        for instruction in ['ld b,0','ld bc,0','pop bc','exx','inc bc','dec b','srl b','set 2,b','ldir','djnz .selected']:
            with self.assertRaises(ValueError):reuse_phase_target(self.phase.replace('.selected:',f'    {instruction}\n.selected:'))

    def test_phase_target_contract_rejects_an_unclassified_callee(self):
        with self.assertRaises(ValueError):reuse_phase_target(self.phase.replace('call Mapper512_SelectBank','call Unknown'))

    def test_phase_target_contract_accepts_reads_and_preserves_single_exit_extent(self):
        result=reuse_phase_target(self.phase.replace('.selected:','    cp b\n.selected:'))
        self.assertIn('    ld b,a\n',result)
        self.assertIn('    call Mapper512_SelectBank\n',result)
        self.assertTrue(result.endswith('    defs 2,0 ; Retain downstream API addresses after the shorter load.\n'))

    def test_workers_descriptors_and_atlas_relocate_together(self):
        raw=bytes([17])*16384;linked=bytearray([255])*16384
        for at,tag in [(0,b'WORKER'),(0x1000,b'DESCRIPTOR'),(0x1200,b'ATLAS')]:
            linked[at:at+len(tag)]=tag
        owner=boot_owner(raw,linked,8704)
        self.assertEqual(owner[:4096],raw[:4096])
        for at,tag in [(0x1000,b'WORKER'),(0x2000,b'DESCRIPTOR'),(0x2200,b'ATLAS')]:
            self.assertEqual(owner[at:at+len(tag)],tag)
        self.assertEqual(owner[4096+8704:],raw[4096+8704:])

    def test_invalid_relocation_cannot_expand_the_owner(self):
        for raw,linked,n in [(b'',bytes(16384),1),(bytes(16384),b'',1),
                             (bytes(16384),bytes(16384),12289)]:
            with self.assertRaises(ValueError):boot_owner(raw,linked,n)

    def test_all_tile_encodings_and_duplicate_pointers_survive_repacking(self):
        rom=bytearray(32768);payloads=[b'\xc1',bytes([64])+bytes(range(8)),
                                    bytes([1])+bytes(range(16)),bytes([255])+bytes(range(32))]
        for i,payload in enumerate(payloads+[payloads[0]]):
            at=256+i*64;rom[i*3:i*3+3]=bytes([0])+int(0x8000+at).to_bytes(2,'little')
            rom[at:at+len(payload)]=payload
        stream=b'\x02\x00\x00\x00\x03\x00';rom[1000:1000+len(stream)]=stream
        pages,frames,info=repack_atlas(bytes(rom),0,0x8000,5,[(0,0x8000+1000,12)])
        self.assertEqual(pages[0][:3],pages[0][12:15])
        bank,address,hold=frames[0]
        self.assertEqual(pages[bank-21][address-0x8000:address-0x8000+len(stream)],stream)
        self.assertEqual(hold,12)
        self.assertEqual(info['unique_tile_bytes'],sum(map(len,payloads)))


if __name__=='__main__':unittest.main()

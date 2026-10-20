"""Assemble synthetic scenes and verify real bank boundaries/reproducibility."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from PIL import Image
from scripts.msx.build import build, destination
from scripts.scenes.storage import json_write, seal

ROOT=Path(__file__).resolve().parents[1]
ASSEMBLER=ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'


class BuildTests(unittest.TestCase):
    @unittest.skipUnless(ASSEMBLER.is_file(),'Run make environment for pinned assembler integration')
    def test_synthetic_rom_bank_offsets_and_identical_rebuild(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            subprocess.run(['git','init','-q',str(root)],check=True)
            (root/'.gitignore').write_text('/references/**\n')
            (root/'src').mkdir()
            shutil.copyfile(ROOT/'src/static-scene.asm',root/'src/static-scene.asm')
            sources=[]
            for name,color in [('normal',(0,0,0)),('overlap',(255,0,0))]:
                source=root/'references'/name
                source.mkdir(parents=True)
                Image.new('RGB',(256,212),color).save(source/'preview.png')
                json_write(source/'layout.json',dict(name='compact',status='approved',
                           maze=dict(source=[12,6,212,218],destination=[0,0,200,212])))
                json_write(source/'comparison.json',dict(mismatches=0))
                seal(source)
                sources.append(source)
            first=build(root,*sources,root/'references/build/first',ASSEMBLER)
            second=build(root,*sources,root/'references/build/second',ASSEMBLER)
            data=first.read_bytes()
            self.assertEqual(data,second.read_bytes())
            self.assertEqual(len(data),128*1024)
            self.assertEqual(data[:2],b'AB')
            self.assertEqual(data[2:4],b'\x10\x40')
            self.assertEqual(data[16384:43520],bytes(27136))
            self.assertEqual(data[49152:76288],bytes([0x11])*27136)
            self.assertEqual(data[43520:49152],bytes([255])*5632)
            with self.assertRaisesRegex(ValueError,'exists'):
                build(root,*sources,first.parent,ASSEMBLER)

    def test_outputs_cannot_escape_ignored_build_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            for target in (root/'src/out',root/'references/build/../out'):
                with self.assertRaises(ValueError): destination(root,target)
            (root/'link').symlink_to(root,target_is_directory=True)
            with self.assertRaises(ValueError): destination(root,root/'link/references/build/out')


if __name__=='__main__': unittest.main()

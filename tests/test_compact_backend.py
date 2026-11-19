"""Synthetic lossless name-store optimization invariants; no game data."""
from pathlib import Path
import sys
import unittest
import tempfile
import json
import hashlib
from src.toolchain.msx.emulator import cartridge_mapper

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from renderer_window_probe import compact_name_stores
from renderer_image_build import compile_map_chunk


class NameStores(unittest.TestCase):
    def test_ordered_writes_and_final_hl_survive_repeated_load_elimination(self):
        body=bytearray()
        for n,value in enumerate([0x6060]*8+[0x6151]*3+[0x6060]*5):
            address=0xd400+n*2
            body.extend((0x21,value&255,value>>8,0x22,address&255,address>>8))
        body.append(0xc9)
        def execute(code):
            at=0;hl=None;writes=[]
            while code[at]!=0xc9:
                op=code[at];word=int.from_bytes(code[at+1:at+3],'little')
                if op==0x21:hl=word
                elif op==0x22:writes.append((word,hl))
                else:raise AssertionError(op)
                at+=3
            return writes,hl
        compact=compact_name_stores(body)
        self.assertEqual(execute(body),execute(compact))
        self.assertEqual(len(body)-len(compact),13*3)

    def test_unknown_or_truncated_instruction_rejected(self):
        for code in [b'',b'\x21\0\0',b'\x21\0\0\x32\0\xc0\xc9']:
            with self.assertRaises(ValueError):compact_name_stores(code)


class MapConstructors(unittest.TestCase):
    def test_byte_updates_and_pushes_match_all_synthetic_word_transitions(self):
        import random
        rng=random.Random(42)
        cases=[[0x1200+n for n in range(8)],[0x0034+n*256 for n in range(8)]]
        cases.extend([[rng.choice([0x1234,0x1256,0x7834,0x9abc]) for _ in range(8)] for _ in range(500)])
        for words in cases:
            raw=b''.join(w.to_bytes(2,'little') for w in words)
            code=compile_map_chunk(raw,0x4567);at=0;hl=0xdead;stack=bytearray(16);sp=16;cycles=0
            while code[at]!=0xc3:
                op=code[at];at+=1
                if op==0x21:hl=int.from_bytes(code[at:at+2],'little');at+=2;cycles+=10
                elif op==0x26:hl=(hl&255)|code[at]*256;at+=1;cycles+=7
                elif op==0x2e:hl=(hl&0xff00)|code[at];at+=1;cycles+=7
                else:
                    self.assertEqual(op,0xe5);sp-=2;stack[sp:sp+2]=hl.to_bytes(2,'little');cycles+=11
            self.assertEqual(stack,raw);self.assertEqual(sp,0)
            self.assertEqual(code[at:],b'\xc3\x67\x45')
            self.assertLessEqual(len(code),35);self.assertLessEqual(cycles,8*21)

    def test_equal_words_share_loads_without_assuming_entry_hl(self):
        for words in [[0x1234]*8,[0x1234]*4+[0x5678]*4,[0x1234,0x5678]*4]:
            raw=b''.join(w.to_bytes(2,'little') for w in words)
            code=compile_map_chunk(raw,0x4567);at=0;stack=bytearray(16);sp=16;hl=0xdead;loads=0
            while code[at]!=0xc3:
                if code[at]==0x21:hl=int.from_bytes(code[at+1:at+3],'little');at+=3;loads+=1
                else:
                    self.assertEqual(code[at],0xe5);at+=1;sp-=2
                    stack[sp:sp+2]=hl.to_bytes(2,'little')
            self.assertEqual(code[at:],b'\xc3\x67\x45')
            self.assertEqual(stack,raw);self.assertEqual(sp,0)
            self.assertEqual(loads,1+sum(a!=b for a,b in zip(words,words[1:])))

    def test_reverse_word_pushes_reproduce_chunk_and_only_use_bounded_language(self):
        chunk=bytes(range(16));code=compile_map_chunk(chunk,0x4567)
        self.assertEqual(len(code),35)
        self.assertEqual(code[32:],b'\xc3\x67\x45')
        memory=bytearray(16);sp=16
        for pc in range(0,32,4):
            self.assertEqual((code[pc],code[pc+3]),(0x21,0xe5))
            sp-=2;memory[sp:sp+2]=code[pc+1:pc+3]
        self.assertEqual(sp,0);self.assertEqual(memory,chunk)

    def test_invalid_chunk_or_continuation_rejected(self):
        for chunk,address in [(b'',0),(bytes(15),0),(bytes(17),0),(bytes(16),65536),(bytes(16),-1)]:
            with self.assertRaises(ValueError):compile_map_chunk(chunk,address)


class MapperSelection(unittest.TestCase):
    def test_metadata_matches_exact_image_and_cannot_rebind_neighbor(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);current=root/'newrallyx.rom';other=root/'other.rom'
            current.write_bytes(b'new');other.write_bytes(b'old')
            (root/'manifest.json').write_text(json.dumps(dict(mapper='ASCII8',rom_sha256=hashlib.sha256(b'new').hexdigest())))
            self.assertEqual(cartridge_mapper(current),'ASCII8')
            self.assertEqual(cartridge_mapper(other),'ASCII16')


if __name__=='__main__':unittest.main()

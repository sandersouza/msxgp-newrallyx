"""Synthetic source slots and suffix-linker tests; no original game data."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mapper512_backend import compile_relative,events,pack_record,suffix_graph,suffix_windows,instructions,absolute_programs,flat_windows,cycles
from compact_transfer import optimize


def record():
    raw=bytearray(4096);busy=bytearray(4096)
    for begin,size in [(0,64),(0x100,328),(0x300,328),(0x500,240),(0x710,192),(0x800,65),(0x900,65),(0xa00,65),(0xb00,65)]:
        for n in range(size):raw[begin+n]=(n*19+begin//256)&255
        busy[begin:begin+size]=b'\1'*size
    return dict(kind='hud',bank=4,data=raw,occupied=busy)


class RelativeSlots(unittest.TestCase):
    def test_source_pair_parity_disappears_and_all_eight_slots_remain_exact(self):
        r=record();codes=[]
        for parity in (0,1):
            base=0x8000+parity*4096
            code=b'\x0e\x98\x21'+(base+0x100).to_bytes(2,'little')+b'\x06\x10\xcd\x34\x12'
            code+=b'\x21'+(base+0x300).to_bytes(2,'little')+b'\xed\xa3'*5+b'\xc3\0\xc0'
            codes.append(compile_relative(code,r,parity))
        self.assertEqual(*codes)
        for slot in range(8):
            base=0x8000+slot*2048;d=base>>8;e=d+2
            ops,hl,b=events(codes[0],d,e)
            self.assertEqual([v[1] for v in ops if v[0]=='data'],list(range(base,base+16))+list(range(base+512,base+517)))
            self.assertEqual(hl,base+517);self.assertEqual(b,('zero',251))

    def test_every_live_metadata_and_pixel_byte_survives_declared_repacking(self):
        r=record();data,busy,locations=pack_record(r)
        self.assertEqual(len(data),2048);self.assertEqual(sum(busy),sum(r['occupied']))
        occupied=set()
        for old,new,size in locations:
            self.assertEqual(data[new:new+size],r['data'][old:old+size])
            self.assertFalse(occupied.intersection(range(new,new+size)));occupied.update(range(new,new+size))
        self.assertEqual(data[:328],r['data'][0x100:0x248]);self.assertEqual(data[512:840],r['data'][0x300:0x448])

    def test_stage_ranking_keeps_current_table_and_pixel_addresses_without_discarding_other_live_fields(self):
        r=record();original=pack_record(r)
        for layout in range(4):
            data,busy,locations=pack_record(r,ranking_layout=layout)
            self.assertEqual(sum(busy),sum(original[1])-195)
            self.assertEqual(data[:328],original[0][:328]);self.assertEqual(data[512:840],original[0][512:840])
            self.assertEqual(data[1024:1089],r['data'][0x800+layout*256:0x841+layout*256])
            for old,new,size in locations:self.assertEqual(data[new:new+size],r['data'][old:old+size])
            retained=set(i for old,_,size in locations for i in range(old,old+size))
            removed=set(i for other in range(4) if other!=layout for i in range(0x800+other*256,0x841+other*256))
            self.assertEqual(retained,{i for i,v in enumerate(r['occupied']) if v}-removed)
        with self.assertRaises(ValueError):pack_record(r,ranking_layout=4)


class SuffixLinker(unittest.TestCase):
    def test_terminal_jump_is_inlined_and_shared_tails_keep_original_instruction_order(self):
        programs=[b'\x0e\x98\x62\x2e'+bytes((n,))+b'\xed\xa3'*5+b'\xc3\0\xc0' for n in range(10)]
        image,entries,jumps=suffix_graph(programs,exit_address=0xc123)
        for code in programs:
            pc=entries[code];seen=[];joins=0
            for _ in range(100):
                at=pc-0x4000;op=image[at]
                if op==0xc3:
                    target=int.from_bytes(image[at+1:at+3],'little')
                    if target==0xc123:seen.append(b'\xc3\0\xc0');break
                    self.assertGreaterEqual(target,0x4000);self.assertLess(target,0x4000+len(image));pc=target;joins+=1;continue
                ins=instructions(image[at:])[0];seen.append(ins);pc+=len(ins)
            else:self.fail('Suffix chain did not terminate')
            self.assertEqual(tuple(seen),instructions(code));self.assertEqual(joins,jumps[code])
        empty=b'\x0e\x98\xc3\0\xc0'
        _,_,jump_count=suffix_graph([empty])
        self.assertEqual(jump_count[empty],0)

    def test_each_window_has_complete_local_closure_and_deterministic_linkage(self):
        programs=[b'\x3e'+bytes((n,))+b'\xed\xa3'*20+b'\xc3\0\xc0' for n in range(30)]
        windows=suffix_windows(programs,limit=100)
        self.assertGreater(len(windows),1)
        self.assertEqual(sum(len(w['entries']) for w in windows),len(programs))
        for window in windows:
            self.assertLessEqual(len(window['data']),100)
            image=window['data']
            for ins in instructions(image):
                if ins[0]==0xc3:
                    target=int.from_bytes(ins[1:],'little')
                    self.assertTrue(target==0xc000 or 0x4000<=target<0x4000+len(image))
        self.assertEqual([w['data'] for w in windows],[w['data'] for w in suffix_windows(reversed(programs),limit=100)])


class ColdAbsoluteLinker(unittest.TestCase):
    def test_all_slots_preserve_video_events_and_baseline_body_cycles_without_de_inputs(self):
        records=[record() for _ in range(8)];cases=[]
        header=bytes.fromhex('0e98 f3 3a27c0 f600 d399 3e8e d399 3e10 d399 3e43 d399 fb')
        for slot in range(8):
            base=0x8000+(slot%2)*4096
            code=header+b'\x21'+(base+0x100).to_bytes(2,'little')+b'\x06\x20\xcd\x34\x12'
            code+=b'\x21'+(base+0x300).to_bytes(2,'little')+b'\xed\xa3'*7+b'\xc3\0\xc0'
            baseline,_=optimize(code)
            cases.append(dict(code=code,record=slot,slot=slot,baseline_cycles=cycles(baseline),relative=compile_relative(code,records[slot],slot)))
        common=absolute_programs(cases,records)
        self.assertEqual(common,header[:14])
        for row in cases:
            self.assertEqual(cycles(common+row['absolute']),row['baseline_cycles'])
            self.assertFalse(any(i in (b'\x62',b'\x63') for i in instructions(row['absolute'])))

    def test_empty_packet_keeps_iff_and_has_no_hoisted_vdp_header(self):
        code=b'\x0e\x98\xc3\0\xc0';full=bytes.fromhex('0e98 f3 3a27c0 f600 d399 3e8e d399 3e10 d399 3e43 d399 fb')
        full+=b'\x21\0\x81'+b'\xed\xa3'*2+b'\xc3\0\xc0'
        rows=[]
        for raw in [code,full]:
            baseline,_=optimize(raw)
            rows.append(dict(code=raw,record=0,slot=0,baseline_cycles=cycles(baseline),relative=compile_relative(raw,record(),0)))
        absolute_programs(rows,[record()])
        self.assertEqual(rows[0]['absolute'],code)

    def test_flat_link_has_no_extra_jumps_and_each_body_stays_contiguous(self):
        programs=[b'\x3e'+bytes((n,))+b'\xed\xa3'*8+b'\xc3\0\xc0' for n in range(30)]
        windows=flat_windows(programs,limit=100,exit_address=0xc123)
        self.assertGreater(len(windows),1)
        for window in windows:
            self.assertLessEqual(len(window['data']),100)
            for code,entry in window['entries'].items():
                at=entry-0x4000;linked=bytes(window['data'][at:at+len(code)])
                self.assertEqual(linked,code[:-2]+b'\x23\xc1')
                self.assertEqual(window['jumps'][code],0)
        again=flat_windows(reversed(programs),limit=100,exit_address=0xc123)
        self.assertEqual([w['data'] for w in windows],[w['data'] for w in again])

    def test_flat_link_rejects_oversized_code_and_invalid_windows(self):
        with self.assertRaises(ValueError):flat_windows([b'\0'*101],limit=100)
        with self.assertRaises(ValueError):flat_windows([],limit=0)
        with self.assertRaises(ValueError):flat_windows([],limit=16385)


if __name__=='__main__':unittest.main()

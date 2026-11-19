"""Repack/decode hot transfers into hypothetical8KiB windows, without a ROM.

This is a reversible storage/linkage experiment, not an executable backend.
Only LD HL source operands move. The independent decoder checks all VDP
writes, literal bytes, normalized instructions and estimated instruction costs.
Host fields/mapper consumers still require adaptation and native timing tests.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/toolchain/screen4'), str(ROOT)]
from rom_audit import decode_transfer


def compact_name_stores(code):
    """Remove repeated LD HL immediates, preserving every ordered RAM store.

    Input is the bounded LD-HL/LD-(nn)-HL/RET generator language. Output keeps
    final HL, flags, IFF and all writes; other registers remain untouched.
    """
    result=bytearray();previous=None
    if not code or code[-1]!=0xc9 or (len(code)-1)%6:raise ValueError('Invalid name-store body')
    for at in range(0,len(code)-1,6):
        if code[at]!=0x21 or code[at+3]!=0x22:raise ValueError('Unexpected name-store instruction')
        value=code[at+1:at+3]
        if value!=previous:result.extend(code[at:at+3]);previous=value
        result.extend(code[at+3:at+6])
    result.append(0xc9);return bytes(result)


def relocate(code, tables):
    result = bytearray(code)
    at = 0
    while at < len(result):
        op = result[at]
        width = (3 if op in (0x3a,0x21,0xcd,0xc3) else
                 2 if op in (0x0e,0x3e,0xf6,0xe6,0xd3,0x06,0xed) else 1)
        if op == 0x21:
            address = int.from_bytes(result[at+1:at+3],'little')
            matches = [new+address-old for old,new,data in tables
                       if old <= address < old+len(data)]
            assert len(matches)==1, ('Unowned transfer source',hex(address))
            result[at+1:at+3]=matches[0].to_bytes(2,'little')
        at += width
    assert at == len(result)
    return result


def probe(data_stride=8192, artifacts=None, records=None, integrated=False, bundle=None, *, fast_transfers=False):
    bundle = Path(bundle or ROOT/'references/build/game').resolve()
    rom = (bundle/'newrallyx.rom').read_bytes()
    session = json.loads((bundle/'session-build.json').read_text())
    symbols = json.loads((bundle/'hud-programs.json').read_text())['linked_symbols']
    rows = []
    split = []
    code_pool = {}
    for kind, banks in (('hud',range(4,68)),('edge',session['edge_banks'])):
        for bank in banks:
            old = rom[bank*16384:(bank+1)*16384]
            image = bytearray(b'\xff'*16384)
            base = 0 if kind=='hud' else 8192
            cpu = 0x8000+base
            tables = []
            record=bytearray(b'\xff'*4096)
            occupied=bytearray(4096)

            def copy(start,end,target,table=False):
                data=old[start:end]
                image[base+target:base+target+len(data)]=data
                assert target+len(data)<=4096
                record[target:target+len(data)]=data
                occupied[target:target+len(data)]=b'\x01'*len(data)
                if table: tables.append((0x8000+start,cpu+target,data))

            if kind=='hud':
                count=old[0x900]
                copy(0,256,0)
                copy(0x100,0x100+count*8,0x100,True)
                copy(0x500,0x500+count*8,0x300,True)
                copy(0x900,0x901,0x500)
                copy(0x2300,0x2300+505,0x510)
                # Full-session flag names are supplied by the native adapter;
                # the historical empty radar-name worker is a single RET.
                assert old[0x2700]==0xc9
                copy(0x2700,0x2701,0xc00)
                for layout in range(4):
                    copy(0x3800+layout*256,0x3800+layout*256+65,0x800+layout*256)
                pointer_old,pointer_new,entries,cursor=0x2600,0x710,64,0xc10
                if integrated:
                    # Raw names are replaced by the bounded phase binding;
                    # uniform metadata has one byte-identical resident copy.
                    occupied[:256]=b'\0'*256
                    occupied[:64]=b'\x01'*64
                    # Replace the separate resident guard-column worker with
                    # identical immediate names appended to the phase program.
                    guard=bytearray()
                    previous=None
                    for row in range(28):
                        target=0xd400+row*32
                        value=old[row*7+6]
                        if value!=previous:guard.extend((0x3e,value));previous=value
                        guard.extend((0x32,target&255,target>>8))
                    guard.append(0xc9)
                    record[0xd10:0xd10+len(guard)]=guard
                    occupied[0xd10:0xd10+len(guard)]=b'\x01'*len(guard)
                    odd=(list(banks).index(bank)%2)*4096
                    entry=0x8d10+odd
                    names=compact_name_stores(old[0x2300:0x2300+505])[:-1]+bytes((0xc3,entry&255,entry>>8))
                    record[0x510:0x510+len(names)]=names
                    occupied[0x510:0x70b]=b'\0'*(0x70b-0x510)
                    occupied[0x510:0x510+len(names)]=b'\x01'*len(names)
            else:
                a,b=old[0xf00],old[0x1500]
                copy(0xa00,0xa00+64,0)
                copy(0x1000,0x1000+64,0x100)
                for source,count,target in ((0xb00,a,0x200),(0xd00,a,0x400),
                                            (0x1100,b,0x600),(0x1300,b,0x800)):
                    copy(source,source+count*8,target,True)
                copy(0xf00,0xf01,0xa00)
                copy(0x1500,0x1501,0xa01)
                pointer_old,pointer_new,entries,cursor=0x2900,0xa10,9,0xa40
            occupied[pointer_new:pointer_new+entries*3]=b'\x01'*(entries*3)
            programs={}
            references=[]
            for n in range(entries):
                source_bank,lo,hi=old[pointer_old+n*3:pointer_old+n*3+3]
                assert source_bank == bank
                address=lo+hi*256
                if address not in programs:
                    decoded=decode_transfer(rom,bank,address,inline_literals=False,
                        exit_address=symbols['hud_upload.done'],transfer_address=symbols['GamePacketFast_Transfer'])
                    code=rom[decoded['offset']:decoded['offset']+decoded['code_bytes']]
                    changed=relocate(code,tables)
                    programs[address]=(cpu+cursor,decoded)
                    image[base+cursor:base+cursor+len(changed)]=changed
                    cursor+=len(changed)
                references.append(programs[address])
            for n,(address,_) in enumerate(references):
                at=base+pointer_new+n*3
                image[at:at+3]=bytes((0,address&255,address>>8))
            fits=cursor<=8192
            if fits:
                for address,decoded in references:
                    checked=decode_transfer(bytes(16384)+bytes(image),1,address,inline_literals=False,
                        exit_address=symbols['hud_upload.done'],transfer_address=symbols['GamePacketFast_Transfer'])
                    assert checked['normalized_sha256']==decoded['normalized_sha256']
                    assert checked['estimated_instruction_cycles']==decoded['estimated_instruction_cycles']
            # Split data/code windows: move edge data into the lower window
            # too, and rebind only source operands. The upper window can now
            # share exact machine-code programs across different phase data.
            data_image = bytearray(16384)
            split_tables=[]
            for old_address,new_address,data in tables:
                paired_offset=((list(banks).index(bank)%2)*4096 if data_stride==4096 else 0)
                destination=new_address-base+paired_offset
                data_image[destination-0x8000:destination-0x8000+len(data)]=data
                split_tables.append((old_address,destination,data))
            paired_offset=((list(banks).index(bank)%2)*4096 if data_stride==4096 else 0)
            if kind=='hud' and not integrated:
                # Name stores contain immediate name pairs and RAM targets,
                # hence relocation must leave both operands byte-identical.
                for at in range(0x510,0x510+504,6):
                    assert record[at]==0x21 and record[at+3]==0x22
            if records is not None:
                records.append(dict(kind=kind,bank=bank,data=record,occupied=occupied,
                                    pointer_offset=pointer_new,entries=entries))
            for index,(_,decoded) in enumerate(references):
                old_code=rom[decoded['offset']:decoded['offset']+decoded['code_bytes']]
                changed=relocate(old_code,split_tables)
                assert len(changed)<=8192
                data_image[8192:8192+len(changed)]=changed
                checked=decode_transfer(bytes(16384)+bytes(data_image),1,0xa000,
                    inline_literals=False,exit_address=symbols['hud_upload.done'],
                    transfer_address=symbols['GamePacketFast_Transfer'])
                assert checked['normalized_sha256']==decoded['normalized_sha256']
                assert checked['estimated_instruction_cycles']==decoded['estimated_instruction_cycles']
                optimization={}
                if fast_transfers:
                    from compact_transfer import optimize,events
                    optimized,optimization=optimize(changed)
                    assert events(optimized)==events(changed),'Specialization changed source/control events or final HL/B'
                    changed=optimized
                code_pool[bytes(changed)]=len(changed)
                if artifacts is not None:
                    artifacts.append(dict(record=len(rows),
                        code=bytes(changed),
                        index=index,original_bank=bank,
                        original_offset=decoded['offset'],
                        estimated_cycles=decoded['estimated_instruction_cycles'],
                        optimization=optimization,
                        writes=[(s['destination'],rom[s['literal_offset']:s['literal_offset']+s['bytes']]) for s in decoded['literal_spans']]))
                split.append(dict(kind=kind,bank=bank,code_sha256=hashlib.sha256(changed).hexdigest()))
            rows.append(dict(kind=kind,original_bank=bank,used_window_bytes=cursor,
                             fits_8k=fits,unique_programs=len(programs),references=entries,
                             decoded_equivalence_checked=fits))
    pages=[]
    for code,size in sorted(code_pool.items(),key=lambda item:(-item[1],item[0])):
        choices=[(8192-used-size,n) for n,used in enumerate(pages) if used+size<=8192]
        if choices:
            _,n=min(choices);pages[n]+=size
        else:pages.append(size)
    split_report=dict(references_checked=len(split),unique_code_programs=len(code_pool),
        unique_code_bytes=sum(code_pool.values()),code_pages_8k=len(pages),
        code_allocated_bytes=len(pages)*8192,
        data_pages_8k=96*data_stride//8192,data_allocated_bytes=96*data_stride,
        hot_allocated_bytes=96*data_stride+len(pages)*8192,
        remaining_bytes_below_1mib=1048576-1-96*data_stride-len(pages)*8192,
        paired_data_fields=data_stride==4096,
        instruction_and_vdp_payload_equivalence=True,
        caveat='No executable backend. Host mapper writes, native/audio16KiB mapping, IRQ ownership, data-field liveness, cold allocation and full-frame timing remain unverified.')
    return dict(rom_sha256=hashlib.sha256(rom).hexdigest(),windows=rows,
        window_count=len(rows),fits_8k=sum(r['fits_8k'] for r in rows),
        largest_window=max(r['used_window_bytes'] for r in rows),
        total_hot_used_bytes=sum(r['used_window_bytes'] for r in rows),
        padded_hot_8k_bytes=sum((r['used_window_bytes']+8191)//8192*8192 for r in rows),
        shared_ring_worker_bytes=json.loads((bundle/'ring-refresh.json').read_text())['bytes'],
        split_data_code_window_probe=split_report,
        scope='Hypothetical relocated hot windows only. Legacy phase edge atlases and diagnostic R18 atlas omitted under a liveness hypothesis; full-session consumers have NOT been relinked or executed. Shared ring worker and all cold/UI/audio/gameplay data require separate allocation. Not a sub1MiB ROM or timing acceptance.')


if __name__=='__main__':
    result=probe()
    result['paired_4k_data_probe']=probe(4096)['split_data_code_window_probe']
    path=ROOT/'docs/measurements/cartridge/issue41-window-probe.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='windows'},indent=2))

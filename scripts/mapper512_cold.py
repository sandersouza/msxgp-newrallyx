"""Build a cartridge-free DOS1/BASIC cold-I/O experiment in declared RAM holes.

Not a runnable game: native bootstrap/F10 presentation and lifecycle callbacks
remain separate. Real filesystem reads install the unchanged active bank bytes
while the OS lives temporarily in stopped flag caches4/5. Inputs are contributor
builds; all generated game/OS payloads remain ignored under references/build.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from mapper512_integrate import common_free_regions
from disk_package import compress_bank,decompress_bank
from compact_game_build import symbols

OUT=ROOT/'references/build/game-mapper512-cold'
BRIDGE_BANK=30;BRIDGE_START=0x1000;BRIDGE_END=0x3c00


def allocate_context(regions,size=32768,reserved=tuple((b,0,16384) for b in range(20,30))+((30,0x1000,0x2e40),)):
    """Pack two OS pages only in declared common holes; split logical pages.

    Return (bank,offset,length,OS CPU source) rows. No scan of image byte values.
    Reservations use (bank,offset,length); failure produces no partial result.
    """
    if size not in (32768,49152):raise ValueError('Two OS pages and optional one world shadow are required')
    declared=bytearray(524288)
    for bank,offset,length in regions:
        if not 0<=bank<32 or offset<0 or length<=0 or offset+length>16384:raise ValueError('Invalid declared hole')
        at=bank*16384+offset
        if any(declared[at:at+length]):raise ValueError('Overlapping declared holes')
        declared[at:at+length]=b'\1'*length
    available=[]
    for bank,offset,length in regions:
        spans=[(offset,offset+length)]
        for b,start,n in reserved:
            if b!=bank:continue
            spans=[part for lo,hi in spans for part in [(lo,min(hi,start)),(max(lo,start+n),hi)] if part[0]<part[1]]
        available.extend((bank,lo,hi-lo) for lo,hi in spans if hi-lo>=16)
    available.sort(key=lambda r:(-r[2],r[0],r[1]))
    allocated=[];done=0
    for bank,offset,length in available:
        while length and done<size:
            n=min(length,size-done,16384-done%16384)
            source=(0,0xc000,0)[done//16384]+done%16384
            allocated.append((bank,offset,n,source));offset+=n;length-=n;done+=n
        if done==size:return allocated
    raise ValueError('Declared holes cannot retain both OS pages')


def layout_source(context,map_stage,records,union):
    """Assembly metadata for the shared bounded decoder and masked installer."""
    inc=['Cold_Context:']
    for bank,offset,n,source in context:inc.extend([f' db {bank}',f' dw {source},{0x8000+offset},{n}'])
    inc+=['Cold_ContextEnd:','Cold_MapStage:']
    for bank,offset,n,source in map_stage:inc.extend([f' db {bank}',f' dw {source},{0x8000+offset},{n}'])
    inc+=['Cold_MapStageEnd:',f'Cold_ResourceCount EQU {len(records)}','Cold_Resources:']
    for r in records:inc.extend([f' db {r["bank"]}',f' dw {r["compressed"]},{r["checksum"]}',f' dd {r["offset"]}'])
    inc+=['Cold_CopyDirectory:']+[f' dw Cold_Copy{b}' for b in range(32)]
    for bank in range(32):
        inc.append(f'Cold_Copy{bank}:');start=0
        while start<16384:
            if not union[bank*16384+start]:start+=1;continue
            end=start+1
            while end<16384 and union[bank*16384+end]:end+=1
            inc.append(f' dw {start},{end-start}');start=end
        inc.append(' dw 0,0')
    return '\n'.join(inc)+'\n'


def build(batching=True):
    out=OUT if batching else OUT.with_name(OUT.name+'-per-resource')
    bundle=ROOT/'references/build/game-mapper512-integrated';manifest=json.loads((bundle/'integration.json').read_text())
    images=[(bundle/f'stage-{i}/hot-image.bin').read_bytes() for i in range(4)]
    masks=[(bundle/f'stage-{i}/live-mask.bin').read_bytes() for i in range(4)]
    layout=json.loads((bundle/'live-layout.json').read_text())
    assert layout['program_images']==[r['sha256'] for r in manifest['stages']]
    assert layout['mask_sha256']==[hashlib.sha256(m).hexdigest() for m in masks]
    for r,image in zip(manifest['stages'],images):assert hashlib.sha256(image).hexdigest()==r['sha256']
    regions=common_free_regions(masks);allocated=allocate_context(regions,size=49152)
    context=[];map_stage=[];done=0
    for row in allocated:
        (context if done<32768 else map_stage).append(row);done+=row[2]
    # Copy the union of live fields. A whole-bank overwrite would destroy the
    # scattered OS snapshots or bridge when a family is replaced.
    union=bytearray(524288)
    for mask in masks:
        for i,v in enumerate(mask):union[i]|=v
    reserved=BRIDGE_BANK*16384+BRIDGE_START
    assert not any(union[reserved:BRIDGE_BANK*16384+0x3e40])
    for bank,offset,n,_ in allocated:assert not any(union[bank*16384+offset:bank*16384+offset+n])
    out.mkdir(parents=True,exist_ok=True);files=out/'files';files.mkdir(exist_ok=True)
    resource=bytearray(b'NRXCOLD1');records=[]
    # Initial family installs all hot owners; later families replace just the
    # specialized HUD, edges, packets and ring permissions. No assets in source.
    map_banks=json.loads((ROOT/'references/build/game/session-build.json').read_text())['map_banks']
    original=(ROOT/'references/build/game/newrallyx.rom').read_bytes()
    for family in range(4):
        for bank in range(6 if family==0 else 11,32):
            raw=images[family][bank*16384:(bank+1)*16384];packed=compress_bank(raw)
            assert len(packed)<=16384 and decompress_bank(packed)==raw
            records.append(dict(family=family,bank=bank,kind='hot',offset=len(resource),compressed=len(packed),checksum=sum(raw)&65535))
            resource.extend(packed)
        # Preserve map3 in scattered cold storage before the final map2 read
        # reuses both world segments as DMA/decode scratch. EndBatch restores it.
        for half,bank in [(1,3),(0,2)]:
            at=map_banks[family*2+half]*16384;raw=original[at:at+16384];packed=compress_bank(raw)
            assert len(raw)==16384 and len(packed)<=16384 and decompress_bank(packed)==raw
            records.append(dict(family=family,bank=bank,kind='map',offset=len(resource),compressed=len(packed),checksum=sum(raw)&65535))
            resource.extend(packed)
    # Wrap3->0 as an actual replacement, reusing the first family's on-disk
    # streams rather than storing a second copy of those payloads.
    records.extend(dict(r) for r in list(records) if r['family']==0 and (r['bank']>=11 or r['kind']=='map'))
    assert len(records)<256
    (files/'NRXCOLD.DAT').write_bytes(resource)
    inc=['Cold_Context:']
    for bank,offset,n,source in context:inc.extend([f' db {bank}',f' dw {source},{0x8000+offset},{n}'])
    inc+=['Cold_ContextEnd:','Cold_MapStage:']
    for bank,offset,n,source in map_stage:inc.extend([f' db {bank}',f' dw {source},{0x8000+offset},{n}'])
    inc+=['Cold_MapStageEnd:',f'Cold_ResourceCount EQU {len(records)}','Cold_Resources:']
    for r in records:inc.extend([f' db {r["bank"]}',f' dw {r["compressed"]},{r["checksum"]}',f' dd {r["offset"]}'])
    inc+=['Cold_CopyDirectory:']+[f' dw Cold_Copy{b}' for b in range(32)]
    for bank in range(32):
        inc.append(f'Cold_Copy{bank}:');start=0
        while start<16384:
            if not union[bank*16384+start]:start+=1;continue
            end=start+1
            while end<16384 and union[bank*16384+end]:end+=1
            inc.append(f' dw {start},{end-start}');start=end
        inc.append(' dw 0,0')
    (out/'cold-layout.inc').write_text('\n'.join(inc)+'\n')
    (out/'cold-mode.inc').write_text(f'COLD_BATCH EQU {int(batching)}\n')
    for name in ['mapper512-cold.asm','mapper512-cold-loader.asm']:shutil.copyfile(ROOT/'src/disk'/name,out/name)
    assembler=ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'
    for source in ['mapper512-cold.asm','mapper512-cold-loader.asm']:
        p=subprocess.run([str(assembler),'--nologo',f'--sym={source}.sym',source],cwd=out,capture_output=True,text=True)
        if p.returncode:raise RuntimeError((p.stdout+p.stderr)[-2000:])
        if source=='mapper512-cold.asm':
            (out/'cold-size.inc').write_text(f'COLD_BYTES EQU {(out/"cold.bin").stat().st_size}\n')
    bridge=(out/'cold.bin').read_bytes();loader=(out/'cold-loader.bin').read_bytes()
    assert len(bridge)<BRIDGE_END-BRIDGE_START
    stub=b'\x21\x11\x01\x11\0\xc1\x01'+struct.pack('<H',len(loader))+b'\xed\xb0\xc3\0\xc1\0\0\0'
    assert len(stub+loader+bridge)<0x3f00
    (files/'NRXCOLD.COM').write_bytes(stub+loader+bridge)
    basic_stub=stub.replace(b'\x21\x11\x01',b'\x21\x11\x80').replace(b'\xc3\0\xc1',b'\xc3\x04\xc1')
    basic=basic_stub+loader+bridge
    (files/'NRXCOLD.BIN').write_bytes(b'\xfe'+struct.pack('<HHH',0x8000,0x8000+len(basic)-1,0x8000)+basic)
    (files/'NRXCOLD.BAS').write_bytes(b'10 CLEAR 200,&HC0FF\r\n20 BLOAD "NRXCOLD.BIN",R\r\n\x1a')
    plan=dict(status='Cartridge-free cold I/O/OS-lifetime diagnostic, not standalone game',os_context_batching=batching,reference_rom_sha256=manifest['reference_rom_sha256'],
              active_images=manifest['stages'],context_bytes=32768,context_fragments=len(context),context=context,
              map_staging_bytes=16384,map_staging_fragments=len(map_stage),map_staging=map_stage,
              bridge=dict(bank=BRIDGE_BANK,offset=BRIDGE_START,bytes=len(bridge),reserved_end=0x3e40,sha256=hashlib.sha256(bridge).hexdigest()),
              loader_bytes=len(loader),resource_bytes=len(resource),resource_sha256=hashlib.sha256(resource).hexdigest(),records=records,
              declared_common_hole_bytes=sum(r[2] for r in regions),mask_sha256=layout['mask_sha256'],union_mask_sha256=hashlib.sha256(union).hexdigest())
    (out/'union-mask.bin').write_bytes(union);(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps({k:v for k,v in plan.items() if k not in ('context','map_staging','records','active_images')},indent=2));return plan


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--per-resource',action='store_true');a=p.parse_args();build(not a.per_resource)

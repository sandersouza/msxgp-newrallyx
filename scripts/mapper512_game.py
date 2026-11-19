"""Integrate native boot/lifecycle with the512KiB filesystem backend.

Only ignored experimental outputs change. Default744KiB cartridge, MegaRAM
and legacy executable stay sealed. Contributor-derived payloads never enter
source control. The boot atlas is repacked losslessly for16KiB RAM mapping.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from compact_game_build import symbols,replace
from mapper512_integrate import common_free_regions
from mapper512_cold import allocate_context,layout_source
from disk_package import compress_bank,decompress_bank

RUNTIME=ROOT/'references/build/game-mapper512-game-runtime'
OUT=ROOT/'references/build/game-mapper512-game'
OBJECT_BASES=tuple(0xbd80+36*i for i in range(4))


def object_templates(themes):
    """Return all four 3x3 objects per theme, including kind4 special flag.

    Cold Page2 constants only; 144 bytes remain below the reserved BE40 helper.
    The cold constructor uses kind-1 times9 and the matching36-byte theme stride.
    """
    if len(themes)!=4 or any(len(raw)<0x2824 for raw in themes):
        raise ValueError('Four complete36-byte theme object tables required')
    return b''.join(raw[0x2800:0x2824] for raw in themes)


def reuse_phase_target(text):
    """Reuse preserved targetB at the common exit; retain downstream addresses.

    Reject another B definition, implicit BC writer or undeclared callee. The
    sole Mapper512_SelectBank call preserves B by its generated inline ABI.
    No live RAM, mapper, stack or IFF change; unreachable padding retains size.
    """
    code=[s.split(';',1)[0].strip().lower() for s in text.splitlines()]
    initial=code.index('ld b,a')
    if any(re.match(r'ld (?:b|bc),|(?:inc|dec) (?:b|bc)$|pop bc$|exx$|djnz\b|(?:rl|rr|rlc|rrc|sla|sra|srl|sll) b$|(?:set|res) \d+,b$|(?:ldir|lddr|cpir|cpdr|inir|indr|otir|otdr)$',s) for s in code[initial+1:]):
        raise ValueError('Phase selector no longer preserves target B')
    if any(s.startswith('call ') and s!='call mapper512_selectbank' for s in code):
        raise ValueError('Phase selector has an undeclared register-clobbering callee')
    old='    ld a,(phase)\n    or $c0'
    if text.count(old)!=1:raise ValueError('Expected one common phase lookup store')
    return text.replace(old,'    ld a,b\n    or $c0')+'\n    defs 2,0 ; Retain downstream API addresses after the shorter load.\n'


def boot_owner(raw,linked,prefix):
    """Return a16KiB owner: raw terrain prefix, relocated linked boot payload.

    The linker emits workers/descriptors/atlas at0/1000/1200; native boot
    consumes them at Page2 addresses9000/A000/A200. No host pointer survives.
    """
    if len(raw)!=16384 or len(linked)!=16384 or not 0<prefix<=12288:
        raise ValueError('Invalid boot owner or relocation extent')
    owner=bytearray(raw);owner[4096:4096+prefix]=linked[:prefix]
    return bytes(owner)


def repack_atlas(rom,table_page,table_address,tile_count,frames):
    """Return three bounded16KiB pages, exact tile bytes/commands and pointers.

    Input pointers belong to the frozen8KiB cartridge layout. Output pointers
    directly address RAM pages21..23; no bank switch may invalidate the frame
    stream, which is copied into cold mainPage0 scratch by the RAM worker.
    """
    pages=[bytearray(b'\xff'*16384)];cursor=tile_count*3;locations={}
    def place(data):
        nonlocal cursor
        if cursor+len(data)>16384:pages.append(bytearray(b'\xff'*16384));cursor=0
        if len(pages)>3:raise ValueError('Boot atlas exceeds three cold pages')
        result=(20+len(pages),0x8000+cursor);pages[-1][cursor:cursor+len(data)]=data;cursor+=len(data);return result
    tile_pointers=[]
    at=table_page*8192+(table_address&8191)
    for i in range(tile_count):
        bank=rom[at+i*3];address=int.from_bytes(rom[at+i*3+1:at+i*3+3],'little');source=bank*8192+(address&8191)
        tag=rom[source];length=33 if tag==255 else 1 if tag>=0xc0 else 9 if tag&64 else 17
        payload=rom[source:source+length]
        if payload not in locations:locations[payload]=place(payload)
        tile_pointers.append(locations[payload])
    table=b''.join(bytes([b])+a.to_bytes(2,'little') for b,a in tile_pointers)
    pages[0][:len(table)]=table
    frame_pointers=[];max_stream=0
    for bank,address,hold in frames:
        source=bank*8192+(address&8191);n=int.from_bytes(rom[source:source+2],'little');payload=rom[source:source+2+n*2]
        assert len(payload)==2+n*2 and len(payload)<=3072
        frame_pointers.append((*place(payload),hold));max_stream=max(max_stream,len(payload))
    # Decode the relocated pointer graph back to the original exact compressed
    # records. This check does not share any emulator/VDP renderer implementation.
    for i,(b,a) in enumerate(tile_pointers):
        original=at+i*3;oldbank=rom[original];oldptr=int.from_bytes(rom[original+1:original+3],'little')
        old=oldbank*8192+(oldptr&8191);tag=rom[old];n=33 if tag==255 else 1 if tag>=192 else 9 if tag&64 else 17
        assert pages[b-21][a-0x8000:a-0x8000+n]==rom[old:old+n]
    for (oldbank,oldptr,_),(b,a,_) in zip(frames,frame_pointers):
        old=oldbank*8192+(oldptr&8191);n=2+2*int.from_bytes(rom[old:old+2],'little')
        assert pages[b-21][a-0x8000:a-0x8000+n]==rom[old:old+n]
    return pages,frame_pointers,dict(tiles=tile_count,frames=len(frames),pages=len(pages),max_stream=max_stream,
                                   unique_tile_bytes=sum(map(len,locations)),table_bytes=len(table))


def adapt(assembly,rom,raw_pages):
    """Patch only the generated experimental assembly before final linking."""
    config=(assembly/'compact-atlas-config.inc').read_text()
    number=lambda n:int(re.search(n+r' EQU (\d+)',config)[1])
    old=(assembly/'session-boot-data.inc').read_text()
    frames=[tuple(map(int,m)) for m in re.findall(r'db (\d+)\s+dw (\d+)\s+dw (\d+)',old)]
    pages,pointers,info=repack_atlas(rom,number('COMPACT_ATLAS_TABLE_PAGE'),number('COMPACT_ATLAS_TABLE_ADDRESS'),number('COMPACT_ATLAS_TILE_COUNT'),frames)
    for i,page in enumerate(pages):(assembly/f'mapper512-atlas-{i}.bin').write_bytes(page)
    (assembly/'compact-atlas-config.inc').write_text(re.sub(r'COMPACT_ATLAS_TABLE_PAGE EQU \d+','COMPACT_ATLAS_TABLE_PAGE EQU 21',re.sub(r'COMPACT_ATLAS_TABLE_ADDRESS EQU \d+','COMPACT_ATLAS_TABLE_ADDRESS EQU 32768',config)))
    seq=iter(pointers)
    def pointer(m):
        bank,address,hold=next(seq);return f'    db {bank}\n    dw {address}\n    dw {hold}'
    (assembly/'session-boot-data.inc').write_text(re.sub(r'    db (\d+)\n    dw (\d+)\n    dw (\d+)',pointer,old))
    p=assembly/'compact-boot-atlas.inc';text=p.read_text().replace('ld ($7800),a','out ($fe),a')
    text=replace(text,'CompactAtlas_Frame:\n','''CompactAtlas_Frame:
    ; Page2 dictionary changes cannot invalidate this frame's command stream.
    push hl
    ld c,(hl)
    inc hl
    ld b,(hl)
    sla c
    rl b
    inc bc
    inc bc
    pop hl
    ld de,$0800
    ldir
    ld hl,$0800
''');p.write_text(text)
    p=assembly/'session-boot.inc';text=p.read_text().replace('ld ($7000),a','out ($fe),a');p.write_text(text)
    p=assembly/'lab.asm';text=p.read_text()
    text=replace(text,'boot:\n    ld a,1\n    ld ($6800),a','boot:')
    text=replace(text,'    ; A minimal IM2 VBlank clock','''    ld hl,Mapper512_RuntimeSource
    ld de,Mapper512_IRQ
    ld bc,Mapper512_RuntimeEnd-Mapper512_IRQ
    ldir
    ; A minimal IM2 VBlank clock''')
    text=replace(text,'Mapper512_RuntimeEnd:\n ASSERT $ <= $d200',''' defs $d1e0-$,0
; DI cold-only ABI. A=operation; no active caller may use this gate.
Mapper512_ColdCall:
 push af
 ld a,30
 out ($fd),a
 pop af
 jp $5003
Mapper512_ColdReturn:
 push af
 ld a,6
 out ($fd),a
 pop af
 ret
Mapper512_RuntimeEnd:
 ASSERT $ <= $d200''')
    text=text.replace(' INCLUDE "compact-maps.inc"','')
    p.write_text(text)
    # The cartridge constructor can never run with RAM Page1/Page2 selected.
    # Its removed code/table also pays for the cold gate/initial IRQ install.
    p=assembly/'modules/mapper/page0.inc';text=p.read_text();a=text.index('GameSession_CopyMap:\n');b=text.index('GameSession_PatchObject:',a)
    text=text[:a]+'GameSession_CopyMap:\n    di\n    halt\n    jr $-1\n\n'+text[b:];p.write_text(text)
    # Cache raw cold owners only for the opening. The constant72 runtime load
    # below is replaced separately; hot native/audio/decor/UI map paths stay fast.
    logical={0:6,1:20,71:7,72:24,73:8,74:26,121:10,122:25,123:9,124:20}
    (assembly/'compact-banks.inc').write_text('Compact_Banks:\n db '+','.join(str(logical.get(i,10)) for i in range(125))+'\n')
    for name,old_id,new_bank in [('game-main.inc',72,24),('game-main.inc',74,26)]:
        p=assembly/name;text=p.read_text()
        label='PLAYER_DATA_BANK' if old_id==72 else 'GAME_RESOURCE_BANK'
        text=replace(text,f'    ld a,10\n    out ($fe),a\n    ld a,{label}',f'    ld a,{new_bank}\n    out ($fe),a\n    ld a,{label}');p.write_text(text)
    p=assembly/'modules/session/boot.inc';text=p.read_text()
    text=replace(text,'    jp GameSession_UI','''    di
    ld a,3
    call Mapper512_ColdCall
    jp GameSession_UI''');p.write_text(text)
    p=assembly/'modules/session/world.inc';text=p.read_text()
    text=replace(text,'    ld a,PLAYER_DATA_BANK\n    call Compact_Map16','    di\n    xor a\n    call Mapper512_ColdCall\n    ld a,PLAYER_DATA_BANK')
    a=text.index('GameSession_BuildMap:\n');b=text.index('    call GameSession_MapTerrain',a)
    text=text[:a]+'''GameSession_BuildMap:
    di
    ld a,1
    call Mapper512_ColdCall
    call Mapper512_TerrainBase
    di
    ld a,2
    call Mapper512_ColdCall
'''+text[b:]
    text=replace(text,'    ld de,$a800','''    push hl
    ld a,(Full_Layout)
    add a,a
    ld l,a
    ld h,0
    ld de,Mapper512_ObjectBases
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    pop hl''')
    a=text.index('GameSession_MapTerrain:\n');text=text[:a]+'''GameSession_MapTerrain:
    ld a,(Full_Layout)
    ld e,a
    ld d,0
    ld hl,GameSession_TerrainBanks
    add hl,de
    ld a,(hl)
    ld (Full_ResourceBank),a
    ld a,30
    out ($fe),a
    ret
Mapper512_ObjectBases:
    dw $bd80,$bda4,$bdc8,$bdec
''';p.write_text(text)
    p=assembly/'modules/renderer/video.inc';text=p.read_text()
    a=text.index('    call GameSession_MapTerrain');b=text.index('    ld a,$ff\n',a)
    base=text[a:b].replace('    call GameSession_MapTerrain\n','')
    text=text[:a]+text[b:]
    # Lift the unchanged terrain upload into a separate cold entry, before the
    # final map reads. The UI owner can then occupy10 during all active play.
    p.write_text(text+'\nMapper512_TerrainBase:\n'+base+'    ret\n')
    # SCREEN5 challenge UI overwrites VRAM after the first cold upload. Rebuild
    # the same map/terrain before SCREEN4 resume; all flags are new/uncollected
    # at that boundary. Reuse stopped cold I/O rather than keep another owner.
    # A cold-only helper occupies resident tail padding, retaining all
    # prior symbols and every active instruction/call path. The UI must never
    # remain mapped while terrain temporarily borrows its RAM10 owner.
    p=assembly/'modules/session/lifecycle.inc';text=p.read_text()
    text=replace(text,'    call GameSession_Video','    call Mapper512_ResumeVideo');p.write_text(text)
    p=assembly/'lab.asm';text=p.read_text()
    text=replace(text,'    ASSERT $ < $8000','''; Cold challenge resume only; AF/BC/DE/HL/IY and IFF follow BuildMap/Video.
; Resident6/Page0 main1/game0; borrows stopped OS/terrain/world/cache lifetimes.
; No active-frame caller or extra mapper segment. CALL adds two cold stack bytes.
Mapper512_ResumeVideo:
    xor a
    ld (ready),a
    ld (GameAuto_FlagsValid),a ; Cold I/O borrows both cached flag segments4/5.
    call GameSession_BuildMap
    jp GameSession_Video
    ASSERT $ < $8000''');p.write_text(text)
    p=assembly/'session-phase.inc';text=p.read_text()
    # Every path retains the original target in B, including the ranking
    # selector (which preserves B). Reuse it at the common cache-store exit;
    # the A=phase input contract and IRQ ownership keep that target stable.
    # Same flags/register results, no extra RAM/mapping/stack; save9 cycles.
    # Keep every subsequent cold/UI/audio entry at its previous address.
    # These two bytes follow RET and are never executed or counted as work.
    p.write_text(reuse_phase_target(text))
    return dict(atlas=info,atlas_ram_pages=list(range(21,21+len(pages))),boot_raw_banks={1:20,72:24,122:25,74:26},
                cold_gate=0xd1e0,cold_return=0xd1e9,object_templates=0x7d80,
                operations={'seed':0,'assets':1,'world':2,'boot_done':3},phase_target_reuse=True)


def package():
    if (OUT/'plan.json').exists():(OUT/'plan.json').unlink()
    manifest=json.loads((RUNTIME/'integration.json').read_text());s=symbols(RUNTIME/'lab.sym');assembly=RUNTIME/'assembly'
    images=[(RUNTIME/f'stage-{i}/hot-image.bin').read_bytes() for i in range(4)]
    masks=[(RUNTIME/f'stage-{i}/live-mask.bin').read_bytes() for i in range(4)]
    union=bytearray(524288)
    for mask in masks:
        for i,v in enumerate(mask):union[i]|=v
    allocated=allocate_context(common_free_regions(masks),49152);context=[];staging=[];used=0
    for row in allocated:(context if used<32768 else staging).append(row);used+=row[2]
    assert not any(union[30*16384+0x1000:30*16384+0x3e40])
    OUT.mkdir(exist_ok=True,parents=True);files=OUT/'files';files.mkdir(exist_ok=True)
    blob=bytearray(b'NRXCOLD1');records=[];streams={}
    def add(bank,data,kind,family=None):
        assert len(data)==16384
        if data not in streams:
            encoded=compress_bank(data);assert len(encoded)<=16384 and decompress_bank(encoded)==data
            streams[data]=(len(blob),len(encoded));blob.extend(encoded)
        offset,length=streams[data];index=len(records)
        records.append(dict(bank=bank,compressed=length,checksum=sum(data)&65535,offset=offset,kind=kind,family=family))
        return index
    family_starts=[];boot=[]
    for f in range(4):
        family_starts.append(len(records)+(5 if f==0 else 0))
        for b in range(6 if f==0 else 11,32):
            idx=add(b,images[f][b*16384:(b+1)*16384],'hot',f)
            if f==0:boot.append(idx)
    from mapper512_reference import reference
    raw=reference().read_bytes();raw_pages=manifest['raw_banks']
    getraw=lambda n:raw[raw_pages[str(n)]*8192:raw_pages[str(n)]*8192+16384]
    # The linker emits the startup workers at file offset0 (DISP2900), but
    # native boot reads them at9000. The cartridge shares this owner with a
    # terrain prefix; preserve the same +4096 relocation for the RAM owner.
    boot_linked=(assembly/'session-boot-linked.bin').read_bytes()
    prefix=json.loads((RUNTIME/'layout.json').read_text()).get('boot_prefix_bytes',4452)
    boot_image=boot_owner(getraw(1),boot_linked,prefix)
    boot.append(add(128|20,bytes(boot_image),'boot'))
    for i in range(manifest['game_boot']['atlas']['pages']):boot.append(add(128|(21+i),(assembly/f'mapper512-atlas-{i}.bin').read_bytes(),'boot'))
    boot.append(add(128|24,getraw(72),'boot'))
    boot.append(add(128|25,(assembly/'session-cold-linked.bin').read_bytes(),'boot'))
    boot.append(add(128|26,getraw(74),'boot'))
    seed=add(10,getraw(72),'seed');nav=add(10,getraw(74),'navigation')
    terrains=[add(10,getraw(b),'terrain',f) for f,b in enumerate([75,86,97,108])]
    original=(ROOT/'references/build/game/newrallyx.rom').read_bytes();banks=json.loads((ROOT/'references/build/game/session-build.json').read_text())['map_banks'];maps=[]
    for f in range(4):
        pair=[]
        for half,target in [(1,3),(0,2)]:
            at=banks[f*2+half]*16384;pair.append(add(target,original[at:at+16384],'map',f))
        maps.extend(pair)
    assert len(records)<256
    (files/'NRX512.DAT').write_bytes(blob)
    (OUT/'cold-layout.inc').write_text(layout_source(context,staging,records,union))
    (OUT/'cold-mode.inc').write_text('COLD_BATCH EQU 1\n DEFINE COLD_GAME 1\n')
    binding=f'GAME_LAYOUT EQU {s["Full_Layout"]}\nGAME_SEED_RESOURCE EQU {seed}\nGAME_NAV_RESOURCE EQU {nav}\nGAME_UI_RESOURCE EQU 4\n'
    binding+='Game_BootResources:\n db '+','.join(map(str,boot+[255]))+'\n'
    binding+='Game_FamilyStarts:\n db '+','.join(map(str,family_starts))+'\n'
    binding+='Game_TerrainResources:\n db '+','.join(map(str,terrains))+'\n'
    binding+='Game_MapResources:\n db '+','.join(map(str,maps))+'\n'
    (OUT/'game-bindings.inc').write_text(binding)
    templates=object_templates([getraw(b) for b in [75,86,97,108]])
    assert OBJECT_BASES[-1]+36<=0xbe40
    (OUT/'game-objects.inc').write_text('\n'.join(' db '+','.join(map(str,templates[i:i+36])) for i in range(0,len(templates),36))+'\n')
    for n in ['mapper512-cold.asm','mapper512-cold-loader.asm','mapper512-game-bridge.inc']:shutil.copyfile(ROOT/'src/disk'/n,OUT/n)
    for src in ['mapper512-cold.asm','mapper512-cold-loader.asm']:
        p=subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),'--nologo',f'--sym={src}.sym',src],cwd=OUT,capture_output=True,text=True)
        if p.returncode:raise RuntimeError((p.stdout+p.stderr)[-2500:])
        if src=='mapper512-cold.asm':(OUT/'cold-size.inc').write_text(f'COLD_BYTES EQU {(OUT/"cold.bin").stat().st_size}\n')
    bridge=(OUT/'cold.bin').read_bytes();loader=(OUT/'cold-loader.bin').read_bytes()
    assert len(bridge)<=0x2e40
    stub=b'\x21\x11\x01\x11\0\xc1\x01'+struct.pack('<H',len(loader))+b'\xed\xb0\xc3\0\xc1\0\0\0'
    assert len(stub+loader+bridge)<0x3f00
    (files/'NRX512.COM').write_bytes(stub+loader+bridge)
    bs=stub.replace(b'\x21\x11\x01',b'\x21\x11\x80').replace(b'\xc3\0\xc1',b'\xc3\x04\xc1')+loader+bridge
    (files/'NRX512.BIN').write_bytes(b'\xfe'+struct.pack('<HHH',0x8000,0x8000+len(bs)-1,0x8000)+bs)
    (files/'NRX512.BAS').write_bytes(b'10 CLEAR 200,&HC0FF\r\n20 BLOAD "NRX512.BIN",R\r\n\x1a')
    plan=dict(status='Experimental native512KiB boot/lifecycle integration, not qualified',runtime=str(RUNTIME.relative_to(ROOT)),records=records,boot_resources=boot,
              family_starts=family_starts,seed_resource=seed,nav_resource=nav,terrain_resources=terrains,map_resources=maps,
              bridge_sha256=hashlib.sha256(bridge).hexdigest(),bridge_bytes=len(bridge),resource_bytes=len(blob),resource_sha256=hashlib.sha256(blob).hexdigest(),
              context=context,map_staging=staging,active_images=manifest['stages'],reference_rom_sha256=manifest['reference_rom_sha256'])
    plan['files']=[dict(name=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(files.glob('NRX512.*'))]
    (OUT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');(OUT/'union-mask.bin').write_bytes(union)
    print(json.dumps({k:v for k,v in plan.items() if k not in ['records','context','map_staging','active_images']},indent=2));return plan


if __name__=='__main__':
    from mapper512_integrate import build
    build(RUNTIME,game=True)
    package()

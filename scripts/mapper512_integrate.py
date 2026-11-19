"""Link the complete game's active backend into a bounded512KiB RAM layout.

This first integration has explicit cartridge/host-assisted cold transitions;
it is not a DOS/BASIC loader or a published replacement. All active code/data,
native rules, audio, sprites and caches must execute from the32 real segments.
Cold providers are forbidden to refill a bank during a measured gameplay frame.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from compact_game_build import symbols,replace
from mapper512_backend import prepare,source_offset,suffix_windows,instructions,cycles
from compact_transfer import tokens,optimize,LONG,SHORT,events

OUT=ROOT/'references/build/game-mapper512-integrated'
RESIDENT=6;NATIVE=7;AUDIO=8;DECOR=9;DYNAMIC=10;HUD=11;EDGE=19;CODE=20


def put(data,busy,at,value):
    if at<0 or at+len(value)>len(data) or any(busy[at:at+len(value)]):raise ValueError('Live allocation collision')
    data[at:at+len(value)]=value;busy[at:at+len(value)]=b'\1'*len(value)


def common_free_regions(masks,bank_size=16384):
    """Declared holes shared by every family, never inferred from FF pixels.

    Return (bank, offset, length) spans, split at physical bank boundaries.
    All masks must describe the same complete bank set. Zero means unowned.
    """
    if not masks or bank_size<=0 or len(masks[0])%bank_size or any(len(m)!=len(masks[0]) for m in masks):
        raise ValueError('Inconsistent live masks')
    regions=[]
    for bank in range(len(masks[0])//bank_size):
        offset=0
        while offset<bank_size:
            if any(m[bank*bank_size+offset] for m in masks):offset+=1;continue
            start=offset
            while offset<bank_size and not any(m[bank*bank_size+offset] for m in masks):offset+=1
            regions.append((bank,start,offset-start))
    return regions


def compile_packets(cases, records):
    """Cold source relocation; independently retain every ordered pixel/control event.

    A/color edge arrays shift40 bytes so both name arrays keep aligned zero
    low bytes. Body ABI remains AF/HL/B scratch, C=98, DE/IX/IY preserved;
    nonempty endsEI and empty keeps entry IFF. No runtime source relocation.
    """
    headers=set()
    for c in cases:
        r=records[c['record']];code=bytearray();base=0x8000+(c['record']%2)*4096
        def address(old):
            offset=source_offset(old,r,base)
            if r['kind']=='edge' and offset<0x400:offset+=0x40
            return 0x8000+(c['record']%8)*2048+offset
        for kind,n,raw in tokens(c['code']):
            code.extend(b'\x21'+address(int.from_bytes(raw[1:],'little')).to_bytes(2,'little') if kind=='load' else raw)
        optimized,_=optimize(bytes(code));c['hot_cycles']=cycles(optimized)
        original,_,old_b=events(c['baseline']);actual,hl,new_b=events(optimized)
        expected=[('data',address(e[1])) if e[0]=='data' else e for e in original]
        assert actual==expected and old_b==new_b,'Packet event/B regression'
        pixels=[e[1] for e in actual if e[0]=='data']
        assert hl==(pixels[-1]+1 if pixels else None)
        if c['writes']:headers.add(optimized[:14]);c['hot']=optimized[14:]
        else:c['hot']=optimized
    assert headers=={bytes.fromhex('0e98 f3 3a27c0 f600 d399 3e8e d399')}


def verify_closures(windows, terminal):
    """Check every entry walks the exact pre-link instructions, joins excluded."""
    checked=0
    for w in windows:
        nodes={};pc=0x4000
        for ins in instructions(w['data']):nodes[pc]=ins;pc+=len(ins)
        for code,entry in w['entries'].items():
            pc=entry;seen=[]
            for _ in range(4096):
                ins=nodes[pc]
                if ins[0]==0xc3:
                    target=int.from_bytes(ins[1:],'little')
                    if target==terminal:break
                    assert target in nodes;pc=target;continue
                seen.append(ins);pc+=len(ins)
            else:raise ValueError('Nonterminating packet closure')
            assert tuple(seen)==instructions(code)[:-1]
            checked+=1
    return checked


def build(output=OUT,game=False):
    OUT=Path(output)
    from mapper512_reference import reference
    baseline=ROOT/'references/build/game-compact-runtime';rom=reference().read_bytes()
    assert hashlib.sha256(rom).hexdigest()=='44be6037d05ebf763283f14ef6deb6e4a8bd58b0a25fcc04c693d899c3704f00'
    assembly=OUT/'assembly'
    if (OUT/'integration.json').exists():(OUT/'integration.json').unlink()
    if assembly.exists():shutil.rmtree(assembly)
    shutil.copytree(baseline/'assembly',assembly)
    for p in baseline.iterdir():
        if p.is_file() and p.suffix in ('.json','.bin','.inc'):shutil.copyfile(p,OUT/p.name)
    cases,records,_=prepare();old_layout=json.loads((baseline/'layout.json').read_text());raw_pages=old_layout['raw_bank_pages']
    logical={0:RESIDENT,71:NATIVE,73:AUDIO,123:DECOR,121:DYNAMIC}
    raw_bank=lambda b:logical.get(b,DYNAMIC)
    at=raw_pages['72']*8192+0x2025
    (assembly/'mapper512-restart.bin').write_bytes(rom[at:at+8])
    (assembly/'compact-banks.inc').write_text('Compact_Banks:\n db '+','.join(str(raw_bank(i)) for i in range(125))+'\n')
    path=assembly/'lab.asm';text=path.read_text()
    start=text.index('clock_irq:\n');end=text.index('upload:\n',start)
    irq=text[start:end].replace('clock_irq:','Mapper512_IRQ:')
    text=text[:start]+'clock_irq EQU Mapper512_IRQ\n'+text[end:]
    start=text.index('Compact_Map16:\n');end=text.index(' INCLUDE "compact-banks.inc"',start)
    text=text[:start]+'''Compact_Map16:
 push af
 push hl
 push de
Mapper512_RawEnter:
 ld e,a
 ld d,0
 ld hl,Compact_Banks
 add hl,de
 ld a,(hl)
 out ($fe),a
 pop de
 pop hl
 pop af
 ret
Compact_MapPair:
 jp Compact_Map16
'''+text[end:]
    start=text.index('Compact_ExactHead:\n');end=text.index('palette:\n',start)
    # Keep the same fixed helper address inside each independently mapped code
    # window. Its resident alias emits no bytes and is never called in bank6.
    text=text[:start]+'''Compact_ExactHead EQU $7e40
Mapper512_HudBank EQU $d10c
Mapper512_RuntimeSource:
 DISP $d180
'''+irq+''' defs $d1b0-$,0
; A=physical code segment; bit7 marks a no-write/IFF-preserving empty packet.
; HL=entry. Page0 exact tails and Page3 stack stay mapped; AF/BC/HL scratch.
Mapper512_Packet:
 or a
 jp m,.empty
 out ($fd),a
 db $0e,$98,$f3,$3a,$27,$c0,$f6,$00,$d3,$99,$3e,$8e,$d3,$99
 jp (hl)
.empty:
 and 127
 out ($fd),a
 jp (hl)
Mapper512_PacketDone:
 ld a,6
 out ($fd),a
 jp hud_upload.done
Mapper512_RuntimeEnd:
 ASSERT $ <= $d200
 ENT
'''+text[end:]
    # Replace the generated hot Page0 helpers as one assembly-time module.
    start=text.index('Compact_Base EQU');end=text.index('GameAuto_WorkersEnd:',start)
    exact=text[text.index('Compact_ExactTail:',start):end]
    boundary=text[text.index('boundaries:\n',start):text.index('Compact_ExactTail:',start)]
    boundary=boundary.replace('    inc a\n    ld h,a','    add a,2\n    ld h,a')
    text=text[:start]+'''Compact_Base EQU $07e6
GameSession_PhaseBank:
 ld a,(Mapper512_HudBank)
 out ($fe),a
 ret
Compact_SelectPhase:
 call Compact_SetPhaseBase
Mapper512_SelectBank:
 srl a
 srl a
 srl a
 add a,11
 ld (Mapper512_HudBank),a
 out ($fe),a
 ret
Compact_SetPhaseBase:
 push af
 and 7
 add a,a
 add a,a
 add a,a
 or $80
 ld (Compact_Base),a
 pop af
 ret
Compact_Bind:
 ld a,(phase)
 srl a
 srl a
 srl a
 add a,11
 ld (Mapper512_HudBank),a
 out ($fe),a
 ld a,(Compact_Base)
 inc a
 ld h,a
 ld l,$50
 jp (hl)
Compact_Names:
 ld a,(Compact_Base)
 add a,5
 ld h,a
 ld l,0
 jp (hl)
Compact_HudPointers:
 ld a,(Compact_Base)
 add a,7
 ld d,a
 ld e,0
 ret
Compact_EdgePointers:
 ld a,(Compact_Base)
 add a,5
 ld d,a
 ld e,$40
 ret
Compact_PatternHL:
 ld a,(Compact_Base)
 ld h,a
 ld l,0
 ret
Compact_ColorHL:
 ld a,(Compact_Base)
 add a,2
 ld h,a
 ld l,0
 ret
Compact_PatternDE:
 ld a,(Compact_Base)
 ld d,a
 ld e,0
 ret
Compact_ColorDE:
 ld a,(Compact_Base)
 add a,2
 ld d,a
 ld e,0
 ret
GameSession_MapEdges:
 ld a,19
 out ($fe),a
 ret
'''+boundary+exact+text[end:]
    text=replace(text,'    and 1\n    rrca\n    rrca\n    rrca\n    rrca\n    or $80\n    ld (Compact_Base),a','    and 7\n    add a,a\n    add a,a\n    add a,a\n    or $80\n    ld (Compact_Base),a')
    # Only the packet dispatcher changes Page1. The old direct code-page store
    # is removed here; Page2 source stays installed until the existing return.
    start=text.index('hud_upload:\n');end=text.index('render.hud_uploaded:',start)
    part=text[start:end]
    part=part.replace('    ld ($7800),a\n','')
    # This legacy cache marker has no reader in the integrated presenter. Its
    # old store also destroys the code-bank A needed by the Page3 dispatcher.
    part=part.replace('    ld a,$ff\n    ld (hud_page),a\n','')
    part=part.replace('    jp (hl)','    jp Mapper512_Packet')
    text=text[:start]+part+text[end:]
    path.write_text(text)
    path=assembly/'game-core.inc';text=path.read_text()
    start=text.index('Game_Restart:\n');end=text.index('    ld de,$e025',start)
    text=text[:start]+'Game_Restart:\n    ld hl,Mapper512_RestartSeed\n'+text[end:]
    at=text.index('    ldir\n',start)+len('    ldir\n')
    text=text[:at]+'    ld hl,$a02d ; Preserve the original native reentry input after cached seed copy.\n'+text[at:]
    path.write_text(text)
    path=assembly/'lab.asm';text=path.read_text().replace(' ALIGN 256\nCompact_UniformTable:', 'Mapper512_RestartSeed:\n INCBIN "mapper512-restart.bin"\n ALIGN 256\nCompact_UniformTable:');path.write_text(text)
    path=assembly/'game-boundary-fast.inc';text=path.read_text().replace('    ld ($7800),a\n','').replace('    ld a,$ff\n    ld (hud_page),a\n','').replace('    jp (hl)','    jp Mapper512_Packet');path.write_text(text)
    path=assembly/'modules/renderer/session-banks.inc';text=path.read_text()
    text=replace(text,'    call Compact_SetPhaseBase','    call Compact_SelectPhase')
    path.write_text(text)
    path=assembly/'session-phase.inc';text=path.read_text()
    text=text.replace('    call GameSession_PhaseBank','    call Mapper512_SelectBank')
    at=text.index('    ld a,(Compact_Base)\n');end=text.index('    ld ix,pattern_phases',at)
    text=text[:at]+'''    ld a,(Compact_Base)
    add a,4
    ld iyh,a
'''+text[end:];path.write_text(text)
    # Same deterministic victim policy, including visible-set exclusion,
    # first-match/first-minimum ties and unknown phase64. Unroll the hot match
    # and ranking scans; no IX/IY use means no save/restore is needed. Pixel
    # data, cache capacity and presentation frequency remain unchanged.
    phase='''; Experimental RAM backend: exact existing eight-slot cache policy.
; A=target phase (also stored in phase). AF/BC/DE/HL scratch; IX/IY/IFF kept.
GameSession_PhaseSelect:
    ld b,a
    or $c0
    ld l,a
    ld h,$28
    ld a,(hl)
    cp 8
    jr nc,.search
    ld c,a
    ld a,(pattern_front)
    cp c
    jr z,.search
    ld a,c
    add a,pattern_phases & $ff
    ld l,a
    ld a,(hl)
    cp b
    jp z,.selected
.search:
    ld a,(pattern_front)
    ld e,a
'''
    for i in range(8):
        phase+=f'''    ld a,e
    cp {i}
    jr z,.match_next{i}
    ld a,(pattern_phases+{i})
    cp b
    jp z,.select{i}
.match_next{i}:
'''
    phase+='''    ld c,0
    ld hl,pattern_phases
.empty:
    ld a,(hl)
    cp $ff
    jp z,.selected
    inc hl
    inc c
    ld a,c
    cp 8
    jr c,.empty
    ld a,b
    call Mapper512_SelectBank
    ld a,(Compact_Base)
    add a,4
    ld h,a
    ld d,$ff
'''
    for i in range(8):
        phase+=f'''    ld a,e
    cp {i}
    jr z,.rank_next{i}
    ld a,(pattern_phases+{i})
    cp $ff
    jr nz,.known{i}
    ld a,64
.known{i}:
    ld l,a
    ld a,(hl)
    cp d
    jr nc,.rank_next{i}
    ld d,a
    ld c,{i}
.rank_next{i}:
'''
    phase+='    jr .selected\n'
    for i in range(8):phase+=f'.select{i}:\n    ld c,{i}\n    jr .selected\n'
    phase+='''.selected:
    ld a,c
    ld (pattern_back),a
    ld a,(phase)
    or $c0
    ld l,a
    ld h,$28
    ld (hl),c
    ret
'''
    path.write_text(phase)
    # Keep all active Page0 code intact (audio/decorators also share the file
    # named "cold"). The permission rows live beside the1934-byte ring worker
    # in segment31, at the exact9000 source addresses the original query uses.
    path=assembly/'game-host.inc';text=path.read_text()
    text=replace(text,'    ld a,(Full_ResourceBank)\n    call Compact_MapPair','    ld a,31\n    out ($fe),a')
    path.write_text(text)
    # Terrain owners become logical IDs; only cold video preparation maps one.
    path=assembly/'session-bank-tables.inc';text=path.read_text();text=re.sub(r'(GameSession_TerrainBanks:\n\s*db )[^\n]+',r'\g<1>75,86,97,108',text);path.write_text(text)
    raw_sites=[]
    for path in sorted(list(assembly.rglob('*.inc'))+list(assembly.glob('*.asm'))):
        text=path.read_text()
        pattern=r'    ld a,(\d+)\n    ld \(\$7000\),a\n    ld a,(\d+)\n    ld \(\$7800\),a\n    ld a,(\w+)'
        def inline(m):
            old=int(m[1]);logical_bank=next(int(k) for k,v in raw_pages.items() if v==old)
            assert int(m[2])==old+1
            name=f'.mapper512_raw_site_{len(raw_sites)}';raw_sites.append((name,logical_bank))
            return f'{name}:\n    ld a,{raw_bank(logical_bank)}\n    out ($fe),a\n    ld a,{m[3]}'
        text=re.sub(pattern,inline,text)
        path.write_text(text)
    # No literal8KiB cartridge store is valid once RAM Page1/Page2 is selected.
    # Cold replay/map constructors remain host-assisted at this step. The
    # active ring instead owns a real immutable Page2 segment in every family.
    path=assembly/'ring.inc';text=path.read_text()
    text=re.sub(r'    ld a,79\n    ld \(\$7800\),a\n    ld a,\(mapcol\)\n    jp \d+', '    ld a,31\n    out ($fe),a\n    ld a,(mapcol)\n    jp $8000',text)
    path.write_text(text)
    # The unchanged position-independent ring worker owns segment31 in Page2;
    # Page1 stays resident, so no wrapper or extra CALL is needed. Cold I/O
    # cannot count this hot segment as scratch; it must reuse a cold cache.
    audio=bytearray((assembly/'session-production-audio.bin').read_bytes())
    game_plan=None
    if game:
        from mapper512_game import adapt
        game_plan=adapt(assembly,rom,raw_pages)
    assembler=ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'
    def assemble():
        result=subprocess.run([str(assembler),'--nologo','--sym=lab.sym','lab.asm'],cwd=assembly,capture_output=True,text=True)
        (OUT/'assembler.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError((result.stdout+result.stderr)[-2000:])
        return symbols(assembly/'lab.sym')
    syms=assemble()
    for at in [0x185a,0x18b8,0x190f,0x1966]:
        assert audio[at]==0xcd
        audio[at:at+3]=b'\xcd'+syms['Compact_Map16'].to_bytes(2,'little')
    (assembly/'session-production-audio.bin').write_bytes(audio);syms=assemble()
    # Recompile source operands once per stage. Edge A/color arrays begin40
    # bytes later so both64-entry name tables retain aligned zero low bytes.
    compile_packets(cases,records)
    stages=[];live_masks=[]
    for family in range(4):
        directory=OUT/f'stage-{family}';directory.mkdir(exist_ok=True)
        selected=[c for c in cases if c['record']<64 or (c['record']-64)//8==family]
        windows=suffix_windows([c['hot'] for c in selected],exit_address=syms['Mapper512_PacketDone'])
        closure_checks=verify_closures(windows,syms['Mapper512_PacketDone'])
        assert len(windows)<=11,('No scratch segment remains',family,len(windows))
        locations={code:(CODE+i,entry) for i,w in enumerate(windows) for code,entry in w['entries'].items()}
        image=bytearray(b'\xff'*524288)
        # Working state and opaque native/audio/decor/UI/resident owners are
        # conservatively full. Only authored source/code/ring masks expose holes.
        live=bytearray(b'\1'*(11*16384)+b'\0'*(21*16384))
        for bank,name in [(RESIDENT,'newrallyx.rom'),(NATIVE,'game-native-linked.bin'),(AUDIO,'session-audio-linked.bin'),(DYNAMIC,'session-ui-linked.bin')]:
            data=(assembly/name).read_bytes();assert len(data)==16384
            image[bank*16384:(bank+1)*16384]=data
        page=raw_pages['123'];image[DECOR*16384:(DECOR+1)*16384]=rom[page*8192:page*8192+16384]
        ring=ROOT/'references/build/game/game-ring-refresh.bin'
        assert ring.stat().st_size==1934
        image[31*16384:31*16384+1934]=ring.read_bytes()
        live[31*16384:31*16384+1934]=b'\1'*1934
        bodies={}
        for i,w in enumerate(windows):
            body=bytearray();
            for ins in instructions(w['data']):
                if ins[0]==0xcd:
                    target=int.from_bytes(ins[1:],'little');n=target&255
                    target=syms['Compact_ExactShortEnd']-2*n if target&0xff00==SHORT else syms['Compact_ExactTailEnd']-2*n if n<=64 else 0x7e40+2*(255-n)
                    ins=b'\xcd'+target.to_bytes(2,'little')
                body.extend(ins)
            head=b'\xed\xa3'*191+b'\xc3'+syms['Compact_ExactTail'].to_bytes(2,'little')
            assert len(body)<=0x3e40
            at=(CODE+i)*16384;image[at:at+len(body)]=body;image[at+0x3e40:at+0x3e40+385]=head
            live[at:at+len(body)]=b'\1'*len(body);live[at+0x3e40:at+0x3e40+385]=b'\1'*385
            bodies[i]=len(body)
        for i in range(72):
            record=i if i<64 else 64+family*8+i-64;r=records[record]
            data=bytearray(b'\xff'*2048);busy=bytearray(2048);base=0x8000+(i%8)*2048
            if i<64:
                put(data,busy,0,bytes(r['data'][0x100:0x248]));put(data,busy,0x200,bytes(r['data'][0x300:0x448]))
                put(data,busy,0x400,bytes(r['data'][0x800+family*256:0x841+family*256]))
                n=sum(r['occupied'][0x510:0x710]);names=bytearray(r['data'][0x510:0x510+n]);assert names[-3]==0xc3
                names[-2:]=(base+0x180).to_bytes(2,'little');put(data,busy,0x500,names)
                n=sum(r['occupied'][0xd10:]);put(data,busy,0x180,bytes(r['data'][0xd10:0xd10+n]))
                bind=bytearray((0x3e,base>>8,0x32))+(syms['GameRadarFast_Draw.compact_source']+2).to_bytes(2,'little')
                bind+=bytes((0x3e,41,0x32))+syms['count'].to_bytes(2,'little')
                for target in [base+0x500,syms['GameSession_Boundaries'],syms['radar'],syms['hud_upload']]:bind+=b'\xcd'+target.to_bytes(2,'little')
                bind+=b'\xc3'+syms['render.hud_uploaded'].to_bytes(2,'little');put(data,busy,0x150,bind)
                pointer=0x700;entries=64
            else:
                a,b=r['data'][0xa00:0xa02]
                for old,new,size in [(0,0,64),(0x100,0x200,64),(0x200,0x40,a*8),(0x400,0x240,a*8),(0x600,0x400,b*8),(0x800,0x600,b*8)]:put(data,busy,new,bytes(r['data'][old:old+size]))
                put(data,busy,0x55b,bytes((a,b)));pointer=0x540;entries=9
            table=bytearray()
            for c in sorted((c for c in selected if c['record']==record),key=lambda c:c['index']):
                bank,entry=locations[c['hot']];table+=bytes((bank|(0 if c['writes'] else 128),))+entry.to_bytes(2,'little')
            assert len(table)==entries*3;put(data,busy,pointer,table)
            at=(HUD+i//8)*16384+(i%8)*2048;image[at:at+2048]=data
            live[at:at+2048]=busy
        terrain_bank=[75,86,97,108][family];p=raw_pages[str(terrain_bank)]
        terrain=rom[p*8192:p*8192+16384];permissions=terrain[0x1000:0x1000+174*32]
        image[31*16384+0x1000:31*16384+0x1000+174*32]=terrain[0x1000:0x1000+174*32]
        live[31*16384+0x1000:31*16384+0x1000+174*32]=b'\1'*(174*32)
        (directory/'permissions.bin').write_bytes(permissions)
        (directory/'hot-image.bin').write_bytes(image)
        (directory/'live-mask.bin').write_bytes(live);live_masks.append(live)
        stages.append(dict(family=family,code_windows=len(windows),closure_checks=closure_checks,code_bytes=sum(bodies.values()),hot_segments=21+len(windows),cold_scratch_segment=None,
            sha256=hashlib.sha256(image).hexdigest(),bytes=len(image),edge_packet_model_delta_max=max(c['hot_cycles']-c['baseline_cycles'] for c in selected)))
    shutil.copyfile(assembly/'lab.sym',OUT/'lab.sym')
    manifest=dict(status='Full-game RAM-active integration; cold cartridge/host provider still required. Not a standalone executable.',
        reference_rom_sha256=hashlib.sha256(rom).hexdigest(),ram_kib=512,stages=stages,
        raw_sites={str(next(v for k,v in syms.items() if k.endswith(n))):bank for n,bank in raw_sites},raw_banks=raw_pages,
        runtime_image_offset=syms['Mapper512_RuntimeSource']-0x4000,runtime_image_bytes=syms['Mapper512_RuntimeEnd']-syms['Mapper512_IRQ'],
        working_segments=dict(page3=0,main=1,maps=[2,3],flags=[4,5]),hot_banks=logical,
        permission_rows='Original32-byte stride in ring segment31,9000..A5BF; no Page0 overlay',
        unresolved=['Cartridge-free DOS/BASIC bootstrap, allocator and cold filesystem provider',
                    'Cold OS snapshot/directory/scratch peak in the same32 segments',
                    'Broader lifecycle, CPU/PAL matrix and strict cadence acceptance; see separate integration report'])
    manifest['runtime_files']={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['lab.sym','assembly/session-cold-linked.bin','assembly/session-boot-linked.bin']}
    if game_plan is not None:
        manifest['game_boot']=game_plan
        manifest['status']='Experimental native boot/lifecycle RAM backend; filesystem packaging and qualification tracked separately.'
        manifest['unresolved']=['Standalone game qualification: exact package/boot/callback evidence, active-speed/audio/lifecycle matrix and hardware compatibility']
    (OUT/'live-layout.json').write_text(json.dumps(dict(
        program_images=[s['sha256'] for s in stages],
        mask_sha256=[hashlib.sha256(m).hexdigest() for m in live_masks],
        common_free_regions=common_free_regions(live_masks)),indent=2)+'\n')
    (OUT/'integration.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2));return manifest


if __name__=='__main__':build()

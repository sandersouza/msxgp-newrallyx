"""Relink the complete default game against the compact8 KiB backend.

Only a generated assembly view is modified. Normal export uses --publish for
dist/newrallyx.rom; standalone output is dist/compact/. Contributor-derived
inputs/outputs stay ignored. Assertions and invalid-bank traps reject missing
bindings; qualify the exact resulting hash before publishing a release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src/toolchain/screen4'),str(ROOT)]
import game_build
from renderer_image_build import build as allocate
from renderer_window_probe import probe


def replace(text,old,new):
    if text.count(old)!=1:raise ValueError(f'Compact anchor count={text.count(old)}: {old[:90]}')
    return text.replace(old,new,1)


def symbols(path):
    return {n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',path.read_text())}


def build(backend='ascii8',publish=False,bundle=None,*,baseline_maps=False,fast_transfers=True,boot_atlas=True,fixed_ram=False):
    assert backend in ('ascii8','megaram')
    if baseline_maps and publish:raise ValueError('Baseline maps are diagnostic-only; default export must use optimized maps')
    if baseline_maps:fast_transfers=boot_atlas=False
    baseline=Path(bundle or ROOT/'references/build/game').resolve()
    allocate(integrated=True,bundle=baseline,optimize_maps=not baseline_maps,fast_transfers=fast_transfers,boot_atlas=boot_atlas)
    allocation=ROOT/'references/build/game-compact-runtime-allocation'
    layout=json.loads((allocation/'layout.json').read_text())
    owner='game-fixedram' if fixed_ram else 'game-compact'
    out=ROOT/'references/build'/(owner+'-runtime' if backend=='ascii8' else owner+'-megaram-runtime')
    assembly=out/'assembly'
    if assembly.exists():shutil.rmtree(assembly)
    assembly.mkdir(parents=True)
    for p in baseline.iterdir():
        if p.is_file() and p.suffix in ('.asm','.inc','.json','.bin'):
            shutil.copyfile(p,out/p.name)
    shutil.copyfile(out/'lab.asm',assembly/'lab.asm')
    game_build.copy_sources(ROOT,out,assembly)
    raw={int(k):v for k,v in layout['raw_bank_pages'].items()}
    cases=[];records=[];probe(4096,cases,records,integrated=True,bundle=baseline,fast_transfers=fast_transfers)
    original=(baseline/'newrallyx.rom').read_bytes()
    counts={original[b*16384+0x900] for b in range(4,68)}
    uniform={original[b*16384+0x2940:b*16384+0x2980] for b in range(4,68)}
    assert counts=={41} and len(uniform)==1
    (assembly/'compact-uniform.bin').write_bytes(next(iter(uniform)))
    banks=[255]*125
    for old,page in raw.items():banks[old]=page
    banks[124]=raw[1]
    for n,r in enumerate(records):banks[r['bank']]=layout['data_base']+n//2
    for n,r in enumerate(layout['maps']):banks[r['old_bank']]=128|n
    (assembly/'compact-banks.inc').write_text('Compact_Banks:\n db '+','.join(map(str,banks))+'\n')
    (assembly/'compact-maps.inc').write_text('Compact_Maps:\n'+''.join(' db '+str(r['entry'][0])+'\n dw '+str(r['entry'][1])+'\n' for r in layout['maps']))

    # This helper is resident even before main Page0 is installed. Replacing
    # LD(7000),A with CALL retains instruction size, AF/HL/DE and IFF ownership.
    mapper='''
; A=original logical bank; preserve AF/BC/DE/HL/IX/IY/IFF. Own both8 KiB windows.
; No scratch; eight extra stack bytes including CALL. Maps carry a tagged index
; and must use CopyMap; retired initial edge banks trap instead of aliasing.
Compact_Map16:
 push af
 push hl
 push de
 ld e,a
 ld d,0
 ld hl,Compact_Banks
 add hl,de
 ld a,(hl)
 bit 7,a
 jr nz,Compact_InvalidBank
 ld ($7000),a
 inc a
 ld ($7800),a
 pop de
 pop hl
 pop af
 ret
Compact_InvalidBank:
 di
 halt
 jr Compact_InvalidBank
; A=physical even page of a raw16 KiB owner; preserve all registers/IFF.
Compact_MapPair:
 push af
 ld ($7000),a
 inc a
 ld ($7800),a
 pop af
 ret
 INCLUDE "compact-banks.inc"
 INCLUDE "compact-maps.inc"
 ALIGN 256
Compact_UniformTable:
 INCBIN "compact-uniform.bin"
'''
    if fast_transfers:
        mapper+='''
; Foreground exact-length OUTI heads. HL=source,C=98, B scratch, AF scratch.
; Entry chosen by generated count; no count dispatch or extra mapper access.
; Base Z80 I/O only. OUTI spacing equals the existing unrolled helper.
Compact_ExactHead:
 REPT 191
 outi
 ENDR
 jp Compact_ExactTail
'''
    path=assembly/'modules/renderer/session-banks.inc'
    text=path.read_text();start=text.index('GameSession_MapEdges:');end=text.index('GameSession_Boundaries:',start)
    edge_source=text[start:end]
    edge_source=edge_source[:edge_source.index('GameSession_PhaseBank:')]
    # HUD phase parity equals fx parity. Keep one Base binding per new phase;
    # edge selection only changes the data page and preserves that binding.
    edge_source=edge_source.replace('    ld ($7000),a','    ld ($7000),a ; Physical lower page from the rebound edge table.')
    path.write_text(text[:start]+text[end:])

    path=assembly/'lab.asm';text=path.read_text()
    # ASCII8 powers up with bank0 mirrored in its windows. Establish the
    # resident upper half before the first call beyond5FFF can execute.
    text=replace(text,'boot:\n    ; BIOS','boot:\n    ld a,1\n    ld ($6800),a\n    ; BIOS')
    start=text.index('boundaries:\n');end=text.index('left_names:\n',start)
    boundaries=text[start:end].replace('    ld h,$8a','    ld a,(Compact_Base)\n    ld h,a').replace('    ld h,$90','    ld a,(Compact_Base)\n    inc a\n    ld h,a')
    stop=text.index('radar:\n',end)
    text=text[:start]+text[stop:]
    start=text.index('left_length:\n');end=text.index('radar:\n',start)
    text=text[:start]+text[end:]
    text=text.replace('    call $a300\n    call left_names','    call Compact_Names')
    start=text.index('.packet:\n',text.index('hud_upload:'));end=text.index('.done:\n',start)
    text=text[:start]+text[end:]
    text=replace(text,'    ld de,$a600','    call Compact_HudPointers')
    text=replace(text,'    ld hl,$8900\n    ld a,(hl)','    call Compact_Count')
    # HUD transition pointers contain physical upper-window pages, not logical
    #16 KiB IDs. Source remains mapped in the lower window across the dispatch.
    start=text.index('hud_upload:');end=text.index('render.hud_uploaded:',start)
    part=text[start:end]
    assert part.count('    ld ($7000),a')==2
    part=part.replace('    ld ($7000),a','    ld ($7800),a',1)
    part=part.replace('    ld hl,$8100','    call Compact_PatternHL').replace('    ld hl,$8500','    call Compact_ColorHL')
    text=text[:start]+part+text[end:]
    text=text.replace('palette:\n',mapper+'\npalette:\n',1)

    helpers='''
; Main Page0 helpers, called only with main segment restored. Compact_Base at
;07E6 is persistent outside the copied worker range and above mapper state.
; SelectPhase A=0..63 -> paired data mapping/Base80 or90; AF scratch, others kept.
Compact_Base EQU $07e6
GameSession_PhaseBank:
 ld a,(phase)
 srl a
 add a,COMPACT_DATA_BASE
 ld ($7000),a
 ret
Compact_SelectPhase:
 call Compact_SetPhaseBase
 srl a
 add a,COMPACT_DATA_BASE
 ld ($7000),a
 ret
Compact_SetPhaseBase:
 push af
 and 1
 rrca
 rrca
 rrca
 rrca
 or $80
 ld (Compact_Base),a
 pop af
 ret
; Tail entry from render: no extra return address. The lower-window phase
; binding program restores its own window across every nested mapper call.
Compact_Bind:
 ld a,(phase)
 srl a
 add a,COMPACT_DATA_BASE
 ld ($7000),a
 ld a,(Compact_Base)
 ld h,a
 ld l,0
 jp (hl)
; Count/Names clobber AF/HL. Names executes immediate stores then returns;
; the guard column is in that same immutable program, with unchanged pixels.
Compact_Names:
 ld a,(Compact_Base)
 add a,5
 ld h,a
 ld l,$10
 jp (hl)
; Pointer-source helpers preserve HL/BC; AF/DE scratch.
Compact_HudPointers:
 ld a,(Compact_Base)
 add a,7
 ld d,a
 ld e,$10
 ret
Compact_EdgePointers:
 ld a,(Compact_Base)
 add a,10
 ld d,a
 ld e,$10
 ret
Compact_PatternHL:
 ld a,(Compact_Base)
 inc a
 ld h,a
 ld l,0
 ret
Compact_ColorHL:
 ld a,(Compact_Base)
 add a,3
 ld h,a
 ld l,0
 ret
Compact_PatternDE:
 ld a,(Compact_Base)
 inc a
 ld d,a
 ld e,0
 ret
Compact_ColorDE:
 ld a,(Compact_Base)
 add a,3
 ld d,a
 ld e,0
 ret
'''.replace('COMPACT_DATA_BASE',str(layout['data_base']))+edge_source+'\n'+boundaries
    if fast_transfers:
        helpers+='''
; Main Page0, foreground only. Exact long tail returns B=0 like old helper;
; exact short tail preserves the old B-N result. Both advance HL by N and
; preserve C/DE/IX/IY/IFF. CALL uses the original Page3 stack, never map SP.
Compact_ExactTail:
 REPT 64
 outi
 ENDR
Compact_ExactTailEnd:
 ld b,0
 ret
Compact_ExactShort:
 REPT 15
 outi
 ENDR
Compact_ExactShortEnd:
 ret
'''
    text=replace(text,'GameAuto_WorkersEnd:',helpers+'\nGameAuto_WorkersEnd:')
    path.write_text(text)
    path=assembly/'session-bank-tables.inc';text=path.read_text()
    edge_banks=[r['bank'] for r in records if r['kind']=='edge']
    text=re.sub(r'(GameSession_EdgeBanks:\n\s*db )[^\n]+',lambda m:m[1]+','.join(str(banks[n]) for n in edge_banks),text)
    terrain=json.loads((baseline/'session-build.json').read_text())['terrain_banks']
    text=re.sub(r'(GameSession_TerrainBanks:\n\s*db )[^\n]+',lambda m:m[1]+','.join(str(raw[n]) for n in terrain),text)
    path.write_text(text)

    path=assembly/'game-boundary-fast.inc';text=path.read_text()
    text=text.replace('    ld de,$a900','    call Compact_EdgePointers').replace('    ld ($7000),a','    ld ($7800),a').replace('    jp hud_upload.packet','    jp (hl)')
    path.write_text(text)
    path=assembly/'ring.inc';text=path.read_text();page,entry=layout['ring']
    text=replace(text,'    ld a,4\n    ld ($7000),a\n    ld a,(mapcol)\n    jp $aa00',
        f'    ld a,{page}\n    ld ($7800),a\n    ld a,(mapcol)\n    jp {entry+8192}')
    path.write_text(text)

    # SelectPhase owns data-half binding, including the cold64/128 cache loops
    # that use GameSession_Phase instead of the current gameplay phase byte.
    for path in list(assembly.rglob('*.inc'))+list(assembly.glob('*.asm')):
        text=path.read_text()
        text=text.replace('    ld (phase),a','    ld (phase),a\n    call Compact_SetPhaseBase')
        text=text.replace('    ld a,(phase)\n    add a,4\n    ld ($7000),a','    call GameSession_PhaseBank')
        text=text.replace('    ld a,(GameSession_Phase)\n    add a,4\n    ld ($7000),a','    ld a,(GameSession_Phase)\n    call Compact_SelectPhase')
        text=text.replace('    ld a,b\n    add a,4\n    ld ($7000),a','    call GameSession_PhaseBank')
        text=text.replace('    call $a300','    call Compact_Names')
        text=text.replace('    ld a,($8900)','    ld a,41')
        text=text.replace('    call Compact_Count','    ld a,41')
        if path.name=='session-phase.inc':
            text=text.replace('    ld a,(Full_Layout)\n    add a,$b8','    ld a,(Compact_Base)\n    add a,8\n    ld e,a\n    ld a,(Full_Layout)\n    add a,e')
        if path.name=='game-radar-fast.inc':
            text=replace(text,'    ld a,c\n    add a,$40\n    ld l,a\n    ld h,$a9',
                '    ld a,c\n    ld l,a\n    ld h,HIGH Compact_UniformTable')
            text=text.replace('    ld de,$8100','.compact_source:\n    ld de,$8100').replace('    add a,4\n    ld h,a','    add a,2\n    ld h,a')
        if path.name=='game-main.inc':
            text=replace(text,'    ld de,$8100','    call Compact_PatternDE')
            text=replace(text,'    ld de,$8500','    call Compact_ColorDE')
        # Keep actual code-page writes7800 separate from logical16KiB mapping.
        if path.name!='lab.asm':text=text.replace('    ld ($7000),a','    call Compact_Map16')
        else:
            # The generated Page0 phase/edge entries write physical pages.
            start=text.index('GameSession_PhaseBank:');end=text.index('GameAuto_WorkersEnd:',start)
            hot=text[start:end].replace('ld ($7000),a','ld (COMPACT_LOWER),a')
            text=text[:start]+hot+text[end:]
            at=text.index('Compact_Map16:');end=text.index(' INCLUDE "compact-banks.inc"',at)
            before=text[:at].replace('    ld ($7000),a','    call Compact_Map16')
            after=text[end:].replace('    ld ($7000),a','    call Compact_Map16')
            text=before+text[at:end]+after
            text=text.replace('ld (COMPACT_LOWER),a','ld ($7000),a')
        path.write_text(text)

    path=assembly/'modules/session/world.inc';text=path.read_text()
    text=replace(text,'    ld (Full_ResourceBank),a\n    call Compact_Map16','    ld (Full_ResourceBank),a\n    call Compact_MapPair')
    path.write_text(text)
    path=assembly/'game-host.inc';text=path.read_text()
    text=replace(text,'    ld a,(Full_ResourceBank)\n    call Compact_Map16','    ld a,(Full_ResourceBank)\n    call Compact_MapPair')
    path.write_text(text)

    # Active radar code owns previously unused Page3C110..C3FF. Its cold ROM
    # image occupies declared cold-bank padding atA000. Map decoder scratch at
    #C100..102 is disjoint. The single source-high operand is patched atomically
    # when the phase binds; IRQ never executes this foreground-only code.
    path=assembly/'modules/renderer/msx2.inc'
    path.write_text(replace(path.read_text(),'    INCLUDE "../../game-radar-fast.inc"','; Active radar is installed once into owned Page3 RAM.'))
    path=assembly/'lab.asm';text=path.read_text()
    marker='    INCBIN "session-auto-font.bin"\n    ENDIF\n    defs $c000-$,$ff'
    insertion='''    INCBIN "session-auto-font.bin"
    ENDIF
    ASSERT $ <= $a000
    defs $a000-$,$ff
    DISP $c110
Compact_RadarImage:
    INCLUDE "game-radar-fast.inc"
Compact_RadarImageEnd:
    ASSERT $ <= $c400
    ENT
    defs $c000-$,$ff'''
    text=replace(text,marker,insertion);path.write_text(text)
    path=assembly/'modules/session/boot.inc';text=path.read_text()
    text=replace(text,'    call GameAuto_Init','''    ld hl,$a000
    ld de,Compact_RadarImage
    ld bc,Compact_RadarImageEnd-Compact_RadarImage
    ldir
    call GameAuto_Init''')
    path.write_text(text)

    # Known raw pairs can issue two immediate bank writes without table
    # lookup, CALL or extra stack. All instructions are LD: AF flags and the
    # original logical A result are retained exactly at each existing site.
    raw_names={'GAME_NATIVE_BANK':71,'PLAYER_BANK':71,'PLAYER_DATA_BANK':72,'AUDIO_BANK':73,
               'GAME_AUDIO_BANK':73,'GAME_RESOURCE_BANK':74}
    for name in ['game-core.inc','game-main.inc','game-host.inc','modules/audio/session.inc','lab.asm']:
        path=assembly/name;text=path.read_text()
        def inline(m):
            label=m[1];page=raw[raw_names[label]]
            return f'    ld a,{page}\n    ld ($7000),a\n    ld a,{page+1}\n    ld ($7800),a\n    ld a,{label}'
        text=re.sub(r'    ld a,('+'|'.join(raw_names)+r')\n    call Compact_Map16',inline,text)
        path.write_text(text)

    # Worker now shares raw terrain bank1; its source is9000, descriptorA000.
    path=assembly/'modules/session/boot.inc';text=path.read_text()
    text=replace(text,'    ld a,SESSION_BOOT_BANK\n    call Compact_Map16\n    ld hl,$8000',
        '    ld a,SESSION_BOOT_BANK\n    call Compact_Map16\n    ld hl,$9000')
    path.write_text(text)
    path=assembly/'session-boot.inc';text=path.read_text()
    text=replace(text,'    ld hl,$9000','    ld hl,$a000')
    # Replay chain bank bytes are physical lower-window pages.
    text=text.replace('    call Compact_Map16','    ld ($7000),a')
    path.write_text(text)
    path=assembly/'session-boot-data.inc';text=path.read_text();n=0
    def entry(m):
        nonlocal n
        bank,address=layout['boot_pointers'][str(n)];n+=1
        return f'    db {bank}\n    dw {address}\n    dw {m[3]}'
    text=re.sub(r'    db (\d+)\n    dw (\d+)\n    dw (\d+)',entry,text)
    assert n==71;n=0;path.write_text(text)

    if boot_atlas:
        shutil.copyfile(ROOT/'src/screen4/compact-boot-atlas.inc',assembly/'compact-boot-atlas.inc')
        shutil.copyfile(allocation/'atlas-luts.bin',assembly/'compact-atlas-luts.bin')
        p,a=layout['atlas_table']
        (assembly/'compact-atlas-config.inc').write_text(f'COMPACT_ATLAS_TABLE_PAGE EQU {p}\nCOMPACT_ATLAS_TABLE_ADDRESS EQU {a}\nCOMPACT_ATLAS_TILE_COUNT EQU {layout["atlas"]["tiles"]}\nCOMPACT_ATLAS_PRIME_COUNT EQU {layout["atlas"]["prime_count"]}\n')
        path=assembly/'session-boot.inc';text=path.read_text()
        text=replace(text,'    ei\n.clear_wait:', '    ei\n    call .install\n.clear_wait:')
        text=replace(text,'    halt\n    jr .wait','''    ; Decode future atlas tiles only with at least one full refresh in
    ; reserve. Stop prefetch before the existing publication deadline.
    ld a,h
    and l
    inc a
    jr z,.idle
    push de
    call CompactAtlas_Prefetch
    pop de
    or a
    jr nz,.wait
.idle:
    halt
    jr .wait''')
        start=text.index('.stream:\n');end=text.index('.clear:\n',start)
        text=text[:start]+'''.stream:
    jp CompactAtlas_Frame
.install:
    ; One-time navigation-RAM reuse; hide this copy under the existing HMMV
    ; clear. IRQ scans keys throughout;128-byte chunks bound skip latency.
    push ix
    ld ix,32
    ld hl,$a200
    ld de,$3000
.install_chunk:
    ld bc,128
    ldir
    ld a,(GameSession_BootSkip)
    or a
    jr nz,.install_done
    dec ixl
    jr nz,.install_chunk
    call CompactAtlas_Init
    call CompactAtlas_Prime
.install_done:
    pop ix
    ret
'''+text[end:]
        path.write_text(text)
        path=assembly/'lab.asm';text=path.read_text()
        anchor='    ASSERT $ <= $df00\n    ENT\n    defs $c000-$,$ff'
        text=replace(text,anchor,'''    ASSERT $ <= $df00
    ENT
    defs $9200-$,$ff
    DISP $3000
CompactAtlas_Start:
    INCLUDE "compact-boot-atlas.inc"
CompactAtlas_End:
    ASSERT $ <= $4000
    ENT
    defs $a200-$,$ff
    defs $c000-$,$ff''')
        path.write_text(text)

    # Resident cold decoder owns Page0 mapping; return path restores main RAM.
    # C100..102 is scratch only during display-off/silent world preparation.
    decoder=(ROOT/'tests/fixtures/issue41-map-decoder.inc').read_text().split('MapEntry:\n',1)[1]
    decoder=decoder[decoder.index('.token:'):].replace('MapFragment','Compact_MapFragment').replace('MapByte','Compact_MapByte')
    decoder=decoder.replace('MapEnd:','').replace('jp z,$4500','jp z,Compact_MapDone').replace('DATAREG','$7000')
    decoder=decoder.replace('$c022','$c100').replace('$c023','$c101')
    wrapper='''GameSession_CopyMap:
 push ix
 push iy
 push bc
 ld e,a
 ld d,0
 ld hl,Compact_Banks
 add hl,de
 ld a,(hl)
 and 127
 ld e,a
 add a,a
 add a,e
 ld e,a
 ld hl,Compact_Maps
 add hl,de
 ld a,(hl)
 ld ($7000),a
 inc hl
 ld e,(hl)
 inc hl
 ld d,(hl)
 ex de,hl
 pop bc
 ld a,c
 out ($fc),a
 call Compact_MapFragment
 ld de,0
'''+decoder+'''
Compact_MapDone:
 call GameSession_RestorePage0
 pop iy
 pop ix
 ret
'''
    if layout['map_backend']=='stack16':
        wrapper='''; Cold-only constructor decoder. Every caller has display/VDP IRQ off.
; Preserve caller IFF, IX/IY and original Page3 stack; AF/BC/DE/HL scratch.
; Only bounded LD-HL/LD-H/LD-L/PUSH-HL/JP executes while SP fills Page0.
; No calls or interrupts may use that temporary data stack. C100..101 owns
; saved SP only until the complete16 KiB destination is built and restored.
GameSession_CopyMap:
 push ix
 push iy
 ld e,a
 ld d,0
 ld a,i
 push af
 di
 ld hl,Compact_Banks
 add hl,de
 ld a,(hl)
 and 127
 ld e,a
 add a,a
 add a,e
 ld e,a
 ld hl,Compact_Maps
 add hl,de
 ld a,(hl)
 ld ($7000),a
 inc hl
 ld e,(hl)
 inc hl
 ld d,(hl)
 ld a,c
 out ($fc),a
 ld ($c100),sp
 ld sp,$4000
 ld bc,1024
.chunk:
 ld a,(de)
 inc de
 ld ($7800),a
 ld a,(de)
 inc de
 ld l,a
 ld a,(de)
 inc de
 ld h,a
 jp (hl)
Compact_MapContinue:
 dec bc
 ld a,b
 or c
 jp nz,GameSession_CopyMap.chunk
 ld sp,($c100)
 call GameSession_RestorePage0
 pop af
 pop iy
 pop ix
 jp po,.disabled
 ei
.disabled:
 ret
'''
    path=assembly/'modules/mapper/page0.inc';text=path.read_text()
    start=text.index('GameSession_CopyMap:');end=text.index('; B/C=',start)
    header='; Generated compact-map override: logical map ID -> exact16K RAM.\n; Cold display/VDP IRQ off; AF/BC/DE/HL scratch, IX/IY/IFF preserved.\n; C100..101 saved-SP scratch; restore mainPage0 and SP before CALL/RET.\n; See generated_backends.compact_game in modules/contracts.json.\n'
    path.write_text(header+text[:start]+wrapper+'\n'+text[end:])

    # Each phase already owns an immediate name program; its now-unused raw
    # name prefix can bind the rest of that phase with fixed operands too.
    # Keep Base available before cache ranking, then tail-enter the binding.
    path=assembly/'lab.asm';text=path.read_text()
    start=text.index('    call Compact_SetPhaseBase\n    call GamePhase_Select',text.index('.hud:\n'))
    end=text.index('hud_upload:\n',start)
    text=text[:start]+'''    ld h,a
    and 1
    rrca
    rrca
    rrca
    rrca
    or $80
    ld (Compact_Base),a
    ld a,h
    call GamePhase_Select
    jp Compact_Bind
'''+text[end:]
    path.write_text(text)

    # A VDP IRQ immediately after LD A,I clears P/V on a real Z80. Retry
    # only the false sample before saving it. An enabled false sample means
    # the ISR has just acknowledged this game's sole maskable IRQ source;
    # the next VBlank is far beyond this bounded second read. With IFF=0 no
    # IRQ can corrupt either read. IRQ preserves AF; no NMI source is supported.
    path=assembly/'lab.asm';text=path.read_text()
    text=replace(text,'    ld a,i\n    push af\n    di',
        '    ld a,i\n    jp pe,.iff_sampled\n    ld a,i\n.iff_sampled:\n    push af\n    di')
    path.write_text(text)

    if fixed_ram:
        from fixedram_backend import adapt as fixed_adapt
        layout['fixed_ram']=fixed_adapt(assembly,backend)
    if backend=='megaram':
        for path in list(assembly.rglob('*.inc'))+list(assembly.glob('*.asm')):
            text=path.read_text().replace('ld ($7000),a','ld ($8000),a').replace('ld ($7800),a','ld ($a000),a').replace('ld ($6800),a','ld ($6000),a')
            if path.name=='lab.asm':
                text=replace(text,'    ld a,4\n    call $005f','    defs 5,0 ; Loader has already called CHGMOD before mapping MegaRAM.')
            path.write_text(text)

    # The frozen audio prefix has four equal-size authored bank stores.
    # Resolve their new resident CALL operands after the assembler defines it.
    audio=bytearray((assembly/'session-production-audio.bin').read_bytes())
    positions=[i for i in range(len(audio)) if audio[i:i+3]==b'\x32\0\x70']
    assert positions==[0x185a,0x18b8,0x190f,0x1966],positions
    assembler=str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus')
    def assemble():
        r=subprocess.run([assembler,'--nologo','--sym=lab.sym','--lst=lab.lst','lab.asm'],cwd=assembly,capture_output=True,text=True)
        (out/'assembler.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError((r.stdout+r.stderr)[-6000:])
        return symbols(assembly/'lab.sym')
    syms=assemble()
    for at in positions:audio[at:at+3]=b'\xcd'+syms['Compact_Map16'].to_bytes(2,'little')
    (assembly/'session-production-audio.bin').write_bytes(audio)
    syms=assemble()
    image=bytearray((allocation/'allocation.bin').read_bytes())
    image[:16384]=(assembly/'newrallyx.rom').read_bytes()
    for old,name in [(71,'game-native'),(121,'session-ui'),(122,'session-cold'),(73,'session-audio')]:
        data=(assembly/(name+'-linked.bin')).read_bytes();assert len(data)==16384
        at=raw[old]*8192;image[at:at+16384]=data
    boot=(assembly/'session-boot-linked.bin').read_bytes()
    prefix_bytes=layout.get('boot_prefix_bytes',4452)
    at=raw[1]*8192+4096;image[at:at+prefix_bytes]=boot[:prefix_bytes]
    for n in range(64):
        base=0x8000+(n%2)*4096
        program=bytearray((0x3e,(base>>8)+1,0x32))
        program.extend((syms['GameRadarFast_Draw.compact_source']+2).to_bytes(2,'little'))
        program.extend((0x3e,41,0x32));program.extend(syms['count'].to_bytes(2,'little'))
        for entry in [base+0x510,syms['GameSession_Boundaries'],syms['radar'],syms['hud_upload']]:
            program.append(0xcd);program.extend(entry.to_bytes(2,'little'))
        program.append(0xc3);program.extend(syms['render.hud_uploaded'].to_bytes(2,'little'))
        assert len(program)<256
        at=layout['data_base']*8192+n*4096
        image[at:at+len(program)]=program
    for record in layout.get('map_constructors',[]):
        page,address=record[:2];size=record[2] if len(record)>2 else 35
        at=page*8192+address-0xa000+size-2
        assert image[at-1:at+2]==b'\xc3\0\0', 'Constructor must end at its declared JP relocation'
        image[at:at+2]=syms['Compact_MapContinue'].to_bytes(2,'little')
    # All exact pooled bodies retain source operands; only resident helper and
    # exit targets change after linking. Placement was independent of targets.
    pages=[];locations={}
    for code in sorted({r['code'] for r in cases},key=lambda c:(-len(c),c)):
        if 'code_locations' in layout:
            p,a=layout['code_locations'][hashlib.sha256(code).hexdigest()]
            locations[code]=p*8192+a-0xa000
        else:
            choices=[(8192-len(p)-len(code),i) for i,p in enumerate(pages) if len(p)+len(code)<=8192]
            i=min(choices)[1] if choices else len(pages)
            if i==len(pages):pages.append(bytearray())
            locations[code]=(layout['code_base']+i)*8192+len(pages[i]);pages[i].extend(code)
    for code,at in locations.items():
        cursor=0
        while cursor<len(code):
            op=code[cursor]
            width=3 if op in (0x3a,0x21,0xcd,0xc3) else 2 if op in (0x0e,0x3e,0xf6,0xe6,0xd3,0x06,0xed,0x26,0x2e) else 1
            if op in (0xcd,0xc3):
                target=int.from_bytes(code[cursor+1:cursor+3],'little')
                if op==0xcd and fast_transfers and target&0xff00 in (0x100,0x200):
                    n=target&255
                    if target&0xff00==0x200:entry=syms['Compact_ExactShortEnd']-2*n
                    elif n<=64:entry=syms['Compact_ExactTailEnd']-2*n
                    else:entry=syms['Compact_ExactHead']+2*(255-n)
                else:entry=syms['GamePacketFast_Transfer' if op==0xcd else 'hud_upload.done']
                image[at+cursor+1:at+cursor+3]=entry.to_bytes(2,'little')
            cursor+=width
    assert len(image)<1048576,len(image)
    destination=ROOT/(('dist/experimental/fixedram' if fixed_ram else 'dist/compact') if backend=='ascii8' else f'references/build/{owner}-megaram-image')
    destination.mkdir(exist_ok=True,parents=True)
    (destination/'newrallyx.rom').write_bytes(image)
    shutil.copyfile(assembly/'lab.sym',out/'lab.sym')
    (out/'layout.json').write_text(json.dumps(layout,indent=2)+'\n')
    shutil.copyfile(destination/'newrallyx.rom',out/'newrallyx.rom')
    profile=json.loads((out/'session-build.json').read_text())
    profile.update(cartridge_mapper='ASCII8' if backend=='ascii8' else 'MegaRAM',logical_bank_pages=raw,boot_source_offset=raw[1]*8192+4096,world_storage='fixed' if fixed_ram else 'mapper')
    (out/'session-build.json').write_text(json.dumps(profile,indent=2)+'\n')
    report=dict(bytes=len(image),rom_sha256=hashlib.sha256(image).hexdigest(),sha256=hashlib.sha256(image).hexdigest(),mapper='ASCII8' if backend=='ascii8' else 'MegaRAM',minimum_main_ram_kib=64,
        invalid_logical_banks=[i for i,b in enumerate(banks) if b==255],
        minimum_mapper_ram_kib=0 if fixed_ram else 64,ram_mapper_required=not fixed_ram,
        status='Complete linkage; qualify this exact hash before publishing',
        workers_end=syms['GameAuto_WorkersEnd'],resident_end=syms.get('GamePlain_ResidentEnd',syms['palette']+32))
    (destination/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    if publish:
        if backend!='ascii8':raise ValueError('Only the cartridge backend can publish the default ROM')
        # Preserve the standard delivery metadata while binding the exact
        # playable artifact to its relinked source bundle and8 KiB mapper.
        target=ROOT/'dist/newrallyx.rom'
        manifest_path=target.with_name('manifest.json')
        manifest=json.loads(manifest_path.read_text())
        manifest.update(rom='dist/newrallyx.rom',rom_sha256=report['sha256'],bytes=len(image),
            mapper='ASCII8',source_bundle=str(out.resolve()),minimum_main_ram_kib=64,
            minimum_mapper_ram_kib=0 if fixed_ram else 64,ram_mapper_required=not fixed_ram,
            world_storage='fixed' if fixed_ram else 'mapper',
            compact_backend='stack16',capacity=dict(bytes=len(image),ceiling_bytes=1048576,below_ceiling=True),
            status='Local test candidate; see docs/hardware-targets.md for qualification; no release',
            boot_test_key=dict(key='F10 (MSX Shift+F5)',window='Hold during ROM/RAM opening until title; release before coin/start',
                effect='Prevent car/rock deaths; walls remain solid',reset='Reset clears the boot latch'))
        target.write_bytes(image)
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
        from src.toolchain.msx.resource_assets import publish as publish_resources
        publish_resources(ROOT,target,'default',bank_bytes=8192)
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--backend',choices=['ascii8','megaram'],default='ascii8')
    parser.add_argument('--publish',action='store_true')
    parser.add_argument('--bundle',type=Path,default=ROOT/'references/build/game')
    parser.add_argument('--baseline-maps',action='store_true',help='Reproduce the early42 map fixture without publishing the default ROM')
    parser.add_argument('--fast-transfers',action=argparse.BooleanOptionalAction,default=True,help='Exact transfer workers; disabling is diagnostic only')
    parser.add_argument('--boot-atlas',action=argparse.BooleanOptionalAction,default=True,help='Exact cold VRAM atlas; disabling is diagnostic only')
    parser.add_argument('--baseline-renderer',action='store_true',help='Reproduce the976KiB renderer for matched comparisons')
    parser.add_argument('--fixed-ram',action='store_true')
    args=parser.parse_args();build(args.backend,args.publish,args.bundle,baseline_maps=args.baseline_maps,fast_transfers=args.fast_transfers and not args.baseline_renderer,boot_atlas=args.boot_atlas and not args.baseline_renderer,fixed_ram=args.fixed_ram)

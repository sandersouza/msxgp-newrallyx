"""Bind cartridge world storage to fixed RAM4000..BFFF, without RAM banking.

Only generated sources change. Resident ROM is hidden only while Page0 workers
run; the identical clock IRQ lives in Page3. Existing expanded radar storage is
optional and independent. Cold constructor dictionaries retain their exact IDs.
"""
from pathlib import Path
from compact_game_build import replace

ROOT=Path(__file__).resolve().parents[1]


def adapt(assembly,backend):
    a=Path(assembly)
    for kind in ['cold','hot','irq']:
        name=f'session-fixedram-{kind}.inc'
        (a/name).write_text((ROOT/'src/screen4'/name).read_text())
    regs=[0x6000,0x6800,0x7000,0x7800] if backend=='ascii8' else [0x4000,0x6000,0x8000,0xa000]
    (a/'fixedram-config.inc').write_text('\n'.join(f'PLAIN_REG{i} EQU ${v:04x}' for i,v in enumerate(regs))+'\n')
    p=a/'lab.asm';text=p.read_text()
    text=replace(text,'    INCLUDE "game-radar-fast.inc"','    INCLUDE "game-radar-fast.inc"\n    INCLUDE "session-fixedram-irq.inc"')
    marker='Compact_RadarImageEnd:\n    ASSERT $ <= $c400\n    ENT\n    defs $c000-$,$ff'
    text=replace(text,marker,'''Compact_RadarImageEnd:
    ASSERT $ <= $c400
    ENT
    ASSERT $ <= $a400
    defs $a400-$,$ff
    DISP $0800
GamePlain_Image:
    INCLUDE "fixedram-config.inc"
    INCLUDE "session-fixedram-cold.inc"
GamePlain_ImageEnd:
    ASSERT $ <= $1400
    ENT
GamePlain_HotROM:
    DISP $2900
GamePlain_HotImage:
    INCLUDE "session-fixedram-hot.inc"
GamePlain_HotImageEnd:
    ASSERT $ <= $2b00
    ENT
    ASSERT $ <= $c000
    defs $c000-$,$ff''')
    p.write_text(text)
    # Reuse the ended boot replay only after credit/start cleared its key gate.
    # Cold0800 overlaps smoke list; restore it on every stopped ColdLoad.
    text=replace(text,'    ld (GameAuto_MemoryKiB),hl\n    call GameAuto_FormatStatus','    ld (GameAuto_MemoryKiB),hl\n    call GamePlain_FormatStatus')
    text=replace(text,'    ASSERT $ < $8000','''; A single probe window means fixed64KiB on this MSX2+ target, not16KiB RAM.
GamePlain_FormatStatus:
    ld hl,(GameAuto_MemoryKiB)
    ld a,h
    or a
    jr nz,.format
    ld a,l
    cp 16
    jr nz,.format
    ld hl,64
    ld (GameAuto_MemoryKiB),hl
    ld hl,.ram_label
    ld de,GameAuto_MapperText
    ld bc,6
    ldir
.format:
    jp GameAuto_FormatStatus
.ram_label:
    db "RAM   "
GamePlain_Install:
    call GameSession_AudioStop
    di
    ld a,SESSION_COLD_BANK
    call Compact_Map16
    ld hl,$a400
    ld de,GamePlain_Image
    ld bc,GamePlain_ImageEnd-GamePlain_Image
    ldir
    ld hl,GamePlain_HotROM
    ld de,GamePlain_HotImage
    ld bc,GamePlain_HotImageEnd-GamePlain_HotImage
    ldir
    call GamePlain_Init
    ret
GamePlain_ResidentEnd:
    ASSERT $ < $8000''')
    p.write_text(text)
    p=a/'modules/session/world.inc';text=p.read_text()
    text=replace(text,'    call GameSession_AudioStop','    call GamePlain_Install');p.write_text(text)
    p=a/'ring.inc';text=p.read_text()
    text=replace(text,'    call GameMap_LoadRun\n    jp GameSession_RestorePage0','    jp GamePlain_LoadRun\n    defs 3,0')
    text=replace(text,'    call GameMap_LoadColumns\n    jp GameSession_RestorePage0','    jp GamePlain_LoadColumns\n    defs 3,0')
    p.write_text(text)
    p=a/'game-main.inc';text=p.read_text();start=text.index('Game_RestoreOne:');end=text.index('Game_PatchOne:',start)
    # Keep this caller-facing entry in resident ROM; all actual RAM access and
    # return mapping happens in Page0 before the resident tail can execute.
    text=text[:start]+'Game_RestoreOne:\n    jp GamePlain_RestoreOne\n\n'+text[end:];p.write_text(text)
    p=a/'modules/mapper/page0.inc';text=p.read_text();start=text.index('GameSession_CopyMap:');end=text.index('; B/C=',start)
    text=text[:start]+'''GameSession_CopyMap:
    jp GamePlain_CopyMap
Compact_MapContinue EQU GamePlain_MapContinue

'''+text[end:]
    start=text.index('GameSession_PatchObject:')
    text=text[:start]+'GameSession_PatchObject:\n    jp GamePlain_PatchObject\n'
    p.write_text(text)
    return dict(world_ram=[0x4000,0xc000],cold_workers=[0x800,0x1400],hot_workers=[0x2900,0x2b00],no_extra_segments=True)

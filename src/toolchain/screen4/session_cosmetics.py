"""Full-session-only transformations; legacy assets/producers remain intact."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib,json,os,subprocess
from pathlib import Path
from hud_module import FONT,YELLOW_TICKS,RED_MARKS,CLASSIC_RED_MARKS,CLASSIC_YELLOW_TICKS

def terminal_font(root):
    from src.toolchain.msx.emulator import reference_machine,tcl
    out=root/'references/cache/msx-terminal-font';out.mkdir(parents=True,exist_ok=True)
    target=out/'font.bin'
    if not target.exists():
        code='set renderer none\nset sound_driver null\nset throttle off\nset save_settings_on_exit false\n'
        code+='filepool add -path '+tcl(root/'references/msxbios')+' -types system_rom -position 1\n'+reference_machine(root,'Panasonic_FS-A1WSX')+'\n'
        code+='after time 0.2 {set at [expr {[debug read memory 4]+256*[debug read memory 5]}];set f [open '+tcl(target)+' wb];puts -nonewline $f [debug read_block memory $at 2048];close $f;exit 0}\n'
        (out/'capture.tcl').write_text(code)
        with (out/'openmsx.log').open('w') as log:
            subprocess.run(['openmsx','-script',str(out/'capture.tcl')],check=True,timeout=30,stdout=log,stderr=subprocess.STDOUT,
                env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    font=target.read_bytes();assert len(font)==2048 and not any(font[32*8:33*8]) and any(font[65*8:66*8])
    return font

def cast_footer(root,out,image,colors):
    from session_title import prepare
    font=terminal_font(root)
    image,title=prepare(root,out,image,colors,font)
    symmetric=json.loads((out/'hud-module.json').read_text())['symmetric_gauge']
    (out/'session-cosmetics.json').write_text(json.dumps(dict(font_source='FS-A1WSX BIOS terminal caption; user-supplied finished namco - retrowork artwork',
        font_sha256=hashlib.sha256(font).hexdigest(),footer=[title['caption'],title['brand']],
        inverted_keys=[],fuel_label=[19,5],fuel_markers=dict(red=[list(p) for p in sorted(RED_MARKS if symmetric else CLASSIC_RED_MARKS)],yellow=[[x,58] for x in (YELLOW_TICKS if symmetric else CLASSIC_YELLOW_TICKS)])),indent=2)+'\n')
    return image

def hud_source(text,*,symmetric_gauge=True):
    assert 'GH_ReadScore:\n' in text and '    db 8,8,8,32,32,32,204,184,184,184,184,60,60,60' in text
    text=text.replace('GH_ReadScore:\n','GH_ReadScoreRaw:\n',1)
    text+='''
; Decode once on source change, then blank leading nibbles using glyph10.
GH_ReadScore:
    call GH_ReadScoreRaw
    push hl
    push bc
    ld hl,-3
    add hl,de
    ld b,2
.pair:
    ld a,(hl)
    or a
    jr nz,.first
    ld (hl),$aa
    inc hl
    djnz .pair
    ld a,(hl)
.first:
    cp $10
    jr nc,.done
    or $a0
    ld (hl),a
.done:
    pop bc
    pop hl
    ret
GameHUD_Ticks:
    db $02,$08,$20,$04,$10,$40
'''
    text=text.replace('184,60,60,60','184,57,57,57',1).replace('    cp 157\n','    cp 160\n',1)
    text=text.replace('    cp 7\n    jr c,.visible\n','    cp 7\n    jr c,.visible\n    cp 11\n    jr nc,.visible\n',1)
    start=text.index('GH_ReadFuel:');end=text.index('GH_CompareEight:',start)
    fuel=text[start:end].replace('    ld b,3\n.fuel_key:','    inc de\n    inc de\n    ld b,3\n.fuel_key:',1)
    fuel=fuel.replace('    inc de\n    djnz .fuel_key\n','    dec de\n    djnz .fuel_key\n    inc de\n    inc de\n    inc de\n    inc de\n',1)
    text=text[:start]+fuel+text[end:]
    text=text.replace('    ld (iy+row),a\n    ld (iy+16+row),b','    ld (iy+3+row),a\n    ld (iy+19+row),b',1)
    needle='    EDUP\n    ret\n.digits:'
    assert needle in text
    text=text.replace(needle,'''    EDUP
    ld a,(GH_Slot)
    sub 11
    add a,a
    ld l,a
    ld h,0
    ld de,GameHUD_Ticks
    add hl,de
    ld a,(hl)
    ld (iy+1),a
    inc hl
    ld a,(hl)
    ld (iy+17),a
    ret
.digits:''',1)
    text=text.replace('.digits:\n    ld a,(GH_Value)', '.digits:\n    IF HUD_SMALL_ROUND\n    ld a,(GH_Slot)\n    cp 6\n    jp z,GH_CopySmallRound\n    ENDIF\n    ld a,(GH_Value)',1)
    for addr,name in (('$e060','HIGH'),('$e0a0','SCORE'),('$e1b0','ROUND'),('$e00f','LIVES'),('$e26b','FUEL')):
        text=text.replace(addr,'HUD_INPUT_'+name)
    text=text.replace('(($ffff << (16-width)) & $ffff)','((1 << width)-1)').replace('(($ffff << (16-width)) & $ff)','(((1 << width)-1) & $ff)')
    if not symmetric_gauge:text=text.replace('db $02,$08,$20,$04,$10,$40','db 0,$42,$20,$04,$21,0')
    return text

"""One cartridge selects existing64/128KiB radar storage at cold boot.

The64KiB functions execute directly from main Page0. Expanded machines patch
their entry bytes to JP to resident banked-cache implementations. No duplicate
graphics, extra RAM segment or recurring capacity test is introduced.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from pathlib import Path
import re
from session_ram64 import replace_once


def rename(text, names):
    return re.sub(r'\b(?:'+ '|'.join(sorted(names,key=len,reverse=True))+r')\b',lambda m:names[m[0]],text)


def adapt(assembly,*,turbo=False):
    """Transform the generated64KiB view into one cold-selected cartridge.

    Run after session_ram64.adapt and before session_turbo.adapt. Work only in
    the temporary assembly directory; the preserved128KiB sources are inputs.
    replace_once deliberately fails if an upstream source anchor drifts.
    """
    a=Path(assembly);root=RUNTIME
    flags64=(a/'session-flags.inc').read_text()
    flags128=(root/'session-flags.inc').read_text()
    blink128=(root/'modules/radar/blink.inc').read_text()
    shared={'GameSession_FlagKey','GameSession_FlagCollected'}
    names={n:n+'128' for n in re.findall(r'(?m)^(\w+):',flags128+blink128) if n not in shared}
    resident_source=flags128+blink128
    for name in shared:
        resident_source=re.sub(r'(?ms)^'+name+r':.*?(?=^\w+:)', '',resident_source,count=1)
    resident=rename(resident_source,names)
    cache=(a/'modules/radar/cache-build.inc').read_text()
    at=cache.index('GameSession_DrawFlagDots:')
    workers=flags64+(a/'modules/radar/blink.inc').read_text()+cache[:at]
    original=(root/'modules/radar/cache-build.inc').read_text()
    prefix=original[:original.index('GameSession_DrawFlagDots:')]
    encoder=original[original.index('GameSession_EncodeFlags:'):]
    names|={'GameSession_BuildFlags':'GameSession_BuildFlags128','GameSession_EncodeFlags':'GameSession_EncodeFlags128'}
    workers+='\n'+rename(prefix+encoder,names)
    entries=set(re.findall(r'(?m)^(\w+):',workers))
    targets={n:n+'128' for n in re.findall(r'(?m)^(\w+):',flags128+blink128) if n in entries and n not in shared}
    targets.update(GameSession_BuildFlags='GameAuto_BuildFlags128',GameSession_EnsureFlags='GameAuto_NoEnsure')
    # Public entries are writable main-Page0 code. Expanded functions stay in
    # resident ROM because selecting their flag bank would hide Page0 code.
    patches='GameAuto_Patches:\n'+''.join(f'    dw {name},{target}\n' for name,target in targets.items())+'    dw 0\n'
    status=(root/'session-auto-status.inc').read_text().replace('IFDEF GameTurbo_Kind',f'IF {int(turbo)}')
    body=(root/'session-auto.inc').read_text()+'\n'+status+'\n'+patches+workers
    # Test controls consume a few extra resident bytes. Their foreground-only
    # input-tick helper can use the spare main-Page0 worker area in that build.
    # Production keeps its exact original location and bytes.
    path=a/'session-input.inc';text=path.read_text()
    input_at=text.index('GameSession_InputTick:')
    body+='\n    IF SESSION_TEST_MODE\n'+text[input_at:]+'\n    ENDIF\n'
    path.write_text(text[:input_at]+'    IF SESSION_TEST_MODE = 0\n'+text[input_at:]+'\n    ENDIF\n')
    #64 APIs move to their existing main Page0 allocation;128 code must stay
    # resident while its names/glyph cache replaces Page0.
    (a/'session-flags.inc').write_text(resident)
    (a/'modules/radar/blink.inc').write_text('; Unified variants are linked with their matching flag implementation.\n')
    (a/'modules/radar/cache-build.inc').write_text(cache[at:])
    path=a/'lab.asm';text=path.read_text()
    cold='''    INCLUDE "session-cold.inc"
GameSession_ColdEnd:
    ASSERT $ <= $2000
    ENT
    defs $c000-$,$ff'''
    new='''    INCLUDE "session-cold.inc"
GameSession_ColdEnd:
    ASSERT $ <= $2000
    ENT
    ASSERT $ <= $9000
    defs $9000-$,$ff
    DISP $0000
GameAuto_Workers:
'''+body+'''
GameAuto_WorkersEnd:
    ASSERT $ <= $07e0
    ENT
    ASSERT $ <= $9800
    defs $9800-$,$ff
    IF SESSION_HARDWARE_CHECK
    INCBIN "session-auto-font.bin"
    ENDIF
    defs $c000-$,$ff'''
    path.write_text(replace_once(text,cold,new))
    path=a/'modules/session/boot.inc';text=path.read_text()
    text=replace_once(text,'    call GameSession_ColdBoot\n','''    ld hl,$9000
    ld de,GameAuto_Workers
    ld bc,GameAuto_WorkersEnd-GameAuto_Workers
    ldir
    call GameAuto_Init
    call GameSession_ColdBoot
''')
    path.write_text(text)
    path=a/'session-boot.inc';text=path.read_text()
    anchor='    ld e,(iy+3)\n'
    text=replace_once(text,anchor,'''    push iy
    pop hl
    ld de,GameAuto_BootStatusDescriptor
    or a
    sbc hl,de
    call z,GameAuto_PaintStatus
'''+anchor)
    path.write_text(text)
    path=a/'modules/session/world.inc';text=path.read_text()
    text=replace_once(text,'    in a,($fc)\n    and 3\n','    ld hl,GameAuto_MapperMask\n    in a,($fc)\n    and (hl)\n')
    text=replace_once(text,'    in a,($ff)\n    and 3\n','    in a,($ff)\n    and (hl)\n')
    text=replace_once(text,'    ld d,2\n','    ld a,(GameAuto_Expanded)\n    add a,2\n    ld d,a\n')
    text=replace_once(text,'.allocated:\n','''.allocated:
    ld e,a
    ld a,(GameAuto_Expanded)
    or a
    ld a,e
    jr z,.off_ready
.off_segment:
    inc a
    cp b
    jr z,.off_segment
    cp c
    jr z,.off_segment
    ld (GameSession_FlagOffSegment),a
.off_ready:
''')
    text=replace_once(text,'    call GameSession_ClearFlags\n','    ld a,(GameAuto_Expanded)\n    or a\n    call z,GameSession_ClearFlags\n')
    text=replace_once(text,'GameSession_ColdLoad:\n','GameSession_ColdLoad:\n    xor a\n    ld (GameAuto_FlagsValid),a\n')
    path.write_text(text)

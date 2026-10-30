"""Opt-in CPU experiment; the frozen non-turbo assembly path is unchanged."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from pathlib import Path


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Turbo adapter anchor changed: {old!r}')
    return text.replace(old, new, 1)


def adapt(assembly):
    """Generate CPU-only wrappers from the selected rules, not duplicated logic.

    Detection selects the original or accelerated loop once. VDP/PSG/input and
    cold transitions retain base timing; no arbitrary banked BIOS call is safe.
    """
    assembly = Path(assembly)
    path = assembly / 'lab.asm'
    text = path.read_text()
    # BIOS information is captured after all boot RAM clears, while BIOS Page0
    # is still visible. No BIOS call is made through the later RAM mapping.
    text = once(text, '    call Game_Init\n', '''    ld a,($002d)
    ld (GameTurbo_BootVersion),a
    in a,($a8)
    and 3
    ld (GameTurbo_BootPrimary),a
    ld a,($fcc5)
    and 3
    ld (GameTurbo_BootSub),a
    call Game_Init
''')
    text = once(text, '    ld (ready),a\nloop:\n', '    ld (ready),a\n    jp GameTurbo_SelectLoop\nloop:\n')
    bridge = '''
; Page3 bridge: BIOS primary0/subslot0 is qualified at initialization.
; CHGCPU saves/transfers both CPU register sets. Caller owns IFF restoration.
GameTurbo_BIOSCode:
GameTurbo_BIOS EQU $d2e0
    push bc
    ld c,a
    in a,($a8)
    push af
    and $fc
    out ($a8),a
    ld a,c
    call $0180
    di
    im 2                    ; CHGCPU leaves the selected CPU in BIOS IM1.
    pop af
    out ($a8),a
    pop bc
    ret
GameTurbo_BIOSEnd EQU GameTurbo_BIOS+($-GameTurbo_BIOSCode)
    ASSERT GameTurbo_BIOSEnd <= $d2f8
GameTurbo_BackendEnd:
'''
    backend = source_path('session-turbo.inc').read_text() + bridge
    # Reuse the existing padded boot-worker reservation; no extra ROM bank,
    # RAM segment, VRAM allocation or gameplay buffer.
    text = once(text, '    ASSERT $ <= $2c00\n', backend + '\n    ASSERT $ <= $2c00\n')
    main = (assembly / 'game-main.inc').read_text()
    prepare = main[main.index('Game_Prepare:'):main.index('Game_Init:')]
    prepare = prepare.replace('Game_Prepare:', 'GameTurbo_Prepare:').replace('call Game_Frame', 'call GameTurbo_Frame').replace('call Game_Actors', 'call GameTurbo_Actors')
    core = (assembly / 'game-core.inc').read_text()
    frame = core[core.index('Game_Frame:'):core.index('Game_LogicTick:')]
    frame = frame.replace('Game_Frame:', 'GameTurbo_Frame:').replace('call Game_LogicTick', 'call GameTurbo_LogicTick')
    wrappers = '''
GameTurbo_Actors:
    call GameTurbo_Enter
    call Game_Actors
    jp GameTurbo_Leave
GameTurbo_LogicTick:
    ld a,(Round_State)
    or a
    jp nz,Game_LogicTick
    ld a,(Death_State)
    or a
    jp nz,Game_LogicTick
    call GameTurbo_Enter
    call Game_LogicTick
    jp GameTurbo_Leave
'''
    loop='''
GameTurbo_SelectLoop:
    ld a,(GameTurbo_Kind)
    or a
    jp z,loop               ; Original loop: no recurring unsupported-machine cost.
GameTurbo_Loop:
    call GameTurbo_Prepare
    call render
    call wait_blank
    call commit
GameTurbo_FrameDone:
    ld hl,frames
    inc (hl)
    jp GameTurbo_Loop
'''
    text = once(text, 'GameSession_BootEnd:\n', prepare + frame + wrappers + loop + '\nGameSession_BootEnd:\n')
    path.write_text(text)
    boot = assembly / 'modules/session/boot.inc'
    if 'GameAuto_Workers:' in text:
        boot.write_text(once(boot.read_text(),'    IF SESSION_HARDWARE_CHECK\n','    call GameTurbo_Init\n    IF SESSION_HARDWARE_CHECK\n'))
    else:
        boot.write_text(once(boot.read_text(), '    ; Boot bitmap scratch', '    call GameTurbo_Init\n    ; Boot bitmap scratch'))
    # The faster presentation cadence exposes the128KiB narrow corner band.
    # Use the existing64KiB six-unit guard for the unchanged doubled native step.
    motion=assembly/'session-motion.inc'
    text=motion.read_text()
    if '    cp 8\n' in text:
        if text.count('    cp 8\n')!=2:raise ValueError('Motion guard anchors changed')
        motion.write_text(text.replace('    cp 8\n','    cp 2\n'))

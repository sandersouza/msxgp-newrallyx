"""Default 64 KiB assembly view; preserved 128 KiB sources stay identical."""
from pathlib import Path


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'64 KiB adapter anchor changed: {old!r}')
    return text.replace(old, new, 1)


def motion_source(text):
    """Snapshot before a doubled native step can enter the corner-risk band.

    Primary native motion is doubled (at most6 units for the preserved2.75
    challenge ceiling). Heading changes can also change the contact-cell
    selection, so retain the conservative6-unit margin on both axes. A narrower
    axis-specific predicate failed the original long steering replay.
    """
    if text.count('    cp 8\n')!=2:raise ValueError('Motion snapshot predicate changed')
    text=text.replace('    cp 8\n','    cp 2\n')
    # Both exact44-byte motion copies already own BC/DE/HL. Keep BC=0 on
    # return, skipping the LDIR repeat overhead and the second counter load.
    for count in (20,24):
        anchor=f'    ld bc,{count}\n    ldir\n'
        if text.count(anchor)!=2:raise ValueError('Motion copy contract changed')
        replacement=('    ld bc,44\n' if count==20 else '')+f'    REPT {count}\n    ldi\n    ENDR\n'
        text=text.replace(anchor,replacement)
    return text


def adapt(assembly):
    source = Path(__file__).parent
    (assembly/'session-flags.inc').write_text((source/'session-ram64-flags.inc').read_text())
    path=assembly/'session-motion.inc'
    path.write_text(motion_source(path.read_text()))
    path = assembly/'modules/session/world.inc'
    text = path.read_text()
    for port in ('$fc','$ff'):
        text = replace_once(text, f'    in a,({port})\n    and 7\n',
                            f'    in a,({port})\n    and 3\n')
    text = replace_once(text, '    ld d,3\n', '    ld d,2\n')
    start = text.index('    ; The fourth private segment')
    end = text.index('    xor a\n', start)
    text = text[:start] + text[end:]
    # Invalidate before native initialization can report any collected flag.
    text = replace_once(text, '    call GameAudio_Init\n',
                        '    call GameSession_ClearFlags\n    call GameAudio_Init\n')
    text = replace_once(text, '    call GameSession_BuildFlags\n', '')
    path.write_text(text)

    # SCREEN5 menus own the entire VRAM. Rebuild after every UI->SCREEN4
    # transition, including the challenge reveal's resume without ColdLoad.
    path = assembly/'modules/renderer/video.inc'
    path.write_text(replace_once(path.read_text(), '    call GameSession_MapTerrain\n',
                                '    call GameSession_BuildFlags\n    call GameSession_MapTerrain\n'))

    path = assembly/'modules/radar/cache-build.inc'
    text = path.read_text()
    start = text.index('GameSession_DrawFlagDots:')
    text = (source/'session-ram64-cache.inc').read_text() + '\n' + text[start:]
    # Generate into the target record directly, without a staging copy.
    text = replace_once(text, '    ld ($ce80),a\n',
                        '    push af\n    call GameSession_SelectFlags\n    ld l,0\n    pop af\n    ld (hl),a\n')
    text = replace_once(text, '    ld de,$ce81\n',
                        '    ld a,(pattern_back)\n    add a,$38\n    ld d,a\n    ld e,1\n')
    for old, offset in (('$ceb4',52), ('$cf04',132)):
        text = replace_once(text, f'    ld de,{old}\n',
                            f'    ld a,(pattern_back)\n    add a,$38\n    ld d,a\n    ld e,{offset}\n')
    text = replace_once(text, '    ld iy,$cf54\n',
                        '    call GameSession_SelectFlags\n    ld l,212\n    push hl\n    pop iy\n')
    text = replace_once(text, '    ld a,(GameSession_Phase)\n    ld (iy+1),a\n',
                        '    ld a,(pattern_back)\n    add a,$38\n    ld (iy+1),a\n')
    path.write_text(text)

    path = assembly/'modules/radar/blink.inc'
    text = replace_once(path.read_text(), '    ld a,(phase)\n    ld h,a\n', '')
    text = replace_once(text, '    ld d,(hl)\n', '    ld d,h\n')
    path.write_text(replace_once(text, '    jp GameSession_RestorePage0\n', '    ret\n'))
    path = assembly/'modules/renderer/session-banks.inc'
    path.write_text(replace_once(path.read_text(), '    call GameSession_FlagUpload\n',
                                '    call GameSession_EnsureFlags\n    call GameSession_FlagUpload\n'))
    # This existing startup-worker reservation is copied at boot; keep hot
    # cache reads out of the crowded cold-code window. No new ROM bank or RAM
    # reservation. INI pacing is checked with the real VDP access callback.
    path = assembly/'lab.asm'
    path.write_text(replace_once(path.read_text(), 'GameSession_BootEnd:\n',
        '''GameSession_ReadFlagCache:
    ; BC=F298, HL=record. Exactly242 paced reads; B=0, HL+=242, H unchanged.
    REPT 242
    ini
    ENDR
    ret
GameSession_BootEnd:
'''))

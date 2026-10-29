"""Inline exact smoke retirement only in the optimized experiment host.

The original helper and shared src/screen5/smoke.inc remain unchanged. Inlining removes
only the CALL/RET around each cell; its comparisons, notifications and zero write
are identical, including the slow dirty-tile path and register preservation.
"""


def inline_body(text, label):
    start = text.index('Smoke_RetireCode:\n') + len('Smoke_RetireCode:\n')
    end = text.index('\nSmoke_DirtyTile:', start)
    body = text[start:end].rstrip()
    assert body.endswith('    ret')
    return body[:-len('    ret')].rstrip().replace('.empty', label) + '\n'


def transform(text):
    needle = '    call Smoke_RetireCode\n'
    assert text.count(needle) == 2, 'Expected exactly row/column retirement sites'
    for loop in ('clear_column', 'clear_row'):
        site = '.' + loop + ':\n' + needle
        assert text.count(site) == 1, loop
        optimized = inline_body(text, '.' + loop + '_empty')
        guarded = ('    IFDEF GAMEPLAY_CONFIGURED\n'
                   '    IF GAME_RENDER_OPT\n' + optimized +
                   '    ELSE\n' + needle +
                   '    ENDIF\n'
                   '    ELSE\n' + needle +
                   '    ENDIF\n')
        text = text.replace(site, '.' + loop + ':\n' + guarded)
    # The inline bodies make two forward exits exceed JR's signed byte range.
    # Keep all legacy opcodes intact; only the optimized host uses long exits.
    start = text.index('Smoke_PreTick:\n')
    end = text.index('\nSmoke_Address:', start)
    before, tick, after = text[:start], text[start:end], text[end:]
    for branch in ('z,.store', 'nz,.jumped'):
        short = '    jr ' + branch + '\n'
        assert tick.count(short) == 2, branch
        guarded = ('    IFDEF GAMEPLAY_CONFIGURED\n'
                   '    IF GAME_RENDER_OPT\n'
                   '    jp ' + branch + '\n'
                   '    ELSE\n' + short +
                   '    ENDIF\n'
                   '    ELSE\n' + short +
                   '    ENDIF\n')
        tick = tick.replace(short, guarded)
    text = before + tick + after
    return text

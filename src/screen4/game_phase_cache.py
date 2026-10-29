"""Four exact VRAM phase sets; two name tables keep their existing ownership."""
def transform(text):
    def change(old,new):
        nonlocal text
        if text.count(old)!=1: raise ValueError(f'Phase cache boundary changed: {old[:70]}')
        text=text.replace(old,new)
    change('    call Game_Init\n    call render','    call GamePhase_Init\n    call Game_Init\n    call render')
    start=text.index('    ld a,(back)\n',text.index('commit:'))
    end=text.index('.scroll:\n',start)
    text=text[:start]+'''    ld a,(pattern_back)
    ld (pattern_front),a
    add a,a
    add a,a
    add a,a
    add a,a
    out ($99),a
    ld a,$84
    out ($99),a
    ld a,(pattern_back)
    add a,a
    inc a
    out ($99),a
    ld a,$8a
    out ($99),a
    reg 3,$1f
    ld a,(back)
    add a,8
    out ($99),a
    ld a,$82
    out ($99),a
'''+text[end:]
    change('    ld (phase),a\n    add a,4','    ld (phase),a\n    call GamePhase_Select\n    ld a,(phase)\n    add a,4')
    change('''    ld hl,loaded_phase
    ld a,(back)
    or a
    jr z,.previous
    inc hl
.previous:
''','''    ld a,(pattern_back)
    ld e,a
    ld d,0
    ld hl,pattern_phases
    add hl,de
''')
    # Only pattern/color transfers change destination. Name table back remains
    # independent, including both dirty queues and resident commit ownership.
    start=text.index('hud_upload:');end=text.index('render.hud_uploaded:',start)
    body=text[start:end].replace('ld a,(back)','ld a,(pattern_back)')
    import re
    body=re.sub(r'    ld a,\(pattern_back\)\n    or a\n    jr z,\.(?:pattern|color)\n    set 7,h\n\.(?:pattern|color):\n    call address',
                '    call GamePattern_Address',body)
    text=text[:start]+body+text[end:]
    return text

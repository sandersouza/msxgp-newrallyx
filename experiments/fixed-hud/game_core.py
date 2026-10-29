"""Reuse authored gameplay adapters while dropping their legacy video producers.

Generated assembly and patched native bytes stay in ignored references outputs.
Native bytes are supplied by the existing contributor-ROM player builder.
"""
from pathlib import Path
import re

CONFIG = dict(FULL_GAME=0, INCREMENTAL_STAGE=9, ENEMY_COUNT=7,AUDIO_ENABLED=0,FLAG_POPUPS=0,
              ENEMY_CONTACT=1, ENEMY_RENDER=0, SMOKE_RUNTIME=1,
              COMPLETION_RUNTIME=1, HUD_ENABLED=0, PLAYER_FAST_BLITTER=1,
              SESSION_RUNTIME=0, RADAR_CELLS_ONLY=0, ROCK_COUNT=99)


def selected(text, **changes):
    """Resolve only existing assembler conditionals against this adapter config."""
    values = CONFIG | changes
    active = True
    stack = []
    result = []
    for line in text.splitlines():
        token = line.strip().split(';', 1)[0].strip()
        if token.startswith('IF '):
            if not active:
                stack.append((False, False))
                continue
            expression = token[3:].replace('&&', ' and ').replace('||', ' or ')
            expression = re.sub(r'!(?!=)', ' not ', expression)
            expression = re.sub(r'\b[A-Z][A-Z_0-9]*\b',
                                lambda m: str(values[m[0]]), expression)
            condition = bool(eval(expression, {'__builtins__': {}}, {}))
            stack.append((active, condition))
            active = active and condition
        elif token == 'ELSE':
            outer, condition = stack[-1]
            active = outer and not condition
        elif token == 'ENDIF':
            active = stack.pop()[0]
        elif active:
            result.append(line)
    if stack:
        raise ValueError('Unbalanced source conditions')
    return '\n'.join(result)+'\n'


def prepare(root, out,*,full_session=False):
    root, out = Path(root), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    def source(name, **changes):
        if full_session:
            changes=dict(FULL_GAME=1,AUDIO_ENABLED=1,FLAG_POPUPS=1)|changes
        return selected((root/'src'/name).read_text(), **changes)
    # Use the seed's immutable rock address list, as in the full-game adapter.
    rock = source('rock-collision.inc', FULL_GAME=1)
    rock = rock[:rock.index('Rock_Cells:')]
    death = source('death.inc').split('Death_Source:')[0]
    flags = source('flags.inc').split('Flag_Source:')[0]
    if not full_session:
        flags += '\nFlag_Records:\n    INCBIN "flag-records.bin"\n'
    score = source('score.inc')
    score = score[:score.index('Score_Frame:')] + score[score.index('Score_FastPoints:'):]
    fuel = source('fuel.inc')
    lives = source('lives.inc').split('Player_RestartNative:')[0]
    enemy = source('enemy.inc', FULL_GAME=1)
    smoke = source('smoke.inc')
    smoke_lookup = smoke[smoke.index('Smoke_CodeAtBC:'):smoke.index('Smoke_Batchable:')]
    declarations = smoke[:smoke.index('Smoke_CachePressure:')]
    smoke = declarations + smoke[smoke.index('Smoke_Init:'):smoke.index('Smoke_ClearPublishedRow:')]
    start = smoke.index('    ld hl,Smoke_Display\n')
    end = smoke.index('    ret\n', start)
    smoke = smoke[:start] + smoke[end:]
    smoke=smoke.replace('Smoke_ClearRings:\n','Smoke_ClearRings:\n    IFDEF GAMEPLAY_CONFIGURED\n    IF GAME_RENDER_OPT\n    call GameSmoke_ClearRows\n    ENDIF\n    ENDIF\n')
    notify='    push hl\n    ld hl,Game_WorldChanged\n    inc (hl)\n    ld hl,Game_SmokeChanged\n    inc (hl)\n    pop hl\n    ret\n'
    smoke += '\nSmoke_EnqueueRow:\n    IFDEF GAMEPLAY_CONFIGURED\n    IF GAME_RENDER_OPT\n    call GameSmoke_MarkRow\n    ENDIF\n    ENDIF\n'+notify
    smoke += '\nSmoke_Enqueue:\n    IFDEF GAMEPLAY_CONFIGURED\n    IF GAME_RENDER_OPT\n    call GameSmoke_MarkCloud\n    ENDIF\n    ENDIF\n'+notify
    smoke += smoke_lookup
    from game_smoke_fast import transform as inline_smoke_retirement
    smoke = inline_smoke_retirement(smoke)
    # No display queue is retained: parent SCREEN4 renderer samples native rings.
    completion = source('completion.inc')
    if full_session:
        from session_completion import round_runtime
        completion=round_runtime(completion)
    (out/'game-host.inc').write_text('\n'.join((rock, death, flags, score, fuel, lives, enemy, smoke, completion)))
    motion = (root/'src/full-native-motion.inc').read_text().split('Full_CacheInitNative:')[0]
    (out/'game-native-motion.inc').write_text(motion)
    ai = (root/'src/full-msx-enemies.inc').read_text()
    (out/'game-native-ai.inc').write_text('''; Place at $b600 in the native bank.
    jp Full_MSXAI
    jp Full_MSXContact
    jp Full_MSXPan
    jp Full_MSXAnimation
'''+ai)
    return dict(resident='game-host.inc', motion='game-native-motion.inc', ai='game-native-ai.inc')


def patch_native(code, program):
    """Apply the validated existing full-game motion/pan/animation boundaries."""
    code = bytearray(code)
    for address, expected, target in ((0xf3, 'dd6602', 0xb500),
                                      (0xf3e, '571e09', 0xb606),
                                      (0x1ddf, 'dd216880', 0xb609)):
        expected = bytes.fromhex(expected)
        if program[address:address+len(expected)] != expected:
            raise ValueError(f'Native adapter boundary changed at {address:04x}')
        code[address:address+len(expected)] = bytes((0xc3, target & 255, target >> 8))+bytes(len(expected)-3)
    return bytes(code)

"""Experimental clear cue and resumable original1B03/1B0A sound-busy wait."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME

def audio_runtime(source):
    old='''    ld a,(Round_State)
    or a
    jr nz,.silent            ; No driving/completion melody during level settlement.
'''
    assert source.count(old)==1,'Clear-cue selector anchor changed'
    return source.replace(old,'''    ld a,(Round_State)
    or a
    jr z,.active_round
    cp 1
    jr nz,.silent            ; Bonus conversion has effects only.
    ld a,($e9f5)
    bit 5,a
    jr nz,.complete          ; Original last-flag fanfare while the board settles.
    jr .silent
.active_round:
''',1)

def round_runtime(source):
    start=source.index('Round_Tick:\n');end=source.index('.bonus:\n',start)
    assert 'Silent port omits the unimplemented sound-busy wait.' in source[start:end]
    # The resident cartridge is nearly full. Put settlement-only work in the
    # already loaded cold worker; no bank switch, busy loop or active-frame call.
    return source[:start]+'''Round_Tick:
    cp 1
    jp z,GameSession_CompletionWait
'''+source[end:]

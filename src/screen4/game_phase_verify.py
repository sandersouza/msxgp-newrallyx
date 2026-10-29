"""Prove visible phase sets remain untouched throughout the live route."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
bundle=ROOT/'references/experiments/stage-one-3-enemies'
source=Path(__file__).with_name('game_verify.py').read_text()
hook=r'''
set cache_frames 0
set cache_hits 0
set cache_cold 0
set cache_front -1
proc visible_graphics {{front}} {{
    set base [expr {{$front*32768}}]
    return [debug read_block VRAM $base 2048][debug read_block VRAM [expr {{$base+16384}}] 2048]
}}
debug set_bp {syms['GamePhase_Select']} {{[debug read memory 0xc00c]==1}} {{
    set ::cache_front [debug read memory {syms['pattern_front']}]
    set ::cache_pixels [visible_graphics $::cache_front]
}}
debug set_bp {syms['hud_upload']} {{[debug read memory 0xc00c]==1}} {{
    set b [debug read memory {syms['pattern_back']}]
    if {{$b==[debug read memory {syms['pattern_front']}]}} {{error "Visible pattern set selected for writes"}}
    set old [debug read memory [expr {{{syms['pattern_phases']}+$b}}]]
    if {{$old==255}} {{incr ::cache_cold}}
    if {{$old==[debug read memory {syms['phase']}]}} {{incr ::cache_hits}}
}}
debug set_bp {syms['render_done']} {{[debug read memory 0xc00c]==1}} {{
    if {{$::cache_pixels ne [visible_graphics $::cache_front]}} {{error "Live render modified visible pattern/color bytes"}}
    incr ::cache_frames
    set f [open [file join $::out phase-cache.json] w]
    puts $f [format {{{{"frames":%d,"exact_phase_hits":%d,"cold_sets":%d,"visible_set_unchanged":true}}}} $::cache_frames $::cache_hits $::cache_cold]
    close $f
}}
'''
source=source.replace('{route_setup}\ndebug set_bp', '{route_setup}\n'+hook+'\ndebug set_bp',1)
source=source[:source.index("if __name__=='__main__':")]
ns={'__file__':str(Path(__file__).with_name('game_verify.py')),'__name__':'phase_cache_probe'}
exec(compile(source,str(Path(__file__).with_name('game_verify.py')),'exec'),ns)
out=ns['run'](10000,'route',True,bundle)
report=json.loads((out/'phase-cache.json').read_text())
assert report['frames']>900 and report['exact_phase_hits']>500 and report['cold_sets']<=4
report['rom_sha256']=hashlib.sha256((out/'measured.rom').read_bytes()).hexdigest()
report['source']=str(out)
report['scope']='Keyboard route through native game over, HUD/audio/3 enemies. Every render compares all visible terrain/HUD/boundary/radar pattern/color bytes before/after; the active set is excluded from cache selection. Emulator only.'
(out/'phase-cache.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

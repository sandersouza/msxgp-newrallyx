"""Keyboard-only fixed64KiB game-over and new-credit/start regression.

No code, state, seed, clock, life or score debugger writes. Cold hook and menu
observer record natural deaths and180 presentations after the next real start.
"""
import argparse
import json
from pathlib import Path
from compact_game_verify import verify


def run(mode='rom'):
    capture=[]
    def transform(script,s,out):
        capture.append(out)
        script=script.replace('if {$::active==300}', 'if {$::restart_frames==180}')
        script=script.replace('after time 120 ', 'after time 600 ')
        hook=f'''
set ::seen_over 0;set ::restart 0;set ::restart_frames 0;set ::death_count 0
set ::life [open [file join {{{out}}} lifecycle.tsv] w]
proc life {{kind}} {{puts $::life "$kind\t[machine_info time]\t[debug read memory 0xe1b0]\t[debug read memory 0xc0ee]";flush $::life}}
debug set_bp {s['GameSession_Death']} {{$::test_phase eq "active"}} {{incr ::death_count;life death}}
debug set_bp {s['GameSession_ColdLoad']} {{$::seen_over && [debug read memory {s['GameSession_LoadKind']}]==0}} {{set ::restart 1;life new_game}}
debug set_bp {s['GameTurbo_FrameDone']} {{$::restart && $::test_phase eq "active"}} {{
 if {{[debug read memory 0xc0ee]}} {{error "Unexpected F10 latch"}}
 incr ::restart_frames
}}
proc lifecycle_poll {{}} {{
 if {{$::test_phase eq "active"}} {{
  set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
  if {{$state==2 && $ready && !$::seen_over}} {{set ::seen_over 1;life game_over;keymatrixup 8 255}}
  if {{$::seen_over && !$::restart && $state==1 && $ready}} {{life title;keymatrixdown 0 32;set ::test_phase coin;set ::age 0}}
 }}
 after time .02 lifecycle_poll
}}
after time .02 lifecycle_poll
'''
        return script+hook
    verify(mode=mode,size=768,ram_kind='plain',fixed_ram=True,script_transform=transform)
    out=capture[0];events=(out/'lifecycle.tsv').read_text().splitlines()
    kinds=[e.split('\t')[0] for e in events]
    assert kinds.count('death')==3 and kinds.index('game_over')<kinds.index('title')<kinds.index('new_game'),events
    report=json.loads((out/'report.json').read_text());report.update(passed=True,lifecycle=events,new_game_presentations=180,scope=__doc__)
    (out/'gameover-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['rom','dos','basic'],default='rom');a=p.parse_args();run(a.mode)

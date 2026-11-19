"""Observe real cold lifecycle after DOS, BASIC or diagnostic cartridge boot.

Game-over uses keyboard-only natural deaths. Completion uses ten explicitly
controlled two-byte flag-contact probes, then the unmodified native score,
music settlement, fuel bonus, challenge and cold next-stage paths. No injected
code, clocks, stage-complete state, lives or score. Neither is a full-course run.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from mapper512_game_verify import verify

ROOT=Path(__file__).resolve().parents[1]


def run(mode='dos',scenario='completion',round_number=2,reset_check=False):
    f10=scenario=='completion'
    def transform(script,s,out):
        # Preserve the existing opening/hot-owner/graphics and timing observer.
        # Stop only after 180 presentations in the next/new game, not at a
        # fixed total count that could truncate a blocked UI or cold transfer.
        script=script.replace('if {$::count==50000}', 'if {$::done}')
        script=script.replace(f'if {{[debug read memory 0xc0ee]!={int(f10)}}}', 'if {[debug read memory 0xc0ee]!=$::expected_f10}')
        script=script.replace(f'if {{{int(f10)}}} {{nrx_boot_f10_down}}', 'if {$::expected_f10} {nrx_boot_f10_down}')
        script=script.replace('$::started && $::phase eq "boot" && [maincode]} {\n set base', '$::started && $::phase eq "boot" && !$::reset_started && [maincode]} {\n set base')
        script=script.replace('if {$::phase eq "active"} return', 'if {[lifecycle_poll]} return\n if {$::phase eq "active"} {after time .02 {checked poll};return}')
        # Fixed held-up input gives reproducible natural contact deaths. The
        # controlled completion fixture is independent of steering and F5.
        script=script.replace('set mask [lindex {128 64 16 32} [expr {($clock/24)%4}]];if {$clock%48<6} {set mask [expr {$mask|1}]}', 'set mask 32')
        hook=f'''
set ::done 0;set ::expected_f10 {int(f10)};set ::fixture_index 0;set ::fixture_wait 0
set ::over_seen 0;set ::title_after_over 0;set ::new_game 0;set ::post_frames 0
set ::clear_started 0;set ::bonus_seen 0;set ::next_seen 0;set ::challenge_seen 0
set ::audible_clear 0;set ::audible_over 0;set ::death_count 0
set ::reset_started 0;set ::reset_boot 0;set ::reset_title 0;set ::reset_frames 0
set ::life_file [open [file join {str(out)!r} lifecycle.jsonl] w]
proc event {{kind}} {{
 set row [format {{\u007b"event":"%s","seconds":%.9f,"tick":%d,"round":%d,"session":%d,"flags":%d,"round_state":%d,"fuel":%d,"music":%d,"f10":%d,"psg":"%s","score":"%s"\u007d}} $kind [machine_info time] [word {s['clock_ticks']}] [debug read memory 0xe1b0] [debug read memory 0xc7d0] [debug read memory {s['Flag_Count']}] [debug read memory {s['Round_State']}] [word 0xe26a] [debug read memory 0xe9f5] [debug read memory 0xc0ee] [binary encode hex [debug read_block {{PSG regs}} 0 14]] [binary encode hex [debug read_block memory 0xe0a0 8]]]
 puts $::life_file $row;flush $::life_file
}}
proc lifecycle_poll {{}} {{
 if {{![maincode] || ![ramcode 6]}} {{return 0}}
 set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 if {{$::reset_started}} {{
  if {{$state==1 && $ready && $::reset_boot && !$::reset_title}} {{
   if {{[debug read memory 0xc0ee]}} {{error "F10 survived reset"}}
   set ::reset_title 1;event reset_title;set ::phase release;set ::age 0;return 0
  }}
  return 0
 }}
 if {{$::phase ne "active"}} {{return 0}}
 if {{{int(scenario=='gameover')} && $state==2 && $ready && !$::over_seen}} {{
  set ::over_seen 1;event game_over;snapshot game-over;keymatrixup 8 255
 }}
 if {{$::over_seen && !$::title_after_over && $state==1 && $ready}} {{
  set ::title_after_over 1;event title_after_game_over;set ::phase release;set ::age 0
 }}
 if {{$state==7 && $ready && !$::challenge_seen}} {{set ::challenge_seen 1;event challenge;snapshot challenge}}
 return 0
}}
debug set_bp {s['GameSession_BootShow']} {{$::reset_started && [maincode]}} {{set ::reset_boot 1;event reset_opening}}
debug set_bp {s['GameSession_Death']} {{$::phase eq "active" && [maincode]}} {{incr ::death_count;event death}}
debug set_bp {s['GameSession_ColdLoad']} {{$::started && [maincode]}} {{
 event cold_load
 if {{$::over_seen && [debug read memory {s['GameSession_LoadKind']}]==0}} {{set ::new_game 1;event new_game}}
 if {{$::reset_started && $::reset_title && [debug read memory {s['GameSession_LoadKind']}]==0}} {{event reset_new_game}}
}}
debug set_bp {s['Flag_Update']} {{{int(scenario=='completion')} && $::phase eq "active" && !$::next_seen && !$::reset_started && [ramcode 6] && [debug read memory 0xe1b0]=={round_number} && [debug read memory {s['Flag_Count']}]<10}} {{
 incr ::fixture_wait
 if {{$::fixture_wait>=20 && ![debug read memory {s['Fuel_Active']}] && ![debug read memory {s['Flag_Jobs']}]}} {{
  set at [expr {{0xdf80+$::fixture_index*6}}]
  debug write memory {s['Rock_ProbeCell']} [debug read memory $at]
  debug write memory {s['Rock_ProbeCell']+1} [debug read memory [expr {{$at+1}}]]
  incr ::fixture_index;set ::fixture_wait 0;event controlled_flag_contact
 }}
}}
debug set_bp {s['GameSession_CompletionWait']} {{$::phase eq "active" && [maincode]}} {{
 if {{!$::clear_started}} {{set ::clear_started 1;set ::clear_fuel [word 0xe26a];set ::clear_score [debug read_block memory 0xe0a0 8];event settlement}}
 if {{[word 0xe26a]!=$::clear_fuel || [debug read_block memory 0xe0a0 8] ne $::clear_score}} {{error "Fuel/score changed during completion music"}}
 if {{[debug read memory 0xe9d3]==4 && ([debug read {{PSG regs}} 8] || [debug read {{PSG regs}} 9] || [debug read {{PSG regs}} 10])}} {{if {{!$::audible_clear}} {{set ::audible_clear 1;event completion_psg}}}}
}}
debug set_bp {s['Completion_Begin']} {{$::phase eq "active" && [ramcode 6]}} {{
 if {{[debug read memory 0xe9f5]&32}} {{error "Fuel bonus began before music completed"}}
 set ::bonus_seen 1;event fuel_bonus
}}
debug set_bp {s['GameSession_NextRound']} {{$::phase eq "active" && [maincode]}} {{event native_next_round}}
debug set_bp {s['GameTurbo_FrameDone']} {{$::phase eq "active" && [maincode]}} {{
 if {{$::over_seen && [debug read memory 0xe9f5]&4 && ([debug read {{PSG regs}} 8] || [debug read {{PSG regs}} 9] || [debug read {{PSG regs}} 10])}} {{set ::audible_over 1}}
 if {{{int(scenario=='completion')} && [debug read memory 0xe1b0]=={round_number+1} && [active] && !$::next_seen}} {{
  set ::next_seen 1;event next_stage;snapshot next-stage
 }}
 if {{($::next_seen || $::new_game) && [active]}} {{incr ::post_frames}}
 if {{$::post_frames>=180 && !$::reset_started}} {{
  event post_play
  if {{{int(reset_check)}}} {{
   set ::reset_started 1;set ::expected_f10 0;set ::phase boot;set ::age 0;set ::started 0
   keymatrixup 8 255;nrx_boot_f10_up;event reset;reset
   {('after time 10 {type_via_keybuf "'+chr(92)+'rrun '+chr(92)+'"NRX512.BAS'+chr(92)+'"'+chr(92)+'r"}') if mode=='basic' else ''}
  }} else {{set ::done 1}}
 }}
 if {{$::reset_title && [active]}} {{incr ::reset_frames;if {{$::reset_frames==180}} {{event reset_post_play;set ::done 1}}}}
}}
'''
        # Use Tcl's standard braced file path; Python repr would retain quotes.
        hook=hook.replace(repr(str(out)), '{'+str(out)+'}')
        return script.replace('proc poll {} {',hook+'\nproc poll {} {')
    report=verify(mode=mode,frames=50000,round_number=round_number,f10=f10,seed=0x1234,script_transform=transform)
    out=ROOT/report['path'];events=[json.loads(line) for line in (out/'lifecycle.jsonl').read_text().splitlines()]
    kinds=[e['event'] for e in events]
    if scenario=='completion':
        assert kinds.count('controlled_flag_contact')==10,kinds
        for k in ['settlement','completion_psg','fuel_bonus','native_next_round','next_stage','post_play']:assert k in kinds,(k,kinds)
        assert kinds.index('settlement')<kinds.index('fuel_bonus')<kinds.index('next_stage')
        if (round_number+1)%4==0:assert 'challenge' in kinds
    else:
        for k in ['death','game_over','title_after_game_over','new_game','post_play']:assert k in kinds,(k,kinds)
        assert kinds.count('death')>=3
    if reset_check:
        for k in ['reset','reset_opening','reset_title','reset_post_play']:assert k in kinds,(k,kinds)
        assert all(e['f10']==0 for e in events if e['event'] in ['reset_title','reset_post_play'])
    report.update(scenario=scenario,reset_check=reset_check,lifecycle=events,diagnostic_contact_writes=20 if f10 else 0,
                  lifecycle_scope='Completion: ten controlled native cell-contact probes, then real music/fuel/score/challenge/cold stages. Game-over: natural keyboard contact deaths, original lives and UI, new coin/start. Optional machine reset. No code, clock, life, score or completion-state injection.')
    # Raw frame traces remain disposable; this report records the exact observer.
    report['lifecycle_sha256']=hashlib.sha256((out/'lifecycle.jsonl').read_bytes()).hexdigest()
    (out/'lifecycle-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--mode',choices=['dos','basic','rom512'],default='dos')
    a.add_argument('--scenario',choices=['completion','gameover'],default='completion');a.add_argument('--round',type=int,default=2)
    a.add_argument('--reset',action='store_true');a.add_argument('--matrix',action='store_true');p=a.parse_args()
    if p.matrix:
        cases=[(m,'completion',n,n==2) for m in ['dos','basic'] for n in [2,3,4,7,8,11,12,15,16]]
        cases += [(m,'gameover',2,False) for m in ['dos','basic','rom512']]
        cases += [('rom512','completion',2,True),('rom512','completion',3,False)]
        def execute(case):
            mode,scenario,n,reset=case
            log=ROOT/f'references/build/issue42-lifecycle-{mode}-{scenario}-r{n}.log'
            command=[sys.executable,'-B',str(Path(__file__).resolve()),'--mode',mode,'--scenario',scenario,'--round',str(n)]
            if reset:command.append('--reset')
            with log.open('w') as output:result=subprocess.run(command,stdout=output,stderr=subprocess.STDOUT)
            return case,result.returncode,str(log.relative_to(ROOT))
        with ThreadPoolExecutor(max_workers=4) as workers:
            results=list(workers.map(execute,cases))
        print(json.dumps(results,indent=2));assert all(r[1]==0 for r in results),results
    else:run(p.mode,p.scenario,p.round,p.reset)

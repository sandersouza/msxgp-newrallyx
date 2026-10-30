"""Drive the integrated cartridge with keyboard input and retain exact states."""
import argparse,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.msx.emulator import reference_machine,tcl,scanout_recording_tcl


def run(bundle,*,headless=False,scenario='start'):
    from session_reference import configure
    configure(bundle)
    bundle=Path(bundle).resolve();out=Path(tempfile.mkdtemp(prefix='session-start-',dir=bundle))
    rom=(bundle/'fixed-hud.rom').read_bytes();(out/'measured.rom').write_bytes(rom)
    (out/'measured.sym').write_bytes((bundle/'lab.sym').read_bytes())
    syms={n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',(bundle/'lab.sym').read_text())}
    setup=f'''set save_settings_on_exit false
{'set renderer none' if headless else 'set renderer SDLGL-PP'}
set sound_driver null
set throttle off
set minframeskip 0
set maxframeskip 0
set vsync off
set cmdtiming real
set limitsprites true
set z80_freq 3579545
set z80_freq_locked true
set gamma 1
set brightness 0
set contrast 0
set blur 0
set noise 0
set scanline 0
set color_matrix {{{{1 0 0}} {{0 1 0}} {{0 0 1}}}}
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
cart {tcl(out/'measured.rom')} -romtype ASCII16
reset
activate_input_layer -blocking full_session_verification
{'' if headless else scanout_recording_tcl(out,syms['boot'])}
set out {tcl(out)}
set phase boot;set age 0;set presents 0;set captured_moving 0
set events [open [file join $out events.tsv] w]
proc snapshot {{name}} {{
 puts $::events "$name [machine_info time] [reg PC] [debug read memory 0xc7d0]";flush $::events
 set f [open [file join $::out "$name.ram"] wb];puts -nonewline $f [debug read_block memory 0 65536];close $f
 set f [open [file join $::out "$name.vram"] wb];puts -nonewline $f [debug read_block VRAM 0 131072];close $f
 set f [open [file join $::out "$name.regs"] wb];puts -nonewline $f [debug read_block {{VDP regs}} 0 64];close $f
 if {{{0 if headless else 1}}} {{screenshot -raw [file join $::out "$name.png"]}}
}}
set VDP.too_fast_vram_access_callback {{puts stderr "VRAM timing violation PC=[reg PC]";exit 2}}
debug set_bp {syms['loop']} {{}} {{incr ::presents}}
debug set_bp {syms['frame_done']} {{[info exists ::capture_next]}} {{
 set name $::capture_next;unset ::capture_next;snapshot $name
 if {{$name eq "moving"}} {{set ::captured_moving 1}}
}}
'''
    script=r'''
proc step {} {
 incr ::age
 set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {
  boot {if {$state==1 && $ready} {snapshot cast;keymatrixdown 0 32;set ::phase coin;set ::age 0}}
  coin {
   if {$::age==5} {keymatrixup 0 32}
   if {$::age>8 && $state==6 && $ready} {
    if {[debug read memory 0xc7d2]!=1} {error "Coin count diverged"}
    snapshot select;keymatrixdown 0 2;set ::phase start;set ::age 0
   }
  }
  start {
   if {$::age==5} {keymatrixup 0 2}
   if {$state==5 && ![info exists ::intro]} {set ::intro 1;snapshot intro}
   if {$state==0 && $::presents>2} {
    if {![info exists ::intro]} {error "Start cue absent"}
    set ::capture_next gameplay;keymatrixdown 8 32;set ::phase action;set ::age 0
   }
  }
  action {
   if {$::age==20} {keymatrixdown 8 1}
   if {$::age==35} {keymatrixup 8 1}
   if {$::age==100} {set ::capture_next moving}
   if {$::captured_moving} {catch {record stop};close $::events;exit 0}
  }
 }
 after time 0.02 poll
}
proc poll {} {if {[catch step problem]} {puts stderr "$::phase: $problem";exit 2}}
after time 90 {puts stderr "Session timeout phase=$::phase PC=[reg PC] SP=[reg SP] state=[debug read memory 0xc7d0] ready=[debug read memory 0xc7dd]";exit 3}
after time 0.02 poll
'''
    if 'GameSession_AudioStop.done' in syms:
        cold=json.loads((bundle/'session-build.json').read_text())['banks']['SESSION_COLD_BANK']
        prefix=rom[cold*16384:cold*16384+16].hex()
        setup+=f'''
set silence_checks 0
set cold_hooks [open [file join $out cold-hooks.tsv] w]
puts $cold_hooks "routine\tinclusive_cycles\tself_cycles"
set cold_stack {{}}
proc cold_enter {{name}} {{lappend ::cold_stack [list $name [machine_info time] 0]}}
proc cold_leave {{name}} {{
 lassign [lindex $::cold_stack end] owner start child
 if {{$owner ne $name}} {{puts stderr "Cold hook nesting mismatch $owner/$name";exit 2;return}}
 set cycles [expr {{([machine_info time]-$start)*3579545}}]
 puts $::cold_hooks "$name\t$cycles\t[expr {{$cycles-$child}}]";flush $::cold_hooks
 set ::cold_stack [lrange $::cold_stack 0 end-1]
 if {{[llength $::cold_stack]}} {{set parent [lindex $::cold_stack end];lset parent 2 [expr {{[lindex $parent 2]+$cycles}}];lset ::cold_stack end $parent}}
}}
debug set_bp {syms['GameSession_AudioStop.done']} {{[debug read_block memory 0x1400 16] eq [binary format H* {prefix}]}} {{
 foreach r {{8 9 10}} {{if {{[debug read {{PSG regs}} $r]}} {{puts stderr "Cold transition retained PSG volume";exit 2}}}}
 if {{([debug read {{PSG regs}} 7]&63)!=63 || [debug read memory 0xe9c0] || [debug read memory 0xe9c3]}} {{puts stderr "Cold transition retained tone/effect debt";exit 2}}
 incr ::silence_checks
 puts $::events "audio-silence [machine_info time] [reg PC] 0";flush $::events
}}
'''
        for name in ('GameSession_ColdLoad','GameSession_Video','GameSession_AudioStop','GameSession_RemoveFlag','GameSession_Prewarm'):
            setup+=f'debug set_bp {syms[name]} {{[debug read_block memory 0x1400 16] eq [binary format H* {prefix}]}} {{cold_enter {name}}}\n'
            setup+=f'debug set_bp {syms[name+".done"]} {{[debug read_block memory 0x1400 16] eq [binary format H* {prefix}]}} {{cold_leave {name}}}\n'
        name='GameSession_ChallengeFrame'
        ui=json.loads((bundle/'session-build.json').read_text())['banks']['SESSION_BANK']
        ui_prefix=rom[ui*16384:ui*16384+16].hex()
        setup+=f'debug set_bp {syms[name]} {{[debug read_block memory 0x8000 16] eq [binary format H* {ui_prefix}]}} {{cold_enter {name}}}\n'
        for label in (name+'.delay_done',name+'.unit_done',name+'.number_done','Full_UIChallengeWait.done','Full_UIChallengeWait.wait_done'):
            setup+=f'debug set_bp {syms[label]} {{[debug read_block memory 0x8000 16] eq [binary format H* {ui_prefix}]}} {{cold_leave {name}}}\n'
    if scenario!='start':
        if 'GameSession_ChallengeReveal' in syms:
            setup+=f'set challenge_reveal_base {syms["GameSession_ChallengeReveal"]}\n'
        script=Path(__file__).with_name('session-scenarios.tcl').read_text().replace('@SCENARIO@',scenario)
    if scenario=='smoke':
        script+=f'''
debug set_bp {syms['frame_done']} {{$::phase eq "smoke_action"}} {{
 snapshot [format smoke-%04d $::smoke_frames]
 incr ::smoke_frames
 # Continuous real keyboard movement and repeated smoke, without guest writes.
 foreach mask {{16 32 64 128}} {{keymatrixup 8 $mask}}
 set direction [lindex {{128 32 16 64}} [expr {{($::smoke_frames/45)%4}}]]
 keymatrixdown 8 $direction
 if {{$::smoke_frames%40<8}} {{keymatrixdown 8 1}} else {{keymatrixup 8 1}}
 if {{$::smoke_frames>=300}} {{
  foreach mask {{1 16 32 64 128}} {{keymatrixup 8 $mask}}
  next_phase finish
 }}
}}
'''
    if scenario=='controls':
        enabled=json.loads((bundle/'session-build.json').read_text())['banks']['SESSION_TEST_MODE']
        setup+=f"set test_enabled {enabled}\n"+Path(__file__).with_name('session-controls.tcl').read_text()
        stub=bytes((0x31,0xe0,0xf2,0xcd,syms['Death_Begin']&255,syms['Death_Begin']>>8,0xc3,0,0xf1))
        setup+=f'''
debug set_bp {syms['frame_done']} {{[info exists ::death_request]}} {{
 lassign $::death_request kind ::death_expected;unset ::death_request
 set ::death_saved {{}};foreach name {{AF BC DE HL IX IY SP PC}} {{lappend ::death_saved $name [reg $name]}}
 set ::native_saved [debug read_block memory 0xe000 4096]
 set ::host_saved [debug read_block memory 0xc400 1024]
 debug write memory {syms['Rock_Contact']} [expr {{$kind eq "rock"}}]
 debug write memory {syms['Enemy_Contact']} [expr {{$kind eq "enemy"}}]
 debug write memory {syms['Death_State']} 0
 debug write_block memory 0xf000 [binary format H* {stub.hex()}]
 reg PC 0xf000
}}
debug set_bp 0xf100 {{[info exists ::death_saved]}} {{
 if {{[debug read memory {syms['Death_State']}]!=$::death_expected}} {{puts stderr "Invulnerability contact policy failed";exit 2}}
 debug write_block memory 0xe000 $::native_saved
 debug write_block memory 0xc400 $::host_saved
 foreach {{name value}} $::death_saved {{reg $name $value}}
 unset ::death_saved;set ::death_checked 1
}}
'''
    if scenario=='radar':
        removed_index=int(os.environ.get('NRX_RADAR_REMOVE_FLAG','8'))
        assert 0<=removed_index<10,'Radar flag index must be 0..9'
        setup+=f'set radar_removed_index {removed_index}\n'
        stub=bytes((0x31,0xe0,0xf2,0xcd,syms['GameSession_RemoveFlag']&255,syms['GameSession_RemoveFlag']>>8,0xc3,0,0xf1))
        setup+=f'''
debug set_bp {syms['Game_Actors']} {{$::phase eq "radar_matrix" && $::matrix_index==128 && ![info exists ::l_removed]}} {{
 set ::l_removed 1
 set ::radar_saved {{}};foreach name {{AF BC DE HL IX IY SP PC}} {{lappend ::radar_saved $name [reg $name]}}
 debug write memory {syms['Flag_Active']+1+removed_index} 0
 debug write memory {syms['GameSession_FlagIndex']} {removed_index}
 debug write_block memory 0xf000 [binary format H* {stub.hex()}]
 reg PC 0xf000
}}
debug set_bp 0xf100 {{[info exists ::radar_saved]}} {{
 foreach {{name value}} $::radar_saved {{reg $name $value}}
 unset ::radar_saved
}}
'''
        script+=f'''
debug set_bp {syms['Game_Actors']} {{$::phase eq "radar_matrix"}} {{
 set n [expr {{$::matrix_index%128}}];set fx [expr {{$n%8}}];set fy [expr {{($n/8)%8}}];set blink [expr {{($n/64)*16}}]
 if {{$::matrix_index>=128 && $::radar_removed_index==8}} {{set fx 0;set fy 0;set blink [expr {{($::matrix_index/16)%2*16}}]}}
 set sx [debug read memory 0xdfba];set sy [debug read memory 0xdfbb]
 set cx [expr {{max(0,min(600,$sx*8-80))/8*8+$fx}}]
 set cy [expr {{max(0,min(1176,$sy*8-80))/8*8+$fy}}]
 foreach {{address value}} [list 0xc000 [expr {{$cx&255}}] 0xc001 [expr {{$cx>>8}}] 0xc002 [expr {{$cy&255}}] 0xc003 [expr {{$cy>>8}}] 0xc0f6 $blink 0xe24e 7] {{debug write memory $address $value}}
 set x [expr {{[debug read memory 0xdfb6]&31}}]
 set cell [expr {{[debug read memory 0xdfb6]+256*[debug read memory 0xdfb7]-0x9800}}]
 set y [expr {{$cell/32}}]
 set ordinary [expr {{[debug read memory 0xdf80]+256*[debug read memory 0xdf81]-0x9800}}]
 set points [list $x $y [expr {{($x+1)%32}}] $y [expr {{($x+9)%32}}] $y [expr {{$ordinary%32}}] [expr {{$ordinary/32}}] 0 0 31 55 31 0 0 55]
 if {{$::matrix_index>=128}} {{set points {{0 0 31 55 31 0 0 55 1 0 30 55 30 0 1 55}}}}
 set actor 0;set descriptor [debug read_block memory 0xe068 32]
 foreach {{px py}} $points {{
  set at [expr {{0xe068+$actor*32}}];debug write_block memory $at $descriptor
  debug write memory [expr {{$at+8}}] $px;debug write memory [expr {{$at+10}}] $py
  incr actor
 }}
 debug write memory {syms['Game_WorldChanged']} [expr {{([debug read memory {syms['Game_WorldChanged']}]+1)&255}}]
}}
debug set_bp {syms['frame_done']} {{$::phase eq "radar_matrix"}} {{
 snapshot radar-$::matrix_index
 incr ::matrix_index
 if {{$::matrix_index==256}} {{next_phase finish}}
}}
'''
    if scenario=='flags':
        setup+=f'''
set clear_costs [open [file join $out clear-costs.tsv] w]
set clear_token 0;array set clear_calls {{}}
proc clear_cost_enter {{}} {{
 set sp [reg SP];set ret [expr {{[debug read memory $sp]+256*[debug read memory [expr {{$sp+1}}]]}}]
 set group minimum
 if {{!([debug read memory 0xe24b]&63)}} {{set group [expr {{[debug read memory 0xe9f5]&32?"music_wait":"begin_bonus"}}]}}
 set n [incr ::clear_token]
 set bp [debug set_bp $ret "\\[reg SP\\]==[expr {{$sp+2}}]" "clear_cost_leave $n"]
 set ::clear_calls($n) [list $group [machine_info time] $bp]
}}
proc clear_cost_leave {{n}} {{
 lassign $::clear_calls($n) group start bp
 puts $::clear_costs "$group [expr {{([machine_info time]-$start)*3579545}}]";flush $::clear_costs
 debug remove_bp $bp;unset ::clear_calls($n)
}}
debug set_bp {syms['GameSession_CompletionWait']} {{[debug read memory 0xc7d0]==0}} {{clear_cost_enter}}
'''
        order=os.environ.get('NRX_TEST_FLAG_ORDER')
        if order:
            assert sorted(map(int,order.split()))==list(range(10))
            script=script.replace('set ::flag_order {0 9 8 1 2 3 4 5 6 7}', 'set ::flag_order {'+order+'}')
        native=json.loads((bundle/'game-resources.json').read_text())['banks']['GAME_NATIVE_BANK']
        code=bytearray((0x31,0xe0,0xf2,0x3e,native,0x32,0,0x70))
        for name in ('Flag_Update','Score_Update','Fuel_Begin','Parameters_Update'):
            code.extend((0xcd,syms[name]&255,syms[name]>>8))
        code.extend((0xaf,0x32,syms['Flag_Jobs']&255,syms['Flag_Jobs']>>8))
        for name in ('Round_Frame','Game_Events'):code.extend((0xcd,syms[name]&255,syms[name]>>8))
        code.extend((0x3a,0x1d,0xc0,0xc6,4,0x32,0,0x70,0xc3,0,0xf1))
        setup+='set flag_stub {'+' '.join(map(str,code))+'}\n'
        setup+=f'''
debug set_bp {syms['frame_done']} {{[info exists ::flag_request]}} {{
 set index $::flag_request;unset ::flag_request
 set address [expr {{0xdf80+$index*6}}]
 debug write memory 0xc486 [debug read memory $address]
 debug write memory 0xc487 [debug read memory [expr {{$address+1}}]]
 if {{$::flag_number in {{3 4}}}} {{
  set score [expr {{$::flag_number==3?19900:79900}}]
  set digits [split [format %08d $score] ""]
  foreach index {{4 5 6 7 0 1 2 3}} digit $digits {{
   set address [expr {{0xe0a0+$index}}]
   debug write memory $address [expr {{([debug read memory $address]&240)|$digit}}]
  }}
  set ::bonus_before [debug read memory 0xe00f]
 }}
 set ::saved_registers {{}};foreach name {{AF BC DE HL IX IY SP PC}} {{lappend ::saved_registers $name [reg $name]}}
 set p 0xf000;foreach byte $::flag_stub {{debug write memory $p $byte;incr p}}
 reg PC 0xf000
}}
debug set_bp 0xf100 {{[info exists ::saved_registers]}} {{
 foreach {{name value}} $::saved_registers {{reg $name $value}}
 unset ::saved_registers;set ::flag_executed 1
}}
'''
    (out/'session.tcl').write_text('if {[catch {\n'+setup+script+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'openmsx.log').open('w') as log:
        result=subprocess.run(['openmsx','-script',str(out/'session.tcl')],timeout=150,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    assert result.returncode==0,(out,(out/'openmsx.log').read_text()[-1200:])
    report=dict(rom_sha256=hashlib.sha256(rom).hexdigest(),scenario=scenario,passed=True,source=str(out),
                snapshots=[p.stem for p in out.glob('*.ram')],input='Keyboard coin/start/arrows/Space/P/F5; transition fixtures explicitly marked in the scenario source')
    machine=re.search(r'Reference RAM mapper: (\d+) bytes; machine: (\S+)',(out/'openmsx.log').read_text())
    assert machine,'Missing actual machine/RAM evidence'
    report.update(machine=machine[2],mapper_ram_kib=int(machine[1])//1024)
    if scenario=='flags':
        start,heard,bonus,fuel=map(float,(out/'clear-order.tsv').read_text().split())
        report['clear_sequence']=dict(settlement_start=start,first_audible_mode4=heard,bonus_start=bonus,settlement_seconds=bonus-start,fuel_before_bonus=int(fuel),fuel_and_score_stable_during_music=True,flag_order=os.environ.get('NRX_TEST_FLAG_ORDER','0 9 8 1 2 3 4 5 6 7'))
    if scenario=='flags':
        if os.environ.get('NRX_CLEAR_TEST_PAUSE')=='1':
            report['clear_sequence']['pause_seconds']=float((out/'clear-pause.tsv').read_text())
            report['clear_sequence']['pause_cursor_and_timer_frozen']=True
        import statistics,math
        values={}
        for row in (out/'clear-costs.tsv').read_text().splitlines():
            name,value=row.split();values.setdefault(name,[]).append(float(value))
        report['clear_costs']=[dict(name='GameSession_CompletionWait ('+name+')',calls=len(v),inclusive=dict(mean=statistics.mean(v),p95=sorted(v)[math.ceil(.95*len(v))-1],max=max(v))) for name,v in values.items()]
        report['clear_cost_method']='Matched entry-to-caller-PC/SP return inclusive guest cycles, including RET/IRQ; no tracked child self costs. Foreground settlement only. begin_bonus includes Completion_Begin; never add parent/child costs.'
    if scenario=='controls':report.update(test_mode=bool(enabled),input='Actual keyboard: international/Japanese equals, Return held/released; controlled real Death_Begin car/rock contacts with state restoration. Walls remain on the unchanged movement path.')
    report['cold_silence_checks']=sum(line.startswith('audio-silence ') for line in (out/'events.tsv').read_text().splitlines())
    if scenario=='integration':
        ram=(out/'challenging-stage.ram').read_bytes();word=lambda a:int.from_bytes(ram[a:a+2],'little')
        speed=abs(int.from_bytes(ram[0xe069:0xe06b],'little',signed=True))
        report['challenge_speed']=dict(native_round=ram[0xe1b0],target_per_tick=word(0xe027)/256,observed_per_tick=speed/256,
             parked=not(word(0xe025) or word(0xe029)),scope='Committed real-session challenge snapshot after native acceleration; no speed fixtures or native RAM edits.')
    if scenario=='smoke':
        states=[p.read_bytes() for p in sorted(out.glob('smoke-*.ram'))]
        count=lambda s:int.from_bytes(s[syms['Smoke_Placements']:syms['Smoke_Placements']+2],'little')
        deltas=[(count(b)-count(a))&65535 for a,b in zip(states,states[1:])]
        # Native life/round reset clears this diagnostic counter. It is not
        # another65536 smoke placements; bounded positive deltas count events.
        placements=sum(d for d in deltas if d<=16)
        phases={axis:sorted({s[address]&7 for s in states}) for axis,address in (('horizontal',0xc000),('vertical',0xc002))}
        assert len(states)==300 and placements>=4 and all(len(v)==8 for v in phases.values()),'Smoke visual fixture did not exercise placements/all fine-scroll phases'
        assert all(s[0xe24e]==3 for s in states),'Smoke fixture lost native three-enemy population'
        report['smoke_regression']=dict(committed_frames=len(states),native_placements=placements,counter_resets=sum(d>16 for d in deltas),fine_phases=phases,
            smoke_rows=[syms['GameSmoke_Rows'],syms['GameSmoke_Rows']+31],phase_cache=[syms['pattern_phases'],syms['pattern_phases']+7],
            scope='Each committed frame checks full HUD/radar and both boundary columns with an independent pixel oracle. Real keyboard only; three native enemies; no native RAM fixtures.')
    report['cold_hook_method']='Guest elapsed cycles from routine entry to pre-RET done label; self subtracts tracked nested bodies. CALL/RET instruction overhead remains with the parent or untracked. No parent/child inclusive sum.'
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(out);print(json.dumps(report,indent=2))
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,default=ROOT/'references/experiments/full-session-64k')
    parser.add_argument('--headless',action='store_true');parser.add_argument('--scenario',choices=['start','integration','two-player','flags','attract','radar','smoke','controls'],default='start')
    parser.add_argument('--contracts',action='store_true',help='Check stable active VRAM against the independent graphics oracle')
    args=parser.parse_args();folder=run(args.bundle,headless=args.headless,scenario=args.scenario)
    if args.contracts:
        from session_contracts import validate
        print(json.dumps(validate(folder,args.bundle),indent=2))

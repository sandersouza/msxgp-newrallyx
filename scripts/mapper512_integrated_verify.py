"""Full-game RAM-active integration against the frozen cartridge baseline.

The bootstrap and cold provider are diagnostic host/cartridge assistance,
explicitly excluded from a standalone512KiB loader claim. Gameplay bank refills
are forbidden. Original geometry/HUD/car oracle and native/PSG traces remain
independent of the new packet compiler.
"""
import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src/toolchain/screen4'),str(ROOT)]
from compact_game_build import symbols
from compact_game_report import distribution
from src.toolchain.msx.emulator import reference_machine,tcl,boot_test_key_bindings
from session_contracts import validate


def verify(candidate=True,round_number=5,frames=240,f10=False,transitions=False,input_clock='presentation',cold_storage=False):
    bundle=ROOT/'references/build/game-mapper512-integrated';old=ROOT/'references/build/game-compact-runtime'
    manifest=json.loads((bundle/'integration.json').read_text());before=(ROOT/'dist/newrallyx.rom').read_bytes()
    for name,sha in manifest['runtime_files'].items():assert hashlib.sha256((bundle/name).read_bytes()).hexdigest()==sha,name
    for stage in manifest['stages']:assert hashlib.sha256((bundle/f"stage-{stage['family']}/hot-image.bin").read_bytes()).hexdigest()==stage['sha256']
    old_s=symbols(old/'lab.sym');s=symbols(bundle/'lab.sym')
    out=Path(tempfile.mkdtemp(prefix=('integrated-' if candidate else 'control-')+f'r{round_number}-',dir=bundle))
    (out/'measured.rom').write_bytes(before) # Oracle's frozen cartridge input, not the RAM program.
    assert input_clock in ('presentation','native')
    storage=None;installed=[]
    if cold_storage:
        assert candidate
        cold=ROOT/'references/build/game-mapper512-cold'
        storage=json.loads((cold/'plan.json').read_text());bridge=(cold/'cold.bin').read_bytes();union=(cold/'union-mask.bin').read_bytes()
        assert hashlib.sha256(bridge).hexdigest()==storage['bridge']['sha256']
        assert storage['active_images']==manifest['stages']
    setup=[]
    for family in range(4):
        source=bundle/f'stage-{family}/hot-image.bin'
        if cold_storage:
            data=bytearray(source.read_bytes())
            for b,offset,n,_ in storage['context']+storage['map_staging']:
                at=b*16384+offset;assert not any(union[at:at+n])
                # Deliberately non-padding, shared across every family. The
                # active renderer must never consume these declared holes.
                data[at:at+n]=bytes((i*37+b*11+83)&255 for i in range(n))
            at=storage['bridge']['bank']*16384+storage['bridge']['offset'];assert not any(union[at:at+len(bridge)])
            data[at:at+len(bridge)]=bridge
            source=out/f'occupied-stage-{family}.bin';source.write_bytes(data)
            installed.append(dict(family=family,sha256=hashlib.sha256(data).hexdigest()))
        setup.append(f'set f [open {tcl(source)} rb];set ::images({family}) [read $f];close $f')
        setup.append(f'set f [open {tcl(bundle/f"stage-{family}/permissions.bin")} rb];set ::permissions({family}) [read $f];close $f')
    script=f'''set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set cmdtiming real
set limitsprites true
set z80_freq 3579545
set z80_freq_locked true
source [file join $::env(OPENMSX_SYSTEM_DATA) scripts _disasm.tcl]
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
{boot_test_key_bindings()}
cart {tcl(ROOT/'dist/newrallyx.rom')} -romtype ASCII8
reset
{chr(10).join(setup)}
set f [open {tcl(ROOT/'references/build/game/newrallyx.rom')} rb];set ::original [read $f];close $f
set f [open {tcl(bundle/'assembly/session-cold-linked.bin')} rb];set ::cold_image [read $f];close $f
set f [open {tcl(bundle/'assembly/session-boot-linked.bin')} rb];set ::boot_image [read $f];close $f
set ::raw_pages [dict create {' '.join(str(k)+' '+str(v) for k,v in manifest['raw_banks'].items())}]
set f [open {tcl(ROOT/'dist/newrallyx.rom')} rb];set ::cartridge [read $f];close $f
set ::candidate {int(candidate)};set ::takeover 0;set ::begun 0;set ::cold 0;set ::family -1;set ::dynamic 121
set ::phase boot;set ::age 0;set ::f5_down 0;set ::stable 0;set ::count 0;set ::warm 0;set ::cold_calls 0;set ::irqs 0
set ::work_start 0;set ::work 0;set ::start_active 0;set ::trace [open {tcl(out/'frames.tsv')} w]
set ::slot_events 0
set ::call_events 0
set ::cache_checks 0
set ::cold_epoch 0;set ::start_epoch 0;set ::transition_frames {{}}
puts $::trace "frame\tcx\tcy\tround\tenemies\tactive\twork\tperiod\tticks\tpsg\tnative\tcold_epoch"
set VDP.too_fast_vram_access_callback {{if {{$::begun}} {{puts stderr "VDP timing violation PC=[reg PC]";exit 7}}}}
proc checked {{script}} {{if {{[catch {{uplevel 1 $script}} error]}} {{puts stderr "FAIL $error PC=[reg PC] frame=$::count";exit 2}}}}
proc word {{address}} {{expr {{[debug read memory $address]+256*[debug read memory [expr {{$address+1}}]]}}}}
proc active {{}} {{expr {{[debug read memory 0xc7d0]==0 && [debug read memory 0xc00c] && [debug read memory 0xc400] && ![debug read memory 0xc490] && ![debug read memory {old_s['Round_State']}]}}}}
proc cache_policy {{}} {{
 set target [reg A];set visible [debug read memory 0xc028];set keys {{}}
 for {{set i 0}} {{$i<8}} {{incr i}} {{lappend keys [debug read memory [expr {{0x2820+$i}}]]}}
 set selected [debug read memory [expr {{0x28c0+$target}}]]
 if {{$selected>=8 || $selected==$visible || [lindex $keys $selected]!=$target}} {{
  set selected -1
  for {{set i 0}} {{$i<8}} {{incr i}} {{if {{$i!=$visible && [lindex $keys $i]==$target}} {{set selected $i;break}}}}
  if {{$selected<0}} {{set selected [lsearch -exact $keys 255]}}
  if {{$selected<0}} {{
   set family [debug read memory 0xdfc9];set at [expr {{(11+($target>>3))*16384+($target&7)*2048+1024}}]
   set best 255
   for {{set i 0}} {{$i<8}} {{incr i}} {{
    if {{$i==$visible}} continue
    set prior [lindex $keys $i];if {{$prior==255}} {{set prior 64}}
    binary scan [string index $::images($family) [expr {{$at+$prior}}]] cu cost
    if {{$cost<$best}} {{set best $cost;set selected $i}}
   }}
  }}
 }}
 if {{$selected<0}} {{error "No cache victim"}}
 set ::cache_expected $selected;set ::cache_target $target;set ::cache_ix [reg IX];set ::cache_iy [reg IY];set ::cache_iff [reg IFF]
 set stack [reg SP];set ret [word $stack]
 set condition [format {{[reg SP]==%d && [debug read ioports 252]%%32==1}} [expr {{$stack+2}}]]
 set ::cache_return_bp [debug set_bp $ret $condition {{checked {{
  if {{[debug read memory 0xc027]!=$::cache_expected || [debug read memory [expr {{0x28c0+$::cache_target}}]]!=$::cache_expected || [reg IX]!=$::cache_ix || [reg IY]!=$::cache_iy || [reg IFF]!=$::cache_iff}} {{error "Cache policy/register regression"}}
  incr ::cache_checks;debug remove_bp $::cache_return_bp
 }}}}]
}}
proc restore_cold {{}} {{debug write_block $::ram 21504 [string range $::cold_image 0 {s['GameSession_ColdEnd']-s['GameSession_ColdStart']-1}]}}
proc install_permissions {{}} {{
 # Permissions are already present in the immutable part of ring segment31.
}}
proc load_stage {{}} {{
 set family [debug read memory 0xdfc9]
 if {{$family!=$::family}} {{
  for {{set bank 11}} {{$bank<32}} {{incr bank}} {{debug write_block $::ram [expr {{$bank*16384}}] [string range $::images($family) [expr {{$bank*16384}}] [expr {{($bank+1)*16384-1}}]]}}
  set ::family $family
 }}
}}
proc raw_owner {{bank}} {{
 if {{$bank in {{0 71 73 123}}}} return
 if {{$bank==121 && $::dynamic==121}} return
 if {{!$::cold && [debug read memory 0xc7d0]==0 && [debug read memory 0xc00c] && [debug read memory 0xc400]}} {{error "Active gameplay requested cold owner $bank"}}
 incr ::cold_calls
 if {{$bank==121}} {{set bytes [string range $::images(0) 163840 180223]}} else {{
  if {{![dict exists $::raw_pages $bank]}} {{error "Unbound raw owner $bank"}}
  set at [expr {{[dict get $::raw_pages $bank]*8192}}];set bytes [string range $::cartridge $at [expr {{$at+16383}}]]
 }}
 debug write_block $::ram 163840 $bytes;set ::dynamic $bank
}}
proc finish_cold {{}} {{
 load_stage;install_permissions;raw_owner 121
 debug write memory 0xd10c [expr {{11+([debug read memory 0xc01d]>>3)}}]
 if {{[debug read memory 0xc0ee]!={int(f10)}}} {{error "Cold transition lost F10 latch"}}
 set ::cold 0
 if {{[info exists ::cold_return_bp]}} {{debug remove_bp $::cold_return_bp;unset ::cold_return_bp}}
}}
proc enter_cold {{}} {{
 if {{$::cold}} return
 incr ::cold_epoch
 set ::cold 1;restore_cold
 set sp [reg SP];set ret [word $sp]
 set condition [format {{$::takeover && $::cold && [reg SP]==%d}} [expr {{$sp+2}}]]
 set ::cold_return_bp [debug set_bp $ret $condition {{checked finish_cold}}]
}}
proc install {{}} {{
 set ::ram ""
 foreach name [debug list] {{if {{[debug desc $name] eq "memory mapper" && [debug size $name]==524288}} {{set ::ram $name}}}}
 if {{$::ram eq ""}} {{error "Exact512KiB RAM missing"}}
 if {{[debug read ioports 252]%32!=1 || [debug read ioports 255]%32!=0 || [debug read_block memory 0xc0d0 4] ne [binary format H* 01020304] || [debug read memory 0xc0f7]!=5}} {{error "Unexpected working segment ownership"}}
 set ::family [debug read memory 0xdfc9]
 set bytes $::images($::family)
 for {{set bank 6}} {{$bank<32}} {{incr bank}} {{debug write_block $::ram [expr {{$bank*16384}}] [string range $bytes [expr {{$bank*16384}}] [expr {{($bank+1)*16384-1}}]]}}
 debug write_block $::ram 16384 [string range $::cold_image 4096 {4096+s['GameAuto_WorkersEnd']-1}]
 restore_cold
 debug write_block $::ram [expr {{16384+0x2900}}] [string range $::boot_image 0 {s['GameSession_BootEnd']-s['GameSession_StartupWorkers']-1}]
 # Reapply exactly the already-selected expanded cache entry patches. No RAM
 # survey or cache reconstruction is performed during the active takeover.
 set at {4096+s['GameAuto_Patches']};set patched 0
 while {{1}} {{
  binary scan [string range $::cold_image $at [expr {{$at+3}}]] cu4 fields
  lassign $fields lo hi dstlo dsthi;set entry [expr {{$lo+256*$hi}}]
  if {{!$entry}} break
  if {{$entry>=0x7e0 || [incr patched]>32}} {{error "Invalid expanded-cache patch directory"}}
  debug write_block $::ram [expr {{16384+$entry}}] [binary format c* [list 195 $dstlo $dsthi]];incr at 4
 }}
 debug write_block memory {s['Mapper512_IRQ']} [string range $bytes [expr {{6*16384+{manifest['runtime_image_offset']}}}] [expr {{6*16384+{manifest['runtime_image_offset']+manifest['runtime_image_bytes']-1}}}]]
 debug write memory 0xd2d3 {s['Mapper512_IRQ']&255};debug write memory 0xd2d4 {s['Mapper512_IRQ']>>8}
 debug write_block memory 0xc110 [string range $::cold_image 8192 {8192+s['Compact_RadarImageEnd']-s['Compact_RadarImage']-1}]
 debug write memory 0xd10c [expr {{11+([debug read memory 0xc01d]>>3)}}]
 debug write memory 0x07e6 [expr {{128+([debug read memory 0xc01d]&7)*8}}]
 # Native smoke invokes two RAM trampolines installed by Smoke_Init. Live
 # diagnostic takeover must retarget them without reinitializing smoke/state.
 debug write_block memory 0xc7b0 [binary format c* [list 195 {s['Smoke_ClearNotify']&255} {s['Smoke_ClearNotify']>>8} 195 {s['Smoke_RecoveredNotify']&255} {s['Smoke_RecoveredNotify']>>8}]]
 install_permissions
 debug write memory 0xdfbd [lindex {{75 86 97 108}} $::family]
 if {{[debug read memory 0xc0ee]!={int(f10)}}} {{error "Takeover changed F10 latch"}}
 set ppi [debug read ioports 168];set sec [expr {{255-[debug read memory 65535]}}]
 set primary [expr {{($ppi&195)|(($ppi>>4)&12)|(($ppi>>2)&48)}}]
 set secondary [expr {{($sec&195)|(($sec>>4)&12)|(($sec>>2)&48)}}]
 set ::ram_primary $primary;set ::ram_secondary $secondary
 puts stderr "INSTALL slots ppi=$ppi sec=$sec target=$primary/$secondary p0=[debug read ioports 252] p3=[debug read ioports 255] mapper=$::ram rawp3=[binary encode hex [debug read_block $::ram 208 4]] cpu=[binary encode hex [debug read_block memory 0xc0d0 4]]"
 set stub [list 243 62 $secondary 50 255 255 62 $primary 211 168 62 6 211 253 62 7 211 254 251 195 {s['GameTurbo_FrameDone']&255} {s['GameTurbo_FrameDone']>>8}]
 debug write_block memory 0xd110 [binary format c* $stub]
 reg IFF 0;reg PC 0xd110;set ::takeover 1
}}
proc snapshot {{name}} {{
 foreach {{device ext size}} {{memory ram 65536 VRAM vram 131072 {{VDP regs}} regs 64}} {{
  set f [open [file join {tcl(out)} "$name.$ext"] wb];puts -nonewline $f [debug read_block $device 0 $size];close $f
 }}
}}
proc keyboard {{}} {{
 keymatrixup 8 255
 # Native scheduling reads the game's own elapsed-tick counter. It changes
 # only the keyboard, never the native clock or its per-presentation sampling.
 set clock {'[expr {[word 0xc440]/2}]' if input_clock=='native' else '$::count'}
 set mask [lindex {{128 64 16 32}} [expr {{($clock/24)%4}}]]
 if {{$clock%48<6}} {{set mask [expr {{$mask|1}}]}}
 keymatrixdown 8 $mask
 if {{{int(transitions)} && $::count==120}} {{keymatrixdown 7 2;after time .10 {{keymatrixup 7 2}}}}
}}
proc done {{}} {{
 if {{!$::begun}} {{
  if {{$::stable<5}} return
  if {{$::candidate && !$::takeover}} {{install;return}}
  set ::begun 1;set ::warm 0;set ::last [machine_info time]
 }}
 if {{$::takeover && ![debug read memory 0x7e2]}} {{error "Expanded cache disabled"}}
 if {{$::takeover && [debug read ioports 253]%32!=6}} {{error "Resident Page1 not restored"}}
 if {{[debug read memory 0xc0ee]!={int(f10)}}} {{error "F10 latch changed in gameplay"}}
 incr ::warm
 if {{$::warm<8}} {{set ::last [machine_info time];return}}
 incr ::count;set now [machine_info time];set period [expr {{($now-$::last)*3579545}}];set ::last $now
 set good [expr {{$::start_active && [active] && !$::cold && $::start_epoch==$::cold_epoch}}]
 if {{$::start_epoch!=$::cold_epoch}} {{lappend ::transition_frames $::count}}
 puts $::trace "$::count\t[word 0xc000]\t[word 0xc002]\t[debug read memory 0xe1b0]\t[debug read memory 0xe24e]\t$good\t$::work\t$period\t[debug read memory 0xc026]\t[binary encode hex [debug read_block {{PSG regs}} 0 14]]\t[binary encode hex [debug read_block memory 0xe088 224]]\t$::cold_epoch";flush $::trace
 if {{$good && ($::count%40==0 || $::count=={frames})}} {{snapshot "frame-$::count"}}
 if {{$::count=={frames}}} {{
  if {{$::takeover}} {{
   for {{set bank 7}} {{$bank<32}} {{incr bank}} {{
    if {{$bank==10}} continue
    if {{[debug read_block $::ram [expr {{$bank*16384}}] 16384] ne [string range $::images($::family) [expr {{$bank*16384}}] [expr {{($bank+1)*16384-1}}]]}} {{error "Immutable hot bank changed $bank"}}
   }}
  }}
  snapshot final;close $::trace
  puts stderr "PASS RAM integration candidate=$::candidate frames=$::count cold=$::cold_calls IRQ=$::irqs F10=[debug read memory 0xc0ee] cache=$::cache_checks";exit;return
 }}
 keyboard
}}
debug set_bp {old_s['GameSession_UI']} {{!$::begun && $::phase eq "boot"}} {{debug write memory 0xe000 52;debug write memory 0xe001 18}}
debug set_bp {old_s['GameSession_BootShow']} {{!$::begun}} {{if {{{int(f10)}}} {{nrx_boot_f10_down}}}}
debug set_bp {old_s['GameTurbo_FrameDone']} {{!$::takeover}} {{checked done}}
debug set_bp {s['GameTurbo_FrameDone']} {{$::takeover}} {{checked done}}
debug set_bp {old_s['GameTurbo_Loop']} {{!$::takeover && $::begun}} {{set ::work_start [machine_info time];set ::start_active [active]}}
debug set_bp {old_s['wait_blank']} {{!$::takeover && $::begun}} {{set ::work [expr {{([machine_info time]-$::work_start)*3579545}}]}}
debug set_bp {s['GameTurbo_Loop']} {{$::takeover && $::begun}} {{set ::work_start [machine_info time];set ::start_active [active];set ::start_epoch $::cold_epoch}}
debug set_bp {s['wait_blank']} {{$::takeover && $::begun && [debug read ioports 253]%32==6}} {{set ::work [expr {{([machine_info time]-$::work_start)*3579545}}]}}
debug set_bp {s['GameSession_ColdLoad']} {{$::takeover && [debug read ioports 252]%32==1}} {{checked enter_cold}}
debug set_bp {s['GameSession_Video']} {{$::takeover && !$::cold && [debug read ioports 252]%32==1}} {{checked enter_cold}}
debug set_bp {s['GameSession_MapTerrain']} {{$::takeover && $::cold}} {{checked load_stage}}
debug set_bp {s['Mapper512_RawEnter']} {{$::takeover && [debug read ioports 253]%32==6}} {{checked {{raw_owner [reg A]}}}}
debug set_bp {s['GameSession_CopyMap']} {{$::takeover && [debug read ioports 253]%32==6}} {{checked {{
 if {{!$::cold}} {{error "Active map reconstruction"}}
 set logical [reg A];set dest [expr {{[reg BC]&255}}]
 if {{$logical ni {{{' '.join(str(x) for x in json.loads((ROOT/'references/build/game/session-build.json').read_text())['map_banks'])}}}}} {{error "Unknown map owner $logical"}}
 debug write_block $::ram [expr {{$dest*16384}}] [string range $::original [expr {{$logical*16384}}] [expr {{($logical+1)*16384-1}}]]
 reg PC [word [reg SP]];reg SP [expr {{[reg SP]+2}}]
}}}}
debug set_bp {s['GameSession_PhaseSelect']} {{$::takeover && $::begun && [debug read ioports 252]%32==1}} {{checked cache_policy}}
debug set_bp {s['Mapper512_IRQ']} {{$::takeover}} {{checked {{
 incr ::irqs
 if {{[debug read memory 0xc7d0]!=0 && [debug read ioports 253]%32!=6}} {{error "Nonactive IRQ without resident key handler"}}
}}}}
debug set_watchpoint write_mem 65535 {{$::takeover}} {{checked {{if {{([reg A]&60)!=($::ram_secondary&60)}} {{error "Cartridge subslot selected during RAM execution"}}}}}}
debug set_watchpoint write_io 168 {{$::takeover}} {{checked {{if {{([reg A]&60)!=($::ram_primary&60)}} {{error "Cartridge primary slot selected during RAM execution"}}}}}}
debug set_watchpoint write_io 252 {{$::takeover}} {{if {{$::slot_events<20}} {{incr ::slot_events;puts stderr "PAGE0 WRITE PC=[reg PC] A=[reg A] SP=[reg SP]"}}}}
debug set_bp {s['GameTurbo_Loop']} {{$::takeover && $::warm<2}} {{puts stderr "NEW LOOP SP=[reg SP] P3=[binary encode hex [debug read_block memory 0xc0d0 4]]"}}
debug set_bp {s['GameAuto_Init']} {{$::takeover && [debug read ioports 252]%32==1}} {{snapshot failure;puts stderr "UNEXPECTED PROBE PC=[reg PC] SP=[reg SP] cold=$::cold frame=$::count p0=[debug read ioports 252] p1=[debug read ioports 253] ret=[word [reg SP]]";exit 11}}
debug set_watchpoint write_mem 0x7000 {{$::takeover && !$::cold}} {{snapshot failure;puts stderr "Legacy mapper write during gameplay PC=[reg PC] SP=[reg SP] I=[reg I] PPI=[debug read ioports 168] sub=[debug read memory 65535] p0=[debug read ioports 252] P1=[debug read ioports 253] p3=[debug read ioports 255] IRQ=$::irqs warm=$::warm rawp3=[binary encode hex [debug read_block $::ram 208 4]] bytes=[binary encode hex [debug read_block memory [reg PC] 16]]";exit 9}}
'''
    for address,bank in manifest['raw_sites'].items():
        guard='[debug read ioports 252]%32==1' if int(address)<0x4000 else '[debug read ioports 253]%32==6'
        script+=f'debug set_bp {address} {{$::takeover && {guard}}} {{checked {{raw_owner {bank}}}}}\n'
    for name in ['GameTurbo_Prepare','GameTurbo_Frame','GameAudio_Tick','Audio_RuntimeStep','Full_TurboOn','Full_TurboOff','GameTurbo_Enter','GameTurbo_Leave','GameTurbo_Set','GameTurbo_LogicTick','GameSession_AfterFrame','GameTurbo_Actors','GameSprites_Prepare','GameHUD_Prepare','render','Ring_Prepare','Game_RingPatch','GamePhase_Select','Compact_Bind','GameSession_FlagNames128','GameSession_LabelNames','GameSession_RadarColor','GameSession_SharedSprite']:
        if name in s:
            script+=f'debug set_bp {s[name]} {{$::takeover && $::warm<2 && $::call_events<80}} {{incr ::call_events;puts stderr "CALL {name} PC=[reg PC] SP=[reg SP] kind=[debug read memory 0xd2f8]"}}\n'
    script+=f'''proc poll {{}} {{
 if {{$::begun}} return
 incr ::age;set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
 boot {{if {{$state==1 && $ready}} {{nrx_boot_f10_up;if {{{int(f10)}}} {{set ::phase release}} else {{keymatrixdown 0 32;set ::phase coin}};set ::age 0}}}}
 release {{if {{$::age>=8 && ![debug read memory 0xc0fb]}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
 coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::phase start;set ::age 0}}}}
 start {{
  if {{$::age==5}} {{keymatrixup 0 2}}
  if {{$state==0 && [debug read memory 0xc00c]}} {{set ::phase advance;set ::age 0}}
 }}
 advance {{
  if {{$::age==10}} {{set ::prior_round [debug read memory 0xe1b0];keymatrixdown 7 2}}
  if {{$::age==15}} {{keymatrixup 7 2}}
  if {{$::age>18 && $state==0 && [debug read memory 0xc00c] && [debug read memory 0xe1b0]>$::prior_round}} {{
   if {{[debug read memory 0xe1b0]=={round_number}}} {{set ::stable 5;return}}
   set ::age 0
  }}
 }}
 }}
 after time .02 {{checked poll}}
}}
after time .02 {{checked poll}}
after time 180 {{puts stderr "TIMEOUT full integration phase=$::phase round=[debug read memory 0xe1b0] frames=$::count PC=[reg PC]";exit 2}}
'''
    (out/'verify.tcl').write_text(script)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB='512',OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    result=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=180)
    (out/'output.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0 and 'PASS RAM integration' in result.stderr,result.stderr[-2500:]
    graphics=validate(out,bundle if candidate else old)
    if candidate:
        graphics['reference_rom_sha256']=graphics.pop('rom_sha256')
        graphics['active_ram_images']=installed or [dict(family=d['family'],sha256=d['sha256']) for d in manifest['stages']]
        graphics['scope']+=' ROM hash identifies oracle/bootstrap input only; active RAM image seals are separate.'
        (out/'graphics-contracts.json').write_text(json.dumps(graphics,indent=2)+'\n')
    data=list(csv.DictReader((out/'frames.tsv').open(),delimiter='\t'));active_rows=[r for r in data if r['active']=='1']
    if transitions:
        assert max(int(r['round']) for r in data)==round_number+1,'F5 did not advance the RAM game'
        assert max(int(r['cold_epoch']) for r in data)>0,'Cold provider was not exercised'
    assert active_rows and graphics['passed'] and (ROOT/'dist/newrallyx.rom').read_bytes()==before
    observations=re.search(r'frames=\d+ cold=(\d+) IRQ=(\d+)',result.stderr);assert observations
    report=dict(passed=True,candidate=candidate,reference_rom_sha256=hashlib.sha256(before).hexdigest(),stage_images=manifest['stages'] if candidate else None,
        machine='Panasonic_FS-A1WSX_NR512',main_ram_kib=512,frames=frames,native_round=round_number,enemies=sorted({int(r['enemies']) for r in active_rows}),
        f10=f10,transitions=transitions,input_clock=input_clock,cold_storage=cold_storage,
        installed_ram_images=installed if cold_storage else None,
        cold_storage_scope='48KiB declared OS/world-shadow holes poisoned; actual bridge bytes resident. Diagnostic host fixture only, no filesystem/game callback handoff.' if cold_storage else None,
        work=distribution(float(r['work']) for r in active_rows),period=distribution(float(r['period']) for r in active_rows),
        active_frames=len(active_rows),cold_epochs=max(int(r['cold_epoch']) for r in data),cold_bank_refills=int(observations[1]),observed_irqs=int(observations[2]),cache_policy_checks=int(re.search(r'cache=(\d+)',result.stderr)[1]),immutable_hot_banks_checked=candidate,cartridge_windows_guarded=candidate,graphics=graphics,path=str(out.relative_to(ROOT)),
        verification_script_sha256=hashlib.sha256((out/'verify.tcl').read_bytes()).hexdigest(),
        scope=('Complete active game in32 actual RAM segments, with real IRQ/HUD/audio/native logic and strict VDP timing. Diagnostic host/cartridge cold provider and takeover remain explicit; no standalone512KiB loader or hardware acceptance.' if candidate else 'Frozen ASCII8 cartridge control on512KiB main RAM; existing expanded cache, HUD/audio and real sprite limits. This is not the RAM-active candidate.'))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--control',action='store_true');p.add_argument('--round',type=int,default=5);p.add_argument('--frames',type=int,default=240)
    p.add_argument('--f10',action='store_true');p.add_argument('--transitions',action='store_true')
    p.add_argument('--input-clock',choices=['presentation','native'],default='presentation');p.add_argument('--cold-storage',action='store_true');a=p.parse_args()
    verify(not a.control,a.round,a.frames,a.f10,a.transitions,a.input_clock,a.cold_storage)

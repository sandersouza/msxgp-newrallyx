if {[catch {
set save_settings_on_exit false
set renderer none
set sound_driver null
filepool add -path "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/references/msxbios" -types system_rom -position 1
source "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/scripts/msx/mapper_reference.tcl"
nrallyx_reference_machine "Panasonic_FS-A1WSX"
set firmwareswitch off
set throttle off
set z80_freq 3579545
set z80_freq_locked false
set limitsprites true
cart "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/radar-uniform-before/probe.rom" -romtype Normal
reset
set out "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/radar-uniform-before"
foreach n {cases fixtures seed} {set f [open [file join $out $n.bin] rb];set ::$n [read $f];close $f}
set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w]
set index 0;set started 0;set stage 0;set last_phase -1
proc issue {} {
 if {$::index==11264} {close $::result;close $::timing;exit 0;return}
 set at [expr {$::index*260}];binary scan [string range $::cases $at [expr {$at+3}]] cu* values
 set phase [lindex $values 0];set count [lindex $values 1];set mask [expr {[lindex $values 2]+256*[lindex $values 3]}]
 set f [expr {$phase*2624}]
 debug write_block memory 0xd400 [string range $::fixtures $f [expr {$f+1023}]]
 if {$phase!=$::last_phase} {
  debug write_block memory 0x8100 [string range $::fixtures [expr {$f+1024}] [expr {$f+1535}]]
  debug write_block memory 0x8500 [string range $::fixtures [expr {$f+1536}] [expr {$f+2047}]]
  debug write_block memory 0xa700 [string range $::fixtures [expr {$f+2048}] [expr {$f+2559}]]
  debug write_block memory 0xa940 [string range $::fixtures [expr {$f+2560}] [expr {$f+2623}]]
  set ::last_phase $phase
 }
 debug write_block memory 0x2400 [string range $::seed 0 511]
 debug write_block memory 0x2300 [string range $::seed 512 575]
 debug write_block memory 0xe068 [string range $::cases [expr {$at+4}] [expr {$at+259}]]
 debug write memory 0xe24e $count;debug write memory 0xc004 [expr {$phase&7}];debug write memory 0xc005 [expr {$phase>>3}]
 for {set i 0} {$i<10} {incr i} {debug write memory [expr {0xc501+$i}] [expr {($mask>>$i)&1}]}
 set routine [expr {$::stage?16771:16452}]
 set p 0xd110;foreach v [list 205 [expr {$routine&255}] [expr {$routine>>8}] 195 64 209] {debug write memory $p $v;incr p}
 reg SP 0xf380;reg PC 0xd110
}
debug set_bp 16449 {!$::started} {set ::started 1;issue}
debug set_bp 16452 {$::started} {set ::at_time [machine_info time]}
debug set_bp 16771 {$::started} {set ::at_time [machine_info time]}
debug set_bp 0xd113 {$::started} {set ::cycles [expr {round(([machine_info time]-$::at_time)*3579545)}]}
debug set_bp 0xd140 {$::started} {
 set cycles $::cycles
 set actual [debug read_block memory 0xc087 1];append actual [debug read_block memory 0xd400 1024] [debug read_block memory 0x2400 512] [debug read_block memory 0x2300 64]
 if {!$::stage} {set ::old $actual;set ::old_cycles $cycles;set ::stage 1;issue} else {
  if {$actual ne $::old} {set f [open [file join $::out mismatch-old.bin] wb];puts -nonewline $f $::old;close $f;set f [open [file join $::out mismatch-new.bin] wb];puts -nonewline $f $actual;close $f;puts stderr "Radar RAM mismatch case $::index";exit 3}
  puts -nonewline $::result $actual;puts $::timing "$::old_cycles $cycles"
  incr ::index;set ::stage 0;issue
 }
}
after time 600 {puts stderr "Radar fast probe timeout";exit 2}
} problem]} {puts stderr $problem;exit 2}

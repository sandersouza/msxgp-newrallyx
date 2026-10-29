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
cart "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/actor-bridge-synthetic/baseline/probe.rom" -romtype Normal
reset
set out "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/actor-bridge-synthetic/baseline"
set f [open [file join $out cases.bin] rb];set data [read $f];close $f
set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w];set index 0;set started 0
proc issue {} {
 if {$::index==1048} {close $::result;close $::timing;exit 0;return}
 set at [expr {$::index*310}];binary scan [string range $::data $at [expr {$at+1}]] cu* values
 debug write memory 0xe24e [lindex $values 0];debug write memory 0xc600 [lindex $values 1]
 debug write_block memory 0xc000 [string range $::data [expr {$at+2}] [expr {$at+5}]]
 debug write_block memory 0xc800 [string range $::data [expr {$at+6}] [expr {$at+53}]]
 debug write_block memory 0xe068 [string range $::data [expr {$at+54}] [expr {$at+309}]]
 debug write memory 52544 [expr {$::index&1}]
 set p 0xd110;foreach v [list 243 205 68 64 0 205 44 66 0 205 153 71 195 64 209] {debug write memory $p $v;incr p}
 reg SP 0xf380;reg PC 0xd110
}
debug set_bp 16407 {!$::started} {set ::started 1;issue}
debug set_bp 16452 {$::started} {set ::actor_at [machine_info time]}
debug set_bp 0xd114 {$::started} {set ::actor_cycles [expr {round(([machine_info time]-$::actor_at)*3579545)}]}
debug set_bp 16940 {$::started} {set ::prepare_at [machine_info time]}
debug set_bp 0xd118 {$::started} {set ::prepare_cycles [expr {round(([machine_info time]-$::prepare_at)*3579545)}]}
debug set_bp 18329 {$::started} {set ::commit_at [machine_info time]}
debug set_bp 0xd11c {$::started} {set ::commit_cycles [expr {round(([machine_info time]-$::commit_at)*3579545)}]}
debug set_bp 0xd140 {$::started} {
 puts $::timing "$::actor_cycles $::prepare_cycles $::commit_cycles"
 set at [expr {$::index*310}]
 if {[debug read_block memory 0xe068 256] ne [string range $::data [expr {$at+54}] [expr {$at+309}]]} {error "Native descriptors changed"}
 if {[debug read_block memory 0xc000 4] ne [string range $::data [expr {$at+2}] [expr {$at+5}]]} {error "Camera changed"}
 puts -nonewline $::result [debug read_block memory 0xc800 48]
 puts -nonewline $::result [debug read_block memory 0xc980 72]
 puts -nonewline $::result [debug read_block VRAM 0x18e0 288]
 set target [expr {[debug read memory 0xcd40]*576+0x2800}]
 puts -nonewline $::result [debug read_block VRAM $target 576]
 puts -nonewline $::result [debug read_block memory 52562 1]
 if {[debug read_block VRAM 0x1a38 72] ne [debug read_block memory 0xc980 72]} {error "SAT publication differs"}
 incr ::index;issue
}
after time 60 {puts stderr "Actor probe timeout";exit 2}
} problem]} {puts stderr $problem;exit 2}

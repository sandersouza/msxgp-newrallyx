if {[catch {
set save_settings_on_exit false
set renderer none
set sound_driver null
filepool add -path "/Users/sandersouza/Developer/msx-gamePorts/newrallyx/references/msxbios" -types system_rom -position 1
source "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/scripts/msx/mapper_reference.tcl"
nrallyx_reference_machine "Panasonic_FS-A1WSX"
set firmwareswitch off
set throttle off
set z80_freq 3579545
set z80_freq_locked false
set limitsprites true
cart "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/hud-synthetic/probe.rom" -romtype Normal
reset
set out "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/hud-synthetic"
set f [open [file join $out cases.bin] rb];set data [read $f];close $f
set result [open [file join $out actual.bin] wb];set times [open [file join $out cycles.txt] w];set index 0;set started 0
proc issue {} {
 if {$::index==1148} {close $::result;close $::times;exit 0;return}
 set at [expr {$::index*20}];binary scan [string range $::data $at [expr {$at+19}]] cu* c
 debug write memory 0xc002 [lindex $c 0]
 debug write_block memory 0xe060 [string range $::data [expr {$at+1}] [expr {$at+8}]]
 debug write_block memory 0xe0a0 [string range $::data [expr {$at+9}] [expr {$at+16}]]
 debug write memory 0xe1b0 [lindex $c 17];debug write memory 0xe00f [lindex $c 18];debug write memory 0xe26b [lindex $c 19]
 set p 0xd110;foreach v [list 243 205 114 64 205 255 67 195 64 209] {debug write memory $p $v;incr p}
 set ::begin [machine_info time];reg SP 0xf380;reg PC 0xd110
}
debug set_bp 16448 {!$::started} {set ::started 1;issue}
debug set_bp 17407 {$::started} {set ::commit [machine_info time]}
debug set_bp 0xd140 {$::started} {
 puts $::times [list [expr {round(($::commit-$::begin)*3579545)}] [expr {round(([machine_info time]-$::commit)*3579545)}]]
 puts -nonewline $::result [debug read_block VRAM 0x1a00 56]
 puts -nonewline $::result [debug read_block VRAM 0x2c80 448]
 incr ::index;issue
}
after time 60 {puts stderr "HUD probe timeout";exit 2}
} problem]} {puts stderr $problem;exit 2}

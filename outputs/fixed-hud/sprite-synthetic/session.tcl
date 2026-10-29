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
cart "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/sprite-synthetic/probe.rom" -romtype Normal
reset
set out "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/sprite-synthetic"
set f [open [file join $out cases.bin] rb];set data [read $f];close $f
set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w];set preparation [open [file join $out prepare-cycles.txt] w];set publication [open [file join $out commit-cycles.txt] w];set index 0;set started 0
proc issue {} {
 if {$::index==1163} {close $::result;close $::timing;close $::preparation;close $::publication;exit 0;return}
 set at [expr {$::index*50}];binary scan [string range $::data $at [expr {$at+1}]] cu* c
 debug write memory 0xc002 [lindex $c 0]
 debug write memory 52544 [lindex $c 1]
 debug write_block memory 0xc800 [string range $::data [expr {$at+2}] [expr {$at+49}]]
 set p 0xd110;foreach v [list 243 205 96 64 205 200 69 195 64 209] {debug write memory $p $v;incr p}
 set ::started_at [machine_info time]
 reg SP 0xf380;reg PC 0xd110
}
debug set_bp 16407 {!$::started} {set ::started 1;issue}
debug set_bp 17864 {$::started} {set ::prepared_at [machine_info time]}
debug set_bp 0xd140 {$::started} {
 puts $::timing [expr {round(([machine_info time]-$::started_at)*3579545)}]
 puts $::preparation [expr {round(($::prepared_at-$::started_at)*3579545)}]
 puts $::publication [expr {round(([machine_info time]-$::prepared_at)*3579545)}]
 set target [expr {[debug read memory 0xcd40]*576+0x2800}]
 puts -nonewline $::result [debug read_block memory 0xc980 72]
 puts -nonewline $::result [debug read_block VRAM 0x18e0 288]
 puts -nonewline $::result [debug read_block VRAM $target 576]
 puts -nonewline $::result [debug read_block memory 52562 1]
 set target [expr {[debug read memory 0xcd40]*576+0x2800}]
 if {[debug read_block VRAM 0x1a38 72] ne [debug read_block memory 0xc980 72]} {error "SAT upload differs"}
 incr ::index;issue
}
after time 60 {puts stderr "Sprite probe timeout";exit 2}
} problem]} {puts stderr $problem;exit 2}

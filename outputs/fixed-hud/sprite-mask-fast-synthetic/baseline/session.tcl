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
cart "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/sprite-mask-fast-synthetic/baseline/probe.rom" -romtype Normal
reset
set out "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/sprite-mask-fast-synthetic/baseline"
foreach n {cases seed} {set f [open [file join $out $n.bin] rb];set ::$n [read $f];close $f}
set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w]
set index 0;set started 0;set fast 0
set VDP.too_fast_vram_access_callback {if {$::started} {incr ::fast}}
proc issue {} {
 if {$::index==13587} {close $::result;close $::timing;set f [open [file join $::out strict.txt] w];puts $f $::fast;close $f;exit 0;return}
 set at [expr {$::index*50}];binary scan [string range $::cases $at [expr {$at+1}]] cu* c
 debug write memory 0xc002 [lindex $c 0]
 debug write memory 52544 [lindex $c 1]
 debug write_block memory 0xc800 [string range $::cases [expr {$at+2}] [expr {$at+49}]]
 set p 0xd110;foreach v [list 243 205 128 64 205 232 69 195 64 209] {debug write memory $p $v;incr p}
 reg SP 0xf380;reg PC 0xd110
}
debug set_bp 16439 {!$::started} {
 debug write_block memory 0xc980 [string range $::seed 0 359]
 debug write_block memory 0xcb00 [string range $::seed 360 935]
 debug write_block VRAM 0x2800 [string range $::seed 936 2087]
 debug write_block VRAM 0x1a38 [string range $::seed 2088 2159]
 debug write_block VRAM 0x18e0 [string range $::seed 2160 2447]
 set ::started 1;issue
}
debug set_bp 16512 {$::started} {set ::begin [machine_info time]}
debug set_bp 0xd114 {$::started} {set ::prepare_cycles [expr {round(([machine_info time]-$::begin)*3579545)}]}
debug set_bp 17896 {$::started} {set ::begin [machine_info time]}
debug set_bp 0xd117 {$::started} {set ::commit_cycles [expr {round(([machine_info time]-$::begin)*3579545)}]}
debug set_bp 0xd140 {$::started} {
 puts $::timing "$::prepare_cycles $::commit_cycles"
 puts -nonewline $::result [debug read_block memory 51584 360]
 puts -nonewline $::result [debug read_block memory 51968 576]
 puts -nonewline $::result [debug read_block memory 51264 130]
 puts -nonewline $::result [debug read_block memory 52544 19]
 puts -nonewline $::result [debug read_block memory 52576 11]
 puts -nonewline $::result [debug read_block VRAM 10240 1152]
 puts -nonewline $::result [debug read_block VRAM 6712 72]
 puts -nonewline $::result [debug read_block VRAM 6368 288]
 incr ::index;issue
}
after time 600 {puts stderr "Sprite-mask probe timeout";exit 2}
} problem]} {puts stderr $problem;exit 2}

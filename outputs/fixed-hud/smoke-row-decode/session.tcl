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
cart "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/smoke-row-decode/probe.rom" -romtype Normal
reset
set out "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/smoke-row-decode"
set f [open [file join $out cases.bin] rb];set data [read $f];close $f
set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w]
set index 0;set started 0
proc issue {} {
 if {$::index==2285} {close $::result;close $::timing;exit 0;return}
 set at [expr {$::index*1066}]
 debug write_block memory 0xe400 [string range $::data $at [expr {$at+1023}]]
 debug write_block memory 0x2800 [string range $::data [expr {$at+1024}] [expr {$at+1055}]]
 debug write_block memory 0xc702 [string range $::data [expr {$at+1056}] [expr {$at+1057}]]
 debug write_block memory 0xc711 [string range $::data [expr {$at+1058}] [expr {$at+1059}]]
 debug write memory 0xc0af 165;debug write memory 0xc0b2 165;debug write memory 0x27ff 165;debug write memory 0x2820 165
 debug write memory 0xc701 1;debug write memory 0xc080 0;debug write memory 0xc051 0
 binary scan [string range $::data [expr {$at+1060}] [expr {$at+1065}]] cu* p
 set ::hook [lindex $p 0];set x [lindex $p 1];set y [lindex $p 2];set h [expr {[lindex $p 3]+256*[lindex $p 4]}]
 debug write memory 0xc0b0 [lindex $p 5]
 debug write memory 0xc510 $x;debug write memory 0xc511 $y
 debug write_block memory 0x0800 [string repeat "Z" 3072];debug write_block memory 0xc082 "4"
 set target [lindex [list 16458 16827 16847 16794 16459 16620 16596 16514] $::hook]
 set p 0xd100;foreach v [list 205 [expr {$target&255}] [expr {$target>>8}] 0 205 220 65 0 205 97 65 195 64 209] {debug write memory $p $v;incr p}
 reg AF 0x7393;reg BC [expr {$x*256+$y}];reg DE 0x7a69;reg HL $h;reg IY 0x9a89;reg SP 0xf380;reg PC 0xd100
 set ::registers [list [reg AF] [reg BC] [reg DE] [reg HL]];set ::hook_at [machine_info time]
}
debug set_bp 16449 {!$::started} {set ::started 1;issue}
debug set_bp 0xd103 {$::started} {
 set ::hook_cycles [expr {round(([machine_info time]-$::hook_at)*3579545)}]
 if {$::hook<=3 && $::registers ne [list [reg AF] [reg BC] [reg DE] [reg HL]]} {error "Hook clobbered original registers"}
 if {[debug read_block memory 0x0800 3072] ne [string repeat "Z" 3072] || [debug read_block memory 0xc082 2] ne "4"} {error "Hook dropped preceding sparse cache before restoration"}
 if {$::hook in {3 4} && ([debug read memory 0xc080]!=1 || [debug read memory 0xc051]!=1)} {error "Ring reset failed to notify parent cache"}
}
debug set_bp 16860 {$::started} {set ::candidate_at [machine_info time]}
debug set_bp 0xd107 {$::started} {
 set ::candidate_cycles [expr {round(([machine_info time]-$::candidate_at)*3579545)}]
 if {[reg IY]!=0x9a89} {error "Cache builder changed IY"}
 foreach address {0x27ff 0x2820 0xc0af 0xc0b2} {if {[debug read memory $address]!=165} {error "Smoke cache scratch out of bounds"}}
 set ::candidate_count [debug read_block memory 0xc082 2];binary scan $::candidate_count s count
 set ::candidate_list [debug read_block memory 0x0800 [expr {$count*3}]]
 puts -nonewline $::result $::candidate_count;puts -nonewline $::result [debug read_block memory 0x0800 3072]
 puts -nonewline $::result [debug read_block memory 0x2800 32];puts -nonewline $::result [debug read_block memory 0xe400 1024]
}
debug set_bp 16737 {$::started} {set ::baseline_at [machine_info time]}
debug set_bp 0xd10b {$::started} {
 set baseline_cycles [expr {round(([machine_info time]-$::baseline_at)*3579545)}]
 if {$::candidate_count ne [debug read_block memory 0xc082 2] || $::candidate_list ne [debug read_block memory 0x0800 [string length $::candidate_list]]} {error "Sparse cache differs from full scan at $::index"}
 puts $::timing "$::hook_cycles $::candidate_cycles $baseline_cycles"
}
debug set_bp 0xd140 {$::started} {incr ::index;issue}
after time 300 {puts stderr "Smoke cache probe timeout";exit 2}
} problem]} {puts stderr $problem;exit 2}

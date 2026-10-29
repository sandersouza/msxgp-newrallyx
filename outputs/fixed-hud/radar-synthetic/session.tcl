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
cart "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/radar-synthetic/probe.rom" -romtype Normal
reset
set out "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/radar-synthetic"
set f [open [file join $out programs.bin] rb];set programs [read $f];close $f
set f [open [file join $out expected.bin] rb];set expected [read $f];close $f
set index 0;set started 0;set blank [binary format c* [lrepeat 1024 238]]
proc issue {} {
 if {$::index==65536} {puts "Generated Z80 radar names passed 65536 cases";exit 0;return}
 set mask [expr {$::index&1023}]
 if {$mask==0} {
  set at [expr {($::index>>10)*512}]
  debug write_block memory 0xa700 [string range $::programs $at [expr {$at+511}]]
  debug write_block memory 0xd400 $::blank
 }
 for {set i 0} {$i<10} {incr i} {debug write memory [expr {0xc501+$i}] [expr {($mask>>$i)&1}]}
 set p 0xd110;foreach v {205 0 167 195 64 209} {debug write memory $p $v;incr p}
 reg SP 0xf380;reg PC 0xd110
}
debug set_bp 0x4014 {!$::started} {set ::started 1;issue}
debug set_bp 0xd140 {$::started} {
 set at [expr {$::index*1024}]
 if {[debug read_block memory 0xd400 1024] ne [string range $::expected $at [expr {$at+1023}]]} {error "Generated radar mismatch $::index"}
 incr ::index;issue
}
after time 60 {puts stderr "Radar probe timeout";exit 2}
} problem]} {puts stderr $problem;exit 2}

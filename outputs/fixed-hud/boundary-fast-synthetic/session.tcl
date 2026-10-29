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
cart "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/boundary-fast-synthetic/probe.rom" -romtype ASCII16
reset
set out "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/outputs/fixed-hud/boundary-fast-synthetic"
set f [open [file join $out initial.bin] rb];set initial [read $f];close $f
set f [open [file join $out phase-banks.bin] rb];set phase_banks [read $f];close $f
set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w]
set index 0;set started 0;set fast 0
set VDP.too_fast_vram_access_callback {if {$::started} {incr ::fast}}
set cases {{0 24 0} {0 24 1} {9 32 0} {9 32 1} {18 40 0} {18 40 1} {27 48 0} {27 48 1} {36 56 0} {36 56 1} {45 0 0} {45 0 1} {54 8 0} {54 8 1} {63 16 0} {63 16 1} {8 25 0} {8 25 1} {17 33 0} {17 33 1} {26 41 0} {26 41 1} {35 49 0} {35 49 1} {44 57 0} {44 57 1} {53 1 0} {53 1 1} {62 9 0} {62 9 1} {7 17 0} {7 17 1} {16 26 0} {16 26 1} {25 34 0} {25 34 1} {34 42 0} {34 42 1} {43 50 0} {43 50 1} {52 58 0} {52 58 1} {61 2 0} {61 2 1} {6 10 0} {6 10 1} {15 18 0} {15 18 1} {24 27 0} {24 27 1} {33 35 0} {33 35 1} {42 43 0} {42 43 1} {51 51 0} {51 51 1} {60 59 0} {60 59 1} {5 3 0} {5 3 1} {14 11 0} {14 11 1} {23 19 0} {23 19 1} {32 28 0} {32 28 1} {41 36 0} {41 36 1} {50 44 0} {50 44 1} {59 52 0} {59 52 1} {4 60 0} {4 60 1} {13 4 0} {13 4 1} {22 12 0} {22 12 1} {31 20 0} {31 20 1} {40 29 0} {40 29 1} {49 37 0} {49 37 1} {58 45 0} {58 45 1} {3 53 0} {3 53 1} {12 61 0} {12 61 1} {21 5 0} {21 5 1} {30 13 0} {30 13 1} {39 21 0} {39 21 1} {48 30 0} {48 30 1} {57 38 0} {57 38 1} {2 46 0} {2 46 1} {11 54 0} {11 54 1} {20 62 0} {20 62 1} {29 6 0} {29 6 1} {38 14 0} {38 14 1} {47 22 0} {47 22 1} {56 31 0} {56 31 1} {1 39 0} {1 39 1} {10 47 0} {10 47 1} {19 55 0} {19 55 1} {28 63 0} {28 63 1} {37 7 0} {37 7 1} {46 15 0} {46 15 1} {55 23 0} {55 23 1} {0 255 0} {0 255 1} {9 255 0} {9 255 1} {18 255 0} {18 255 1} {27 255 0} {27 255 1} {36 255 0} {36 255 1} {45 255 0} {45 255 1} {54 255 0} {54 255 1} {63 255 0} {63 255 1}}
proc issue {} {
 if {$::index==144} {close $::result;close $::timing;set f [open [file join $::out strict.txt] w];puts $f $::fast;close $f;exit 0;return}
 lassign [lindex $::cases $::index] phase prior table
 set at [expr {$::index*131072}];debug write_block VRAM 0 [string range $::initial $at [expr {$at+131071}]]
 debug write memory 0xc01d $phase;debug write memory 0xc020 $prior;debug write memory 0xc006 $table
 set p 0xd180;foreach v [list 62 [expr {$phase+4}] 50 0 112 205 93 64 243 195 192 209] {debug write memory $p $v;incr p}
 reg SP 0xf380;reg PC 0xd180
}
debug set_bp 16474 {!$::started} {set ::started 1;issue}
debug set_bp 16477 {$::started} {set ::begin [machine_info time]}
debug set_bp 0xd188 {$::started} {set ::cycles [expr {round(([machine_info time]-$::begin)*3579545)}]}
debug set_bp 0xd1c0 {$::started} {
 lassign [lindex $::cases $::index] phase prior table
 set at [expr {$phase*16384}]
 if {[debug read_block memory 0x8000 16384] ne [string range $::phase_banks $at [expr {$at+16383}]]} {puts stderr "Phase mapper not restored case=$::index phase=$phase";exit 3}
 puts -nonewline $::result [debug read_block VRAM 0 131072];puts $::timing $::cycles
 incr ::index;issue
}
after time 60 {puts stderr "Boundary probe timeout";exit 2}
} problem]} {puts stderr $problem;exit 2}

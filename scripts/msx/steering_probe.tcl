# Real keyboard multi-key stress; complete HUD and native hardware clocks.
if {[catch {
set save_settings_on_exit false
set renderer none
set sound_driver null
filepool add -path @BIOS@ -types system_rom -position 1
source @MAPPER@
nrallyx_reference_machine "Panasonic_FS-A1WSX"
set firmwareswitch off
set throttle off
set z80_freq 3579545
set z80_freq_locked false
set cmdtiming real
set limitsprites true
activate_input_layer -blocking steering_regression
cart @ROM@ -romtype ASCII16
reset
set out @OUTPUT@
set smoke_stress @SMOKE_STRESS@
set smoke_log [open [file join $out smoke.tsv] w]
set f [open [file join $out board.bin] rb];set board [read $f];close $f
set headers [open [file join $out headers.tsv] w];set skip_headers 0
set log [open [file join $out movement.tsv] w];set n 0;set age 0;set phase boot;set mask 0;set seed 12345;set games 0;set checked 0;set keys_checked 0
proc menu {} {if {[catch {menu_step} p]} {puts stderr $p;exit 2};after time 0.02 menu}
proc menu_step {} {set s [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd];incr ::age;switch $::phase {
boot {if {$s && $ready} {keymatrixup 8 255;keymatrixdown 0 32;set ::phase coin;set ::age 0}}
coin {if {$::age==3} {keymatrixup 0 32;set ::phase release;set ::age 0}}
release {if {$::age==3} {keymatrixdown 0 2;set ::phase start;set ::age 0}}
start {if {$s==0} {keymatrixup 0 2;set ::phase game;set ::age 0;incr ::games}}
game {if {$s && $ready} {set ::phase boot;set ::age 0}}
}}
proc movement {} {incr ::checked;set q [expr {(~[debug read memory 0xe3f0])&60}];if {$q&($q-1)} {error "Diagonal reached native game input"};if {$::n>=1 && $::n<=32} {if {$q!=$::expected_direction} {error "Newest keyboard direction lost priority"};incr ::keys_checked};set lo [debug read memory 0xc486];set hi [debug read memory 0xc487];set a [expr {$lo+256*$hi-0x9800}];set cell -1;if {$a>=0 && $a<1792} {binary scan [string index $::board $a] cu cell};
puts $::log "$::n $::mask $a $cell [debug read memory 0xe070] [debug read memory 0xe072] [debug read memory 0xe06d] [debug read memory 0xe06f] [debug read memory 0xe28f] [debug read memory 0xc50b]";
if {$cell>=0 && ($cell&248)} {set f [open [file join $::out stuck.state] wb];puts -nonewline $f [debug read_block memory 0xc000 12288];close $f;puts stderr "Wall entry at refresh$::n cell$a input$::mask";close $::log;set f [open [file join $::out post.bin] wb];puts -nonewline $f [debug read_block memory 0xe000 4096];close $f;store_machine [machine] [file join $::out stuck.oms];exit 2}}
proc frame {} {if {$::phase ne "game"} {return};incr ::n;if {$::skip_headers} {incr ::skip_headers -1};keymatrixup 8 255;if {$::n<=32} {set k [expr {($::n-1)/4}];set ::mask [lindex {128 160 128 0 16 80 64 0} $k];set ::expected_direction [lindex {8 32 8 0 4 16 16 0} $k]} elseif {$::n%16==1} {set ::seed [expr {(1103515245*$::seed+12345)&2147483647}];set ::mask [lindex {0 16 32 64 128 48 96 192 144 80 160 112 176 208 224 240} [expr {($::seed>>16)&15}]]};if {$::mask} {keymatrixdown 8 $::mask};if {$::smoke_stress && $::n>32 && $::n%40<16} {keymatrixdown 8 1};puts $::smoke_log "$::n [expr {[debug read memory 0xc711]+256*[debug read memory 0xc712]}] [debug read memory 0xc70e]";if {$::n>=16000} {set f [open [file join $::out summary.tsv] w];puts $f "$::n $::checked $::games [expr {[debug read memory 0xc7e6]+256*[debug read memory 0xc7e7]}] $::keys_checked";close $f;set ::done 1;close $::headers;close $::log;close $::smoke_log;exit 0}}
debug set_watchpoint write_mem 0xc000 {$wp_last_value==2} {if {[catch {frame} p]} {puts stderr $p;exit 2}}
debug set_bp @AFTER_ROCK@ {$::phase eq "game"} {if {[catch {movement} p]} {puts stderr $p;exit 2}}
debug set_watchpoint write_mem 0xc03c {![info exists ::done] && $::phase eq "game" && !$::skip_headers && $wp_last_value in {2 4}} {puts $::headers "$wp_last_value $::n stress [machine_info time] 0 0"}
debug set_bp @SHOW_SCENE@ {$::phase eq "game"} {puts $::headers "0 $::n reload [machine_info time] 1 0";set ::skip_headers 4}
after time 600 {puts stderr "Wall stress timeout";exit 2}
after time 0.02 menu
} p]} {puts stderr $p;exit 2}

# Exercise the real keyboard matrix through the assembled VBlank adapter.
# This is peripheral-adapter evidence, independent of logical replay inputs.
catch {unplug joyporta}
set nr_input_cases {{0 0 255} {0 32 127} {0 2 191} {8 32 223} {8 64 239} {8 16 251} {8 128 247} {8 1 253} {8 177 209}}
set nr_input_prior {0 1 2 3 16 64 128 255}
set nr_input_case 0
set nr_input_pending 0
set nr_input_log [open [file join $nr_out physical-inputs.tsv] w]
puts $nr_input_log "case\trow\tmask\tprior\texpected\tactual\tppi_before\tppi_after\tpsg_after\tp2\tdip"
debug set_bp [dict get $nr_symbols Native_ReadInputs] {$::nr_started && $::nr_input_case < 72} {
    set ::nr_input_pending 1
    keymatrixup 0 255
    keymatrixup 8 255
    lassign [lindex $::nr_input_cases [expr {$::nr_input_case/8}]] row mask expected
    if {$mask} {keymatrixdown $row $mask}
    set prior [lindex $::nr_input_prior [expr {$::nr_input_case%8}]]
    debug write "PSG regs" 15 $prior
    set ::nr_input_ppi [debug read ioports 170]
    set ::nr_input_ram [nr_game_bytes]
}
debug set_bp [dict get $nr_symbols Native_InputReturn] {$::nr_started && $::nr_input_pending} {
    if {$::nr_input_ram ne [nr_game_bytes]} {puts stderr "Keyboard adapter changed original RAM"; exit 2}
    lassign [lindex $::nr_input_cases [expr {$::nr_input_case/8}]] row mask expected
    set prior [lindex $::nr_input_prior [expr {$::nr_input_case%8}]]
    set base [dict get $::nr_symbols Native_InputCache]
    set values [list $::nr_input_case $row $mask $prior $expected [debug read memory $base] $::nr_input_ppi [debug read ioports 170] [debug read "PSG regs" 15] [debug read memory [expr {$base+1}]] [debug read memory [expr {$base+2}]]]
    puts $::nr_input_log [join $values "\t"]
    flush $::nr_input_log
    keymatrixup 0 255
    keymatrixup 8 255
    set ::nr_input_pending 0
    incr ::nr_input_case
}

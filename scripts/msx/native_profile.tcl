# Optional read-only instruction timing over a bounded logical-tick window.
# No trace bytes or register contents are exported. Account each elapsed CPU
# clock to the PC before the instruction; fixed-frequency acquisition owns time.
# Interrupt-acceptance clocks share that interval; these are elapsed PC costs,
# not an isolated opcode timing table.
set nr_profile_active 0
set nr_profile_totals [dict create]
proc nr_profile_sample {} {
    set now [expr {round([machine_info time]*3579545)}]
    if {[info exists ::nr_profile_previous]} {
        set delta [expr {$now-$::nr_profile_time}]
        dict incr ::nr_profile_totals $::nr_profile_previous $delta
    }
    set ::nr_profile_time $now
    set ::nr_profile_previous [reg PC]
}
proc nr_profile_boundary {tick} {
    if {$tick == [lindex $::nr_profile_range 0]} {
        set ::nr_profile_active 1
        set ::nr_profile_begin [expr {round([machine_info time]*3579545)}]
        nr_profile_sample
        set ::nr_profile_condition [debug set_condition 1 nr_profile_sample]
    }
    if {$::nr_profile_active && $tick == [lindex $::nr_profile_range 1]} {
        nr_profile_sample
        debug remove_condition $::nr_profile_condition
        set ::nr_profile_active 0
        set file [open [file join $::nr_out profile.tsv] w]
        puts $file "pc\tcycles"
        dict for {pc cycles} $::nr_profile_totals {puts $file "$pc\t$cycles"}
        close $file
        set file [open [file join $::nr_out profile-window.tsv] w]
        puts $file "start\tend\tcycles"
        puts $file "[lindex $::nr_profile_range 0]\t$tick\t[expr {$::nr_profile_time-$::nr_profile_begin}]"
        close $file
    }
}

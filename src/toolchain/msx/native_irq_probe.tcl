# Exercise the real host dispatcher against an authored page-0 foreground.
proc nr_u32 {name} {
    set address [dict get $::nr_symbols $name]
    set value 0
    for {set n 3} {$n >= 0} {incr n -1} {
        set value [expr {$value*256+[debug read memory [expr {$address+$n}]]}]
    }
    return $value
}
proc nr_schedule_reset {} {
    set ::nr_case 0
    set ::nr_remainder 0
    set ::nr_pending 0
    set ::nr_ticks 0
    set file [open [file join $::out schedule.tsv] w]
    puts $file "case\tgate\tpending\tticks\tremainder"
    close $file
    set file [open [file join $::out drain.tsv] w]
    puts $file "case\tevent\tpending\tticks\tremainder"
    close $file
    set ::nr_drain_case 0
    set ::nr_in_flight 0
    set ::nr_wait_case 0
    set ::nr_wait_frames 0
    set file [open [file join $::out waits.tsv] w]
    puts $file "case\tticks\tframes\tpending"
    close $file
}
proc nr_due_cache {} {
    if {[debug read memory [dict get $::nr_symbols Native_Due]] != ([nr_u32 Native_Pending] != 0)} {
        puts stderr "Pending nonempty cache disagrees with full queue"; exit 2
    }
}
proc nr_drain_event {event} {
    nr_due_cache
    if {$event eq "frame"} {
        set total [expr {$::nr_remainder+$::nr_frame_cycles*2000}]
        incr ::nr_pending [expr {$total/118124985}]
        set ::nr_remainder [expr {$total%118124985}]
    } elseif {$event eq "claim"} {
        if {$::nr_pending <= 0} {puts stderr "Game IRQ invented a logical tick"; exit 2}
        incr ::nr_pending -1
        set ::nr_in_flight 1
    } elseif {$event eq "publish"} {
        incr ::nr_ticks
        set ::nr_in_flight 0
    }
    # Host IRQs may interrupt the game's four-byte counter update before the
    # publication event. Only that publication commits the logical tick.
    set check_ticks [expr {$event ne "frame" || !$::nr_in_flight}]
    if {[nr_u32 Native_Clock] != $::nr_remainder || [nr_u32 Native_Pending] != $::nr_pending || ($check_ticks && [nr_u32 Native_GameTicks] != $::nr_ticks)} {
        puts stderr "Foreground checkpoint lost ticks: event=$event clock=[nr_u32 Native_Clock]/$::nr_remainder pending=[nr_u32 Native_Pending]/$::nr_pending ticks=[nr_u32 Native_GameTicks]/$::nr_ticks"; exit 2
    }
    set file [open [file join $::out drain.tsv] a]
    puts $file "$::nr_drain_case\t$event\t$::nr_pending\t$::nr_ticks\t$::nr_remainder"
    close $file
    incr ::nr_drain_case
}
proc nr_irq_before {} {
    set ::nr_game_regs [regs]
    set phase [debug read memory [dict get $::nr_symbols Native_ProbePhase]]
    if {$phase != 1} {return}
    if {$::nr_case >= 64} {error "Extra synthetic IRQ iteration"}
    set gate [expr {$::nr_case%6}]
    foreach {symbol blocked} {Native_VirtualIFF 1 Native_GameBusy 2 Native_Suspended 3 Native_AssetMapped 4} {
        set value [expr {$symbol eq "Native_VirtualIFF" ? $gate != $blocked : $gate == $blocked}]
        debug write memory [dict get $::nr_symbols $symbol] $value
    }
    debug write memory 41345 [expr {$gate != 5}]
}
proc nr_irq_after {} {
    nr_due_cache
    if {[regs] ne $::nr_game_regs || [reg SP] != 33792} {
        puts stderr "Game IRQ changed foreground registers/flags/SP"; exit 2
    }
    set phase [debug read memory [dict get $::nr_symbols Native_ProbePhase]]
    if {!$phase} {
        incr ::nr_game_stack_irqs
        return
    }
    if {$phase == 2} {
        nr_drain_event checkpoint
        return
    }
    if {$phase == 3} {
        set expected [lindex {1 4 4} $::nr_wait_case]
        set pending [lindex {1 255 0} $::nr_wait_case]
        if {$::nr_wait_case >= 3 || [nr_u32 Native_GameTicks] != $expected || $::nr_wait_frames != 2 || [nr_u32 Native_Pending] != $pending} {
            puts stderr "Logical wait/poll released incorrectly: case=$::nr_wait_case ticks=[nr_u32 Native_GameTicks] frames=$::nr_wait_frames"; exit 2
        }
        set file [open [file join $::out waits.tsv] a]
        puts $file "$::nr_wait_case\t[nr_u32 Native_GameTicks]\t$::nr_wait_frames\t[nr_u32 Native_Pending]"
        close $file
        incr ::nr_wait_case
        return
    }
    set total [expr {$::nr_remainder+$::nr_frame_cycles*2000}]
    incr ::nr_pending [expr {$total/118124985}]
    set ::nr_remainder [expr {$total%118124985}]
    set gate [expr {$::nr_case%6}]
    if {$gate == 0 && $::nr_pending > 0} {incr ::nr_pending -1; incr ::nr_ticks}
    if {[nr_u32 Native_Clock] != $::nr_remainder || [nr_u32 Native_Pending] != $::nr_pending || [nr_u32 Native_GameTicks] != $::nr_ticks} {
        puts stderr "IRQ schedule mismatch case=$::nr_case: clock=[nr_u32 Native_Clock]/$::nr_remainder pending=[nr_u32 Native_Pending]/$::nr_pending ticks=[nr_u32 Native_GameTicks]/$::nr_ticks"
        exit 2
    }
    set file [open [file join $::out schedule.tsv] a]
    puts $file "$::nr_case\t$gate\t$::nr_pending\t$::nr_ticks\t$::nr_remainder"
    close $file
    incr ::nr_case
}
debug set_bp [dict get $nr_symbols Native_TestScheduler] {$::nr_started && $::nr_booted} nr_schedule_reset
debug set_watchpoint write_mem [dict get $nr_symbols Native_ProbeBefore] {$::nr_started && $::nr_booted} nr_irq_before
debug set_watchpoint write_mem [dict get $nr_symbols Native_ProbeAfter] {$::nr_started && $::nr_booted} nr_irq_after
debug set_bp [dict get $nr_symbols Native_ClockDone] {$::nr_started && $::nr_booted && [debug read memory [dict get $::nr_symbols Native_ProbePhase]] == 2} {nr_drain_event frame}
set claim_name Native_EnterGameIRQ
if {[dict exists $nr_symbols Native_ClaimGameIRQ]} {set claim_name Native_ClaimGameIRQ}
debug set_bp [dict get $nr_symbols $claim_name] {$::nr_started && $::nr_booted && [debug read memory [dict get $::nr_symbols Native_ProbePhase]] == 2} {nr_drain_event claim}
debug set_watchpoint write_mem [dict get $nr_symbols Native_Published] {$::nr_started && $::nr_booted && [debug read memory [dict get $::nr_symbols Native_ProbePhase]] == 2} {nr_drain_event publish}
debug set_bp [dict get $nr_symbols Native_ClockDone] {$::nr_started && $::nr_booted && [debug read memory [dict get $::nr_symbols Native_ProbePhase]] == 3} {
    incr ::nr_wait_frames
    if {$::nr_wait_frames == 2} {debug write memory [dict get $::nr_symbols Native_GameBusy] 0}
}

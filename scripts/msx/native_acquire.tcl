set nr_started 0
debug set_watchpoint write_mem {0 32767} {$::nr_started} {
    if {[dict exists $::nr_symbols Native_FrameMapped] &&
        [debug read memory [dict get $::nr_symbols Native_FrameMapped]] == 1 &&
        [debug read memory [dict get $::nr_symbols Native_Suspended]] == 1 &&
        $::wp_last_address >= 8192 && $::wp_last_address < 10240 &&
        ([reg PC] == [dict get $::nr_symbols Native_FrameCopyCodes]+1 ||
         [reg PC] == [dict get $::nr_symbols Native_FrameCopyAttrs]+1 ||
         [reg PC] == [dict get $::nr_symbols Native_FrameCopyCodeCell]+1 ||
         [reg PC] == [dict get $::nr_symbols Native_FrameCopyAttrCell]+1)} {
        # Explicit host snapshot in asset-bank-3 padding, not the program bank.
    } else {
    puts stderr "Unexpected native code write: PC=[reg PC] SP=[reg SP] HL=[reg HL] DE=[reg DE]"
    exit 2
    }
}
if {[info exists nr_entry_spans]} {
    foreach span $nr_entry_spans {
        lassign $span first length
        for {set pc [expr {$first+1}]} {$pc < $first+$length} {incr pc} {
            debug set_bp $pc {$::nr_started} {
                puts stderr "Guest entered a guarded patch interior: PC=[reg PC] SP=[reg SP]"
                exit 2
            }
        }
    }
}
if {[dict exists $nr_symbols NATIVE_VIDEO] && [dict get $nr_symbols NATIVE_VIDEO]} {
    set nr_unmarked [open [file join $nr_out unmarked-writes.tsv] w]
    puts $nr_unmarked "tick\tpc\taddress\tcached\tvalue\tstage"
    set nr_unmarked_count 0
    foreach span {{33792 34815} {35840 36863}} {
        debug set_watchpoint write_mem $span {$::nr_started} nr_tile_write
    }
    set nr_context_calls 0
    set nr_context_steps 0
    debug set_bp [dict get $nr_symbols Native_PrepareFrame] {$::nr_started} nr_present_enter
    foreach name {Native_FrameReturn Native_SkipReturn} {
        debug set_bp [dict get $nr_symbols $name] {$::nr_started} nr_present_leave
    }
    set nr_dirty_trace [open [file join $nr_out dirty-requests.tsv] w]
    puts $nr_dirty_trace "tick\tde\tbc\thl\tcaller"
    debug set_bp [dict get $nr_symbols Native_RequestAllTiles] {$::nr_started} {
        set s [reg SP]
        set caller [expr {[debug read memory $s]+256*[debug read memory [expr {$s+1}]]}]
        puts $::nr_dirty_trace "[nr_u32 Native_GameTicks]\t[reg DE]\t[reg BC]\t[reg HL]\t$caller"
        flush $::nr_dirty_trace
    }
    set nr_video [open [file join $nr_out video.tsv] w]
    set nr_video_steps [open [file join $nr_out video-steps.tsv] w]
    puts $nr_video_steps "input_tick\ttick\tstage\tcycles\ttime"
    puts $nr_video "frame\ttick\tcycles\tphase\ttime\thud_cycles\ttile_cycles\trestore_cycles\tactor_cycles\tinput_tick\tlatency_cycles"
    set nr_video_frame 0
    set nr_uploads [open [file join $nr_out uploads.tsv] w]
    puts $nr_uploads "kind\ttick\tcode\tattr\tslot"
    foreach kind {Tile Actor} {
        debug set_bp [dict get $nr_symbols Native_Upload$kind] {$::nr_started} [list nr_upload_event $kind]
    }
    set nr_radar_enabled [dict exists $nr_symbols Native_RadarEnemies]
    set nr_raster [open [file join $nr_out raster.tsv] w]
    puts $nr_raster "event\tlevel\tframe\ty\tx\ttime\tr2\tr19\tr23\tr25\tpc\tsp\tiff\tsuspended"
    foreach kind {horizontal vertical} {
        debug probe set_bp VDP.IRQ$kind {$::nr_started} [list nr_raster_edge $kind]
    }
    debug set_watchpoint write_mem [dict get $nr_symbols Native_RasterPhase] {$::nr_started} {
        nr_raster_record phase $::wp_last_value
    }
    set nr_gpu [open [file join $nr_out gpu.tsv] w]
    puts $nr_gpu "executing\ttime\tcommand\tdx\tdy\tnx\tny"
    debug probe set_bp VDP.commandExecuting {$::nr_started} nr_gpu_event
    set VDP.too_fast_vram_access_callback {
        if {$::nr_started} {puts stderr "Native VRAM access timing violation"; exit 2}
    }
    if {$nr_radar_enabled} {
        # The phase ledger distinguishes the new bitmap radar from game actors.
        close $nr_video
        set nr_video [open [file join $nr_out video.tsv] w]
        puts $nr_video "frame\ttick\tcycles\tphase\ttime\thud_cycles\ttile_cycles\trestore_cycles\tactor_cycles\tinput_tick\tlatency_cycles\tradar_cycles"
    }
    debug set_bp [dict get $nr_symbols Native_DrawFrame] {$::nr_started} {
        set ::nr_video_start [machine_info time]
        set ::nr_video_input_tick [nr_u32 Native_GameTicks]
        set ::nr_video_input "[debug read_block memory 32768 4096][debug read_block memory 38912 2048][debug read_block memory 40960 392]"
        set ::nr_stage_cycles [dict create 0 0 1 0 2 0 3 0 4 0]
        if {$::nr_radar_enabled} {dict set ::nr_stage_cycles 5 0}
    }
    debug set_bp [dict get $nr_symbols Native_FrameDone] {$::nr_started} nr_video_frame
    debug set_bp [dict get $nr_symbols Native_FrameAfterHUD] {$::nr_started} {
        set ::nr_hud_cycles [expr {round(([machine_info time]-$::nr_video_start)*3579545)}]
    }
    debug set_bp [dict get $nr_symbols Native_RenderJob] {$::nr_started} {
        set ::nr_step_start [machine_info time]
        set ::nr_step_stage [debug read memory [dict get $::nr_symbols Native_RenderStage]]
    }
    debug set_bp [dict get $nr_symbols Native_StepDone] {$::nr_started} nr_end_step
    if {$nr_scanout_enabled} {
      debug set_watchpoint write_mem [dict get $nr_symbols Native_ActiveR2] {$::nr_started} {
        set tick [nr_u32 Native_GameTicks]
        foreach boundary {200 1100 1800 2400} {
            if {$tick >= $boundary && ![info exists ::nr_scanout($boundary)]} {
                set ::nr_scanout($boundary) 1
                after time 0.025 [list nr_scanout_capture $boundary]
            }
        }
      }
    }
}
proc nr_raster_edge {kind} {
    nr_raster_record $kind [debug probe read VDP.IRQ$kind]
}
proc nr_raster_record {event level} {
    puts $::nr_raster "$event\t$level\t[machine_info VDP_frame_count]\t[machine_info VDP_msx_y_pos]\t[machine_info VDP_msx_x256_pos]\t[machine_info time]\t[debug read {VDP regs} 2]\t[debug read {VDP regs} 19]\t[debug read {VDP regs} 23]\t[debug read {VDP regs} 25]\t[reg PC]\t[reg SP]\t[reg IFF]\t[debug read memory [dict get $::nr_symbols Native_Suspended]]"
}
proc nr_upload_event {kind} {
    if {$kind eq "Tile"} {
        set fields {Native_TileCode Native_TileAttr Native_TileSlot}
    } else {
        set fields {Native_ActorFlags Native_ActorPalette Native_ActorSlot}
    }
    set values {}
    foreach field $fields {lappend values [debug read memory [dict get $::nr_symbols $field]]}
    puts $::nr_uploads "$kind\t[nr_u32 Native_GameTicks]\t[join $values \t]"
}

proc nr_gpu_event {} {
    # Command-register debug reads synchronize the engine. Inside its transition
    # callback that can recurse into command execution; inspect our RAM packet.
    set base [dict get $::nr_symbols Native_Command]
    set values [list [debug probe read VDP.commandExecuting] [machine_info time] [debug read memory [expr {$base+14}]]]
    foreach offset {4 6 8 10} {
        lappend values [expr {[debug read memory [expr {$base+$offset}]]+256*[debug read memory [expr {$base+$offset+1}]]}]
    }
    puts $::nr_gpu [join $values "\t"]
}
proc nr_scanout_capture {boundary} {
    screenshot -raw -size auto [file join $::nr_out scanout-$boundary.png]
}
proc nr_tile_write {} {
    set address $::wp_last_address
    set index [expr {($address-33792)&1023}]
    set dirty [debug read memory [expr {51200+$index/8}]]
    set cached [debug read memory [expr {($address >= 35840 ? 59392 : 51456)+$index}]]
    if {!($dirty & (1<<($index%8))) &&
        ![debug read memory [dict get $::nr_symbols Native_DirtyAllPending]] &&
        $cached != $::wp_last_value && $::nr_unmarked_count < 4096} {
        incr ::nr_unmarked_count
        puts $::nr_unmarked "[nr_u32 Native_GameTicks]\t[reg PC]\t$address\t$cached\t$::wp_last_value\t[debug read memory [dict get $::nr_symbols Native_RenderStage]]"
        flush $::nr_unmarked
    }
}
proc nr_game_bytes {} {
    return "[debug read_block memory 32768 4096][debug read_block memory 38912 2048][debug read_block memory 40960 392]"
}
proc nr_present_enter {} {
    if {[info exists ::nr_present_regs]} {puts stderr "Nested presentation entry"; exit 2}
    set ::nr_present_regs [dict create]
    foreach name {AF BC DE HL IX IY AF2 BC2 DE2 HL2 SP} {
        dict set ::nr_present_regs $name [reg $name]
    }
    set ::nr_present_bytes [nr_game_bytes]
}
proc nr_present_leave {} {
    if {![info exists ::nr_present_regs]} {puts stderr "Missing presentation entry"; exit 2}
    dict for {name value} $::nr_present_regs {
        if {[reg $name] != $value} {
            puts stderr "Presentation changed $name: [reg $name]/$value"; exit 2
        }
    }
    if {[nr_game_bytes] ne $::nr_present_bytes} {puts stderr "Presentation changed original RAM"; exit 2}
    if {[debug read memory [dict get $::nr_symbols Native_FrameMapped]]} {
        puts stderr "Presentation left page 0 mapped to snapshot data"; exit 2
    }
    incr ::nr_context_calls
    if {[reg PC] == [dict get $::nr_symbols Native_FrameReturn]} {incr ::nr_context_steps}
    unset ::nr_present_regs
    unset ::nr_present_bytes
}
proc nr_video_frame {} {
    nr_end_step
    if {[debug read memory [dict get $::nr_symbols Native_Error]]} {
        puts stderr "Native renderer mapping error"; exit 2
    }
    incr ::nr_video_frame
    set latency [expr {round(([machine_info time]-$::nr_video_start)*3579545)}]
    set cycles 0
    dict for {stage value} $::nr_stage_cycles {incr cycles $value}
    set tick [nr_u32 Native_GameTicks]
    set row "$::nr_video_frame\t$tick\t$cycles\t[debug read memory [dict get $::nr_symbols Native_RasterPhase]]\t[machine_info time]\t[expr {[dict get $::nr_stage_cycles 0]+[dict get $::nr_stage_cycles 4]}]\t[dict get $::nr_stage_cycles 1]\t[dict get $::nr_stage_cycles 2]\t[dict get $::nr_stage_cycles 3]\t$::nr_video_input_tick\t$latency"
    if {$::nr_radar_enabled} {append row "\t[dict get $::nr_stage_cycles 5]"}
    puts $::nr_video $row
    nr_capture_video [format video-frame-%05d $::nr_video_frame]
    foreach boundary {1100 1800 2400} {
      if {$tick >= $boundary && ![info exists ::nr_video_captured($boundary)]} {
        set ::nr_video_captured($boundary) 1
        nr_capture_video video-$boundary
      }
    }
}
proc nr_end_step {} {
    if {![info exists ::nr_step_start]} {return}
    set cycles [expr {round(([machine_info time]-$::nr_step_start)*3579545)}]
    puts $::nr_video_steps "$::nr_video_input_tick\t[nr_u32 Native_GameTicks]\t$::nr_step_stage\t$cycles\t[machine_info time]"
    dict incr ::nr_stage_cycles $::nr_step_stage $cycles
    unset ::nr_step_start
}
proc nr_capture_video {prefix} {
        set file [open [file join $::nr_out $prefix-state.bin] wb]
        puts -nonewline $file $::nr_video_input
        close $file
        if {$::nr_radar_enabled} {
            set file [open [file join $::nr_out $prefix-hud.bin] wb]
            puts -nonewline $file [debug read_block memory 49152 1140]
            close $file
        }
        foreach {name data} [list $prefix-vram.bin [debug read_block VRAM 0 131072] $prefix-dirty.bin [debug read_block memory [dict get $::nr_symbols Native_DirtyTiles] 128] $prefix-host.bin [debug read_block memory 51072 2176] $prefix-cache.bin [debug read_block memory 57344 4096]] {
            set file [open [file join $::nr_out $name] wb]
            puts -nonewline $file $data
            close $file
        }
}
if {![dict exists $nr_symbols NATIVE_FINE_IRQ]} {dict set nr_symbols NATIVE_FINE_IRQ 0}
if {![dict exists $nr_symbols NATIVE_FINE_DEADLINE]} {dict set nr_symbols NATIVE_FINE_DEADLINE 0}
set nr_claimed 0
set nr_boot_seen 0
set nr_pre -1
set nr_post 0
set nr_stack_min 33792
set nr_foreground_counts [dict create 3116 0 4178 0 4318 0 5573 0]
set nr_events [open [file join $nr_out events.tsv] w]
set nr_masks [open [file join $nr_out masks.tsv] w]
set nr_registers [open [file join $nr_out registers.tsv] w]
set nr_startup [open [file join $nr_out startup.tsv] w]
puts $nr_startup "phase\ttime\tresume\tsp"
set nr_work [open [file join $nr_out work.tsv] w]
puts $nr_work "tick\tcheckpoint\tplayer\tplayer_ei\tactors\tstage\ttimer"
puts $nr_registers "tick\tphase\tAF\tBC\tDE\tHL\tIX\tIY\tAF2\tBC2\tDE2\tHL2"
proc nr_registers {tick phase} {
    set row [list $tick $phase]
    foreach name {AF BC DE HL IX IY AF2 BC2 DE2 HL2} {lappend row [format %04x [reg $name]]}
    puts $::nr_registers [join $row "\t"]
}
puts $nr_masks "tick\tpc\tvalue\tbusy\tpending\ttime"
puts $nr_events "tick\tphase\tpc\tsp\tpending\tcycles\ttime"
proc nr_u32 {name} {
    set address [dict get $::nr_symbols $name]
    set value 0
    for {set n 3} {$n >= 0} {incr n -1} {
        set value [expr {$value*256+[debug read memory [expr {$address+$n}]]}]
    }
    return $value
}
proc nr_snapshot {name} {
    set file [open [file join $::nr_out $name] wb]
    puts -nonewline $file "[debug read_block memory 32768 4096][debug read_block memory 38912 2048][debug read_block memory 40960 392]"
    close $file
}
proc nr_ready {} {
    if {!$::nr_boot_seen} {puts stderr "Missing original CPU boot context"; exit 2}
    if {[reg SP] != 33792 || [reg IFF] != 0} {puts stderr "Unsafe original initialization boundary"; exit 2}
    set ::nr_started 1
    puts $::nr_startup "initialization-entry\t[machine_info time]\t0\t[reg SP]"
    nr_registers 0 initialization-entry
    nr_snapshot initialization.bin
    nr_code initial
    nr_clock
    if {[dict exists $::nr_symbols NATIVE_FUNCTION_PROBE] && [dict get $::nr_symbols NATIVE_FUNCTION_PROBE]} {
        set cases [nr_u32 Native_FunctionCases]
        if {$cases != 131072 || [debug read memory [dict get $::nr_symbols Native_FunctionDone]] != 1} {
            puts stderr "Incomplete coordinate differential proof"; exit 2
        }
        set file [open [file join $::nr_out function.json] w]
        if {$::nr_function_reference_count != $cases || $::nr_function_optimized_count != $cases} {
            puts stderr "Incomplete function timing evidence"; exit 2
        }
        puts $file [format {{"cases":%d,"complete":true,"compared":["AF","HL","BC","DE"],"reference_cycles":%d,"optimized_cycles":%d}} $cases $::nr_function_reference_cycles $::nr_function_optimized_cycles]
        close $file
        if {[dict get $::nr_symbols NATIVE_FINE_IRQ]} {
            if {[debug read memory [dict get $::nr_symbols Native_FineProofDone]] != 1} {
                puts stderr "Incomplete fine-clock arithmetic proof"; exit 2
            }
            set file [open [file join $::nr_out fine-math.json] w]
            if {[dict get $::nr_symbols NATIVE_FINE_DEADLINE]} {
                if {$::nr_fine_math_cases != 100000} {puts stderr "Missing deadline arithmetic cases"; exit 2}
                puts $file [format {{"cases":%d,"frame_lines":%d,"deadline":%d,"error":%d}} $::nr_fine_math_cases [dict get $::nr_symbols NATIVE_FRAME_LINES] $::nr_fine_math_deadline $::nr_fine_math_error]
            } else {
            puts $file [format {{"frames":100000,"complete":true,"frame_cycles":%d,"ticks":%d,"remainder":%d}} [expr {228*[dict get $::nr_symbols NATIVE_FRAME_LINES]}] [nr_u32 Native_FineProofTicks] [nr_u32 Native_FineProofRemainder]]
            }
            close $file
        }
    }
}
proc nr_boot {} {
    puts $::nr_startup "reset-entry\t[machine_info time]\t0\t[reg SP]"
    set expected {AF 64 BC 0 DE 0 HL 0 IX 65535 IY 65535 AF2 0 BC2 0 DE2 0 HL2 0}
    set row {}
    foreach {name value} $expected {
        if {[reg $name] != $value} {puts stderr "Invalid original CPU boot register $name"; exit 2}
        lappend row [format {"%s":%d} $name [reg $name]]
    }
    set file [open [file join $::nr_out boot-registers.json] w]
    puts $file "\{[join $row ,]\}"
    close $file
    set ::nr_boot_seen 1
}
proc nr_clock {} {
    if {$::z80_freq_locked || $::z80_freq != 3579545} {puts stderr "Native CPU clock is not fixed at standard speed"; exit 2}
    set file [open [file join $::nr_out clock.json] w]
    puts $file [format {{"z80_freq":%d,"z80_freq_locked":false}} $::z80_freq]
    close $file
}
proc nr_code {phase} {
    foreach {name base} {program 0 resident 16384} {
        set file [open [file join $::nr_out $phase-$name.bin] wb]
        puts -nonewline $file [debug read_block memory $base 16384]
        close $file
    }
}
proc nr_pre {} {
    set tick [nr_u32 Native_GameTicks]
    if {$tick != $::nr_post || $tick >= $::nr_target} {puts stderr "Nested or unexpected game IRQ"; exit 2}
    set ::nr_pre $tick
    set row [list $tick]
    foreach pc {3116 4178 4318 5573} {lappend row [dict get $::nr_foreground_counts $pc]}
    lappend row [debug read memory 32802] [debug read memory 33355]
    puts $::nr_work [join $row "\t"]
    if {$tick < 2} {
        set sp [reg SP]
        set resume [expr {[debug read memory $sp]+256*[debug read memory [expr {$sp+1}]]}]
        puts $::nr_startup "irq-$tick\t[machine_info time]\t$resume\t$sp"
    }
    if {$tick <= 1} {nr_registers $tick pre-game-irq}
    set ::nr_begin [machine_info time]
    debug write_block memory 41472 [binary format cu* [lindex $::nr_inputs $tick]]
    puts $::nr_events "$tick\tpre-game-irq\t[reg PC]\t[reg SP]\t[nr_u32 Native_Pending]\t0\t[machine_info time]"
}
proc nr_post {} {
    set tick [nr_u32 Native_GameTicks]
    if {$::nr_pre != $tick-1 || $tick != $::nr_post+1} {puts stderr "Nonmonotonic game publication"; exit 2}
    set ::nr_post $tick
    set kind [debug read memory [dict get $::nr_symbols Native_PublishKind]]
    if {$kind ni {0 1 2}} {puts stderr "Invalid game publication kind"; exit 2}
    set phase [lindex {post-game-irq post-game-irq-transfer post-game-irq-collision} $kind]
    if {$tick <= 1} {nr_registers $tick $phase}
    set cycles [expr {round(([machine_info time]-$::nr_begin)*3579545)}]
    puts $::nr_events "$tick\t$phase\t[reg PC]\t[reg SP]\t[nr_u32 Native_Pending]\t$cycles\t[machine_info time]"
    nr_snapshot [format state-%05d.bin $tick]
    if {[info exists ::nr_profile_range]} {nr_profile_boundary $tick}
    if {$tick == $::nr_target} {
        if {[info exists ::nr_context_calls]} {
            if {[info exists ::nr_present_regs] || !$::nr_context_steps} {puts stderr "Incomplete presentation context proof"; exit 2}
            set file [open [file join $::nr_out presentation-context.json] w]
            puts $file [format {{"complete":true,"calls":%d,"steps":%d,"game_ram_bytes":6536,"registers":["AF","BC","DE","HL","IX","IY","AF2","BC2","DE2","HL2","SP"]}} $::nr_context_calls $::nr_context_steps]
            close $file
        }
        nr_code final
        nr_clock
        set counts [open [file join $::nr_out foreground.tsv] w]
        puts $counts "pc\tcount"
        dict for {pc count} $::nr_foreground_counts {puts $counts "$pc\t$count"}
        close $counts
        close $::nr_events
        close $::nr_masks
        close $::nr_registers
        close $::nr_startup
        close $::nr_work
        if {[info exists ::nr_fine]} {
            close $::nr_fine
            set file [open [file join $::nr_out fine-final.json] w]
            if {[dict get $::nr_symbols NATIVE_FINE_DEADLINE]} {
                puts $file [format {{"claimed":%d,"pending":%d,"accepted":%d,"deadlines":%d}} $::nr_claimed [nr_u32 Native_Pending] $::nr_deadline_accepted $::nr_deadline_sequence]
            } else {
            puts $file [format {{"claimed":%d,"pending":%d,"remainder":%d}} $::nr_claimed [nr_u32 Native_Pending] [nr_u32 Native_Clock]]
            }
            close $file
        }
        set file [open [file join $::nr_out execution.json] w]
        puts $file [format {{"schema_version":1,"complete":true,"ticks":%d,"stack_min":%d}} $tick $::nr_stack_min]
        close $file
        exit 0
    }
}
debug set_bp 0 {!$::nr_started && [reg IM] == 2 && [reg I] == 208 && [debug read memory [dict get $::nr_symbols Native_Status]] == 1} nr_boot
debug set_bp 3 {[reg IM] == 2 && [reg I] == 208 && [debug read memory [dict get $::nr_symbols Native_Status]] == 1} nr_ready
debug set_bp 496 {$::nr_started} nr_pre
debug set_bp [dict get $nr_symbols Native_HostIRQ] {$::nr_started && !(([reg SP] >= 32768 && [reg SP] <= 33792) || ([reg SP] >= 61440 && [reg SP] <= 62336))} {
    set s [reg SP]
    set pc [expr {[debug read memory $s] + 256*[debug read memory [expr {$s+1}]]}]
    nr_code failure
    puts stderr "Host IRQ observed an invalid interrupted stack: SP=$s resume=$pc tick=$::nr_post"
    exit 2
}
debug set_watchpoint write_mem [dict get $nr_symbols Native_Published] {$::nr_started} nr_post
debug set_watchpoint write_mem {32768 33791} {$::nr_started && [reg SP] >= 32768 && [reg SP] < $::nr_stack_min} {set ::nr_stack_min [reg SP]}
debug set_watchpoint write_mem 41345 {$::nr_started} {
    puts $::nr_masks "[nr_u32 Native_GameTicks]\t[reg PC]\t[debug read memory 41345]\t[debug read memory [dict get $::nr_symbols Native_GameBusy]]\t[nr_u32 Native_Pending]\t[machine_info time]"
}
foreach pc [dict keys $nr_foreground_counts] {
    debug set_bp $pc {$::nr_started} {dict incr ::nr_foreground_counts [reg PC]}
}
if {[dict get $nr_symbols NATIVE_FINE_IRQ]} {
    set claim_name Native_EnterGameIRQ
    if {[dict exists $nr_symbols Native_ClaimGameIRQ]} {set claim_name Native_ClaimGameIRQ}
    debug set_bp [dict get $nr_symbols $claim_name] {$::nr_started} {incr ::nr_claimed}
    set nr_fine [open [file join $nr_out fine.tsv] w]
    if {[dict get $nr_symbols NATIVE_FINE_DEADLINE]} {
        set nr_deadline_sequence 0
        set nr_deadline_accepted 0
        set nr_fine_math_cases 0
        puts $nr_fine "event\tsequence\tline\terror\ttarget\tclaimed\tpending\taccepted\tarmed\ttime"
        debug set_bp [dict get $nr_symbols Native_DeadlineSync] {$::nr_started} {nr_deadline_log sync}
        debug set_bp [dict get $nr_symbols Native_DeadlinePulse] {$::nr_started} {incr ::nr_deadline_sequence; nr_deadline_log deadline}
        debug set_bp [dict get $nr_symbols Native_DeadlineQueue] {$::nr_started} {incr ::nr_deadline_accepted}
        if {[dict get $nr_symbols NATIVE_FUNCTION_PROBE]} {
            debug set_bp [dict get $nr_symbols Native_DeadlineNextDone] {!$::nr_started} nr_deadline_math
        }
    } else {
    puts $nr_fine "claimed\tquantum\tnext\tpending\tremainder\ttime"
    debug set_bp [dict get $nr_symbols Native_AddClock] {$::nr_started} {
        puts $::nr_fine "$::nr_claimed\t[nr_u32 Native_ClockDelta]\t[debug read memory [dict get $::nr_symbols Native_FineIndex]]\t[nr_u32 Native_Pending]\t[nr_u32 Native_Clock]\t[machine_info time]"
    }
    }
}
proc nr_u16 {name} {
    set a [dict get $::nr_symbols $name]
    return [expr {[debug read memory $a]+256*[debug read memory [expr {$a+1}]]}]
}
proc nr_deadline_log {event} {
    set row [list $event $::nr_deadline_sequence [nr_u16 Native_DeadlineLine] [nr_u16 Native_DeadlineError] [debug read memory [dict get $::nr_symbols Native_FineIndex]] $::nr_claimed [nr_u32 Native_Pending] $::nr_deadline_accepted [debug read memory [dict get $::nr_symbols Native_ClockArmed]] [machine_info time]]
    puts $::nr_fine [join $row "\t"]
}
proc nr_deadline_math {} {
    set n [incr ::nr_fine_math_cases]
    set total [expr {$n*259+($n*1399+30399)/30400}]
    set line [expr {$total%[dict get $::nr_symbols NATIVE_FRAME_LINES]}]
    set error [expr {(30400-($n*1399)%30400)%30400}]
    set target [expr {$line>212 ? 0 : $line}]
    if {[nr_u16 Native_DeadlineLine] != $line || [nr_u16 Native_DeadlineError] != $error || [reg A] != $target} {
        puts stderr "Deadline arithmetic mismatch at case $n"; exit 2
    }
    set ::nr_fine_math_deadline $line
    set ::nr_fine_math_error $error
}
if {[dict exists $nr_symbols NATIVE_FUNCTION_PROBE] && [dict get $nr_symbols NATIVE_FUNCTION_PROBE]} {
    foreach kind {reference optimized} {
        set nr_function_${kind}_count 0
        set nr_function_${kind}_cycles 0
        set name [string totitle $kind]
        debug set_bp [dict get $nr_symbols Native_Function${name}Call] 1 [list nr_function_begin $kind]
        debug set_bp [dict get $nr_symbols Native_Function${name}Done] 1 [list nr_function_end $kind]
    }
}
proc nr_function_begin {kind} {
    set ::nr_function_begin($kind) [expr {round([machine_info time]*3579545)}]
}
proc nr_function_end {kind} {
    incr ::nr_function_${kind}_count
    incr ::nr_function_${kind}_cycles [expr {round([machine_info time]*3579545)-$::nr_function_begin($kind)}]
}
after time 120 {
    nr_snapshot timeout-state.bin
    set file [open [file join $::nr_out timeout-host.bin] wb]
    puts -nonewline $file [debug read_block memory 49152 16384]
    close $file
    set values {}
    foreach n {0 1 15 19 23 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46} {
        lappend values $n [debug read {VDP regs} $n]
    }
    puts stderr "Native acquisition timed out: PC=[reg PC] SP=[reg SP] ticks=[nr_u32 Native_GameTicks] pending=[nr_u32 Native_Pending] busy=[debug read memory [dict get $::nr_symbols Native_GameBusy]] VDP=$values"
    exit 2
}

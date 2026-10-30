# Isolated graphical fixture: only host HUD/VRAM are supplied from verified
# prepared frames. Original game RAM is neither seeded nor executed afterwards.
proc ns_bytes {path} {
    set file [open $path rb]
    set bytes [read $file]
    close $file
    return $bytes
}
proc ns_game_bytes {} {
    return "[debug read_block memory 32768 4096][debug read_block memory 38912 2048][debug read_block memory 40960 392]"
}
proc ns_store {name value} {
    debug write memory [dict get $::ns_symbols $name] $value
}
proc ns_load {index} {
    set fixture [lindex $::ns_fixtures $index]
    lassign $fixture prefix page high low sy
    debug write_block VRAM 0 [ns_bytes $prefix-vram.bin]
    debug write_block memory 49152 [ns_bytes $prefix-hud.bin]
    ns_store Native_Suspended 1
    ns_store Native_VirtualIFF 0
    ns_store Native_ClockArmed 0
    ns_store Native_HUDReady 0
    ns_store Native_StreamActive 0
    ns_store Native_ActiveR2 [expr {31+32*$page}]
    ns_store Native_ActiveHigh $high
    ns_store Native_ActiveLow $low
    ns_store Native_ActiveY $sy
    ns_store Native_DisplayR1 98
    foreach {from to} {life_sat Native_LifeSAT fuel_sat Native_FuelSAT} {
        debug write_block memory [dict get $::ns_symbols $to] [debug read_block memory [dict get $::ns_symbols $from] 12]
    }
    after time 0.400 [list ns_capture $index]
}
proc ns_capture {index} {
    if {[ns_game_bytes] ne $::ns_original} {
        puts stderr "Sprite fixture changed original game RAM"
        exit 2
    }
    lassign [lindex $::ns_fixtures $index] prefix
    screenshot -raw -size auto $prefix-actual.png
    foreach {suffix address size} [list sat 128512 128 colors 128272 208 patterns $::ns_actor_patterns_address 416] {
        set file [open $prefix-$suffix.bin wb]
        puts -nonewline $file [debug read_block VRAM $address $size]
        close $file
    }
    incr index
    if {$index < [llength $::ns_fixtures]} {
        ns_load $index
    } else {
        set file [open [file join $::ns_out execution.json] w]
        puts $file [format {{"complete":true,"fixtures":%d,"original_game_ram_bytes":6536,"original_game_ram_unchanged":true,"gameplay":false,"assembled_sprite_compiler":false}} $index]
        close $file
        exit 0
    }
}
proc ns_begin {} {
    debug remove_bp $::ns_boot_bp
    set ::ns_original [ns_game_bytes]
    # Executed host-only EI/HALT/JP loop in the unused software-dispatch stack.
    # Real raster IRQs continue; Native_Suspended blocks original game dispatch.
    debug write_block memory 61440 [binary format H* fb76c300f0]
    reg SP 62336
    reg PC 61440
    ns_load 0
}
set ns_boot_bp [debug set_bp [dict get $ns_symbols Native_ResetFinalize] {} ns_begin]

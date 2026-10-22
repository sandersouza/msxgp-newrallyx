# Reset-only gate. Full game IRQ/input acquisition is a separate runtime mode.
set nr_started 0
proc nr_binary {name data} {
    set file [open [file join $::nr_out $name] wb]
    puts -nonewline $file $data
    close $file
}
proc nr_capture_reset {} {
    nr_binary initialization.bin "[debug read_block memory 32768 4096][debug read_block memory 38912 2048][debug read_block memory 40960 392]"
    nr_binary program.bin [debug read_block memory 0 16384]
    nr_binary resident.bin [debug read_block memory 16384 16384]
    nr_binary mapper.bin [debug read_block {Main RAM} 0 [debug size {Main RAM}]]
    set file [open [file join $::nr_out execution.json] w]
    puts $file [format {{"schema_version":1,"pc":%d,"sp":%d,"im":%d,"i":%d,"iff":%d,"complete":true}} [reg PC] [reg SP] [reg IM] [reg I] [reg IFF]]
    close $file
    exit 0
}
debug set_bp [dict get $nr_symbols Native_Reset] {[reg IM] == 2 && [reg I] == 208} {set ::nr_started 1}
debug set_bp 3 {$::nr_started} nr_capture_reset
after time 120 {puts stderr "Original reset gate timed out: PC=[reg PC] SP=[reg SP]"; exit 2}

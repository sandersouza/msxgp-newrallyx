# Generic reference defaults to128 KiB; full-session callers pass64/128 KiB.
proc nrallyx_reference_machine {name} {
    set ram_kib 128
    if {[info exists ::env(NRX_REFERENCE_RAM_KIB)]} {
        set ram_kib $::env(NRX_REFERENCE_RAM_KIB)
        if {$ram_kib ni {64 128}} {error "Reference RAM must be 64 or 128 KiB"}
    }
    if {[info exists ::env(NRX_REFERENCE_MACHINE)]} {
        set name $::env(NRX_REFERENCE_MACHINE)
    }
    if {$name eq "Panasonic_FS-A1WSX"} {
        set source [file join $::env(OPENMSX_SYSTEM_DATA) machines "$name.xml"]
        set stream [open $source r]
        set config [read $stream]
        close $stream
        set pattern {(<MemoryMapper id="Main RAM">.*?)<size>[0-9]+</size>}
        if {[regsub $pattern $config "\\1<size>$ram_kib</size>" config] != 1} {
            error "Cannot identify the reference machine's main RAM mapper"
        }
        set readback [expr {$ram_kib == 64 ? 2 : 3}]
        regsub {<MapperReadBackBits>[0-9]+</MapperReadBackBits>} $config \
            "<MapperReadBackBits>$readback</MapperReadBackBits>" config
        set name Panasonic_FS-A1WSX_NR$ram_kib
        set directory [file join $::env(OPENMSX_USER_DATA) machines]
        file mkdir $directory
        set stream [open [file join $directory "$name.xml"] w]
        puts $stream $config
        close $stream
    }
    machine $name
    set largest 0
    foreach device [debug list] {
        if {[debug desc $device] eq "memory mapper"} {
            set largest [expr {max($largest, [debug size $device])}]
        }
    }
    if {$largest < $ram_kib*1024} {error "The selected profile requires at least $ram_kib KiB of RAM mapper"}
    puts stderr "Reference RAM mapper: $largest bytes; machine: $name"
}

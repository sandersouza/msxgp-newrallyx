# Generic reference defaults to128 KiB; full-session callers pass64/128 KiB.
proc nrallyx_reference_machine {name} {
    set ram_kib 128
    if {[info exists ::env(NRX_REFERENCE_RAM_KIB)]} {
        set ram_kib $::env(NRX_REFERENCE_RAM_KIB)
        if {$ram_kib ni {64 128 256 512 1024 2048 4096}} {error "Reference RAM must be64..4096KiB in powers of two"}
    }
    if {[info exists ::env(NRX_REFERENCE_MACHINE)]} {
        set name $::env(NRX_REFERENCE_MACHINE)
    }
    if {$name eq "Panasonic_FS-A1WSX" ||
        ($ram_kib >= 128 && $name in {Panasonic_FS-A1FX Panasonic_FS-A1WX})} {
        set source [file join $::env(OPENMSX_SYSTEM_DATA) machines "$name.xml"]
        set stream [open $source r]
        set config [read $stream]
        close $stream
        set pattern {(<MemoryMapper id="Main RAM">.*?)<size>[0-9]+</size>}
        if {[regsub $pattern $config "\\1<size>$ram_kib</size>" config] != 1} {
            error "Cannot identify the reference machine's main RAM mapper"
        }
        set readback 0
        for {set n [expr {$ram_kib/16}]} {$n>1} {set n [expr {$n/2}]} {incr readback}
        regsub {<MapperReadBackBits>[0-9]+</MapperReadBackBits>} $config \
            "<MapperReadBackBits>$readback</MapperReadBackBits>" config
        set name ${name}_NR$ram_kib
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

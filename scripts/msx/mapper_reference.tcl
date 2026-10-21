# Session-local FS-A1WSX variant for the port's 128 KB RAM-mapper baseline.
proc nrallyx_reference_machine {name} {
    if {$name eq "Panasonic_FS-A1WSX"} {
        set source [file join $::env(OPENMSX_SYSTEM_DATA) machines "$name.xml"]
        set stream [open $source r]
        set config [read $stream]
        close $stream
        set pattern {(<MemoryMapper id="Main RAM">.*?)<size>[0-9]+</size>}
        if {[regsub $pattern $config {\1<size>128</size>} config] != 1} {
            error "Cannot identify the reference machine's main RAM mapper"
        }
        regsub {<MapperReadBackBits>[0-9]+</MapperReadBackBits>} $config \
            {<MapperReadBackBits>3</MapperReadBackBits>} config
        set name Panasonic_FS-A1WSX_NR128
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
    if {$largest < 131072} {error "The port requires at least 128 KB of RAM mapper"}
    puts stderr "Reference RAM mapper: $largest bytes; machine: $name"
}

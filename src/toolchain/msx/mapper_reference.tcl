# Generic reference defaults to128 KiB; full-session callers pass64/128 KiB.
proc nrallyx_reference_machine {name} {
    set ram_kind mapper
    if {[info exists ::env(NRX_REFERENCE_RAM_KIND)]} {
        set ram_kind $::env(NRX_REFERENCE_RAM_KIND)
        if {$ram_kind ni {mapper plain}} {error "Reference RAM kind must be mapper or plain"}
    }
    set ram_kib 128
    if {[info exists ::env(NRX_REFERENCE_RAM_KIB)]} {
        set ram_kib $::env(NRX_REFERENCE_RAM_KIB)
        if {$ram_kib ni {64 128 256 512 1024 2048 4096}} {error "Reference RAM must be64..4096KiB in powers of two"}
    }
    if {[info exists ::env(NRX_REFERENCE_MACHINE)]} {
        set name $::env(NRX_REFERENCE_MACHINE)
    }
    if {$ram_kind eq "plain" && ($ram_kib != 64 || $name ne "Panasonic_FS-A1WSX")} {
        error "Plain reference RAM requires the64KiB FS-A1WSX profile"
    }
    if {$name eq "Panasonic_FS-A1WSX" ||
        ($ram_kib >= 128 && $name in {Panasonic_FS-A1FX Panasonic_FS-A1WX})} {
        set source [file join $::env(OPENMSX_SYSTEM_DATA) machines "$name.xml"]
        set stream [open $source r]
        set config [read $stream]
        close $stream
        if {$ram_kind eq "plain"} {
            # Fixed64KiB RAM has no mapper device, FC..FF register behavior,
            # or MapperReadBackBits setting. Keep its original slot topology.
            set pattern {<MemoryMapper id="Main RAM">.*?</MemoryMapper>}
            if {[regsub $pattern $config {<RAM id="Main RAM"><mem base="0x0000" size="0x10000"/></RAM>} config] != 1} {
                error "Cannot identify the reference machine's main RAM mapper"
            }
            regsub {<MapperReadBackBits>[0-9]+</MapperReadBackBits>} $config {} config
            set name ${name}_PLAIN64
            set topology expanded
            if {[info exists ::env(NRX_REFERENCE_PLAIN_TOPOLOGY)]} {set topology $::env(NRX_REFERENCE_PLAIN_TOPOLOGY)}
            if {$topology eq "unexpanded"} {
                regsub {<RAM id="Main RAM">.*?</RAM>} $config {} config
                if {[regsub {<primary external="true" slot="2"/>} $config {<primary slot="2"><RAM id="Main RAM"><mem base="0x0000" size="0x10000"/></RAM></primary>} config]!=1} {error "Cannot install unexpanded fixed RAM"}
                append name _P2
            } elseif {$topology eq "shared"} {
                if {[regsub {<secondary slot="3">\s*<ROM id="FS-A1WSX">.*?</ROM>\s*</secondary>} $config {<secondary external="true" slot="3"/>} config]!=1} {error "Cannot expose shared-primary cartridge slot"}
                append name _SHARED
            } elseif {$topology ne "expanded"} {error "Unknown fixed-RAM slot topology"}
        } else {
            set pattern {(<MemoryMapper id="Main RAM">.*?)<size>[0-9]+</size>}
            if {[regsub $pattern $config "\\1<size>$ram_kib</size>" config] != 1} {
                error "Cannot identify the reference machine's main RAM mapper"
            }
            set readback 0
            for {set n [expr {$ram_kib/16}]} {$n>1} {set n [expr {$n/2}]} {incr readback}
            regsub {<MapperReadBackBits>[0-9]+</MapperReadBackBits>} $config \
                "<MapperReadBackBits>$readback</MapperReadBackBits>" config
            set name ${name}_NR$ram_kib
        }
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
    if {$ram_kind eq "plain"} {
        if {$largest != 0 || [debug size {Main RAM}] != 65536} {error "Plain RAM profile must have64KiB fixed RAM and no RAM mapper"}
        puts stderr "Reference plain RAM: 65536 bytes; RAM mapper: 0 bytes; machine: $name"
    } else {
        if {$largest < $ram_kib*1024} {error "The selected profile requires at least $ram_kib KiB of RAM mapper"}
        puts stderr "Reference RAM mapper: $largest bytes; machine: $name"
    }
}

"""Session-local replay/state capture; never writes guest game memory."""
from .emulator import tcl


def setup(output):
    return [
        'if {[dict get [reverse status] status] ne "enabled"} {reverse start}',
        f'set nrallyx_capture_dir {tcl(output)};set nrallyx_capture_count 0',
        'proc nrallyx_capture {base} {',
        ' file mkdir [file dirname $base]',
        ' reverse savereplay $base.omr',
        ' store_machine [machine] $base.oms',
        ' foreach {extension data} [list state [debug read_block memory 0xc000 12288] vram [debug read_block VRAM 0 131072] vdp [debug read_block {VDP regs} 0 64]] {',
        '  set stream [open $base.$extension wb];puts -nonewline $stream $data;close $stream',
        ' }',
        ' set stream [open $base.txt w]',
        ' puts $stream "time=[machine_info time] PC=[reg PC] SP=[reg SP] primary=[debug read ioports 168] page0=[debug read ioports 252] page3=[debug read ioports 255]"',
        ' puts $stream [reverse status];close $stream',
        ' catch {screenshot -raw $base.png}',
        ' puts stderr "Maze capture saved: $base"',
        '}',
        'proc maze_capture {} {',
        ' nrallyx_capture [file join $::nrallyx_capture_dir capture-[incr ::nrallyx_capture_count]]',
        '}',
        'proc nrallyx_capture_exit {base} {',
        ' if {[catch {nrallyx_capture $base} problem]} {puts stderr "Exit capture failed: $problem"}',
        '}',
        'bind F6 maze_capture',
        f'after quit [list nrallyx_capture_exit [file join {tcl(output)} exit]]',
    ]

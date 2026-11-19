"""Read-only proof of mapper capacity, probe restoration and selected cache tier."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import json
import os
from src.toolchain.msx.emulator import tcl


def setup(syms,out):
    if 'GameAuto_Init.probed' not in syms:return ''
    build=json.loads((out.parent/'session-build.json').read_text())
    machine=os.environ.get('NRX_REFERENCE_MACHINE','Panasonic_FS-A1WSX')
    expected=0 if not build.get('turbo') else 2 if machine in ('Panasonic_FS-A1ST','Panasonic_FS-A1GT') else 1 if machine in ('Panasonic_FS-A1FX','Panasonic_FS-A1WX','Panasonic_FS-A1WSX') else 0
    rom=(out/'measured.rom').read_bytes()
    bank=build['banks']['SESSION_COLD_BANK']
    selected_hook=syms.get('GameSession_BootShow',syms['loop'])
    from session_reference import bank_offset
    at=bank_offset(out.parent,bank)+0x1000
    prefix=rom[at:at+16].hex()
    return f'''
set auto_probe_seen 0
set auto_probe_restored 0
set auto_selected_seen 0
set auto_plain {int(os.environ.get('NRX_REFERENCE_RAM_KIND')=='plain')}
set auto_prefix [binary format H* {prefix}]
set auto_log [open {tcl(out/'mapper-auto.tsv')} w]
puts $auto_log "mapper_kib\tprofile_kib\tturbo_kind\tprobe_restored\tsegments"
proc auto_fail {{message}} {{puts stderr "Auto mapper contract: $message PC=[reg PC]";exit 2}}
proc auto_markers {{}} {{
 set bytes {{}}
 for {{set i 0}} {{$i<$::auto_banks}} {{incr i}} {{lappend bytes [debug read $::auto_device [expr {{$i*16384+0x3ff0}}]]}}
 return $bytes
}}
debug set_bp 0xd500 {{!$::auto_probe_seen && [debug read_block memory 0 16] eq $::auto_prefix}} {{
 set ::auto_probe_seen 1
 set ::auto_banks 0
 foreach device [debug list] {{
  if {{[debug desc $device] eq "memory mapper" && [debug size $device]/16384>$::auto_banks}} {{set ::auto_device $device;set ::auto_banks [expr {{[debug size $device]/16384}}]}}
 }}
 if {{$::auto_plain}} {{
  if {{$::auto_banks!=0 || [debug size {{Main RAM}}]!=65536}} {{auto_fail "Fixed RAM has a mapper or wrong capacity"}}
  set ::auto_banks 1;set ::auto_device {{Main RAM}}
 }}
 set ::auto_before [auto_markers]
 set ::auto_fc [debug read ioports 252]
}}
debug set_bp {syms['GameAuto_Init.probed']} {{$::auto_probe_seen && [debug read_block memory 0 16] eq $::auto_prefix}} {{
 if {{[reg HL]!=$::auto_banks || [auto_markers] ne $::auto_before || [debug read ioports 252]!=$::auto_fc}} {{auto_fail "Capacity/restoration/FC: HL=[reg HL], expected=$::auto_banks, FC=[debug read ioports 252]/$::auto_fc, before=$::auto_before, after=[auto_markers]"}}
 set ::auto_probe_restored 1
}}
debug set_bp {selected_hook} {{!$::auto_selected_seen && [debug read_block memory 0 16] eq $::auto_prefix}} {{
 set ::auto_selected_seen 1
 set ::auto_mapper_kib [expr {{[debug read memory {syms['GameAuto_MemoryKiB']}]+256*[debug read memory {syms['GameAuto_MemoryKiB']+1}]}}]
 set expanded [debug read memory {syms['GameAuto_Expanded']}]
 if {{!$::auto_probe_restored || $::auto_mapper_kib!=($::auto_plain?64:$::auto_banks*16) || $expanded!=($::auto_banks>=8)}} {{auto_fail "Wrong RAM size or cache selection"}}
 set ::auto_profile_kib [expr {{$expanded?128:64}}]
 set mask [expr {{$::auto_banks-1}}]
 set segments [list [debug read memory {syms['GameSession_MainSegment']}] [expr {{[debug read ioports 255]&$mask}}] [debug read memory {syms['GameSession_MapSegments']}] [debug read memory {syms['GameSession_MapSegments']+1}]]
 if {{$expanded}} {{
  lappend segments [debug read memory {syms['GameSession_FlagSegment']}] [debug read memory {syms['GameSession_FlagOffSegment']}]
  if {{[debug read memory {syms['GameSession_FlagNames']}]!=195}} {{auto_fail "Expanded API not selected"}}
 }}
 if {{!$::auto_plain && ([llength [lsort -unique $segments]]!=[llength $segments] || [lindex [lsort -integer $segments] end]>=$::auto_banks)}} {{auto_fail "RAM segment alias"}}
 set ::auto_turbo_kind {f'[debug read memory {syms["GameTurbo_Kind"]}]' if 'GameTurbo_Kind' in syms else '0'}
 if {{$::auto_turbo_kind!={expected}}} {{auto_fail "Turbo capability was not initialized before the hardware check"}}
 puts $::auto_log "$::auto_mapper_kib\t$::auto_profile_kib\t$::auto_turbo_kind\t$::auto_probe_restored\t$segments";flush $::auto_log
}}
'''

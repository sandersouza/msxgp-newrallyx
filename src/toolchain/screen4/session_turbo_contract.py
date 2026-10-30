"""Observe actual CPU/controller state and reject accelerated foreground I/O."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from src.toolchain.msx.emulator import tcl
import os
import json


def setup(syms, out, *, io=True):
    if 'GameTurbo_Kind' not in syms:
        return f'''
set base_cpu_records [open {tcl(out / 'base-cpu.tsv')} w]
puts $base_cpu_records "time\tcpu\tz80_hz"
debug set_bp {syms['loop']} {{[debug read memory 0x4000]==65 && [debug read memory 0x4001]==66 && [debug read memory 0xc00c]==1}} {{
 if {{[get_active_cpu] ne "z80" || [machine_info z80_freq]!=3579545 || !$::z80_freq_locked}} {{puts stderr "Base CPU contract failed";exit 2}}
 puts $::base_cpu_records "[machine_info time]\t[get_active_cpu]\t[machine_info z80_freq]";flush $::base_cpu_records
}}
'''
    machine=os.environ.get('NRX_REFERENCE_MACHINE','Panasonic_FS-A1WSX')
    expected=2 if machine in ('Panasonic_FS-A1ST','Panasonic_FS-A1GT') else 1 if machine in ('Panasonic_FS-A1FX','Panasonic_FS-A1WX','Panasonic_FS-A1WSX') else 0
    bank=json.loads((out.parent/'session-build.json').read_text())['banks']['SESSION_BOOT_BANK']
    prefix=(out/'measured.rom').read_bytes()[bank*16384:bank*16384+16].hex()
    code=f'''
set turbo_started 0
set turbo_main_prefix [binary format H* {prefix}]
array set turbo_returns {{}}
array set turbo_saved {{}}
set turbo_abi_checks 0
set turbo_records [open {tcl(out / 'turbo.tsv')} w]
puts $turbo_records "time\tkind\tactive\tcpu\tz80_hz\tcontroller"
proc turbo_fail {{message}} {{puts stderr "Turbo contract: $message PC=[reg PC] SP=[reg SP]";exit 2}}
proc turbo_observe {{}} {{
 set kind [debug read memory {syms['GameTurbo_Kind']}]
 set active [debug read memory {syms['GameTurbo_Active']}]
 set cpu [get_active_cpu]
 set hz [machine_info z80_freq]
 if {{$kind!={expected}}} {{turbo_fail "Expected backend{expected}, found $kind"}}
 if {{!$::z80_freq_locked}} {{turbo_fail "Synthetic frequency override enabled"}}
 if {{$kind==1}} {{
  set controller [debug read ioports 65]
  if {{($controller&254)!=([debug read memory {syms['GameTurbo_Status']}]&254)}} {{turbo_fail "Unrelated Panasonic status bits changed"}}
  if {{$cpu ne "z80" || $hz!=($active?5369318:3579545) || ($controller&1)!=!$active}} {{turbo_fail "Panasonic mode mismatch"}}
 }} elseif {{$kind==2}} {{
  set controller [debug read "S1990 regs" 6]
  if {{$cpu ne ($active?"r800":"z80") || $controller!=($active?64:96)}} {{turbo_fail "R800 ROM/Z80 mode mismatch"}}
 }} else {{
  set controller -1
  if {{$cpu ne "z80" || $hz!=3579545}} {{turbo_fail "Fallback changed CPU"}}
 }}
 puts $::turbo_records "[machine_info time]\t$kind\t$active\t$cpu\t$hz\t$controller";flush $::turbo_records
}}
debug set_bp {syms['GameTurbo_Prepare']} {{[debug read_block memory 0x2900 16] eq $::turbo_main_prefix}} {{set ::turbo_started 1;turbo_observe}}
debug set_bp {syms['loop']} {{}} {{set ::turbo_started 1;turbo_observe}}
debug set_bp {syms['GameTurbo_Set.done']} {{[debug read_block memory 0x2900 16] eq $::turbo_main_prefix}} {{turbo_observe}}
proc turbo_save {{}} {{
 set sp [reg SP]
 set ret [expr {{[debug read memory $sp]+256*[debug read memory [expr {{$sp+1}}]]}}]
 set key "$ret:[expr {{$sp+2}}]"
 if {{[info exists ::turbo_saved($key)]}} {{return}}
 set values {{}}
 foreach name {{AF BC DE HL IX IY I IM}} {{lappend values [reg $name]}}
 lappend values [expr {{[reg IFF]&1}}] [debug read ioports 168] [debug read ioports 252] [debug read memory 65535]
 set ::turbo_saved($key) $values
 if {{![info exists ::turbo_returns($ret)]}} {{
  set ::turbo_returns($ret) [debug set_bp $ret {{}} {{turbo_check}}]
 }}
}}
proc turbo_check {{}} {{
 set key "[reg PC]:[reg SP]"
 if {{![info exists ::turbo_saved($key)]}} {{return}}
 set values {{}}
 foreach name {{AF BC DE HL IX IY I IM}} {{lappend values [reg $name]}}
 lappend values [expr {{[reg IFF]&1}}] [debug read ioports 168] [debug read ioports 252] [debug read memory 65535]
 if {{$values ne $::turbo_saved($key)}} {{turbo_fail "Register, IFF or slot/mapper ownership changed: $::turbo_saved($key) -> $values"}}
 unset ::turbo_saved($key)
 incr ::turbo_abi_checks
}}
debug set_bp {syms['GameTurbo_Enter']} {{[debug read_block memory 0x2900 16] eq $::turbo_main_prefix}} {{turbo_save}}
debug set_bp {syms['GameTurbo_Leave']} {{[debug read_block memory 0x2900 16] eq $::turbo_main_prefix}} {{turbo_save}}
proc turbo_io {{}} {{
 if {{[get_active_cpu] ne "z80" || [machine_info z80_freq]!=3579545}} {{turbo_fail "Foreground VDP/PSG/PPI I/O at accelerated clock"}}
}}
debug set_watchpoint write_io {{0x98 0x9b}} {{$::turbo_started}} {{turbo_io}}
debug set_watchpoint read_io 0x98 {{$::turbo_started}} {{turbo_io}}
debug set_watchpoint write_io {{0xa0 0xa1}} {{$::turbo_started}} {{turbo_io}}
debug set_watchpoint read_io 0xa2 {{$::turbo_started}} {{turbo_io}}
debug set_watchpoint write_io {{0xa9 0xab}} {{$::turbo_started}} {{turbo_io}}
debug set_watchpoint read_io 0xa9 {{$::turbo_started}} {{turbo_io}}
'''
    return code if io else code.split('proc turbo_io')[0]

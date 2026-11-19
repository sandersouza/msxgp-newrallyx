"""Read-only full-map and caller-ownership observers for the compact decoder.

The breakpoint never supplies map data or changes registers. Expected bytes
come from the independent original map files; reads use the physical RAM
mapper so the caller's restored Page0 cannot conceal the destination segment.
"""
import json
from pathlib import Path


def hooks(bundle, out, syms, rom):
    bundle=Path(bundle)
    layout=bundle/'layout.json'
    if layout.exists() and json.loads(layout.read_text()).get('map_backend')=='stack16':
        rows=json.loads(layout.read_text())['maps']
    else:
        import hashlib
        banks=json.loads((bundle/'session-build.json').read_text())['map_banks']
        rows=[dict(old_bank=b,sha256=hashlib.sha256(rom[b*16384:(b+1)*16384]).hexdigest()) for b in banks]
    expected=''
    for n,row in enumerate(rows):
        data=(bundle/f'session-map-{n//2}.bin').read_bytes()[n%2*16384:(n%2+1)*16384]
        import hashlib
        assert hashlib.sha256(data).hexdigest()==row['sha256']
        expected+=f'set ::map_expected({row["old_bank"]}) [binary format H* {data.hex()}]\n'
    pc=syms['GameSession_CopyMap']
    prefix=rom[pc-0x4000:pc-0x4000+16].hex()
    fixed=json.loads(layout.read_text()).get('fixed_ram') if layout.exists() else None
    if fixed:
        import os
        plain=os.environ.get('NRX_REFERENCE_RAM_KIND')=='plain'
        device_setup='set ::map_ram {Main RAM}' if plain else ''
        offset='[expr {$segment*16384}]' if not plain else f'[expr {{$segment==[debug read memory {syms["GameSession_MapSegments"]}]?16384:32768}}]'
    else:device_setup='';offset='[expr {$segment*16384}]'
    return expected+f'''
set ::map_contract [open [file join $out map-contract.tsv] w]
puts $::map_contract "logical_bank\\tsegment\\tiff\\tinclusive_cycles"
set ::map_ram ""
foreach d [debug list] {{if {{[debug desc $d] eq "memory mapper" && ($::map_ram eq "" || [debug size $d]>[debug size $::map_ram])}} {{set ::map_ram $d}}}}
{device_setup}
proc map_contract_enter {{}} {{
 set bank [reg A];set segment [expr {{[reg C]&([debug size $::map_ram]/16384-1)}}]
 set sp [reg SP];set ret [expr {{[debug read memory $sp]+256*[debug read memory [expr {{$sp+1}}]]}}]
 set ::map_saved [list $bank $segment [reg IX] [reg IY] [expr {{[reg IFF]&1}}] [machine_info time]]
 set ::map_return_bp [debug set_bp $ret "\\[reg SP\\]==[expr {{$sp+2}}]" map_contract_leave]
}}
proc map_contract_leave {{}} {{
 lassign $::map_saved bank segment ix iy iff start
 debug remove_bp $::map_return_bp
 if {{[debug read_block $::map_ram {offset} 16384] ne $::map_expected($bank)}} {{puts stderr "Full map mismatch bank=$bank segment=$segment";exit 12;return}}
 if {{[reg IX]!=$ix || [reg IY]!=$iy || ([reg IFF]&1)!=$iff}} {{puts stderr "Map decoder changed caller IX/IY/IFF";exit 13;return}}
 puts $::map_contract "$bank\\t$segment\\t$iff\\t[expr {{([machine_info time]-$start)*3579545}}]";flush $::map_contract
}}
debug set_bp {pc} {{[debug read_block memory {pc} 16] eq [binary format H* {prefix}]}} map_contract_enter
'''

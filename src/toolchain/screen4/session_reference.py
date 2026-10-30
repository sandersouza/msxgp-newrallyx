"""Bind full-session emulator checks to the built ROM's actual RAM profile."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from src.toolchain.msx.artifacts import cartridge_path


def runtime_symbols(table):
    """Select observer PCs for the machine's one-time chosen foreground loop."""
    if 'GameTurbo_Loop' in table and os.environ.get('NRX_REFERENCE_MACHINE','Panasonic_FS-A1WSX') in (
            'Panasonic_FS-A1FX','Panasonic_FS-A1WX','Panasonic_FS-A1WSX','Panasonic_FS-A1ST','Panasonic_FS-A1GT'):
        table['loop']=table['GameTurbo_Loop']
        table['frame_done']=table['GameTurbo_FrameDone']
    return table


def runtime_guard(bundle):
    """Reject BIOS/cache numeric PC aliases before synthetic guest injection."""
    bundle=Path(bundle)
    build=json.loads((bundle/'session-build.json').read_text())
    if not build.get('turbo',False):return '1'
    bank=build['banks']['SESSION_BOOT_BANK']
    prefix=cartridge_path(bundle).read_bytes()[bank*16384:bank*16384+16].hex()
    return f'[debug read_block memory 0x2900 16] eq [binary format H* {prefix}]'


def configure(bundle):
    """Reject conflicting overrides rather than certify 64 KiB on 128 KiB."""
    profile=json.loads((Path(bundle)/'session-build.json').read_text())
    # Older preserved bundles predate the 64 KiB adapter and require 128 KiB.
    ram=int(profile.get('ram_kib',128))
    if ram not in (64,128):
        raise ValueError('Unknown full-session RAM profile')
    requested=os.environ.get('NRX_REFERENCE_RAM_KIB')
    if profile.get('ram_auto',False):
        selected=int(requested or 64)
        if selected not in (64,128,256,512,1024,2048,4096):
            raise ValueError('Automatic reference RAM must be64..4096KiB in powers of two')
        os.environ['NRX_REFERENCE_RAM_KIB']=str(selected)
        return selected
    if requested is not None and requested!=str(ram):
        raise ValueError(f'Built ROM requires profile {ram} KiB; conflicting NRX_REFERENCE_RAM_KIB={requested}')
    os.environ['NRX_REFERENCE_RAM_KIB']=str(ram)
    return ram

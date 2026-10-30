"""Bind full-session emulator checks to the built ROM's actual RAM profile."""
import json
import os
from pathlib import Path


def configure(bundle):
    """Reject conflicting overrides rather than certify 64 KiB on 128 KiB."""
    profile=json.loads((Path(bundle)/'session-build.json').read_text())
    # Older preserved bundles predate the 64 KiB adapter and require 128 KiB.
    ram=int(profile.get('ram_kib',128))
    if ram not in (64,128):
        raise ValueError('Unknown full-session RAM profile')
    requested=os.environ.get('NRX_REFERENCE_RAM_KIB')
    if requested is not None and requested!=str(ram):
        raise ValueError(f'Built ROM requires profile {ram} KiB; conflicting NRX_REFERENCE_RAM_KIB={requested}')
    os.environ['NRX_REFERENCE_RAM_KIB']=str(ram)
    return ram

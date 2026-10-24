#!/usr/bin/env python3
"""Acquire the unmodified arcade's two-player turns through real input ports."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import destination
from scripts.graphics.roms import input_records,load_metadata,validate_roms
from scripts.scenes.bundle import digest
from scripts.scenes.storage import require_ignored,json_write,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path(__file__).resolve().parents[1]
    out=destination(root,args.output);require_ignored(root,[out/'events.tsv']);out.mkdir(parents=True)
    roms=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Session inventory requires MAME 0.289')
    script=root/'scripts/msx/session_inventory.lua'
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-debug','-debugger','none','-autoboot_delay','0','-autoboot_script',str(script),
        '-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-seconds_to_run','700']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,check=True,timeout=180,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,SESSION_INVENTORY_OUTPUT=str(out)))
    if '[LUA ERROR]' in (out/'mame.log').read_text():
        raise ValueError('Original lifecycle acquisition reported a Lua failure')
    if not (out/'complete').is_file():raise ValueError('Incomplete original two-player lifecycle')
    turns=[list(map(int,row.split())) for row in (out/'events.tsv').read_text().splitlines()]
    if [row[1] for row in turns]!=[0,1,0,1,0,1]:raise ValueError('Unexpected original turn sequence')
    if any(row[6]!=0 for row in turns) or turns[0][2:4]!=[3,3]:
        raise ValueError('Original start credit/life defaults differ from the selected adapter')
    expected=[[3,3],[2,3],[2,2],[1,2],[1,1],[0,1]]
    if [row[2:4] for row in turns]!=expected:raise ValueError('Original lives/turn accounting diverged')
    if input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))!=roms:
        raise ValueError('Original ROM inputs changed during acquisition')
    json_write(out/'report.json',dict(roms=roms,emulator=version,script_sha256=digest(script),
        turns=turns,guest_state_writes=False,rejected_insufficient_credits=True,
        scope='Unmodified original: two real coins, two-player start, six natural turns/deaths and zero remaining lives. No CPU/RAM/ROM writes.'))
    require_ignored(root,[x for x in out.rglob('*') if x.is_file()]);seal(out)
    print(f'Original two-player lifecycle acquired: {out}/report.json')


if __name__=='__main__':main()

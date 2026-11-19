"""Run the existing independent PSG/PCM fixture after real512KiB disk boot.

Only the observer/startup transport changes. The fixture deliberately installs
its existing sound-event/velocity stubs after normal game initialization; this
is not a natural gameplay or audio-lifecycle acceptance claim.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/toolchain/screen4'),str(ROOT/'scripts'),str(ROOT)]
import session_audio_verify as audio
import session_reference as reference
from src.toolchain.msx.emulator import tcl


def verify(mode='dos'):
    runtime=ROOT/'references/build/game-mapper512-game-runtime'
    bundle=ROOT/'references/build/game-mapper512-game'
    plan=json.loads((bundle/'plan.json').read_text())
    previous_ram=os.environ.get('NRX_REFERENCE_RAM_KIB');os.environ['NRX_REFERENCE_RAM_KIB']='512'
    # The frozen cartridge remains only an input fingerprint. Execution starts
    # through the real filesystem and uses the relinked RAM symbols/workers.
    original_path=audio.cartridge_path;original_guard=reference.runtime_guard
    from mapper512_reference import reference as mapper_reference
    audio.cartridge_path=lambda _:mapper_reference()
    prefix=(runtime/'assembly/session-boot-linked.bin').read_bytes()[:16].hex()
    reference.runtime_guard=lambda _:f'[debug read ioports 252]%32==1 && [debug read ioports 253]%32==6 && [debug read_block memory 0x2900 16] eq [binary format H* {prefix}]'
    run=subprocess.run
    def launch(args,**kwargs):
        if args[0]=='openmsx':
            script=Path(args[args.index('-script')+1]);out=script.parent
            files=out/'files';files.mkdir()
            for p in (bundle/'files').glob('NRX512.*'):shutil.copyfile(p,files/p.name)
            if mode=='dos':
                for n in ['msxdos.sys','command.com']:shutil.copyfile(ROOT/'references/cache/dos-validation'/n,files/n.upper())
                (files/'AUTOEXEC.BAT').write_bytes(b'NRX512\r\n')
            text=script.read_text()
            text,n=re.subn(r'cart [^\n]+ -romtype ASCII8\nreset',f'diska {tcl(files)}\nreset',text)
            assert n==1,'Audio fixture startup changed'
            text=text.replace('after time 90','after time 900')
            if mode=='basic':text+='\nafter time 10 {type_via_keybuf "\\rrun \\"NRX512.BAS\\"\\r"}\n'
            script.write_text(text)
        return run(args,**kwargs)
    subprocess.run=launch
    try:out=audio.verify(runtime)
    finally:
        subprocess.run=run;audio.cartridge_path=original_path;reference.runtime_guard=original_guard
        if previous_ram is None:os.environ.pop('NRX_REFERENCE_RAM_KIB',None)
        else:os.environ['NRX_REFERENCE_RAM_KIB']=previous_ram
    report=json.loads((out/'report.json').read_text())
    report.update(mode=mode,resource_sha256=plan['resource_sha256'],bridge_sha256=plan['bridge_sha256'],
                  cartridge=False,scope='Existing synthetic sound-event/velocity PSG and recorded-PCM fixture after real512KiB DOS/BASIC boot; no physical/listening or natural gameplay acceptance.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(path=str(out),mode=mode,passed=report['passed'],resource_sha256=plan['resource_sha256']),indent=2))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['dos','basic'],default='dos');a=p.parse_args();verify(a.mode)

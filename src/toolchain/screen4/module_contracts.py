"""Enforce the frozen binary/map and declared assembly module interfaces.

Only hashes, sizes and exported symbol addresses are emitted. ROMs, maps and
source-derived payloads remain in the contributor's ignored bundle.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from session_reference import cartridge_path

import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = RUNTIME
SYMBOL = re.compile(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)\s*$')
ABI_FIELDS = ('inputs','outputs','registers','interrupts','memory','dependencies','reuse')


def rebuild_baseline(bundle,profile):
    """Recreate disposable baseline bytes from the recorded source configuration."""
    import os,subprocess,sys
    from build_profiles import build_reference
    if profile=='first_stage':raise ValueError('Rebuild the recorded first-stage configuration explicitly')
    build_reference()
    # This gate compares a historical whole ROM, including its original logo.
    # Keep that input pinned instead of blessing a new asset by changing hashes.
    import io
    from PIL import Image
    root=HERE.parents[1]
    original=subprocess.check_output(['git','show','ae19827eddcd941818f34ecf4d5e8da222db904c:assets/msx-logo.png'],cwd=root)
    with Image.open(io.BytesIO(original)) as image:
        image=image.convert('RGB')
        points=[(x,y) for y in range(image.height) for x in range(image.width) if max(image.getpixel((x,y)))<30]
        x0,y0=min(x for x,y in points),min(y for x,y in points)
        assert (max(x for x,y in points)+1-x0,max(y for x,y in points)+1-y0)==(162,60)
        logo=Image.new('1',(54,20))
        logo.putdata([255 if min(image.getpixel((x0+3*x+1,y0+3*y+1)))>=128 else 0 for y in range(20) for x in range(54)])
    Path(bundle).mkdir(parents=True,exist_ok=True)
    historical_logo=Path(bundle).resolve()/'baseline-logo.bmp';logo.save(historical_logo)
    env=dict(os.environ,NRX_RAM_AUTO='0',NRX_RAM_KIB='128',NRX_TURBO='0',
        NRX_TEST_MODE=str(int(profile=='test')),NRX_HUD_VARIANT='classic' if profile=='classic' else 'compact',
        NRX_HARDWARE_CHECK=str(int(profile!='no_check')),NRX_MSX_LOGO='1',NRX_BUILD_OUTPUT=str(Path(bundle).resolve()),NRX_BASELINE_LOGO=str(historical_logo))
    subprocess.run([sys.executable,'-B',str(source_path('build.py')),'--full-session'],env=env,check=True)


def symbols(text):
    rows = SYMBOL.findall(text)
    if not rows:
        raise ValueError('Empty assembler symbol map')
    result = {name:int(value,16) for name,value in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate assembler symbol')
    return result


def symbol_digest(table):
    canonical = json.dumps(table,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(canonical).hexdigest()


def validate_registry(registry, root=HERE):
    ids = set()
    profiles = set(registry['profiles'])
    for module in registry['modules']:
        if module['id'] in ids:
            raise ValueError('Duplicate module id')
        ids.add(module['id'])
        if not set(module['profiles']) <= profiles or not module['profiles']:
            raise ValueError(f'Unknown/empty profiles: {module["id"]}')
        entry = (root/module['entry']).resolve()
        if not entry.is_relative_to(root.resolve()) or not entry.is_file():
            raise ValueError(f'Missing/unsafe module entry: {module["entry"]}')
        if not module['exports'] or len(set(module['exports'])) != len(module['exports']):
            raise ValueError(f'Empty/duplicate exports: {module["id"]}')
        for field in ABI_FIELDS:
            if field not in module or (field != 'dependencies' and not module[field]):
                raise ValueError(f'Missing {field} contract: {module["id"]}')


def verify_image(data, table, expected):
    if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
        raise ValueError('Module extraction changed the cartridge bytes or size')
    if len(table) != expected['symbol_count'] or symbol_digest(table) != expected['symbols_sha256']:
        raise ValueError('Module extraction changed symbol addresses, state aliases or layout')


def verify(bundle, profile, registry, baselines):
    validate_registry(registry)
    bundle = Path(bundle)
    data = (cartridge_path(bundle)).read_bytes()
    table = symbols((bundle/'lab.sym').read_text())
    verify_image(data,table,baselines[profile])
    exports = {}
    for module in registry['modules']:
        if profile not in module['profiles']:
            continue
        missing = [name for name in module['exports']+module['dependencies'] if name not in table]
        if missing:
            raise ValueError(f'Module {module["id"]} has unresolved contract symbols: {missing}')
        exports[module['id']] = {name:table[name] for name in module['exports']}
    return dict(passed=True,profile=profile,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                symbol_count=len(table),symbols_sha256=symbol_digest(table),exports=exports,
                resource_delta=dict(rom_bytes=0,instructions=0,ram_bytes=0,vram_bytes=0,
                                    stack_bytes=0,mapper_writes=0,vdp_writes=0,synchronization=0),
                proof='Complete ROM and complete symbol map match the frozen pre-extraction profile. Same instructions/data, RAM aliases, branch destinations and mapper/VDP schedule; no runtime wrapper was introduced.',
                limitation='The zero-delta proof is relative to this exact accepted build/configuration. New host bindings, inputs, assets or hardware need their own integration validation.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',required=True,choices=('default','test','classic','no_check','first_stage'))
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not cartridge_path(args.bundle).exists():rebuild_baseline(args.bundle,args.profile)
    registry=json.loads((HERE/'modules/contracts.json').read_text())
    baselines=json.loads((HERE/'modules/baselines.json').read_text())
    result=verify(args.bundle,args.profile,registry,baselines)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('passed','profile','bytes','sha256','symbol_count','resource_delta')},indent=2))

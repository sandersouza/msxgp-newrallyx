"""Enforce the frozen binary/map and declared assembly module interfaces.

Only hashes, sizes and exported symbol addresses are emitted. ROMs, maps and
source-derived payloads remain in the contributor's ignored bundle.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
SYMBOL = re.compile(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)\s*$')
ABI_FIELDS = ('inputs','outputs','registers','interrupts','memory','dependencies','reuse')


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
    data = (bundle/'fixed-hud.rom').read_bytes()
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
    registry=json.loads((HERE/'modules/contracts.json').read_text())
    baselines=json.loads((HERE/'modules/baselines.json').read_text())
    result=verify(args.bundle,args.profile,registry,baselines)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('passed','profile','bytes','sha256','symbol_count','resource_delta')},indent=2))

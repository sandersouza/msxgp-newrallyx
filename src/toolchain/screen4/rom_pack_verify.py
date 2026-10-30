"""Compare every graphics transfer and cold replay command across ROM layouts.

This independent decoder never invokes the packer/compiler. Reports contain
only hashes and counts; original bytes remain in the ignored local bundles.
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

from rom_audit import decode_transfer, BANK_BYTES


def load(bundle):
    bundle = Path(bundle)
    return dict(rom=(cartridge_path(bundle)).read_bytes(),
                session=json.loads((bundle/'session-build.json').read_text()),
                game=json.loads((bundle/'game-resources.json').read_text()),
                symbols=json.loads((bundle/'hud-programs.json').read_text())['linked_symbols'],
                boot=json.loads((bundle/'session-boot.json').read_text()))


def transfer(bundle, bank, offset, packed):
    rom = bundle['rom']
    at = bank*BANK_BYTES+offset
    target,lo,hi = rom[at:at+3]
    if not target:
        raise ValueError('Unexpected graphics fallback')
    symbols = bundle['symbols']
    program = decode_transfer(rom,target,lo+hi*256,
                              exit_address=symbols['hud_upload.done'],
                              transfer_address=symbols['GamePacketFast_Transfer'],
                              inline_literals=not packed)
    writes = [(s['destination'],rom[s['literal_offset']:s['literal_offset']+s['bytes']])
              for s in program['literal_spans']]
    return program,writes


def cold_records(bundle):
    """Decode actual descriptors, destinations, fills and bank-local references."""
    rom = bundle['rom']
    bank = bundle['session']['banks']['SESSION_BOOT_BANK']
    table = bank*BANK_BYTES+0x1000
    records = []
    for frame in range(bundle['boot']['frame_count']):
        descriptor = table+frame*5
        bank = rom[descriptor]
        address = int.from_bytes(rom[descriptor+1:descriptor+3],'little')
        tick = int.from_bytes(rom[descriptor+3:descriptor+5],'little')
        commands = []
        seen = set()
        while True:
            if (not 0 <= bank < len(rom)//BANK_BYTES or not 0x8000 <= address < 0xc000 or
                    (bank,address) in seen):
                raise ValueError('Invalid/cyclic cold replay pointer')
            seen.add((bank,address))
            at = bank*BANK_BYTES+address-0x8000
            op = rom[at]
            if op == 0:
                break
            if op == 3:
                if address+4 > 0xc000:
                    raise ValueError('Truncated cold chain')
                bank = rom[at+1]
                address = int.from_bytes(rom[at+2:at+4],'little')
                continue
            if op not in (1,2,4) or address+4 > 0xc000:
                raise ValueError('Unknown/truncated cold command')
            destination = int.from_bytes(rom[at+1:at+3],'little')
            length = rom[at+3] or 256
            size = 4+length if op == 1 else 5 if op == 2 else 6
            if address+size > 0xc000 or destination+length > 27136:
                raise ValueError('Cold command crosses bank or VRAM page')
            if op == 1:
                raw = rom[at+4:at+size]
            elif op == 2:
                raw = rom[at+4:at+5]*length
            else:
                pointer = int.from_bytes(rom[at+4:at+6],'little')
                if not 0x8000 <= pointer or pointer+length > 0xc000:
                    raise ValueError('Invalid cold literal alias')
                source = bank*BANK_BYTES+pointer-0x8000
                raw = rom[source:source+length]
            commands.append((destination,raw))
            address += size
        records.append((tick,commands))
    return records


def verify(before, after):
    before,after = load(before),load(after)
    for key in ('sample_frames','publication_ticks','physical_deadline_ticks','palette'):
        if before['boot'][key] != after['boot'][key]:
            raise ValueError(f'Boot contract changed: {key}')
    cases = []
    for current in range(64):
        for old in range(64):
            cases.append(('hud',4+current,4+current,0x2600+old*3))
    for old_bank,new_bank in zip(before['session']['edge_banks'],after['session']['edge_banks'],strict=True):
        for old in range(9):
            cases.append(('boundary',old_bank,new_bank,0x2900+old*3))
    counts = dict(hud=0,boundary=0)
    compared = 0
    for family,old_bank,new_bank,offset in cases:
        a,writes_a = transfer(before,old_bank,offset,False)
        b,writes_b = transfer(after,new_bank,offset,True)
        if (writes_a != writes_b or a['code_bytes'] != b['code_bytes'] or
                a['normalized_sha256'] != b['normalized_sha256'] or
                a['estimated_instruction_cycles'] != b['estimated_instruction_cycles']):
            raise ValueError(f'Graphics transfer changed: {family} bank={old_bank} pointer={offset:x}')
        if b['bank'] != new_bank:
            raise ValueError('Graphics transfer left its source bank')
        counts[family] += 1
        compared += sum(len(data) for _,data in writes_a)
    # Check preserved source tables, padding, name/radar programs and cost rows.
    for phase in range(64):
        for begin,end in ((0,0x901),(0xa00,0xf01),(0x1000,0x1501),(0x1f00,0x2201),
                          (0x2300,0x2300+505),(0x2700,0x2900),(0x2940,0x2980),(0x3800,0x3c00)):
            at=(4+phase)*BANK_BYTES
            if before['rom'][at+begin:at+end] != after['rom'][at+begin:at+end]:
                raise ValueError('Preserved phase field changed')
    for old_bank,new_bank in zip(before['session']['edge_banks'],after['session']['edge_banks'],strict=True):
        if before['rom'][old_bank*BANK_BYTES:old_bank*BANK_BYTES+0x2900] != after['rom'][new_bank*BANK_BYTES:new_bank*BANK_BYTES+0x2900]:
            raise ValueError('World-edge source table changed')
    for name in ('terrain_banks','map_banks'):
        for old_bank,new_bank in zip(before['session'][name],after['session'][name],strict=True):
            if before['rom'][old_bank*BANK_BYTES:(old_bank+1)*BANK_BYTES] != after['rom'][new_bank*BANK_BYTES:(new_bank+1)*BANK_BYTES]:
                raise ValueError(f'World resource changed: {name}')
    preserved_banks=[]
    for section,names in (('session',('SESSION_IMAGE_BANK','SESSION_DATA_BANK','SESSION_BANK','SESSION_DECOR_BANK','AUDIO_BANK')),
                          ('game',('GAME_NATIVE_BANK','PLAYER_DATA_BANK','GAME_AUDIO_BANK','GAME_RESOURCE_BANK'))):
        for name in names:
            old_bank=before[section]['banks'][name]
            new_bank=after[section]['banks'][name]
            if before['rom'][old_bank*BANK_BYTES:(old_bank+1)*BANK_BYTES] != after['rom'][new_bank*BANK_BYTES:(new_bank+1)*BANK_BYTES]:
                raise ValueError(f'Immutable resource bank changed: {name}')
            preserved_banks.append(name)
    old_replay,new_replay = cold_records(before),cold_records(after)
    if old_replay != new_replay:
        raise ValueError('Boot destinations, payload, order or deadlines changed')
    return dict(passed=True,before_sha256=hashlib.sha256(before['rom']).hexdigest(),
                after_sha256=hashlib.sha256(after['rom']).hexdigest(),
                before_bytes=len(before['rom']),after_bytes=len(after['rom']),
                transitions=counts,referenced_graphics_bytes_compared=compared,
                replay_frames=len(new_replay),replay_commands=sum(len(c) for _,c in new_replay),
                byte_identical_resource_banks=preserved_banks,
                active_transfer_instructions_unchanged=True,
                scope='Independent ROM decoding: all HUD/boundary writes and code shapes/cycle estimates; preserved graphic tables, all round maps/terrain; boot destinations/payload/order/deadlines. Emulator behavior and timing are verified separately.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--after',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=verify(args.before,args.after)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

"""Inspect generated graphics tables and transfer programs without modifying ROMs.

Only hashes, counts, ownership ranges and storage models are emitted. Original
graphics/program bytes must remain in the contributor's ignored bundle.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from session_reference import cartridge_path

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.toolchain.msx.cartridge_size import inventory, BANK_BYTES
from session_phase import compiled_cycles


def decode_transfer(rom, bank, address, *, exit_address, transfer_address, inline_literals=True):
    """Validate the compile_packet vocabulary, including inline literal bounds."""
    if not 0x8000 <= address < 0xc000 or not 0 <= bank < len(rom)//BANK_BYTES:
        raise ValueError('Transfer entry outside the ROM bank')
    base = bank*BANK_BYTES
    start = base+address-0x8000
    at = start
    if rom[at:at+2] != b'\x0e\x98':
        raise ValueError('Transfer is not an emitted HUD program')
    normalized = bytearray()
    sources = []
    relocations = []
    pending = None
    count = None
    immediate_values = []
    while at < base+BANK_BYTES:
        offset = at
        op = rom[at]
        at += 1
        width = (3 if op in (0x3a,0x21,0xcd,0xc3) else
                 2 if op in (0x0e,0x3e,0xf6,0xe6,0xd3,0x06,0xed) else 1)
        if offset+width > base+BANK_BYTES:
            raise ValueError('Transfer code crosses a bank boundary')
        if op in (0xf3, 0xfb, 0x87, 0x0f):
            length = 1
        elif op in (0x0e, 0x3e, 0xf6, 0xe6, 0xd3, 0x06):
            length = 2
            if op == 0x06:
                count = rom[at]
            elif op == 0x3e:
                immediate_values.append(rom[at])
        elif op in (0x3a, 0x21, 0xcd, 0xc3):
            length = 3
            value = int.from_bytes(rom[at:at+2], 'little')
            if op == 0x21:
                if len(immediate_values)<2:
                    raise ValueError('Missing emitted VDP address')
                pending = dict(address=value, bytes=0,
                               destination=immediate_values[-2]+((immediate_values[-1]&63)<<8))
                sources.append(pending)
                count = None
            elif op == 0xcd:
                if value != transfer_address or pending is None or not count:
                    raise ValueError('Unexpected transfer helper or count')
                pending['bytes'] += count
                relocations.append(offset+1-BANK_BYTES)
            elif op == 0xc3:
                if value != exit_address:
                    raise ValueError('Unexpected transfer exit')
                relocations.append(offset+1-BANK_BYTES)
        elif op == 0xed:
            length = 2
            if rom[at] != 0xa3 or pending is None:
                raise ValueError('Unexpected short transfer')
            pending['bytes'] += 1
        else:
            raise ValueError(f'Unexpected generated opcode {op:02x}')
        if offset+length > base+BANK_BYTES:
            raise ValueError('Transfer code crosses a bank boundary')
        instruction = rom[offset:offset+length]
        normalized.extend(b'\x21\0\0' if op == 0x21 else instruction)
        at = offset+length
        if op == 0xc3:
            break
    else:
        raise ValueError('Unterminated transfer program')
    code_bytes = at-start
    literal = bytearray()
    expected = address+code_bytes
    for source in sources:
        if (not source['bytes'] or not 0x8000 <= source['address'] or
                source['address']+source['bytes'] > 0xc000 or
                (inline_literals and source['address'] != expected)):
            raise ValueError('Noncontiguous or empty emitted literal span')
        expected += source['bytes']
        if inline_literals and expected > 0xc000:
            raise ValueError('Transfer literals cross a bank boundary')
        begin = base+source['address']-0x8000
        literal.extend(rom[begin:begin+source['bytes']])
    if inline_literals and len(literal) != expected-address-code_bytes:
        raise ValueError('Truncated transfer literal data')
    spans = [dict(destination=s['destination'],bytes=s['bytes'],
                  literal_offset=base+s['address']-0x8000) for s in sources]
    return dict(bank=bank, address=address, offset=start, code_bytes=code_bytes,
                literal_bytes=len(literal), total_bytes=code_bytes+len(literal),
                spans=len(sources), literal_spans=spans,
                normalized_sha256=hashlib.sha256(normalized+literal).hexdigest(),
                relocations=relocations,
                estimated_instruction_cycles=compiled_cycles(rom[BANK_BYTES:], bank, address))


def next_fit(sizes, capacity=BANK_BYTES):
    pages = used = 0
    for size in sizes:
        if size > capacity:
            raise ValueError('Program exceeds a bank')
        if not pages or used+size > capacity:
            pages += 1
            used = 0
        used += size
    return pages*capacity


def free_ranges(protected, capacity=BANK_BYTES):
    result=[];at=0
    for begin,end in sorted(protected):
        if not 0<=begin<=end<=capacity:
            raise ValueError('Invalid protected ROM range')
        if begin>at:result.append([at,begin])
        at=max(at,end)
    if at<capacity:result.append([at,capacity])
    return result


def place_code(programs, identities, gaps):
    gaps=[list(gap) for gap in gaps];spill=[];placed=0
    for identity in sorted(set(identities),key=lambda key:(-programs[key]['code_bytes'],key)):
        size=programs[identity]['code_bytes']
        choices=[(end-begin-size,index) for index,(begin,end) in enumerate(gaps) if end-begin>=size]
        if not choices:spill.append(identity);continue
        _,index=min(choices);gaps[index][0]+=size;placed+=size
    return gaps,spill,placed


def verify_literal_aliases(rom, program, source_bank, ranges):
    """Verify every existing inline byte against the proposed same-bank table."""
    checked=0
    for span in program['literal_spans']:
        matches=[(destination,source,length) for destination,source,length in ranges
                 if destination<=span['destination'] and span['destination']+span['bytes']<=destination+length]
        if len(matches)!=1:raise ValueError('Literal does not map to exactly one raw graphics table')
        destination,source,length=matches[0]
        at=source_bank*BANK_BYTES+source+span['destination']-destination
        literal=span['literal_offset'];size=span['bytes']
        if rom[at:at+size]!=rom[literal:literal+size]:
            raise ValueError('Proposed raw graphics alias changes literal bytes')
        checked+=size
    return checked


def replay_commands(rom, metadata, boot):
    """Expand existing cold opcode4 references into raw opcode1 command models."""
    bank=metadata['banks']['SESSION_BOOT_BANK'];records=[];wire=0;source_banks=set();chains=0
    table=bank*BANK_BYTES+0x1000
    for frame in range(boot['frame_count']):
        at=table+frame*5;source=rom[at];address=int.from_bytes(rom[at+1:at+3],'little')
        commands=[];steps=0;visited=set()
        while True:
            steps+=1
            if (steps>100000 or not 0x8000<=address<0xc000 or
                    not 0<=source<len(rom)//BANK_BYTES or (source,address) in visited):
                raise ValueError('Invalid/cyclic boot stream')
            visited.add((source,address))
            at=source*BANK_BYTES+address-0x8000;op=rom[at]
            source_banks.add(source)
            if op==0:commands.append((0,None));wire+=1;break
            if op==3:
                if address+4>0xc000:raise ValueError('Replay chain crosses bank')
                source=rom[at+1];address=int.from_bytes(rom[at+2:at+4],'little');wire+=4;chains+=1;continue
            if op not in (1,2,4) or address+4>0xc000:
                raise ValueError('Unknown/truncated cold replay opcode')
            length=rom[at+3] or 256
            if op==1:
                payload=bytes(rom[at+4:at+4+length]);size=4+length
                commands.append((1,payload))
            elif op==2:size=5;commands.append((2,None))
            elif op==4:
                if address+6>0xc000:raise ValueError('Replay source pointer crosses bank')
                pointer=int.from_bytes(rom[at+4:at+6],'little')
                if not 0x8000<=pointer or pointer+length>0xc000:
                    raise ValueError('Replay literal pointer outside bank')
                begin=source*BANK_BYTES+pointer-0x8000
                payload=bytes(rom[begin:begin+length]);size=6
                commands.append((1,payload))
            else:raise ValueError('Unknown cold replay opcode')
            if address+size>0xc000:raise ValueError('Replay command crosses bank')
            address+=size;wire+=size
        records.append(commands)
    raw=sum(1 if op==0 else 5 if op==2 else 4+len(data) for record in records for op,data in record)
    if raw!=boot['unshared_stream_bytes'] or wire!=boot['compressed_bytes']:
        raise ValueError('Cold replay stream accounting mismatch')
    return dict(records=records,banks=sorted(source_banks),wire_bytes=wire,raw_bytes=raw,chains=chains)


def pack_replay_model(records, segments):
    """Model the existing cold codec in unused holes, with unchanged span sizes."""
    segments=sorted(segments,key=lambda s:(-(s[2]-s[1]),s[0],s[1]))
    current=None;used=0;literals=set();encoded=0;chains=0;chunks=0;reuses=0
    for record in records:
        for op,payload in record:
            raw=1 if op==0 else 5 if op==2 else 4+len(payload)
            reused=op==1 and len(payload)>2 and payload in literals
            size=6 if reused else raw
            if current is None or used+size+4>current[2]-current[1]:
                if current is not None:encoded+=4;chains+=1
                candidates=[(i,s) for i,s in enumerate(segments) if s[2]-s[1]>=raw+4]
                if not candidates:return dict(fits=False,encoded_bytes=encoded,remaining_segments=len(segments))
                index,current=candidates[0];segments.pop(index);used=0;literals=set();size=raw;reused=False;chunks+=1
            if reused:reuses+=1
            if op==1 and not reused:literals.add(payload)
            used+=size;encoded+=size
    return dict(fits=True,encoded_bytes=encoded,chunks=chunks,chains=chains,literal_reuses=reuses,
                scope='Storage simulation only. Original command/span lengths and existing opcodes are retained; extra cold chains and changed literal reuse require native-deadline and skip verification.')


def alias_model(rom,bundle,metadata,programs,refs,counts):
    ring=json.loads((bundle/'ring-refresh.json').read_text())
    free=[];spill=set();placed=0;checked=0
    for current in range(64):
        bank=4+current;n=counts[current]
        identities={tuple(e['program']) for e in refs['hud'] if e['key'][1]==current}
        for key in identities:
            checked+=verify_literal_aliases(rom,programs[key],bank,((0x300,0x100,n*8),(0x2300,0x500,n*8)))
        # Keep every authored field, including old atlases and radar programs.
        # Retain complete padded name/pattern/color fields and complete cost
        # blocks too; reclaim only the gaps between emitted resource fields.
        protected=[(0,0x901),
                   (0xa00,0xf01),(0x1000,0x1501),(0x1f00,0x2201),
                   (0x2300,0x2300+505),(0x2600,0x26c0),(0x2700,0x2980)]
        protected.append((0x3800,0x3c00))
        if bank==ring['mapper_bank']:
            protected.append((ring['entry']-0x8000,ring['entry']-0x8000+ring['bytes']))
        gaps,missing,used=place_code(programs,identities,free_ranges(protected))
        free.extend((bank,begin,end) for begin,end in gaps if end>begin);spill.update(missing);placed+=used
    for index,bank in enumerate(metadata['edge_banks']):
        n=rom[bank*BANK_BYTES+0xf00]*8;m=rom[bank*BANK_BYTES+0x1500]*8
        ranges=((0x500,0xb00,min(384,n)),(0x2500,0xd00,min(384,n)),
                (0x448,0xc80,max(0,n-384)),(0x2448,0xe80,max(0,n-384)),
                (0x680,0x1100,m),(0x2680,0x1300,m))
        identities={tuple(e['program']) for e in refs['boundary'] if e['key'][0]==index//8 and e['key'][2]==index%8}
        for key in identities:checked+=verify_literal_aliases(rom,programs[key],bank,ranges)
        gaps,missing,used=place_code(programs,identities,[[0x2920,BANK_BYTES]])
        free.extend((bank,begin,end) for begin,end in gaps if end>begin);spill.update(missing);placed+=used
    spill_bytes=next_fit([programs[key]['total_bytes'] for key in sorted(spill)])
    original_banks=len({p['bank'] for p in programs.values()})
    model_size=len(rom)-original_banks*BANK_BYTES+spill_bytes
    boot=json.loads((bundle/'session-boot.json').read_text())
    cold=replay_commands(rom,metadata,boot) if boot.get('enabled') else None
    replay=pack_replay_model(cold['records'],free) if cold else None
    final_size=model_size-len(cold['banks'])*BANK_BYTES if cold and replay['fits'] else None
    return dict(literal_bytes_checked_against_raw_tables=checked,active_code_bytes_placed=placed,
        spill_programs=len(spill),spill_bank_bytes=spill_bytes,
        replaced_transfer_bank_bytes=original_banks*BANK_BYTES,
        image_bytes_after_transfer_alias_model=model_size,
        remaining_hole_bytes=sum(end-begin for bank,begin,end in free),
        remaining_hole_bytes_at_least_260=sum(end-begin for bank,begin,end in free if end-begin>=260),
        boot_repack=replay,
        original_boot_data_banks=cold['banks'] if cold else [],
        original_boot_wire_bytes=cold['wire_bytes'] if cold else 0,
        original_boot_chains=cold['chains'] if cold else 0,
        image_bytes_after_transfer_and_boot_model=final_size,
        preferred_headroom_in_model=2*1024*1024-final_size if final_size is not None else None,
        scope='Read-only same-bank raw-table alias and hole-packing model; no new active transfer instructions. Actual linker/consumer offsets, size, runtime, full graphics and cold deadlines still require implementation and verification.')


def tile_statistics(rom, groups):
    tiles=[];patterns=[];colors=[]
    for bank,pattern,color,count in groups:
        for index in range(count):
            p=bytes(rom[bank*BANK_BYTES+pattern+index*8:bank*BANK_BYTES+pattern+(index+1)*8])
            c=bytes(rom[bank*BANK_BYTES+color+index*8:bank*BANK_BYTES+color+(index+1)*8])
            patterns.append(p);colors.append(c);tiles.append(p+c)
    return dict(tile_records=len(tiles),raw_bytes=len(tiles)*16,
                unique_pattern_color_pairs=len(set(tiles)),
                unique_pair_bytes=len(set(tiles))*16,
                repeated_pair_bytes=(len(tiles)-len(set(tiles)))*16,
                unique_pattern_bytes=len(set(patterns))*8,unique_color_bytes=len(set(colors))*8,
                scope='Exact pattern/color bytes only, excluding table padding. Sharing requires preserving tile IDs, phase addressing and access cost.')


def ownership(rom,metadata,families,cold_banks,bundle,packed=False):
    owners={0:'resident-code'}
    def mark(banks,name):
        for bank in banks:
            if bank in owners:raise ValueError('Overlapping bank ownership')
            owners[bank]=name
    mark([1],'initial-terrain');mark([2,3],'initial-map')
    mark(range(4,68),'phase-hud-tables-workers-transfer-code-and-cold-streams' if packed else 'phase-hud-tables-and-embedded-workers')
    if not packed:mark(families['hud']['banks'],'hud-transfer-programs')
    old=json.loads((bundle/'boundary-cost.json').read_text())
    mark(range(old['first_packet_bank'],old['first_packet_bank']+old['added_banks']),'initial-boundary-packets')
    game=json.loads((bundle/'game-resources.json').read_text())['banks']
    for key in ('GAME_NATIVE_BANK','PLAYER_DATA_BANK','GAME_AUDIO_BANK','GAME_RESOURCE_BANK'):
        mark([game[key]],key)
    for key in ('terrain_banks','map_banks','edge_banks'):
        mark(metadata[key],'world-edge-tables-transfer-code-and-cold-streams' if packed and key=='edge_banks' else key)
    if not packed:mark(families['boundary']['banks'],'world-boundary-transfer-programs')
    for key in ('SESSION_IMAGE_BANK','SESSION_DATA_BANK','SESSION_BANK','SESSION_COLD_BANK','SESSION_DECOR_BANK','SESSION_BOOT_BANK'):
        mark([metadata['banks'][key]],key)
    if not packed:mark(cold_banks,'cold-startup-replay-streams')
    expected=set(range(len(rom)//BANK_BYTES))
    if set(owners)!=expected:raise ValueError(f'Unclassified banks: {sorted(expected-set(owners))}')
    counts=Counter(owners.values())
    return [dict(category=name,banks=count,bytes=count*BANK_BYTES,
                 bank_numbers=sorted(bank for bank,owner in owners.items() if owner==name))
            for name,count in sorted(counts.items())]


def audit(rom, bundle):
    if not rom or len(rom) % BANK_BYTES:
        raise ValueError('Expected a complete bank-aligned ROM')
    metadata = json.loads((bundle/'session-build.json').read_text())
    program_meta = json.loads((bundle/'hud-programs.json').read_text())
    packing_path=bundle/'rom-packing.json'
    packing=json.loads(packing_path.read_text()) if packing_path.exists() else None
    packed=bool(packing and packing.get('mode')=='same-bank-table-alias')
    if not program_meta.get('boundary_programs'):
        raise ValueError('Expected the maintained full-session compiled graphics bundle')
    syms = program_meta['linked_symbols']
    programs = {}
    refs = defaultdict(list)
    full_costs = {}
    counts = {}
    def pointer(bank, offset, family, key):
        at = bank*BANK_BYTES+offset
        target, lo, hi = rom[at:at+3]
        if not target:
            return None
        address = lo+256*hi
        identity = (target, address)
        if identity not in programs:
            programs[identity] = decode_transfer(rom, target, address,
                exit_address=syms['hud_upload.done'], transfer_address=syms['GamePacketFast_Transfer'],
                inline_literals=not packed)
        refs[family].append(dict(key=key, program=identity))
        return identity
    for current in range(64):
        bank = 4+current
        count = rom[bank*BANK_BYTES+0x900]
        if not 0 < count <= 128:
            raise ValueError('Unexpected phase HUD tile count')
        counts[current] = count
        full_costs[current] = count*16*17+250
        for old in range(64):
            pointer(bank, 0x2600+old*3, 'hud', [old,current])
    for index, bank in enumerate(metadata['edge_banks']):
        for old in range(9):
            pointer(bank, 0x2900+old*3, 'boundary', [index//8,old,index%8])
    expected_relocations = {entry['offset'] for entry in program_meta['relocations']}
    actual_relocations = {at for program in programs.values() for at in program['relocations']}
    if actual_relocations != expected_relocations:
        raise ValueError(f'Unaccounted compiled relocations: missing={len(expected_relocations-actual_relocations)}, extra={len(actual_relocations-expected_relocations)}')
    families = {}
    for name, entries in refs.items():
        identities = {tuple(entry['program']) for entry in entries}
        selected = [programs[key] for key in sorted(identities)]
        bank_ids = sorted({p['bank'] for p in selected})
        families[name] = dict(pointer_references=len(entries), unique_programs=len(selected),
            banks=bank_ids, allocated_bytes=len(bank_ids)*BANK_BYTES,
            code_bytes=sum(p['code_bytes'] for p in selected), literal_bytes=sum(p['literal_bytes'] for p in selected),
            program_bytes=sum(p['total_bytes'] for p in selected),
            largest_program_bytes=max(p['total_bytes'] for p in selected))
    semantic = defaultdict(list)
    for key, program in programs.items():
        semantic[program['normalized_sha256']].append(key)
    semantic_duplicate_bytes = sum(sum(programs[key]['total_bytes'] for key in keys[1:])
                                   for keys in semantic.values() if len(keys)>1)
    policies = {}
    for name, predicate in (
            ('same_xy_parity', lambda old,current,p: (old%8-current%8)%2==0 and (old//8-current//8)%2==0),
            ('compiled_not_slower_than_full_estimate', lambda old,current,p: p['estimated_instruction_cycles']<=full_costs[current]),
            ('compiled_within_125_percent_of_full_estimate', lambda old,current,p: p['estimated_instruction_cycles']<=full_costs[current]*1.25)):
        kept = set(); fallback = 0
        for entry in refs['hud']:
            old,current = entry['key'];key=tuple(entry['program'])
            if predicate(old,current,programs[key]):kept.add(key)
            else:fallback+=1
        sizes = [programs[key]['total_bytes'] for key in sorted(kept)]
        policies[name] = dict(kept_unique_programs=len(kept),fallback_pairs=fallback,
            program_bytes=sum(sizes),next_fit_bank_bytes=next_fit(sizes),
            scope='Read-only storage model. Existing full-upload path preserves pixels; actual timing, cache selection and input workload require emulator measurement before adoption.')
    if packed:
        cold=replay_commands(rom,metadata,json.loads((bundle/'session-boot.json').read_text())) if metadata['banks'].get('SESSION_HARDWARE_CHECK') else None
        model=dict(applied=True,actual_image_bytes=len(rom),packing=packing,
                   original_boot_data_banks=cold['banks'] if cold else [],
                   scope='Applied table-alias layout. Transfer literal bytes count references to shared tables; family bank totals overlap and must not be added. Use the allocation ledger for whole-ROM ownership.')
    else:
        model=alias_model(rom,bundle,metadata,programs,refs,counts)
    hud_tiles=tile_statistics(rom,[(4+phase,0x100,0x500,count) for phase,count in counts.items()])
    edge_tiles=tile_statistics(rom,[(bank,pattern,color,rom[bank*BANK_BYTES+count])
        for bank in metadata['edge_banks'] for pattern,color,count in ((0xb00,0xd00,0xf00),(0x1100,0x1300,0x1500))])
    allocations=ownership(rom,metadata,families,model['original_boot_data_banks'],bundle,packed)
    report = dict(rom=inventory(rom), families=families,table_alias_model=model,
        allocation_ledger=allocations,allocation_total_bytes=sum(row['bytes'] for row in allocations),
        graphics_tiles=dict(hud=hud_tiles,world_boundaries=edge_tiles),
        compiled_programs_total=len(programs), compiled_relocations_checked=len(actual_relocations),
        semantic_duplicate_program_bytes=semantic_duplicate_bytes,
        policies=policies, hud_tile_counts=dict(min=min(counts.values()),max=max(counts.values())),
        phase_bank_bytes=64*BANK_BYTES,
        phase_legacy_left_atlas_bytes=64*(0x2201-0x1f00),
        phase_base_boundary_atlas_bytes=64*(0x1600-0xa00),
        limitations='No ROM changed. Whole-bank reservation, actual transfer code/literals and modeled policy savings are separate quantities. Code-cycle estimates omit complete-frame effects; full-copy estimates are existing selector heuristics, not measured deadline guarantees.')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'references/experiments/full-session')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit((args.cartridge_path(bundle)).read_bytes(),args.bundle)
    sources = [ROOT/'src/toolchain/msx/cartridge_size.py', Path(__file__)]
    sources += [source_path(name) for name in (
        'build.py', 'hud_programs.py', 'session_build.py', 'session_boot.py',
        'session_phase.py', 'game_ring_refresh.py', 'rom_pack.py', 'rom_pack_verify.py')]
    metadata = [args.bundle/name for name in (
        'session-build.json', 'hud-programs.json', 'ring-refresh.json',
        'session-boot.json', 'boundary-cost.json', 'game-resources.json')]
    result['provenance'] = dict(
        checkout=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in sources},
        bundle_metadata_sha256={path.name:hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in metadata})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('families','semantic_duplicate_program_bytes','policies','table_alias_model')},indent=2))


if __name__=='__main__':
    main()

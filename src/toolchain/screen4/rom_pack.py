"""Deterministic same-bank graphics-code and cold-stream allocation.

No graphics bytes are discarded, decoded at runtime or copied into new RAM.
Ranges are generator contracts, never guessed from runs of zero/FF bytes.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import json
from pathlib import Path

from hud_programs import compile_packet, transition_packet

BANK_BYTES = 16384


def free_ranges(protected):
    """Return the complement of declared live ranges, never guessed FF padding."""
    result = []
    cursor = 0
    for begin, end in sorted(protected):
        if not 0 <= begin <= end <= BANK_BYTES:
            raise ValueError('Invalid protected ROM range')
        if begin > cursor:
            result.append([cursor, begin])
        cursor = max(cursor, end)
    if cursor < BANK_BYTES:
        result.append([cursor, BANK_BYTES])
    return result


def phase_gaps(phase, ring):
    # Fixed resources and the actually assembled ring worker are both live.
    # A generator/layout change must update these contracts before reclaiming space.
    protected = [(0,0x901), (0xa00,0xf01), (0x1000,0x1501),
                 (0x1f00,0x2201), (0x2300,0x2300+505), (0x2600,0x26c0),
                 (0x2700,0x2980), (0x3800,0x3c00)]
    if 4+phase == ring['mapper_bank']:
        start = ring['entry']-0x8000
        protected.append((start,start+ring['bytes']))
    return free_ranges(protected)


def pack_transfers(image, bank, packets, tables, gaps):
    """Place unique code largest-first, returning exact pointers/relocations.

    image is banks.bin (resident bank zero excluded); gaps are consumed in place.
    Exhaustion is fatal, rather than silently selecting a slower fallback.
    """
    base = (bank-1)*BANK_BYTES
    if bank < 1 or base+BANK_BYTES > len(image):
        raise ValueError('Missing transfer source bank')
    previous = 0
    for begin,end in sorted(gaps):
        if not 0 <= begin <= end <= BANK_BYTES or begin < previous:
            raise ValueError('Invalid/overlapping transfer code holes')
        previous = end
    for _,address,raw in tables:
        # Aliasing is legal only after byte comparison in this exact mapped bank.
        # A matching table elsewhere cannot satisfy an immediate16-bit pointer.
        at = base+address-0x8000
        if not 0x8000 <= address or address+len(raw) > 0xc000 or image[at:at+len(raw)] != raw:
            raise ValueError('Transfer source table differs from the mapped bank')
        start = address-0x8000
        if any(begin < start+len(raw) and end > start for begin,end in gaps) and raw:
            raise ValueError('Transfer code hole overlaps its graphics source')
    payloads = {packet:compile_packet(packet,0x8000,back_address=0xc027,
                                     packed8=True,source_tables=tables) for packet in set(packets)}
    pointers = {}
    relocations = []
    code_bytes = 0
    for packet in sorted(payloads,key=lambda p:(-len(payloads[p][0]),p)):
        payload, relocs = payloads[packet]
        size = len(payload)
        choices = [(end-begin-size,i) for i,(begin,end) in enumerate(gaps) if end-begin >= size]
        if not choices:
            raise ValueError(f'No safe code space in graphics bank {bank}')
        _,index = min(choices)
        offset = gaps[index][0]
        gaps[index][0] += size
        image[base+offset:base+offset+size] = payload
        pointers[packet] = (bank,0x8000+offset)
        relocations.extend(dict(offset=base+offset+at,symbol=name) for at,name in relocs)
        code_bytes += size
    return pointers,relocations,code_bytes


def pack_hud(image, hud_data, active, out):
    ring = json.loads((Path(out)/'ring-refresh.json').read_text())
    relocations = []
    patches = {}
    holes = []
    code_bytes = programs = 0
    for current in range(64):
        bank = 4+current
        tables = [(0x300,0x8100,hud_data[current][0]),(0x4300,0x8500,hud_data[current][1])]
        packets = [transition_packet(hud_data[previous],hud_data[current],(0x300,0x4300),
                                    active[previous],active[current]) for previous in range(64)]
        gaps = phase_gaps(current,ring)
        pointers,relocs,used = pack_transfers(image,bank,packets,tables,gaps)
        relocations.extend(relocs)
        programs += len(pointers)
        code_bytes += used
        for previous,packet in enumerate(packets):
            target = (bank-1)*BANK_BYTES+0x2600+previous*3
            b,address = pointers[packet]
            image[target:target+3] = bytes((b,address&255,address>>8))
            patches.setdefault(packet,(b,address))
        holes.extend([bank,begin,end] for begin,end in gaps if end > begin)
    (Path(out)/'rom-packing.json').write_text(json.dumps(dict(
        mode='same-bank-table-alias',hud_code_bytes=code_bytes,hud_programs=programs,
        holes=holes,no_new_ram=True,no_new_active_instructions=True),indent=2)+'\n')
    return image,relocations,patches


def pack_replay(records, image, holes):
    """Encode existing boot commands into holes, preserving all frame entries.

    The existing opcodes 3/4 handle arbitrary chain addresses and same-bank
    literal pointers. Literal dictionaries reset at each fragment. At least
    four bytes are reserved for a chain even when a fragment ends a frame.
    """
    previous = {}
    for bank,begin,end in sorted(holes):
        if (not 1 <= bank <= len(image)//BANK_BYTES or not 0 <= begin < end <= BANK_BYTES or
                begin < previous.get(bank,0)):
            raise ValueError('Invalid/overlapping cold packing holes')
        previous[bank] = end
    segments = sorted(holes,key=lambda s:(-(s[2]-s[1]),s[0],s[1]))
    current = None
    used = encoded = chains = reuses = 0
    literals = {}
    pointers = {}
    chunks = []

    def write(data):
        nonlocal used,encoded
        bank,begin,_ = current
        at = (bank-1)*BANK_BYTES+begin+used
        image[at:at+len(data)] = data
        used += len(data)
        encoded += len(data)

    for frame,record in enumerate(records):
        data = record['data']
        at = 0
        while at < len(data):
            op = data[at]
            if op not in (0,1,2) or (op and at+4 > len(data)):
                raise ValueError('Unknown/truncated raw boot command')
            size = 1 if op == 0 else 5 if op == 2 else 4+(data[at+3] or 256)
            if at+size > len(data) or (op == 0 and at+1 != len(data)):
                raise ValueError('Truncated or unterminated raw boot frame')
            raw = data[at+4:at+size] if op == 1 else None
            reused = raw is not None and len(raw)>2 and raw in literals
            wire_size = 6 if reused else size
            if current is None or used+wire_size+4 > current[2]-current[1]:
                candidates = [(i,s) for i,s in enumerate(segments) if s[2]-s[1] >= size+4]
                if not candidates:
                    raise ValueError('Cold boot does not fit reserved graphics-bank holes')
                index,next_segment = candidates[0]
                segments.pop(index)
                if current is not None:
                    bank,begin,_ = next_segment
                    address = 0x8000+begin
                    write(bytes((3,bank,address&255,address>>8)))
                    chains += 1
                current = next_segment
                used = 0
                literals = {}
                reused = False
                chunks.append(list(current))
            if at == 0:
                pointers[frame] = (current[0],0x8000+current[1]+used)
            if reused:
                pointer = literals[raw]
                write(bytes((4,data[at+1],data[at+2],data[at+3],pointer&255,pointer>>8)))
                reuses += 1
            else:
                if raw is not None:
                    literals.setdefault(raw,0x8000+current[1]+used+4)
                write(data[at:at+size])
            at += size
        if not data or op != 0:
            raise ValueError('Unterminated raw boot frame')
    return pointers,dict(encoded_bytes=encoded,chains=chains,chunks=chunks,literal_reuses=reuses)

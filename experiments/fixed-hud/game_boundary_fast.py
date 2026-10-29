"""Exact phase-local boundary-atlas transition packets for the SCREEN4 lab.

Append after HUD transition pages and before native gameplay resource pages.
All source-derived atlas bytes remain inside the caller's ignored output tree.
"""
import hashlib
import json
from pathlib import Path

BANK_BYTES = 16384
PHASE_BANK_FIRST = 3  # Zero-based index in banks.bin, which excludes resident.
POINTER_OFFSET = 0x2900
ARRAYS = ((0x0b00, 0x0f00, 0x0500), (0x0d00, 0x0f00, 0x4500),
          (0x1100, 0x1500, 0x0680), (0x1300, 0x1500, 0x4680))


def atlas_arrays(banks, phase):
    offset = (PHASE_BANK_FIRST+phase)*BANK_BYTES
    page = banks[offset:offset+BANK_BYTES]
    assert len(page) == BANK_BYTES, 'Missing complete phase bank'
    arrays = []
    for source, count_at, destination in ARRAYS:
        count = page[count_at]
        assert count <= 48, 'Boundary dictionary exceeds its character range'
        arrays.append(bytes(page[source:source+count*8]))
    return tuple(arrays)


def packet(previous, current):
    """Emit bounded exact writes; absent previous tails always require writes."""
    result = bytearray()
    for (_, _, base), old, new in zip(ARRAYS, previous, current):
        changed = [i for i, value in enumerate(new) if i >= len(old) or old[i] != value]
        cursor = 0
        while cursor < len(changed):
            start = changed[cursor]
            end = start+1
            cursor += 1
            while cursor < len(changed) and changed[cursor]-end <= 12 and changed[cursor]-start < 255:
                end = changed[cursor]+1
                cursor += 1
            at = base+start
            result.extend((at & 255, at >> 8, end-start))
            result.extend(new[start:end])
    result.extend((0, 0, 0))
    return bytes(result)


def packet_cost(data):
    cursor = payload = spans = 0
    while data[cursor+2]:
        length = data[cursor+2]
        payload += length
        spans += 1
        cursor += 3+length
    assert cursor+3 == len(data)
    return dict(payload_bytes=payload, spans=spans, packet_bytes=len(data))


def append_packets(banks, out):
    """Return copied/extended banks and write boundary-cost.json to out."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    assert len(banks) % BANK_BYTES == 0, 'Input banks must be complete ROM pages'
    result = bytearray(banks)
    source_sha = hashlib.sha256(result).hexdigest()
    atlases = [atlas_arrays(result, fx) for fx in range(8)]
    for phase in range(64):
        assert atlas_arrays(result, phase) == atlases[phase & 7], 'Boundary atlas unexpectedly depends on FY'
        at = (PHASE_BANK_FIRST+phase)*BANK_BYTES+POINTER_OFFSET
        assert all(value in (0, 255) for value in result[at:at+27]), 'Boundary pointer table overlaps existing phase data'
    first_bank = len(result)//BANK_BYTES+1
    page = bytearray()
    unique = {}
    pointers = {}
    transitions = {}
    for previous in range(9):
        old = atlases[previous] if previous < 8 else (b'',)*4
        for current in range(8):
            data = packet(old, atlases[current])
            if data not in unique:
                if len(page)+len(data) > BANK_BYTES:
                    result.extend(page.ljust(BANK_BYTES, b'\xff'))
                    page = bytearray()
                bank = len(result)//BANK_BYTES+1
                assert bank < 256, 'Boundary packets exceed ASCII16 mapper capacity'
                unique[data] = (bank, 0x8000+len(page))
                page.extend(data)
            bank, address = unique[data]
            pointers[previous, current] = bytes((bank, address & 255, address >> 8))
            cost = packet_cost(data)
            cost['full_payload_bytes'] = sum(map(len, atlases[current]))
            cost['saved_payload_bytes'] = cost['full_payload_bytes']-cost['payload_bytes']
            transitions[f'{previous}->{current}'] = cost
    if page:
        result.extend(page.ljust(BANK_BYTES, b'\xff'))
    for phase in range(64):
        at = (PHASE_BANK_FIRST+phase)*BANK_BYTES+POINTER_OFFSET
        for previous in range(9):
            result[at+previous*3:at+previous*3+3] = pointers[previous, phase & 7]
    report = dict(complete=True, phases_checked=64, transitions=72,
                  pointer_offset=POINTER_OFFSET, mapper_bank_numbers='One-based banks.bin page indices; resident ROM is mapper bank0',
                  first_packet_bank=first_bank, added_banks=(len(result)-len(banks))//BANK_BYTES,
                  unique_packets=len(unique), unique_packet_bytes=sum(map(len, unique)),
                  input_banks_sha256=source_sha, output_banks_sha256=hashlib.sha256(result).hexdigest(),
                  costs=transitions,
                  scope='Exact four current live pattern/color atlas arrays; all FY phases identical for an FX. Unknown prior FX8 forces complete active-byte writes. ROM packets never cross a16KiB page; writes are at most255 bytes. Transfer byte counts only; no measured CPU/gameplay/scanout claim.')
    (out/'boundary-cost.json').write_text(json.dumps(report, indent=2)+'\n')
    return result

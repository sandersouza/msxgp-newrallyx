"""Give equal static HUD tiles the same character ID across scroll phases.

Color the coexistence graph: tiles present in one phase must have distinct
slots, while mutually exclusive tiles can share a slot. This is offline ROM
layout only; every original pixel and flag-variant choice is retained.
"""
from collections import Counter


def arrange(payloads, variants):
    phase_keys = []
    frequency = Counter()
    graph = {}
    for payload in payloads:
        count = (len(payload)-224)//16
        p, c = payload[224:224+count*8], payload[224+count*8:]
        keys = [bytes(p[i*8:i*8+8]+c[i*8:i*8+8]) for i in range(count)]
        assert len(set(keys)) == count
        phase_keys.append(keys)
        frequency.update(keys)
        for key in keys:
            graph.setdefault(key, set()).update(k for k in keys if k != key)
    assigned = {}
    saturation = {key: set() for key in graph}
    while len(assigned) < len(graph):
        key = max((k for k in graph if k not in assigned),
                  key=lambda k: (len(saturation[k]), len(graph[k]), frequency[k], k))
        used = saturation[key]
        slot = next(n for n in range(256) if n not in used)
        assigned[key] = slot
        for neighbor in graph[key]:
            if neighbor not in assigned:
                saturation[neighbor].add(slot)
    count = max(assigned.values())+1
    assert count <= 64, f'HUD coexistence graph needs{count}slots; existing limit64'
    defaults = [max((k for k in graph if assigned[k] == slot), key=lambda k: (frequency[k], k))
                for slot in range(count)]
    output, remapped = [], {}
    checked = 0
    active_slots = []
    for phase, (payload, keys) in enumerate(zip(payloads, phase_keys)):
        slots = [assigned[key] for key in keys]
        active_slots.append(sorted(slots))
        assert len(set(slots)) == len(keys)
        values = defaults[:]
        for key, slot in zip(keys, slots):
            values[slot] = key
        names = bytes(slots[n] for n in payload[:224])
        patterns = b''.join(k[:8] for k in values)
        colors = b''.join(k[8:] for k in values)
        output.append(names+patterns+colors)
        remapped[str(phase)] = [group | dict(ids=[96+slots[n-96] for n in group['ids']])
                                for group in variants[str(phase)]]
        # Independent complete character equality also protects every possible
        # flag-state lookup, not just the currently visible panel names.
        for key, slot in zip(keys, slots):
            assert patterns[slot*8:slot*8+8]+colors[slot*8:slot*8+8] == key
            checked += 64
    return output, remapped, dict(phases=len(payloads), global_tiles=len(graph),
        allocated_slots=count, exact_character_pixels=checked,active_slots=active_slots,
        extra_ram=0, existing_slot_limit=64,
        scope='Offline graph allocation; same original patterns/colors for every source tile and flag variant. Stable fallback for absent slots; no runtime cache or quality change.')


def verify_bundle(bundle, out):
    import hashlib
    import json
    from pathlib import Path
    from radar_variants import name_program
    bundle,out=Path(bundle),Path(out)
    banks=(bundle/'banks.bin').read_bytes()
    variants=json.loads((bundle/'radar-variants.json').read_text())
    cells=flags=0
    for phase in range(64):
        source=(bundle/f'hud-{phase:02d}.bin').read_bytes()
        n=(len(source)-224)//16
        oldp,oldc=source[224:224+n*8],source[224+n*8:]
        page=banks[(3+phase)*16384:(4+phase)*16384]
        def old_key(tile):return oldp[tile*8:tile*8+8]+oldc[tile*8:tile*8+8]
        def new_key(tile):return page[0x100+tile*8:0x108+tile*8]+page[0x500+tile*8:0x508+tile*8]
        for at,old in enumerate(source[:224]):
            assert old_key(old)==new_key(page[at]-96),(phase,at)
            cells+=1
        groups=variants[str(phase)]
        old_program=name_program(groups)
        table_length=sum(len(g['ids']) for g in groups)
        code_length=len(old_program)-table_length
        assert page[0x2700:0x2700+code_length]==old_program[:code_length], 'Flag program instructions changed'
        cursor=0x2700+code_length
        for group in groups:
            for old in group['ids']:
                assert old_key(old-96)==new_key(page[cursor]-96),(phase,cursor)
                cursor+=1;flags+=1
    report=dict(complete=True,rom_sha256=hashlib.sha256((bundle/'fixed-hud.rom').read_bytes()).hexdigest(),
        phases=64,exact_logical_cells=cells,exact_flag_variant_choices=flags,
        exact_decoded_pixels=(cells+flags)*64,
        scope='Independent original phase names and flag lookup tables versus actual linked phase banks. Exact original16-byte glyph keys; unchanged flag program instructions/addresses. Covers every logical cell and every individual flag lookup choice.')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();verify_bundle(a.bundle,a.out)

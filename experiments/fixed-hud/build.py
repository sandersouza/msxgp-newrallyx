"""Assemble the isolated cartridge using local contributor-derived assets."""
import json
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import os
from collections import Counter
from prepare import OUT, ROOT, prepare, encode_tile
from scripts.msx.raster_scroll import palette_rgb
from edge import edge_tiles


def decode(pattern, colors):
    return bytes(colors[y]>>4 if pattern[y] & (128>>x) else colors[y]&15
                 for y in range(8) for x in range(8))


def boundary(source, hud, keep, rgb):
    """Preserve every HUD pixel; apply authorized two-color adaptation to scenery."""
    result=bytearray()
    for y in range(8):
        scenery=source[y*8:y*8+keep]
        fixed=hud[y*8+keep:y*8+8]
        colors=sorted(set(fixed))
        if len(colors)>2: raise ValueError('HUD itself exceeds SCREEN 4 color limit')
        if len(colors)<2:
            candidates=Counter(c for c in scenery if c not in colors)
            if candidates: colors.append(candidates.most_common(1)[0][0])
        selected=bytes(c if c in colors else min(colors,key=lambda k:
            sum((a-b)**2 for a,b in zip(rgb[c],rgb[k]))) for c in scenery)
        result.extend(selected+fixed)
    return encode_tile(result)

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--high-score',type=int,default=20000)
parser.add_argument('--score',type=int,default=0)
parser.add_argument('--round-number',type=int,default=1)
parser.add_argument('--lives',type=int,default=4)
parser.add_argument('--gameplay',action='store_true')
parser.add_argument('--full-session',action='store_true',help='Shared production sessions/rules with the optimized presenter')
parser.add_argument('--enemies',type=int,choices=(1,3,7),default=1)
parser.add_argument('--legacy-render',action='store_true',help='Matched graphics baseline for diagnostics only')
options=vars(parser.parse_args())
gameplay=options.pop('gameplay')
full_session=options.pop('full_session')
test_mode=int(os.environ.get('NRX_TEST_MODE','0')) if full_session else 0
if test_mode not in (0,1):parser.error('TEST_MODE must be0 or1')
gameplay=gameplay or full_session
enemies=options.pop('enemies')
legacy_render=options.pop('legacy_render')
if full_session and legacy_render:
    parser.error('--full-session requires the optimized presenter; --legacy-render is a first-stage diagnostic')
if gameplay:
    import prepare as preparation
    variant=(('full-session-test' if test_mode else 'full-session')+('-hud-classic' if os.environ.get('NRX_HUD_VARIANT','compact')=='classic' else '')+('-no-logo' if os.environ.get('NRX_MSX_LOGO','1')=='0' else '')+('-no-check' if os.environ.get('NRX_HARDWARE_CHECK','1')=='0' else '')) if full_session else 'stage-one'+(f'-{enemies}-enemies' if enemies!=1 else '')+('-baseline' if legacy_render else '')
    OUT=ROOT/'references/experiments'/variant
    preparation.OUT=OUT
from hud_module import selected as selected_hud
hud_module=selected_hud() if full_session else None
prepare(**options,arcade=full_session,small_round=bool(hud_module and hud_module['small_round']),symmetric_gauge=bool(hud_module and hud_module['symmetric_gauge']))
if hud_module:(OUT/'hud-module.json').write_text(json.dumps(hud_module,indent=2)+'\n')
if gameplay:
    import game_build
    game_build.prepare_inputs(ROOT,OUT,full_session=full_session)
hud_base=96 if gameplay else 64
hud_vram=hud_base*8
names_address=0xd400 if gameplay else 0xc400
report=json.loads((OUT/'prepare.json').read_text())
assert report['scenery_tiles']<=64, 'Scenery overlaps the HUD character slots'
terrain=(OUT/'terrain-patterns.bin').read_bytes()+(OUT/'terrain-colors.bin').read_bytes()
banks=bytearray(terrain.ljust(16384,b'\xff'))
banks.extend((OUT/'map.bin').read_bytes())
rgb=palette_rgb((OUT/'palette.bin').read_bytes())
terrain_pixels=[decode(terrain[i*8:i*8+8],terrain[2048+i*8:2056+i*8])
                for i in range(report['scenery_tiles'])]
hud_data=[]
hud_payloads=[(OUT/f'hud-{phase:02d}.bin').read_bytes() for phase in range(64)]
hud_active=None
hud_variants=json.loads((OUT/'radar-variants.json').read_text()) if gameplay else None
if gameplay and not legacy_render:
    from hud_tile_layout import arrange as arrange_hud_tiles
    hud_payloads,hud_variants,layout_report=arrange_hud_tiles(hud_payloads,hud_variants)
    hud_active=list(map(set,layout_report['active_slots']))
    (OUT/'hud-layout.json').write_text(json.dumps(layout_report,indent=2)+'\n')
stable_edges = None
if gameplay and not legacy_render:
    from game_boundary_stable import family as stable_boundary_family
    stable_edges = [stable_boundary_family(terrain_pixels, which, slot)
                    for which, slot in ((0, 160), (1, 208))]
for phase in range(64):
    payload=hud_payloads[phase]
    names=bytes(n+hud_base for n in payload[:224])
    count=(len(payload)-224)//16
    assert count<=(64 if gameplay else 128), 'HUD overlaps the boundary character slots'
    hud_data.append((payload[224:224+count*8],payload[224+count*8:]))
    bank=names.ljust(256,b'\0')+payload[224:224+count*8].ljust(1024,b'\0')
    bank+=payload[224+count*8:].ljust(1024,b'\0')+bytes([count])
    fx=phase%8
    bank=bytearray(bank.ljust(0x1600 if gameplay else 0x1200,b'\0'))
    # Two static atlases: scenery-only tile 24 and scenery/black tile 25.
    # HUD content is a full eight pixels away from the mixed tile.
    atlases=((0,160,0xa00,0xb00,0xd00,0xf00),
             (1,208,0x1000,0x1100,0x1300,0x1500)) if gameplay else (
             (0,192,0xa00,0xb00,0xc00,0xd00),
             (1,220,0xe00,0xf00,0x1000,0x1100))
    for which,slot,lut,pg,ct,length_at in atlases:
        dictionary={}; ids=bytearray(); patterns=bytearray(); colors=bytearray()
        for source in terrain_pixels:
            p,c=encode_tile(edge_tiles(source,fx)[which])
            key=p+c
            if key not in dictionary:
                dictionary[key]=slot+len(dictionary)
                patterns.extend(p);colors.extend(c)
            ids.append(dictionary[key])
        if stable_edges is not None:
            ids, patterns, colors, stable_count = stable_edges[which][fx]
            dictionary = dict.fromkeys(range(stable_count))
        assert len(dictionary)<=(48 if gameplay else 28), 'Edge atlas exceeds its character allocation'
        bank[lut:lut+len(ids)]=ids
        size=512 if gameplay else 256
        bank[pg:pg+size]=patterns.ljust(size,b'\0')
        bank[ct:ct+size]=colors.ljust(size,b'\0')
        bank[length_at]=len(dictionary)
    # Legacy R18 diagnostic data, retained in ROM only. It is never uploaded by
    # the R26/R27 renderer and does not reserve VRAM character slots 192..239.
    left_ids=bytearray(); left_patterns=bytearray(); left_colors=bytearray(); unique={}
    for source in terrain_pixels:
        reversed_source=bytes(source[y*8+7-x] for y in range(8) for x in range(8))
        if fx:
            p,c=boundary(reversed_source,bytes([11])*64,8-fx,rgb)
            p=bytes(int(f'{v:08b}'[::-1],2) for v in p)
        else:
            p,c=encode_tile(source)
        key=p+c
        if key not in unique:
            unique[key]=192+len(unique);left_patterns.extend(p);left_colors.extend(c)
        left_ids.append(unique[key])
    bank=bank.ljust(0x2201,b'\0')
    bank[0x1f00:0x1f00+len(left_ids)]=left_ids
    bank[0x2000:0x2100]=left_patterns[:256].ljust(256,b'\0')
    bank[0x2100:0x2200]=left_colors[:256].ljust(256,b'\0')
    bank[0x2200]=len(unique)
    assert len(unique)<=48, 'Legacy left-edge atlas exceeds its ROM allocation'
    # Compile six HUD names per row into direct Z80 word stores.
    code=bytearray()
    for row in range(28):
        for column in (0,2,4):
            address=names_address+row*32+26+column
            code.extend((0x21,names[row*7+column],names[row*7+column+1],
                         0x22,address&255,address>>8))
    code.append(0xc9)
    bank=bank.ljust(0x26c0,b'\0')
    bank[0x2300:0x2300+len(code)]=code
    if gameplay:
        from radar_variants import name_program
        groups=hud_variants[str(phase)]
        program=name_program(groups,names=names_address)
        bank=bank.ljust(0x2700+len(program),b'\0')
        bank[0x2700:0x2700+len(program)]=program
    banks.extend(bank.ljust(16384,b'\xff'))


def patch_packet(old,new,old_active=None,current_active=None):
    from hud_programs import transition_packet
    return transition_packet(old,new,(hud_vram,hud_vram+0x4000),old_active,current_active)


# Transition packets replace runtime comparisons/bit shifts. Every prior phase
# is supported, including abrupt reversal, diagonal movement and Shift changes.
patches={}; page=bytearray(); first_patch_bank=len(banks)//16384+1; fallback=0
hud_programs = gameplay and not legacy_render
program_relocations=[]
if hud_programs:
    from hud_programs import compile_packet
for current in range(64):
    allocated=0
    candidates=[(previous,patch_packet(hud_data[previous],hud_data[current],
        hud_active[previous] if hud_active else None,hud_active[current] if hud_active else None)) for previous in range(64)]
    candidates.sort(key=lambda item:(
        (current%8-item[0]%8)%8 not in (0,2,4,6) or (current//8-item[0]//8)%8 not in (0,2,4,6),
        len(item[1])))
    for previous,packet in candidates:
        target=(3+current)*16384+0x2600+previous*3
        if packet not in patches and allocated+len(packet)>(100000 if hud_programs else 40000):
            banks[target:target+3]=bytes(3);fallback+=1;continue
        if packet not in patches:
            payload, relocs = compile_packet(packet,0x8000,back_address=0xc027,packed8=full_session) if hud_programs else (packet, [])
            if len(page)+len(payload)>16384:
                banks.extend(page.ljust(16384,b'\xff'));page=bytearray()
                payload, relocs = compile_packet(packet,0x8000,back_address=0xc027,packed8=full_session) if hud_programs else (packet, [])
            elif hud_programs:
                payload, relocs = compile_packet(packet,0x8000+len(page),back_address=0xc027,packed8=full_session)
            bank_number=len(banks)//16384+1
            assert bank_number<256, 'Transition toolchain exceeds ASCII16 capacity'
            patches[packet]=(bank_number,0x8000+len(page))
            for offset,symbol in relocs:
                program_relocations.append(dict(offset=len(banks)+len(page)+offset,symbol=symbol))
            page.extend(payload)
            allocated+=len(payload)
        bank_number,address=patches[packet]
        banks[target:target+3]=bytes((bank_number,address&255,address>>8))
banks.extend(page.ljust(16384,b'\xff'))
if hud_programs:
    (OUT/'hud-programs.json').write_text(json.dumps(dict(programs=len(patches),
        relocations=program_relocations, no_new_ram=True,
        scope='Compiled exact HUD packets; direct short OUTI spans, shared R14 changes, resident burst helper for long spans; foreground only.'),indent=2)+'\n')
# Decode actual packed bank pointers independently. Poison unused previous slots
# to catch transitions that accidentally rely on an earlier, larger dictionary.
for current in range(64):
    for previous in range(64):
        pointer=(3+current)*16384+0x2600+previous*3
        bank_number,lo,hi=banks[pointer:pointer+3]
        memory=bytearray([0xee])*0x8000
        for base,data in zip((hud_vram,hud_vram+0x4000),hud_data[previous]):
            memory[base:base+len(data)]=data
        if bank_number and hud_programs:
            # Independently decode the original bounded writes; the compiled
            # program is validated separately against these exact transitions.
            from hud_programs import writes
            for destination,data in writes(patch_packet(hud_data[previous],hud_data[current],
                    hud_active[previous] if hud_active else None,hud_active[current] if hud_active else None)):
                memory[destination:destination+len(data)]=data
        elif bank_number:
            cursor=(bank_number-1)*16384+lo+hi*256-0x8000
            while True:
                lo,hi,length=banks[cursor:cursor+3];cursor+=3
                if not length: break
                destination=lo+hi*256
                assert hud_vram<=destination<hud_vram+1024 or hud_vram+0x4000<=destination<hud_vram+0x4400
                memory[destination:destination+length]=banks[cursor:cursor+length]
                cursor+=length
        else:
            base=(3+current)*16384
            count=banks[base+0x900]*8
            memory[hud_vram:hud_vram+count]=banks[base+0x100:base+0x100+count]
            memory[hud_vram+0x4000:hud_vram+0x4000+count]=banks[base+0x500:base+0x500+count]
        for base,data in zip((hud_vram,hud_vram+0x4000),hud_data[current]):
            for i,value in enumerate(data):
                if hud_active is None or i//8 in hud_active[current]:
                    assert memory[base+i]==value,(previous,current,i)
(OUT/'transition-cost.json').write_text(json.dumps(dict(rom_banks=1+len(banks)//16384,
    unique_packets=len(patches),first_patch_bank=first_patch_bank,
    packet_bytes=sum(len(p) for p in patches),full_upload_fallbacks=fallback,
    transitions_checked=4096),indent=2)+'\n')
if gameplay:
    from game_boundary_fast import append_packets as append_boundary_packets
    banks=append_boundary_packets(banks,OUT)
    if not legacy_render:
        from game_radar_source_cache import append_metadata as append_radar_metadata
        banks=append_radar_metadata(banks,OUT)
        from game_ring_refresh import append_worker as append_ring_refresh
        banks=append_ring_refresh(banks,ROOT,OUT,names_base=0x0800 if full_session else 0x2000)
    banks=game_build.append_resources(ROOT,OUT,banks,enemies=enemies,legacy_render=legacy_render,full_session=full_session)
(OUT/'banks.bin').write_bytes(banks)
(OUT/'radar-x.bin').write_bytes(bytes(8+(x+100)*32//816 for x in range(617)))
(OUT/'radar-y.bin').write_bytes(bytes(70+(y+106)*106//1392 for y in range(1181)))
shutil.copyfile(Path(__file__).with_name('lab.asm'), OUT/'lab.asm')
if gameplay:
    text=game_build.renderer_source((OUT/'lab.asm').read_text(),phase_cache=not legacy_render)
    if full_session:
        from session_build import renderer_source as full_renderer_source
        text=full_renderer_source(text,OUT)
    (OUT/'lab.asm').write_text(text)
shutil.copyfile(Path(__file__).with_name('ring.inc'), OUT/'ring.inc')
with tempfile.TemporaryDirectory(prefix='.assemble-',dir=OUT) as temporary:
    assembly=Path(temporary)
    for name in ('lab.asm','ring.inc','palette.bin','radar-x.bin','radar-y.bin'):
        shutil.copyfile(OUT/name,assembly/name)
    if gameplay:
        game_build.copy_sources(ROOT,OUT,assembly)
    subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo',
                    '--sym=lab.sym', '--lst=lab.lst', 'lab.asm'],cwd=assembly,check=True)
    rom=assembly/'fixed-hud.rom'
    if gameplay:
        banks=game_build.finalize_banks(assembly,OUT,banks)
    resident=rom.read_bytes()
    assert len(resident)==16384
    rom.write_bytes(resident+banks)
    for name in ('lab.sym','lab.lst'):
        shutil.copyfile(assembly/name,OUT/name)
    rom.replace(OUT/'fixed-hud.rom')
print(OUT/'fixed-hud.rom')

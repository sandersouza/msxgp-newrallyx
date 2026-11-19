"""Produce a standalone512KiB ASCII8 diagnostic of the current RAM backend.

Embedded-resource provider replaces only stopped filesystem transport. This
does not prove DOS/BASIC I/O and requires512KiB main RAM; keep64KiB ROM intact.
Contributor-derived payloads remain ignored; no release or default publication.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from compact_game_build import symbols,replace
from disk_package import compress_bank,decompress_bank

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'references/build/game-mapper512-testrom'
DIST=ROOT/'dist/experimental/mapper512'


def build():
    base=ROOT/'references/build/game-mapper512-game';plan=json.loads((base/'plan.json').read_text())
    OUT.mkdir(exist_ok=True,parents=True)
    for n in ['cold-layout.inc','cold-mode.inc','game-bindings.inc','game-objects.inc','mapper512-game-bridge.inc']:
        shutil.copyfile(base/n,OUT/n)
    text=(ROOT/'src/disk/mapper512-cold.asm').read_text()
    text=replace(text,'.bdos:\n    ld (Cold_Bdos+1),hl','.bdos:\n    ld hl,Mapper512_RomBdos\n    ld (Cold_Bdos+1),hl')
    text=replace(text,'Cold_CodeEnd:', '    INCLUDE "mapper512-rom-bdos.inc"\nCold_CodeEnd:')
    (OUT/'mapper512-cold.asm').write_text(text)
    shutil.copyfile(ROOT/'src/disk/mapper512-rom-bdos.inc',OUT/'mapper512-rom-bdos.inc')
    shutil.copyfile(ROOT/'src/disk/mapper512-testrom.asm',OUT/'mapper512-testrom.asm')
    # Reuse the same bounded authored LZ decoder; no original assets in source.
    original=(ROOT/'src/disk/mapper512-cold.asm').read_text()
    decoder=original[original.index('Cold_Decode:'):original.index('Cold_Mode:')].replace('Cold_','Boot_')
    (OUT/'boot-decoder.inc').write_text(decoder)
    assembler=ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'
    def assemble(name):
        p=subprocess.run([str(assembler),'--nologo',f'--sym={name}.sym',name],cwd=OUT,capture_output=True,text=True)
        if p.returncode:raise RuntimeError((p.stdout+p.stderr)[-2200:])
    # Link the thunk first, then bridge against its fixed addresses. Compressed
    # bridge resides in bank0; the bootstrap occupies final-file padding.
    resource=(base/'files/NRX512.DAT').read_bytes();end=8192+len(resource)
    (OUT/'rom-config.inc').write_text(f'ROM_TAIL_BANK EQU {end//8192}\nROM_TAIL_ADDRESS EQU {0x8000+end%8192}\n')
    (OUT/'bridge-packed.bin').write_bytes(b'\0')
    assemble('mapper512-testrom.asm')
    syms=symbols(OUT/'mapper512-testrom.asm.sym')
    names=[n for n in syms if n.startswith('ROMIO')]
    binding='\n'.join(f'{n} EQU {syms[n]}' for n in names if '.' not in n)+'\n'
    (OUT/'rom-api.inc').write_text(binding)
    p=OUT/'mapper512-cold.asm';p.write_text('    INCLUDE "rom-api.inc"\n'+p.read_text())
    assemble('mapper512-cold.asm')
    bridge=(OUT/'cold.bin').read_bytes();image=bytes(4096)+bridge+bytes(16384-4096-len(bridge))
    packed=compress_bank(image);assert decompress_bank(packed)==image
    (OUT/'bridge-packed.bin').write_bytes(packed);assemble('mapper512-testrom.asm')
    # Only PackedBridge's length changes in bank0; Page3 ABI must stay fixed.
    linked=symbols(OUT/'mapper512-testrom.asm.sym');assert all(linked[n]==syms[n] for n in names)
    boot=(OUT/'boot-image.bin').read_bytes();rom=(OUT/'rom-head.bin').read_bytes()+resource+boot
    assert len(rom)<=524288 and len(boot)<=8192-end%8192
    rom+=bytes([255])*(524288-len(rom));DIST.mkdir(parents=True,exist_ok=True)
    target=DIST/'newrallyx-512-test.rom';target.write_bytes(rom)
    result=dict(status='Experimental diagnostic only; no release',rom=str(target.relative_to(ROOT)),rom_sha256=hashlib.sha256(rom).hexdigest(),
        bytes=len(rom),mapper='ASCII8',minimum_mapper_ram_kib=512,minimum_standard_cartridge_ram_kib=64,
        minimum_vram_kib=128,reference_machine='MSX2+ Panasonic_FS-A1WSX, base Z80,512KiB main mapper',
        standard_rom='dist/newrallyx.rom',standard_rom_unchanged_sha256=hashlib.sha256((ROOT/'dist/newrallyx.rom').read_bytes()).hexdigest(),
        resource_sha256=plan['resource_sha256'],disk_bridge_sha256=plan['bridge_sha256'],rom_bridge_sha256=hashlib.sha256(bridge).hexdigest(),
        packed_bridge_bytes=len(packed),bootstrap_bytes=len(boot),scope='Current RAM-game code/data; embedded-resource cold transport. No DOS/BASIC filesystem or64KiB-only operation claim for this diagnostic.')
    (DIST/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result


if __name__=='__main__':build()

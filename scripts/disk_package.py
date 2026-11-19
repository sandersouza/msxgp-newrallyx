"""Build the expanded-mapper disk edition without modifying the cartridge.

Bank compression is a bounded LZ stream: literals 0..127 encode 1..128 bytes;
matches 128..255 encode 3..130 bytes followed by a little-endian distance.
Each bank resets its dictionary. All original-derived outputs remain ignored.
"""
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK_SIZE = 16384


def compress_bank(data):
    if len(data) != BANK_SIZE:
        raise ValueError('Expected one 16 KiB bank')
    result = bytearray()
    literal = bytearray()
    history = {}

    def flush():
        if literal:
            result.append(len(literal)-1)
            result.extend(literal)
            literal.clear()

    i = 0
    while i < len(data):
        key = data[i:i+3]
        best, distance = 0, 0
        for previous in reversed(history.get(key, [])[-8:]):
            count = 3
            while count < 130 and i+count < len(data) and data[previous+count] == data[i+count]:
                count += 1
            if count > best:
                best, distance = count, i-previous
        if len(key) < 3:
            best = 0
        advance = best if best >= 3 else 1
        if best >= 3:
            flush()
            result.append(128+best-3)
            result.extend(struct.pack('<H', distance))
        else:
            literal.append(data[i])
            if len(literal) == 128:
                flush()
        for position in range(i, i+advance):
            positions = history.setdefault(data[position:position+3], [])
            positions.append(position)
            if len(positions) > 8:
                del positions[0]
        i += advance
    flush()
    return bytes(result)


def decompress_bank(data):
    result = bytearray()
    cursor = 0
    while cursor < len(data):
        token = data[cursor]
        cursor += 1
        if token < 128:
            count = token+1
            if cursor+count > len(data):
                raise ValueError('Truncated literal')
            result.extend(data[cursor:cursor+count])
            cursor += count
        else:
            if cursor+2 > len(data):
                raise ValueError('Truncated match')
            distance = int.from_bytes(data[cursor:cursor+2], 'little')
            cursor += 2
            if not 0 < distance <= len(result):
                raise ValueError('Invalid match distance')
            for _ in range((token & 127)+3):
                result.append(result[-distance])
        if len(result) > BANK_SIZE:
            raise ValueError('Bank overflow')
    if len(result) != BANK_SIZE:
        raise ValueError('Incomplete bank')
    return bytes(result)


def mapper_source(text):
    return re.sub(r'(?im)^(\s*)ld\s+\(\$7000\),a\b', r'\1out ($fe),a', text)


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f'Disk adapter anchor changed: {before!r}')
    return text.replace(before, after, 1)


def link_payload(bundle, work):
    sys.path[:0] = [str(ROOT/'src/toolchain/screen4'), str(ROOT)]
    import game_build
    for source in bundle.iterdir():
        if source.is_file() and source.suffix in ('.inc', '.bin', '.json', '.asm'):
            shutil.copyfile(source, work/source.name)
    assembly = work/'assembly'
    assembly.mkdir()
    shutil.copyfile(work/'lab.asm',assembly/'lab.asm')
    game_build.copy_sources(ROOT, work, assembly)
    path = assembly/'game-main.inc'
    path.write_text(replace_once(path.read_text(), '    ld b,0\n.segment:',
                                '    ld b,250\n.segment:'))
    path = assembly/'modules/session/world.inc'
    path.write_text(replace_once(path.read_text(), '    xor a\n.segment:',
                                '    ld a,251\n.segment:'))
    changes = 0
    for path in list(assembly.rglob('*.inc')) + list(assembly.glob('*.asm')):
        before = path.read_text()
        after = mapper_source(before)
        changes += before.count('ld ($7000),a')
        path.write_text(after)
    # This preserved audio prefix is an already-linked authored worker. Its
    # absolute internal addresses require equal-size replacement instructions.
    path = assembly/'session-production-audio.bin'
    audio = bytearray(path.read_bytes())
    positions = [i for i in range(len(audio)) if audio[i:i+3] == b'\x32\x00\x70']
    if positions != [0x185a, 0x18b8, 0x190f, 0x1966]:
        raise ValueError('Preserved audio worker bank instructions changed')
    for position in positions:
        audio[position:position+3] = b'\xd3\xfe\x00'
    path.write_bytes(audio)
    subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo',
                    '--sym=lab.sym', '--lst=lab.lst', 'lab.asm'], cwd=assembly, check=True)
    banks = game_build.finalize_banks(assembly, work, bytearray((work/'banks.bin').read_bytes()))
    payload = (assembly/'newrallyx.rom').read_bytes() + banks
    shutil.copyfile(assembly/'lab.sym',work/'lab.sym')
    if len(payload) > 125*BANK_SIZE:
        raise ValueError('Disk bank reservation exceeded')
    return payload, changes+len(positions)


def build(bundle, output):
    output.mkdir(parents=True, exist_ok=True)
    cartridge = ROOT/'dist/newrallyx.rom'
    original = cartridge.read_bytes()
    if len((bundle/'newrallyx.rom').read_bytes())!=125*BANK_SIZE:
        raise ValueError('The system-mapper edition needs the complete16 KiB source link')
    with tempfile.TemporaryDirectory(prefix='disk-', dir=ROOT/'references/build') as temporary:
        work = Path(temporary)
        payload, switches = link_payload(bundle, work)
        archive_data = bytearray(b'NRXDSK1' + bytes([len(payload)//BANK_SIZE]))
        for i in range(0, len(payload), BANK_SIZE):
            bank = payload[i:i+BANK_SIZE]
            packed = compress_bank(bank)
            if decompress_bank(packed) != bank:
                raise ValueError('Compression verification failed')
            archive_data.extend(struct.pack('<HH', len(packed), sum(bank) & 65535))
            archive_data.extend(packed)
        (output/'NRALLYX.DAT').write_bytes(archive_data)
        shutil.copyfile(ROOT/'src/disk/loader.asm', work/'loader.asm')
        subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo',
                        '--sym=loader.sym', 'loader.asm'], cwd=work, check=True)
        loader = (work/'loader.bin').read_bytes()
        # COM relocates the same position-bound code used by BLOAD to C100.
        stub = b'\x21\x11\x01\x11\x00\xc1\x01' + struct.pack('<H',len(loader)) + b'\xed\xb0\xc3\x00\xc1\x00\x00\x00'
        (output/'NRALLYX.COM').write_bytes(stub+loader)
        (output/'NRALLYX.BIN').write_bytes(b'\xfe' + struct.pack('<HHH',0xc100,0xc100+len(loader)-1,0xc104) + loader)
        (output/'NRALLYX.BAS').write_bytes(b'10 CLEAR 200,&HC0FF\r\n20 BLOAD "NRALLYX.BIN",R\r\n\x1a')
        intermediate = ROOT/'references/build/game-disk'
        intermediate.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(work/'lab.sym', intermediate/'disk.sym')
        shutil.copyfile(work/'loader.sym', intermediate/'loader.sym')
        (intermediate/'disk-image.bin').write_bytes(payload)
    if cartridge.read_bytes() != original:
        raise ValueError('Normal cartridge changed during disk build')
    manifest = dict(source_rom_sha256=hashlib.sha256((bundle/'newrallyx.rom').read_bytes()).hexdigest(),
                    cartridge_rom_sha256=hashlib.sha256(original).hexdigest(),
                    disk_image_sha256=hashlib.sha256(payload).hexdigest(),
                    dos_com_sha256=hashlib.sha256((output/'NRALLYX.COM').read_bytes()).hexdigest(),
                    basic_bin_sha256=hashlib.sha256((output/'NRALLYX.BIN').read_bytes()).hexdigest(),
                    data_sha256=hashlib.sha256(archive_data).hexdigest(),
                    source_overlay='SOURCE/',
                    minimum_mapper_ram_kib=4096, banks=len(payload)//BANK_SIZE,
                    bank_instructions=switches, compressed_bytes=len(archive_data))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (output/'README.TXT').write_text(
        'New Rally-X - expanded RAM mapper disk edition\n\n'
        'Requires MSX2+/V9958, 128 KiB VRAM and 4 MiB standard mapper RAM\n'
        'in the main RAM slot. No MegaRAM or flash cartridge is required.\n'
        'Copy all NRALLYX.* files to one directory on your disk/SD/CF.\n'
        'MSX-DOS: run NRALLYX\n'
        'Disk BASIC: RUN "NRALLYX.BAS"\n'
        'Test shortcut: hold F10 (MSX Shift+F5) during ROM/RAM opening until the title, then release.\n'
        'Cars/rocks cannot kill in this mode; walls stay solid. Reset clears it.\n'
        'The loader reads the entire game before starting. Reset to exit.\n'
        'Boot with a clean mapper; resident software may prevent loading.\n'
        'The cartridge edition continues to support 64 KiB RAM.\n\n'
        'Rebuild: check out the source ROM release, supply your arcade ROMs,\n'
        'copy SOURCE/ into the checkout, then run:\n'
        'make -f Makefile -f src/disk/targets.mk build-disk\n'
        'No operating system files or BIOS are included in this package.\n')
    names = ['NRALLYX.COM','NRALLYX.BIN','NRALLYX.BAS','NRALLYX.DAT','README.TXT','manifest.json']
    sums = ''.join(f'{hashlib.sha256((output/n).read_bytes()).hexdigest()}  {n}\n' for n in names)
    (output/'SHA256SUMS').write_text(sums)
    with zipfile.ZipFile(output/'newrallyx-disk.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in names+['SHA256SUMS']:
            archive.write(output/name,name)
        for name in ('scripts/disk_package.py','scripts/verify_disk.py','src/disk/loader.asm',
                     'src/disk/targets.mk','tests/test_disk_package.py','docs/disk-executable.md',
                     'docs/measurements/timing/disk-executable.json'):
            archive.write(ROOT/name,'SOURCE/'+name)
    print(json.dumps(manifest,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'references/build/game')
    parser.add_argument('--output',type=Path,default=ROOT/'dist/disk')
    args = parser.parse_args()
    build(args.bundle.resolve(),args.output.resolve())

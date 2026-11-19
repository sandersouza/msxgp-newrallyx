"""Package the complete compact MegaRAM backend for DOS1 and Disk BASIC."""
import hashlib
import json
from pathlib import Path
import struct
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from disk_package import compress_bank,decompress_bank


def capacity(pages):
    """Round programmed8KiB pages to supported128/256/512/768/1024KiB tiers.

    Probe0, the first bank exposing the next address bit, and the tier's last
    bank. Sampling0/middle/last by arithmetic midpoint alone misses512K aliasing
    on a768K request: bank95 aliases31, not either of0/48.
    """
    if not 2<=pages<=128:raise ValueError('Expected2..128 programmed pages')
    kib=next(n for n in (128,256,512,768,1024) if n>=pages*8)
    banks=kib//8;middle=1<<((banks-1).bit_length()-1)
    return kib,middle,banks-1


def build(fixed_ram=False,publish=False):
    work=ROOT/'references/build'/('game-fixedram-megaram-runtime' if fixed_ram else 'game-compact-megaram-runtime')
    payload=(work/'newrallyx.rom').read_bytes()
    assert len(payload)%8192==0 and 16384<=len(payload)<1048576
    padded=payload.ljust((len(payload)+16383)//16384*16384,b'\xff')
    archive=bytearray(b'NRXMGR1'+bytes([len(payload)//8192]))
    for at in range(0,len(padded),16384):
        bank=padded[at:at+16384];compressed=compress_bank(bank)
        assert decompress_bank(compressed)==bank
        archive.extend(struct.pack('<HH',len(compressed),sum(bank)&65535));archive.extend(compressed)
    source=ROOT/'src/disk/megaram-loader.asm'
    shutil.copyfile(source,work/'megaram-loader.asm')
    required,middle,last=capacity(len(payload)//8192)
    (work/'megaram-layout.inc').write_text(f'EXPECTED_PAGES EQU {len(payload)//8192}\nMEGA_REQUIRED_KIB EQU {required}\nMEGA_PROBE_MIDDLE EQU {middle}\nMEGA_PROBE_LAST EQU {last}\n')
    result=subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),'--nologo','--sym=megaram-loader.sym','megaram-loader.asm'],cwd=work,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    loader=(work/'loader.bin').read_bytes()
    stub=b'\x21\x11\x01\x11\x00\xc1\x01'+struct.pack('<H',len(loader))+b'\xed\xb0\xc3\x00\xc1\0\0\0'
    out=ROOT/('dist/experimental/fixedram/megaram' if fixed_ram else 'dist/compact/megaram');out.mkdir(parents=True,exist_ok=True)
    (out/'NRXMEGA.COM').write_bytes(stub+loader)
    (out/'NRXMEGA.BIN').write_bytes(b'\xfe'+struct.pack('<HHH',0xc100,0xc100+len(loader)-1,0xc104)+loader)
    (out/'NRXMEGA.BAS').write_bytes(b'10 CLEAR 200,&HC0FF\r\n20 BLOAD "NRXMEGA.BIN",R\r\n\x1a')
    (out/'NRXMEGA.DAT').write_bytes(archive)
    ram_note='No standard RAM mapper is required.\n' if fixed_ram else 'Historical backend: standard RAM mapper required.\n'
    (out/'README.TXT').write_text(f'New Rally-X compact MegaRAM edition\n\nRequires MSX2+/128 KiB VRAM, 64 KiB main RAM and at least {required} KiB MegaRAM.\n'+ram_note+'MSX-DOS1: NRXMEGA\nDisk BASIC: RUN "NRXMEGA.BAS"\nKeep all NRXMEGA.* files together. Loader takes over the machine; reset to exit.\nTest shortcut: hold F10 (MSX Shift+F5) during ROM/RAM opening until the title, then release.\nCars/rocks cannot kill in this mode; walls stay solid. Reset clears it.\nNo BIOS or operating system files are included.\nPhysical hardware and subjective listening acceptance remain separate.\n')
    report=dict(programmed_bytes=len(payload),physical_padded_bytes=len(padded),pages_8k=len(payload)//8192,
        rom_sha256=hashlib.sha256(payload).hexdigest(),data_sha256=hashlib.sha256(archive).hexdigest(),
        minimum_main_ram_kib=64,minimum_mapper_ram_kib=0 if fixed_ram else 64,ram_mapper_required=not fixed_ram,
        minimum_megaram_kib=required,probe_banks=[0,middle,last],loader_bytes=len(loader),compressed_bytes=len(archive))
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    names=['NRXMEGA.COM','NRXMEGA.BIN','NRXMEGA.BAS','NRXMEGA.DAT','README.TXT','manifest.json']
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256((out/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in names))
    with zipfile.ZipFile(out/'newrallyx-megaram.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in names+['SHA256SUMS']:
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,(out/name).read_bytes())
    if publish:
        if not fixed_ram:raise ValueError('Default MegaRAM delivery must use fixed-RAM binding')
        target=ROOT/'dist/compact/megaram';target.mkdir(parents=True,exist_ok=True)
        for name in names+['SHA256SUMS','newrallyx-megaram.zip']:
            shutil.copyfile(out/name,target/name)
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--fixed-ram',action='store_true');p.add_argument('--publish',action='store_true');a=p.parse_args();build(a.fixed_ram,a.publish)

"""Read-only Issue41 inventory and storage probes; emits metadata, never a ROM.

Reuses the maintained transfer decoder and ownership contracts. Compression
figures include exact round-trip checks but exclude a target decoder/cache;
they are storage observations, not executable-cartridge size claims.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/toolchain/screen4'), str(ROOT)]
from rom_audit import audit


def investigate(bundle, rom_path):
    rom = rom_path.read_bytes()
    baseline = audit(rom, bundle)
    symbols = {n:int(v,16) for n,v in re.findall(
        r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)', (bundle/'lab.sym').read_text())}
    metadata = json.loads((bundle/'session-build.json').read_text())
    packing = json.loads((bundle/'rom-packing.json').read_text())
    terrain = (bundle/'terrain-patterns.bin').read_bytes() + (bundle/'terrain-colors.bin').read_bytes()
    assert len(terrain) == 4096 and rom[16384:20480] == terrain
    boot_bank = metadata['banks']['SESSION_BOOT_BANK']
    assert boot_bank == len(rom)//16384-1
    worker_bytes = symbols['GameSession_BootEnd']-symbols['GameSession_StartupWorkers']
    descriptor_bytes = symbols['GameSession_BootTableEnd']-symbols['GameSession_BootFrames']
    assert 0 < worker_bytes <= 4096 and 0 < descriptor_bytes <= 4096
    # Retain complete symbol-bounded regions, including meaningful final FF.
    prefix_bytes = 4096+descriptor_bytes
    source = rom[boot_bank*16384:boot_bank*16384+prefix_bytes]
    assert 4096+len(source) <= 16384
    simulated = bytearray(rom[16384:32768])
    simulated[4096:4096+len(source)] = source
    assert simulated[:4096] == terrain
    assert simulated[4096:4096+worker_bytes] == source[:worker_bytes]
    assert simulated[8192:8192+descriptor_bytes] == source[4096:]
    # This checks storage placement only: live bank/address constants still
    # require relinking and emulator proofs. No candidate image is published.
    compression = []
    for row in baseline['allocation_ledger']:
        total = 0
        for bank in row['bank_numbers']:
            raw = rom[bank*16384:(bank+1)*16384]
            packed = zlib.compress(raw,9)
            assert zlib.decompress(packed) == raw
            total += len(packed)
        compression.append(dict(category=row['category'],raw_bytes=row['bytes'],
                                host_zlib_bank_bytes=total))
    arcade_files = [p for p in (ROOT/'references/roms/nrallyx').iterdir() if p.is_file()]
    # Cartridge capacities use binary units. This is a layout-specific floor,
    # not an information-theoretic minimum for a redesigned renderer.
    fixed_hot_banks = 64 + len(metadata['edge_banks'])
    return dict(rom=baseline['rom'], allocation_ledger=baseline['allocation_ledger'],
        graphics_tiles=baseline['graphics_tiles'],
        semantic_duplicate_program_bytes=baseline['semantic_duplicate_program_bytes'],
        compiled_relocations_checked=baseline['compiled_relocations_checked'],
        compiled_programs=baseline['compiled_programs_total'],
        packed_transfer_code_bytes=packing['hud_code_bytes']+packing['boundary_code_bytes'],
        boot_stream_bytes=packing['boot']['encoded_bytes'],
        cold_bank_placement_probe=dict(source_bank=boot_bank,target_bank=1,
            target_offset=4096,worker_bytes=worker_bytes,descriptor_bytes=descriptor_bytes,
            retained_prefix_bytes=prefix_bytes,terrain_bytes_preserved=4096,
            storage_fit=True,potential_removed_bank_bytes=16384,
            projected_size_if_relinked=len(rom)-16384,
            status='Storage fit only; no linked candidate or runtime acceptance'),
        compression_probes=compression,
        compression_total=sum(r['host_zlib_bank_bytes'] for r in compression),
        exact_page_dictionary_probes={str(size):dict(
            page_count=len(rom)//size,
            unique_pages=len({rom[i:i+size] for i in range(0,len(rom),size)}),
            unique_payload_bytes=len({rom[i:i+size] for i in range(0,len(rom),size)})*size,
            scope='Host storage dictionary only; excludes indexing and runtime access cost')
            for size in (4096,8192)},
        smaller_cartridge_gate=dict(target_exclusive_bytes=1048576,
            maximum_16k_banks_below_target=63,
            banks_to_remove_from_current=125-63,
            minimum_saving_to_reach_63_banks=62*16384,
            current_fixed_hot_bank_count=fixed_hot_banks,
            fixed_layout_hot_bytes=fixed_hot_banks*16384,
            cold_only_repacking_cannot_reach_target=fixed_hot_banks*16384>=1048576,
            scope='Retaining current direct bank identities and addressing only; does not rule out a redesigned renderer/cache'),
        arcade_input_bytes=dict(total=sum(p.stat().st_size for p in arcade_files),
            program=sum(p.stat().st_size for p in arcade_files if 'prg' in p.name),
            graphics=sum(p.stat().st_size for p in arcade_files if 'chg' in p.name)),
        limitations='No ROM, symbols, graphics, audio, gameplay or timing changed. Fill tails are not proven free. Compression excludes decoder, metadata and runtime storage. Duplicate tile/program observations overlap existing bank ownership and are not additive savings.',
        provenance=dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        audit_source_sha256=hashlib.sha256((ROOT/'src/toolchain/screen4/rom_audit.py').read_bytes()).hexdigest()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'references/build/game')
    parser.add_argument('--rom',type=Path,default=ROOT/'references/build/game/newrallyx.rom')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/measurements/cartridge/issue41-inventory.json')
    args = parser.parse_args()
    result = investigate(args.bundle,args.rom)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('cold_bank_placement_probe','compression_total')},indent=2))

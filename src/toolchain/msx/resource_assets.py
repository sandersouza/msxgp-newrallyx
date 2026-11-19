"""Publish exact linked cartridge resources outside disposable build directories.

Bank images preserve the linker's interleaved graphics/audio/native-code layout;
these are not re-encoded pictures. The resident bank stays exclusively in dist/.
A compact manifest ties every retained bank byte to its final cartridge offset.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile


def publish(root, rom, configuration='default', *, bank_bytes=16384):
    root=Path(root).resolve()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',configuration):
        raise ValueError('Invalid resource configuration name')
    data=Path(rom).read_bytes()
    if bank_bytes not in (8192,16384) or not data or len(data)%bank_bytes or len(data)>2097152:
        raise ValueError('Expected complete8/16 KiB cartridge banks of at most2 MiB')
    first_resource=16384//bank_bytes
    parent=root/'assets/arcade/msx'
    if any(p.is_symlink() for p in (parent,*parent.parents)):
        raise ValueError('Resource output must not traverse symlinks')
    parent.mkdir(parents=True,exist_ok=True)
    target=parent/configuration
    if target.exists():
        if target.is_symlink():raise ValueError('Resource output is a symlink')
        manifest=json.loads((target/'manifest.json').read_text())
        if manifest.get('tool')!='newrallyx-linked-resources':raise ValueError('Unknown resource output')
        expected={'manifest.json'}|{f'bank-{i:03d}.bin' for i in range(manifest.get('first_resource_bank',1),manifest['bank_count'])}
        if {p.name for p in target.iterdir()}!=expected:raise ValueError('Unknown resource files')
        for entry in manifest['resources']:
            if entry['path'] not in expected or hashlib.sha256((target/entry['path']).read_bytes()).hexdigest()!=entry['sha256']:
                raise ValueError('Modified resource output; preserve it before rebuilding')
    with tempfile.TemporaryDirectory(prefix='.resources-',dir=parent) as temporary:
        staging=Path(temporary);resources=[]
        for i in range(first_resource,len(data)//bank_bytes):
            payload=data[i*bank_bytes:(i+1)*bank_bytes];name=f'bank-{i:03d}.bin'
            (staging/name).write_bytes(payload)
            resources.append(dict(path=name,rom_offset=i*bank_bytes,bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest()))
        manifest=dict(tool='newrallyx-linked-resources',configuration=configuration,
            rom_sha256=hashlib.sha256(data).hexdigest(),bank_count=len(data)//bank_bytes,bank_bytes=bank_bytes,first_resource_bank=first_resource,
            encoding=f'Exact final{bank_bytes}-byte resource banks, including interleaved native code and padding; resident16 KiB excluded',resources=resources)
        (staging/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        if target.exists():shutil.rmtree(target)
        staging.rename(target)
    return target

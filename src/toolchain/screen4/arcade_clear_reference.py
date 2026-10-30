"""Reproducible isolated original clear-cue capture; local contributor ROMs only."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib,json,os,shutil,subprocess
from pathlib import Path

def capture(root):
    from src.toolchain.graphics.roms import input_records,load_metadata,validate_roms
    root=Path(root);source=source_path('arcade-clear-audio.lua')
    seed=root/'assets/arcade/native/native-v1/video.bin';out=root/'references/cache/arcade-clear-audio';out.mkdir(parents=True,exist_ok=True)
    version=subprocess.check_output(['mame','-version'],text=True).strip();assert version.startswith('0.289 ')
    key=dict(emulator=version,script_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),seed_sha256=hashlib.sha256(seed.read_bytes()).hexdigest(),
        roms=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())))
    marker=out/'reference.json';old=json.loads(marker.read_text()) if marker.exists() else {}
    if old.get('inputs')!=key or not (out/'complete').exists() or not (out/'wsg.tsv').exists() or old.get('wsg_sha256')!=hashlib.sha256((out/'wsg.tsv').read_bytes()).hexdigest():
        shutil.copyfile(seed,out/'seed.bin')
        cmd=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),'-video','none','-sound','none',
            '-wavwrite',str(out/'arcade.wav'),'-samplerate','48000','-nothrottle','-noautosave','-skip_gameinfo','-autoboot_delay','0',
            '-autoboot_script',str(source),'-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-seconds_to_run','10']
        with (out/'mame.log').open('w') as log:subprocess.run(cmd,check=True,timeout=60,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,NRX_CLEAR_AUDIO_OUTPUT=str(out)))
    ticks=int((out/'complete').read_text());rows=[list(map(int,row.split())) for row in (out/'wsg.tsv').read_text().splitlines()]
    assert ticks==107 and any(any(r[2+21+5*c] for c in range(3)) for r in rows)
    result=dict(inputs=key,completion_call=ticks,nominal_arcade_hz=2000/33,seconds=ticks/(2000/33),
        wsg_sha256=hashlib.sha256((out/'wsg.tsv').read_bytes()).hexdigest(),wav_sha256=hashlib.sha256((out/'arcade.wav').read_bytes()).hexdigest(),
        original_wait_addresses=['1B03','1B0A'],port_score_parts=[8,9,10],port_score_frames_30hz=53,
        scope='Original2580 routine at one call per original video tick; clear request28 and contributor RAM seed, no original ROM writes. Original1B03 minimum-settle/1B0A sound-ready waits inspected separately. Controlled sound fixture, not natural playthrough.')
    marker.write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    import sys
    root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root));print(json.dumps(capture(root),indent=2))

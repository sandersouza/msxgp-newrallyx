"""Compile challenge notes from captured original WSG execution, not a guessed playlist."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib,json,os,re,shutil,subprocess
from pathlib import Path


def arcade_reference(root):
    source=source_path('arcade-audio-feedback.lua')
    seed=root/'assets/arcade/native/native-v1/video.bin'
    out=root/'references/cache/arcade-audio-feedback';out.mkdir(parents=True,exist_ok=True)
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    assert version.startswith('0.289 '),'Original audio capture requires pinned MAME0.289'
    key=dict(script_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),seed_sha256=hashlib.sha256(seed.read_bytes()).hexdigest(),emulator=version)
    marker=out/'reference.json'
    cached=json.loads(marker.read_text()) if marker.exists() else {}
    if not(cached.get('inputs')==key and (out/'complete').exists() and
           cached.get('wsg_sha256')==hashlib.sha256((out/'wsg.tsv').read_bytes()).hexdigest()):
        shutil.copyfile(seed,out/'seed.bin');(out/'complete').unlink(missing_ok=True)
        command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
            '-video','none','-sound','none','-wavwrite',str(out/'arcade.wav'),'-samplerate','48000','-nothrottle','-noautosave',
            '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(source),'-cfg_directory',str(out/'cfg'),
            '-nvram_directory',str(out/'nvram'),'-seconds_to_run','70']
        with (out/'mame.log').open('w') as log:
            subprocess.run(command,check=True,timeout=120,stdout=log,stderr=subprocess.STDOUT,
                env=dict(os.environ,NRX_ARCADE_AUDIO_OUTPUT=str(out)))
        assert (out/'complete').exists(),'Incomplete original sound capture'
        marker.write_text(json.dumps(dict(inputs=key,wsg_sha256=hashlib.sha256((out/'wsg.tsv').read_bytes()).hexdigest(),
            scope='Original sound routine at one call per original video frame; original RAM seed and explicit crash/challenge requests. No original ROM writes; not a natural gameplay run.'),indent=2)+'\n')
    return out


def patch(root,out,production):
    reference=arcade_reference(root)
    from arcade_motion_reference import capture
    motion=capture(root)
    rows={stage:[] for stage in ('crash','intro','music')}
    for line in (reference/'wsg.tsv').read_text().splitlines():
        stage,frame,request,*values=line.split();rows[stage].append(list(map(int,values)))
    assert len(rows['intro'])==385 and len(rows['music'])==1800
    def voices(regs,channels):
        result=[]
        for ch in channels:
            volume=regs[21+ch*5]
            step=(regs[16] if ch==0 else 0)+sum(regs[17+ch*5+n]<<(4*(n+1)) for n in range(4))
            result.append((step if volume else 0,volume))
        return tuple(result)
    music=[voices(r,(1,2)) for r in rows['music']]
    assert music[:260]==music[1540:1800],'Original challenge loop does not repeat at1540 ticks'
    metadata=json.loads((production/'audio-relocation.json').read_text())['compiled_scores']
    image=bytearray((out/'session-production-audio.bin').read_bytes())
    score=(out/'audio-score.inc').read_text();entries=metadata['dictionary']['entries']
    tones={(image[n]+256*image[256+n],image[512+n]):n for n in range(entries)}
    levels=[0]+[2**((i-15)/2) for i in range(1,16)]
    def tone(pitch,volume):
        nonlocal entries
        key=(pitch,volume)
        if key not in tones:
            assert entries<256,'PSG note dictionary capacity exceeded'
            tones[key]=entries;image[entries]=pitch&255;image[256+entries]=pitch>>8;image[512+entries]=volume;entries+=1
        return tones[key]
    def encode(payloads):
        result=bytearray();previous=None;count=0
        for p in payloads:
            if p!=previous or count==255:
                if count:result.extend(bytes((count,))+previous)
                previous=p;count=0
            count+=1
        result.extend(bytes((count,))+previous);result.append(0);return bytes(result)
    def convert(samples):
        packed=[]
        for parts in samples[::2]:
            values=[]
            for step,vol in parts:
                pitch=0 if not step else max(1,min(4095,round(1789772.5/(16*(step*96000/1048576)))))
                volume=min(range(16),key=lambda j:abs(levels[j]-vol/15)) if pitch else 0
                values.append(tone(pitch,volume))
            packed.append(bytes((values+[0,0,0])[:3]))
        return encode(packed)
    challenge=convert(music[:1540]);intro=convert([voices(r,(0,)) for r in rows['intro'][:384]])
    start=metadata['challenge']['address'];stop=metadata['intro']['address']
    assert len(challenge)<=stop-start and len(intro)<=1024
    image[start:stop]=challenge.ljust(stop-start,b'\0');image[0x3c00:0x4000]=intro.ljust(1024,b'\0')
    # The arcade BANG is a gated noise circuit, not a falling pitched effect.
    # Cache a broad attack/hold and short release; no runtime envelope arithmetic.
    crash_levels=[15]*8+[14]*3+[13]*3+[12]*2+[11,10,9,8,7,6,4,2,0]
    bass_hz=[100,82,68,56,48,42,38,34]+[32]*(len(crash_levels)-8)
    bass_periods=[round(1789772.5/(16*freq)) for freq in bass_hz]
    bang=encode([bytes((tone(period if level else 0,level),31,4)) for period,level in zip(bass_periods,crash_levels)])
    assert not any(image[0x3800:0x3900]) and len(bang)<=256
    image[0x3800:0x3800+len(bang)]=bang
    score=re.sub(r'(?m)^Audio_FX8Score EQU \$[0-9a-fA-F]+$','Audio_FX8Score EQU $3800',score)
    # Wave4 is a16th-harmonic carrier gated at the WSG cycle frequency.
    # AY C/B share a hardware saw envelope: no PCM interrupts or per-sample work.
    # Four original60Hz steps become two bounded30Hz packets at pair midpoints.
    smoke_periods=[round(1789772.5/(256*((a['step']+b['step'])/2*96000/1048576)))
                   for a,b in zip(motion['smoke'][::2],motion['smoke'][1::2])]
    smoke_levels=[16]*len(smoke_periods)
    smoke_score=encode([bytes((tone(period,16),0,0x20)) for period in smoke_periods])
    smoke_at=0x3900
    assert not any(image[smoke_at:0x3a00]) and len(smoke_score)<256
    image[smoke_at:smoke_at+len(smoke_score)]=smoke_score
    score=re.sub(r'(?m)^Audio_FX2Score EQU \$[0-9a-fA-F]+$','Audio_FX2Score EQU $3900',score)
    engine_period=round(1789772.5/(16*motion['engine_hz']))
    for heading in range(4):
        for velocity in ('Cruise','Drive'):
            key=f'Audio_Engine{heading}{velocity}Tone'
            score=re.sub(r'(?m)^'+key+r' EQU \d+$',key+' EQU '+str(engine_period),score)
    (out/'session-production-audio.bin').write_bytes(image);(out/'audio-score.inc').write_text(score)
    result=dict(reference=str(reference),reference_wsg_sha256=hashlib.sha256((reference/'wsg.tsv').read_bytes()).hexdigest(),
        challenge_original_ticks=1540,challenge_psg_frames=770,challenge_bytes=len(challenge),intro_original_calls=385,intro_psg_frames=192,
        dictionary_entries=entries,engine=dict(levels=[12,13],high_level_duty=[7/32,7/32,5/32],requested_amplitude_ratio=.85,revoicing_authorized='2026-10-28',
        scope='Volume-controlled square at the former envelope fundamental; deterministic physical-clock level mixing. PCM attenuation is measured separately.'),
        motion_reference=motion,
        smoke=dict(levels=smoke_levels,tone_periods=smoke_periods,envelope_periods=smoke_periods,envelope_shape=8,
        noise_periods=[0]*len(smoke_periods),frames=len(smoke_periods),channels=['B','C'],original_ticks=4,
        score_offset=smoke_at,scope='Captured rising gated tone, pair-midpoint conversion at30Hz. B is leased only during smoke; A continues music and B is restored immediately. Hardware envelope approximates the square gate; not literal PCM.'),
        crash=dict(noise_period=31,mixer=4,frames=len(crash_levels),levels=crash_levels,bass_hz=bass_hz,bass_periods=bass_periods,
        nominal_seconds=len(crash_levels)/30,channels=['B','C'],
        reference='https://github.com/mamedev/mame/blob/mame0289/src/mame/namco/nl_rallyx.cpp',
        scope='C retains gated noise, B adds a100..32Hz falling impact body. Both use cached note packets; B returns to music afterwards. AY timbre is an approximation; final auditory acceptance remains with user.'),
        scope='Pitches, original linear volumes and part/loop order from original WSG execution. AY waveforms remain an approximation; runtime does not execute the original sound CPU.')
    (out/'session-audio-corrections.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

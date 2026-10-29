"""Capture unmodified arcade motion/smoke and retain contributor data ignored."""
import hashlib,json,os,subprocess,wave
from pathlib import Path
from scripts.graphics.roms import input_records,load_metadata,validate_roms

def capture(root):
    source=Path(__file__).with_name('arcade-motion-audio.lua')
    out=root/'references/experiments/arcade-motion-audio';out.mkdir(parents=True,exist_ok=True)
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    assert version.startswith('0.289 ')
    key=dict(script_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),emulator=version,
             roms=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())))
    manifest=out/'reference.json'
    previous=json.loads(manifest.read_text()) if manifest.exists() else {}
    valid=previous.get('inputs')==key and (out/'complete').exists()
    valid=valid and all(hashlib.sha256((out/name).read_bytes()).hexdigest()==value for name,value in previous.get('hashes',{}).items())
    if not valid:
        command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
            '-video','none','-sound','none','-wavwrite',str(out/'arcade.wav'),'-samplerate','48000','-nothrottle','-noautosave',
            '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(source),'-cfg_directory',str(out/'cfg'),
            '-nvram_directory',str(out/'nvram'),'-seconds_to_run','70']
        (out/'complete').unlink(missing_ok=True)
        with (out/'mame.log').open('w') as log:
            subprocess.run(command,check=True,timeout=120,stdout=log,stderr=subprocess.STDOUT,
                           env=dict(os.environ,NRX_MOTION_AUDIO_OUTPUT=str(out)))
    assert (out/'complete').exists()
    rows=[line.split() for line in (out/'frames.tsv').read_text().splitlines()]
    assert len(rows)==4000 and all(len(r)==48 and int(r[0])==n for n,r in enumerate(rows,1))
    def voice(row):
        r=list(map(int,row[16:]));return dict(waveform=r[5]&7,step=r[16]+sum(r[17+n]<<(4*(n+1)) for n in range(4)),volume=r[21])
    bursts=[];engine=[]
    for index,row in enumerate(rows):
        v=voice(row)
        if row[2]=='2' and v['waveform']==4 and v['volume']==15:
            if not bursts or index!=bursts[-1][-1]+1:bursts.append([])
            bursts[-1].append(index)
        if row[2]=='2' and v['waveform']<4 and v['volume']==8:engine.append(index)
    bursts=[b for b in bursts if len(b)==4]
    assert len(bursts)>=4
    smoke=[voice(rows[i]) for i in bursts[0]]
    assert all([voice(rows[i]) for i in b]==smoke for b in bursts)
    axes={axis:[i for i in engine if int(rows[i][12])==(255 if axis=='horizontal' else 0)] for axis in ('horizontal','vertical')}
    assert all(len(indices)>100 for indices in axes.values())
    steps=sorted({voice(rows[i])['step'] for i in engine});assert len(steps)==1
    clips={}
    with wave.open(str(out/'arcade.wav'),'rb') as wav:
        parameters=wav.getparams();rate=wav.getframerate();data=wav.readframes(wav.getnframes());width=wav.getsampwidth()*wav.getnchannels()
    def clip(name,first,last):
        # MAME attotime string groups fractional digits with commas.
        seconds=lambda r:float(r[1].replace(',',''))
        start=seconds(rows[first-1]);stop=seconds(rows[last])
        target=out/(name+'.wav')
        with wave.open(str(target),'wb') as wav:
            wav.setparams(parameters);wav.writeframes(data[round(start*rate)*width:round(stop*rate)*width])
        clips[name]=dict(path=str(target),start_seconds=start,stop_seconds=stop,scope='Full original mix; music is not suppressed.')
    b=bursts[0];clip('smoke-arcade',b[0]-5,b[-1]+5)
    for axis,indices in axes.items():
        start=next(i for i in indices if i>2200 and all(j in indices for j in range(i,i+30)))
        clip('engine-'+axis+'-arcade',start,start+29)
    result=dict(inputs=key,frames=4000,smoke_bursts=len(bursts),smoke=smoke,engine_steps=steps,
        engine_hz=steps[0]*96000/1048576,axis_frames={k:len(v) for k,v in axes.items()},clips=clips,
        hashes={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ('frames.tsv','writes.tsv','inputs.tsv','arcade.wav')},
        scope='Real original coin/start/4-way/smoke input. No guest RAM/ROM writes, forced sound calls or muted voices. Captured wavetable timbre cannot be copied literally into a square-wave PSG.')
    manifest.write_text(json.dumps(result,indent=2)+'\n');return result

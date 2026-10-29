"""Timed PCM and PSG checks for the experimental production-audio adapter.

Sound-event/velocity fixtures do not constitute a natural full-course playthrough.
The worker is real ROM code and the recorded waveform is openMSX output.
"""
import argparse,array,hashlib,json,math,os,re,subprocess,tempfile,wave
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.msx.emulator import reference_machine,tcl
HZ=3579545;INTERVAL=2*59736/HZ


def verify(bundle):
    bundle=Path(bundle).resolve();out=Path(tempfile.mkdtemp(prefix='audio-proof-',dir=bundle))
    rom=(bundle/'fixed-hud.rom').read_bytes();(out/'measured.rom').write_bytes(rom)
    (out/'measured.sym').write_bytes((bundle/'lab.sym').read_bytes())
    s={n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',(bundle/'lab.sym').read_text())}
    def stub(address):return bytes((0xf3,0x31,0xe0,0xf2,0xcd,address&255,address>>8,0xf3,0xc3,0,0xf1)).hex()
    code=f'''set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set z80_freq {HZ}
set z80_freq_locked true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
cart {tcl(out/'measured.rom')} -romtype ASCII16
reset
activate_input_layer -blocking full_audio_proof
set out {tcl(out)}
set tick_stub [binary format H* {stub(s['GameAudio_Tick'])}]
set stop_stub [binary format H* {stub(s['GameSession_AudioStop'])}]
set tick_address {s['clock_ticks']}
set phase boot;set age 0;set stage engine;set step 0;set active 0;set ready 0
set rows [open [file join $out psg.tsv] w]
set costs [open [file join $out costs.tsv] w]
proc advance_clock {{}} {{
 set at $::tick_address;set tick [expr {{[debug read memory $at]+256*[debug read memory [expr {{$at+1}}]]+2}}]
 debug write memory $at [expr {{$tick&255}}];debug write memory [expr {{$at+1}}] [expr {{($tick>>8)&255}}]
}}
proc enter {{}} {{
 advance_clock
 if {{$::stage eq "engine"}} {{
  set ordinal [expr {{$::step/15}}];set velocity [expr {{$ordinal/4}}];set heading [expr {{$ordinal%4}}]
  set axis [expr {{$heading%2?0:255}}];set speed [expr {{$velocity==2?544:512}}]
  if {{$heading>=2}} {{set speed [expr {{-$speed}}]}}
  foreach {{a v}} [list 0xe048 [expr {{$velocity==0?3:0}}] 0xe069 [expr {{$speed&255}}] 0xe06a [expr {{($speed>>8)&255}}] 0xe06b $axis] {{debug write memory $a $v}}
 }}
 if {{$::stage eq "fuel"}} {{debug write memory 0xe9f4 2}}
 if {{$::stage eq "cold"}} {{
  if {{$::local_step==0}} {{debug write_block memory 0xf000 $::stop_stub;set ::active 1;reg PC 0xf000;return}}
  capture;return
 }}
 debug write_block memory 0xf000 $::tick_stub;set ::active 1;reg PC 0xf000
}}
proc capture {{}} {{
 binary scan [debug read_block {{PSG regs}} 0 14] cu* psg
 set mode [debug read memory 0xe9d3]
 puts $::rows "$::step $::stage [machine_info time] $mode [debug read memory 0xe9db] $psg"
 if {{$::stage eq "cold"}} {{
  foreach r {{8 9 10}} {{if {{[lindex $psg $r]}} {{error "PSG audible during cold transfer hold"}}}}
  if {{[debug read memory 0xe9c0] || [debug read memory 0xe9c3]}} {{error "Effect queue retained during cold transfer"}}
 }}
 incr ::step;incr ::local_step
 if {{$::stage eq "engine" && $::step==180}} {{
  set ::stage smoke1;set ::local_step 0
  debug write memory {s['Smoke_Placements']} [expr {{[debug read memory {s['Smoke_Placements']}]+1}}]
 }}
 if {{$::stage eq "smoke1" && $::local_step==18}} {{
  set ::stage smoke2;set ::local_step 0
  debug write memory {s['Smoke_Placements']} [expr {{[debug read memory {s['Smoke_Placements']}]+1}}]
 }}
 if {{$::stage eq "smoke2" && $::local_step==18}} {{
  set ::stage crash1;set ::local_step 0
  debug write memory 0xc490 1;debug write memory 0xe9f4 128;debug write memory 0xe9f5 8
 }}
 if {{$::stage eq "crash1" && $::local_step==36}} {{
  set ::stage crash2;set ::local_step 0;debug write memory 0xe9f4 128
 }}
 if {{$::stage eq "crash2" && $::local_step==36}} {{
  set ::stage complete;set ::local_step 0;set ::heard_complete 0
  debug write memory 0xc490 0;debug write memory 0xc724 1;debug write memory 0xe9f4 0;debug write memory 0xe9f5 40
 }}
 if {{$::stage eq "complete"}} {{
  if {{$mode==4}} {{set ::heard_complete 1}}
  if {{$::heard_complete && $mode==0 && !([debug read memory 0xe9f5]&32)}} {{set ::stage fuel;set ::local_step 0;debug write memory 0xc724 2}}
  if {{$::local_step>80}} {{error "Clear cue absent or did not finish"}}
 }}
 if {{$::stage eq "fuel" && $::local_step==30}} {{set ::stage cold;set ::local_step 0;debug write memory 0xc724 0}}
 if {{$::stage eq "cold" && $::local_step==12}} {{
  set ::stage gameover;set ::local_step 0;set ::heard_over 0
  debug write memory 0xc7d0 2;debug write memory 0xe9f5 4;debug write memory 0xd156 1
 }}
 if {{$::stage eq "gameover"}} {{
  if {{$mode==5}} {{set ::heard_over 1}}
  if {{$::heard_over && $mode==0 && !([debug read memory 0xe9f5]&4)}} {{
   set ::stage challenge_intro;set ::local_step 0;set ::heard_challenge 0
   debug write memory 0xc7d0 7;debug write memory 0xe9f5 64;debug write memory 0xd156 1
  }}
 }}
 if {{$::stage eq "challenge_intro"}} {{
  if {{$mode==6}} {{set ::heard_challenge 1}}
  if {{$::heard_challenge && $mode==0 && !([debug read memory 0xe9f5]&64)}} {{
   set ::stage challenge;set ::local_step 0
   debug write memory 0xc7d0 0;debug write memory 0xe1b0 4;debug write memory 0xe9f5 16;debug write memory 0xd156 1
  }}
 }}
 if {{$::stage eq "challenge" && $::local_step==31}} {{
  if {{$mode!=2}} {{error "Challenge music not selected"}}
  record stop;close $::rows;set f [open [file join $::out complete] w];puts $f done;close $f;exit 0;return
 }}
 if {{$::step>1500}} {{error "Music cue did not reach its end"}}
 set delay [expr {{max(0.000001,$::origin+$::step*{INTERVAL}-[machine_info time])}}]
 after time $delay guarded_enter
}}
proc guarded_enter {{}} {{if {{[catch enter error]}} {{puts stderr $::errorInfo;exit 2}}}}
debug set_bp 0xf007 {{$::active && [info exists ::audio_start]}} {{
  # Exact return address: before either trailing caller instruction executes.
  set group $::stage
  if {{[string match smoke* $group]}} {{set group [expr {{[debug read memory 0xe9c3]==2?"smoke_active":"smoke_resume"}}]}}
  puts $::costs "$group [expr {{([machine_info time]-$::audio_start)*{HZ}}}]"
  flush $::costs;unset ::audio_start
}}
debug set_bp 0xf100 {{$::active}} {{
 set ::active 0;reg PC 0xf200
 if {{[catch capture error]}} {{puts stderr $::errorInfo;exit 2}}
}}
debug set_bp {s['GameAudio_Tick']} {{$::active}} {{set ::audio_start [machine_info time]}}
debug set_bp {s['GameSession_AudioStop']} {{$::active}} {{set ::audio_start [machine_info time]}}
debug set_bp {s['frame_done']} {{!$::ready && [debug read memory 0xc7d0]==0}} {{
 set ::ready 1
 debug write {{VDP regs}} 1 [expr {{[debug read {{VDP regs}} 1]&223}}]
 foreach {{a v}} {{0xc7d0 0 0xc7ee 0 0xc490 0 0xc724 0 0xc050 0 0xc50b 0 0xc711 0 0xc712 0 0xe9f4 0 0xe9f5 0 0xe9f6 0 0xd150 0 0xd156 0}} {{debug write memory $a $v}}
 debug write_block memory 0xe9a0 [string repeat [binary format c 0] 80]
 debug write_block memory 0xe9b0 [string repeat [binary format cu 255] 14]
 debug write_block memory 0xf200 [binary format H* f3c300f2]
 set ::local_step 0;record start -audioonly [file join $::out engine-and-cues.wav];set ::origin [machine_info time]
 enter
}}
proc menu {{}} {{
 if {{$::ready}} {{return}}
 incr ::age;set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
 boot {{if {{$state==1 && $ready}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
 coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::phase start;set ::age 0}}}}
 start {{if {{$::age==5}} {{keymatrixup 0 2}}}}
 }}
 after time 0.02 menu
}}
after time 0.02 menu
after time 90 {{puts stderr "Audio fixture timeout";exit 3}}
'''
    (out/'audio.tcl').write_text('if {[catch {\n'+code+'\n} e]} {puts stderr $::errorInfo;exit 2}\n')
    with (out/'openmsx.log').open('w') as log:
        run=subprocess.run(['openmsx','-script',str(out/'audio.tcl')],timeout=120,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    assert run.returncode==0 and (out/'complete').exists(),(out,(out/'openmsx.log').read_text()[-1200:])
    rows=[]
    for line in (out/'psg.tsv').read_text().splitlines():
        n,stage,time,mode,key,*regs=line.split();rows.append(dict(step=int(n),stage=stage,time=float(time),mode=int(mode),key=int(key),regs=list(map(int,regs))))
    for velocity in range(3):
        cases=[rows[(velocity*4+heading)*15+10] for heading in range(4)]
        assert len({tuple(r['regs'][i] for i in (4,5,11,12,13)) for r in cases})==1,'Direction changed engine pitch/envelope parameters'
        assert all(r['regs'][10] in (12,13) for r in cases),'Engine gain escaped calibrated levels'
    reference=Path(json.loads((bundle/'session-audio-corrections.json').read_text())['reference'])
    native=[list(map(int,line.split()[3:])) for line in (reference/'wsg.tsv').read_text().splitlines() if line.startswith('music ')]
    levels=[0]+[2**((i-15)/2) for i in range(1,16)]
    challenge=[r for r in rows if r['stage']=='challenge']
    for index,row in enumerate(challenge):
        sample=native[index*2]
        for channel,source in enumerate((1,2)):
            volume=sample[21+source*5]
            step=sum(sample[17+source*5+n]<<(4*(n+1)) for n in range(4))
            pitch=max(1,min(4095,round(1789772.5/(16*(step*96000/1048576))))) if step and volume else 0
            amplitude=min(range(16),key=lambda j:abs(levels[j]-volume/15)) if pitch else 0
            assert (row['regs'][channel*2]+256*row['regs'][channel*2+1],row['regs'][channel+8])==(pitch,amplitude),'Challenge PSG differs from captured arcade note/volume'
    for name in ('crash1','crash2'):
        tail=[r for r in rows if r['stage']==name][-1]
        assert tail['regs'][9]==tail['regs'][10]==0,'Crash channel lease was not restored'
    with wave.open(str(out/'engine-and-cues.wav'),'rb') as wav:
        rate=wav.getframerate();channels=wav.getnchannels();assert wav.getsampwidth()==2
        pcm=array.array('h',wav.readframes(wav.getnframes()));seconds=len(pcm)/rate/channels
    assert max(map(abs,pcm))<32767 and max(map(abs,pcm))>100
    smoke=[]
    smoke_meta=json.loads((bundle/'session-audio-corrections.json').read_text())['smoke']
    smoke_levels=smoke_meta['levels'];smoke_frames=smoke_meta['frames']
    for name in ('smoke1','smoke2'):
        samples=[r for r in rows if r['stage']==name]
        assert [r['regs'][10] for r in samples[:smoke_frames]]==smoke_levels,'Smoke placement did not play its complete level contour'
        for row,period in zip(samples[:smoke_frames],smoke_meta['tone_periods']):
            regs=row['regs']
            assert regs[2]+256*regs[3]==regs[4]+256*regs[5]==period,'Smoke captured carrier changed'
            assert regs[11]+256*regs[12]==period and regs[13]==8,'Smoke hardware gate changed'
            assert regs[9]==regs[10]==16 and regs[7]&63==56,'Smoke channel lease/mixer changed'
        assert samples[smoke_frames]['regs'][9]!=16,'Smoke retained music channel B'
        assert samples[-1]['key'] and samples[-1]['regs'][10] in (12,13),'Smoke did not restore the engine'
        begin=samples[0]['time']-rows[0]['time']
        raw=pcm[round((begin+.008)*rate)*channels:round((begin+.118)*rate)*channels]
        mean=sum(raw)/len(raw);amplitude=(sum((v-mean)**2 for v in raw)/len(raw))**.5
        assert amplitude>10,'Smoke was silent'
        smoke.append(dict(cue=name,rms=amplitude,levels=smoke_levels,tone_periods=smoke_meta['tone_periods'],
                          envelope_shape=8,leased_channels=['B','C'],sound_frames=smoke_frames,native_placement_trigger=True))
    smoke_baseline=ROOT/'outputs/full-session/baseline-15c931/audio-smoke-baseline.json'
    if smoke_baseline.exists():
        prior=json.loads(smoke_baseline.read_text())
        if prior['rom_sha256']!=hashlib.sha256(rom).hexdigest():
            for current,previous_smoke in zip(smoke,prior['smoke']):
                ratio=current['rms']/previous_smoke['rms']
                assert ratio>2,'Smoke did not become meaningfully louder'
                current.update(baseline_rms=previous_smoke['rms'],amplitude_ratio=ratio,gain_db=20*math.log10(ratio))
    # Measure the added low-frequency body separately from overall noise RMS.
    # The baseline is immutable evidence from the pre-cosmetics cartridge.
    crash_baseline=ROOT/'outputs/full-session/baseline-70d633/verification.json'
    bass_before=None
    if crash_baseline.exists():
        prior=json.loads(crash_baseline.read_text())
        assert prior['rom_sha256']=='70d6335163a702045b4a6da5cc3ac4eba1dd5e5b48e1aeda3cb628a81887a3c4'
        baseline_audio=Path(prior['audio']['path'])
        if (baseline_audio/'engine-and-cues.wav').exists():
            with wave.open(str(baseline_audio/'engine-and-cues.wav'),'rb') as f:
                assert (f.getframerate(),f.getnchannels())==(rate,channels)
                bass_before=array.array('h',f.readframes(f.getnframes()))
            prior_rows=[r.split() for r in (baseline_audio/'psg.tsv').read_text().splitlines()]
    def low_band(signal,begin):
        raw=signal[round((begin+.02)*rate)*channels:round((begin+.28)*rate)*channels]
        mono=[sum(raw[i:i+channels])/channels for i in range(0,len(raw),channels)]
        mean=sum(mono)/len(mono)
        window=[(v-mean)*(.5-.5*math.cos(2*math.pi*i/(len(mono)-1))) for i,v in enumerate(mono)]
        result=0.
        for freq in range(30,201,2):
            coefficient=2*math.cos(2*math.pi*freq/rate);a=b=0.
            for v in window:a,b=v+coefficient*a-b,a
            result+=max(0,a*a+b*b-coefficient*a*b)
        return result
    crash=[]
    crash_meta=json.loads((bundle/'session-audio-corrections.json').read_text())['crash']
    for name in ('crash1','crash2'):
        row=next(r for r in rows if r['stage']==name)
        begin=row['time']-rows[0]['time']
        def energy(start,stop):
            raw=pcm[round((begin+start)*rate)*channels:round((begin+stop)*rate)*channels]
            mean=sum(raw)/len(raw);return (sum((v-mean)**2 for v in raw)/len(raw))**.5
        early,late=energy(.02,.15),energy(.65,.78)
        assert early>100 and late<early*.4,(name,early,late)
        samples=[r for r in rows if r['stage']==name]
        for sample,period in zip(samples,crash_meta['bass_periods']):
            if not sample['regs'][10]:continue
            assert sample['regs'][2]+256*sample['regs'][3]==period,'Explosion bass period changed'
            assert sample['regs'][9]==sample['regs'][10],'Explosion bass/noise contour differs'
            assert sample['regs'][7]&18==16,'Explosion lost B tone or enabled B noise'
        measured=low_band(pcm,begin)
        case=dict(cue=name,initial_rms=early,tail_rms=late,low_band_power=measured,band_hz=[30,200],window_seconds=[.02,.28],method='DC-removed stereo mean, Hann window, summed Goertzel power at2Hz steps')
        if bass_before is not None:
            prior_begin=float(next(r for r in prior_rows if r[1]==name)[2])-float(prior_rows[0][2])
            previous_power=low_band(bass_before,prior_begin)
            assert measured>previous_power*1.2,'Explosion gained no measurable low-frequency body'
            case.update(baseline_low_band_power=previous_power,low_band_gain_db=10*math.log10(measured/previous_power),baseline_rom_sha256=prior['rom_sha256'])
        crash.append(case)
    assert .6<crash[1]['initial_rms']/crash[0]['initial_rms']<1.5,'Second crash envelope did not retrigger'
    engine=[]
    baseline_index=ROOT/'outputs/full-session/baseline-5451bd/verification.json'
    baseline=None
    if baseline_index.exists():
        info=json.loads(baseline_index.read_text())
        assert info['rom_sha256']=='5451bd8933b22f1fa334dbc538a905b5615cf1ea58623af23933e900cdf3ffa2'
        previous=Path(info['audio']['path'])/'engine-and-cues.wav'
        if previous.exists():
            with wave.open(str(previous),'rb') as prior:
                assert prior.getframerate()==rate and prior.getnchannels()==channels
                baseline=array.array('h',prior.readframes(prior.getnframes()))
    def rms(signal):
        mean=sum(signal)/len(signal)
        return (sum((x-mean)**2 for x in signal)/len(signal))**.5
    for velocity in range(3):
        r=rows[velocity*60+10];regs=r['regs'];period=regs[11]+256*regs[12]
        expected=HZ/2/(16*(regs[4]+256*regs[5]))
        start=round((velocity*60+5)*INTERVAL*rate)*channels;length=round(.25*rate)*channels
        raw=pcm[start:start+length];signal=[sum(raw[i:i+channels])/channels for i in range(0,len(raw),channels)]
        mean=sum(signal)/len(signal);window=[(v-mean)*(.5-.5*math.cos(2*math.pi*i/(len(signal)-1))) for i,v in enumerate(signal)]
        def magnitude(freq):
            coef=2*math.cos(2*math.pi*freq/rate);a=b=0.
            for v in window:a,b=v+coef*a-b,a
            return max(0,a*a+b*b-coef*a*b)**.5
        measured=max((expected*(.96+i*.001) for i in range(81)),key=magnitude)
        assert abs(measured/expected-1)<.025,(velocity,expected,measured)
        case=dict(velocity=velocity,expected_fundamental_hz=expected,measured_pcm_hz=measured,all_four_headings_identical=True)
        if baseline is not None:
            begin=round((velocity*60*INTERVAL+.15)*rate)*channels
            end=round((velocity*60*INTERVAL+1.95)*rate)*channels
            before,after=rms(baseline[begin:end]),rms(pcm[begin:end])
            ratio=after/before
            assert .80<ratio<.90,('Engine attenuation outside approximately15%',velocity,ratio)
            case.update(baseline_rms=before,rms=after,amplitude_ratio=ratio,reduction_percent=100*(1-ratio))
        engine.append(case)
    cues={name:sum(r['stage']==name for r in rows) for name in ('complete','gameover','challenge_intro','challenge','cold')}
    clear=[r for r in rows if r['stage']=='complete']
    assert sum(r['mode']==4 for r in clear)==53,('Incorrect clear-melody length',len(clear))
    assert any(any(r['regs'][n] for n in (8,9,10)) for r in clear),'Clear melody is silent'
    from arcade_clear_reference import capture as capture_clear
    original_clear=capture_clear(ROOT)
    native_clear=[list(map(int,line.split()))[2:] for line in (ROOT/'references/experiments/arcade-clear-audio/wsg.tsv').read_text().splitlines()]
    cents=[]
    for index,row in enumerate(r for r in clear if r['mode']==4):
        wsg=native_clear[index*2];ay=row['regs']
        for ch in range(3):
            step=(wsg[16] if ch==0 else 0)+sum(wsg[17+ch*5+n]<<(4*(n+1)) for n in range(4))
            period=ay[ch*2]+256*ay[ch*2+1]
            if step and wsg[21+ch*5] and period and ay[8+ch]:
                cents.append(abs(math.log2((1789772.5/(16*period))/(step*96000/1048576)))*1200)
    assert cents and max(cents)<10,('Clear melody differs from original pitches',max(cents))
    import statistics
    grouped={}
    for line in (out/'costs.tsv').read_text().splitlines():
        name,cycles=line.split();name=re.sub(r'[12]$','',name);grouped.setdefault(name,[]).append(float(cycles))
    cost_summary=[dict(name='GameAudio_Tick ('+name+')' if name!='cold' else 'GameSession_AudioStop',calls=len(values),
         inclusive=dict(mean=statistics.mean(values),p95=sorted(values)[math.ceil(.95*len(values))-1],max=max(values)))
         for name,values in grouped.items()]
    clear_cue=dict(frames=53,nominal_seconds=53*INTERVAL,original=original_clear,compared_voice_samples=len(cents),max_pitch_error_cents=max(cents),scope='All three note voices against original WSG on paired native ticks; PSG period quantization, not waveform/timbre equivalence.')
    report=dict(clear_cue=clear_cue,passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),path=str(out),seconds=seconds,engine=engine,smoke=smoke,crash=crash,cue_ticks_30hz=cues,audio_costs=cost_summary,
        audio_cost_method='Sound-only fixtures; breakpoint at worker entry and exact caller return address before trailing instructions. Guest elapsed inclusive cycles including RET; no tracked child self costs, no active-game FPS claim.',
        scope='Real PSG worker and openMSX PCM at physical-clock cadence; explicit sound-only fixtures. Direction equality and fundamental tested; subjective arcade timbre remains for user acceptance.')
    if baseline is not None:report['engine_baseline']=dict(rom_sha256=info['rom_sha256'],wav=str(previous),wav_sha256=hashlib.sha256(previous.read_bytes()).hexdigest(),window_seconds=[.15,1.95],method='DC-removed PCM RMS at each velocity across all four headings; matched machine/PSG settings')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=ROOT/'references/experiments/full-session');a=p.parse_args();verify(a.bundle)

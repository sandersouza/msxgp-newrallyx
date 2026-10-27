#!/usr/bin/env python3
"""Record a timed production-PSG audition with explicitly seeded sound events."""
import argparse
import array
import math
import os
from pathlib import Path
import subprocess
import sys
import wave

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine, tcl
from scripts.msx.hud_verify import symbols
from scripts.scenes.bundle import digest, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal


def magnitude(samples, rate, frequency):
    coefficient=2*math.cos(2*math.pi*frequency/rate)
    first=second=0.
    for value in samples:
        current=value+coefficient*first-second
        second,first=first,current
    return math.sqrt(max(0.,first*first+second*second-coefficient*first*second))*2/len(samples)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path(__file__).resolve().parents[1]
    rom=args.rom.resolve();verify_manifest(rom.parent);s=symbols(rom.parent/'raster-scroll.sym')
    out=destination(root,args.output);require_ignored(root,[out/'audition.wav']);out.mkdir(parents=True)
    events={0:'credit',30:'three-voice Start',155:'music and driving engine',210:'idle engine',
            230:'cruising engine',250:'driving engine',290:'fuel refill',320:'fuel conversion',340:'smoke',380:'flag',
            420:'special flag',480:'low-fuel warning',550:'extra life',590:'crash'}
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off',
        f'cart {tcl(rom)} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set started 0;set active 0;set step 0;set rows [open [file join $out psg.tsv] w]',
        'proc issue {} {',
        ' if {$::step==630} {record stop;close $::rows;exit 0;return}',
        ' switch $::step {',
        ' 0 {debug write memory 0xe9f6 128}',
        f' 30 {{debug write memory 0xc7d0 5;debug write memory 0xe9f5 128;debug write memory {s["Audio_NewScene"]} 1}}',
        f' 155 {{debug write memory 0xc7d0 0;debug write memory 0xe9f5 16;debug write memory {s["Audio_NewScene"]} 1}}',
        ' 210 {debug write memory 0xe9f5 0;debug write memory 0xe06a 0} 230 {debug write memory 0xe06a 1} 250 {debug write memory 0xe06a 2}',
        ' 270 {debug write memory 0xe9f5 16}',
        ' 290 {debug write memory 0xe9f6 64} 320 {debug write memory 0xe9f4 2} 340 {debug write memory 0xe9f4 16}',
        ' 380 {debug write memory 0xe9f4 4} 420 {debug write memory 0xe9f4 8}',
        ' 480 {debug write memory 0xe9f4 32} 550 {debug write memory 0xe9f4 1}',
        ' 590 {debug write memory 0xe9f4 128}',
        ' }',
        f' debug write memory 0x7000 {s["PLAYER_BANK"]}',
        f' debug write memory {s["ticks"]} [expr {{([debug read memory {s["ticks"]}]+2)&255}}]',
        ' reg PC 0xd140;reg SP 0xf380;set ::active 1',
        '}',
        f'debug set_bp {s["main"]} {{!$::started}} {{',
        ' set ::started 1;debug write {VDP regs} 0 6;debug write {VDP regs} 1 2',
        ' debug write memory 0xc7d0 1;debug write memory 0xc7ee 0;debug write memory 0xc490 0;debug write memory 0xc724 0',
        ' debug write memory 0xc50b 0;debug write memory 0xc711 0;debug write memory 0xe048 0;debug write memory 0xe069 0;debug write memory 0xe06a 2;debug write memory 0xe06b 0',
        ' debug write memory 0xe9f4 0;debug write memory 0xe9f5 0;debug write memory 0xe9f6 0',
        f' debug write memory {s["Audio_NewScene"]} 1;debug write memory {s["Audio_Mute"]} 0',
        f' set at 0xd140;foreach value {{243 205 {s["Audio_Work"]&255} {s["Audio_Work"]>>8} 243 195 95 209}} {{debug write memory $at $value;incr at}}',
        ' debug write_block memory 0xd160 [binary format c* {195 96 209}]',
        f' record start -audioonly {tcl(out/"audition.wav")}',
        ' set ::origin [machine_info time];issue',
        '}',
        'debug set_bp 0xd15f {$::active} {',
        ' set ::active 0;reg PC 0xd160;binary scan [debug read_block {PSG regs} 0 14] cu* values',
        ' puts $::rows "$::step [machine_info time] $values";incr ::step',
        ' set delay [expr {max(0.00001,$::origin+$::step*2*0.01668815450008311-[machine_info time])}];after time $delay issue',
        '}',
        'after time 60 {puts stderr "Audition timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=120,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    rows=[line.split() for line in (out/'psg.tsv').read_text().splitlines()]
    if len(rows)!=630:raise ValueError('Incomplete timed audition')
    with wave.open(str(out/'audition.wav'),'rb') as wav:
        if wav.getsampwidth()!=2:raise ValueError('Expected signed 16-bit recording')
        rate=wav.getframerate();channels=wav.getnchannels()
        seconds=wav.getnframes()/rate;pcm=array.array('h',wav.readframes(wav.getnframes()))
    peak=max(map(abs,pcm));rms=(sum(v*v for v in pcm)/len(pcm))**.5
    if not 20<seconds<22 or not 100<rms or peak>=32767:raise ValueError('Audition silent, clipped or mistimed')
    engine=[]
    if int(rows[220][12])==16:  # PSG register 10, after step/time and registers 0..9.
        for step,name in ((220,'Idle'),(240,'Cruise'),(260,'Drive')):
            start=round(step*2*.01668815450008311*rate)*channels
            raw=pcm[start:start+round(.25*rate)*channels]
            samples=[sum(raw[i:i+channels])/channels for i in range(0,len(raw),channels)]
            mean=sum(samples)/len(samples);signal_rms=(sum((v-mean)**2 for v in samples)/len(samples))**.5
            window=[(v-mean)*(.5-.5*math.cos(2*math.pi*i/(len(samples)-1))) for i,v in enumerate(samples)]
            expected=1789772.5/(16*s[f'Audio_Engine{name}Period'])
            candidates=[expected*(.94+i*.002) for i in range(61)]
            measured=max(candidates,key=lambda f:magnitude(window,rate,f))
            fundamental=magnitude(window,rate,measured)
            if abs(measured/expected-1)>.02 or fundamental<signal_rms*.25:
                raise ValueError(f'Engine PCM pitch disagrees with the original spectral target: {name}')
            engine.append(dict(velocity=name,expected_hz=expected,measured_hz=measured,
                second_harmonic_ratio=magnitude(window,rate,measured*2)/fundamental))
    json_write(out/'report.json',dict(rom_sha256=digest(rom),passed=True,seconds=seconds,peak=peak,rms=rms,
        engine_spectrum=engine,events=[dict(seconds=step*2*.01668815450008311,label=label) for step,label in events.items()],
        scope='Actual emulator PCM from production PSG worker at physical-clock cadence, with seeded UI/velocity/event fixtures. '
              'No raster/gameplay performance or subjective listening verdict is implied.'))
    seal(out);print(f'Timed PSG audition recorded: {out}/audition.wav')


if __name__=='__main__':main()

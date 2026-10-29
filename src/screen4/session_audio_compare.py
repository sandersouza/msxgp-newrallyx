"""Create a level-matched listening aid; original audio remains ignored."""
import array,hashlib,json,math,wave
from pathlib import Path

def build(root,proof):
    reference=root/'references/experiments/arcade-motion-audio'
    out=reference/'comparison';out.mkdir(exist_ok=True)
    pcm_path=proof/'engine-and-cues.wav'
    def read(path):
        with wave.open(str(path),'rb') as wav:
            assert wav.getsampwidth()==2
            rate,channels=wav.getframerate(),wav.getnchannels()
            pcm=array.array('h',wav.readframes(wav.getnframes()))
        return rate,[sum(pcm[i:i+channels])/channels for i in range(0,len(pcm),channels)]
    rate,pcm=read(pcm_path)
    rows=[line.split() for line in (proof/'psg.tsv').read_text().splitlines()]
    origin=float(rows[0][2]);smoke=next(r for r in rows if r[1]=='smoke1')
    data=[];segments=[];target_rate=48000
    def append(name,path,start=None,duration=None):
        if start is None:hz,raw=read(path)
        else:hz,raw=rate,pcm[round(start*rate):round((start+duration)*rate)]
        mean=sum(raw)/len(raw);raw=[x-mean for x in raw]
        rms=math.sqrt(sum(v*v for v in raw)/len(raw));gain=2200/rms
        begin=len(data)/target_rate
        for n in range(round(len(raw)*target_rate/hz)):
            at=n*hz/target_rate;lo=min(int(at),len(raw)-1);hi=min(lo+1,len(raw)-1)
            value=(raw[lo]+(raw[hi]-raw[lo])*(at-lo))*gain
            data.append(round(max(-32760,min(32760,value))))
        segments.append(dict(name=name,start_seconds=begin,end_seconds=len(data)/target_rate,
                             source=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rms_gain=gain))
        data.extend([0]*round(.3*target_rate))
    append('Smoke arcade',reference/'smoke-arcade.wav')
    append('Smoke MSX',pcm_path,float(smoke[2])-origin,.231)
    for axis,index in (('horizontal',65),('vertical',80)):
        append('Engine '+axis+' arcade',reference/f'engine-{axis}-arcade.wav')
        append('Engine '+axis+' MSX',pcm_path,float(rows[index][2])-origin,.3)
    target=out/'arcade-msx.wav'
    with wave.open(str(target),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(target_rate)
        wav.writeframes(array.array('h',data).tobytes())
    report=dict(path=str(target),segments=segments,
        scope='Listening aid: arcade then MSX for smoke, horizontal engine, vertical engine. Clips RMS matched; not an output-volume comparison. Arcade is the full original mix; MSX uses the controlled sound fixture. Not waveform equivalence evidence.')
    (out/'comparison.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('proof',type=Path)
    args=parser.parse_args();print(json.dumps(build(Path(__file__).resolve().parents[2],args.proof),indent=2))

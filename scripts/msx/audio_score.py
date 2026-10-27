"""Compile original parts and tonal effects into bounded three-voice PSG packets."""
from .audio_psg import period, volume_curve

FRAME_BYTES = 9


def voice_at(notes, tick, volume, articulate=False):
    for word,duration in notes:
        if tick < duration:
            value=period(word)
            if not value:return 0,0
            if articulate and duration>=6:
                volume+=int(tick<2)-int(duration>=10 and tick>=duration-2)
            return value,max(0,min(15,volume))
        tick-=duration
    raise ValueError('Incomplete melody')


def voice_frames(parts, *, volumes=None, articulate=False):
    if not 1<=len(parts)<=3:raise ValueError('Expected one to three parts')
    volumes=volumes or (12,11,11)
    stop=min(sum(d for _,d in part) for part in parts)
    result=[]
    for tick in range(0,stop,2):
        values=[voice_at(part,tick,volumes[i],articulate) for i,part in enumerate(parts)]
        values.extend([(0,0)]*(3-len(values)))
        result.append(b''.join(p.to_bytes(2,'little') for p,v in values)+bytes(v for p,v in values))
    return result


def tone_index(tones, pitch, volume):
    key=(pitch,volume)
    if key not in tones:
        if len(tones)==256:raise ValueError('Tone dictionary exceeds 256 entries')
        tones[key]=len(tones)
    return tones[key]


def rle(payloads):
    result=bytearray();previous=None;count=0
    for payload in payloads:
        if payload!=previous or count==255:
            if count:result.extend(bytes((count,))+previous)
            previous=payload;count=0
        count+=1
    if count:result.extend(bytes((count,))+previous)
    result.append(0)
    return bytes(result)


def dictionary_encode(frames, tones):
    if not frames or any(len(f)!=FRAME_BYTES for f in frames):raise ValueError('Expected three-voice packets')
    return rle(bytes(tone_index(tones,int.from_bytes(f[ch*2:ch*2+2],'little'),f[6+ch])
                     for ch in range(3)) for f in frames)


def effect_frames(program, identifier):
    # Keep the original melodic identity; smoke/crash alone use authored noise.
    source={1:11,3:6,4:7,5:0,6:3,7:4,9:1}
    if identifier in source:
        notes=melody(program,source[identifier]);stop=sum(d for _,d in notes)
        return [p.to_bytes(2,'little')+bytes((v,0,32))
                for tick in range(0,stop,2)
                for p,v in [voice_at(notes,tick,12 if identifier!=3 else 11)]]
    profiles={2:((0,10,4,4),(0,9,8,4),(0,7,12,4),(0,4,18,4)),
              8:((380,15,10,0),(480,14,13,0),(640,13,17,0),(850,11,21,0),
                 (1100,9,25,0),(1400,6,31,0),(1800,3,31,0))}
    return [p.to_bytes(2,'little')+bytes((v,n,m)) for p,v,n,m in profiles[identifier]]


def melody(program, identifier):
    at = int.from_bytes(program[0x2b58+identifier*2:0x2b5a+identifier*2], 'little')
    notes = []
    for _ in range(256):
        if not 0x2b00 <= at < 0x3000:
            raise ValueError('Melody leaves the validated sound-data range')
        note = program[at]
        if note == 255:
            if not notes: raise ValueError('Empty melody')
            return notes
        duration = program[at+1]
        if not duration: raise ValueError('Zero-duration melody note')
        base = int.from_bytes(program[0x2afd+(note&15)*2:0x2aff+(note&15)*2], 'little')
        notes.append((base >> (note>>4), duration))
        at += 2
    raise ValueError('Unterminated melody')


def pair_frames(first, second, *omitted):
    """Sample note boundaries at 30 Hz, retaining original durations in ticks.

    Every original part retains its shared stop authority, including a third
    voice omitted from PSG output. Otherwise shared table tails can be played
    as extra phrases after the original group would already have stopped.
    """
    stop = min(sum(n for _,n in part) for part in (first,second,*omitted))
    def voice_at(notes, tick):
        for word,duration in notes:
            if tick < duration:
                value = period(word)
                return value, volume_curve()[8] if value else 0
            tick -= duration
        raise ValueError('Incomplete paired melody')
    result = []
    for tick in range(0, stop, 2):
        a,av = voice_at(first,tick); b,bv = voice_at(second,tick)
        result.append(a.to_bytes(2,'little')+b.to_bytes(2,'little')+bytes((av,bv)))
    return result


def encode(frames):
    if not frames: raise ValueError('Empty score')
    result = bytearray(); previous = None; count = 0
    for frame in frames:
        if len(frame)!=6 or any(value>15 for value in frame[4:]):
            raise ValueError('Expected a two-voice PSG packet')
        frame=frame[:4]+bytes((frame[4]|frame[5]<<4,))
        if frame!=previous or count==255:
            if count: result.extend(bytes((count,))+previous)
            previous=frame; count=0
        count+=1
    result.extend(bytes((count,))+previous)
    result.append(0)
    return bytes(result)


def build(program, out):
    # Original background playlist: $10, $0d, $0d. The challenge alternates
    # its two original accompaniment choices against melody $0d.
    playlist=program[0x2b54:0x2b58]
    if len(playlist)!=4 or playlist[-1]!=255 or any(value>=23 for value in playlist[:-1]):
        raise ValueError('Original background playlist changed')
    pairs = dict(normal=tuple((value,value+1) for value in playlist[:-1]),
                 challenge=((14,13),(14,13),(23,13),(23,13)),
                 intro=((18,19,20),), complete=((8,9,10),),gameover=((21,22),))
    image=bytearray(768); declarations=['Audio_ToneLow EQU $8000','Audio_ToneHigh EQU $8100','Audio_ToneVolume EQU $8200']; metadata={}
    engine_at=int.from_bytes(program[0x2b5c:0x2b5e],'little')
    engine_words=[]
    for offset in (0,2):
        note=program[engine_at+offset]
        word=int.from_bytes(program[0x2afd+(note&15)*2:0x2aff+(note&15)*2],'little')>>(note>>4)
        engine_words.append(word)
    for heading,harmonic in enumerate((3,1,3,5)):
        for name,word in zip(('Idle','Cruise','Drive'),(engine_words[0],sum(engine_words)//2,engine_words[1])):
            pitch=period(word*harmonic)
            declarations.append(f'Audio_Engine{heading}{name}Envelope EQU {max(1,round(pitch/16))}')
            if heading==1:
                declarations.append(f'Audio_Engine{name}Period EQU {pitch}')
    tones={(0,0):0}
    for name,parts in pairs.items():
        frames=[]
        for part in parts:
            # The sine-like original bass needs presence, not the extra harmony
            # attenuation. Square-wave parts retain more energy than saw/sine.
            gains=tuple((12 if program[0x2b3c+i] in (5,6) else 13)
                        -int(ch==1 and program[0x2b3c+i]!=5) for ch,i in enumerate(part))
            frames.extend(voice_frames(tuple(melody(program,i) for i in part),volumes=gains,articulate=True))
        code=dictionary_encode(frames,tones)
        declarations.append(f'Audio_{name.title()}Score EQU ${len(image):04x}')
        metadata[name]=dict(address=len(image),bytes=len(code),frames=len(frames),parts=parts)
        (out/f'audio-{name}-frames.bin').write_bytes(b''.join(frames))
        image.extend(code)
    for identifier in range(1,10):
        frames=effect_frames(program,identifier)
        code=rle(bytes((tone_index(tones,int.from_bytes(f[:2],'little'),f[2]),f[3],f[4])) for f in frames)
        declarations.append(f'Audio_FX{identifier}Score EQU ${len(image):04x}')
        metadata[f'effect{identifier}']=dict(address=len(image),bytes=len(code),frames=len(frames))
        (out/f'audio-fx-{identifier}-frames.bin').write_bytes(b''.join(frames))
        image.extend(code)
    for (pitch,volume),index in tones.items():
        image[index]=pitch&255;image[256+index]=pitch>>8;image[512+index]=volume
    metadata['dictionary']=dict(entries=len(tones),bytes=768,total_bytes=len(image))
    if len(image)>6144: raise ValueError(f'Compiled music/effects exceed private 6 KB score bank: {len(image)}')
    (out/'audio-score.bin').write_bytes(bytes(image).ljust(6144,b'\0'))
    (out/'audio-score.inc').write_text('\n'.join(declarations)+'\n')
    return metadata

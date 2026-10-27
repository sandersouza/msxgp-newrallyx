"""Compile contributor-supplied melody tables into bounded two-voice packets."""
from .audio_psg import period, volume_curve


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
    image=bytearray(); declarations=[]; metadata={}
    for name,parts in pairs.items():
        frames=[]
        for part in parts: frames.extend(pair_frames(*(melody(program,identifier) for identifier in part)))
        code=encode(frames)
        declarations.append(f'Audio_{name.title()}Score EQU ${len(image):04x}')
        metadata[name]=dict(address=len(image),bytes=len(code),frames=len(frames),parts=parts)
        (out/f'audio-{name}-frames.bin').write_bytes(b''.join(frames))
        image.extend(code)
    if len(image)>4096: raise ValueError('Compiled music exceeds its private 4 KB score bank')
    (out/'audio-score.bin').write_bytes(bytes(image).ljust(4096,b'\0'))
    (out/'audio-score.inc').write_text('\n'.join(declarations)+'\n')
    return metadata

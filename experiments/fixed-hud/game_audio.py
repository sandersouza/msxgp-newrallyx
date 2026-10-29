"""Compile local contributor melody tables for the resident fixed-HUD adapter.

Derived from the authored enhancement/13-psg-audio compiler; no extracted
game data belongs in this module. build(program, out) returns (bank, metadata).
Generated files must stay under ignored references/ output directories.
"""

from pathlib import Path

PSG_CLOCK = 3579545 / 2


def period(word):
    if type(word) is not int or not 0 <= word <= 65535:
        raise ValueError('Expected an aligned sixteen-bit WSG phase word')
    if not word:
        return 0
    return max(1, min(4095, int(PSG_CLOCK / (16 * word * 96000 / 65536) + .5)))


def volume_curve():
    levels = [0] + [2 ** ((i-15)/2) for i in range(1, 16)]
    return bytes(min(range(16), key=lambda j: abs(levels[j]-i/15)) for i in range(16))

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
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if len(program) < 0x3000:
        raise ValueError("Program image is too short for melody tables")
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
        declarations.append(f'GameAudio_{name.title()}Score EQU ${0x8000+len(image):04x}')
        metadata[name]=dict(address=len(image),bytes=len(code),frames=len(frames),parts=parts)
        (out/f'game-audio-{name}-frames.bin').write_bytes(b''.join(frames))
        image.extend(code)
    if len(image)>4096: raise ValueError('Compiled music exceeds its private 4 KB score bank')
    bank = bytes(image).ljust(16384, b'\xff')
    (out/'game-audio-bank.bin').write_bytes(bank)
    (out/'game-audio-data.inc').write_text('\n'.join(declarations)+'\n')
    return bank, metadata

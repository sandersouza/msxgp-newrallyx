"""Decode observed WSG state, independently of original music/sequencer data.

Register semantics follow pinned MAME namco_wsg_device::pacman_sound_w.
The Rally-X driver clocks it at 96 kHz; a complete waveform cycle has 20 bits
of phase. Wave selection does not change this nominal oscillator frequency.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Voice:
    waveform: int
    step: int
    volume: int

    @property
    def frequency_hz(self):
        return self.step * 96000 / (1 << 20)


def decode_voices(registers):
    if len(registers) != 32 or any(type(v) is not int or not 0 <= v <= 255 for v in registers):
        raise ValueError('Expected exactly 32 WSG byte registers')
    r = [v & 15 for v in registers]
    return tuple(Voice(r[5 + ch * 5] & 7,
                       (r[16] if ch == 0 else 0) +
                       sum(r[17 + ch * 5 + n] << (4 * (n + 1)) for n in range(4)),
                       r[21 + ch * 5]) for ch in range(3))


def summarize(frames, writes, *, boot_frame=0):
    """Frame prefix: index, five gameplay fields and three command bytes.

    The nine prefix fields are frame/mode/round/credit/lives/flags/request0..2.
    Write rows are frame/PC/address/raw byte, in original execution order.
    A write tagged zero precedes the first end-of-frame sample.
    """
    if not frames or not 0 <= boot_frame < len(frames) or any(len(row) != 41 or row[0] != i or
                         any(type(v) is not int or not 0 <= v <= 255 for v in row[1:])
                         for i, row in enumerate(frames, 1)):
        raise ValueError('Incomplete or malformed consecutive audio frame trace')
    last_frame = -1
    rising = 0
    bang = 0
    bang_frames = set()
    request_bits = {at: set() for at in range(0x89f4, 0x89f7)}
    counts = {}
    for row in writes:
        if len(row) != 4 or any(type(v) is not int for v in row):
            raise ValueError('Malformed sound write trace')
        frame, pc, address, value = row
        if (not last_frame <= frame < len(frames) or frame < 0 or
                not 0 <= pc <= 65535 or not 0 <= value <= 255 or
                not (0xa100 <= address <= 0xa11f or address in (0xa180, 0xa182) or
                     address in request_bits)):
            raise ValueError('Invalid, reordered or out-of-capture sound write')
        last_frame = frame
        counts[address] = counts.get(address, 0) + 1
        if address == 0xa180:
            level = value & 1
            rising += int(level and not bang)
            bang = level
            if level:
                bang_frames.add(frame)
        if address in request_bits and frame >= boot_frame:
            request_bits[address].update(bit for bit in range(8) if value & (1 << bit))
    voices = [dict(audible_frames=0, waveforms=set(), minimum_hz=None, maximum_hz=None)
              for _ in range(3)]
    maximum_active = 0
    for row in frames:
        active = 0
        for channel, voice in enumerate(decode_voices(row[9:])):
            if not voice.volume or not voice.step:
                continue
            active += 1
            entry = voices[channel]
            entry['audible_frames'] += 1
            entry['waveforms'].add(voice.waveform)
            hz = voice.frequency_hz
            entry['minimum_hz'] = hz if entry['minimum_hz'] is None else min(hz, entry['minimum_hz'])
            entry['maximum_hz'] = hz if entry['maximum_hz'] is None else max(hz, entry['maximum_hz'])
        maximum_active = max(maximum_active, active)
    for entry in voices:
        entry['waveforms'] = sorted(entry['waveforms'])
    return dict(frames=len(frames), maximum_active_voices=maximum_active, voices=voices,
                boot_complete_frame=boot_frame,
                observed_modes=sorted({row[1] for row in frames if row[0] > boot_frame}),
                observed_internal_rounds=sorted({row[2] for row in frames if row[0] > boot_frame}),
                request_bits_written={f'{at:04x}': sorted(bits) for at, bits in request_bits.items()},
                writes_by_address={f'{at:04x}': count for at, count in sorted(counts.items())},
                bang=dict(rising_edges=rising, active_write_frames=sorted(bang_frames)),
                scope='Observed capture only. Active voice means nonzero volume and phase step; '
                      'nominal frequency is not a claim about dominant harmonic or perceived pitch. '
                      'BANG edges are electrical writes, not a count of gameplay explosions.')

"""Authored PSG conversion tables; no original game bytes or song data."""
PSG_CLOCK = 3579545 / 2


def period(word):
    if type(word) is not int or not 0 <= word <= 65535:
        raise ValueError('Expected an aligned sixteen-bit WSG phase word')
    if not word:
        return 0  # The adapter also forces volume zero for this sentinel.
    frequency = word * 96000 / 65536
    return max(1, min(4095, int(PSG_CLOCK / (16 * frequency) + .5)))


def period_banks():
    raw = b''.join(period(word).to_bytes(2, 'little') for word in range(65536))
    return [raw[i:i+16384] for i in range(0, len(raw), 16384)]


def volume_curve():
    # Nearest voltage to a linear WSG envelope, using the AY's nominal 3 dB
    # steps. Waveform shape and analog output levels remain approximations.
    levels = [0] + [2 ** ((i-15)/2) for i in range(1, 16)]
    return bytes(min(range(16), key=lambda j: abs(levels[j]-i/15)) for i in range(16))

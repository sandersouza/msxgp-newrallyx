"""Exact native cadence, input levels and phase-aligned snapshot comparison."""
from dataclasses import dataclass


# 16.5 ms = 33/2000 seconds at the standard-speed MSX clock.
CLOCK_DIVISOR = 3579545 * 33
INPUT_MASKS = dict(coin=0x80, start=0x40, up=0x20, down=0x10,
                   right=0x08, left=0x04, smoke=0x02)
REGIONS = (('video', 0x8000, 4096), ('work', 0x9800, 2048), ('shadows', 0xa000, 392))


def advance_clock(remainder: int, elapsed_cycles: int) -> tuple[int, int]:
    """Return due logical ticks and retain the exact rational remainder."""
    if (type(remainder) is not int or not 0 <= remainder < CLOCK_DIVISOR
            or type(elapsed_cycles) is not int or elapsed_cycles < 0):
        raise ValueError('Invalid native clock remainder or elapsed cycle count')
    return divmod(remainder + elapsed_cycles * 2000, CLOCK_DIVISOR)


def input_bytes(pressed: frozenset[str], dip: int) -> bytes:
    """Encode levels, leaving coin/start debounce to the original game.

    MAME 0.289 rallyx.cpp: nrallyx inherits rallyx P1/P2 wiring. P2 is
    released with upright cabinet bit set. DIP is already a raw bus byte.
    This function never shares storage with radar/watchdog/sound shadows.
    """
    if (not isinstance(pressed, (set, frozenset))
            or any(key not in INPUT_MASKS for key in pressed)):
        raise ValueError('Unsupported native input name or pressed-key set')
    if type(dip) is not int or not 0 <= dip <= 255:
        raise ValueError('Native DIP must be a raw byte')
    p1 = 0xff
    for key in pressed:
        p1 &= ~INPUT_MASKS[key]
    return bytes((p1, 0xff, dip))


@dataclass(frozen=True)
class Snapshot:
    tick: int
    phase: str
    video: bytes
    work: bytes
    shadows: bytes

    def __post_init__(self):
        if type(self.tick) is not int or self.tick < 0:
            raise ValueError('Snapshot tick must be a nonnegative integer')
        if self.phase not in ('initialization-entry', 'pre-game-irq', 'post-game-irq',
                              'post-game-irq-transfer', 'post-game-irq-collision'):
            raise ValueError('Snapshot phase must identify a reset or game IRQ boundary')
        for name, _, size in REGIONS:
            payload = getattr(self, name)
            if type(payload) is not bytes or len(payload) != size:
                raise ValueError(f'Snapshot {name} must contain exactly {size} immutable bytes')


@dataclass(frozen=True)
class Exclusion:
    address: int
    reason: str
    evidence: str

    def __post_init__(self):
        if (type(self.address) is not int
                or not any(base <= self.address < base + size for _, base, size in REGIONS)):
            raise ValueError('Exclusion address must identify one captured byte')
        if (not isinstance(self.reason, str) or not self.reason.strip()
                or not isinstance(self.evidence, str) or not self.evidence.strip()):
            raise ValueError('Exclusion requires a specific reason and evidence')


def first_difference(expected: Snapshot, actual: Snapshot,
                     exclusions: tuple[Exclusion, ...] = ()) -> dict | None:
    """Return the first differing original address, rejecting misaligned records.

    Equal phase labels are necessary, not proof of acquisition alignment. The
    harness must establish identical reset/input timing and logical boundaries.
    """
    if not isinstance(expected, Snapshot) or not isinstance(actual, Snapshot):
        raise ValueError('Comparison requires complete native snapshots')
    if expected.tick != actual.tick or expected.phase != actual.phase:
        raise ValueError('Cannot compare mismatched native tick or IRQ phase')
    ignored = set()
    for exclusion in exclusions:
        if not isinstance(exclusion, Exclusion):
            raise ValueError('Invalid snapshot exclusion record')
        if exclusion.address in ignored:
            raise ValueError('Duplicate snapshot exclusion address')
        ignored.add(exclusion.address)
    for name, base, _ in REGIONS:
        for offset, (wanted, observed) in enumerate(zip(getattr(expected, name), getattr(actual, name))):
            address = base + offset
            if wanted != observed and address not in ignored:
                return dict(tick=expected.tick, region=name, address=address,
                            expected=wanted, actual=observed)
    return None

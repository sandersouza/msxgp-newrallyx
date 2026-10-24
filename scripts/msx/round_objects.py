"""Compact dynamic object ownership, independent of the background atlas."""
CELLS = 32*56
PACKED_BYTES = CELLS//2


def owners(video, *, relocated=False):
    """One nibble per original cell: flags 1..10, rocks 15, empty 0."""
    if len(video) != 4096:
        raise ValueError('Object ownership requires a complete video state')
    result = bytearray(PACKED_BYTES)
    base = 0xe000 if relocated else 0x8000

    def table(at, count):
        pointer = int.from_bytes(video[at:at+2], 'little')-base
        if not 0 <= pointer <= len(video)-count*2:
            raise ValueError('Object table leaves video state')
        return [int.from_bytes(video[p:p+2], 'little')-0x9800
                for p in range(pointer, pointer+count*2, 2)]

    seen = set()
    def put(cell, owner):
        if cell in seen or not 0 <= cell < CELLS:
            raise ValueError('Object ownership overlaps or leaves the original world')
        seen.add(cell)
        result[cell//2] |= owner << (4*(cell&1))

    for owner, cell in enumerate(table(0x992, 10), 1):
        put(cell, owner)
    count = video[0x251]
    if count > 12:
        raise ValueError('Original rock count exceeds the verified inventory')
    for cell in table(0x996, count):
        put(cell, 15)
    return bytes(result)


def at(packed, cell):
    if len(packed) != PACKED_BYTES or not 0 <= cell < CELLS:
        raise ValueError('Invalid packed object lookup')
    return packed[cell//2] >> (4*(cell&1)) & 15

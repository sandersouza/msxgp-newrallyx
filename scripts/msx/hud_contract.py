"""Read-only reference for the pinned native HUD RAM format, not gameplay rules."""
DIGIT_OFFSETS = (6,7,0,1,2,3)


def native_values(video):
    if len(video)!=4096:
        raise ValueError('Native HUD input must contain 4096 bytes')
    def pointer(address):
        value=int.from_bytes(video[address-0x8000:address-0x8000+2],'little')
        if not 0x8000<=value<=0x8ff8:
            raise ValueError('Native HUD pointer is outside the snapshot')
        return value-0x8000
    def number(offset):
        digits=[video[offset+i]&15 for i in DIGIT_OFFSETS]
        if any(digit>9 for digit in digits):
            raise ValueError('Invalid native score digit')
        return int(''.join(map(str,digits)))
    score=number(pointer(0x8990))
    high=number(0x60)
    lives=max(0,min(9,video[pointer(0x8988)]-1))
    fuel=pointer(0x898e)
    if video[fuel]>=10:
        raise ValueError('Invalid fractional fuel digit')
    return dict(score=score,high=high,lives=lives,fuel=min(video[fuel+1],54)*30//54)

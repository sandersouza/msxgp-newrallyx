; Synthetic only. Main BIOS visible, execute from Page3 RAM; MegaRAM primary1.
; Clobbers AF/HL/IFF, Page2 slots and MegaRAM bank registers/write mode.
; Requires only64KiB system RAM; no game assets or expanded system mapper.
    OUTPUT "probe.bin"
    ORG $c100
Start:
    di
    ld sp,$cf00
    ld a,1
    ld h,$80
    call $0024
    xor a
    out ($8e),a
    ld (0x8000),a
    in a,($8e)
    ld a,$a5
    ld ($8000),a
    out ($8e),a
    ld a,64
    ld ($8000),a
    in a,($8e)
    ld a,$5a
    ld ($8000),a
    out ($8e),a
    ld a,127
    ld ($8000),a
    in a,($8e)
    ld a,$c3
    ld ($9fff),a
    out ($8e),a
    xor a
    ld ($8000),a
    ld a,($8000)
    cp $a5
    jp nz,Failed
    ld a,64
    ld ($8000),a
    ld a,($8000)
    cp $5a
    jp nz,Failed
    ld a,127
    ld ($8000),a
    ld a,($9fff)
    cp $c3
    jp nz,Failed
    ld a,42
    ld ($a000),a
    in a,($8e)
    ld a,$f1
    ld ($a000),a
    out ($8e),a
    xor a
    ld ($8000),a
    ld a,($a000)
    cp $f1
    jp nz,Failed
    ld a,127
    ld ($8000),a
    ld a,($9fff)
    cp $c3
    jp nz,Failed
Passed:
    jr Passed
Failed:
    jr Failed

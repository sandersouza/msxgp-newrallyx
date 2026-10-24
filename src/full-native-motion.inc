; Preserve the original movement path unless an enemy has zero velocity and
; already-normalized fine coordinates. Its position/fraction is then unchanged;
; the original cell-pointer writer still runs. Player centering is never skipped.
Full_NativeMotion:
    ld h,(ix+2)
    ld l,(ix+1)
    ld a,h
    or l
    jr nz,.original
    ld a,iyl
    or a
    jr nz,.original
    ld a,(ix+3)
    or a
    jr z,.vertical
    ld a,(ix+5)
    jr .fine
.vertical:
    ld a,(ix+7)
.fine:
    add a,23
    cp 47
    jr nc,.original
    dec iyl
    jp $815a
.original:
    ld a,(ix+3)
    jp $80fc

; Reserve the mapper segment adjacent to page3, preserving BIOS page0 mapping.
; No game/BIOS path changes slot configuration after this boot-time capture.
Full_CacheInitNative:
    call Full_TurboNative
    xor a
    ld (Full_CacheHeld),a
    in a,($fc)
    ld (Full_CacheMapper),a
    in a,($ff)
    xor 1
    ld (Full_CacheSegment),a
    in a,($a8)
    ld (Full_CachePrimary),a
    ld b,a
    rlca
    rlca
    and 3
    ld c,a
    ld e,a
    ld d,0
    ld a,b
    and $fc
    or c
    ld (Full_CacheRAMPrimary),a
    ld hl,$fcc1
    add hl,de
    ld a,(hl)
    and $80
    ld (Full_CacheExpanded),a
    ret z
    ld a,($ffff)
    cpl
    ld (Full_CacheSub),a
    ld b,a
    rlca
    rlca
    and 3
    ld c,a
    ld a,b
    and $fc
    or c
    ld (Full_CacheRAMSub),a
    ret

; Detect the factory Panasonic MSX2+ turbo. Other machines retain their clock.
; On compatible hardware selector8 is reserved for clock changes. Other
; machines recover the previous selector; SRAM/configuration is untouched.
Full_TurboNative:
    xor a
    ld (Full_TurboEnabled),a
    ld (Full_TurboActive),a
    in a,($40)
    cpl
    ld b,a
    ld a,8
    out ($40),a
    in a,($40)
    cp $f7
    jr nz,.restore
    in a,($41)
    bit 2,a
    jr nz,.restore
    ld a,1
    out ($41),a
    ld (Full_TurboEnabled),a
    xor a
    ld (Full_TurboActive),a
    ret                      ; Own selector8; IRQs can restore base I/O timing.
.restore:
    ld a,b
    out ($40),a
    ret

Full_MarkLogicalSmokeRows:
    ld a,(Smoke_Y)
    sub 10
    and 31
    or Smoke_LogicalRows & 255
    ld l,a
    ld h,Smoke_LogicalRows/256
    ld b,3
.row:
    ld (hl),1
    inc l
    ld a,l
    and 31
    or Smoke_LogicalRows & 255
    ld l,a
    djnz .row
    ret

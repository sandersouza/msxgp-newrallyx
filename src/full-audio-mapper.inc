; PLAYER bank tail. Page0 may already belong to the terrain engine. Interrupts
; see CacheHeld=0 while audio owns Page0 and restore its actual interrupted map.
Audio_ReferenceTick:
    ld a,1
Audio_Enter:
    ld (Audio_ReferenceMode),a
    call Full_TurboOn        ; Sequencing/lookup owns no VDP access deadline.
    di
    in a,($a8)
    push af
    in a,($fc)
    push af
    ld a,($ffff)
    cpl
    push af
    ld a,(Full_CacheHeld)
    push af
    xor a
    ld (Full_CacheHeld),a
    call Full_CacheEnter
    in a,($ff)
    xor 2
    out ($fc),a
    ei
    call Audio_Step
    di
    pop af
    ld (Full_CacheHeld),a
    pop af
    ld b,a
    ld a,(Full_CacheExpanded)
    or a
    jr z,.primary
    ld a,b
    ld ($ffff),a
.primary:
    pop af
    out ($fc),a
    pop af
    out ($a8),a
    ei
    jp Full_TurboOff

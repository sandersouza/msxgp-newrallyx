; Stage 02: original contact-cell geometry plus immutable rock-address lookup.
; Diagnostic events only. Movement, death, score, fuel and guest RAM are untouched.
    IF INCREMENTAL_STAGE >= 2
Rock_Contact EQU $c480          ; zero outside contact; otherwise rock index+1
Rock_Events EQU $c482           ; one event when entering a different contact
Rock_LastCell EQU $c484
Rock_ProbeCell EQU $c486

Rock_Init:
    xor a
    ld hl,Rock_Contact
    ld de,Rock_Contact+1
    ld bc,7
    ld (hl),a
    ldir
    ret

Rock_Update:
    ; The selected original $1774..$17a5 routine reads the native descriptor,
    ; applies its signed-offset +/-12 boundaries and returns the cell in DE.
    ; PLAYER_BANK is already mapped by Player_Advance, as for movement/steering.
    call $9774
    ld (Rock_ProbeCell),de
    IF ROCK_COUNT == 0
    xor a
    ld (Rock_Contact),a
    ret
    ELSE
    ld hl,Rock_Cells
    ld b,ROCK_COUNT
    ld c,1
.next:
    ld a,(hl)
    inc hl
    cp e
    jr nz,.miss
    ld a,(hl)
    cp d
    jr z,.contact
.miss:
    inc hl
    inc c
    djnz .next
    ld c,0
.contact:
    ld a,c
    ld hl,Rock_Contact
    cp (hl)
    ret z
    ld (hl),a
    or a
    ret z
    ld hl,(Rock_Events)
    inc hl
    ld (Rock_Events),hl
    ld hl,(Rock_ProbeCell)
    ld (Rock_LastCell),hl
    ret
    ENDIF
Rock_Cells:
    INCBIN "rock-cells.bin"
    ASSERT $-Rock_Cells == ROCK_COUNT*2
    ENDIF

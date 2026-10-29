; Explicit laboratory population override. Zero is the unmodified native rule.
; Init follows Enemy_Init on initial entry and every restart. Parameters follows
; Parameters_Update, which can restore the native first-stage count after flags.
; APIs clobber AF/BC/DE/HL/IX/IY. No private RAM, graphics, or hardware changes.
; Descriptor stride is 32 but ONLY bytes0..23 belong to each cloned descriptor.
; Bytes24..31 overlap original counters (including score); never copy them.
    ASSERT GAME_TEST_ENEMIES == 0 || GAME_TEST_ENEMIES == 3 || GAME_TEST_ENEMIES == 7

GameMulti_Init:
    IF GAME_TEST_ENEMIES
    ld ix,$e0a8                 ; Preserve the original first enemy at $e088.
    ld iy,GameMulti_Spawns
    ld b,GAME_TEST_ENEMIES-1
.actor:
    push bc
    push ix
    pop de
    ld hl,$e088
    ld bc,24
    ldir
    ; Normal drive state; the unchanged native AI supplies speed and heading.
    ; Start exactly at a road centre, with no stale fractional displacement.
    xor a
    ld (ix+0),a
    ld (ix+1),a
    ld (ix+2),a
    ld (ix+3),a
    ld (ix+4),a
    ld (ix+5),a
    ld (ix+6),a
    ld (ix+7),a
    ld a,(iy+0)
    ld (ix+8),a
    ld a,(iy+1)
    ld (ix+10),a
    inc iy
    inc iy
    ld de,32
    add ix,de
    pop bc
    djnz .actor
    ENDIF
GameMulti_Parameters:
    IF GAME_TEST_ENEMIES
    ld a,GAME_TEST_ENEMIES
    ld ($e24e),a
    ENDIF
    ret

    IF GAME_TEST_ENEMIES
GameMulti_Spawns:
    INCBIN "game-multi-spawns.bin"
GameMulti_SpawnsEnd:
    ASSERT GameMulti_SpawnsEnd-GameMulti_Spawns == (GAME_TEST_ENEMIES-1)*2
    ENDIF

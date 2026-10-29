; New test controls are completely absent from a TEST_MODE=0 build.
GameSession_TestHeld EQU $c0ed
GameSession_Invulnerable EQU $c0ee
    IF SESSION_TEST_MODE
GameSession_TestKeys:
    ; A=row7: Return. '=' is row1bit3 internationally or Shift+row1bit2
    ; on the target Japanese MSX. Holding either key produces one edge.
    and $80
    ld c,a
    push bc
    ld a,1
    call read_keys
    pop bc
    ld b,a
    bit 3,b
    jr nz,.equal
    bit 2,b
    jr z,.mask
    push bc
    ld a,6
    call read_keys
    pop bc
    bit 0,a
    jr z,.mask
.equal:
    set 1,c
.mask:
    ld a,(GameSession_TestHeld)
    cpl
    and c
    ld b,a
    ld a,c
    ld (GameSession_TestHeld),a
    bit 1,b
    jr z,.next
    ld a,(GameSession_Invulnerable)
    xor 1
    ld (GameSession_Invulnerable),a
.next:
    bit 7,b
    ret z
    ld a,(Death_State)
    or a
    ret nz
    ld a,(Full_Attract)
    or a
    ret nz
    ld a,1
    ld (Full_ChallengeBypass),a
    jp GameSession_NextRound
    ENDIF

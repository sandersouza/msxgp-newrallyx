Game_State EQU $c040           ; 0 active, 1 game over, 2 first stage completed
Game_Due EQU $c041
Game_FlagSeen EQU $c042
Game_SmokeSeen EQU $c043
Game_DeathSeen EQU $c045
Game_RoundSeen EQU $c046
Game_ActorCount EQU $c047
Game_ActorSource EQU $c048
Game_ActorKind EQU $c04a
Game_ActorRemaining EQU $c04b
Game_ActorX EQU $c04c
Game_ActorY EQU $c04e
Game_SmokeChanged EQU $c051
paused EQU $c050
Game_WorldChanged EQU $c080   ; generation consumed by SCREEN4 world overlay
Game_ActorsBase EQU $c800
driving EQU $c400
player_animation EQU $c404
player_x EQU $c405
player_y EQU $c407
player_native_ticks EQU $c440
player_pending_x EQU $c450
player_pending_y EQU $c452
Enemy_HitAddress EQU $c63c
VIEWPORT_HALF EQU 104
STAGE_COLUMNS EQU 102
STAGE_ROWS EQU 174
PLAYER_BANK EQU GAME_NATIVE_BANK
Full_AITable0 EQU $d2a8
Full_AITable1 EQU $d2b6
Full_AIBefore EQU $d2c4
Full_AITick EQU $d2cb

Player_AxisY:
    ld c,(hl)
    ld h,0
    ld l,a
    call Player_Cell
    ld a,c
    neg
    jr Player_Offset
Player_Axis:
    ld c,(hl)
    ld h,0
    ld l,a
    call Player_Cell
    ld a,c
Player_Offset:
    ld e,a
    ld d,0
    bit 7,a
    jr z,.positive
    dec d
.positive:
    add hl,de
    ret
Player_Cell:
    add hl,hl
    add hl,hl
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ld de,36
    add hl,de
    ret
Game_Actors:
    ld ix,Game_ActorsBase
    ld iy,$e068
    xor a
    ld (Game_ActorKind),a
    ld a,($e24e)
    inc a
    cp 9
    jr c,.count
    ld a,8
.count:
    ld (Game_ActorCount),a
    ld b,8
.actor:
    push bc
    ld (ix+5),255
    ld a,(Game_ActorKind)
    ld c,a
    ld a,(Game_ActorCount)
    cp c
    jr z,.next
    jr c,.next
    ld a,(iy+8)
    push iy
    pop hl
    ld de,5
    add hl,de
    call Player_Axis
    ld de,(cx)
    or a
    sbc hl,de
    ld de,-8
    add hl,de
    ld (ix+0),l
    ld (ix+1),h
    ld a,(iy+10)
    push iy
    pop hl
    ld de,7
    add hl,de
    call Player_AxisY
    ld de,(cy)
    or a
    sbc hl,de
    ld de,-8
    add hl,de
    ld (ix+2),l
    ld (ix+3),h
    ld a,(iy+15)
    ld l,a
    ld h,0
    ld de,Game_AnimationFlags
    add hl,de
    ld a,(hl)
    cp 12
    jr nc,.next
    ld (ix+4),a
    ld a,(Game_ActorKind)
    or a
    jr nz,.enemy
    ld a,(Death_State)
    or a
    jr nz,.next
    xor a
    jr .kind
.enemy:
    ld a,1
.kind:
    ld (ix+5),a
.next:
    ld de,6
    add ix,de
    ld de,32
    add iy,de
    ld hl,Game_ActorKind
    inc (hl)
    pop bc
    dec b
    jp nz,.actor
    ret


Game_AnimationFlags:
 INCBIN "player-flags.bin"

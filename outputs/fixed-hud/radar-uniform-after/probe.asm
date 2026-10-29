 DEFINE GAME_RADAR_UNIFORM_SOURCE
 OUTPUT "probe.rom"
fx EQU $c004
fy EQU $c005
dotx EQU $c012
doty EQU $c013
names EQU $d400
GAME_RADAR_COLOR EQU $c1
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
 in a,($a8)
 rlca
 rlca
 and 3
 ld c,a
 ld b,0
 ld hl,$fcc1
 add hl,bc
 bit 7,(hl)
 jr z,.primary
 ld a,($ffff)
 cpl
 ld b,a
 rlca
 rlca
 and 3
 ld d,a
 ld a,b
 and $fc
 or d
 ld ($ffff),a
.primary:
 in a,($a8)
 and $fc
 or c
 out ($a8),a
 ld a,4
 out ($fc),a
main:
 jp main
Game_WorldGeneration EQU $c080
Game_LastWorldGeneration EQU $c081
Game_SmokeCount EQU $c082
Game_PatchX EQU $c084
Game_PatchY EQU $c085
Game_PatchID EQU $c086
Game_RadarCount EQU $c087
Game_RadarX EQU $c088
Game_RadarY EQU $c089
Game_RadarIndex EQU $c08a
Game_RadarEraseFlag EQU $c08b
Game_RadarName EQU $c08c
Game_LastSmokeChanged EQU $c090
Game_PrevDeath EQU $c091
Game_PrevDeathX EQU $c092
Game_PrevDeathY EQU $c093
Game_LastPatchCol EQU $c094
Game_LastPatchRow EQU $c095
Game_RadarAddresses EQU $2300
Game_RadarPatterns EQU $2400
Game_RadarColors EQU $2500
Game_SmokeList EQU $0800

Baseline_Radar:
    IFDEF GAMEPLAY_CONFIGURED
    IF GAME_RENDER_OPT
    jp GameRadarFast_Draw
    ENDIF
    ENDIF
    xor a
    ld (Game_RadarCount),a
    ; Phase-local character variants retain exact collected-flag pixels.
    ; Only live actor dots still need a copied character in RAM.
    call $a700
    ld ix,$e068
    ld b,8
.actors:
    push bc
    ld a,b
    cp 8
    jr z,.actor
    ld a,8
    sub b
    ld c,a
    ld a,($e24e)
    cp c
    jr c,.next_actor
.actor:
    ; Original inactive descriptors may be parked below the maze. They have
    ; no radar position until entering the native 32x56 world bounds.
    ld a,(ix+10)
    cp 56
    jr nc,.next_actor
    ld a,(ix+8)
    cp 32
    jr nc,.next_actor
    add a,8
    ld (Game_RadarX),a
    ld a,(ix+10)
    call Baseline_RadarCellY
    call Baseline_RadarDot
.next_actor:
    ld de,32
    add ix,de
    pop bc
    djnz .actors
    ret
Baseline_RadarCellY:
    ld l,a
    ld h,0
    ld de,Game_RadarCellRows
    add hl,de
    ld a,(hl)
    ld (Game_RadarY),a
    ret
Baseline_RadarErase:
    ld a,1
    ld (Game_RadarEraseFlag),a
    jr Baseline_RadarPoint
Baseline_RadarDot:
    xor a
    ld (Game_RadarEraseFlag),a
Baseline_RadarPoint:
    ld a,(Game_RadarX)
    ld b,a
    ld a,(fx)
    add a,b
    ld (dotx),a
    ld a,(Game_RadarY)
    ld b,a
    ld a,(fy)
    add a,b
    ld (doty),a
    and $f8
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(dotx)
    REPT 3
    rrca
    ENDR
    and 7
    add a,26
    ld e,a
    ld d,0
    add hl,de
    ld de,names
    add hl,de
    ld (Game_RadarName),hl
    ld a,(hl)
    cp 64
    jr c,.new
    cp 96
    jr nc,.new
    sub 64
    jr .index
.new:
    ld a,(Game_RadarCount)
    cp 32
    ret nc
    ld (Game_RadarIndex),a
    inc a
    ld (Game_RadarCount),a
    ld a,(hl)
    sub 96
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    push hl
    ld a,(Game_RadarIndex)
    ld l,a
    ld h,0
    add hl,hl
    ld de,Game_RadarAddresses
    add hl,de
    ld de,(Game_RadarName)
    ld (hl),e
    inc hl
    ld (hl),d
    ld a,(Game_RadarIndex)
    add a,64
    ex de,hl
    ld (hl),a
    pop hl
    push hl
    ld de,$8100
    add hl,de
    push hl
    ld a,(Game_RadarIndex)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,Game_RadarPatterns
    add hl,de
    ex de,hl
    pop hl
    ld bc,8
    ldir
    pop hl
    ld de,$8500
    add hl,de
    push hl
    ld a,(Game_RadarIndex)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,Game_RadarColors
    add hl,de
    ex de,hl
    pop hl
    ld bc,8
    ldir
    ld a,(Game_RadarIndex)
.index:
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,(doty)
    and 7
    ld e,a
    ld d,0
    add hl,de
    ld de,Game_RadarPatterns
    add hl,de
    push hl
    ld a,(dotx)
    and 7
    ld b,a
    ld a,$80
    jr z,.mask
.rotate:
    rrca
    djnz .rotate
.mask:
    ld c,a
    ld a,GAME_RADAR_COLOR
    ld de,$100
    add hl,de
    cp (hl)
    ld (hl),a
    pop hl
    jr z,.merge
    ld (hl),0
.merge:
    ld a,(Game_RadarEraseFlag)
    or a
    ld a,(hl)
    jr z,.set
    ld b,a
    ld a,c
    cpl
    and b
    ld (hl),a
    ret
.set:
    or c
    ld (hl),a
    ret

 INCLUDE "game-radar-fast.inc"
Game_RadarCellRows:
 INCBIN "rows.bin"
 ASSERT $ < $8000
 defs $8000-$,$ff

; Synthetic consumer of the real HUD API. Generated inputs contain no bundled game data.
    OUTPUT "hud-api-driver.bin"
    INCLUDE "hud-imports.inc"
    ORG $7800
command EQU $c3a0
hold EQU $c3a1
result EQU $c3a2
carry_expected EQU $c3a3
command_a EQU $c3a4
command_bc EQU $c3a5
command_hl EQU $c3a7
wait_frames EQU $c3a9
call_stub EQU $c3b0
registers EQU $c3c0
driver:
    ld a,(paused)
    or a
    jr nz,.initialized
    xor a
    ld (command),a
    ld (hold),a
.initialized:
    ld a,1
    ld (paused),a
    ld a,(hold)
    or a
    jr z,.command
    dec a
    ld (hold),a
    ret
.command:
    ld a,(command)
    cp COMMANDS
    ret nc
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$8000
    add hl,de
    ld a,TEST_DATA_BANK
    ld ($7000),a
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld (call_stub+1),de
    ld a,(hl)
    inc hl
    ld (command_a),a
    ld c,(hl)
    inc hl
    ld b,(hl)
    inc hl
    ld (command_bc),bc
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld (command_hl),de
    ld a,(hl)
    ld (carry_expected),a
    inc hl
    ld a,(hl)
    ld (wait_frames),a
    ; A native snapshot fixture is copied to E000 only in the test consumer.
    ld a,d
    cp $90
    jr c,.prepared
    ld a,d
    sub $90
    add a,TEST_DATA_BANK+1
    ld ($7000),a
    ld hl,$8000
    ld de,$e000
    ld bc,$1000
    ldir
    ld hl,$e000
    ld (command_hl),hl
.prepared:
    ld a,$cd
    ld (call_stub),a
    ld a,$c9
    ld (call_stub+3),a
    exx
    ld bc,$1111
    ld de,$2222
    ld hl,$3333
    exx
    ld hl,$4455
    push hl
    pop af
    ex af,af'
    ld bc,(command_bc)
    ld de,$5678
    ld hl,(command_hl)
    ld ix,$9abc
    ld iy,$def0
    ld a,(command_a)
    ld (registers+12),sp
    call call_stub
    ld (registers+14),sp
    ld (registers+0),bc
    ld (registers+2),de
    ld (registers+4),hl
    ld (registers+6),ix
    ld (registers+8),iy
    push af
    pop hl
    ld (registers+10),hl
    exx
    ld (registers+16),bc
    ld (registers+18),de
    ld (registers+20),hl
    exx
    ex af,af'
    push af
    pop hl
    ld (registers+22),hl
    ex af,af'
    ld a,(command)
    inc a
    ld (command),a
    ld a,(wait_frames)
    ld (hold),a
    ret
    ASSERT $ <= $8000

; Standalone V9958 SCREEN 4 probe. No sprites and no VDP commands.
    OUTPUT "fixed-hud.rom"
    MACRO reg number,value
    ld a,value
    out ($99),a
    ld a,$80+number
    out ($99),a
    ENDM
cx EQU $c000
cy EQU $c002
fx EQU $c004
fy EQU $c005
back EQU $c006
count EQU $c007
maprow EQU $c008
mapcol EQU $c009
speed EQU $c00a
keys EQU $c00b
ready EQU $c00c
frames EQU $c00d
oldcol EQU $c00e
oldrow EQU $c00f
hudptr EQU $c010
dotx EQU $c012
doty EQU $c013
seen EQU $c018
phase EQU $c01d
loaded_phase EQU $c01e
prior_phase EQU $c020
clock_ticks EQU $c022
input_tick EQU $c024
elapsed_ticks EQU $c026
ring_x EQU $c030
ring_y EQU $c031
ring_length EQU $c032
ring_dx EQU $c033
ring_dy EQU $c034
ring_first EQU $c035
ring_rest EQU $c036
ring_target EQU $c038
ring_seen_ptr EQU $c03a
world_ids EQU $d800
ring_pointers EQU $ce00
hud_page EQU $c03e
boundary_ids EQU $c920
names EQU $c400
dotpat EQU $c900
    ORG $4000
    db "AB"
    dw boot,0,0,0,0,0,0
boot:
    di
    ld sp,$f380
    call $0138
    rrca
    rrca
    and 3
    ld c,a
    ld b,0
    ld hl,$fcc1
    add hl,bc
    ld a,(hl)
    and $80
    or c
    ld c,a
    ld de,4
    add hl,de
    ld a,(hl)
    and $0c
    or c
    ld h,$80
    call $0024
    ld a,4
    call $005f
    di
    reg 1,$02
    reg 0,4
    reg 8,$2a
    reg 9,$82
    reg 18,0
    reg 25,2
    reg 26,0
    reg 27,0
    reg 23,0
    reg 7,11
    reg 16,0
    ld hl,palette
    ld bc,$209a
    otir
    xor a
    ld hl,$c000
    ld de,$c001
    ld bc,$1000
    ld (hl),a
    ldir
    ; A minimal IM2 VBlank clock keeps control speed independent of render cost.
    ld hl,$d000
    ld de,$d001
    ld bc,256
    ld (hl),$d2
    ldir
    ld a,$c3
    ld ($d2d2),a
    ld hl,clock_irq
    ld ($d2d3),hl
    ld a,$d0
    ld i,a
    im 2
    reg 15,0
    ld hl,264
    ld (cx),hl
    ld hl,1032
    ld (cy),hl
    ld a,$ff
    ld (loaded_phase),a
    ld (loaded_phase+1),a
    ld (oldcol),a
    ld (oldrow),a
    ld hl,seen
    ld (hl),a
    inc hl
    ld (hl),a
    inc hl
    ld (hl),a
    inc hl
    ld (hl),a
    ; Initialize both independent, shared-quarter pattern/color tables.
    ld a,1
    ld ($7000),a
    ld hl,$0000
    call address
    ld hl,$8000
    ld de,2048
    call upload
    ld hl,$4000
    call address
    ld hl,$8800
    ld de,2048
    call upload
    ld hl,$8000
    call address
    ld hl,$8000
    ld de,2048
    call upload
    ld hl,$c000
    call address
    ld hl,$8800
    ld de,2048
    call upload
    call render
    ; Enable the first picture at a fresh blanking edge as well.
    di
    reg 15,2
.boot_leave:
    in a,($99)
    and $40
    jr nz,.boot_leave
.boot_enter:
    in a,($99)
    and $40
    jr z,.boot_enter
    reg 15,0
    in a,($99)
    call commit
    reg 1,$62
    ld a,1
    ld (ready),a
loop:
    call input
    call render
    call wait_blank
    call commit
frame_done:
    ld hl,frames
    inc (hl)
    jp loop

; Wake at a fresh VBlank, then commit the complete prepared table set.
wait_blank:
    ei
    halt
    ret

commit:
    di
    ld a,(back)
    or a
    jr z,.zero
    reg 4,16
    reg 3,$1f
    reg 10,3
    reg 2,9
    jr .scroll
.zero:
    reg 4,0
    reg 3,$1f
    reg 10,1
    reg 2,8
.scroll:
    ld a,(cy)
    out ($99),a
    ld a,$97
    out ($99),a
    ld a,(mapcol)
    ld b,a
    ld a,(fx)
    or a
    ld a,b
    jr z,.coarse
    inc a
.coarse:
    and 31
    out ($99),a
    ld a,$9a
    out ($99),a
    ld a,(fx)
    neg
    and 7
    out ($99),a
    ld a,$9b
    out ($99),a
    ld a,(back)
    xor 1
    ld (back),a
    ei
    ret

input:
    ld hl,(clock_ticks)
    ld de,(input_tick)
    ld (input_tick),hl
    or a
    sbc hl,de
    ld a,l
    or a
    jr nz,.elapsed
    inc a
.elapsed:
    ld (elapsed_ticks),a
    in a,($aa)
    and $f0
    or 6
    out ($aa),a
    in a,($a9)
    and 1
    xor 1
    inc a
    ld (speed),a
    in a,($aa)
    and $f0
    or 8
    out ($aa),a
    in a,($a9)
    cpl
    ld (keys),a
    ld hl,(cx)
    ld a,(speed)
    ld b,a
    ld a,(elapsed_ticks)
    dec b
    jr z,.distance
    add a,a
.distance:
    ld e,a
    ld d,0
    ld a,(keys)
    bit 4,a
    call nz,subtract
    ld a,(keys)
    bit 7,a
    jr z,.xlimit
    add hl,de
.xlimit:
    ld bc,616
    call clamp
    ld (cx),hl
    ld hl,(cy)
    ld a,(keys)
    bit 5,a
    call nz,subtract
    ld a,(keys)
    bit 6,a
    jr z,.ylimit
    add hl,de
.ylimit:
    ld bc,1180
    call clamp
    ld (cy),hl
    ret
subtract:
    or a
    sbc hl,de
    ret
clamp:
    bit 7,h
    jr z,.maximum
    ld hl,0
    ret
.maximum:
    push hl
    or a
    sbc hl,bc
    pop hl
    ret c
    ld h,b
    ld l,c
    ret

render:
    ld hl,(cx)
    ld a,l
    and 7
    ld (fx),a
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ld a,l
    ld (mapcol),a
    ld hl,(cy)
    ld a,l
    and 7
    ld (fy),a
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ld a,l
    ld (maprow),a
    call Ring_Prepare
.hud:
    ; Phase bank: padded 256 names, 1024 pattern bytes, 1024 color bytes.
    ld a,(fy)
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,(fx)
    add a,b
    ld (phase),a
    add a,4
    ld ($7000),a
    ld hl,$8900
    ld a,(hl)
    ld (count),a
    call $a300
    call left_names
    call boundaries
    call radar
    ; Transfer to the inactive table set, never move existing VRAM blocks.
    call hud_upload
    jp .hud_uploaded
hud_upload:
    ld hl,loaded_phase
    ld a,(back)
    or a
    jr z,.previous
    inc hl
.previous:
    ld a,(hl)
    ld (prior_phase),a
    ld b,a
    ld a,(phase)
    ld (hl),a
    ld a,b
    cp $ff
    jr z,.full
    ld l,a
    ld h,0
    ld e,l
    ld d,h
    add hl,hl
    add hl,de
    ld de,$a600
    add hl,de
    ld a,(hl)
    or a
    jp z,.full
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    ex de,hl
    ld ($7000),a
    ld a,$ff
    ld (hud_page),a
.packet:
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld a,(hl)
    inc hl
    or a
    jr z,.done
    ld b,a
    push hl
    ex de,hl
    ld a,h
    and $40
    rlca
    rlca
    ld c,a
    ld a,(back)
    add a,a
    or c
    ld c,a
    ld a,(hud_page)
    cp c
    di
    jr z,.target
    ld a,c
    ld (hud_page),a
    out ($99),a
    ld a,$8e
    out ($99),a
.target:
    ld a,l
    out ($99),a
    ld a,h
    or $40
    out ($99),a
    ei
    pop hl
    ld c,$98
    otir
    jr .packet
.done:
    ld a,(phase)
    add a,4
    ld ($7000),a
    ret
.full:
    ld hl,$0200
    ld a,(back)
    or a
    jr z,.pattern
    set 7,h
.pattern:
    call address
    ld hl,$8100
    call length
    call upload
    ld hl,$4200
    ld a,(back)
    or a
    jr z,.color
    set 7,h
.color:
    call address
    ld hl,$8500
    call length
    call upload
    ret
render.hud_uploaded:
    ld a,(prior_phase)
    cp $ff
    jr z,.boundary_needed
    and 7
    ld b,a
    ld a,(fx)
    cp b
    jr z,.no_boundary
.boundary_needed:
    ld hl,$0600
    ld a,(back)
    or a
    jr z,.boundary_p
    set 7,h
.boundary_p:
    call address
    ld hl,$8b00
    ld a,($8d00)
    call tile_bytes
    call upload
    ld hl,$4600
    ld a,(back)
    or a
    jr z,.boundary_c
    set 7,h
.boundary_c:
    call address
    ld hl,$8c00
    ld a,($8d00)
    call tile_bytes
    call upload
    ld hl,$06e0
    ld a,(back)
    or a
    jr z,.mixed_p
    set 7,h
.mixed_p:
    call address
    ld hl,$8f00
    ld a,($9100)
    call tile_bytes
    call upload
    ld hl,$46e0
    ld a,(back)
    or a
    jr z,.mixed_c
    set 7,h
.mixed_c:
    call address
    ld hl,$9000
    ld a,($9100)
    call tile_bytes
    call upload
.no_boundary:
.no_left:
    ld hl,$07c0
    ld a,(back)
    or a
    jr z,.dotp
    set 7,h
.dotp:
    call address
    ld hl,dotpat
    ld de,8
    call upload
    ld hl,$47c0
    ld a,(back)
    or a
    jr z,.dotc
    set 7,h
.dotc:
    call address
    ld hl,dotpat+8
    ld de,8
    call upload
    call Ring_UploadNames
render_done:
    ret
    INCLUDE "ring.inc"
length:
    ld a,(count)
    ld e,a
    ld d,0
    sla e
    rl d
    sla e
    rl d
    sla e
    rl d
    ret
tile_bytes:
    ld e,a
    ld d,0
    sla e
    rl d
    sla e
    rl d
    sla e
    rl d
    ret
left_length:
    ld a,($a200)
    ld e,a
    ld d,0
    sla e
    rl d
    sla e
    rl d
    sla e
    rl d
    ret

boundaries:
    ld h,$8a
    DUP 28, row
    ld a,(boundary_ids+row*3)
    ld l,a
    ld a,(hl)
    ld (names+row*32+24),a
    EDUP
    ld h,$8e
    DUP 28, row
    ld a,(boundary_ids+row*3+1)
    ld l,a
    ld a,(hl)
    ld (names+row*32+25),a
    EDUP
    ret

left_names:
    ; The masked first column supplies the wrapped seventh HUD guard cell.
    DUP 28, row
    ld a,($8000+row*7+6)
    ld (names+row*32),a
    EDUP
    ret

radar:
    ld hl,(cx)
    ld de,radar_x
    add hl,de
    ld a,(fx)
    add a,(hl)
    ld (dotx),a
    ld hl,(cy)
    ld de,radar_y
    add hl,de
    ld a,(fy)
    add a,(hl)
    ld (doty),a
    ; Find the pre-shifted background tile under the player dot.
    rrca
    rrca
    rrca
    and 31
    ld l,a
    ld h,0
    ld d,h
    ld e,l
    add hl,hl
    add hl,hl
    add hl,hl
    or a
    sbc hl,de
    ld a,(dotx)
    rrca
    rrca
    rrca
    and 7
    ld e,a
    add hl,de
    ld de,$8000
    add hl,de
    ld a,(hl)
    sub 64
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    push hl
    ld de,$8100
    add hl,de
    ld de,dotpat
    ld bc,8
    ldir
    pop hl
    ld de,$8500
    add hl,de
    ld de,dotpat+8
    ld bc,8
    ldir
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
    ld a,(doty)
    and 7
    ld e,a
    ld d,0
    ld hl,dotpat
    add hl,de
    push hl
    ld de,8
    add hl,de
    ld a,(hl)
    cp $11
    pop hl
    jr nz,.existing
    ld (hl),0
.existing:
    ld a,(hl)
    or c
    ld (hl),a
    ld de,8
    add hl,de
    ld (hl),$c1
    ld a,(doty)
    and $f8
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(dotx)
    rrca
    rrca
    rrca
    and 7
    add a,26
    and 31
    ld e,a
    ld d,0
    add hl,de
    ld de,names
    add hl,de
    ld (hl),248
    ret

; HL is a 16-bit VRAM address. All traffic is ROM/RAM -> VRAM.
address:
    di
    ld a,h
    rlca
    rlca
    and 3
    out ($99),a
    ld a,$8e
    out ($99),a
    ld a,l
    out ($99),a
    ld a,h
    and $3f
    or $40
    out ($99),a
    ei
    ret

clock_irq:
    push af
    in a,($99)
    bit 7,a
    jr z,.done
    push hl
    ld hl,(clock_ticks)
    inc hl
    ld (clock_ticks),hl
    pop hl
.done:
    pop af
    ei
    reti
upload:
    ld c,$98
    ld a,d
    or a
    jr z,.tail
.page:
    ld b,0
    otir
    dec d
    jr nz,.page
.tail:
    ld a,e
    or a
    ret z
    ld b,e
    otir
    ret
palette:
    INCBIN "palette.bin"
radar_x:
    INCBIN "radar-x.bin"
radar_y:
    INCBIN "radar-y.bin"
    ASSERT $ < $8000
    defs $8000-$,$ff

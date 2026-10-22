; Renderer integration contract: src/hud-api.inc and docs/hud.md.
HUD_Init:
    ld b,14
    ld a,7
    call register
    xor a
    out ($99),a
    ld a,$78
    out ($99),a
    ld hl,patterns
    ld de,PATTERN_BYTES
    call upload
    xor a
    out ($99),a
    ld a,$74
    out ($99),a
    ld hl,sprite_colors
    ld de,SPRITE_COLOR_BYTES
    call upload
    ; Start with the bare white frame. All game points arrive through the API;
    ; separate colored markers never recolor an outer-border scanline.
    ld hl,radar_patterns
    ld a,$a0
    out ($99),a
    ld a,$78
    out ($99),a
    ld de,768
    call upload
    ld b,14
    ld a,4
    call register
    xor a
    out ($99),a
    ld a,$40
    out ($99),a
    ld a,HUD_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,1024
    call upload
    ld de,1024
.separator:
    ld a,BLACK*17
    out ($98),a
    dec de
    ld a,d
    or e
    jr nz,.separator
    ld hl,attributes_template
    ld de,sat
    ld bc,SAT_BYTES
    ldir
    jp HUD_InitState

; Reusable SCREEN 5 HUD implementation. Public entries/state: hud-api.inc.
; Rendering calls run in the renderer's scheduled VDP phases with DI.
update_lives:
    ; The hardware left mask owns the only hidden edge; SAT starts with radar.
    ld hl,sat
    ld a,(scroll_y)
    add a,RADAR_Y-1
    ld (sprite_y),a
    ld a,20
    ld (sprite_base),a
    ld b,4
.radar_band:
    push bc
    ld a,(sprite_y)
    ld d,a
    ld a,(sprite_base)
    ld e,a
    ld b,3
    ld c,RADAR_X
.radar_column:
    ; Stagger columns by one scanline. Their 15-row bands then never
    ; overlap on the same row, keeping the complete scene at <=8 sprites/line.
    ld a,c
    sub RADAR_X
    rrca
    rrca
    rrca
    rrca
    add a,d
    sub 2
    cp 216
    jr nz,.column_safe
    dec a
    push de
    ld d,a
    ld a,e
    add a,48
    ld e,a
    ld (hl),d
    jr .column_pattern
.column_safe:
    push de
    ld (hl),a
.column_pattern:
    inc hl
    ld (hl),c
    inc hl
    ld (hl),e
    inc hl
    ld (hl),0
    inc hl
    pop de
    ld a,c
    add a,16
    ld c,a
    ld a,e
    add a,4
    ld e,a
    djnz .radar_column
    ld a,(sprite_y)
    add a,15
    ld (sprite_y),a
    ld a,(sprite_base)
    add a,12
    ld (sprite_base),a
    pop bc
    djnz .radar_band
    ld a,(point_x)
    ld d,a
    ld a,(point_y)
    ld e,a
    ld c,116
    call point_attribute
    ld a,(enemy_x)
    ld d,a
    ld a,(enemy_y)
    ld e,a
    ld c,124
    call point_attribute
    ld de,fuel_sat
    ld b,12
.fuel:
    ld a,(de)
    ld (hl),a
    inc de
    inc hl
    djnz .fuel
    ld (hl),216
    ld b,14
    ld a,7
    call register
    xor a
    out ($99),a
    ld a,$76
    out ($99),a
    ld hl,sat
    ld bc,SAT_BYTES*256+$98
    otir
    ret

point_attribute:
    ld a,e
    and $f8
    add a,RADAR_Y-1
    ld e,a
    ld a,(scroll_y)
    add a,e
    cp 216
    jr nz,.safe
    dec a
    inc c
    inc c
    inc c
    inc c
.safe:
    ld (hl),a
    inc hl
    ld a,d
    and $f8
    add a,RADAR_X
    ld (hl),a
    inc hl
    ld (hl),c
    inc hl
    ld (hl),0
    inc hl
    ret

update_radar:
    ld a,(hud_enemy_x)
    ld b,a
    ld a,(hud_enemy_drawn_x)
    cp b
    jr nz,.enemy
    ld a,(hud_enemy_y)
    ld b,a
    ld a,(hud_enemy_drawn_y)
    cp b
    jr z,.player
.enemy:
    ld a,(hud_enemy_x)
    ld (enemy_x),a
    ld (hud_enemy_drawn_x),a
    ld d,a
    ld a,(hud_enemy_y)
    ld (enemy_y),a
    ld (hud_enemy_drawn_y),a
    ld e,a
    call draw_point
    vdp_write 14,7
    ld a,$e0
    out ($99),a
    ld a,$7b
    out ($99),a
    ld hl,point_buffer
    ld bc,$4098
    otir
.player:
    ld a,(hud_force)
    or a
    jr nz,.force
    ld a,(radar_clock)
    and 1
    ret nz
.force:
    ld a,(hud_player_x)
    ld d,a
    ld a,(hud_player_y)
    ld e,a
    ld a,(radar_clock)
    and 16
    ld b,WHITE
    jr z,.color
    ld b,BLACK
.color:
    ld a,(point_x)
    cp d
    jr nz,.dirty
    ld a,(point_y)
    cp e
    jr nz,.dirty
    ld a,(point_color)
    cp b
    ret z
.dirty:
    ld a,b
    ld (point_color),a
    ld a,d
    ld (point_x),a
    ld a,e
    ld (point_y),a
    call draw_point
    ld b,14
    ld a,7
    call register
    ld a,$a0
    out ($99),a
    ld a,$7b
    out ($99),a
    ld hl,point_buffer
    ld bc,$4098
    otir
    ld a,PLAYER_COLORS&255
    out ($99),a
    ld a,$40+((PLAYER_COLORS>>8)&$3f)
    out ($99),a
    ld a,(point_color)
    or $20
    ld b,16
.colors:
    out ($98),a
    nop
    djnz .colors
    ret

; Rebuild both 16x16 phases from coordinates, including the x=7 byte crossing.
; Only 64 pattern bytes and one 16-byte color row change when the marker moves.
draw_point:
    push de
    ld hl,point_buffer
    ld de,point_buffer+1
    ld bc,63
    ld (hl),0
    ldir
    pop de
    ld a,d
    cp 255
    ret z
    and 7
    add a,a
    ld l,a
    ld h,0
    ld bc,point_masks
    add hl,bc
    ld c,(hl)
    inc hl
    ld b,(hl)
    ld a,e
    and 7
    ld e,a
    ld d,0
    ld hl,point_buffer
    add hl,de
    call point_rows
    ld hl,point_buffer+33
    add hl,de
point_rows:
    ld (hl),c
    inc hl
    ld (hl),c
    push de
    ld de,15
    add hl,de
    pop de
    ld (hl),b
    inc hl
    ld (hl),b
    ret
point_masks:
    db $c0,0,$60,0,$30,0,$18,0,$0c,0,6,0,3,0,1,$80

update_fuel_sat:
    ld a,(scroll_y)
    add a,FUEL_Y-1
    ld d,a
    ld e,132
    ld c,140
    cp 216
    jr nz,.safe
    dec d
    ld e,136
    ld c,148
.safe:
    ld hl,fuel_sat
    ld (hl),d
    inc hl
    ld (hl),RADAR_X
    inc hl
    ld (hl),e
    inc hl
    ld (hl),0
    inc hl
    ld (hl),d
    inc hl
    ld (hl),RADAR_X+16
    inc hl
    ld (hl),c
    inc hl
    ld (hl),0
    inc hl
    ld (hl),d
    inc hl
    ld (hl),RADAR_X+32
    inc hl
    ld a,c
    add a,4
    ld (hl),a
    inc hl
    ld (hl),0
    ret

update_fuel:
    ld a,(hud_fuel_pixels)
    ld c,a
    ld a,(hud_fuel_drawn)
    cp c
    ret z
    ld a,(hud_force)
    or a
    jr nz,.due
    ld a,(fuel_at)
    ld b,a
    ld a,(ticks)
    sub b
    ld b,a
    ld a,(cadence)
    cp b
    jr z,.due
    ret nc
.due:
    ld a,HUD_DATA_BANK
    ld ($7000),a
    ld a,c
    ld (hud_fuel_drawn),a
    ld hl,0
    ld h,a
    srl h
    rr l                      ; level * 128
    ld de,fuel_states
    add hl,de
    ld b,14
    ld a,7
    call register
    ld a,$60                  ; pattern 140, two columns and both Y phases
    out ($99),a
    ld a,$7c
    out ($99),a
    ld bc,$8098
    otir
    ld a,(ticks)
    ld (fuel_at),a
    ret

update_life_sat:
    ld a,(scroll_y)
    add a,LIFE_Y-1
    ld d,a
    ld e,156
    ld c,172
    cp 216
    jr nz,.safe
    dec d
    ld e,164
    ld c,176
.safe:
    ld hl,life_sat
    ld (hl),d
    inc hl
    ld (hl),LIFE_X0
    inc hl
    ld (hl),e
    inc hl
    ld (hl),0
    inc hl
    ld (hl),d
    inc hl
    ld (hl),LIFE_X0
    inc hl
    ld a,e
    add a,4
    ld (hl),a
    inc hl
    ld (hl),0
    inc hl
    ld (hl),d
    inc hl
    ld (hl),LIFE_X1
    inc hl
    ld (hl),c
    inc hl
    ld (hl),0
    ret

; One fixed sprite slot; expand only the selected eight asset rows on a change.
update_life_digit:
    ld a,(lives)
    ld b,a
    ld a,(life_drawn)
    cp b
    ret z
    ld a,b
    ld (life_drawn),a
    add a,a
    add a,a
    add a,a
    ld e,a
    ld d,0
    ld hl,life_digits
    add hl,de
    push hl
    ld hl,point_buffer
    ld de,point_buffer+1
    ld bc,63
    ld (hl),0
    ldir
    pop hl
    ld de,point_buffer+3
    ld b,8
.glyph:
    ld a,(hl)
    ld (de),a
    push hl
    ld hl,33
    add hl,de
    ld (hl),a
    pop hl
    inc hl
    inc de
    djnz .glyph
    vdp_write 14,7
    ld a,$60                  ; pattern 172, normal and shifted
    out ($99),a
    ld a,$7d
    out ($99),a
    ld hl,point_buffer
    ld bc,$4098
    otir
    ret

HUD_FlushNumbers:
    ld c,0
    ld a,(hud_score_dirty)
    or a
    jr z,.check_high
    ld a,(hud_force)
    or a
    jr nz,.score_ready
    ld a,(hud_score_at)
    call hud_number_due
    jr c,.check_high
.score_ready:
    inc c
.check_high:
    ld a,(hud_high_dirty)
    or a
    jr z,.choose
    ld a,(hud_force)
    or a
    jr nz,.high_ready
    ld a,(hud_high_at)
    call hud_number_due
    jr c,.choose
.high_ready:
    set 1,c
.choose:
    ld a,c
    or a
    ret z
    cp 1
    jr z,.score
    cp 2
    jr z,.high
    ld a,(hud_score_turn)
    or a
    jr nz,.high
.score:
    ld a,(ticks)
    ld (hud_score_at),a
    ld a,1
    ld (hud_score_turn),a
    xor a
    ld (hud_score_dirty),a
    ld hl,hud_score_pending
    ld de,hud_score_drawn
    ld bc,SCORE_X/2
    ld ix,$8400
    jr .field
.high:
    ld a,(ticks)
    ld (hud_high_at),a
    xor a
    ld (hud_score_turn),a
    ld (hud_high_dirty),a
    ld hl,hud_high_pending
    ld de,hud_high_drawn
    ld bc,36
    ld ix,$9d00
.field:
    ld (hud_field_pending),hl
    ld (hud_field_drawn),de
    ld (hud_field_dest),bc
    ld (hud_field_font),ix
    ld a,HUD_BANK
    ld ($7000),a
    xor a
    ld (hud_field_index),a
.pair:
    ld hl,(hud_field_pending)
    ld de,(hud_field_drawn)
    ld a,(de)
    cp (hl)
    jr nz,.changed
    inc de
    inc hl
    ld a,(de)
    cp (hl)
    jr z,.next
.changed:
    ld hl,(hud_field_pending)
    ld de,(hud_field_drawn)
    ld a,(hl)
    ld (de),a
    ld b,a
    add a,a
    add a,a
    add a,b
    add a,a                  ; tens * 10
    inc hl
    inc de
    add a,(hl)
    ld b,a
    ld a,(hl)
    ld (de),a
    ld l,b
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,(hud_field_font)
    add hl,de
    ld de,(hud_field_dest)
    call hud_write_pair
.next:
    ld hl,(hud_field_pending)
    inc hl
    inc hl
    ld (hud_field_pending),hl
    ld hl,(hud_field_drawn)
    inc hl
    inc hl
    ld (hud_field_drawn),hl
    ld hl,(hud_field_dest)
    ld de,8
    add hl,de
    ld (hud_field_dest),hl
    ld a,(hud_field_index)
    inc a
    ld (hud_field_index),a
    cp 3
    jr nz,.pair
    ret
hud_number_due:
    ld b,a
    ld a,(ticks)
    sub b
    ld b,a
    ld a,(cadence)
    cp b
    jr z,.yes
    jr c,.yes
    scf
    ret
.yes:
    or a
    ret
hud_write_pair:
    vdp_write 14,4
    ld a,8
.row:
    push af
    ld a,e
    out ($99),a
    ld a,d
    or $40
    out ($99),a
    ld bc,$0898
    otir
    ld a,e
    add a,128
    ld e,a
    jr nc,.next
    inc d
.next:
    pop af
    dec a
    jr nz,.row
    ret

    INCLUDE "hud-api.inc"
    INCLUDE "hud-native.inc"
    INCLUDE "hud-assets.inc"

; SCREEN 5 hardware-scroll ring, fixed radar/fuel and one outlined car plus a life digit.
    OUTPUT "raster-scroll.rom"
    INCLUDE "config.inc"
    INCLUDE "hud-state.inc"
    MACRO vdp_write number,value
    ld a,value
    out ($99),a
    ld a,$80+number
    out ($99),a
    ENDM
    INCLUDE "hud-raster.inc"
marker      EQU $c000
scene       EQU $c001
camera_x    EQU $c006
camera_y    EQU $c007
paused      EQU $c009
ticks       EQU $c00a
last_space  EQU $c00c
last_nine   EQU $c00d
last_home   EQU $c00e
last_scene  EQU $c00f
last_zero   EQU $c012
score_goal  EQU $c013
score_state EQU $c014
high_state  EQU $c015
key8        EQU $c018
key0        EQU $c019
scroll_high EQU $c01a
scroll_low  EQU $c01b
scroll_y    EQU $c01c
irq_stage   EQU $c03c
line_count  EQU $c03d
vblank_count EQU $c03e
dx          EQU $c050
dy          EQU $c051
line_before EQU $c090
radar_world_x EQU $c09a
radar_world_y EQU $c09c
raster_phase EQU $c0a0
last_f      EQU $c0a1
fuel_goal   EQU $c0a2
fuel_state  EQU $c0a3

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
    inc hl
    inc hl
    inc hl
    inc hl
    ld a,(hl)
    and $0c
    or c
    ld h,$80
    call $0024
    ld a,5
    call $005f
    di
    ld b,0
    ld a,6
    call register
    ld b,1
    ld a,2
    call register
    ld b,9
    ld a,VDP_R9
    call register
    ld b,18
    ld a,HORIZONTAL_ADJUST
    call register
    ld b,7
    ld a,BLACK
    call register
    ld b,8
    ld a,$2a                  ; opaque palette zero; sprites off in the header
    call register
    ld b,16
    xor a
    call register
    ld hl,palette
    ld bc,$209a
    otir
    ld b,5
    ld a,$ef                  ; mode-2 attributes at 0x1f600, colors at 0x1f400
    call register
    ld b,11
    ld a,3
    call register
    ld b,6
    ld a,$3f                  ; patterns at 0x1f800, outside both maze pages
    call register
    ld a,8
.mute:
    out ($a0),a
    ld c,a
    xor a
    out ($a1),a
    ld a,c
    inc a
    cp 11
    jr nz,.mute
    ld hl,$c000
    ld de,$c001
    ld bc,95
    ld (hl),0
    ldir
    ld hl,$5aa5
    ld ($c002),hl
    ld hl,$5253
    ld ($c004),hl
    ld a,2
    ld (cadence),a
    ld hl,$d000
    ld de,$d001
    ld bc,256
    ld (hl),$d2
    ldir
    ld a,$c3
    ld ($d2d2),a
    ld hl,interrupt
    ld ($d2d3),hl
    ld a,$d0
    ld i,a
    im 2
    xor a
    ld (last_enter),a
startup_mode:
    ld a,1                   ; The default development ROM starts with the car active.
    ld (driving),a
    call show_scene
    ld a,(ticks)
    ld (frame_tick),a
main:
    ld a,3
    ld (marker),a
.wait:
    ld a,(ticks)
    ld b,a
    ld a,(frame_tick)
    cp b
    jr nz,.ready
    ei
    halt
    jr .wait
.ready:
    di
    ld a,b
    ld (frame_tick),a
    ld a,1
    ld (marker),a
    ld a,(line_count)
    ld (line_before),a
    call keys
    di
    ld a,(paused)
    or a
    jr nz,.position
    call Player_Update
.position:
    call stage_position
    call Player_Radar
    ld a,(paused)
    call HUD_SetForce
    call HUD_PrepareFrame
    call Player_Draw
    ; The numeric HUD lives on a hidden page during the maze. Patch it after
    ; the split, keeping the larger sprite population out of the raster deadline.
.split_wait:
    ld a,(line_before)
    ld b,a
    ld a,(line_count)
    cp b
    jr nz,.split_done
    ei
    halt
    jr .split_wait
.split_done:
    di
    ld a,(ticks)
    ld (frame_tick),a         ; A scene reload may have crossed a VBlank/header.
    call Player_Patch
    ld a,(paused)
    or a
    call z,hud_demo_numbers
    call HUD_DrawContent
    call Player_Advance
    call stage_stream
    ld a,(driving)
    or a
    call nz,stage_wait_command
    call hud_demo_sync_fuel
    ld a,2
    ld (marker),a
    jp main

; AF/BC are always preserved; color/footer uploads save HL locally.
; All control-port pairs are atomic.
interrupt:
    push af
    push bc
    ld b,15
    ld a,1
    call register
    in a,($99)
    and 1
    jp z,vertical
    ld a,(raster_phase)
    or a
    jp nz,life_interrupt
    ld a,3
    ld (irq_stage),a
    vdp_write 1,$22            ; hide register latching inside the separator
    vdp_write 8,$28            ; arm maze sprites; the first row has a VRAM mask
    vdp_write 0,6              ; suppress stale line matching while R23 changes
    vdp_write 25,3             ; two-page torus and the 8-pixel left mask
    vdp_write 26,(scroll_high)
    vdp_write 27,(scroll_low)
    vdp_write 23,(scroll_y)
    vdp_write 2,$3f            ; SP2 requires R2.A15=1; maze pages 0/1
    vdp_write 1,$62
    ld a,1
    ld (raster_phase),a
    ld a,(scroll_y)
    add a,LIFE_SPLIT
    ld b,19
    call register
    vdp_write 0,$16            ; reuse the completed fuel sprites for the footer
    ld a,(line_count)
    inc a
    ld (line_count),a
    ld a,4
    ld (irq_stage),a
    jp irq_return
life_interrupt:
    ld a,5
    ld (irq_stage),a
    HUD_FooterSprites
    ld a,6
    ld (irq_stage),a
    jp irq_return
vertical:
    ld b,15
    xor a
    call register
    in a,($99)
    and $80
    jp z,irq_return
    ld a,1
    ld (irq_stage),a
    xor a
    ld (raster_phase),a
    HUD_VBlankSprites
    ld b,8
    ld a,$2a
    call register
    ld b,25
    xor a
    call register
    ld b,26
    xor a
    call register
    ld b,27
    xor a
    call register
    ld b,23
    xor a
    call register
    ld b,2
    ld a,$5f                  ; header bitmap at 0x10000, fixed at scroll zero
    call register
    ld b,19
    ld a,7                    ; compare while R23=0, after the last header row
    call register
    ld b,0
    ld a,$16
    call register
    ld b,1
    ld a,$62
    call register
    ld a,(ticks)
    inc a
    ld (ticks),a
    ld a,(vblank_count)
    inc a
    ld (vblank_count),a
    ld a,2
    ld (irq_stage),a
irq_return:
    ld b,15
    xor a
    call register
    pop bc
    pop af
    ei
    reti

register:
    out ($99),a
    ld a,b
    or $80
    out ($99),a
    ret
    INCLUDE "hud-demo.inc"
show_scene:
    di
    ld b,0
    ld a,6
    call register
    ld b,1
    ld a,2
    call register
    ld b,14
    xor a
    call register
    xor a
    out ($99),a
    ld a,$40
    out ($99),a
    ld a,(driving)
    or a
    call nz,Player_Init
    ld a,(driving)
    or a
    call nz,stage_atlas_init
    call stage_load
    call HUD_Init
    call hud_demo_reset
    xor a
    ld (camera_x),a
    ld (camera_y),a
    ld (score_goal),a
    ld (score_state),a
    ld (scroll_high),a
    ld (scroll_low),a
    ld a,4
    ld (high_state),a
    xor a
    ld (fuel_goal),a
    ld (fuel_state),a
    ld (raster_phase),a
    ld a,256-BODY_TOP
    ld (scroll_y),a
    xor a
    call stage_position
    xor a
    ld (radar_clock),a
    ld a,(scene)
    add a,a
    ld l,a
    ld h,0
    ld de,radar_enemies
    add hl,de
    ld b,(hl)
    inc hl
    ld c,(hl)
    call HUD_SetEnemy
    call Player_Radar
    call HUD_Prime
    call Player_Draw
    ld b,15
    ld a,1
    call register
    in a,($99)
    ld b,15
    xor a
    call register
    in a,($99)
    ld a,(ticks)
    ld (content_at),a
    ld b,1
    ld a,$22
    call register
    ei
    ret
upload:
    ld a,(hl)
    out ($98),a
    inc hl
    dec de
    ld a,d
    or e
    jr nz,upload
    ret

    INCLUDE "hud.inc"
    INCLUDE "player.inc"
    INCLUDE "stage-one-stream.inc"
palette:
    INCBIN "palette.bin"
    ASSERT $ <= $8000
    defs $8000-$,$ff
    INCLUDE "payload.inc"

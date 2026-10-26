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
    IF FULL_GAME
irq_scroll_y EQU $d2cc
    ELSE
irq_scroll_y EQU scroll_y
    ENDIF
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
    IF INCREMENTAL_STAGE >= 9
    xor a
    ld (Sprite_UploadActive),a
    ENDIF
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
    IF INCREMENTAL_STAGE >= 7
    ld (Life_Restarting),a
    ENDIF
startup_mode:
    IF FULL_GAME
    call Full_CopyCold
    ENDIF
    IF SESSION_RUNTIME
    call Session_Init
    ENDIF
    ld a,1                   ; The default development ROM starts with the car active.
    ld (driving),a
    call show_scene
    ld a,(ticks)
    ld (frame_tick),a
main:
    ld a,3
    ld (marker),a
.wait:
    IF INCREMENTAL_STAGE >= 9
    di                      ; Check and EI/HALT must form one atomic wait decision.
    ENDIF
    ld a,(ticks)
    ld b,a
    IF FULL_GAME
    ld a,(Session_State)
    or a
    jr nz,.frame_check       ; A UI transition cannot wait for a gameplay packet.
    ld a,(Full_PresentReady)
    or a
    jr z,.packet_available
    call Full_PresentIdle
    jr c,.wait               ; Drain safe body time instead of sleeping after one copy.
    di
    ld a,(Full_PresentReady)
    or a
    jr z,.wait               ; Do not sleep past a commit serviced during prefetch.
    jr .sleep
.packet_available:
    bit 0,b
    jr nz,.sleep
    ENDIF
.frame_check:
    ld a,(frame_tick)
    cp b
    jr nz,.ready
.sleep:
    ei
    halt
    jr .wait
.ready:
    di
    ld a,b
    ld (frame_tick),a
    IF FULL_GAME
    xor a
    ld (Full_LoopTicks),a
    ENDIF
    IF SESSION_RUNTIME
    ld a,(Session_State)
    or a
    jp nz,Session_Main
    ENDIF
    IF RASTER_GUARD
    xor a
    ld (Stage_GuardClosed),a
    IF STAGE_TILE_STRIPS && RADAR_CELLS_ONLY && HUD_ENABLED && !SMOKE_RUNTIME
    inc a
    ld (Radar_TailWork),a
    ENDIF
    ENDIF
    IF FULL_GAME
    jp Full_MainFrame
    ELSE
    ld a,1
    ld (marker),a
    ld a,(line_count)
    ld (line_before),a
    IF SESSION_RUNTIME
    ei                      ; Keyboard and frame RAM preparation own no VDP latch.
    nop
    ENDIF
    IF FULL_GAME
    call Full_TurboOn
    ENDIF
    call keys
    IF FULL_GAME
    call Full_TurboOff
    ENDIF
    IF !SESSION_RUNTIME
    di
    ENDIF
    IF INCREMENTAL_STAGE >= 9
    IF PLAYER_FAST_BLITTER || SMOKE_RUNTIME
    call Flag_Frame
    ENDIF
    IF RADAR_CELLS_ONLY && HUD_ENABLED
    call Radar_CommitPublished
    ENDIF
    call Death_Frame
    ENDIF
    IF FLICKER_STRESS
    ld a,(paused)
    or a
    jr z,.stress_running
    ; The diagnostic scene is already prepared. Isolate the priority exchange
    ; during pause, without rebuilding identical actor/HUD RAM every refresh.
    call Flicker_Publish
    jp Enemy_AfterPrepare.split_wait
.stress_running:
    ENDIF
    ld a,(paused)
    or a
    jr nz,.position
    call Player_Update
.position:
    IF SESSION_RUNTIME
    ld a,1
    ld (Session_PositionIRQ),a
    ei                      ; Cache-bound calculations do not own a VDP latch.
    nop
    ENDIF
    call stage_position
    IF RADAR_CELLS_ONLY || SPRITE_FLICKER
    ei
    nop
    ENDIF
    IF RADAR_CELLS_ONLY && HUD_ENABLED
    IF RADAR_PLAYER_SPRITE
    call Player_Radar       ; Freeze the dot with this refresh's player position.
    ENDIF
    call HUD_PrepareEarlyCoordinates
    IF FULL_GAME
    call Full_TurboOn
    call HUD_FinishCoordinates ; Prepare fuel/life; maze IRQ owns fixed radar SAT.
    call Full_TurboOff
    ENDIF
    ENDIF
    IF ENEMY_RENDER
    IF FULL_GAME
    call Full_EnemyFrame
    ELSE
    call Enemy_Prepare
    ENDIF
Enemy_AfterPrepare:
    IF RADAR_PLAYER_SPRITE
    call Enemy_Radar
    ENDIF
    ENDIF
    IF RADAR_CELLS_ONLY && HUD_ENABLED
    IF ENEMY_RENDER
    IF !FULL_GAME
    di
    ENDIF
    IF !FULL_GAME
    call Enemy_Draw         ; An enemy may begin at the first maze scanline.
    ENDIF
    ENDIF
    IF !FULL_GAME
    call HUD_FinishCoordinates
    ENDIF
    ei
    nop
    ENDIF
    IF HUD_ENABLED
    IF !RADAR_PLAYER_SPRITE
    call Player_Radar
    ENDIF
    ld a,(paused)
    call HUD_SetForce
    IF RADAR_CELLS_ONLY
    di
    call Player_Draw
    ei
    nop
    di
    IF ENEMY_COUNT
    ; Commit the frame's existing presentation before advancing native state.
    call Player_Patch
    ld b,64
    call Death_Stream
    IF SMOKE_RUNTIME
    ; Publish the previous native tick's collection before its scanlines.
    ; New collections remain visible until the next presentation snapshot.
    ld b,64
    call Flag_Stream
    ENDIF
    IF PLAYER_FAST_BLITTER
    ld b,64
    call Flag_Stream
    xor a
    ld (Fuel_HudWork),a
    call update_fuel        ; Fuel sprites are fetched before the player's band.
    call Bitmap_Draw        ; Finish this snapshot before advancing simulation.
    ENDIF
    call Player_AdvanceEarly
    IF SMOKE_RUNTIME
    ld b,3                  ; One cloud row, before its central scanlines.
    call Smoke_Stream       ; Bound burst work; full clouds publish over refreshes.
    ENDIF
    ld b,64
    call Flag_Stream
    call Score_ReservedFrame
    ENDIF
    ENDIF
    IF SPRITE_FLICKER
    di
    ENDIF
    IF FULL_GAME
    call Full_TurboOn
    ENDIF
    call HUD_PrepareFrame
    IF FULL_GAME
    call Full_TurboOff
    ENDIF
    IF SPRITE_FLICKER
    ei
    nop
    ENDIF
    ELSE
    IF RADAR_CELLS_ONLY
    di
    ENDIF
    call Stage_HideHUD
    ENDIF
    IF !RADAR_CELLS_ONLY || !HUD_ENABLED
    IF SPRITE_FLICKER
    di
    ENDIF
    IF RADAR_CELLS_ONLY && ENEMY_RENDER && ENEMY_COUNT >= 2 && !HUD_ENABLED
    call Enemy_Draw         ; Top-edge cars must be ready before player patterns.
    call Player_Draw
    ELSE
    call Player_Draw
    IF SPRITE_FLICKER
    ei
    nop
    di
    ENDIF
    IF ENEMY_RENDER
    call Enemy_Draw
    ENDIF
    ENDIF
    ENDIF
    IF SPRITE_FLICKER
    call Flicker_Publish
    ENDIF
    IF ENEMY_COUNT && !SPRITE_FLICKER
    IF !RADAR_CELLS_ONLY || !HUD_ENABLED
    call Player_AdvanceEarly
    IF INCREMENTAL_STAGE >= 9 && ENEMY_COUNT >= 2 && !HUD_ENABLED
    ld b,64
    call Flag_Stream
    call Score_ReservedFrame
    ENDIF
    ENDIF
    ENDIF
    IF RADAR_BLITTER
    call BitmapRadar_FrameRestore
    ENDIF
    IF PLAYER_BLITTER && !PLAYER_FAST_BLITTER
    ; The previous player band has passed. Spend the blank interval on VDP
    ; save/restore/draw rather than extending the visible guard-work phase.
    call Bitmap_Restore
    call Bitmap_Draw
    ENDIF
    IF RADAR_BLITTER
    call BitmapRadar_FrameDraw
    ENDIF
    ; The numeric HUD lives on a hidden page during the maze. Patch it after
    ; the split, keeping the larger sprite population out of the raster deadline.
.split_wait:
    IF FULL_GAME
    ; A loop which starts after the maze latch can use the current safe body
    ; interval. Waiting for another latch would add a whole refresh of latency.
    ei
    nop
    ld a,(raster_phase)
    or a
    jr nz,.split_done
    ENDIF
    IF INCREMENTAL_STAGE >= 9
    di                      ; A split arriving before HALT must not be slept past.
    ENDIF
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
    IF !FULL_GAME
    ld a,(ticks)
    ld (frame_tick),a         ; A scene reload may have crossed a VBlank/header.
    ENDIF
    IF SPRITE_FLICKER
    call Player_AdvanceEarly
    ENDIF
    IF !PLAYER_BLITTER
    IF !RADAR_CELLS_ONLY || !HUD_ENABLED
    call Player_Patch
    ENDIF
    ENDIF
    IF HUD_ENABLED
    ld a,(paused)
    or a
    call z,hud_demo_numbers
    call HUD_DrawContent
    ENDIF
    call Player_Advance
    IF ENEMY_COUNT
    call Flag_PublishHUD
    ENDIF
    IF RADAR_CELLS_ONLY && HUD_ENABLED
    call Radar_WaitPublish
    ENDIF
    IF FULL_GAME
    call Full_CacheEnter
    ld a,1
    ld (Full_CacheHeld),a
    ENDIF
    call stage_stream
    IF FULL_GAME
    xor a
    ld (Full_CacheHeld),a
    call Full_CacheLeave
    ENDIF
    ld a,(driving)
    or a
    IF !TILE_MODE
    call nz,stage_wait_command
    ENDIF
    IF SESSION_RUNTIME
    ei                      ; Finished VDP work; fuel/life/session checks are RAM work.
    nop
    ENDIF
    IF STAGE_TILE_STRIPS && RADAR_CELLS_ONLY && HUD_ENABLED && !SMOKE_RUNTIME
    ; The next refresh publishes these payloads in its safe radar window.
    ; Use the tail instead of displacing urgent terrain before scanout.
    call Radar_PrepareTail
    ENDIF
    IF HUD_ENABLED
    call hud_demo_sync_fuel
    ENDIF
    IF INCREMENTAL_STAGE >= 7
    call Life_Frame
    ENDIF
    IF COMPLETION_RUNTIME
    call Round_Frame
    ENDIF
    IF SESSION_RUNTIME
    call Session_Check
    ENDIF
    IF FULL_GAME
    call Full_PresentSeal
    ENDIF
    ld a,2
    ld (marker),a
    jp main

    ENDIF
    IF FULL_GAME
    INCLUDE "full-main.inc"
    ENDIF

; AF/BC are always preserved; color/footer uploads save HL locally.
; All control-port pairs are atomic.
interrupt:
    push af
    push bc
    IF FULL_GAME
    ld a,(Full_TurboActive)
    or a
    jr z,.base_clock
    ld a,1
    out ($41),a
.base_clock:
    ENDIF
    ld b,15
    ld a,1
    call register
    in a,($99)
    and 1
    jp z,vertical
    ld a,(raster_phase)
    IF RASTER_GUARD
    or a
    jp z,maze_interrupt      ; retain the baseline header-dispatch cycle count
    IF RADAR_CELLS_ONLY && HUD_ENABLED
    cp 3
    jp z,radar_interrupt
    cp 4
    jp z,radar_close_interrupt
    IF STAGE_GUARD_LINE < LIFE_SPLIT
    cp 5
    jp z,prefetch_guard_interrupt
    ENDIF
    ENDIF
    IF FULL_GAME
    cp 6
    jp z,full_prefetch_close_interrupt
    ENDIF
    cp 2
    jp z,guard_interrupt
    jp life_interrupt
    ELSE
    or a
    jp nz,life_interrupt
    ENDIF
maze_interrupt:
    ld a,3
    ld (irq_stage),a
    IF FULL_GAME
    call Full_LatchScrollY   ; Compute before the line6..9 register-latch window.
    ENDIF
    IF INCREMENTAL_STAGE >= 9
    ; Reserve the split before foreground work can mask its exact deadline.
    ; Keep the complete seven-row font visible, then latch the maze registers.
    ld a,6
    ld b,19
    call register
.header_end:
    in a,($99)
    and 1
    jr z,.header_end
    ENDIF
    vdp_write 1,$22            ; hide register latching inside the separator
    vdp_write 8,$28            ; arm maze sprites; the first row has a VRAM mask
    vdp_write 0,MAZE_R0              ; suppress stale line matching while R23 changes
    vdp_write 25,3             ; two-page torus and the 8-pixel left mask
    IF FULL_GAME
    vdp_write 26,(Full_PresentActiveX)
    vdp_write 27,(Full_PresentActiveX+1)
    ELSE
    vdp_write 26,(scroll_high)
    vdp_write 27,(scroll_low)
    ENDIF
    IF FULL_GAME
    ld a,(irq_scroll_y)
    out ($99),a
    ld a,$97
    out ($99),a
    ELSE
    vdp_write 23,(scroll_y)
    ENDIF
    vdp_write 2,MAZE_R2            ; SP2 requires R2.A15=1; maze pages 0/1
    IF INCREMENTAL_STAGE >= 9
    ; Prepare early, then latch display-on at a hardware line boundary. A
    ; variable foreground DI tail must not move the first visible maze row.
    ld a,(irq_scroll_y)
    add a,9
    ld b,19
    call register
    vdp_write 0,MAZE_R0+16
.separator:
    in a,($99)               ; S1 remains selected by interrupt dispatch.
    and 1
    jr z,.separator
    ENDIF
    vdp_write 1,$62
    IF FULL_GAME
    call Full_RadarIRQ
    ENDIF
    IF RADAR_CELLS_ONLY && HUD_ENABLED
    ld a,3
    ELSE
    ld a,1
    ENDIF
    ld (raster_phase),a
    ld a,(irq_scroll_y)
    IF RADAR_CELLS_ONLY && HUD_ENABLED
    add a,80
    ELSE
    add a,LIFE_SPLIT
    ENDIF
    ld b,19
    call register
    vdp_write 0,MAZE_R0+16            ; reuse the completed fuel sprites for the footer
    ld a,(line_count)
    inc a
    ld (line_count),a
    ld a,4
    ld (irq_stage),a
    jp irq_return
    IF RADAR_CELLS_ONLY && HUD_ENABLED
radar_interrupt:
    ld a,1
    ld (Radar_Scanned),a
    IF STAGE_GUARD_LINE < LIFE_SPLIT
    ld a,5
    ld (raster_phase),a
    ld a,(irq_scroll_y)
    add a,STAGE_GUARD_LINE
    ld b,19
    call register
    jp irq_return
prefetch_guard_interrupt:
    ld a,(Radar_TailWork)
    or a
    jr z,.no_marker_tail
    ld a,1
    ld (Stage_GuardClosed),a
.no_marker_tail:
    ENDIF
    ld a,4
    ld (raster_phase),a
    ld a,(irq_scroll_y)
    add a,144
    ld b,19
    call register
    jp irq_return
radar_close_interrupt:
    ld a,2
    ld (Radar_Scanned),a
    IF FULL_GAME
    ld a,6
    ELSE
    ld a,1
    ENDIF
    ld (raster_phase),a
    ld a,(irq_scroll_y)
    IF FULL_GAME
    add a,152               ; Stop foreground copies before the footer deadline.
    ELSE
    add a,LIFE_SPLIT
    ENDIF
    ld b,19
    call register
    jp irq_return
    IF FULL_GAME
full_prefetch_close_interrupt:
    ld a,1
    ld (raster_phase),a
    ld a,(irq_scroll_y)
    add a,LIFE_SPLIT
    ld b,19
    call register
    jp irq_return
    ENDIF
    ENDIF
life_interrupt:
    ld a,5
    ld (irq_stage),a
    IF HUD_ENABLED
    HUD_FooterSprites
    ELSE
    vdp_write 0,MAZE_R0
    ENDIF
    IF RASTER_GUARD
    ld a,2
    ld (raster_phase),a
    IF STAGE_GUARD_LINE < LIFE_SPLIT
    ld a,(Radar_TailWork)
    or a
    jr z,.terrain_tail
    vdp_write 0,MAZE_R0             ; The marker producer owns the remaining tail.
    jr .tail_ready
.terrain_tail:
    ld a,(irq_scroll_y)
    add a,196
    ld b,19
    call register
    vdp_write 0,MAZE_R0+16
.tail_ready:
    ELSE
    ld a,(irq_scroll_y)
    add a,STAGE_GUARD_LINE
    ld b,19
    call register
    vdp_write 0,MAZE_R0+16
    ENDIF
    ENDIF
    ld a,6
    ld (irq_stage),a
    jp irq_return
    IF RASTER_GUARD
; Stop before the next visible refresh. The final indivisible command has
; STAGE_GUARD_LINE leaves a measured tail before VBlank; foreground checks this
; flag between copies (16 scanlines in the reference, eight in stage09).
guard_interrupt:
    ld a,1
    ld (Stage_GuardClosed),a
    vdp_write 0,MAZE_R0
    jp irq_return
    ENDIF
vertical:
    ld b,15
    xor a
    call register
    in a,($99)
    and $80
    jp z,irq_return
    IF SESSION_RUNTIME
    ld a,(Session_State)
    or a
    jp nz,Session_VBlank
    ENDIF
    IF PLAYER_BLITTER || INCREMENTAL_STAGE >= 9 || TILE_MODE
    ; VBlank is also a hard stop if a late split prevented the earlier guard
    ; comparator from firing. Never carry optional cache work into a new frame.
    ld a,1
    ld (Stage_GuardClosed),a
    ENDIF
    ld a,1
    ld (irq_stage),a
    xor a
    ld (raster_phase),a
    IF RADAR_CELLS_ONLY && HUD_ENABLED
    ld (Radar_Scanned),a
    ENDIF
    IF HUD_ENABLED
    IF OUTLINE_FLICKER
    call Outline_Commit
    ENDIF
    IF !FULL_GAME
    HUD_VBlankSprites
    ENDIF
    ENDIF
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
    IF INCREMENTAL_STAGE >= 9
    IF SESSION_RUNTIME
    IF FULL_GAME
    xor a                     ; Full RAM producers yield before the header deadline.
    ELSE
    ld a,1                    ; Reserve enough lead for a busy lucky-bonus DI tail.
    ENDIF
    ELSE
    ld a,3                    ; Reserve split; wait for font end and line nine.
    ENDIF
    ELSE
    ld a,7                    ; compare while R23=0, after the last header row
    ENDIF
    call register
    ld b,0
    ld a,$16
    call register
    ld b,1
    ld a,$62
    call register
    IF FULL_GAME
    call Full_PresentCommit
    ENDIF
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
    IF INCREMENTAL_STAGE >= 9
    ld a,(Sprite_UploadActive)
    or a
    call nz,Sprite_ResumeUpload
    ENDIF
    IF FULL_GAME
    ld a,(Full_TurboActive)
    or a
    jr z,.base_clock
    xor a
    out ($41),a
.base_clock:
    ENDIF
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
    IF !FULL_GAME
show_scene:
    IF FULL_GAME
    call Full_TurboOff
    xor a
    ld (Full_PresentEnabled),a
    ld (Full_PresentReady),a
    ENDIF
    di
    IF FULL_GAME
    xor a
    ld (Full_CacheReady),a
    ld (Full_CameraBlocked),a
    ENDIF
    IF SESSION_RUNTIME
    xor a
    ld (Session_PositionIRQ),a
    ENDIF
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
    IF STAGE_TILE_STRIPS
    call Stage_StripInit
    ENDIF
    call stage_load
    call HUD_Init
    IF FULL_GAME
    ld a,SESSION_BANK
    ld ($7000),a
    call $b815
    ENDIF
    IF SPRITE_FLICKER
    call Flicker_Init
    ENDIF
    IF PLAYER_BLITTER
    call Bitmap_Init
    ENDIF
    IF RADAR_BLITTER
    call BitmapRadar_Init
    ENDIF
    IF ENEMY_RENDER
    ld a,(driving)
    or a
    call nz,Enemy_InitPatterns
    ENDIF
    IF HUD_ENABLED
    call hud_demo_reset
    IF FULL_GAME
    ld a,(Full_Player)
    inc a
    call HUD_SetPlayerNumber
    ENDIF
    IF INCREMENTAL_STAGE >= 5
    ld a,(driving)
    or a
    call nz,Score_Publish
    ENDIF
    IF INCREMENTAL_STAGE >= 6
    ld a,(driving)
    or a
    call nz,Fuel_Publish
    ENDIF
    IF INCREMENTAL_STAGE >= 7
    ld a,(driving)
    or a
    jr z,.life_published
    call Life_Publish
    call Life_Flags
.life_published:
    ENDIF
    ENDIF
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
    IF ENEMY_RENDER
    call Enemy_Prepare
    ENDIF
    IF HUD_ENABLED
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
    ELSE
    call Stage_HideHUD
    ENDIF
    call Player_Draw
    IF PLAYER_BLITTER
    call Bitmap_Draw
    ENDIF
    IF RADAR_BLITTER
    call BitmapRadar_Draw
    ENDIF
    IF ENEMY_RENDER
    call Enemy_Draw
    ENDIF
    IF SPRITE_FLICKER
    call Flicker_Publish
    IF OUTLINE_FLICKER
    call Outline_Commit
    ENDIF
    ENDIF
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
    ENDIF
    IF !HUD_ENABLED
; Preserve the established car slot numbers while hiding every unused HUD entry.
; There is no Y=216 terminator before the car and no HUD work per refresh.
Stage_HideHUD:
    IF PLAYER_SLOT == 0
    ret                     ; A HUD-free SAT contains only player and enemies.
    ENDIF
    IF INCREMENTAL_STAGE >= 9
    ei                      ; RAM preparation must not delay the reserved header.
    nop
    ENDIF
    ld a,(scroll_y)
    add a,211
    cp 216
    jr nz,.safe
    inc a
.safe:
    ld hl,sat
    ld de,4
    ld b,PLAYER_SLOT
.hide:
    ld (hl),a
    add hl,de
    djnz .hide
    ld (hl),216
    IF INCREMENTAL_STAGE >= 9
    ld hl,sat
    ld de,$7600
    ld b,SAT_BYTES
    jp Sprite_Upload
    ENDIF
    vdp_write 14,7
    xor a
    out ($99),a
    ld a,$76
    out ($99),a
    ld hl,sat
    ld bc,SAT_BYTES*256+$98
    otir
    ret
    ENDIF
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
    IF PLAYER_BLITTER || RADAR_BLITTER
    INCLUDE "bitmap-player.inc"
    ENDIF
    IF RADAR_BLITTER
    INCLUDE "bitmap-radar.inc"
    ENDIF
    IF SPRITE_FLICKER
    INCLUDE "sprite-flicker.inc"
    ELSE
    IF INCREMENTAL_STAGE >= 9
    INCLUDE "sprite-upload.inc"
    ENDIF
    ENDIF
    INCLUDE "stage-one-stream.inc"
    INCLUDE "rock-collision.inc"
    INCLUDE "death.inc"
    INCLUDE "flags.inc"
    INCLUDE "score.inc"
    INCLUDE "fuel.inc"
    INCLUDE "lives.inc"
    INCLUDE "enemy.inc"
    IF SMOKE_RUNTIME
    INCLUDE "smoke.inc"
    ENDIF
    IF COMPLETION_COMPONENT
    INCLUDE "completion.inc"
    ENDIF
    IF RADAR_CELLS_ONLY
    INCLUDE "radar-cells.inc"
    ENDIF
    IF SESSION_RUNTIME
    INCLUDE "session-loader.inc"
    ENDIF
    IF FULL_GAME
    INCLUDE "full-round-runtime.inc"
    ENDIF
palette:
    INCBIN "palette.bin"
    ASSERT $ <= $8000
    defs $8000-$,$ff
    INCLUDE "payload.inc"

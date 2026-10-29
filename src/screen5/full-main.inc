; A complete packet is built from one simulation/camera snapshot. Hidden
; prefetch follows sealing; it cannot postpone an already finished packet.
Full_MainFrame:
    ld a,1
    ld (marker),a
    ld a,(line_count)
    ld (line_before),a
    xor a
    ld (Full_SealedFrame),a
    call Full_TurboOn
    call keys
    call Full_TurboOff
    ld hl,(Full_CameraCentreX)
    ld (Full_FrameOriginX),hl
    ld hl,(Full_CameraCentreY)
    ld (Full_FrameOriginY),hl
    call Player_AdvanceEarly
    ei
    nop
    call hud_demo_sync_fuel
    ld a,(paused)
    or a
    call z,Player_Update
    call Death_Frame
    call Flag_Frame
    call Flag_PublishHUD
    call Radar_CommitPublished
    ; Only a committed packet may change the scroll used by raster IRQs.
    ; Scene initialization uses zero; active preparation must leave it latched.
    ld a,1
    ld (Session_PositionIRQ),a
    ei
    nop
    call stage_position
    ld a,(paused)
    or a
    jr nz,.camera_ready
    call Full_WarmCamera     ; Prime nearest cells; blocked edges retain their repair budget.
    ld a,(Full_CameraBlocked)
    or a
    jr z,.camera_ready
    xor a
    ld (Full_CameraAppliedValid),a
    call Player_Apply
    call stage_position
.camera_ready:
    ld a,PLAYER_BANK
    ld ($7000),a
    call Player_Radar
    call HUD_PrepareEarlyCoordinates
    call Full_TurboOn
    call HUD_FinishCoordinates
    call Full_TurboOff
    ld b,3                   ; Live effects precede the variable enemy workload.
    call Smoke_Stream
    call Full_EnemyFrame
    call Enemy_Radar
    ld a,(paused)
    call HUD_SetForce
    call Player_Draw
    call Player_Patch
    ld b,64
    call Death_Stream
    ld b,64
    call Flag_Stream
    ; The actor/camera snapshot is complete. Publish its readiness before
    ; score and bitmap-HUD maintenance consume the rest of this frame.
    ld a,(Death_Jobs)
    or a
    jr nz,.maze_wait
    call stage_wait_command
    ei
    nop
    call Full_PresentSeal
    ld a,1
    ld (Full_SealedFrame),a
    IF AUDIO_ENABLED
    call Audio_Work
    ENDIF
.maze_wait:
    di
    ld a,(raster_phase)
    or a
    jr nz,.maze_ready
    ei
    halt
    jr .maze_wait
.maze_ready:
    call Score_Frame         ; Owns EI; this loop reserves one early native tick.
    call Full_TurboOn
    call HUD_PrepareFrame
    call HUD_FlushFlags       ; Bounded RAM work precedes optional numeric VRAM writes.
    call Full_TurboOff
    ld a,(paused)
    or a
    call z,hud_demo_numbers
    call HUD_DrawContent
    call Full_AdvanceClock   ; Timer debt survives a packet that already committed.
.prefetch:
    ld a,(Full_SealedFrame)
    or a
    jr z,.copy_guards
    ld a,(Full_PresentReady)
    or a
    jr z,.after_prefetch     ; A committed frame yields to the next snapshot.
.copy_guards:
    IF FLAG_POPUPS
    call Popup_Frame
    or a
    jr nz,.after_prefetch     ; Visible award work replaces optional guard copies.
    ENDIF
    call Full_CacheEnter
    ld a,1
    ld (Full_CacheHeld),a
    call stage_stream
    xor a
    ld (Full_CacheHeld),a
    call Full_CacheLeave
    call stage_wait_command
    ei
    nop
.after_prefetch:
    ei                       ; Skipped optional work must also yield to the header IRQ.
    nop
    call Life_Frame
    call Round_Frame
    call Session_Check
    ld a,(Full_SealedFrame)
    or a
    call z,Full_PresentSeal
    ld a,2
    ld (marker),a
    jp main

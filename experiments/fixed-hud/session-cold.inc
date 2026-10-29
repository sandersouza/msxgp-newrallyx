; Runs from independent Page0 RAM. Resident helpers temporarily map other RAM
; segments and restore this segment before returning. No active-frame rebuild.
    INCLUDE "session-phase.inc"
    INCLUDE "session-sprite-static.inc"
GameSession_ColdBoot:
    in a,($fc)
    and 7
    ld (GameSession_MainSegment),a
    ld c,a
    in a,($ff)
    and 7
    ld b,a
    ld hl,GameSession_MapSegments
    ld d,3
    xor a
.segment:
    cp b
    jr z,.next
    cp c
    jr z,.next
    ld (hl),a
    inc hl
    dec d
    jr z,.allocated
.next:
    inc a
    jr .segment
.allocated:
    ; The fourth private segment caches the S-hidden radar phase variants.
.off_segment:
    inc a
    cp b
    jr z,.off_segment
    cp c
    jr z,.off_segment
    ld (GameSession_FlagOffSegment),a
    xor a
    ld hl,$c7ca
    ld de,$c7cb
    ld bc,$2a
    ld (hl),a
    ldir
    ld hl,$e060
    ld de,Session_High
    ld bc,8
    ldir
    inc a
    ld (Session_State),a
    ld (Full_Players),a
    call GameAudio_Init
    IF SESSION_TEST_MODE
    xor a
    ld (GameSession_TestHeld),a
    ld (GameSession_Invulnerable),a
    ENDIF
    ret

GameSession_ColdLoad:
    call GameSession_AudioStop
    xor a
    ld (ready),a
    di
    reg 1,$02
    ld a,(GameSession_LoadKind)
    cp 2
    jr nz,.seed
    ld hl,Flag_Active+1
    ld de,GameSession_SaveFlags
    ld bc,10
    ldir
.seed:
    ld a,(GameSession_LoadKind)
    or a
    jr nz,.native
    ld (GameSession_RoundCaps),a
    ld (GameSession_RoundCaps+1),a
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld hl,$a000
    ld de,$e000
    ld bc,4096
    ldir
.native:
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
    ld a,(GameSession_LoadKind)
    or a
    jr z,.first
    dec a
    jr z,.next_round
    call $ae06
    jr .prepared
.first:
    call $ae00
    jr .prepared
.next_round:
    call $ae03
.prepared:
    xor a
    ld hl,$c080
    ld de,$c081
    ld bc,$3f
    ld (hl),a
    ldir
    call Game_InitCore
    ld a,(GameSession_LoadKind)
    cp 2
    jr nz,.state_ready
    ld hl,GameSession_SaveFlags
    ld de,Flag_Active+1
    ld bc,10
    ldir
    ld a,($e271)
    ld (Flag_Count),a
    ld (Score_Seen),a
    ld hl,Flag_Cells
    ld de,Flag_Active+1
    ld b,10
.inactive:
    ld a,(de)
    or a
    jr nz,.cell_ready
    ld (hl),a
    inc hl
    ld (hl),a
    dec hl
.cell_ready:
    inc hl
    inc hl
    inc de
    djnz .inactive
    call Flag_Frame
.state_ready:
    xor a
    ld (Session_State),a
    ld (Session_Drawn),a
    ld (paused),a
    ld (GameSession_PauseHeld),a
    ld (Game_State),a
    ld (Game_Due),a
    ld (Session_RiskFrames),a
    ld (Session_GuardActive),a
    ld (Popup_Active),a
    ld (Popup_Pending),a
    ld hl,Popup_Loaded
    ld b,8
.popup_keys:
    ld (hl),$ff
    inc hl
    djnz .popup_keys
    call GameSession_BuildMap
    call GameSession_BuildFlags
    call GameSession_Video
    ld a,1
    ld (Audio_NewScene),a
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
.done:
    ret

GameSession_BuildMap:
    ld a,(Full_Layout)
    add a,a
    ld e,a
    ld d,0
    ld hl,GameSession_MapBanks
    add hl,de
    ld a,(hl)
    push hl
    push af
    ld a,(GameSession_MapSegments)
    ld c,a
    pop af
    call GameSession_CopyMap
    pop hl
    inc hl
    ld a,(hl)
    push af
    ld a,(GameSession_MapSegments+1)
    ld c,a
    pop af
    call GameSession_CopyMap
    ; Native navigation shares the original four geometry maps.
    ld a,GAME_RESOURCE_BANK
    ld ($7000),a
    ld a,(Full_Layout)
    add a,a
    add a,a
    add a,a
    add a,$80
    ld h,a
    ld l,0
    ld de,$3000
    ld bc,2048
    ldir
    call GameSession_MapTerrain
    ld ix,Flag_Records
    ld a,10
    ld (GameSession_Count),a
.flag:
    ld b,(ix+4)
    ld c,(ix+5)
    ld a,(ix+2)
    dec a
    call .object
    ld de,6
    add ix,de
    ld hl,GameSession_Count
    dec (hl)
    jr nz,.flag
    ld ix,($e996)
    ld a,($e251)
    ld (GameSession_Count),a
    or a
    ret z
.rock:
    ; Spare navigation bit4 owns stone occupancy; exit bits0..3 stay exact.
    ld l,(ix+0)
    ld a,(ix+1)
    sub $68
    ld h,a
    set 4,(hl)
    ld a,(ix+0)
    and 31
    ld b,a
    add a,a
    add a,b
    add a,3
    ld b,a
    ld a,(ix+1)
    sub $98
    REPT 3
    add a,a
    ENDR
    ld c,a
    ld a,(ix+0)
    REPT 3
    rlca
    ENDR
    and 7
    or c
    ld c,a
    add a,a
    add a,c
    add a,3
    ld c,a
    ld a,2
    call .object
    inc ix
    inc ix
    ld hl,GameSession_Count
    dec (hl)
    jr nz,.rock
    ret
.object:
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld e,a
    ld d,0
    add hl,de
    ld de,$a800
    add hl,de
    push hl
    pop iy
    jp GameSession_PatchObject

GameSession_MapTerrain:
    ld a,(Full_Layout)
    ld e,a
    ld d,0
    ld hl,GameSession_TerrainBanks
    add hl,de
    ld a,(hl)
    ld (Full_ResourceBank),a
    ld ($7000),a
    ret

GameSession_Video:
    call GameSession_AudioStop
    ; UI reveal fields alias the gameplay popup packet. No UI pointer/timer
    ; may survive into the first restored gameplay render.
    xor a
    ld (Popup_Active),a
    ld (Popup_Pending),a
    ld (Popup_Age),a
    ld hl,Popup_Loaded
    ld b,8
.popup_invalid:
    ld (hl),255
    inc hl
    djnz .popup_invalid
    di
    reg 1,$02
    reg 0,4
    reg 8,$28
    reg 9,$80
    reg 18,0
    reg 25,2
    reg 26,0
    reg 27,0
    reg 23,0
    reg 7,GAME_BLACK
    reg 16,0
    ld hl,palette
    ld bc,$209a
    otir
    call GameSession_MapTerrain
    xor a
.terrain_set:
    ld (pattern_back),a
    ld hl,0
    call GamePattern_Address
    ld hl,$8000
    ld de,2048
    call upload
    ld hl,$4000
    call GamePattern_Address
    ld hl,$8800
    ld de,2048
    call upload
    ld a,(pattern_back)
    inc a
    cp 8
    jr c,.terrain_set
    ld a,$ff
    ld hl,pattern_phases
    ld b,8
.invalidate:
    ld (hl),a
    inc hl
    djnz .invalidate
    ld (pattern_front),a
    ld (oldcol),a
    ld (oldrow),a
    ld (seen),a
    ld (seen+1),a
    ld (seen+2),a
    ld (seen+3),a
    ld (Game_LastWorldGeneration),a
    xor a
    ld (pattern_next),a
    ld (back),a
    ld hl,$2600
    ld de,$2601
    ld bc,511
    ld (hl),a
    ldir
    ld (GameDirty_Lengths),a
    ld (GameDirty_Lengths+1),a
    ld hl,$28c0
    ld de,$28c1
    ld bc,63
    ld (hl),255
    ldir
    call Game_Position
    call GameSession_Prewarm
    call Game_Actors
    call GameSprites_Init
    call GameHUD_Init
    call GameSprites_Prepare
    call GameHUD_Prepare
    call render
    di
    reg 15,2
.leave:
    in a,($99)
    and $40
    jr nz,.leave
.enter:
    in a,($99)
    and $40
    jr z,.enter
    reg 15,0
    in a,($99)
    call commit
    di
    reg 1,$62
    ld hl,(clock_ticks)
    ld (input_tick),hl
    ld a,1
    ld (ready),a
    ei
.done:
    ret

GameSession_BuildFlags:
    call GameSession_ClearFlags
    xor a
    ld (GameSession_Phase),a
.phase:
    ld a,(GameSession_Phase)
    and 7
    ld (fx),a
    ld a,(GameSession_Phase)
    REPT 3
    srl a
    ENDR
    ld (fy),a
    ld a,(GameSession_Phase)
    add a,4
    ld ($7000),a
    call $a300
    xor a
    ld (Game_RadarCount),a
    call GameSession_DrawFlagDots
    call GameSession_EncodeFlags
    ld a,(GameSession_Phase)
    call GameSession_WriteFlags
    ld hl,GameSession_Phase
    inc (hl)
    ld a,(hl)
    cp 64
    jr nz,.phase
    xor a
    ld (GameSession_FlagGeneration),a
    ld (GameSession_FlagIndex),a
    ld hl,Flag_Active+1
    ld b,10
.collected:
    push bc
    push hl
    ld a,(hl)
    or a
    call z,GameSession_RemoveFlag
    pop hl
    inc hl
    ld a,(GameSession_FlagIndex)
    inc a
    ld (GameSession_FlagIndex),a
    pop bc
    djnz .collected
    ld a,$ff
    ld hl,GameSession_FlagLoaded
    ld b,8
.keys:
    ld (hl),a
    inc hl
    djnz .keys
    ret

GameSession_DrawFlagDots:
    ld ix,Flag_Records
    ld b,10
.dot:
    push bc
    call GameSession_FlagCoordinates
    call Game_RadarDot
    ld de,6
    add ix,de
    pop bc
    djnz .dot
    ret
GameSession_FlagCoordinates:
    ld a,(ix+0)
    and 31
    add a,8
    ld (Game_RadarX),a
    ld a,(ix+1)
    sub $98
    REPT 3
    add a,a
    ENDR
    ld c,a
    ld a,(ix+0)
    REPT 3
    rlca
    ENDR
    and 7
    or c
    jp Game_RadarCellY

GameSession_EncodeFlags:
    ld a,(Game_RadarCount)
    ld ($ce80),a
    ld b,a
    ld c,146
    ld hl,Game_RadarAddresses
    ld de,$ce81
.name:
    ld a,$21
    ld (de),a
    inc de
    push bc
    ldi
    ldi
    pop bc
    ld a,$36
    ld (de),a
    inc de
    ld a,c
    ld (de),a
    inc de
    inc c
    djnz .name
    ld a,$c9
    ld (de),a
    ld hl,Game_RadarPatterns
    ld de,$ceb4
    ld bc,80
    ldir
    ld hl,Game_RadarColors
    ld de,$cf04
    ld bc,80
    ldir
    ld ix,Flag_Records
    ld iy,$cf54
    ld b,10
.metadata:
    push bc
    call GameSession_FlagCoordinates
    ld a,(Game_RadarY)
    ld c,a
    ld a,(fy)
    add a,c
    ld (doty),a
    and $f8
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(Game_RadarX)
    ld c,a
    ld a,(fx)
    add a,c
    ld (dotx),a
    REPT 3
    rrca
    ENDR
    and 7
    add a,26
    ld e,a
    ld d,HIGH names
    add hl,de
    ld a,(hl)
    sub 64
    add a,a
    add a,a
    add a,a
    add a,52
    ld c,a
    ld a,(doty)
    and 7
    add a,c
    ld (iy+0),a
    ld a,(GameSession_Phase)
    ld (iy+1),a
    ld a,(dotx)
    and 7
    ld c,a
    ld a,$80
    jr z,.mask
.rotate:
    rrca
    dec c
    jr nz,.rotate
.mask:
    ld (iy+2),a
    ld de,3
    add iy,de
    ld de,6
    add ix,de
    pop bc
    djnz .metadata
    ret

GameSession_UI:
    call GameSession_AudioStop
    xor a
    ld (ready),a
    di
    reg 1,$22
    reg 16,0
    ld hl,GameSession_UIPalette
    ld bc,$209a
    otir
    ei
.frame:
    ld hl,(clock_ticks)
    ld (input_tick),hl
    ld a,SESSION_BANK
    ld ($7000),a
    call $8000
    push af
    call GameAudio_Tick
    pop af
    cp 2
    jr z,.start
    cp 3
    jr z,.resume
    ei
    halt
    jr .frame
.start:
    xor a
    ld (GameSession_LoadKind),a
    call GameSession_ColdLoad
    ld a,SESSION_BANK
    ld ($7000),a
    call $8003
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
    ret
.resume:
    xor a
    ld (Session_State),a
    call GameSession_Video
    ld a,$10
    ld ($e9f5),a
    ld a,1
    ld (Audio_NewScene),a
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
    ret

GameSession_NextRound:
    ld a,(Full_Attract)
    or a
    jp nz,GameSession_EndDemo
    ld a,1
    ld (GameSession_LoadKind),a
    call GameSession_ColdLoad
    ld a,(Full_ChallengeBypass)
    ld b,a
    xor a
    ld (Full_ChallengeBypass),a
    ld a,($e1b0)
    and 3
    ret nz
    ld a,b
    or a
    ret nz
    ld a,7
    ld (Session_State),a
    xor a
    ld (Session_Drawn),a
    ld a,$40
    ld ($e9f5),a
    ld a,1
    ld (Audio_NewScene),a
    jp GameSession_UI

GameSession_Death:
    ld a,(Full_Attract)
    or a
    jp nz,GameSession_EndDemo
    ld a,SESSION_BANK
    ld ($7000),a
    call $8006
    ld b,a
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
    ld a,b
    or a
    jp z,Game_Restart
    cp 1
    jp z,GameSession_NextRound
    cp 3
    jr z,.restore
    ld a,2
    ld (Session_State),a
    xor a
    ld (Session_Drawn),a
    ld a,4
    ld ($e9f5),a
    jp GameSession_UI
.restore:
    ld a,2
    ld (GameSession_LoadKind),a
    jp GameSession_ColdLoad


GameAudio_Init:
    xor a
    ld hl,$d150
    ld de,$d151
    ld bc,7
    ld (hl),a
    ldir
    ld a,1
    ld (Audio_NewScene),a
    ld a,(ticks)
    ld (Audio_LastUI),a
    ret
GameAudio_Tick:
    ld a,(ticks)
    ld hl,Audio_LastUI
    sub (hl)
    cp 2
    ret c
    srl a
    ld (Audio_Elapsed),a
    add a,a
    add a,(hl)
    ld (hl),a
    ld a,AUDIO_BANK
    ld ($7000),a
    call Audio_RuntimeStep
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
    ret
GameAudio_Event:
    or a
    ret nz                  ; Shared worker observes original native requests.
    ld a,1
    ld (Audio_NewScene),a
    ret
GameAudio_EVENT_BACKGROUND EQU 0
GameAudio_EVENT_FLAG EQU 1
GameAudio_EVENT_SPECIAL_FLAG EQU 2
GameAudio_EVENT_SMOKE EQU 3
GameAudio_EVENT_DEATH EQU 4
GameAudio_EVENT_CLEAR EQU 5
GameAudio_EVENT_GAMEOVER EQU 6
Full_TurboOn:
Full_TurboOff:
    ret                     ; Fixed measured CPU frequency, no factory turbo.

; UI requests use the original bitmap mode only outside active gameplay.
register:
    out ($99),a
    ld a,b
    or $80
    out ($99),a
    ret
stage_wait_command:
    di
    reg 15,2
.busy:
    in a,($99)
    and 1
    jr nz,.busy
    reg 15,0
    ei
    ret
Session_CopyImage:
    xor a
    out ($99),a
    ld a,$40
    out ($99),a
    ld a,SESSION_IMAGE_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,$4000
    call upload
    ld a,SESSION_DATA_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,$2a00
    call upload
    ld a,SESSION_BANK
    ld ($7000),a
    ret

GameSession_AfterFrame:
    call GameSession_SpecialFrame
    ld a,(Full_Attract)
    or a
    jr z,.human
    ld a,SESSION_BANK
    ld ($7000),a
    call $8009
    ld a,(Session_State)
    or a
    jp nz,GameSession_UI
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
    ret
.human:
    jp GameSession_PopupFrame
GameSession_EndDemo:
    xor a
    ld (Full_Attract),a
    ld (Session_Drawn),a
    ld a,1
    ld (Session_State),a
    jp GameSession_UI

GameSession_DecorAddress:
    ld a,SESSION_DECOR_BANK
    ld ($7000),a
    ld a,(phase)
    ld h,0
    ld l,a
    REPT 7
    add hl,hl
    ENDR
    set 7,h
    ret
GameSession_LabelNames:
    ld a,(Full_Player)
    or a
    ret z
    call GameSession_DecorAddress
    ld b,(hl)
    inc hl
.name:
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld a,(hl)
    inc hl
    ld (de),a
    djnz .name
    jp GameSession_PhaseBank
GameSession_LabelUpload:
    ld a,(Full_Player)
    or a
    ret z
    ld a,(prior_phase)
    ld hl,phase
    cp (hl)
    ret z
    call GameSession_DecorAddress
    ld a,(hl)
    ld (GameSession_Count),a
    push hl
    ld hl,$04e0
    call GamePattern_Address
    pop hl
    ld de,16
    add hl,de
    ld a,(GameSession_Count)
    call tile_bytes
    call upload
    call GameSession_DecorAddress
    push hl
    ld hl,$44e0
    call GamePattern_Address
    pop hl
    ld de,48
    add hl,de
    ld a,(GameSession_Count)
    call tile_bytes
    call upload
    jp GameSession_PhaseBank

GameSession_PopupFrame:
    ld a,(paused)
    or a
    ret nz
    ld a,(Popup_Active)
    or a
    jr z,.pending
    ld a,(ticks)
    ld hl,Popup_Tick
    sub (hl)
    ld b,a
    ld a,(ticks)
    ld (hl),a
    ld a,(Popup_Age)
    add a,b
    ld (Popup_Age),a
    cp 45
    jr nc,.erase
    ld a,(Death_State)
    ld hl,Popup_Pending
    or (hl)
    jr z,.pending
.erase:
    ld a,(Popup_X)
    ld b,a
    ld a,(Popup_Y)
    ld c,a
    ld d,3
.restore:
    push de
    call Game_RestoreOne
    inc b
    pop de
    dec d
    jr nz,.restore
    xor a
    ld (Popup_Active),a
    ld hl,Game_WorldChanged
    inc (hl)
.pending:
    ld a,(Popup_Pending)
    or a
    ret z
    xor a
    ld (Popup_Pending),a
    ld a,(Death_State)
    or a
    ret nz
    ld a,($e250)
    dec a
    cp 10
    ret nc
    ld b,a
    ld a,($e023)
    and 1
    ld a,b
    jr z,.index
    add a,10
.index:
    ld (Popup_Index),a
    ld a,(Flag_X)
    ld (Popup_X),a
    ld a,(Flag_Y)
    inc a
    ld (Popup_Y),a
    ld a,(ticks)
    ld (Popup_Tick),a
    xor a
    ld (Popup_Age),a
    inc a
    ld (Popup_Active),a
    ld hl,Game_WorldChanged
    inc (hl)
    ret
GameSession_PopupOverlay:
    ld a,(Popup_Active)
    or a
    ret z
    ld a,(mapcol)
    ld b,a
    ld a,(Popup_X)
    sub b
    cp 1
    jr c,.road
    cp 22
    jr nc,.road              ; Complete24px label stays before the mixed border.
    ld a,92
    jr .patch
.road:
    ld a,GAME_EMPTY_TILE
.patch:
    ld (Game_PatchID),a
    ld a,(Popup_X)
    ld b,a
    ld a,(Popup_Y)
    ld c,a
    ld a,(Game_PatchID)
    push af
    call Game_PatchOne
    pop af
    inc b
    cp GAME_EMPTY_TILE
    jr z,.second
    inc a
.second:
    push af
    call Game_PatchOne
    pop af
    inc b
    cp GAME_EMPTY_TILE
    jr z,.third
    inc a
.third:
    jp Game_PatchOne
GameSession_PopupUpload:
    ld a,(Popup_Active)
    or a
    ret z
    ld a,(pattern_back)
    ld e,a
    ld d,0
    ld hl,Popup_Loaded
    add hl,de
    ld a,(Popup_Index)
    cp (hl)
    ret z
    ld (hl),a
    ld l,a
    ld h,0
    REPT 4
    add hl,hl
    ENDR
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ld de,$a000
    add hl,de
    push hl
    ld a,SESSION_DECOR_BANK
    ld ($7000),a
    ld hl,$02e0
    call GamePattern_Address
    pop hl
    ld de,24
    push hl
    call upload
    ld hl,$42e0
    call GamePattern_Address
    pop hl
    ld de,24
    add hl,de
    call upload
    jp GameSession_PhaseBank

; The native8-bit stage packet can wrap. Once a player's display reaches99,
; keep it there until a new game, independently of the other player's packet.
GameSession_DisplayRound:
    push bc
    push de
    push hl
    ld a,($e1b0)
    ld b,a
    ld a,(Full_Player)
    ld e,a
    ld d,0
    ld hl,GameSession_RoundCaps
    add hl,de
    ld a,(hl)
    or a
    ld a,100
    jr nz,.done
    ld a,b
    cp 100
    jr c,.done
    ld (hl),1
    ld a,100
.done:
    pop hl
    pop de
    pop bc
    ret

; Same guard and rollback as the pinned production session. It snapshots only
; motion/camera fields, preserving fuel, score, enemies and original tick clocks.
    INCLUDE "session-motion.inc"
GameSession_ValidateMotion:
    ld a,(Session_GuardActive)
    or a
    ret z
    call GameSession_ContactWall
    ret nc
    ; Native centering and the doubled primary step can disagree at a corner.
    ; Retry the primary step with the pre-step perpendicular coordinates. Both
    ; candidates face the original packed-wall lookup; no wall can be bypassed.
    ld a,($d217)             ; Pre-step axis (E06B), not the new escape heading.
    or a
    jr z,.vertical
    ld hl,($d21a)            ; E06E/E06F: perpendicular fractional/fine Y
    ld ($e06e),hl
    ld a,($d21e)
    ld ($e072),a
    ld hl,($d206)
    ld ($e04e),hl
    ld a,($d209)
    ld ($e051),a
    ld hl,($d221)            ; Full_MSXPan updates the player's screen word only.
    ld ($e075),hl
    jr .retry
.vertical:
    ld hl,($d218)            ; E06C/E06D: perpendicular fractional/fine X
    ld ($e06c),hl
    ld a,($d21c)
    ld ($e070),a
    ld hl,($d204)
    ld ($e04c),hl
    ld a,($d208)
    ld ($e050),a
    ld hl,($d21f)
    ld ($e073),hl
.retry:
    push ix
    ld ix,$e068
    call $815a              ; Recompute the native base-cell pointer.
    pop ix
    call GameSession_ContactWall
    jr c,.blocked
    ; The rejected centering decision may have reversed primary velocity.
    ; Keep the pre-step heading for the accepted primary-only candidate.
    ld hl,($d215)
    ld ($e069),hl
    ld a,($d217)
    ld ($e06b),a
    ret
.blocked:
    jp Session_RestoreMotion

GameSession_ContactWall:
    call $9774
    ld a,d
    and 7
    add a,a
    add a,a
    add a,a
    ld c,a
    ld a,e
    rlca
    rlca
    rlca
    and 7
    or c
    ld c,a
    ld a,e
    and 31
    ld d,a
    ld e,c
    xor a
    call $94e0
    ret

GameSession_SpecialFrame:
    ld a,(clock_ticks)
    and 16
    ld hl,GameSession_Blink
    cp (hl)
    ret z
    ld (hl),a
    ret

; SCREEN4 has two colors per eight-pixel row. Preserve yellow flags when an
; enemy shares that row. The player's marker, drawn last, has color priority.
GameSession_RadarColor:
    push bc
    inc h
    ld b,(hl)
    ld a,b
    rrca
    rrca
    rrca
    rrca
    xor b
    and 15
    jr nz,.pattern_ready
    dec h
    ld (hl),0
    inc h
.pattern_ready:
    ld a,ixl
    cp $68
    jr z,.player
    ld a,b
    and $f0
    cp $c0
    jr nz,.red
    dec h
    ld a,(hl)
    inc h
    or a
    ld a,b
    jr nz,.store
.red:
    ld a,$6a
    jr .store
.player:
    ld a,(GameSession_Blink)
    or a
    ld a,$8a
    jr z,.store
    ld a,$ba
.store:
    ld (hl),a
    dec h
    pop bc
    ret

; Silence the real PSG before any blocking mode/map transfer, discard effect
; debt, and invalidate its register cache. Native melody request is preserved.
GameSession_AudioStop:
    ld a,7
    out ($a0),a
    in a,($a2)
    or $3f
    out ($a1),a
    ld b,3
    ld c,8
.volume:
    ld a,c
    out ($a0),a
    xor a
    out ($a1),a
    inc c
    djnz .volume
    ld hl,$e9a0
    ld de,$e9a1
    ld bc,79
    ld (hl),0
    ldir
    xor a
    ld ($e9f4),a
    ld a,($e9f6)
    and $3f
    ld ($e9f6),a
    ld hl,$e9b0
    ld b,14
.invalidate:
    ld (hl),255
    inc hl
    djnz .invalidate
    ld a,(clock_ticks)
    ld (Audio_LastUI),a
    ld a,1
    ld (Audio_NewScene),a
.done:
    ret

; Source1B03 waits for the minimum settlement, then1B0A waits for sound ready.
; API: tail-called from Round_Tick only in state1, on the main RAM segment with
; the native8000 bank already selected. AF/HL clobbered. RET yields each tick;
; no HALT/spin, state RAM or bank switch. 33 code bytes use reserved cold RAM.
; The regular pause gate freezes it.
GameSession_CompletionWait:
    ld hl,$e24b
    ld a,(hl)
    and 63
    jr z,.settled
    inc (hl)
    ld a,(hl)
    and 63
    ret nz
.settled:
    ld a,(Full_Attract)
    or a
    jr nz,.bonus           ; Silent demos must not wait on an unplayed request.
    ld a,($e9f5)
    bit 5,a
    ret nz                 ; The music cursor alone clears this bit at score end.
.bonus:
    ld a,2
    ld (Round_State),a
    jp Completion_Begin

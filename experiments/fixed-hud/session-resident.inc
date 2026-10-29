; Full sessions share native rules with the audio branch. This file contains
; only resident mapper/VDP boundaries; cold work lives in independent Page0 RAM.
Session_State EQU $c7d0
Session_Drawn EQU $c7d1
Session_Credits EQU $c7d2
Session_Keys EQU $c7d3
Session_High EQU $c7d4
Session_Edges EQU $c7dc
Session_Ready EQU $c7dd
Session_HeldDirections EQU $c7de
Session_SelectedDirection EQU $c7df
Full_Players EQU $c7eb
Full_Player EQU $c7ec
Full_NewBoard EQU $c7ed
Full_Attract EQU $c7ee
Full_NumberBlack EQU $c7ef
Full_ChallengeBypass EQU $c7f0
Full_UIHeld EQU $c7f1
Full_UIEdges EQU $c7f2
Full_AttractClock EQU $c7ca
Full_Shadow EQU $d230
Full_Loading EQU $dfc8
Full_Layout EQU $dfc9
Full_ResourceBank EQU $dfbd
Flag_Records EQU $df80
Full_DebugHeld EQU $dfcb
GameSession_MainSegment EQU $c0d0
GameSession_MapSegments EQU $c0d1
GameSession_FlagSegment EQU $c0d3
GameSession_FlagGeneration EQU $c0d4
GameSession_FlagLoaded EQU $2860
GameSession_FlagIndex EQU $c0d9
GameSession_FlagMask EQU $c0da
GameSession_Count EQU $c0db
GameSession_Phase EQU $c0dc
GameSession_LoadKind EQU $c0dd
GameSession_SaveFlags EQU $c0e0
GameSession_PauseHeld EQU $c0ea
GameSession_Key0 EQU $c0eb
GameSession_Key8 EQU $c0ec
Popup_Pending EQU $dfe5
Popup_Active EQU $dfe4
Popup_X EQU $dfe6
Popup_Y EQU $dfe7
Popup_Tick EQU $dfe8
Popup_Age EQU $dfe9
Popup_Index EQU $dfea
Popup_Loaded EQU $2880
GameSession_RoundCaps EQU $c0f4
GameSession_Blink EQU $c0f6
GameSession_FlagOffSegment EQU $c0f7
Session_WallBlocks EQU $c7e6
Session_RiskFrames EQU $c7e8
Session_GuardActive EQU $c7e9
ticks EQU clock_ticks

GameSession_Boot:
    ld a,SESSION_COLD_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,GameSession_ColdStart
    ld bc,GameSession_ColdEnd-GameSession_ColdStart
    ldir
    call GameSession_ColdBoot
    ld a,SESSION_BOOT_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,GameSession_StartupWorkers
    ld bc,GameSession_BootEnd-GameSession_StartupWorkers
    ldir
    IF SESSION_HARDWARE_CHECK
    call GameSession_BootShow
    ENDIF
    ; Boot bitmap scratch must not become native game/audio state.
    xor a
    ld hl,$d300
    ld de,$d301
    ld bc,$1fff
    ld (hl),a
    ldir
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld hl,$a000
    ld de,$e000
    ld bc,$1000
    ldir
    call GameAudio_Init
    jp GameSession_UI

; Page0 map data may be selected only inside these resident helpers. The
; foreground returns to its original RAM segment before any Page0 code/data use.
GameSession_MapPage:
    push hl
    ld hl,GameSession_MapSegments
    or a
    jr z,.selected
    inc hl
.selected:
    ld a,(hl)
    out ($fc),a
    pop hl
    ret
GameSession_RestorePage0:
    ld a,(GameSession_MainSegment)
    out ($fc),a
    ret
GameSession_CopyMap:
    ld ($7000),a
    ld a,c
    out ($fc),a
    ld hl,$8000
    ld de,0
    ld bc,$4000
    ldir
    jp GameSession_RestorePage0

; B/C=world top-left, IY=nine theme-local tile IDs in mapped ROM.
GameSession_PatchObject:
    push ix
    ld ix,$0303
.row:
    push bc
    ld a,c
    and $80
    rlca
    call GameSession_MapPage
    ld a,c
    and 127
    ld l,a
    ld h,0
    REPT 7
    add hl,hl
    ENDR
    ld e,b
    ld d,0
    add hl,de
    ld ixl,3
.cell:
    ld a,(iy+0)
    ld (hl),a
    inc hl
    inc iy
    dec ixl
    jr nz,.cell
    pop bc
    inc c
    dec ixh
    jr nz,.row
    pop ix
    jp GameSession_RestorePage0

GameSession_MapEdges:
    ld a,(Full_Layout)
    add a,a
    add a,a
    add a,a
    ld e,a
    ld a,(fx)
    add a,e
    ld e,a
    ld d,0
    ld hl,GameSession_EdgeBanks
    add hl,de
    ld a,(hl)
    ld ($7000),a
    ret
GameSession_PhaseBank:
    ld a,(phase)
    add a,4
    ld ($7000),a
    ret
GameSession_Boundaries:
    call GameSession_MapEdges
    call boundaries
    jp GameSession_PhaseBank

; Fill every inactive cache with the actual initial phase while display is off.
; First turns then patch a known phase instead of paying a complete atlas load.
GameSession_Prewarm:
    ld a,(cx)
    and 7
    ld (fx),a
    ld b,a
    ld a,(cy)
    and 7
    ld (fy),a
    add a,a
    add a,a
    add a,a
    or b
    ld (phase),a
    xor a
.set:
    ld (pattern_back),a
    push af
    call GameSession_PhaseBank
    ld a,($8900)
    ld (count),a
    call hud_upload
    call GameSession_MapEdges
    call GameBoundary_Upload
    call GameSession_FlagUpload
    call GameSession_LabelUpload
    pop af
    inc a
    cp 8
    jr c,.set
.done:
    ret

; Blink variants differ at exactly the original S point's one pattern bit.
; Colors and the other flag glyphs remain valid in this exact phase/set.
GameSession_FlagBlinkUpload:
    call GameSession_SelectFlags
    ld a,(phase)
    ld h,a
    ld l,239
    ld e,(hl)
    inc l
    ld d,(hl)
    ld a,(de)
    ld b,a
    ld a,e
    sub 52
    ld l,a
    ld h,0
    ld de,$0490
    add hl,de
    call GamePattern_Address
    ld a,b
    out ($98),a
    jp GameSession_RestorePage0

GameSession_UIPalette:
    INCBIN "session-ui-palette.bin"

Full_MarkLogicalSmokeRows:
    push af
    push bc
    ld a,(Smoke_X)
    ld b,a
    ld a,(Smoke_Y)
    ld c,a
    call GameSmoke_MarkCloud
    pop bc
    pop af
    ret
Full_EnqueueSmoke:
    jp Smoke_Enqueue
Full_ObjectAtTile:
    push bc
    push de
    push hl
    ld a,b
    sub 3
    jr c,.none
    ld l,a
    ld h,$e3
    ld a,(hl)
    cp 32
    jr nc,.none
    ld e,a
    ld a,c
    sub 3
    jr c,.none
    ld l,a
    ld a,(hl)
    cp 56
    jr nc,.none
    ld l,a
    ld h,0
    REPT 5
    add hl,hl
    ENDR
    ld d,$98
    add hl,de
    call $ac03
    jr .done
.none:
    xor a
.done:
    pop hl
    pop de
    pop bc
    ret

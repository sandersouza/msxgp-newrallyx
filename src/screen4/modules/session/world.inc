; Module contract: Main Page0 cold initialization, round loading, map construction; display/audio gated.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
; Runs from independent Page0 RAM. Resident helpers temporarily map other RAM
; segments and restore this segment before returning. No active-frame rebuild.
    INCLUDE "../../session-phase.inc"
    INCLUDE "../../session-sprite-static.inc"
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

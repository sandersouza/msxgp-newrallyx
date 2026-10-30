; Reuse contract: session-decorations (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameSession_AfterFrame, GameSession_EndDemo, GameSession_LabelNames,
;   GameSession_LabelUpload, GameSession_PopupFrame, GameSession_PopupOverlay,
;   GameSession_PopupUpload
; Inputs: Native player/event/camera state, current pattern phase and decor bank. Run
;   AfterFrame after native simulation; names/overlay/uploads follow the existing renderer
;   order.
; Outputs: Exact player label and score inscriptions through existing dirty/lazy caches; demo
;   completion follows native lifecycle.
; Registers: Common caller-saved ABI.
; Interrupts: Foreground only; VDP helpers keep existing latch ownership. No new per-frame
;   polling or transfer is added.
; Memory / hardware: Existing DFE4..DFEA popup state, 2880 keys and shared UI/game scratch.
;   UI/video restoration invalidates stale popup state.
; Reuse boundary: Game-specific event/label format. Rebind at assembly time; do not reuse UI
;   scratch while a gameplay popup owns it.
; Keep this summary synchronized with the registry and modules/README.md.

; Module contract: Round/player labels and point inscriptions; existing phase caches and scratch.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
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

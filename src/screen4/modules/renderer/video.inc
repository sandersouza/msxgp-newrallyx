; Reuse contract: session-video (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameSession_Video
; Inputs: Cold mode transition; main Page0, native seed, world/HUD resources and renderer
;   aliases valid.
; Outputs: SCREEN4 registers/palette, terrain/cache/HUD/sprite restoration, first commit and
;   ready latch; returns EI.
; Registers: Common caller-saved ABI.
; Interrupts: Owns cold DI/EI and display-enable sequence; must not run concurrently with
;   active presentation.
; Memory / hardware: Existing popup invalidation, terrain, eight pattern sets, two name tables
;   and sprite areas; no new buffers.
; Reuse boundary: Host-specific mode/palette/restoration policy; replace this binding for
;   another viewport/resource layout instead of adding a runtime branch.
; Keep this summary synchronized with the registry and modules/README.md.

; Module contract: Cold SCREEN4 mode/terrain/cache restore; DI then established presentation setup.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
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

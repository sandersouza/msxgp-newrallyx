; Module contract: Map phase/theme sources and cold-prewarm eight inactive pattern sets; HUD retained.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
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

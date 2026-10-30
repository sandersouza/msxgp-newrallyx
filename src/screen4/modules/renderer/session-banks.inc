; Reuse contract: session-render-banks (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameSession_MapEdges, GameSession_PhaseBank, GameSession_Boundaries,
;   GameSession_Prewarm
; Inputs: Current Full_Layout/fx/phase; prewarm additionally requires camera, exact
;   HUD/boundary/flag/label tables and display off.
; Outputs: Selects the existing phase/theme bank; Boundaries restores phase bank. Prewarm
;   initializes all eight physical cache keys and glyph sets.
; Registers: MapEdges AF/DE/HL scratch; PhaseBank AF scratch; other entries common
;   caller-saved ABI.
; Interrupts: Prewarm is cold-only; VDP helpers retain their DI/EI behavior. Active helpers
;   keep current foreground mapper ownership.
; Memory / hardware: Existing cache key state and eight 16 KiB pattern/color sets; no new
;   RAM/VRAM or transfer staging.
; Reuse boundary: Full-session packed-layout binding. Supply matching phase/theme resources;
;   never prewarm a visible set during gameplay.
; Keep this summary synchronized with the registry and modules/README.md.

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
    ; phase indexes immutable ROM resources, not a RAM-mapper segment. Keep
    ; this Page2 cartridge switch distinct from Page0 map/cache ownership.
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
    ; Build all eight inactive sets only while the display is off. Repeating
    ; this work in active frames would turn startup latency into frame stalls.
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

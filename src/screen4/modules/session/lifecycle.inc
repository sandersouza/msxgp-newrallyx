; Reuse contract: session-lifecycle (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameSession_UI, GameSession_NextRound, GameSession_Death
; Inputs: Native session/player/attract state, main Page0 and generated UI/native bank
;   bindings.
; Outputs: Existing menu, challenge, death/restart, round and alternating-player transitions;
;   returns or tail-enters the original state machine.
; Registers: Common caller-saved ABI.
; Interrupts: Owns blocking cold UI HALT/display/DI/EI sequence. Never call as an IRQ service
;   or renderer callback.
; Memory / hardware: Existing session/native/UI aliases and their cold/game lifetimes.
;   UI alone reuses input_tick as its last consumed refresh. Native RNG E000
;   advances once per elapsed refresh; active play retains its existing call.
;   The catch-up loop clobbers AF/BC/DE/HL, preserves IX/IY/IFF, owns Page2
;   briefly. Stack: two-byte loop scratch plus eight bytes for the original
;   PRNG CALL/three saved pairs, excluding the unchanged IRQ stack envelope.
;   IRQ never accesses that mapping.
; Reuse boundary: Game-specific policy with direct native entry calls. Supply another
;   assembly-time policy for another game.
; Keep this summary synchronized with the registry and modules/README.md.

; Module contract: Native menu, round, death and player-turn transitions; blocking cold execution.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
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
    ld hl,(clock_ticks)
    ld (input_tick),hl
    ei
.frame:
    ld hl,(clock_ticks)
    ld de,(input_tick)
    ld (input_tick),hl
    or a
    sbc hl,de
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
.random:
    ld a,h
    or l
    jr z,.ui
    dec hl
    push hl
    call $8f24              ; Original PRNG, also used unchanged in Game_Frame.
    pop hl
    jr .random
.ui:
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

; Reuse contract: audio-stop-completion (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameSession_AudioStop, GameSession_CompletionWait
; Inputs: Stop: main native audio RAM valid. CompletionWait: tail-called from native
;   Round_Tick state 1 with native bank/main Page0 already mapped; regular pause gate
;   surrounds it.
; Outputs: Stop silences real PSG, clears effect debt and invalidates cache while preserving
;   native melody request. Completion yields until original settlement/audio-ready condition,
;   then tail-enters bonus.
; Registers: Stop AF/BC/DE/HL scratch. CompletionWait AF/HL scratch until its existing tail
;   call.
; Interrupts: IFF unchanged; no HALT/spin, extra state or bank switch in CompletionWait. IRQ
;   must not compete for PSG.
; Memory / hardware: Existing E9xx native audio cache, native round clock/state and
;   Audio_LastUI; no additional state.
; Reuse boundary: Native event pacing/PSG binding; preserve request completion semantics
;   rather than replacing them with a delay.
; Keep this summary synchronized with the registry and modules/README.md.

; Silence the real PSG before any blocking mode/map transfer, discard effect
; debt, and invalidate its register cache. Native melody request is preserved.
; Module contract: PSG silence and native completion pacing; foreground, existing state only.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
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

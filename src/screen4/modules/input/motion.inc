; Reuse contract: input-motion (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameSession_DisplayRound, GameSession_ValidateMotion, GameSession_ContactWall,
;   Session_SaveMotion, Session_RestoreMotion
; Inputs: Native player/movement/wall fields, Session_GuardActive and the established pre-step
;   snapshot. Save before native motion; Validate after motion.
; Outputs: Preserves accepted primary movement or restores the previous native motion
;   snapshot; no wall bypass. DisplayRound is a display-only accessor and never advances the
;   round.
; Registers: Common caller-saved ABI across native calls; DisplayRound preserves BC/DE/HL and
;   returns its existing biased/capped value in A.
; Interrupts: Foreground only, no added synchronization; native motion and input sampling
;   order remain required.
; Memory / hardware: Existing D200..D222 motion snapshot and native E0xx fields; no extra
;   input or movement buffer.
; Reuse boundary: Native gameplay policy. Keep original native movement/wall entry points and
;   snapshot encoding; use another compile-time adapter for another game.
; Keep this summary synchronized with the registry and modules/README.md.

; Module contract: Display-round accessor and native corner rollback; original input/motion consistency.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
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
    INCLUDE "../../session-motion.inc"
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

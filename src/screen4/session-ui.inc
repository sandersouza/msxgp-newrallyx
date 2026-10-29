    jp Full_UIFrame
    jp GameSession_AfterStart
    jp Full_SessionDeath
    jp Full_DemoFrame
    jp Full_DebugAdvance
Session_Registers:
    db 0,6,1,$22,8,$2a,25,0,26,0,27,0,23,0,2,$5f,14,4,15,0
Full_UIReveal EQU $dfe4
Full_UITimer EQU $dfe6
Full_UICastDone EQU $dfe7
Full_UIWidth EQU $dfe8
Full_UIRows EQU $dfe9
Full_UIDestination EQU $dfea
Full_UIRowDestination EQU $dfec
Full_UIBackground EQU $dfee
Full_UIForeground EQU $dfef
Full_UIPairs EQU Score_Old
GameSession_AfterStart:
    call Full_SessionInit
    ld hl,Session_High
    ld de,$e060
    ld bc,8
    ldir
    ld a,(Session_Credits)
    ld ($e024),a
    xor a
    ld (Session_State),a
    ld (Session_Drawn),a
    ld (Session_Ready),a
    ld (paused),a
    ld (Session_HeldDirections),a
    ld (Session_SelectedDirection),a
    ret
    INCLUDE "session-ui-options.inc"
    INCLUDE "session-title.inc"
    INCLUDE "full-ui.inc"
    INCLUDE "session-challenge.inc"
    INCLUDE "session-turns.inc"
    INCLUDE "full-ui-data.inc"

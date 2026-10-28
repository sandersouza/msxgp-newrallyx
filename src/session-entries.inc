; Stable banked ABI, independent of the expanded full-game UI implementation.
    ASSERT $ == $b800
    jp Session_Frame
    jp Session_AfterStart
    jp Session_Reset
    jp Session_FourWay
    jp Session_SaveMotion
    jp Session_RestoreMotion
    jp Full_SessionDeath
    jp Full_DrawRound
    jp Full_DemoFrame
    jp Full_DebugAdvance
    IF FLAG_POPUPS
    jp Full_PopupFrame
    ENDIF

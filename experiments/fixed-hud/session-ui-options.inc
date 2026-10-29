; Optional cold-title component. Remove/comment the INCLUDE to omit its code,
; bitmap and draw call. MSX_LOGO=0 also disables it for a separate test build.
    IF SESSION_MSX_LOGO
    INCLUDE "session-msx-logo.inc"
    ENDIF

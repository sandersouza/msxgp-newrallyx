; Seven complete immutable drawings in the unused2E40..2FFF sprite suffix.
; Four cardinal poses plus initial/return animation variants. All other poses
; and every clipped/sentinel car retain the original private double buffers.
GameSession_SharedInit:
    ld hl,$2e40
    call GS_Address
    ld hl,GameSprites_Templates+0*64
    ld de,64
    call GS_Upload
    ld hl,GameSprites_Templates+1*64
    ld de,64
    call GS_Upload
    ld hl,GameSprites_Templates+2*64
    ld de,64
    call GS_Upload
    ld hl,GameSprites_Templates+3*64
    ld de,64
    call GS_Upload
    ld hl,GameSprites_Templates+6*64
    ld de,64
    call GS_Upload
    ld hl,GameSprites_Templates+9*64
    ld de,64
    call GS_Upload
    ld hl,GameSprites_Templates+10*64
    ld de,64
    jp GS_Upload
GameSession_SharedSprite:
    ld a,(GS_Animation)
    ld l,a
    ld h,0
    ld de,GameSession_SharedIDs
    add hl,de
    ld a,(hl)
    cp 255
    ret z
    ld (GS_PatternID),a
    call GS_InteriorAttributes
    scf
    ret
GameSession_SharedIDs:
    db 200,208,216,224,255,255,232,255,255,240,248,255

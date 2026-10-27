; BC=previous logical anchor, DE=new anchor. Prioritize the existing footprint
; at crossings and along seams. Ordinary one-cell motion stays optional.
; Radar_UpdatePoints retains the RADAR_CACHE_BANK lookup mapping throughout.
Full_RadarDepartureNative:
    ld iyh,d
    ld iyl,e
    ld d,b
    ld e,c
    call .mark
    push de
    ld d,iyh
    ld e,iyl
    call .mark
    pop hl
    ld a,l
    xor e
    ld b,a
    ld a,h
    xor d
    or b
    jr nz,.crossing
    push hl
    dec hl
    ld a,l
    and e
    ld b,a
    ld a,h
    and d
    or b
    pop hl
    jr nz,.crossing          ; A moving dot still spans more than one cell.
    ld de,0
    jr .queue
.crossing:
    ; When a footprint expands across a seam, replace the existing side first.
    ; The new side has no old ink to erase and remains an ordinary dirty cell.
    ld a,l
    and e
    ld b,a
    ld a,h
    and d
    or b
    jr z,.disjoint
    ex de,hl
    jr .queue
.disjoint:
    ld a,l
    or e
    ld e,a
    ld a,h
    or d
    ld d,a
.queue:
    ld hl,(Radar_Cleanup)
    ld a,l
    or e
    ld l,a
    ld a,h
    or d
    ld h,a
    ld (Radar_Cleanup),hl
    ; A queued old snapshot must not survive a departure and reintroduce ink.
    ld hl,(Radar_Ready)
    ld a,e
    cpl
    and l
    ld l,a
    ld a,d
    cpl
    and h
    ld h,a
    ld (Radar_Ready),hl
    ld hl,(Radar_Urgent)
    ld a,e
    cpl
    and l
    ld l,a
    ld a,d
    cpl
    and h
    ld h,a
    ld (Radar_Urgent),hl
    jp Full_RadarRAMExit
.mark:
    ld a,d
    cp 255
    jp nz,Radar_Mark
    ld de,0
    ret

; Preserve the original per-cell snapshot/dirty contract in the mapper overlay.
Full_RadarCommitNative:
    ld a,(hud_cell)
    ld l,a
    ld h,0
    REPT 4
    add hl,hl
    ENDR
    ld de,Radar_StagedPoints
    add hl,de
    ex de,hl
    ld hl,Radar_Last
    ld bc,16
    ldir
    ld a,(hud_cell)
    ld l,a
    ld h,0
    ld de,Radar_WorkVisibility
    add hl,de
    ld a,(hl)
    ld de,Radar_StagedVisibility-Radar_WorkVisibility
    add hl,de
    ld (hl),a
    call Radar_CellBit
    ld hl,(Radar_Cleanup)
    ld a,l
    and e
    ld c,a
    ld a,h
    and d
    ld b,a
    ld hl,(Radar_Urgent)
    ld a,l
    or c
    ld l,a
    ld a,h
    or b
    ld h,a
    ld (Radar_Urgent),hl
    ld hl,(Radar_Cleanup)
    call .clear
    ld (Radar_Cleanup),hl
    ld hl,(Radar_Dirty)
    call .clear
    ld (Radar_Dirty),hl
    ld hl,(Radar_Ready)
    ld a,l
    or e
    ld l,a
    ld a,h
    or d
    ld h,a
    ld (Radar_Ready),hl
    di
    jp Full_RadarRAMExit
.clear:
    ld a,e
    cpl
    and l
    ld l,a
    ld a,d
    cpl
    and h
    ld h,a
    ret

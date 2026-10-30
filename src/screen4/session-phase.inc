; Eight16KiB sets: reuse an exact inactive match or an unused slot first.
; Rank remaining inactive sets by immutable HUD+boundary transfer cost.
; Current phase bank B800..BB40 contains four65-byte256-cycle cost tables.
; The visible set is always excluded, including exact phase matches.
    ASSERT pattern_phases >= GameSmoke_Rows+32
    ASSERT pattern_phases+8 <= $2860
    ASSERT (pattern_phases >> 8) == $28
GameSession_PhaseSelect:
    push ix
    push iy
    ld b,a
    or $c0
    ld l,a
    ld h,$28
    ld a,(hl)
    cp 8
    jr nc,.search
    ld c,a
    ld a,(pattern_front)
    cp c
    jr z,.search
    ld a,c
    add a,pattern_phases & $ff
    ld l,a
    ld a,(hl)
    cp b
    jr z,.selected
.search:
    ; Exact reuse avoids uploads. Every candidate still excludes the visible
    ; set: matching bytes do not transfer ownership of a displayed buffer.
    ld c,0
    ld hl,pattern_phases
.match:
    ld a,(pattern_front)
    cp c
    jr z,.match_next
    ld a,(hl)
    cp b
    jr z,.selected
.match_next:
    inc hl
    inc c
    ld a,c
    cp 8
    jr c,.match
    ld c,0
    ld hl,pattern_phases
.empty:
    ld a,(hl)
    cp $ff
    jr z,.selected
    inc hl
    inc c
    ld a,c
    cp 8
    jr c,.empty
    ld a,b
    add a,4
    ld ($7000),a
    ld a,(Full_Layout)
    add a,$b8
    ld iyh,a
    ld ix,pattern_phases
    ld d,$ff
    ld c,0
.candidate:
    ; Costs are precomputed for this theme/target phase, not measured here.
    ; Pick one inactive victim; do not sum these estimates as runtime timings.
    ld a,(pattern_front)
    cp c
    jr z,.next
    ld a,(ix+0)
    cp $ff
    jr nz,.known
    ld a,64
.known:
    ld l,a
    ld a,iyh
    ld h,a
    ld a,(hl)
    cp d
    jr nc,.next
    ld d,a
    ld iyl,c
    jr .next
.next:
    inc ix
    inc c
    ld a,c
    cp 8
    jr c,.candidate
    ld a,iyl
    ld c,a
.selected:
    ld a,c
    ld (pattern_back),a
    ld a,(phase)
    or $c0
    ld l,a
    ld h,$28
    ld (hl),c
    pop iy
    pop ix
    ret

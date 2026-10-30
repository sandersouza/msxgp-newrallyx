; Module contract: Native game object/smoke hooks; fixed native tables and scratch remain required.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
Full_MarkLogicalSmokeRows:
    push af
    push bc
    ld a,(Smoke_X)
    ld b,a
    ld a,(Smoke_Y)
    ld c,a
    call GameSmoke_MarkCloud
    pop bc
    pop af
    ret
Full_EnqueueSmoke:
    jp Smoke_Enqueue
Full_ObjectAtTile:
    push bc
    push de
    push hl
    ld a,b
    sub 3
    jr c,.none
    ld l,a
    ld h,$e3
    ld a,(hl)
    cp 32
    jr nc,.none
    ld e,a
    ld a,c
    sub 3
    jr c,.none
    ld l,a
    ld a,(hl)
    cp 56
    jr nc,.none
    ld l,a
    ld h,0
    REPT 5
    add hl,hl
    ENDR
    ld d,$98
    add hl,de
    call $ac03
    jr .done
.none:
    xor a
.done:
    pop hl
    pop de
    pop bc
    ret

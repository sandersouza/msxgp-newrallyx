; Physical input levels. Original code owns debounce, credits and smoke cost.
; Called on the host IRQ stack with main/alternate registers already saved.
Native_InputCache EQU $c7d0
Native_ReadInputs:
    in a,($aa)
    ld e,a
    and $f0
    out ($aa),a
    in a,($a9)
    ld c,$ff
    bit 5,a                    ; keyboard 5: coin
    jr nz,.start
    res 7,c
.start:
    bit 1,a                    ; keyboard 1: one player start
    jr nz,.arrows
    res 6,c
.arrows:
    ld a,e
    and $f0
    or 8
    out ($aa),a
    in a,($a9)
    bit 0,a
    jr nz,.left
    res 1,c
.left:
    bit 4,a
    jr nz,.up
    res 2,c
.up:
    bit 5,a
    jr nz,.down
    res 5,c
.down:
    bit 6,a
    jr nz,.right
    res 4,c
.right:
    bit 7,a
    jr nz,.keyboard_done
    res 3,c
.keyboard_done:
    ld a,e
    out ($aa),a                ; retain keyboard row and unrelated PPI outputs
    ld a,15
    out ($a0),a
    in a,($a2)
    ld e,a
    and $af                    ; port 1, pin 8 low; restore outputs after read
    or 3                       ; release trigger pins 6/7 before sampling inputs
    out ($a1),a
    ld a,14
    out ($a0),a
    in a,($a2)
    ld d,a
    ld a,15
    out ($a0),a
    ld a,e
    out ($a1),a
    bit 0,d
    jr nz,.joy_down
    res 5,c
.joy_down:
    bit 1,d
    jr nz,.joy_left
    res 4,c
.joy_left:
    bit 2,d
    jr nz,.joy_right
    res 2,c
.joy_right:
    bit 3,d
    jr nz,.joy_smoke
    res 3,c
.joy_smoke:
    bit 4,d
    jr nz,.publish
    res 1,c
.publish:
    ld a,c
    ld (Native_InputCache),a
    ld a,$ff
    ld (Native_InputCache+1),a
    ld a,$c3
    ld (Native_InputCache+2),a
Native_InputReturn:
    ret

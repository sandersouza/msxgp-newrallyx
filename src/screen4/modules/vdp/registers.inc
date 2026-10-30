; UI requests use the original bitmap mode only outside active gameplay.
; Foreground VDP register/command API. register: A=value,B=register, AF clobbered, IFF unchanged.
; stage_wait_command: no input, AF clobbered, returns EI with R15=0; may block.
; Caller supplies the existing reg macro; IRQ must not race the control latch.
register:
    out ($99),a
    ld a,b
    or $80
    out ($99),a
    ret
stage_wait_command:
    di
    reg 15,2
.busy:
    in a,($99)
    and 1
    jr nz,.busy
    reg 15,0
    ei
    ret

; Reuse contract: vdp-registers (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: register, stage_wait_command
; Inputs: register: A=value, B=register number; caller serializes the two-port control latch.
;   Wait: no input; only cold UI/transition use.
; Outputs: register writes one VDP register. Wait returns when command-engine busy clears,
;   with R15=0.
; Registers: AF/flags scratch; BC/DE/HL/IX/IY unchanged.
; Interrupts: register preserves IFF. Wait uses DI, polls status 2, restores selector 0 and
;   returns EI; it is not an IRQ-safe primitive or an IFF-preserving lock.
; Memory / hardware: Code only, ports 99; no new scratch. Wait may block and must not be
;   inserted into active gameplay.
; Reuse boundary: Independent mechanism with the existing host reg macro. Define an equivalent
;   immediate-register macro; preserve the established instruction expansion.
; Keep this summary synchronized with the registry and modules/README.md.

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

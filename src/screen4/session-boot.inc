; API: call GameSession_BootShow once, after cold initialization, with the
; shared startup-worker bank mapped at8000. Returns EI, PSG silent, R15=0,
; regular BLACK border selected. AF/BC/DE/HL/IY and ASCII16 bank at8000
; clobbered; the main RAM-mapper segment is retained.
; Uses C0F8..C0FC, D300 descriptor RAM, two VRAM pages; caller restores native
; scratch/seed/audio. Only the cold UI IRQ scans keys. Zero active-game calls.
; Omit through session-startup-options.inc; shared HUD/test workers are separate.
; Startup-only SCREEN5 delta replay. Code at2900; table atD300, no scratch
; bitmap. IM2 vectors D000..D100, trampoline D2D2 and stack F380 stay intact.
; Each displayed state is pixel-exact within the established MSX crop/palette.
; Publication deadlines retain native arcade speed; offline selection fits the
; transfer budget. IRQ scans all keyboard rows, independently of ROM mapping.
GameSession_BootStartTick EQU $c0f8
GameSession_BootBack EQU $c0fa
GameSession_BootShow:
    xor a
    ld (GameSession_BootSkip),a
    inc a
    ld (GameSession_BootKeyGate),a
    ld hl,(clock_ticks)
    ld (GameSession_BootStartTick),hl
    ld hl,$9000
    ld de,GameSession_BootFrames
    ld bc,GameSession_BootTableEnd-GameSession_BootFrames
    ldir
    di
    reg 7,0 ; Boot palette index0 is black; do not inherit game BLACK=11.
    reg 0,6
    reg 1,$22
    reg 2,$1f
    reg 8,$2a
    reg 23,0
    reg 25,0
    reg 26,0
    reg 27,0
    reg 16,0
    ld hl,GameSession_BootPalette
    ld bc,$209a
    otir
    ; Clear both 32KiB display pages with one cold HMMV. Interrupts remain
    ; enabled between status probes so any key can skip even this first fill.
    reg 17,36
    ld hl,.clear
    ld bc,$0b9b
    otir
    ei
.clear_wait:
    di
    ld a,(GameSession_BootSkip)
    or a
    jr z,.status
    reg 46,0
.status:
    reg 15,2
    in a,($99)
    push af
    reg 15,0
    pop af
    ei
    and 1
    jr nz,.clear_wait
    xor a
    ld (GameSession_BootBack),a
    ld iy,GameSession_BootFrames
.frame:
    ld a,(GameSession_BootSkip)
    or a
    jr nz,.done
    ld a,(iy+0)
    cp 255
    jr z,.finish
    ld ($7000),a
    ld l,(iy+1)
    ld h,(iy+2)
    call .stream
    ld a,(GameSession_BootSkip)
    or a
    jr nz,.done
    ld e,(iy+3)
    ld d,(iy+4)
    call .wait
    ld a,(GameSession_BootSkip)
    or a
    jr nz,.done
    ; Flip only a completed hidden page at its absolute native-time deadline.
    di
    ld a,(GameSession_BootBack)
    rrca
    rrca
    rrca
    rrca
    or $1f
    ld b,2
    call register
    reg 1,$62
.published:
    ld a,(GameSession_BootBack)
    xor 2
    ld (GameSession_BootBack),a
    ld de,5
    add iy,de
    ei
    jr .frame
.finish:
    ld de,GameSession_BootDeadline
    call .wait
.done:
    ; Restore the regular border index without a yellow flash while the caller
    ; clears native scratch/seed. BLACK is a different index in the boot palette.
    di
    reg 16,BLACK
    xor a
    out ($9a),a
    out ($9a),a
    reg 7,BLACK
    ; A skipped key is consumed until all rows are released on the title.
    ; Natural completion disables the boot-only keyboard gate immediately.
    ld a,(GameSession_BootSkip)
    or a
    jr nz,.consume
    ld (GameSession_BootKeyGate),a
.consume:
    xor a
    ld (Full_UIHeld),a
    ld (Full_UIEdges),a
    ei
    ret
.wait:
    ld a,(GameSession_BootSkip)
    or a
    ret nz
    ld hl,(clock_ticks)
    ld bc,(GameSession_BootStartTick)
    or a
    sbc hl,bc
    or a
    sbc hl,de
    ret nc
    halt
    jr .wait
.stream:
    ld a,(GameSession_BootSkip)
    or a
    ret nz
    ld a,(hl)
    inc hl
    or a
    ret z
    cp 3
    jr nz,.span
    ld a,(hl)
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld ($7000),a
    ex de,hl
    jp .stream
.span:
    ld c,a
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld b,(hl)
    inc hl
    push bc
    ; R14 includes the offset's bit14 as well as the selected 32KiB page.
    ld a,d
    rlca
    rlca
    and 3
    ld e,a
    ld a,(GameSession_BootBack)
    or e
    push hl
    dec hl
    dec hl
    dec hl
    ld e,(hl)
    pop hl
    di
    push bc
    ld b,14
    call register
    pop bc
    ld a,e
    out ($99),a
    ld a,d
    and $3f
    or $40
    out ($99),a
    ei
    dec c
    jr z,.literal
    ld a,c
    cp 3
    jr nz,.fill
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    push hl
    ex de,hl
    ld c,$98
    otir
    pop hl
    pop bc
    jp .stream
.literal:
    ld c,$98
    otir
    pop bc
    jp .stream
.fill:
    ld a,(hl)
    inc hl
.fill_byte:
    out ($98),a
    djnz .fill_byte
    pop bc
    jp .stream
.clear:
    db 0,0,0,0,0,1,$d4,1,0,0,$c0
    INCLUDE "session-boot-palette.inc"

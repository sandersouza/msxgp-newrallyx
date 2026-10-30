; Issue39 experimental CPU-only scopes. Main Page0 must be restored on entry.
; Enter/Leave preserve AF/BC/DE/HL and incoming IFF, and never touch Page2/mapper.
; BIOS bridge executes in the reserved Page3 RAM while Page0 is temporarily BIOS.
; IRQ remains in the selected CPU: active-session ISR only reads VDP status0.
GameTurbo_Kind EQU $d2f8       ; 0 unsupported,1 Panasonic Z80,2 turboR BIOS
GameTurbo_BootVersion EQU $d2f9
GameTurbo_BootPrimary EQU $d2fa
GameTurbo_Status EQU $d2fd
GameTurbo_BootSub EQU $d2fe
GameTurbo_Active EQU $d2fb

GameTurbo_Init:
    ; Copy the CHGCPU bridge into Page3 before any Page0 BIOS mapping occurs.
    ; Init runs once at cold boot; foreground wrappers never repeat detection.
    ld hl,GameTurbo_BIOSCode
    ld de,GameTurbo_BIOS
    ld bc,GameTurbo_BIOSEnd-GameTurbo_BIOS
    ldir
    xor a
    ld (GameTurbo_Kind),a
    ld (GameTurbo_Active),a
    ld a,(GameTurbo_BootVersion)
    cp 3
    jr z,.r800
    in a,($40)
    ; Switched I/O uses a complemented manufacturer ID. Save the old selector
    ; so unsupported machines do not inherit a different selected device.
    cpl
    ld b,a
    ld a,8
    out ($40),a
    in a,($40)
    cp $f7
    jr nz,.restore
    in a,($41)
    ; Preserve unrelated controller bits. Capability and actual clock are
    ; verified separately in the emulator contract; Ren-sha is not CPU turbo.
    bit 2,a
    jr nz,.restore
    or 1
    ld (GameTurbo_Status),a
    out ($41),a
    ld a,1
    ld (GameTurbo_Kind),a
    ret
.restore:
    ld a,b
    out ($40),a
    ret
.r800:
    ; Qualified stock ST/GT: main BIOS in primary0, subslot0 remains selected.
    ld a,(GameTurbo_BootPrimary)
    or a
    ret nz
    ld a,(GameTurbo_BootSub)
    or a
    ret nz
    ; MSXVER=3 supplies standard CHGCPU. No BIOS call through Page0 RAM.
    ld a,2
    ld (GameTurbo_Kind),a
    xor a
    jp GameTurbo_BIOS

GameTurbo_Enter:
    push af
    ld a,1
    jr GameTurbo_Set
GameTurbo_Leave:
    push af
    xor a
GameTurbo_Set:
    ; LD A,I exposes incoming IFF2 in P/V. Save that flag before DI and use
    ; JP PO on exit; unconditional EI would corrupt a caller's critical section.
    push bc
    ld c,a
    ld a,i
    push af
    di
    push de
    push hl
    ld a,c
    ld (GameTurbo_Active),a
    ld a,(GameTurbo_Kind)
    cp 2
    jr z,.r800
    ld a,(GameTurbo_Status)
    xor c
    out ($41),a
    jr .done
.r800:
    ; GameTurbo_BIOS temporarily exposes captured BIOS Page0 from Page3 code.
    ; That bridge also restores IM2: CHGCPU leaves the selected CPU in IM1.
    ld a,c                  ; BIOS mode0=Z80,1=R800 ROM; no DRAM shadow changes.
    call GameTurbo_BIOS
.done:
    ; Unwind HL/DE, the AF containing incoming IFF2, then BC. POP BC preserves
    ; P/V for JP PO; the final outer AF restores the caller's original flags.
    pop hl
    pop de
    pop af
    pop bc
    jp po,.disabled
    pop af
    ei
    ret
.disabled:
    pop af
    ret

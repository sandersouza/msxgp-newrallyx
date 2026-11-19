; Cold-only keyboard helpers, installed in main Page0 with the replay worker.
; BootAnyKey: Z=no skip key; NZ=skip. Ignore Shift alone and Shift+F5(F10)
; during replay, so the owner can hold F10 through the complete opening.
; Once invulnerability is committed, scan every key until release at the title.
; ReadF10: A=0/1; Commit: latch C0EE until reset and consume the held combo.
; AF/BC/DE/HL scratch; IX/IY and IFF preserved. Called by the existing cold IRQ
; with its register wrapper, or by BootShow.done under DI. No active-game scan.
; No new RAM/VRAM/buffer. The caller keeps main Page0 installed and owns PPI;
; read_keys restores row-selector port AA. Not reentrant and not an NMI helper.
GameSession_BootAnyKey:
    ld a,(GameSession_Invulnerable)
    or a
    jr nz,.all
    ld a,7
    call read_keys
    ld d,a
    ld a,6
    call read_keys
    ld h,a
    and $fe
    ld l,a
    ld a,d
    and $fd
    or l
    ret nz
    bit 0,h
    jr nz,.other_rows
    ld a,d
    and 2
    ret nz
.other_rows:
    ld e,10
.row:
    ld a,e
    call read_keys
    or a
    ret nz
    dec e
    ld a,e
    cp 7
    jr nz,.next
    ld e,5
.next:
    ld a,e
    or a
    jp p,.row
    xor a
    ret
.all:
    ld e,10
.held_row:
    ld a,e
    call read_keys
    or a
    ret nz
    dec e
    jp p,.held_row
    xor a
    ret

GameSession_BootReadF10:
    ld a,7
    call read_keys
    and 2
    ret z
    ld a,6
    call read_keys
    and 1
    ret

GameSession_BootCommitF10:
    call GameSession_BootReadF10
    ld (GameSession_Invulnerable),a
    or a
    ret z
    ld a,2
    ld (GameSession_BootKeyGate),a
    or a
    ret

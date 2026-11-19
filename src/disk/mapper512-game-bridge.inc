; Native RAM-game boot and cold callbacks. Page1 physical30, Page0 main1 and
; Page3 game0. GameCommand entry requiresDI; caller owns display/audio stop.
; No active renderer/native/audio path calls this module. Cold disk calls
; temporarily use BIOS IM1/I with R1=22, then restore game IM2/I and R1=02.
; All callback registers are preserved; returnDI via Page3 gate to resident6.
; Owns world2/3 and flag4/5 until world finalization/cache reconstruction.
; Bootstrap raw pages20..29 may be fully replaced only before active play;
; OS/shadow allocations exclude them. No cartridge/host payload provider.
Mapper512_GameBoot:
    ld sp,$f380
    ld a,1
    out ($fc),a
    ld hl,Game_BootResources
.load:
    ld a,(hl)
    cp 255
    jr z,.loaded
    inc hl
    push hl
    ld c,a
    call Cold_Read
    jp c,Mapper512_GameFailed
    pop hl
    jr .load
.loaded:
    call Cold_EndBatch
    jp c,Mapper512_GameFailed
    ; Recover a real BIOS Page3 image before invoking the unchanged BIOS-side
    ; game initializer. A Page1 stack survives copying the new Page3/stack.
    di
    ld sp,$7d00
    ld a,5
    out ($fe),a
    xor a
    out ($fc),a
    ld hl,$8000
    ld de,0
    ld bc,$4000
    ldir
    ld a,1
    out ($fc),a
    xor a
    out ($ff),a
    ld sp,$f380
    ld a,(Cold_OsI)
    ld i,a
    im 1
    ld a,(Cold_RamSecondary)
    and $fc
    ld ($ffff),a
    in a,($a8)
    and $fc
    out ($a8),a
    ld hl,.enter
    ld de,$d1e0
    ld bc,8
    ldir
    jp $d1e0
.enter:
    ld a,6
    out ($fd),a
    jp $4010
    db 0

Mapper512_GameCommand:
    push af
    push bc
    push de
    push hl
    push ix
    push iy
    ex af,af'
    push af
    ex af,af'
    exx
    push bc
    push de
    push hl
    exx
    cp 3
    jr z,.boot_done
    cp 0
    jr z,.seed
    cp 1
    jr z,.assets
    cp 2
    jp nz,Mapper512_GameFailed
.world:
    call Mapper512_GameIoOn
    ld c,GAME_UI_RESOURCE
    call Cold_Read
    jp c,Mapper512_GameFailed
    ld a,(GAME_LAYOUT)
    add a,a
    ld e,a
    ld d,0
    ld hl,Game_MapResources
    add hl,de
    ld c,(hl)
    inc hl
    push hl
    call Cold_Read
    jp c,Mapper512_GameFailed
    pop hl
    ld c,(hl)
    call Cold_Read
    jp c,Mapper512_GameFailed
    call Cold_EndBatch
    jp c,Mapper512_GameFailed
    jr .io_done
.boot_done:
    ld a,255
    ld (Game_CurrentFamily),a
    jr .return
.seed:
    call Mapper512_GameIoOn
    ld c,GAME_SEED_RESOURCE
    call Cold_Read
    jp c,Mapper512_GameFailed
    call Cold_EndBatch
    jp c,Mapper512_GameFailed
    jr .io_done
.assets:
    call Mapper512_GameIoOn
    ld a,(GAME_LAYOUT)
    ld b,a
    ld a,(Game_CurrentFamily)
    cp b
    jr z,.navigation
    ld l,b
    ld h,0
    ld de,Game_FamilyStarts
    add hl,de
    ld c,(hl)
    ld b,21
.family:
    push bc
    call Cold_Read
    jp c,Mapper512_GameFailed
    pop bc
    inc c
    djnz .family
    ld a,(GAME_LAYOUT)
    ld (Game_CurrentFamily),a
.navigation:
    ld c,GAME_NAV_RESOURCE
    call Cold_Read
    jp c,Mapper512_GameFailed
    ld a,(GAME_LAYOUT)
    add a,a
    add a,a
    add a,a
    add a,$80
    ld h,a
    ld l,0
    ld de,$3000
    ld bc,2048
    ldir
    ld a,(GAME_LAYOUT)
    ld l,a
    ld h,0
    ld de,Game_TerrainResources
    add hl,de
    ld c,(hl)
    call Cold_Read
    jp c,Mapper512_GameFailed
    call Cold_EndBatch
    jp c,Mapper512_GameFailed
.io_done:
    call Mapper512_RestorePsg
    ld a,$02
    out ($99),a
    ld a,$81
    out ($99),a
.return:
    exx
    pop hl
    pop de
    pop bc
    exx
    ex af,af'
    pop af
    ex af,af'
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    jp $d1e9

Mapper512_GameIoOn:
    di
    ld hl,Game_Psg
    ld b,0
.psg:
    ld a,b
    out ($a0),a
    in a,($a2)
    ld (hl),a
    inc hl
    inc b
    ld a,b
    cp 14
    jr c,.psg
    xor a
    out ($99),a
    ld a,$8f
    out ($99),a
    ld a,$22
    out ($99),a
    ld a,$81
    out ($99),a
    ret
Mapper512_RestorePsg:
    ld hl,Game_Psg
    ld b,0
.psg:
    ld a,b
    out ($a0),a
    in a,($a2)
    cp (hl)
    jr z,.next
    ld a,(hl)
    out ($a1),a
.next:
    inc hl
    inc b
    ld a,b
    cp 14
    jr c,.psg
    ret
Mapper512_GameFailed:
    di
    halt
    jr Mapper512_GameFailed
Game_CurrentFamily: db 255
Game_Psg: ds 14,0
    INCLUDE "game-bindings.inc"

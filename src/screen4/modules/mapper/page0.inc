; Reuse contract: page0-mapper (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameSession_MapPage, GameSession_RestorePage0, GameSession_CopyMap,
;   GameSession_PatchObject
; Inputs: MapPage: A=0/1 RAM map index. CopyMap: A=ASCII16 ROM bank, C=destination RAM
;   segment. PatchObject: B=world X, C=world Y, IY=nine row-major IDs; valid 3x3 region in a
;   128x256 map.
; Outputs: MapPage selects the indexed Page0 segment. RestorePage0 selects main segment.
;   CopyMap copies 16 KiB and restores main Page0, leaving its source Page2 bank. PatchObject
;   writes nine IDs, advances IY by nine and C by three, and restores Page0.
; Registers: MapPage: AF scratch, HL preserved. Restore: AF scratch. CopyMap: AF/BC/DE/HL
;   scratch. PatchObject: AF/BC/DE/HL/IY scratch, IX preserved.
; Interrupts: IFF unchanged; helpers execute from resident code. IRQ cannot assume another
;   Page0 segment or change mappings.
; Memory / hardware: Host-provided GameSession_MainSegment byte and GameSession_MapSegments
;   pair; no allocation. Uses mapper port FC and ASCII16 register 7000.
; Reuse boundary: Mechanism with fixed 128x256 map geometry. Another host can define the two
;   state aliases at assembly time; never execute these helpers from the Page0 segment being
;   replaced.
; Keep this summary synchronized with the registry and modules/README.md.

; Page0 map data may be selected only inside these resident helpers. The
; foreground returns to its original RAM segment before any Page0 code/data use.
; Module contract: Resident Page0/ASCII16 access helpers; foreground only; restore main RAM segment.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
GameSession_MapPage:
    push hl
    ld hl,GameSession_MapSegments
    or a
    jr z,.selected
    inc hl
.selected:
    ld a,(hl)
    out ($fc),a
    pop hl
    ret
GameSession_RestorePage0:
    ld a,(GameSession_MainSegment)
    out ($fc),a
    ret
GameSession_CopyMap:
    ; Source is a cartridge bank in Page2; destination is mapper RAM in Page0.
    ; Keep the copy and its return path resident while the destination is mapped.
    ld ($7000),a
    ld a,c
    out ($fc),a
    ld hl,$8000
    ld de,0
    ld bc,$4000
    ldir
    jp GameSession_RestorePage0

; B/C=world top-left, IY=nine theme-local tile IDs in mapped ROM.
GameSession_PatchObject:
    push ix
    ld ix,$0303
.row:
    ; The world is split into two128-row halves. Y bit7 selects the RAM half;
    ; the remaining seven bits select a row inside that16KiB segment.
    push bc
    ld a,c
    and $80
    rlca
    call GameSession_MapPage
    ld a,c
    and 127
    ld l,a
    ld h,0
    REPT 7
    add hl,hl
    ENDR
    ld e,b
    ld d,0
    add hl,de
    ld ixl,3
.cell:
    ld a,(iy+0)
    ld (hl),a
    inc hl
    inc iy
    dec ixl
    jr nz,.cell
    pop bc
    inc c
    dec ixh
    jr nz,.row
    pop ix
    jp GameSession_RestorePage0

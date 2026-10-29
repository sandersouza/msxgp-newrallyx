; Integration contract:
; Init must run with DI while display/sprites are not yet visible. It configures
; R5=$37/R11=0/R6=5 and uploads native templates+initial world color suffix.
; Caller owns R1 bit1=1 (16x16, unmagnified), R18=0, R23=cy low and palette.
; Prepare must be followed by Commit before another Prepare; neither may be
; reentered. IRQ handlers may read status, but must not upload VRAM during a
; foreground data stream unless they restore its exact data pointer afterward.
; Source768B templates are copied from player.py's normal two-plane frames.
; Palette RGBs must be permuted with scenery to preserve OR3|9=11black and
; OR6|10=14black. The helper reports/validates this contract; no RGB reduction.
; RAM: actors c800..c82f caller-owned; caches c840..c8c1; scratch c980..cd6a.
; VRAM: patterns2800..2c7f (two18-group sets); parentHUD groups36..49,
; patternIDs144..199 at2c80..2e3f; worldcolors18e0..19ff; worldSAT1a38..1a7f.
; Hidden world slots use a scroll-compensated offscreen Y (never216), so stale
; invisible pattern/color data can remain untouched. Parent HUD slots0..13
; must never contain Y216 while any world actor follows. No SAT terminator is
; needed: all32 physical slots are bounded and slots30/31 are hidden when idle.
; Sentinel216 preserves every visible source pixel: shift main down1 row and
; place its original bottom row in two spare tail slots. Only one sentinel
; actor fits; any later sentinel actor is wholly culled, exposed in GS_Culled.
; Hardware8-sprites/scanline stays enabled; no source-pixel thinning or scaling.
; Real Z80 synthetic ledger (3,579,545Hz FS-A1WSX_NR128; 1163cases) currently:
; eight warm interior cars14,658 mean/14,782max inclusive Prepare+Commit;
; eight animation changes32,882mean/33,150max; scroll-only14,657mean;
; eight simultaneously right-clipped changing animations137,350max. This last
; pathological workload exceeds30-FPS budget; actual gameplay must be measured.
; Stable Commit=2,122cycles (72 SAT bytes,0 changedcolors). Dirty Prepare uploads
; only active changed pattern spans:0B stable,512B for8 changed main car frames,
; plus64B for a sentinel tail. Full-render/frame/synchronization costs excluded.
; Run test_game_sprites.py --emulator --bios PATH for byte contracts and JSON
; ledger, including ROM/source SHA256, mean/p99/max and preparation/commit split.
; Fixed HUD world cars. Caller owns interrupt state and sets R18=0/R23=cy.
; APIs clobber AF,BC,DE,HL,IX,IY. Init/Prepare leave interrupts as entered.
; Prepare uploads ONLY inactive patterns. Commit must run with DI at blanking.
; Leading HUD slots0..13 and pattern IDs144..199 remain owned by caller.
GameSprites_Actors EQU $c800
GameSprites_SAT EQU $c980
GameSprites_Colors EQU $c9c8
GameSprites_Patterns EQU $cb00
GS_Set EQU $cd40
GS_Next EQU $cd41
GS_Actor EQU $cd42
GS_Index EQU $cd44
GS_X EQU $cd45
GS_Y EQU $cd47
GS_Animation EQU $cd49
GS_Kind EQU $cd4a
GS_EC EQU $cd4b
GS_Mask EQU $cd4c
GS_Top EQU $cd4e
GS_Bottom EQU $cd4f
GS_Sentinel EQU $cd50
GS_TailUsed EQU $cd51
GS_Culled EQU $cd52             ; bit per actor, sentinel slot exhaustion only
GS_Row EQU $cd53
GS_Plane EQU $cd54
GS_PatternID EQU $cd55
GS_SatY EQU $cd56
GS_SatX EQU $cd57
GS_Ink EQU $cd58
GS_Tail EQU $cd59
GS_TailID EQU $cd5b
GS_SavedSP EQU $cd5c
GS_Key EQU $cd60
GS_PatternDirty EQU $cd66
GS_ColorDirty EQU $cd67
GS_ColorBits EQU $cd68
GS_TailColorDirty EQU $cd69
GS_Cache EQU $c840
GS_ColorCache EQU $c8a0
GS_TailColorCache EQU $c8b0
GS_FastCache EQU $c8b2
GS_Hidden EQU $cd6a

GameSprites_Init:
    xor a
    ld (GS_Set),a
    ld hl,GS_Cache
    ld de,GS_Cache+1
    ld bc,$c1-$40
    ld (hl),$ff
    ldir
    ; mode2 SAT=$1a00, colors=$1800, patterns=$2800, 16x16 unmagnified.
    ld a,$37
    out ($99),a
    ld a,$85
    out ($99),a
    xor a
    out ($99),a
    ld a,$8b
    out ($99),a
    ld a,5
    out ($99),a
    ld a,$86
    out ($99),a
    ld hl,$2800
    call GS_Address
    ld hl,GameSprites_Templates
    ld de,768
    call GS_Upload
    ld hl,$18e0
    call GS_Address
    ld hl,GameSprites_InitialColors
    ld de,288
    jp GS_Upload

GameSprites_Prepare:
    ld a,(GS_Set)
    xor 1
    ld (GS_Next),a
    xor a
    ld (GS_TailUsed),a
    ld (GS_Culled),a
    ld (GS_ColorBits),a
    ld (GS_TailColorDirty),a
    ld a,(cy)
    add a,211
    cp 216
    jr nz,.hidden
    inc a
.hidden:
    ld (GS_Hidden),a
    ld (GameSprites_SAT+64),a
    ld (GameSprites_SAT+68),a
    ld hl,GameSprites_Actors
    ld (GS_Actor),hl
    xor a
    ld (GS_Index),a
.actor:
    call GS_PrepareActor
    ld hl,(GS_Actor)
    ld de,6
    add hl,de
    ld (GS_Actor),hl
    ld a,(GS_Index)
    inc a
    ld (GS_Index),a
    cp 8
    jr nz,.actor
    ret

GS_PrepareActor:
    ld hl,(GS_Actor)
    ; All records live in c800..c82f. Reject inactive kinds before loading
    ; four coordinate bytes; subtracting five cannot cross a page here.
    ld de,5
    add hl,de
    ld a,(hl)
    cp 2
    jp nc,GS_HideActor
    ld (GS_Kind),a
    ld a,l
    sub 5
    ld l,a
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld (GS_X),de
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld (GS_Y),de
    ld a,(hl)
    inc hl
    cp 12
    jp nc,GS_HideActor
    ld (GS_Animation),a
    ; Signed ranges x=-7..199 and y=-15..211, before low-byte math.
    ld hl,(GS_X)
    ld de,7
    add hl,de
    ld de,207
    or a
    sbc hl,de
    jp nc,GS_HideActor
    ld hl,(GS_Y)
    ld de,15
    add hl,de
    ld de,227
    or a
    sbc hl,de
    jp nc,GS_HideActor
    call GS_TryFast
    ret c
    xor a
    ld (GS_EC),a
    ld hl,$ffff
    ld de,(GS_X)
    bit 7,d
    jr z,.positive_x
    ld a,$80
    ld (GS_EC),a
.positive_x:
    ld a,e
    ld (GS_SatX),a
    ld a,(GS_EC)
    or a
    jr z,.clip_left
    ld a,e
    add a,32
    ld (GS_SatX),a
.clip_left:
    ld a,e
    cp 8
    jr c,.left
    bit 7,d
    jr z,.clip_right
.left:
    ld a,8
    sub e
    ld b,a
.left_bit:
    srl h
    rr l
    djnz .left_bit
.clip_right:
    ld a,e
    cp 185
    jr c,.mask_ready
    bit 7,d
    jr nz,.mask_ready
    sub 184
    ld b,a
    ; clear low bits without shifting the already-clipped high bits.
    ld de,$ffff
.right_bit:
    sla e
    rl d
    djnz .right_bit
    ld a,h
    and d
    ld h,a
    ld a,l
    and e
    ld l,a
.mask_ready:
    ld (GS_Mask),hl
    xor a
    ld (GS_Top),a
    ld a,16
    ld (GS_Bottom),a
    ld hl,(GS_Y)
    bit 7,h
    jr z,.positive_y
    ld a,l
    neg
    ld (GS_Top),a
    jr .y_ready
.positive_y:
    ld a,l
    cp 197
    jr c,.y_ready
    ld a,212
    sub l
    ld (GS_Bottom),a
.y_ready:
    ld a,(cy)
    add a,l
    dec a
    ld (GS_SatY),a
    cp 216
    ld a,0
    jr nz,.sentinel_ready
    ld a,(GS_TailUsed)
    or a
    jr z,.new_tail
    ld a,(GS_Index)
    ld b,a
    ld a,1
    inc b
.cull_bit:
    dec b
    jr z,.cull_mark
    add a,a
    jr .cull_bit
.cull_mark:
    ld hl,GS_Culled
    or (hl)
    ld (hl),a
    jp GS_HideActor
.new_tail:
    inc a
    ld (GS_TailUsed),a
    ld a,215
    ld (GS_SatY),a
    ld a,1
.sentinel_ready:
    ld (GS_Sentinel),a
    call GS_CheckColor
    call GS_CheckPattern
    ld (GS_PatternDirty),a
    ld a,(GS_Animation)
    ld l,a
    ld h,0
    DUP 6
    add hl,hl
    EDUP
    ld de,GameSprites_Templates
    add hl,de
    push hl
    pop ix
    ld a,(GS_Index)
    ld l,a
    ld h,0
    DUP 6
    add hl,hl
    EDUP
    ld de,GameSprites_Patterns
    add hl,de
    ld a,(GS_Sentinel)
    ld e,a
    ld d,0
    add hl,de
    push hl
    pop iy
    ld a,(GS_Index)
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,(GS_Next)
    or a
    ld a,b
    jr z,.pattern_ready
    add a,72
.pattern_ready:
    ld (GS_PatternID),a
    ld a,(GS_PatternDirty)
    or a
    jr nz,.copy_needed
    jp GS_InteriorAttributes
.copy_needed:
    ; Interior cars retain all64 native bytes via a bounded block copy.
    ; Only actual viewport edges and sentinel216 need per-row masking.
    ld a,(GS_Sentinel)
    or a
    jr nz,.slow
    ld a,(GS_Top)
    or a
    jr nz,.slow
    ld a,(GS_Bottom)
    cp 16
    jr nz,.slow
    ld hl,(GS_Mask)
    ld a,h
    and l
    cp $ff
    jp nz,GS_MaskedCopyFast
    push ix
    pop hl
    push iy
    pop de
    ld bc,64
    ldir
    call GS_InteriorAttributes
    jp GS_UploadActor
.slow:
    ld a,(GS_Sentinel)
    or a
    jr z,.slow_ready
    ld (iy-1),0
    ld (iy+15),0
    ld (iy+31),0
    ld (iy+47),0
    ld hl,GameSprites_Patterns+512
    ld de,GameSprites_Patterns+513
    ld bc,63
    ld (hl),0
    ldir
.slow_ready:
    xor a
    ld (GS_Plane),a
    ld hl,GameSprites_Patterns+512
    ld (GS_Tail),hl
.plane:
    xor a
    ld (GS_Row),a
.row:
    ld a,(GS_Row)
    ld b,a
    ld a,(GS_Top)
    cp b
    jr z,.bottom
    jr nc,.empty
.bottom:
    ld a,(GS_Bottom)
    cp b
    jr z,.empty
    jr c,.empty
    ld a,(GS_Mask+1)
    and (ix+0)
    ld d,a
    ld a,(GS_Mask)
    and (ix+16)
    ld e,a
    jr .pixels
.empty:
    ld de,0
.pixels:
    ld a,(GS_Sentinel)
    or a
    jr z,.main_row
    ld a,(GS_Row)
    cp 15
    jr nz,.main_row
    ld hl,(GS_Tail)
    ld (hl),d
    ld bc,16
    add hl,bc
    ld (hl),e
    jr .next_row
.main_row:
    ld (iy+0),d
    ld (iy+16),e
.next_row:
    inc ix
    inc iy
    ld a,(GS_Row)
    inc a
    ld (GS_Row),a
    cp 16
    jr nz,.row
    ld de,16
    add ix,de
    add iy,de
    call GS_Attributes
    ld hl,(GS_Tail)
    ld de,32
    add hl,de
    ld (GS_Tail),hl
    ld a,(GS_PatternID)
    add a,4
    ld (GS_PatternID),a
    ld a,(GS_Plane)
    inc a
    ld (GS_Plane),a
    cp 2
    jp nz,.plane
    jp GS_UploadActor

GS_HideActor:
    ld a,(GS_Index)
    add a,a
    add a,a
    add a,a
    add a,GameSprites_SAT & $ff
    ld l,a
    ld h,GameSprites_SAT >> 8
    ld a,(GS_Hidden)
    ld (hl),a
    DUP 4
    inc l
    EDUP
    ld (hl),a
    ret

GS_FastCacheAddress:
    ld a,(GS_Index)
    ld l,a
    ld h,0
    ld de,GS_FastCache
    add hl,de
    ld a,(GS_Next)
    or a
    ret z
    ld de,8
    add hl,de
    ret

GS_TryFast:
    ; Caller already bounded signed X=-7..199 and Y=-15..211. Their
    ; negative low bytes fail these interior bounds without high-byte tests.
    ld a,(GS_X)
    cp 8
    jp c,.fallback
    cp 185
    jp nc,.fallback
    ld (GS_SatX),a
    ld a,(GS_Y)
    cp 197
    jp nc,.fallback
    ld b,a
    ld a,(cy)
    add a,b
    dec a
    cp 216
    jp z,.fallback
    ld (GS_SatY),a
    xor a
    ld (GS_EC),a
    ld (GS_Sentinel),a
    call GS_CheckColor
    ld a,(GS_Index)
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,(GS_Next)
    or a
    ld a,b
    jr z,.pattern_id
    add a,72
.pattern_id:
    ld (GS_PatternID),a
    call GS_FastCacheAddress
    ld a,(GS_Animation)
    cp (hl)
    jr nz,.changed
    call GS_InteriorAttributes
    scf
    ret
.changed:
    ld (hl),a
    ; Invalidate the full clipping key after replacing its actual pattern.
    ld a,(GS_Index)
    ld l,a
    ld h,0
    add hl,hl
    ld e,l
    ld d,h
    add hl,hl
    add hl,de
    ld de,GS_Cache
    add hl,de
    ld a,(GS_Next)
    or a
    jr z,.invalidate
    ld de,48
    add hl,de
.invalidate:
    ld (hl),$ff
    ld a,(GS_Animation)
    ld l,a
    ld h,0
    DUP 6
    add hl,hl
    EDUP
    ld de,GameSprites_Templates
    add hl,de
    push hl
    call GS_InteriorAttributes
    pop hl
    call GS_UploadDirect
    scf
    ret
.fallback:
    call GS_FastCacheAddress
    ld (hl),$ff
    or a
    ret

GS_InteriorAttributes:
    ld a,(GS_Index)
    add a,a
    add a,a
    add a,a
    ld l,a
    ld h,0
    ld de,GameSprites_SAT
    add hl,de
    ld a,(GS_SatY)
    ld (hl),a
    inc hl
    ld a,(GS_SatX)
    ld (hl),a
    inc hl
    ld a,(GS_PatternID)
    ld (hl),a
    inc hl
    ld (hl),0
    inc hl
    ld a,(GS_SatY)
    ld (hl),a
    inc hl
    ld a,(GS_SatX)
    ld (hl),a
    inc hl
    ld a,(GS_PatternID)
    add a,4
    ld (hl),a
    inc hl
    ld (hl),0
    ld a,(GS_ColorDirty)
    or a
    ret z
    ld a,(GS_Index)
    ld l,a
    ld h,0
    DUP 5
    add hl,hl
    EDUP
    ld de,GameSprites_Colors
    add hl,de
    ld a,(GS_Kind)
    or a
    ld a,3
    jr z,.body
    ld a,6
.body:
    ld b,a
    ld a,(GS_EC)
    or b
    ld b,16
.body_fill:
    ld (hl),a
    inc hl
    djnz .body_fill
    ld a,(GS_Kind)
    add a,$49
    ld b,a
    ld a,(GS_EC)
    or b
    ld b,16
.window_fill:
    ld (hl),a
    inc hl
    djnz .window_fill
    ret

GS_Attributes:
    ld a,(GS_Index)
    add a,a
    ld b,a
    ld a,(GS_Plane)
    add a,b
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld de,GameSprites_SAT
    add hl,de
    ld a,(GS_SatY)
    ld (hl),a
    inc hl
    ld a,(GS_SatX)
    ld (hl),a
    inc hl
    ld a,(GS_PatternID)
    ld (hl),a
    inc hl
    ld (hl),0
    ld a,(GS_ColorDirty)
    or a
    jr z,.tail_check
    ; Color index for this actor's two stable slots.
    ld a,(GS_Index)
    ld l,a
    ld h,0
    DUP 5
    add hl,hl
    EDUP
    ld a,(GS_Plane)
    or a
    jr z,.color_plane
    ld de,16
    add hl,de
.color_plane:
    ld de,GameSprites_Colors
    add hl,de
    ld a,(GS_Kind)
    or a
    ld a,3
    jr z,.player
    ld a,6
.player:
    ld b,a
    ld a,(GS_Plane)
    or a
    ld a,b
    jr z,.ink
    ld a,(GS_Kind)
    add a,$49
.ink:
    ld b,a
    ld a,(GS_EC)
    or b
    ld (GS_Ink),a
    ld b,16
.fill_color:
    ld (hl),a
    inc hl
    djnz .fill_color
.tail_check:
    ld a,(GS_Sentinel)
    or a
    ret z
    ld a,(GS_Plane)
    add a,16
    add a,a
    add a,a
    ld b,a
    ld a,(GS_Next)
    or a
    ld a,b
    jr z,.tail_id
    add a,72
.tail_id:
    ld (GS_TailID),a
    ld a,(GS_Plane)
    add a,a
    add a,a
    ld l,a
    ld h,0
    ld de,GameSprites_SAT+64
    add hl,de
    ld a,(GS_SatY)
    add a,16
    ld (hl),a
    inc hl
    ld a,(GS_SatX)
    ld (hl),a
    inc hl
    ld a,(GS_TailID)
    ld (hl),a
    inc hl
    ld (hl),0
    ld a,(GS_TailColorDirty)
    or a
    ret z
    ld hl,GameSprites_Colors+256
    ld a,(GS_Plane)
    or a
    jr z,.tail_color
    ld de,16
    add hl,de
.tail_color:
    ld a,(GS_Ink)
    ld b,16
.tail_fill:
    ld (hl),a
    inc hl
    djnz .tail_fill
    ret

GS_CheckPattern:
    ld a,(GS_Animation)
    ld (GS_Key),a
    ld hl,(GS_Mask)
    ld (GS_Key+1),hl
    ld a,(GS_Top)
    ld (GS_Key+3),a
    ld a,(GS_Bottom)
    ld (GS_Key+4),a
    ld a,(GS_Sentinel)
    ld (GS_Key+5),a
    ld a,(GS_Index)
    ld l,a
    ld h,0
    add hl,hl
    ld e,l
    ld d,h
    add hl,hl
    add hl,de
    ld de,GS_Cache
    add hl,de
    ld a,(GS_Next)
    or a
    jr z,.address
    ld de,48
    add hl,de
.address:
    push hl
    ld de,GS_Key
    ld b,6
.compare:
    ld a,(de)
    cp (hl)
    jr nz,.dirty
    inc de
    inc hl
    djnz .compare
    pop hl
    ld a,(GS_Sentinel) ; shared tail slots are deliberately never cached.
    ret
.dirty:
    pop de
    ld hl,GS_Key
    ld bc,6
    ldir
    ld a,1
    ret

GS_CheckColor:
    ld a,(GS_Index)
    add a,a
    ld l,a
    ld h,0
    ld de,GS_ColorCache
    add hl,de
    ld a,(GS_Kind)
    cp (hl)
    jr nz,.dirty
    inc hl
    ld a,(GS_EC)
    cp (hl)
    jr nz,.ec_dirty
    xor a
    ld (GS_ColorDirty),a
    ld a,(GS_Sentinel)
    or a
    ret z
    ; Sentinel rows use the same inks; updating the actor as well is bounded.
    dec hl
.dirty:
    ld a,(GS_Kind)
    ld (hl),a
    inc hl
.ec_dirty:
    ld a,(GS_EC)
    ld (hl),a
    ld a,1
    ld (GS_ColorDirty),a
    ld a,(GS_Index)
    ld b,a
    ld a,1
    inc b
.bit:
    dec b
    jr z,.mark
    add a,a
    jr .bit
.mark:
    ld hl,GS_ColorBits
    or (hl)
    ld (hl),a
    ld a,(GS_Sentinel)
    or a
    ret z
    ld a,1
    ld (GS_TailColorDirty),a
    ret

GS_UploadDirect:
    ; Interior source masks already have the exact native byte layout.
    push hl
    ld a,(GS_Index)
    ld l,a
    ld h,0
    DUP 6
    add hl,hl
    EDUP
    ld de,$2800
    add hl,de
    ld a,(GS_Next)
    or a
    jr z,.target
    ld de,576
    add hl,de
.target:
    call GS_Address
    pop hl
    ld de,64
    jp GS_Upload

GS_UploadActor:
    ld a,(GS_Index)
    ld l,a
    ld h,0
    DUP 6
    add hl,hl
    EDUP
    push hl
    ld de,$2800
    add hl,de
    ld a,(GS_Next)
    or a
    jr z,.target
    ld de,576
    add hl,de
.target:
    call GS_Address
    pop hl
    ld de,GameSprites_Patterns
    add hl,de
    ld de,64
    call GS_Upload
    ld a,(GS_Sentinel)
    or a
    ret z
    ld hl,$2800+512
    ld a,(GS_Next)
    or a
    jr z,.tail_target
    ld de,576
    add hl,de
.tail_target:
    call GS_Address
    ld hl,GameSprites_Patterns+512
    ld de,64
    jp GS_Upload

GameSprites_Commit:
    ; Commit only changed color spans. SAT describes all current visibility.
    xor a
    ld (GS_Index),a
    ld a,(GS_ColorBits)
    or a
    jr z,.after_colors
.colors:
    ld a,(GS_ColorBits)
    rrca
    ld (GS_ColorBits),a
    jr nc,.next
    ld a,(GS_Index)
    ld l,a
    ld h,0
    DUP 5
    add hl,hl
    EDUP
    push hl
    ld de,$18e0
    add hl,de
    call GS_Address
    pop hl
    ld de,GameSprites_Colors
    add hl,de
    ld de,32
    call GS_Upload
.next:
    ld a,(GS_Index)
    inc a
    ld (GS_Index),a
    cp 8
    jr nz,.colors
.after_colors:
    ld a,(GS_TailColorDirty)
    or a
    jr z,.sat
    ld hl,$19e0
    call GS_Address
    ld hl,GameSprites_Colors+256
    ld de,32
    call GS_Upload
.sat:
    ld hl,$1a38
    call GS_Address
    ld hl,GameSprites_SAT
    ld de,72
    call GS_Upload
    ld a,(GS_Next)
    ld (GS_Set),a
    ret

GS_Address:
    ; Serialize control pairs; preserve caller interrupt enable state.
    ld a,i
    push af
    di
    xor a
    out ($99),a
    ld a,$8e
    out ($99),a
    ld a,l
    out ($99),a
    ld a,h
    or $40
    out ($99),a
    pop af
    ret po
    ei
    ret
GS_Upload:
    ld c,$98
    ld a,d
    or a
    jr z,.tail
.page:
    ld b,0
    otir
    dec d
    jr nz,.page
.tail:
    ld a,e
    or a
    ret z
    ld b,e
    otir
    ret
GameSprites_InitialColors:
    defs 16,3
    defs 16,$49
    DUP 7
    defs 16,6
    defs 16,$4a
    EDUP
    defs 32,0
GameSprites_Templates:
    INCBIN "game-sprite-templates.bin"

 INCLUDE "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/experiments/fixed-hud/game-sprite-mask-fast.inc"

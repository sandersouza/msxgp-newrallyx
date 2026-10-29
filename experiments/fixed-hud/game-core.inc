; First-stage gameplay with resident host logic and native ROM worker.
; Include generated game-host.inc after this file. No VDP writes occur here.
; Game_Frame A=elapsed native 60Hz ticks; returns GAME_NATIVE_BANK mapped.
; Game_InitCore expects Page0 RAM/navigation and relocated E000 seed installed.
; Caller preserves live registers; IRQ must preserve registers and mapping.
Game_State EQU $c040           ; 0 active, 1 game over, 2 first stage completed
Game_Due EQU $c041
Game_FlagSeen EQU $c042
Game_SmokeSeen EQU $c043
Game_DeathSeen EQU $c045
Game_RoundSeen EQU $c046
Game_ActorCount EQU $c047
Game_ActorSource EQU $c048
Game_ActorKind EQU $c04a
Game_ActorRemaining EQU $c04b
Game_ActorX EQU $c04c
Game_ActorY EQU $c04e
Game_SmokeChanged EQU $c051
paused EQU $c050
Game_WorldChanged EQU $c080   ; generation consumed by SCREEN4 world overlay
Game_ActorsBase EQU $c800
driving EQU $c400
player_animation EQU $c404
player_x EQU $c405
player_y EQU $c407
player_native_ticks EQU $c440
player_pending_x EQU $c450
player_pending_y EQU $c452
Enemy_HitAddress EQU $c63c
VIEWPORT_HALF EQU 104
STAGE_COLUMNS EQU 102
STAGE_ROWS EQU 174
PLAYER_BANK EQU GAME_NATIVE_BANK
Full_AITable0 EQU $d2a8
Full_AITable1 EQU $d2b6
Full_AIBefore EQU $d2c4
Full_AITick EQU $d2cb

Game_InitCore:
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
    xor a
    ld hl,$c040
    ld de,$c041
    ld bc,63
    ld (hl),a
    ldir
    ld a,1
    ld (Game_WorldChanged),a
    xor a
    ld hl,$c400
    ld de,$c401
    ld bc,$3ff
    ld (hl),a
    ldir
    call Rock_Init
    call Death_Init
    call Flag_Init
    call Score_Init
    call Fuel_Init
    call Life_Init
    call Smoke_Init
    ld hl,Game_SmokeChanged
    inc (hl)
    call $9b1f
    call Game_InitCars
    call GameAudio_Init
    ld a,GameAudio_EVENT_START
    call GameAudio_Event
    jp Game_Position

Game_InitCars:
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
    call $8c6c
    call Enemy_Init
    IFDEF GAMEPLAY_CONFIGURED
    IF GAME_TEST_ENEMIES
    call GameMulti_Init
    ENDIF
    ENDIF
    ld hl,($e027)
    ld ($e069),hl
    ld ($e02d),hl
    ld a,1
    ld (driving),a
    ld ($e020),a
    ld ($e28b),a
    xor a
    ld (player_animation),a
    ret

Game_Frame:
    ld (Game_Due),a
.tick:
    ld a,(Game_Due)
    or a
    jp z,Game_Position
    dec a
    ld (Game_Due),a
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
    call GameAudio_Tick
    ld a,(Game_State)
    or a
    jr nz,.tick
    call Game_ReadInput
    call $8f24
    call $83fd
    call Game_LogicTick
    ld hl,(player_native_ticks)
    inc hl
    ld (player_native_ticks),hl
    call Game_Events
    jr .tick

Game_LogicTick:
    ld a,(Round_State)
    or a
    jr z,.death
    call Round_Tick
    ld a,(Round_State)
    cp 3
    ret nz
    ld a,2
    ld (Game_State),a
    ret
.death:
    ld a,(Death_State)
    or a
    jr z,.active
    call Death_Tick
    ld a,(Death_State)
    ld (Death_DisplayState),a
    cp 2
    ret nz
    ld a,($e00f)
    or a
    jr nz,Game_Restart
    ld a,1
    ld (Game_State),a
    ld a,GameAudio_EVENT_GAMEOVER
    jp GameAudio_Event
.active:
    call Fuel_Tick
    ld a,(Fuel_SpeedClock)
    and 7
    call z,$8472
    ld a,(Fuel_Active)
    or a
    ret nz
    ld a,(player_native_ticks)
    and 1
    jr nz,.idle
    call Smoke_PreTick
    call $b60c
    call $8069
    call Smoke_Tick
    call $9052
    call Game_Animation
    call Enemy_AfterMove
    call Rock_Update
    ld a,(Enemy_Contact)
    or a
    call z,Flag_Update
    call Score_Update
    call Fuel_Begin
    call Parameters_Update
    IFDEF GAMEPLAY_CONFIGURED
    IF GAME_TEST_ENEMIES
    call GameMulti_Parameters
    ENDIF
    ENDIF
    call Death_Begin
    ld a,(Death_State)
    ld (Death_DisplayState),a
    xor a
    ld (Flag_Jobs),a
    ld (Death_Jobs),a
    call Round_Frame
    ret
.idle:
    call $8069
    call Smoke_Tick
    call Game_Animation
    call $b600
    jp Enemy_CameraOnly

Game_Restart:
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld hl,$a025
    ld de,$e025
    ld bc,8
    ldir
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
    call $88e7
    call Fuel_Init
    call Death_Init
    call Rock_Init
    call Smoke_Init
    ld hl,Game_SmokeChanged
    inc (hl)
    xor a
    ld (Game_SmokeSeen),a
    ld (Game_SmokeSeen+1),a
    ld hl,Game_WorldChanged
    inc (hl)
    call Game_InitCars
    ld a,GameAudio_EVENT_BACKGROUND
    jp GameAudio_Event

Game_Animation:
    ld hl,player_animation
    inc (hl)
    ld a,(hl)
    cp 4
    ret c
    ld (hl),0
    jp $9ddf

Game_Events:
    ld a,(Flag_Count)
    ld hl,Game_FlagSeen
    cp (hl)
    jr z,.smoke
    ld (hl),a
    ld hl,Game_WorldChanged
    inc (hl)
    ld a,(Flag_Kind)
    cp 1
    ld a,GameAudio_EVENT_FLAG
    jr z,.flag_event
    ld a,GameAudio_EVENT_SPECIAL_FLAG
.flag_event:
    call GameAudio_Event
.smoke:
    ld hl,(Smoke_Placements)
    ld de,(Game_SmokeSeen)
    or a
    sbc hl,de
    jr z,.death
    ld hl,(Smoke_Placements)
    ld (Game_SmokeSeen),hl
    ld a,GameAudio_EVENT_SMOKE
    call GameAudio_Event
.death:
    ld a,(Death_State)
    ld hl,Game_DeathSeen
    cp (hl)
    jr z,.round
    ld (hl),a
    ld hl,Game_WorldChanged
    inc (hl)
    cp 1
    jr nz,.round
    ld a,GameAudio_EVENT_DEATH
    call GameAudio_Event
.round:
    ld a,(Round_State)
    ld hl,Game_RoundSeen
    cp (hl)
    ret z
    ld (hl),a
    cp 1
    ret nz
    ld a,GameAudio_EVENT_CLEAR
    jp GameAudio_Event

Game_ReadInput:
    in a,($aa)
    ld e,a
    and $f0
    or 8
    out ($aa),a
    in a,($a9)
    ld d,a
    ld a,e
    out ($aa),a
    ld b,255
    xor a
    ld (Smoke_Key),a
    bit 0,d
    jr nz,.left
    inc a
    ld (Smoke_Key),a
    res 1,b
.left:
    bit 4,d
    jr nz,.up
    res 2,b
.up:
    bit 5,d
    jr nz,.down
    res 5,b
.down:
    bit 6,d
    jr nz,.right
    res 4,b
.right:
    bit 7,d
    jr nz,.done
    res 3,b
.done:
    ld a,b
    ld ($e3f0),a
    ret

Player_Position:
Game_Position:
    ld a,($e070)
    ld hl,$e06d
    call Player_Axis
    ld (player_x),hl
    ld (player_pending_x),hl
    ld de,-104
    add hl,de
    ld de,608
    call Game_Clamp
    ld (cx),hl
    ld a,($e072)
    ld hl,$e06f
    call Player_AxisY
    ld (player_y),hl
    ld (player_pending_y),hl
    ld de,-105
    add hl,de
    ld de,1180
    call Game_Clamp
    ld (cy),hl
    ret
Game_Clamp:
    bit 7,h
    jr z,.maximum
    ld hl,0
    ret
.maximum:
    push hl
    or a
    sbc hl,de
    pop hl
    ret c
    ex de,hl
    ret
Player_AxisY:
    ld c,(hl)
    ld h,0
    ld l,a
    call Player_Cell
    ld a,c
    neg
    jr Player_Offset
Player_Axis:
    ld c,(hl)
    ld h,0
    ld l,a
    call Player_Cell
    ld a,c
Player_Offset:
    ld e,a
    ld d,0
    bit 7,a
    jr z,.positive
    dec d
.positive:
    add hl,de
    ret
Player_Cell:
    add hl,hl
    add hl,hl
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ld de,36
    add hl,de
    ret
stage_div8:
    sra h
    rr l
    sra h
    rr l
    sra h
    rr l
    ret

Game_Actors:
    ld ix,Game_ActorsBase
    ld iy,$e068
    xor a
    ld (Game_ActorKind),a
    ld a,($e24e)
    inc a
    cp 9
    jr c,.count
    ld a,8
.count:
    ld (Game_ActorCount),a
    ld b,a
    or a
    jp z,.inactive
    ; Cell coordinates have the same +36 center offset on both axes. Fold
    ; the -8 sprite origin and camera subtraction once per presentation.
    ld hl,28
    ld de,(cx)
    or a
    sbc hl,de
    ld (Game_ActorX),hl
    ld hl,28
    ld de,(cy)
    or a
    sbc hl,de
    ld (Game_ActorY),hl
.actor:
    push bc
    ld (ix+5),255
    ld c,(iy+5)
    ld a,(iy+8)
    call Game_ActorAxis
    ld de,(Game_ActorX)
    add hl,de
    ld (ix+0),l
    ld (ix+1),h
    ld a,(iy+7)
    neg
    ld c,a
    ld a,(iy+10)
    call Game_ActorAxis
    ld de,(Game_ActorY)
    add hl,de
    ld (ix+2),l
    ld (ix+3),h
    ld a,(iy+15)
    ld l,a
    ld h,0
    ld de,Game_AnimationFlags
    add hl,de
    ld a,(hl)
    cp 12
    jr nc,.next
    ld (ix+4),a
    ld a,(Game_ActorKind)
    or a
    jr nz,.enemy
    ld a,(Death_State)
    or a
    jr nz,.next
    xor a
    jr .kind
.enemy:
    ld a,1
.kind:
    ld (ix+5),a
.next:
    ld de,6
    add ix,de
    ld de,32
    add iy,de
    ld hl,Game_ActorKind
    inc (hl)
    pop bc
    djnz .actor
.inactive:
    ; Inactive records retain their old coordinate/animation bytes, exactly
    ; as before; only kind is published. No native descriptor is read here.
    ld a,(Game_ActorCount)
    neg
    add a,8
    jr z,.done
    ld b,a
    ld de,6
.hide:
    ld (ix+5),255
    add ix,de
    djnz .hide
.done:
    ld a,8
    ld (Game_ActorKind),a
    ret

Game_ActorAxis:
    ; A=unsigned cell, C=signed native offset (Y has already used 8-bit NEG).
    ; Keep the native modulo-65536 arithmetic, including offset -128.
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ld a,c
    rlca
    sbc a,a
    ld d,a
    ld e,c
    add hl,de
    ret

; Permanent Page0 RAM removes the production mapper overlay's ownership work.
Full_CacheEnter:
Full_CacheLeave:
    ret
; These native-bank labels are fixed entry points emitted by game_core.py.
; The AI file begins with 12 bytes of jumps followed by constants then speed.
Game_AnimationFlags:
    INCBIN "player-flags.bin"

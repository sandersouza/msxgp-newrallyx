; ROM entry runs at $9000; copied code runs at $1000 in the audio mapper.
Audio_InitOverlay:
    call Full_CacheEnter
    in a,($ff)
    xor 2
    out ($fc),a
    ld hl,$8000
    ld de,0
    ld bc,$4000
    ldir
    call Full_CacheLeave
    xor a
    ld (Audio_Mute),a
    ld (Audio_Held),a
    ld (Audio_Ticks),a
    ld (Audio_Ticks+1),a
    ld (Audio_ReferenceMode),a
    ld (Audio_NewScene),a
    ld (Audio_Elapsed),a
    ld a,(ticks)
    ld (Audio_LastUI),a
    ret

Audio_Step:
    call Audio_Control
    ld a,($e9f4)
    bit 7,a
    jr z,.sequence
    ld a,15
    ld (Audio_BangAge),a
.sequence:
    ld a,(Audio_BangAge)
    or a
    jr z,.bang_clocked
    dec a
    ld (Audio_BangAge),a
.bang_clocked:
    call $2580
    ld a,(Audio_Ticks)
    and 1
    call z,Audio_Render
Audio_Return:
    ld a,PLAYER_BANK
    ld ($7000),a
    ret

Audio_Control:
    ld hl,(Audio_Ticks)
    inc hl
    ld (Audio_Ticks),hl
    ; F4 edge changes only the output. Original sequencing never stops.
    ld a,7
    call read_keys
    and 1
    ld b,a
    ld a,(Audio_Held)
    xor b
    and b
    ld a,b
    ld (Audio_Held),a
    jr z,.key_done
    ld a,(Audio_Mute)
    xor 1
    ld (Audio_Mute),a
    ld a,1
    ld (Audio_OutputDirty),a
.key_done:
    ret

; Preserve all four high nibbles of the original aligned 20-bit phase step.
; A lookup trades unused cartridge space for bounded conversion time.
    MACRO audio_voice source,dest,volume
    ld a,(source+4)
    and 15
    jr z,1f                  ; Inaudible voices need no frequency conversion.
    ld c,a
    ld a,(source+3)
    and 15
    rlca
    rlca
    rlca
    rlca
    ld h,a
    ld a,(source+2)
    and 15
    or h
    ld h,a
    ld a,(source+1)
    and 15
    rlca
    rlca
    rlca
    rlca
    ld l,a
    ld a,(source)
    and 15
    or l
    ld l,a
    ld a,h
    rlca
    rlca
    rlca
    and 7
    add a,AUDIO_PERIOD_BANK
    ld ($7000),a
    add hl,hl
    ld a,h
    and $3f
    or $80
    ld h,a
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld (dest),de
    ld a,d
    or e
    jr z,2f
    ld l,c
    ld h,Audio_Volumes/256
    ld a,(hl)
    jr 2f
1:  ld hl,0
    ld (dest),hl
    xor a
2:
    ld (volume),a
    ENDM

Audio_Render:
    audio_voice $3a11,Audio_Desired,Audio_Desired+8
    audio_voice $3a16,Audio_Desired+2,Audio_Desired+9
    audio_voice $3a1b,Audio_Desired+4,Audio_Desired+10
    ld a,7
    out ($a0),a
    in a,($a2)
    and $c0                  ; Keep both joystick I/O directions intact.
    or $38                   ; Three tones; noise initially disabled.
    ld (Audio_Desired+7),a
    ld a,(Audio_BangAge)
    or a
    jr z,Audio_WriteOutput
    ld (Audio_Desired+10),a  ; Bounded decay, channel C temporarily owns BANG.
    cpl
    and 15
    add a,12
    ld (Audio_Desired+6),a
    ld a,(Audio_Desired+7)
    xor $24                  ; Noise C on, tone C off; preserve tones A/B.
    ld (Audio_Desired+7),a
Audio_WriteOutput:
    ld a,(Audio_Mute)
    ld b,a
    ld a,(Full_Attract)
    or b
    jr z,.write
    ld hl,(Audio_Desired+8)
    push hl
    ld a,(Audio_Desired+10)
    push af
    xor a
    ld (Audio_Desired+8),a
    ld (Audio_Desired+9),a
    ld (Audio_Desired+10),a
    call .write
    pop af
    ld (Audio_Desired+10),a
    pop hl
    ld (Audio_Desired+8),hl
    ret
.write:
    ld hl,Audio_Desired
    ld de,Audio_LastPSG
    ld b,11
    ld c,0
.register:
    ld a,(de)
    cp (hl)
    jr z,.next
    ld a,c
    out ($a0),a
    ld a,(hl)
    out ($a1),a
    ld (de),a
.next:
    inc hl
    inc de
    inc c
    djnz .register
    ret
    ALIGN 256
Audio_Volumes:
    INCBIN "audio-volumes.bin"

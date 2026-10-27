; Two music voices and one independent noise voice. Events never wait for a
; playing effect to finish: one queued event starts per 30 Hz output packet.
Audio_PlayDesired EQU $e9a0
Audio_PlayLastPSG EQU $e9b0
Audio_QueueCount EQU $e9c0
Audio_QueueHead EQU $e9c1
Audio_QueueTail EQU $e9c2
Audio_NoiseID EQU $e9c3
Audio_NoisePhase EQU $e9c4
Audio_QueueDrops EQU $e9c5
Audio_DeathSeen EQU $e9c6
Audio_SmokeSeen EQU $e9c7
Audio_MusicRequest EQU $e9ca
Audio_MusicDirty EQU $e9cb
Audio_OutputDirty EQU $e9cd
Audio_NoiseDirty EQU $e9ce
Audio_FlagSeen EQU $e9cf
Audio_MusicPointer EQU $e9d0
Audio_MusicLeft EQU $e9d2
Audio_MusicMode EQU $e9d3
Audio_Queue EQU $e9e0

Audio_RuntimeStep:
    ei
    nop
    call Full_TurboOn
    call Audio_RuntimeControl
    call Audio_Observe
    call Audio_MusicTick
    call Audio_NoiseTick
    ld a,(Audio_MusicDirty)
    ld b,a
    ld a,(Audio_NoiseDirty)
    or b
    ld b,a
    ld a,(Audio_OutputDirty)
    or b
    call nz,Audio_RenderMusic
    xor a
    ld (Audio_OutputDirty),a
    jp Full_TurboOff

Audio_RuntimeControl:
    ld hl,(Audio_Ticks)
    inc hl
    ld (Audio_Ticks),hl
    ld a,7
    call read_keys
    and 1
    ld b,a
    ld a,(Audio_Held)
    xor b
    and b
    ld a,b
    ld (Audio_Held),a
    ret z
    ld a,(Audio_Mute)
    xor 1
    ld (Audio_Mute),a
    ld a,1
    ld (Audio_OutputDirty),a
    ret

Audio_Observe:
    ; Scene reloads restart the melody, without coupling it to bitmap work.
    ld a,(Audio_NewScene)
    or a
    jr z,.death
    xor a
    ld (Audio_NewScene),a
    ld hl,$e9a0
    ld de,$e9a1
    ld bc,79
    ld (hl),0
    ldir
    ld hl,Audio_PlayLastPSG
    ld b,11
.invalidate:
    ld (hl),255
    inc hl
    djnz .invalidate
    ld a,1
    ld (Audio_OutputDirty),a ; A silent scene must also replace the preceding PSG output.
    ld a,(Session_State)
    or a
    jr nz,.scene_ready
    ld a,$10                ; Scene loads begin background music, never the start cue.
    ld ($e9f5),a
.scene_ready:
    ld a,(Flag_Count)
    ld (Audio_FlagSeen),a
    ld a,(Smoke_Placements)
    ld (Audio_SmokeSeen),a
.death:
    ld a,(Death_State)
    cp 1
    ld a,0
    jr nz,.death_latch
    inc a
    ld b,a
    ld a,(Audio_DeathSeen)
    or a
    ld a,b
    jr nz,.death_latch
    push af
    ld a,(Session_State)
    or a
    jr nz,.death_ignored    ; Ignore stale UI death state without taxing the live path.
    ld a,$80
    ld ($e9f4),a
    ld a,8
    ld ($e9f5),a
.death_ignored:
    pop af
.death_latch:
    ld (Audio_DeathSeen),a
    ld a,(Flag_Count)
    ld hl,Audio_FlagSeen
    cp (hl)
    jr z,.flags_done
    ld (hl),a
    jr c,.flags_done
    ld hl,$e9f4
    ld a,(Flag_Kind)
    cp 1
    jr nz,.special_flag
    set 2,(hl)
    jr .flags_done
.special_flag:
    set 3,(hl)
.flags_done:
    ld a,(Smoke_Placements)
    ld hl,Audio_SmokeSeen
    cp (hl)
    jr z,.smoke_done
    ld (hl),a
    ld hl,$e9f4
    set 4,(hl)
.smoke_done:
    ld a,($e9f6)
    and $c0
    ld b,a
    ld a,($e9f4)
    and $bf
    or b
    ret z
    ld a,($e9f4)
    ld b,a
    and $40                  ; Retain the engine request as native state only.
    ld ($e9f4),a
    ld a,($e9f6)
    ld c,a
    and $3f
    ld ($e9f6),a
    ; Coalesce simultaneous effects by priority; capture/death wins over smoke.
    ld a,8
    bit 7,b
    jr nz,.enqueue
    dec a
    bit 3,b
    jr nz,.enqueue
    bit 6,c
    jr nz,.enqueue
    dec a
    bit 2,b
    jr nz,.enqueue
    dec a
    bit 7,c
    jr nz,.enqueue
    dec a
    bit 0,b
    jr nz,.enqueue
    dec a
    bit 5,b
    jr nz,.enqueue
    dec a
    bit 4,b
    jr nz,.enqueue
    dec a
.enqueue:
    jp Audio_Enqueue

; A=authored effect ID 1..8. Never block gameplay on a saturated queue.
Audio_Enqueue:
    ld c,a
    cp 8
    jr nz,.capacity
    xor a                    ; A crash preempts stale lower-priority effects.
    ld (Audio_QueueCount),a
    ld (Audio_QueueHead),a
    ld (Audio_QueueTail),a
.capacity:
    ld hl,Audio_QueueCount
    ld a,(hl)
    cp 8
    jr c,.space
    ld hl,Audio_QueueDrops
    inc (hl)
    ret
.space:
    inc (hl)
    ld a,(Audio_QueueTail)
    ld e,a
    inc a
    and 7
    ld (Audio_QueueTail),a
    ld d,0
    ld hl,Audio_Queue
    add hl,de
    ld (hl),c
    ret

Audio_MusicTick:
    xor a
    ld (Audio_MusicDirty),a
    ld a,($e9f5)
    and $b4
    ld (Audio_MusicRequest),a
    call Audio_SelectMusic   ; UI/attract transitions can leave native request bits unchanged.
    ld c,a
    ld a,(Audio_MusicMode)
    cp c
    jr nz,.changed
.same_request:
    ld a,(Audio_MusicMode)
    or a
    ret z
    ld a,(Audio_Elapsed)
    ld b,a
    ld a,(Audio_MusicLeft)
    sub b
    jr c,.due
    jr z,.due
    ld (Audio_MusicLeft),a
    ret
.due:
    neg
    ld b,a                  ; Carry elapsed score frames across a note boundary.
    jr .load
.changed:
    ld a,c
    ld (Audio_MusicMode),a
    or a
    jp z,.silence
    call Audio_ScoreStart
    ld b,0
.load:
    ld hl,(Audio_MusicPointer)
    ld a,(hl)
    or a
    jr z,.end
    sub b
    jr c,.skip
    jr z,.skip
    ld (Audio_MusicLeft),a
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld (Audio_PlayDesired),de
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld (Audio_PlayDesired+2),de
    ld a,(hl)
    ld c,a
    and 15
    ld (Audio_PlayDesired+8),a
    ld a,c
    rrca
    rrca
    rrca
    rrca
    and 15
    ld (Audio_PlayDesired+9),a
    inc hl
    ld (Audio_MusicPointer),hl
    ld a,1
    ld (Audio_MusicDirty),a
    ret
.skip:
    neg
    ld b,a
    ld de,6
    add hl,de
    ld (Audio_MusicPointer),hl
    jr .load
.end:
    ld a,(Audio_MusicMode)
    cp 3
    jr z,.intro_end
    cp 4
    jr z,.complete_end
    cp 5
    jr z,.gameover_end
    call Audio_ScoreStart
    jr .load
.intro_end:
    ld hl,$e9f5
    res 7,(hl)
    jr .next_song
.complete_end:
    ld hl,$e9f5
    res 5,(hl)
    jr .next_song
.gameover_end:
    ld hl,$e9f5
    res 2,(hl)
.next_song:
    call Audio_SelectMusic
    ld (Audio_MusicMode),a
    or a
    jr z,.silence
    call Audio_ScoreStart
    jr .load
.silence:
    xor a
    ld (Audio_PlayDesired+8),a
    ld (Audio_PlayDesired+9),a
    ld hl,0
    ld (Audio_PlayDesired),hl
    ld (Audio_PlayDesired+2),hl
    ld a,1
    ld (Audio_MusicDirty),a
    ret

Audio_SelectMusic:
    ld a,(Full_Attract)
    or a
    jr nz,.silent
    ld a,(Session_State)
    or a
    jr z,.gameplay
    cp 5
    jr z,.start
    cp 2
    jr nz,.silent           ; Insert-coin/player-select screens have no melody.
    ld a,($e9f5)
    bit 2,a
    jr nz,.gameover
    jr .silent
.start:
    ld a,($e9f5)
    bit 7,a
    jr nz,.intro
    jr .silent
.gameplay:
    ld a,($e9f5)
    bit 5,a
    jr nz,.complete
    bit 2,a
    jr nz,.gameover
    bit 4,a
    jr z,.silent
    ld a,($e1b0)
    and 3
    ld a,1
    ret nz
    inc a
    ret
.intro:
    ld a,3
    ret
.complete:
    ld a,4
    ret
.gameover:
    ld a,5
    ret
.silent:
    xor a
    ret
Audio_ScoreStart:
    add a,a
    ld e,a
    ld d,0
    ld hl,Audio_Scores
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld (Audio_MusicPointer),de
    ret
Audio_Scores:
    dw 0,Audio_NormalScore+$8000,Audio_ChallengeScore+$8000,Audio_IntroScore+$8000,Audio_CompleteScore+$8000,Audio_GameoverScore+$8000

Audio_NoiseTick:
    ld a,(Audio_QueueCount)
    or a
    jr nz,.active
    ld a,(Audio_NoiseID)
    or a
    jr nz,.active
    xor a
    ld (Audio_NoiseDirty),a
    ld a,(Session_State)
    or a
    jr nz,.silent
    ld a,(Death_State)
    or a
    jr nz,.silent
    ld a,(Audio_PlayDesired+10)
    cp 2
    ret z                    ; Sustained engine requires no synthesis or PSG writes.
    jr .silent
.active:
    ld a,(Audio_NoiseID)
    ld b,a
    ld a,(Audio_QueueCount)
    or b
    ld (Audio_NoiseDirty),a
    ld hl,Audio_QueueCount
    ld a,(hl)
    or a
    jr z,.profile
    dec (hl)
    ld a,(Audio_QueueHead)
    ld e,a
    inc a
    and 7
    ld (Audio_QueueHead),a
    ld d,0
    ld hl,Audio_Queue
    add hl,de
    ld a,(hl)
    ld (Audio_NoiseID),a
    xor a
    ld (Audio_NoisePhase),a
.profile:
    ld a,(Audio_NoiseID)
    or a
    jr z,.silent
    dec a
    rlca
    rlca
    rlca
    rlca
    ld e,a
    ld a,(Audio_NoisePhase)
    add a,a
    add a,e
    ld l,a
    ld h,Audio_NoiseProfiles/256
    ld a,(hl)
    ld (Audio_PlayDesired+6),a
    inc hl
    ld a,(hl)
    ld (Audio_PlayDesired+10),a
    or a
    jr z,.finished
    ld hl,Audio_NoisePhase
    inc (hl)
    ret
.silent:
    ld c,0
    ld a,(Session_State)
    or a
    jr nz,.engine_volume
    ld a,(Death_State)
    or a
    jr nz,.engine_volume
    ld a,9
    ld hl,Audio_PlayDesired+6
    cp (hl)
    jr z,.engine_same
    ld (hl),a
    ld a,1
    ld (Audio_NoiseDirty),a
.engine_same:
    ld c,2                  ; Quiet engine texture; discrete effects preempt it.
.engine_volume:
    ld hl,Audio_PlayDesired+10
    ld a,c
    cp (hl)
    ret z
    ld (hl),a
    ld a,1
    ld (Audio_NoiseDirty),a
    ret
.finished:
    ld (Audio_NoiseID),a
    ret

Audio_RenderMusic:
    ld a,7
    out ($a0),a
    in a,($a2)
    and $c0
    or $1c                   ; Tones A/B; independent noise C, no tone C.
    ld (Audio_PlayDesired+7),a
    ; Preserve the desired packet while muting only physical amplitudes.
    ld a,(Audio_Mute)
    ld b,a
    ld a,(Full_Attract)
    or b
    jr z,Audio_WritePSG
    ld hl,(Audio_PlayDesired+8)
    push hl
    ld a,(Audio_PlayDesired+10)
    push af
    xor a
    ld (Audio_PlayDesired+8),a
    ld (Audio_PlayDesired+9),a
    ld (Audio_PlayDesired+10),a
    call Audio_WritePSG
    pop af
    ld (Audio_PlayDesired+10),a
    pop hl
    ld (Audio_PlayDesired+8),hl
    ret
Audio_WritePSG:
    ld hl,Audio_PlayDesired
    ld de,Audio_PlayLastPSG
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
Audio_NoiseProfiles:
    ; Eight (period,volume) pairs; zero volume always terminates a profile.
    db 3,6, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0  ; fuel award
    db 4,9, 8,8, 12,6, 16,3, 0,0, 0,0, 0,0, 0,0 ; smoke
    db 2,10, 5,7, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0 ; warning
    db 1,12, 3,10, 5,8, 0,0, 0,0, 0,0, 0,0, 0,0 ; extra life
    db 2,11, 4,8, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0 ; credit
    db 1,12, 3,8, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0 ; flag
    db 1,14, 2,12, 4,10, 7,6, 0,0, 0,0, 0,0, 0,0 ; special flag
    db 12,15, 16,14, 20,12, 24,10, 28,7, 31,4, 0,0, 0,0 ; crash
Audio_RuntimeEnd:

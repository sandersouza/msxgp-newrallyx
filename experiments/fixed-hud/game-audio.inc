; Resident adapter reusing the authored Issue #13 PSG music/noise worker.
; Include game-audio-data.inc before this file. Define GAME_AUDIO_BANK.
; All code below stays in the fixed $4000..$7fff cartridge bank; score packets
; alone live at $8000 in GAME_AUDIO_BANK. Never execute this file from Page2.
; No native gameplay state is read or written. Private RAM: $dc00..$dc52.
;
; Init: starts looping background, clears queue and invalidates PSG shadow.
; Tick: A = current ASCII16 Page2 bank; invoke exactly once per elapsed nominal
;       60 Hz simulation tick. Every second call services 30 Hz audio and restores
;       A's bank before returning. Catch up elapsed ticks, do not drop them.
; Event: A = constants below. No bank requirement. May clobber AF/BC/DE/HL.
; Stop: silences A/B/C immediately and clears requests/queue.
; All APIs clobber AF/BC/DE/HL; caller saves live native registers. Not reentrant.
; IRQ may interrupt PSG writes only if it never accesses PSG or changes mapper.
; APIs preserve interrupt enable state (no DI/EI); run from main loop only.
; Timing estimates, UNMEASURED at 3.58MHz: idle packet roughly 1.5K cycles;
; note/effect packet roughly 3K cycles, maximum PSG update adds ~1.2K cycles.
; Integration ledger must measure actual inclusive/self and worst-case costs.
GameAudio_EVENT_START EQU 1
GameAudio_EVENT_FLAG EQU 2
GameAudio_EVENT_SMOKE EQU 3
GameAudio_EVENT_DEATH EQU 4
GameAudio_EVENT_CLEAR EQU 5
GameAudio_EVENT_BACKGROUND EQU 6
GameAudio_EVENT_SPECIAL_FLAG EQU 7
GameAudio_EVENT_GAMEOVER EQU 8
GameAudio_Inactive EQU $dc50
GameAudio_Elapsed EQU $dc51
GameAudio_Divider EQU $dc52
GameAudio_StateEnd EQU $dc53

GameAudio_Init:
    xor a
    ld hl,$dc00
    ld de,$dc01
    ld bc,GameAudio_StateEnd-$dc00-1
    ld (hl),a
    ldir
    ld hl,GameAudio_PlayLastPSG
    ld b,11
.invalidate:
    ld (hl),255
    inc hl
    djnz .invalidate
    ld a,1
    ld (GameAudio_Elapsed),a
    ld (GameAudio_MusicRequest),a
    ld (GameAudio_OutputDirty),a
    ret

GameAudio_Tick:
    push af
    ld hl,GameAudio_Divider
    ld a,(hl)
    xor 1
    ld (hl),a
    jr nz,.return
    ld a,GAME_AUDIO_BANK
    ld ($7000),a
    call GameAudio_MusicTick
    call GameAudio_NoiseTick
    ld a,(GameAudio_MusicDirty)
    ld b,a
    ld a,(GameAudio_NoiseDirty)
    or b
    ld b,a
    ld a,(GameAudio_OutputDirty)
    or b
    call nz,GameAudio_RenderMusic
    xor a
    ld (GameAudio_OutputDirty),a
.return:
    pop af
    ld ($7000),a
    ret

GameAudio_Event:
    cp GameAudio_EVENT_FLAG
    ld c,6
    jr z,.effect
    cp GameAudio_EVENT_SPECIAL_FLAG
    ld c,7
    jr z,.effect
    cp GameAudio_EVENT_SMOKE
    ld c,2
    jr z,.effect
    cp GameAudio_EVENT_DEATH
    jr z,.death
    cp GameAudio_EVENT_START
    ld c,3
    jr z,.music
    cp GameAudio_EVENT_CLEAR
    ld c,4
    jr z,.inactive_music
    cp GameAudio_EVENT_GAMEOVER
    ld c,5
    jr z,.inactive_music
    cp GameAudio_EVENT_BACKGROUND
    ret nz
    ld c,1
.music:
    xor a
    ld (GameAudio_Inactive),a
    jr .request
.inactive_music:
    ld a,1
    ld (GameAudio_Inactive),a
.request:
    ld a,c
    ld (GameAudio_MusicRequest),a
    ld a,255
    ld (GameAudio_MusicMode),a
    ret
.death:
    ld a,1
    ld (GameAudio_Inactive),a
    xor a
    ld (GameAudio_MusicRequest),a
    ld c,8
.effect:
    ld a,c
    jp GameAudio_Enqueue

GameAudio_Stop:
    call GameAudio_Init
    xor a
    ld (GameAudio_MusicRequest),a
    inc a
    ld (GameAudio_Inactive),a
    ; Init cleared desired amplitudes and invalidated the register shadow.
    jp GameAudio_RenderMusic

GameAudio_PlayDesired EQU $dc00
GameAudio_PlayLastPSG EQU $dc10
GameAudio_QueueCount EQU $dc20
GameAudio_QueueHead EQU $dc21
GameAudio_QueueTail EQU $dc22
GameAudio_NoiseID EQU $dc23
GameAudio_NoisePhase EQU $dc24
GameAudio_QueueDrops EQU $dc25
GameAudio_DeathSeen EQU $dc26
GameAudio_SmokeSeen EQU $dc27
GameAudio_MusicRequest EQU $dc2a
GameAudio_MusicDirty EQU $dc2b
GameAudio_OutputDirty EQU $dc2d
GameAudio_NoiseDirty EQU $dc2e
GameAudio_FlagSeen EQU $dc2f
GameAudio_MusicPointer EQU $dc30
GameAudio_MusicLeft EQU $dc32
GameAudio_MusicMode EQU $dc33
GameAudio_Queue EQU $dc40

GameAudio_Enqueue:
    ld c,a
    cp 8
    jr nz,.capacity
    xor a                    ; A crash preempts stale lower-priority effects.
    ld (GameAudio_QueueCount),a
    ld (GameAudio_QueueHead),a
    ld (GameAudio_QueueTail),a
.capacity:
    ld hl,GameAudio_QueueCount
    ld a,(hl)
    cp 8
    jr c,.space
    ld hl,GameAudio_QueueDrops
    inc (hl)
    ret
.space:
    inc (hl)
    ld a,(GameAudio_QueueTail)
    ld e,a
    inc a
    and 7
    ld (GameAudio_QueueTail),a
    ld d,0
    ld hl,GameAudio_Queue
    add hl,de
    ld (hl),c
    ret

GameAudio_MusicTick:
    xor a
    ld (GameAudio_MusicDirty),a
    call GameAudio_SelectMusic
    ld c,a
    ld a,(GameAudio_MusicMode)
    cp c
    jr nz,.changed
.same_request:
    ld a,(GameAudio_MusicMode)
    or a
    ret z
    ld a,(GameAudio_Elapsed)
    ld b,a
    ld a,(GameAudio_MusicLeft)
    sub b
    jr c,.due
    jr z,.due
    ld (GameAudio_MusicLeft),a
    ret
.due:
    neg
    ld b,a                  ; Carry elapsed score frames across a note boundary.
    jr .load
.changed:
    ld a,c
    ld (GameAudio_MusicMode),a
    or a
    jp z,.silence
    call GameAudio_ScoreStart
    ld b,0
.load:
    ld hl,(GameAudio_MusicPointer)
    ld a,(hl)
    or a
    jr z,.end
    sub b
    jr c,.skip
    jr z,.skip
    ld (GameAudio_MusicLeft),a
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld (GameAudio_PlayDesired),de
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld (GameAudio_PlayDesired+2),de
    ld a,(hl)
    ld c,a
    and 15
    ld (GameAudio_PlayDesired+8),a
    ld a,c
    rrca
    rrca
    rrca
    rrca
    and 15
    ld (GameAudio_PlayDesired+9),a
    inc hl
    ld (GameAudio_MusicPointer),hl
    ld a,1
    ld (GameAudio_MusicDirty),a
    ret
.skip:
    neg
    ld b,a
    ld de,6
    add hl,de
    ld (GameAudio_MusicPointer),hl
    jr .load
.end:
    ld a,(GameAudio_MusicMode)
    cp 3
    jr z,.intro_end
    cp 4
    jr z,.complete_end
    cp 5
    jr z,.gameover_end
    call GameAudio_ScoreStart
    jr .load
.intro_end:
    ld a,1                  ; Intro releases the looping background score.
    jr .next_song
.complete_end:
.gameover_end:
    xor a
.next_song:
    ld (GameAudio_MusicRequest),a
    ld (GameAudio_MusicMode),a
    or a
    jr z,.silence
    call GameAudio_ScoreStart
    jr .load
.silence:
    xor a
    ld (GameAudio_PlayDesired+8),a
    ld (GameAudio_PlayDesired+9),a
    ld hl,0
    ld (GameAudio_PlayDesired),hl
    ld (GameAudio_PlayDesired+2),hl
    ld a,1
    ld (GameAudio_MusicDirty),a
    ret

GameAudio_SelectMusic:
    ld a,(GameAudio_MusicRequest)
    ret
GameAudio_ScoreStart:
    add a,a
    ld e,a
    ld d,0
    ld hl,GameAudio_Scores
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld (GameAudio_MusicPointer),de
    ret
GameAudio_Scores:
    dw 0,GameAudio_NormalScore,GameAudio_ChallengeScore,GameAudio_IntroScore,GameAudio_CompleteScore,GameAudio_GameoverScore

GameAudio_NoiseTick:
    ld a,(GameAudio_QueueCount)
    or a
    jr nz,.active
    ld a,(GameAudio_NoiseID)
    or a
    jr nz,.active
    xor a
    ld (GameAudio_NoiseDirty),a
    ld a,(GameAudio_Inactive)
    or a
    jr nz,.silent
    ld a,(GameAudio_Inactive)
    or a
    jr nz,.silent
    ld a,(GameAudio_PlayDesired+10)
    cp 2
    ret z                    ; Sustained engine requires no synthesis or PSG writes.
    jr .silent
.active:
    ld a,(GameAudio_NoiseID)
    ld b,a
    ld a,(GameAudio_QueueCount)
    or b
    ld (GameAudio_NoiseDirty),a
    ld hl,GameAudio_QueueCount
    ld a,(hl)
    or a
    jr z,.profile
    dec (hl)
    ld a,(GameAudio_QueueHead)
    ld e,a
    inc a
    and 7
    ld (GameAudio_QueueHead),a
    ld d,0
    ld hl,GameAudio_Queue
    add hl,de
    ld a,(hl)
    ld (GameAudio_NoiseID),a
    xor a
    ld (GameAudio_NoisePhase),a
.profile:
    ld a,(GameAudio_NoiseID)
    or a
    jr z,.silent
    dec a
    rlca
    rlca
    rlca
    rlca
    ld e,a
    ld a,(GameAudio_NoisePhase)
    add a,a
    add a,e
    ld l,a
    ld h,GameAudio_NoiseProfiles/256
    ld a,(hl)
    ld (GameAudio_PlayDesired+6),a
    inc hl
    ld a,(hl)
    ld (GameAudio_PlayDesired+10),a
    or a
    jr z,.finished
    ld hl,GameAudio_NoisePhase
    inc (hl)
    ret
.silent:
    ld c,0
    ld a,(GameAudio_Inactive)
    or a
    jr nz,.engine_volume
    ld a,(GameAudio_Inactive)
    or a
    jr nz,.engine_volume
    ld a,9
    ld hl,GameAudio_PlayDesired+6
    cp (hl)
    jr z,.engine_same
    ld (hl),a
    ld a,1
    ld (GameAudio_NoiseDirty),a
.engine_same:
    ld c,2                  ; Quiet engine texture; discrete effects preempt it.
.engine_volume:
    ld hl,GameAudio_PlayDesired+10
    ld a,c
    cp (hl)
    ret z
    ld (hl),a
    ld a,1
    ld (GameAudio_NoiseDirty),a
    ret
.finished:
    ld (GameAudio_NoiseID),a
    ret

GameAudio_RenderMusic:
    ld a,7
    out ($a0),a
    in a,($a2)
    and $c0
    or $1c                   ; Tones A/B; independent noise C, no tone C.
    ld (GameAudio_PlayDesired+7),a
    jp GameAudio_WritePSG
GameAudio_WritePSG:
    ld hl,GameAudio_PlayDesired
    ld de,GameAudio_PlayLastPSG
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
GameAudio_NoiseProfiles:
    ; Eight (period,volume) pairs; zero volume always terminates a profile.
    db 3,6, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0  ; fuel award
    db 4,9, 8,8, 12,6, 16,3, 0,0, 0,0, 0,0, 0,0 ; smoke
    db 2,10, 5,7, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0 ; warning
    db 1,12, 3,10, 5,8, 0,0, 0,0, 0,0, 0,0, 0,0 ; extra life
    db 2,11, 4,8, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0 ; credit
    db 1,12, 3,8, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0 ; flag
    db 1,14, 2,12, 4,10, 7,6, 0,0, 0,0, 0,0, 0,0 ; special flag
    db 12,15, 16,14, 20,12, 24,10, 28,7, 31,4, 0,0, 0,0 ; crash
GameAudio_RuntimeEnd:

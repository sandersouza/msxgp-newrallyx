; Reuse contract: native-core (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: Game_InitCore, Game_Frame, Game_Position, Game_Actors
; Inputs: Game_Frame: A=elapsed native ticks. Init: relocated E000 seed, navigation and main
;   Page0 RAM installed; generated game-config, multi and host bindings available.
; Outputs: Native state, camera and actor records advance using the original rules; Game_Frame
;   returns with GAME_NATIVE_BANK mapped.
; Registers: Common caller-saved ABI; host/native callbacks must obey their existing adjacent
;   contracts.
; Interrupts: Foreground only. IRQ preserves live registers and mappings. No VDP writes in the
;   simulation core itself.
; Memory / hardware: Existing C040..C07F/core aliases, E000..EFFF relocated native state and
;   Page0 navigation. Original memory lifetimes remain required.
; Reuse boundary: Game-specific native binding. Another port must replace native entry
;   points/state/event adapters at assembly time; the current arcade layout is not a generic
;   API.
; Keep this summary synchronized with the registry and modules/README.md.

; Module contract: Native simulation and host binding; supply generated game-config, seed, host and multi-worker.
; Include once at the original code position. No loader or runtime dispatch.
    INCLUDE "../../game-multi.inc"
    INCLUDE "../../game-core.inc"
    INCLUDE "../../game-host.inc"

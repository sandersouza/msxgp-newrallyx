; Reuse contract: screen4-renderer (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: Game_Init, Game_Prepare, Game_RingPatch, Game_Radar, Game_RadarUpload,
;   GameDirty_Mark, GameDirty_Plan, GameSmoke_MarkCloud, GameNameStream_Wide,
;   GameBoundary_Upload
; Inputs: Prepared native events/actors, world-ID ring, camera/phase state, generated
;   map/terrain/transition tables. Init precedes foreground Prepare/render; commit owns
;   publication.
; Outputs: Updates existing inactive patterns/names, dirty queues, smoke candidates and radar;
;   no visible-set writes are authorized.
; Registers: Common caller-saved ABI; GameDirty_Mark and smoke mark hooks retain their
;   stronger adjacent preservation contracts.
; Interrupts: Host owns foreground/blanking schedule. Existing VDP helpers may DI/EI; no
;   concurrent VRAM writer unless its pointer is restored.
; Memory / hardware: Existing C080/C096/C0B0 state, Page0 radar/dirty/smoke fields at
;   2300..281F, D800 ring and renderer metadata. All aliases and ranges remain in their owner
;   includes.
; Reuse boundary: Assembly-time composition, not a game-independent drop-in. Supply matching
;   world/actor/event adapters and packed SCREEN4 layout. First-stage four-set and
;   full-session eight-set profiles are distinct ABIs.
; Keep this summary synchronized with the registry and modules/README.md.

; Module contract: SCREEN4 cache/ring/dirty/radar assembly-time composition; host owns init/prepare/commit order.
; Include once at the original code position. No loader or runtime dispatch.
    INCLUDE "../../game-phase-cache.inc"
    INCLUDE "../../game-main.inc"
    INCLUDE "../../game-dirty.inc"
    INCLUDE "../../game-smoke-cache.inc"
    INCLUDE "../../game-radar-fast.inc"
    INCLUDE "../../game-name-stream.inc"
    INCLUDE "../../game-boundary-fast.inc"
    INCLUDE "../vdp/transfers.inc"

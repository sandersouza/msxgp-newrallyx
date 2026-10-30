; Reuse contract: world-sprites (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameSprites_Init, GameSprites_Prepare, GameSprites_Commit, GS_MaskedCopyFast,
;   GS_ClippedCopyFast
; Inputs: Eight six-byte records: signed16 X, signed16 Y, animation 0..11, kind
;   player/enemy/inactive. Install compatible two-plane templates and palette. Init ->
;   (Prepare -> Commit)*; cy is the next R23 epoch.
; Outputs: Complete car patterns, mode-2 colors and world SAT slots 14..31. Existing
;   culling/sentinel behavior remains; GS_Culled reports exhausted sentinel tails.
; Registers: AF/BC/DE/HL/IX/IY caller-saved.
; Interrupts: Init requires DI/display off; Prepare preserves entry IFF; Commit is called DI
;   in blanking. IRQ must preserve foreground VDP pointer ownership.
; Memory / hardware: Actors C800..C82F, caches C840..C8C1, scratch C980..CD6A. VRAM patterns
;   2800..2C7F, world colors 18E0..19FF and SAT 1A38..1A7F. Full-session shared poses also
;   retain 2E40..2FFF. HUD slots/patterns remain separate.
; Reuse boundary: Mechanism with an explicit actor/template/palette ABI. Keep 16x16
;   unmagnified sprites, R18=0, R23=cy, sentinel compensation, full drawings and real
;   eight-sprites-per-scanline limits.
; Keep this summary synchronized with the registry and modules/README.md.

; Module contract: Complete native sprite preparation/publication with existing masks, sentinel and hardware limits.
; Include once at the original code position. No loader or runtime dispatch.
    INCLUDE "../../game-sprites.inc"
    INCLUDE "../../game-sprite-mask-fast.inc"
    INCLUDE "../../game-sprite-clip-fast.inc"

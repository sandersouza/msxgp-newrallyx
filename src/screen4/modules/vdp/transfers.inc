; Reuse contract: vdp-transfers (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GamePacketFast_Transfer, GamePacketFast_End
; Inputs: B=1..255, C=VDP data port, HL=readable source. Caller has already selected the VDP
;   write address and mapped the source bank.
; Outputs: B=0; HL advances by input length; C unchanged. Exactly that many bytes go to the
;   VDP data port.
; Registers: AF/flags scratch; B consumed; HL advanced. C, DE, IX, IY preserved.
; Interrupts: No DI/EI; IFF unchanged. IRQ must not change the source mapping, C or the VDP
;   data pointer.
; Memory / hardware: Code only. No scratch RAM, buffers, VRAM reservation, mapper writes or
;   address setup.
; Reuse boundary: Independent mechanism. Include directly in another host with a compatible
;   MSX VDP stream and source lifetime. B=0 is outside this API.
; Keep this summary synchronized with the registry and modules/README.md.

; Module contract: B=1..255,C=VDP data port,HL=source; AF scratch,B=0,HL+=n; DE/IX/IY/IFF preserved.
; Include once at the original code position. No loader or runtime dispatch.
    INCLUDE "../../game-packet-fast.inc"

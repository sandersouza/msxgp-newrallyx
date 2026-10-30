; Reuse contract: startup-replay (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameSession_BootShow
; Inputs: Call once after cold initialization with shared startup bank mapped at 8000;
;   generated opcode 0..4 replay descriptors and palette supplied.
; Outputs: Native-timeline cold replay or consumed skip key; returns EI, PSG silent, R15=0 and
;   regular BLACK border. Caller restores native scratch/seed/audio.
; Registers: AF/BC/DE/HL/IY and Page2 bank caller-saved; main Page0 segment retained.
; Interrupts: Cold UI IRQ scans keys. No active-game calls. HARDWARE_CHECK=0 omits resources,
;   code and gate at build time.
; Memory / hardware: Existing 2900..2FFF worker, C0F8..C0FC state, D300 descriptors and two
;   VRAM pages; no full decoded bitmap buffer.
; Reuse boundary: Reusable replay codec only with matching generated descriptors/timing/skip
;   policy. Include removal must use the existing generator selection contract.
; Keep this summary synchronized with the registry and modules/README.md.

; Optional startup presentation. Comment/remove this one INCLUDE to omit the
; replay code, capture resources and keyboard gate. HARDWARE_CHECK=0 also omits
; it in a separate build. No runtime enable/disable branch is emitted.
    INCLUDE "session-boot.inc"

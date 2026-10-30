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

; Reset-only acquisition. Stop before the original game enables interrupts.
; Original bytes are supplied locally, never embedded in this authored fixture.
    OUTPUT "native.rom"
    INCLUDE "native.asm"
    INCLUDE "native-runtime.inc"
    IF NATIVE_SCHEDULER
    INCLUDE "native-scheduler.inc"
    ENDIF
    IF NATIVE_VIDEO
    INCLUDE "native-video.inc"
    INCLUDE "native-input.inc"
    INCLUDE "video-trampolines.inc"
    ENDIF
    IF NATIVE_LOGIC
    INCLUDE "logic-trampolines.inc"
    IF NATIVE_COORDINATE_OPT
    ALIGN 256
Native_CoordinateDelta:
    INCBIN "native-coordinate.bin"
    ENDIF
    IF NATIVE_FUNCTION_PROBE
    INCLUDE "native-function.inc"
    IF NATIVE_FINE_IRQ
    INCLUDE "native-deadline.inc"
    ENDIF
    ENDIF
    ENDIF
    ASSERT $ <= $8000
    defs $8000-$,$ff
    INCBIN "native-program.bin"
    INCBIN "native-assets.bin"
    defs $24000-$,$ff

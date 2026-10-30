; Module contract: B=1..255,C=VDP data port,HL=source; AF scratch,B=0,HL+=n; DE/IX/IY/IFF preserved.
; Include once at the original code position. No loader or runtime dispatch.
    INCLUDE "../../game-packet-fast.inc"

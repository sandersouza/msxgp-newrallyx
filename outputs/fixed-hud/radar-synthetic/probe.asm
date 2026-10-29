 OUTPUT "probe.rom"
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
main:
 jp main
 defs $8000-$,$ff

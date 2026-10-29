; Host-owned audio state survives native scene reloads. The sequencer's own
; 512-byte workspace lives in the separate Page3-XOR-2 mapper segment.
Audio_Mute EQU $d150
Audio_Held EQU $d151
Audio_Ticks EQU $d152
Audio_LastUI EQU $d154
Audio_ReferenceMode EQU $d155
Audio_NewScene EQU $d156
Audio_Elapsed EQU $d157
Audio_Desired EQU $3b00
Audio_LastPSG EQU $3b20
Audio_BangAge EQU $3b30

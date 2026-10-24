; New addresses are generated and validated by native_build.py.
    INCLUDE "native-layout.inc"
Native_Status       EQU NATIVE_STATE
Native_Error        EQU NATIVE_STATE+1
Native_RAMSlot      EQU NATIVE_STATE+2
Native_Primary      EQU NATIVE_STATE+3
Native_InitialSlots EQU NATIVE_STATE+4
Native_Segments     EQU NATIVE_STATE+8 ; host, renderer, program, game, assets 0..3
Native_SavedTags    EQU NATIVE_STATE+16
Native_Count        EQU NATIVE_STATE+32
Native_Candidate    EQU NATIVE_STATE+33
Native_TagSave      EQU NATIVE_STATE+34
Native_AssetMapped  EQU NATIVE_STATE+36
Native_Suspended    EQU NATIVE_STATE+37
Native_AssetIndex   EQU NATIVE_STATE+38
Native_IRQs         EQU NATIVE_STATE+40
Native_Before       EQU NATIVE_STATE+42
Native_After        EQU NATIVE_STATE+43
Native_Restored     EQU NATIVE_STATE+44
Native_Loops        EQU NATIVE_STATE+46
Native_Clock        EQU NATIVE_STATE+48 ; four bytes, exact rational accumulator
Native_Mapped       EQU NATIVE_STATE+52
Native_Canary       EQU NATIVE_STATE+54
Native_GuardTests   EQU NATIVE_STATE+56
Native_InterruptedSP EQU NATIVE_STATE+58
Native_ProbeReturnSP EQU NATIVE_STATE+60 ; synthetic probe only
Native_ProbeBefore EQU NATIVE_STATE+62
Native_ProbeAfter EQU NATIVE_STATE+63
Native_Pending EQU NATIVE_STATE+64 ; four-byte queued logical ticks
Native_VirtualIFF EQU NATIVE_STATE+68
Native_GameBusy EQU NATIVE_STATE+69
Native_Due EQU NATIVE_STATE+70 ; exact nonempty cache of four-byte Pending
Native_GameTicks EQU NATIVE_STATE+72 ; four-byte completed logical ticks
Native_Published EQU NATIVE_STATE+76
Native_PublishKind EQU NATIVE_STATE+77
Native_ClockMode EQU NATIVE_STATE+88
Native_ClockArmed EQU NATIVE_STATE+89
Native_ReadValue EQU NATIVE_STATE+90
Native_TransferSP EQU NATIVE_STATE+92
Native_TransferPublish EQU NATIVE_STATE+94
Native_WaitStart EQU NATIVE_STATE+96 ; four-byte logical HALT boundary
Native_FunctionIndex EQU NATIVE_STATE+104
Native_FunctionHL EQU NATIVE_STATE+106
Native_FunctionAF EQU NATIVE_STATE+108
Native_FunctionCases EQU NATIVE_STATE+110
Native_FunctionDone EQU NATIVE_STATE+114
Native_FunctionCarry EQU NATIVE_STATE+115
Native_ClockDelta EQU NATIVE_STATE+116 ; fine clock quantum, four bytes
Native_FineIndex EQU NATIVE_STATE+120
Native_FineStage EQU NATIVE_STATE+121
Native_FineStatus EQU NATIVE_STATE+122
Native_FineLine EQU NATIVE_STATE+123
Native_SoftwareSP EQU NATIVE_STATE+124
Native_SoftwareBusy EQU NATIVE_STATE+126
Native_FineProofDone EQU NATIVE_STATE+95
Native_FineProofRemainder EQU NATIVE_STATE+80
Native_FineProofTicks EQU NATIVE_STATE+84
Native_DeadlineLine EQU NATIVE_STATE+100
Native_DeadlineError EQU NATIVE_STATE+102

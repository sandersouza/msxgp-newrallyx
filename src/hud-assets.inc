; Generated original-derived HUD assets and bank contracts.
    IF INCREMENTAL_STAGE >= 9
patterns EQU $9800
    ELSE
patterns:
    INCBIN "sprite-patterns.bin"
    ENDIF
sprite_colors:
    INCBIN "sprite-colors.bin"
attributes_template:
    INCBIN "sprite-attributes.bin"
    IF INCREMENTAL_STAGE >= 9
radar_patterns EQU $9800+PATTERN_BYTES
    ELSE
radar_patterns:
    INCBIN "radar-patterns.bin"
    ENDIF
fuel_states EQU $8000
life_digits:
    INCBIN "life-digits.bin"
life_colors:
    defs 16,YELLOW|$20
    defs 16,BLACK|$20
    defs 16,WHITE|$20

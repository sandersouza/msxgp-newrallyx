"""Full-session workload adapters for the existing cycle profiler."""

def adapt(source,base):
    # Extend existing records; the same fields participate in the control check.
    source=source.replace(r'top_level"',r'top_level\tstart_vframe\tstart_vtick\tstart_s2\tend_vframe\tend_vtick\tend_s2"')
    source=source.replace('name start child ret sp owner\n','name start child ret sp owner vf vt s2\n')
    source=source.replace(r'[expr {{[llength $::stack]==1}}]"',
        r'[expr {{[llength $::stack]==1}}]\t$vf\t$vt\t$s2\t[machine_info VDP_frame_count]\t[machine_info VDP_cycle_in_frame]\t[debug read "VDP status regs" 2]"')
    source=source.replace('0 $ret $sp $::frame]',
        '0 $ret $sp $::frame [machine_info VDP_frame_count] [machine_info VDP_cycle_in_frame] [debug read "VDP status regs" 2]]')
    source=source.replace(r'active_end"',r'active_end\tenemy_positions\tr9\tr18"')
    source=source.replace(r'[active_gameplay]"',
        r'[active_gameplay]\t[binary encode hex [debug read_block memory 0xe088 96]]\t[debug read "VDP regs" 9]\t[debug read "VDP regs" 18]"')
    source=source.replace('else 120','else 360')
    source=source.replace('after time 30','after time 90')
    source=source.replace("workload='Integrated first-stage deterministic keyboard route; frames5..120'",
        "workload='Full session, keyboard coin/start and F5 to native round5 (RND4), layout1, three native enemies; frames5..360, fixed directional input'")
    source=source.replace('First-stage route; natural enemy population, HUD and audio enabled; no hardware validation.',
        'Full session; three native enemies, real sprite limits, HUD, point inscriptions and production PSG enabled. Short directional sample, not a complete course; no hardware validation.')
    source=source.replace('[debug read memory 0xc50b]<10',
        '[debug read memory 0xc50b]<10 && [debug read memory 0xc7d0]==0 && [debug read memory 0xe1b0]==5 && [debug read memory 0xe24e]==3')
    for name,purpose in {
        'GameSession_PhaseSelect':'Exact phase lookup, then offline ranking of seven inactive sets',
        'Game_ReadInput':'One hardware input sample per presented gameplay update',
        'GameSession_InputTick':'Preserve native60Hz corner-risk clock while reusing sampled input',
        'GameSession_SharedSprite':'Whole immutable car poses; unchanged private fallback for clips/other frames',
        'GameSession_FlagBlinkUpload':'One-byte S blink patch for an otherwise valid cached phase',
        'GameSession_Boundaries':'Boundary name preparation and theme mapping',
        'GameBoundary_Upload':'Boundary pattern/color transition transfer',
        'Session_SaveMotion':'Shared conditional movement snapshot for corner risk',
        'Session_RestoreMotion':'Conditional corner rollback; preserves the newly selected escape direction',
        'GameSession_ValidateMotion':'Shared native wall/contact validation and bounded rollback',
        'GameSession_SpecialFrame':'Physical-clock S/player flash latch',
        'GameSession_EnemyRocks':'Native stone occupancy lookup and rebound batch',
        'GameSession_EnemyRockProbe':'Original-boundary stone probe and optional recoil',
        'GameSession_RadarColor':'Actor radar color and packed-row priority',
        'GameSession_FlagNames':'Cached flag radar name stores',
        'GameSession_FlagUpload':'Lazy per-pattern-set flag radar upload',
        'GameSession_LabelNames':'Current player label names',
        'GameSession_LabelUpload':'Lazy current player label upload',
        'GameSession_PopupFrame':'Point inscription event state',
        'GameSession_PopupOverlay':'Point inscription terrain overlay',
        'GameSession_PopupUpload':'Lazy point inscription glyph upload',
        'GameSession_AfterFrame':'Demo and point inscription frame hooks',
    }.items():
        source=source.replace("    'clock_irq':'VBlank ISR body'",f"    {name!r}:{purpose!r},\n    'clock_irq':'VBlank ISR body'")
    source=source.replace('if not rows and name in (',"if not rows and name in ('GameSession_EnemyRockProbe','Session_RestoreMotion','GameSession_FlagBlinkUpload',")
    # Page0 also executes cached flag name programs. Reject their numeric aliases
    # while another RAM segment is selected. Page2 already has immutable bank guards.
    source=source.replace("    script = f'''", """    cold_bank=json.loads((BASE/'session-build.json').read_text())['banks']['SESSION_COLD_BANK']
    cold_prefix=measured_bytes[cold_bank*16384:cold_bank*16384+16]
    page2_setup+='set cold_prefix [binary format H* '+cold_prefix.hex()+']\\n'
    page2_setup+='set cold_entries {'+' '.join(n for n in ROUTINES if 0x1400<=syms[n]<0x2000)+'}\\n'
    script = f'''""")
    source=source.replace('proc enter {{name}} {{\n', '''proc enter {{name}} {{
        if {{$name in $::cold_entries && [debug read_block memory 0x1400 16] ne $::cold_prefix}} {{incr ::page2_rejected;return}}
    ''')
    autostart=r"""
    set full_profile_ready 0
    set full_phase boot
    set full_age 0
    proc full_poll {} {
     incr ::full_age
     set state [debug read memory 0xc7d0]
     set ready [debug read memory 0xc7dd]
     switch $::full_phase {
      boot {if {$state==1 && $ready} {keymatrixdown 0 32;set ::full_phase coin;set ::full_age 0}}
      coin {
       if {$::full_age==5} {keymatrixup 0 32}
       if {$::full_age>8 && $state==6 && $ready} {keymatrixdown 0 2;set ::full_phase start;set ::full_age 0}
      }
      start {
       if {$::full_age==5} {keymatrixup 0 2}
       if {$state==0 && [debug read memory 0xc00c]} {set ::full_phase advance;set ::full_age 0}
      }
      advance {
       if {$::full_age==10} {set ::full_round [debug read memory 0xe1b0];keymatrixdown 7 2}
       if {$::full_age==15} {keymatrixup 7 2}
       if {$::full_age>18 && $state==0 && [debug read memory 0xc00c] && [debug read memory 0xe1b0]>$::full_round} {
        if {[debug read memory 0xe1b0]==5} {
         if {[debug read memory 0xe24e]!=3} {error "Wrong enemy workload"}
         set ::full_profile_ready 1
         return
        }
        set ::full_age 0
       }
      }
     }
     after time 0.02 full_poll
    }
    after time 0.02 full_poll
    """
    source=source.replace("debug set_bp {syms['loop']} {{}} {{next_frame}}",
        "{autostart}\ndebug set_bp {syms['loop']} {{$::full_profile_ready}} {{next_frame}}")
    # Inject the Tcl string as a local of the inner profiler main().
    source=source.replace('    script = f\'\'\'', '    autostart='+repr(autostart)+'\n    script = f\'\'\'')
    return source

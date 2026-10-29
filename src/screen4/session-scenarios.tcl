# Keyboard drives all UI and debug advances. Controlled death/completion
# fixtures exercise cold/session ownership independently from collision timing.
set scenario @SCENARIO@
set saw_intro 0;set round_wait 0
proc request {name} {set ::capture_next $name}
proc next_phase {phase} {set ::phase $phase;set ::age 0}
proc u16 {at} {expr {[debug read memory $at]+256*[debug read memory [expr {$at+1}]]}}
proc step {} {
 incr ::age
 if {$::scenario eq "flags"} {
  set round_state [debug read memory 0xc724]
  if {$round_state==1} {
   if {![info exists ::clear_fuel]} {set ::clear_fuel [u16 0xe26a];set ::clear_start [machine_info time];set ::clear_score [debug read_block memory 0xe0a0 8]}
   if {[u16 0xe26a]!=$::clear_fuel || [debug read_block memory 0xe0a0 8] ne $::clear_score} {error "Fuel/score conversion began before clear melody ended"}
   if {[debug read memory 0xe9d3]==4 && ![info exists ::clear_heard]} {set ::clear_heard [machine_info time]}
   if {[info exists ::env(NRX_CLEAR_TEST_PAUSE)] && $::env(NRX_CLEAR_TEST_PAUSE)==1 && [info exists ::clear_heard]} {
    if {![info exists ::clear_pause_request] && [machine_info time]-$::clear_heard>.3} {keymatrixdown 4 32;set ::clear_pause_request 1}
    if {[debug read memory 0xc050] && ![info exists ::clear_pause_start]} {
     keymatrixup 4 32;set ::clear_pause_start [machine_info time]
     set ::clear_pause_cursor [debug read_block memory 0xe9d0 3];set ::clear_pause_timer [debug read memory 0xe24b]
    }
    if {[info exists ::clear_pause_start] && ![info exists ::clear_pause_resume]} {
     if {[debug read_block memory 0xe9d0 3] ne $::clear_pause_cursor || [debug read memory 0xe24b]!=$::clear_pause_timer} {error "Paused clear melody or settlement timer advanced"}
     if {[machine_info time]-$::clear_pause_start>.25} {keymatrixdown 4 32;set ::clear_pause_resume 1}
    }
    if {[info exists ::clear_pause_resume] && ![debug read memory 0xc050] && ![info exists ::clear_pause_done]} {
     keymatrixup 4 32;set ::clear_pause_done 1
     set f [open [file join $::out clear-pause.tsv] w];puts $f [expr {[machine_info time]-$::clear_pause_start}];close $f
    }
   }
  }
  if {$round_state==2 && ![info exists ::clear_bonus]} {
   if {![info exists ::clear_heard] || ([debug read memory 0xe9f5]&32) || [debug read memory 0xe9d3]==4} {error "Clear melody missing or cut by fuel conversion"}
   set ::clear_bonus [machine_info time]
   set f [open [file join $::out clear-order.tsv] w];puts $f "$::clear_start $::clear_heard $::clear_bonus $::clear_fuel";close $f
   if {$::clear_bonus-$::clear_start<1.65} {error "Clear cue completed too early"}
  }
 }

 if {$::scenario eq "controls"} {controls_step}
 set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {
  boot {if {$state==1 && $ready} {
   snapshot cast
   if {$::scenario eq "attract"} {next_phase attract_wait} else {keymatrixdown 0 32;next_phase coin}
  }}
  attract_wait {
   if {$state==0 && [debug read memory 0xc7ee] && [debug read memory 0xc00c]} {
    set ::demo_position [debug read_block memory 0xe070 3]
    request demo;next_phase attract_move
   }
  }
  attract_move {
   if {$::age==30} {
    if {$::demo_position eq [debug read_block memory 0xe070 3]} {error "Attract car did not move"}
    request demo-moving;keymatrixdown 0 32;next_phase attract_coin
   }
  }
  attract_coin {
   if {$::age==5} {keymatrixup 0 32}
   if {$state==6 && $ready} {
    if {[debug read memory 0xc7ee] || [debug read memory 0xc7d2]!=1} {error "Coin did not exit demo"}
    snapshot demo-select;keymatrixdown 0 2;next_phase start
   }
  }
  coin {
   if {$::age==5} {keymatrixup 0 32}
   if {$::age>8 && $state==6 && $ready} {
    if {[debug read memory 0xc7d2]!=1} {error "Coin1 count diverged"}
    snapshot select
    if {$::scenario eq "two-player"} {keymatrixdown 0 32;next_phase coin2} else {keymatrixdown 0 2;next_phase start}
   }
  }
  coin2 {
   if {$::age==5} {keymatrixup 0 32}
   if {$::age>8 && [debug read memory 0xc7d2]==2 && $ready} {snapshot select-two;keymatrixdown 0 4;next_phase start}
  }
  start {
   if {$::age==5} {keymatrixup 0 6}
   if {$state==5} {set ::saw_intro 1}
   if {$state==0 && [debug read memory 0xc00c] && $::presents>3} {
    if {!$::saw_intro} {error "Start cue missing"}
    request first-stage;next_phase initial
   }
  }
  initial {
   if {$::age==10} {
    if {$::scenario eq "controls"} {
     controls_begin
    } elseif {$::scenario eq "smoke"} {
     next_phase smoke_advance
    } elseif {$::scenario eq "radar"} {
     debug write memory 0xc050 1;set ::matrix_index 0;next_phase radar_matrix
    } elseif {$::scenario eq "flags"} {
     set ::flag_order {0 9 8 1 2 3 4 5 6 7}
     set ::flag_number 0;set ::flag_executed 0;next_phase flag_prepare
    } elseif {$::scenario eq "attract"} {
     next_phase finish
    } elseif {$::scenario eq "two-player"} {
     if {[debug read memory 0xc7eb]!=2 || [debug read memory 0xc7ec]!=0} {error "Two-player start state"}
     # Boundary fixture: completed death, with native life decrement applied.
     set lives [debug read memory 0xe00f];debug write memory 0xe00f [expr {$lives-1}]
     debug write memory 0xc490 2
     next_phase player2
    } else {
     keymatrixdown 7 1;next_phase mute
    }
   }
  }
  radar_matrix {}
  smoke_advance {
   if {$::age==3} {keymatrixdown 7 2;set ::before_round [debug read memory 0xe1b0]}
   if {$::age==8} {keymatrixup 7 2}
   if {$::age>10 && $state==0 && [debug read memory 0xc00c] && [debug read memory 0xe1b0]>$::before_round} {
    if {[debug read memory 0xe1b0]<5} {next_phase smoke_advance} else {
     set ::smoke_frames 0
     next_phase smoke_action
    }
   }
  }
  smoke_action {}
  player2 {
   if {$state==0 && [debug read memory 0xc7ec]==1 && [debug read memory 0xc00c]} {
    request player-two;set ::p2lives [debug read memory 0xe00f];next_phase player2_hold
   }
  }
  player2_hold {
   if {$::age==10} {
    debug write memory 0xe00f [expr {$::p2lives-1}]
    debug write memory 0xc490 2;next_phase player1_restored
   }
  }
  player1_restored {
   if {$state==0 && [debug read memory 0xc7ec]==0 && [debug read memory 0xc00c]} {
    request player-one-restored;next_phase finish
   }
  }
  flag_prepare {
   if {$::age==3} {set ::flag_executed 0;set ::flag_request [lindex $::flag_order $::flag_number];next_phase flag_wait}
  }
  flag_wait {
   if {$::flag_executed && [debug read memory 0xc50b]==$::flag_number+1} {
    if {[lindex $::flag_order $::flag_number]==9 && !([debug read memory 0xe023]&1)} {error "Special flag multiplier absent"}
    if {$::flag_number in {3 4} && [debug read memory 0xe00f]!=$::bonus_before+1} {error "Native20k/80k bonus life absent"}
    request captured-flag-[expr {$::flag_number+1}]
    next_phase flag_hold
   }
  }
  flag_hold {
   if {$::age>8 && ![debug read memory 0xc5b0]} {
    incr ::flag_number
    if {$::flag_number<10} {next_phase flag_prepare} else {next_phase flag_completion}
   }
  }
  flag_completion {
   if {$state==0 && [debug read memory 0xe1b0]==3 && [debug read memory 0xc00c]} {
    if {[debug read memory 0xc50b]!=0} {error "New round did not reset flags"}
    request after-ten-flags;next_phase finish
   }
  }
  mute {
   if {$::age==5} {keymatrixup 7 1}
   if {$::age==10} {
    if {![debug read memory 0xd150]} {error "F4 did not mute"}
    foreach reg {8 9 10} {if {[debug read {PSG regs} $reg]} {error "Muted PSG audible"}}
    keymatrixdown 7 1;next_phase unmute
   }
  }
  unmute {
   if {$::age==5} {keymatrixup 7 1}
   if {$::age==10} {
    if {[debug read memory 0xd150]} {error "F4 did not unmute"}
    keymatrixdown 4 32;next_phase pause
   }
  }
  pause {
   if {$::age==5} {keymatrixup 4 32}
   if {$::age==10} {
    if {![debug read memory 0xc050]} {error "P did not pause"}
    set ::pause_position [debug read_block memory 0xe068 24]
    set ::pause_music [debug read_block memory 0xe9d0 3]
    request paused
   }
   if {$::age==25} {
    if {$::pause_position ne [debug read_block memory 0xe068 24] || $::pause_music ne [debug read_block memory 0xe9d0 3]} {error "Paused motion/music advanced"}
    foreach reg {8 9 10} {if {[debug read {PSG regs} $reg]} {error "Paused PSG audible"}}
    keymatrixdown 4 32;next_phase resume
   }
  }
  resume {
   if {$::age==5} {keymatrixup 4 32}
   if {$::age==10} {
    if {[debug read memory 0xc050]} {error "Pause did not release"}
    keymatrixdown 7 2;set ::before_round [debug read memory 0xe1b0];next_phase debug
   }
  }
  debug {
   if {$::age==5} {keymatrixup 7 2}
   if {$::age>8 && $state==0 && [debug read memory 0xc00c] && [debug read memory 0xe1b0]==$::before_round+1} {
    request second-stage;next_phase complete
   }
  }
  complete {
   if {$::age==10} {
    # Completion boundary fixture, without fabricating flag/score results.
    debug write memory 0xc724 3;next_phase challenge
   }
  }
  challenge {
   if {$state==7 && $ready && ![info exists ::challenge_seen]} {set ::challenge_seen 1;snapshot challenge}
   if {$state==7 && $ready && [info exists ::challenge_reveal_base]} {
    set unit [expr {([u16 0xdfe4]-$::challenge_reveal_base)/7}]
    if {$unit>=5 && ![info exists ::typing_seen]} {set ::typing_seen 1;snapshot challenge-typing}
    if {$unit>=23 && ![info exists ::item_seen]} {set ::item_seen 1;snapshot challenge-items}
    if {[debug read memory 0xdfe7] && ![info exists ::reveal_complete]} {set ::reveal_complete 1;snapshot challenge-complete}
   }
   if {[info exists ::challenge_seen] && $state==0 && [debug read memory 0xc00c]} {
    if {[u16 0xe025] || [u16 0xe029]} {error "Challenge resume activated parked cars"}
    if {[info exists ::challenge_reveal_base] && (![info exists ::typing_seen] || ![info exists ::item_seen] || ![info exists ::reveal_complete])} {error "Challenge reveal skipped its staged content"}
    next_phase challenge_music
   }
  }
  challenge_music {
   if {$::age==15} {
    if {[debug read memory 0xe9d3]!=2 || !([debug read {PSG regs} 8] || [debug read {PSG regs} 9] || [debug read {PSG regs} 10])} {error "Challenge gameplay music absent"}
    set speed [u16 0xe069];if {$speed>=32768} {set speed [expr {65536-$speed}]}
    if {[u16 0xe025] || [u16 0xe029] || $speed<=512 || $speed>[u16 0xe027]} {error "Parked challenge did not retain native faster player motion"}
    if {[debug read memory 0xdfe4] || [debug read memory 0xdfe5]} {error "UI reveal leaked a gameplay popup"}
    request challenging-stage;next_phase layouts
   }
  }
  layouts {
   if {$::age==10} {
    keymatrixdown 7 2;set ::before_round [debug read memory 0xe1b0];next_phase layout_wait
   }
  }
  layout_wait {
   if {$::age==5} {keymatrixup 7 2}
   if {$::age>8 && $state==0 && [debug read memory 0xc00c] && [debug read memory 0xe1b0]==$::before_round+1} {
    request round-[debug read memory 0xe1b0]-layout-[debug read memory 0xdfc9]
    if {[debug read memory 0xe1b0]<14} {next_phase layouts} else {next_phase gameover}
   }
  }
  gameover {
   if {$::age==10} {debug write memory 0xe00f 0;debug write memory 0xc490 2;next_phase over}
  }
  over {
   if {$state==2 && $ready && ![info exists ::over_seen]} {set ::over_seen 1;snapshot game-over}
   if {$state==2 && [debug read memory 0xe9d3]==5} {set ::over_song_started 1}
   if {[info exists ::over_seen] && $state==1 && $ready} {
    if {![info exists ::over_song_started] || [debug read memory 0xe9f5]&4 || [debug read memory 0xe9d3]==5} {error "Game-over cue cut before its native end"}
    snapshot cast-return;next_phase finish
   }
  }
  finish {
   if {$::age==12} {catch {record stop};close $::events;exit 0}
  }
 }
 after time 0.02 poll
}
proc poll {} {if {[catch step problem]} {puts stderr "$::phase: $problem";exit 2}}
after time 180 {puts stderr "Integration timeout phase=$::phase PC=[reg PC] state=[debug read memory 0xc7d0] round=[debug read memory 0xe1b0]";exit 3}
after time 0.02 poll

# Actual keyboard edges. Controlled death hooks isolate car/rock policy.
proc controls_begin {} {
 set ::initial_round [debug read memory 0xe1b0]
 set ::initial_invulnerable [debug read memory 0xc0ee]
 keymatrixdown 1 8
 next_phase equal_on
}
proc controls_step {} {
 switch $::phase {
 equal_on {
  if {$::age==12} {
   if {$::test_enabled && ![debug read memory 0xc0ee]} {error "Equals did not enable invulnerability"}
   if {!$::test_enabled && [debug read memory 0xc0ee]!=$::initial_invulnerable} {error "Normal ROM reacted to equals"}
  }
  if {$::age==24} {
   if {$::test_enabled && [debug read memory 0xc0ee]!=1} {error "Held equals repeated"}
   keymatrixup 1 8
   set ::death_request [list rock [expr {!$::test_enabled}]]
   next_phase contact_rock
  }
 }
 contact_rock {
  if {[info exists ::death_checked]} {unset ::death_checked;set ::death_request [list enemy [expr {!$::test_enabled}]];next_phase contact_enemy}
 }
 contact_enemy {
  if {[info exists ::death_checked]} {unset ::death_checked;keymatrixdown 1 4;keymatrixdown 6 1;next_phase jis_equal}
 }
 jis_equal {
  if {$::age==12} {
   if {$::test_enabled && [debug read memory 0xc0ee]} {error "Japanese equals did not disable invulnerability"}
   keymatrixup 1 4;keymatrixup 6 1
   set ::death_request [list rock 1];next_phase contact_enabled
  }
 }
 contact_enabled {
  if {[info exists ::death_checked]} {unset ::death_checked;keymatrixdown 7 128;next_phase return_held}
 }
 return_held {
  if {$::age==45} {
   set expected [expr {$::initial_round+$::test_enabled}]
   if {[debug read memory 0xe1b0]!=$expected} {error "Return did not advance exactly once while held"}
   keymatrixup 7 128;set ::released_at $::presents;next_phase return_release
  }
 }
 return_release {
  if {$::age>=10 && [debug read memory 0xc00c] && $::presents>$::released_at+2} {keymatrixdown 7 128;set ::again_at $::presents;next_phase return_again}
 }
 return_again {
  if {$::age>=45 && [debug read memory 0xc00c] && $::presents>$::again_at+3} {
   set expected [expr {$::initial_round+2*$::test_enabled}]
   if {$::test_enabled && [debug read memory 0xc7d0]==7} {return}
   if {[debug read memory 0xe1b0]!=$expected} {error "Second Return edge failed round=[debug read memory 0xe1b0] state=[debug read memory 0xc7d0] death=[debug read memory 0xc490]"}
   keymatrixup 7 128;request controls-complete;next_phase finish
  }
 }
 }
}

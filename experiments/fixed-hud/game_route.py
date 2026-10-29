"""Keyboard-only first-stage navigation using the existing native maze oracle.

Only keyboard inputs are changed. Native cars, collision, fuel, flags and lives
remain authoritative; no counter, position or enemy-count injection is used.
"""
from scripts.msx.completion_route_verify import navigation
from scripts.msx.flags import records
from game_build import inputs


def setup(root,out,allow_gameover=False):
    program,video,cells,pairs,assets=inputs(root)
    (out/'navigation.bin').write_bytes(navigation(cells,records(video,cells)))
    script=r'''
set navfile [open [file join $out navigation.bin] rb]
set route_nav [read $navfile];close $navfile
set route_tx 396
set route_ty 1236
set route_mask 0
set route_done 0
set route_stopped 0
set route_seen 0
set route_death 0
set route_fire 0
set route_capture_frame -1
set route_capture_name event
proc signed {a} {set v [debug read memory $a];expr {$v>127?$v-256:$v}}
proc route_keys {mask smoke} {
    keymatrixup 8 255
    if {$mask} {keymatrixdown 8 $mask}
    if {$smoke} {keymatrixdown 8 1}
}
proc route_choose {x y} {
    set goal -1
    for {set i 0} {$i<10} {incr i} {
        if {[debug read memory [expr {0xc501+$i}]]} {set goal $i;break}
    }
    if {$goal<0} {set ::route_mask 0;return}
    binary scan [string index $::route_nav [expr {$goal*1792+$y*32+$x}]] cu mask
    if {$mask==255 || !$mask} {error "Invalid active-flag navigation cell $x,$y"}
    set ::route_mask $mask
    set ::route_tx [expr {36+24*($x+($mask==128)-($mask==16))}]
    set ::route_ty [expr {36+24*($y+($mask==64)-($mask==32))}]
}
proc route_step {} {
    if {$::n==$::route_capture_frame} {save $::route_capture_name}
    set flags [debug read memory 0xc50b]
    if {$flags!=$::route_seen} {
        set ::route_seen $flags
        save flag-$flags
    }
    set death [debug read memory 0xc490]
    if {$death!=$::route_death} {
        if {$death==1} {save death-$::n;set ::route_capture_frame [expr {$::n+2}];set ::route_capture_name explosion-$::n}
        set ::route_death $death
        if {!$death} {set ::route_tx 396;set ::route_ty 1236;set ::route_mask 0}
    }
    set state [debug read memory 0xc040]
    if {$state==1} {GAMEOVER_ACTION}
    if {$state==2} {
        if {$flags!=10} {error "Completion without all flags"}
        incr ::route_stopped
        route_keys 0 0
        if {$::route_stopped==3} {save completed}
        if {$::route_stopped>=12} {set ::route_done 1}
        return
    }
    if {$death || [debug read memory 0xc724]} {route_keys 0 0;return}
    set x [word 0xc405];set y [word 0xc407]
    if {abs($::route_tx-$x)<=6 && abs($::route_ty-$y)<=6} {
        route_choose [expr {int(($::route_tx-36)/24)}] [expr {int(($::route_ty-36)/24)}]
    }
    set facing [debug read memory 0xe077]
    for {set e 0} {$e<[debug read memory 0xe24e]} {incr e} {
        set base [expr {0xe088+32*$e}]
        set ex [expr {36+24*[debug read memory [expr {$base+8}]]+[signed [expr {$base+5}]]}]
        set ey [expr {36+24*[debug read memory [expr {$base+10}]]-[signed [expr {$base+7}]]}]
        set dx [expr {$ex-$x}];set dy [expr {$ey-$y}]
        set behind [expr {($facing==240 && $dy>24 && $dy<96 && abs($dx)<12) || ($facing==242 && $dy< -24 && $dy> -96 && abs($dx)<12) || ($facing==252 && $dx< -24 && $dx> -96 && abs($dy)<12) || ($facing==253 && $dx>24 && $dx<96 && abs($dy)<12)}]
        if {!$::route_fire && $behind} {set ::route_fire 4}
    }
    route_keys $::route_mask [expr {$::route_fire>0}]
    if {$::route_fire} {incr ::route_fire -1}
}
'''
    action='save game-over;route_keys 0 0;set ::route_done 1;return' if allow_gameover else 'error "Keyboard route exhausted native lives"'
    return script.replace('GAMEOVER_ACTION',action)

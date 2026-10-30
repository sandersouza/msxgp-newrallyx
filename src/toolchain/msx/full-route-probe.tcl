set phase boot
set age 0
set frames 0
set current_round -1
set current_deaths -1
set tx 396
set ty 1236
set mask 0
set fire 0
set shots 0
set skip_headers 0
set events [open [file join $out events.tsv] w]
set headers [open [file join $out headers.tsv] w]
set cadence [open [file join $out cadence.tsv] w]
proc u16 {a} {expr {[debug read memory $a]+256*[debug read memory [expr {$a+1}]]}}
proc signed {a} {set n [debug read memory $a];expr {$n<128?$n:$n-256}}
proc keys {mask fire} {
    keymatrixup 8 255
    keymatrixup 6 2
    if {$mask} {keymatrixdown 8 $mask}
    if {$fire} {keymatrixdown 6 2}
}
proc byte {data at} {binary scan [string index $data $at] cu v;return $v}
proc prepare_navigation {} {
    catch {unset ::nav}
    catch {unset ::distance}
    set ::blocked {}
    set p [u16 0xe996]
    for {set i 0} {$i<[debug read memory 0xe251]} {incr i} {
        dict set ::blocked [expr {[u16 [expr {$p+$i*2}]]-0x9800}] 1
    }
    set ::board $::boards([expr {[debug read memory 0xe28f]&3}])
    set ::flag_table [u16 0xe992]
    set ::tx [expr {36+24*[debug read memory 0xe070]}]
    set ::ty [expr {36+24*[debug read memory 0xe072]}]
    set ::mask 0
    set ::fire 0
}
proc navigate_static {x y} {
    set here [expr {$y*32+$x}]
    set best -1
    set best_distance 100000
    for {set id 0} {$id<10} {incr id} {
        if {![debug read memory [expr {0xc501+$id}]]} {continue}
        if {![info exists ::nav($id)]} {
            set goal [expr {[u16 [expr {$::flag_table+$id*2}]]-0x9800}]
            set path [lrepeat 1792 255]
            set distances [lrepeat 1792 100000]
            lset path $goal 0
            lset distances $goal 0
            set queue [list $goal]
            for {set head 0} {$head<[llength $queue]} {incr head} {
                set cell [lindex $queue $head]
                set cx [expr {$cell%32}];set cy [expr {$cell/32}]
                foreach {dx dy key} {0 1 32 -1 0 128 0 -1 64 1 0 16} {
                    set nx [expr {$cx+$dx}];set ny [expr {$cy+$dy}];set n [expr {$ny*32+$nx}]
                    if {$nx<0 || $nx>=32 || $ny<0 || $ny>=56 || [dict exists $::blocked $n]} {continue}
                    if {[lindex $path $n]!=255 || ([byte $::board $n]&248)} {continue}
                    lset path $n $key
                    lset distances $n [expr {[lindex $distances $cell]+1}]
                    lappend queue $n
                }
            }
            set ::nav($id) $path
            set ::distance($id) $distances
        }
        set d [lindex $::distance($id) $here]
        if {$d<$best_distance} {set best $id;set best_distance $d}
    }
    if {$best<0} {set ::mask 0;return}
    set m [lindex $::nav($best) $here]
    if {$m==255} {error "Active flag is unreachable while avoiding original rocks"}
    if {$m==0} {return}
    set ::mask $m
    set ::tx [expr {36+24*($x+($m==128)-($m==16))}]
    set ::ty [expr {36+24*($y+($m==64)-($m==32))}]
}
# Forward BFS is recomputed only at cell targets. It changes host input planning,
# not guest memory, enemy behavior or game rules.
proc navigate {x y} {
    if {!$::avoid_enemies} {navigate_static $x $y;return}
    set here [expr {$y*32+$x}]
    set goals {}
    for {set id 0} {$id<10} {incr id} {
        if {[debug read memory [expr {0xc501+$id}]]} {
            dict set goals [expr {[u16 [expr {$::flag_table+$id*2}]]-0x9800}] 1
        }
    }
    if {[dict exists $goals $here]} {return}
    set blocked $::blocked
    for {set i 0} {$i<[debug read memory 0xe24e]} {incr i} {
        set cx [debug read memory [expr {0xe090+$i*32}]]
        set cy [debug read memory [expr {0xe092+$i*32}]]
        if {$cy>=56} {continue}
        for {set dy -1} {$dy<=1} {incr dy} {
            for {set dx -1} {$dx<=1} {incr dx} {
                set nx [expr {$cx+$dx}];set ny [expr {$cy+$dy}]
                if {$nx>=0 && $nx<32 && $ny>=0 && $ny<56} {dict set blocked [expr {$ny*32+$nx}] 1}
            }
        }
    }
    set first [lrepeat 1792 0];lset first $here 255
    set queue [list $here];set move 0
    for {set head 0} {$head<[llength $queue] && !$move} {incr head} {
        set cell [lindex $queue $head];set cx [expr {$cell%32}];set cy [expr {$cell/32}]
        foreach {dx dy key} {0 -1 32 1 0 128 0 1 64 -1 0 16} {
            set nx [expr {$cx+$dx}];set ny [expr {$cy+$dy}];set n [expr {$ny*32+$nx}]
            if {$nx<0 || $nx>=32 || $ny<0 || $ny>=56 || [dict exists $blocked $n]} {continue}
            if {[lindex $first $n] || ([byte $::board $n]&248)} {continue}
            set step [expr {$cell==$here?$key:[lindex $first $cell]}]
            lset first $n $step;lappend queue $n
            if {[dict exists $goals $n]} {set move $step;break}
        }
    }
    if {!$move} {navigate_static $x $y;return}
    set ::mask $move
    set ::tx [expr {36+24*($x+($move==128)-($move==16))}]
    set ::ty [expr {36+24*($y+($move==64)-($move==32))}]
}
proc snapshot {} {
    set n [incr ::shots]
    foreach {ext data} [list state [debug read_block memory 0xc000 12288] vram [debug read_block VRAM 0 131072]] {
        set f [open [file join $::out "$n.$ext"] wb];puts -nonewline $f $data;close $f
    }
}
proc route_frame {} {
    if {$::phase ne "game"} {return}
    incr ::frames
    if {$::skip_headers} {incr ::skip_headers -1}
    set state [debug read memory 0xc7d0]
    set r [debug read memory 0xe1b0]
    set death [debug read memory 0xc490]
    puts $::cadence "[machine_info time] $r $death [debug read memory 0xc724] [u16 0xc440] [u16 0xc71d] [debug read memory 0xe24e] [debug read memory 0xc472] @CLOCK_DUE@ @CAMERA_BLOCKED@ @CLOCK_DROPPED@ [debug read memory 0xc00a] $state"
    puts $::events "$::frames $r [debug read memory 0xc50b] [debug read memory 0xe00f] $death [u16 0xe26a] [u16 0xc711] [u16 0xc71d] [u16 0xc440] [debug read memory 0xe28b] [debug read memory 0xe289] [debug read memory 0xe24e] [debug read memory 0xc472]"
    if {$::frames>40000 || $state==2} {
        snapshot
        error "Natural route ended before target rounds: state=$state round=$r flags=[debug read memory 0xc50b]"
    }
    if {$r!=$::current_round} {
        set ::current_round $r
        prepare_navigation
        set ::skip_headers 4
        snapshot
        if {$r>$::rounds+1} {close $::events;close $::headers;exit 0}
    }
    if {$death} {keys 0 0;set ::mask 0;return}
    set deaths [debug read memory 0xc5c2]
    if {$deaths!=$::current_deaths} {set ::current_deaths $deaths;prepare_navigation}
    if {[debug read memory 0xc724] || [debug read memory 0xc009]} {keys 0 0;return}
    # Plan the next input from the current native position. The visible camera
    # deliberately presents the preceding simulation snapshot.
    set x [u16 0xc450];set y [u16 0xc452]
    if {abs($::tx-$x)<=$::steering_margin && abs($::ty-$y)<=$::steering_margin} {
        navigate [expr {int(($::tx-36)/24)}] [expr {int(($::ty-36)/24)}]
    }
    set facing [debug read memory 0xe077]
    set behind 0
    for {set i 0} {$i<7} {incr i} {
        set p [expr {0xe088+$i*32}]
        set dx [expr {36+24*[debug read memory [expr {$p+8}]]+[signed [expr {$p+5}]]-$x}]
        set dy [expr {36+24*[debug read memory [expr {$p+10}]]-[signed [expr {$p+7}]]-$y}]
        if {[u16 [expr {0xe089+$i*32}]] && ![debug read memory [expr {0xe09d+$i*32}]] &&
            (($facing==240 && $dy>24 && $dy<96 && abs($dx)<12) ||
             ($facing==242 && $dy< -24 && $dy> -96 && abs($dx)<12) ||
             ($facing==252 && $dx< -24 && $dx> -96 && abs($dy)<12) ||
             ($facing==253 && $dx>24 && $dx<96 && abs($dy)<12))} {set behind 1}
    }
    if {!$::fire && $behind} {set ::fire 8}
    keys $::mask [expr {$::fire>0}]
    if {$::fire} {incr ::fire -1}
    if {$::frames%240==0 && ![debug read memory 0xc50e] && ![debug read memory 0xc494] && ![debug read memory 0xc70e]} {snapshot}
}
proc ui_poll {} {
    incr ::age
    set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
    switch $::phase {
        boot {if {$state==1 && $ready} {keymatrixdown 0 32;set ::phase coin;set ::age 0}}
        coin {if {$::age==4} {keymatrixup 0 32;set ::phase release;set ::age 0}}
        release {if {$::age==4} {keymatrixdown 0 2;set ::phase start;set ::age 0}}
        start {if {$::age==4} {keymatrixup 0 2};if {$state==0} {set ::phase game;set ::skip_headers 4}}
    }
    if {$::phase ne "game"} {after time 0.02 ui_poll}
}
debug set_watchpoint write_mem 0xc000 {$wp_last_value==2} {
    if {[catch {route_frame} p]} {puts stderr $p;exit 2}
}
debug set_watchpoint write_mem 0xc03c {$::phase eq "game" && !$::skip_headers && $wp_last_value in {2 3 4}} {
    puts $::headers "$wp_last_value $::frames pc-[u16 [expr {[reg SP]+4}]] [machine_info time] 0 0"
}
debug set_bp @SHOW_SCENE@ {$::phase eq "game"} {
    puts $::headers "0 $::frames reload [machine_info time] 1 0";set ::skip_headers 4
}
after time 0.02 ui_poll

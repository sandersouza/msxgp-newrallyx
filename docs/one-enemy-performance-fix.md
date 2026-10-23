# One enemy: use the blank interval after preparing presentation

The first enemy logic-only candidate passes 2,643 exact original state/contact
cases but fails the unchanged gameplay refresh gate at 23.999 ms. No enemy
graphics or additional population is enabled while this regression is open.

Read-only live profiling identifies enemy cleanup at 2,151 median / 2,330 maximum
elapsed clocks and the AI/camera/registration group at 4,062 / 6,252 clocks.
Pure original AI within that group measures 2,261 / 4,270 clocks. Tile copies
measure 997 median clocks; actual VDP command execution is 782 median / 864
maximum clocks. Wall probes are only 226 median / 340 maximum clocks. These
elapsed clocks include interrupt/VDP waits where applicable; do not attribute
the whole regression to wall decoding or start rewriting original AI blindly.

The existing loop prepares the current camera and SAT, then waits for the maze
split before running every logical tick. VBlank-to-split measures 6.481 ms at
the median. The prepared presentation is already stable during that interval;
the pure-RAM selected logic can use it without changing scroll/SAT fields.

Run the first logical tick after current presentation preparation, with raster
interrupts enabled, before waiting for the split. Keep its resulting position
pending for the following presentation. When 50 Hz resampling requires a second
16.5 ms tick, run that tick after the split. Keep original ordering within each
tick, the same input sample, resampling accumulator and one/two tick count.
The current frame's camera, SAT and drawn-facing fields remain unchanged.
If logic extends beyond the split, the ISR still consumes the already prepared
presentation. No CPU overclock, skipped tick or timing-tolerance change.

Queue the flag's HUD setter until after HUD drawing, retaining its former
publication phase. Otherwise an early collection could combine the dirty radar
and nine terrain tiles in a frame that previously separated those costs. The
logical flag event remains immediate; the source-compatible HUD update remains
one presentation behind. Fuel/score/life publishers already run in the body.

The first split-tick candidate v5 reduces the maximum to 22.175 ms; every
remaining late interval belongs to a two-tick work frame. Reserve seven guard
copies after visible dirty jobs/scoring on those frames, matching the measured
body enemy cost. Keep pending guard work, exact tick count and the existing
cache halo. Ordinary one-tick frames retain their previous budget. This does
not postpone a partially drawn collected flag or explosion to make timings pass.

Rerun exact component state, the standard 1,600-state driving/cache/timing proof,
then full RGB and focused collision/life tests when enemy presentation is added.
Keep accepted stage 07 immutable and verify it still reproduces its original ROM.

## Presentation regression and measured scheduling

Logic-only v6 passes 1,600 cache/player states and 39 full RGB captures with
20.232 ms maximum main interval. Adding exact two-plane enemy presentation and
the moving radar point raises that interval to 21.398 ms. The 1,928-case executed
presentation matrix verifies every facing, both horizontal clipping boundaries,
cache eviction and SAT-Y=216. It exposed a low-byte-only decrement at Y=0; the
adapter now decrements the complete signed coordinate for its declared bias.

Fixed additional guard-copy reservations improve timing but starve prefetch:
48-column candidates fail full-cache checks at frames 343 and 523. A temporary
44-column candidate passes the common cache route but fails the natural enemy
route. These candidates are rejected. The current candidate restores the
48-column cache and eight-tile horizontal guard; visible geometry never changed.

Use an additional line interrupt at maze scanline 196 to close invisible guard
work, with sixteen scanlines remaining before VBlank. Check its latched flag
between indivisible VDP transactions. Clear it only when beginning a new host
frame, never during VBlank: a late frame must not accidentally acquire a fresh
budget. Raster handlers retain current scroll and sprite publication ownership.
Visible flag/death repairs precede guard work; pending guard jobs persist.

Collected-flag cleanup now uses three 24x8 copies instead of nine 8x8 copies.
Three exact copies of the original empty tile occupy spare positions in the
existing 2 KiB command atlas; neither VRAM allocation nor sprites increase.
Split each row at a physical 256-pixel page edge. All 512 executed horizontal,
vertical-wrap and budget-1/9 canary cases pass against original empty pixels.
Measured dirty work drops from 18,700 to 6,808 elapsed clocks on the worst frame.

Candidate v9 passes the natural keyboard enemy collision/restart route with
1,138 exact cache states and 28 full RGB captures. The remaining common-route
stress failure is 21.123 ms when two logical ticks, fuel-gauge publication,
collected-flag cleanup and a new score publication coincide. Start a pending
score transaction before the footer or retain it for the following refresh,
as the previous bounded job scheduler already did when its budget was exhausted.
Collection state and visible terrain remain immediate. V10 still starts just
before the footer in this stress frame and fails at 21.142 ms. V11 also retains
a new flag-score transaction across an active two-tick refresh, draining on the
next ordinary refresh; paused/dead states can drain immediately.

## Pre-header cost and full-border graphics

Capturing every dynamic left clip exposes faults that periodic images missed.
Copy-and-mask unrolling reduces the worst presentation component from 9,804 to
7,822 clocks but still delays the first maze rows. Precompute all twelve facings
and sixteen horizontal clips into 12 KiB of one extra ROM bank; its final 4 KiB
hold all 64 radar-point phases. Transfer the same masks directly, without pixel
generation in the pre-header interval. The cartridge remains 1 MiB, now 54 banks;
RAM/VRAM allocation and sprite count do not increase.

Keep interrupts enabled through the private pending-coordinate calculation at
the end of each native tick. The ISR reads prepared scroll/SAT, not pending
coordinates. The former DI interval could delay the maze split even without HUD.
Retain the baseline header dispatch cost and VDP register order. An attempted
earlier R23 write makes maze pixels appear in the separator and is rejected.

The remaining small first-row difference is enemy pixels at screen y11, where
sprite enable/prefetch crosses the header boundary. Declare the sprite viewport
at y12 while retaining the bitmap viewport at y11. Clear just that source mask
row in the cached two-plane pattern; all other pixels and world/collision
coordinates remain unchanged. The complete image is still compared, including
the underlying maze row. The upload ending at $1ffff advances R14: reset it
explicitly before four clear-byte writes. The executed presentation proof also
checks that the entire 64 KiB maze cache remains unchanged.

Finally, a 24x8 command can still be busy during the footer deadline. Service
interrupts between status polls, then reselect status 2 because the ISR owns R15.
No control-port latch remains open across the interrupt. This fixes a 21.050 ms
footer interval without shortening the original simulation or relaxing tolerance.

## Accepted v24 results

Both HUD modes pass the standard 1,600-state movement/cache control with every
dynamic left clip captured: 38 full RGB images with HUD, 36 without. Main maxima
are 20.100599 / 19.937730 ms; footer maxima are 20.491431 / 20.307888 ms. VDP command
counts peak at 26 / 30 because real deadline scheduling uses available time to
finish invisible guard work instead of charging pessimistic fixed reservations.

Both complete one-enemy keyboard runs pass 1,138 cache states and 28 full RGB,
including pursuit/contact, pause, explosion, retained score/flags, restart and
Home. Main maxima are 20.049755 / 19.937730 ms; footer maxima are 20.510149 /
20.334707 ms. Continuous line occupancy peaks at eight/four, with 21 SAT slots
reserved and 11 free. The original enemy oracle passes 2,643 cases, presentation
passes 1,928, grouped flag repair passes 512, and all 302 tests pass. The stage 07
ROM still reproduces its accepted SHA-256. The 48-column cache and eight-tile
guard remain; no viewport reduction is accepted from the failed candidates.

The earlier v19/v20 style experiment changed only graphic resources: motion,
events, timing, ticks, contacts, occupancy and reload files were byte-identical.
The user subsequently clarified that the score header must remain black. V25
restores it and adds a square white radar border, since a solid blue radar fill
would require another layer or work during scrolling. V24/v25 symbols and
executable bytes are identical; only resident radar patterns and HUD resource
banks differ. Full-border checking includes the four shifted header pixels
exposed to the left of the normal 256-pixel canvas.

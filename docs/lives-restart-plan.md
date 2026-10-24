# Stage 07: lives and restart

Stage 06 is accepted before this component is enabled. Keep its immutable HUD
on/off cartridges available. Do not integrate enemies until stage 07 passes.

Use the original active-game life decrement at `$18da..$18e7`, returning before
the two-player dispatcher. One contact starts one death; repeated contact during
the hold must not decrement again. The native life count includes the driven
car; the HUD shows `max(count-1,0)`, capped only for presentation. Source bonus
life accounting from stage 05 continues to own increases and award bits.

Non-final deaths retain the verified 120-tick hold. The final source wait starts
its incrementing byte at `$a0` and returns on zero: **96 logical ticks**, not 160.
Verify this source loop independently. Pause freezes both timers.

Restart the same round after the effect is restored. Retain current/high score,
bonus-life award bits, collected count and cleared flag addresses. Selected
original `$0c6c` resets the car, special multiplier and current-life flag ordinal;
therefore the next surviving flag is worth 100 base points, independent of the
stage's collected count. Refill fuel to 60 whole units through the selected
`$08e7..$0907` RAM initialization; restore first-stage movement parameters and
the explicit fresh active fuel clock. Source difficulty/AI dispatch remains a
later component, never start the complete arcade loop.

Reuse the bounded scene reload for the camera teleport; preserve gameplay RAM
and host collection state while rebuilding the cache/HUD. Report reload latency
separately from ordinary driving, as already done for Home. A zero life count
keeps the run stopped; Home resets the stage fixture. Credit/start/game-over
presentation belongs to stage 11.

Verify an independent original decrement/restart/timer oracle; keyboard deaths
through all three lives, pause and a score/flag collected before death; actual
HUD lives, persistent cleared bitmap/radar flags and the next flag's reset ordinal;
full RGB/cache edges and measured steady refreshes in both HUD modes. Keep the
standard movement/fuel/collection regressions. Stop and fix the first regression
before proceeding to stage 08.

## Accepted evidence

V4 contains the same ROM bytes as the V2/V3 proof candidates. The independent
original oracle passes 48 cases: exact decrement, 120/96-tick source waits,
refill, native car/parameter initialization, retained collected count, next-flag
ordinal reset, score/high-score and the 20k bonus-life boundary. RAM-only core
maximums: loss 257 cycles, hold 179, restart 3,049; score cases up to 20,896.

Both HUD modes pass a real keyboard route through three rock deaths. A special
flag before death awards 200; the next normal flag after restart awards 100,
preserving 300 through the final life. Collected bitmap/radar flags persist.
The route checks 1,289 complete visible caches, 19 full RGB images, 40 paused
refreshes, movement lock throughout 120/120/96 ticks, stopped zero-life controls,
and Home reset. Source ROMs/BIOS are unchanged; no gameplay RAM writes are used.

Two gameplay reloads take 714.323/713.909 ms with HUD, 668.719 ms without. These
explicit transition events and two warm-up frames are excluded from ordinary
refresh statistics, including any suppressed footer interrupts. Life-route main
maximum is 19.938 ms; footer 20.299 ms with HUD / 20.248 ms without. Standard
1,600-state routes pass 37/39 RGB, main maximum 20.304 ms. The existing complete
ten-flag route passes 2,786 cache states / 12 RGB. GPU maximum remains 19. Full
suite: 295 tests pass; developer default-flag checks are rerun after promotion.

The new route caught a verification error at camera X=571: the old death-image
oracle indexed past the 816-pixel world into the next row instead of repeating
the flower margin. Actual VRAM and RGB agreed. The corrected padded oracle and
a synthetic edge regression fix this; no renderer or viewport change was made.
Old comparison images remain labelled in the local evidence's diagnostics folder.

Evidence: `references/build/issue11-r07-v2-lives-check`, both
`issue11-r07-{no-hud-,}v3-life-route-check` and `v3-player-check`, and
`issue11-r07-v3-all-flags-check`. Generated data remains local and ignored.

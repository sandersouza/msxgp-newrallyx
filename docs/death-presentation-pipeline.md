# Stage 09: present collision effects on the following refresh

The original 16.5 ms logical clock, collision event, movement lock, life loss
and 120/96-tick hold remain unchanged. Stage 09 snapshots the native death
state at the start of each host refresh, then draws that snapshot consistently.
An event computed during the refresh appears on the following refresh, adding
at most one display period (about 16.7 ms at 60 Hz) of visual latency.

The earlier immediate path is not safe for every 60 Hz work frame. The centered
car begins near 9.4 ms after VBlank. A logical tick, radar updates and another
resampled tick can discover contact after that scanline has passed. Updating
VRAM then gives a complete explosion in memory and an absent/partial explosion
on the already scanned display. Moving dirty work earlier improves the case
but cannot redraw pixels that have already been scanned.

`Death_Frame` transfers the native state into a presentation state before any
frame preparation. Presentation transitions queue effect/restore work, and
player visibility, bitmap sources and image/cache oracles consume that same
snapshot. Native hold checks continue using the original logical state. The
prior stage 08 has zero additional latency and retains identical ROM bytes.

Verify the exact original contact/hold/life behavior separately from display
state, then compare complete RGB and all visible cache states. Record the
presentation-state byte alongside every cache sample; never rewrite native
state to make a screenshot agree. The existing raster-period tolerance stays
unchanged. This is a documented temporal adaptation under the user's playable
port acceptance decision.

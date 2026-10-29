# Multi-car performance pass

User scope: another measured optimization pass and tests with multiple real
circulating/visible enemy cars, preserving current graphics and keeping all
changes in codex/fixed-hud-lab. No commits or new visual concessions.

- Preserve the63f0d6a baseline ROM/evidence before new rendering changes.
- Replace effect-triggered1024-name refills with per-buffer dirty name-cell
  queues, preserving camera streaming and fixed HUD/edge priority.
- Use exact native smoke candidate-row tracking instead of scanning empty rows.
- Add explicit3/7-enemy test variants with valid road spawns; keep native1enemy
  behavior as the default and preserve source descriptor padding/counters.
- Measure identical variant configurations before/after, including visible actor
  peaks, movement, hardware scanline limits, native state and active VRAM.
- Repeat full keyboard stage, smoke, restart, port spacing and VBlank checks;
  update the scoped cycle ledger and provide runnable ROMs.

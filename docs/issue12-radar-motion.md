# Issue #12: remove old enemy radar markers

The preceding flag/smoke correction kept ordinary enemy cells behind terrain
work. Different cells could therefore display different old positions of the
same enemy. The original observers checked fixed sprite coordinates and flag
removal, but did not reject this accumulation of enemy markers.

The new observer reproduces duplicate positions lasting 2.47 seconds in the
two-round capture and 27.70 seconds in the loaded round-six capture of ROM
`2e8a91d43232b76d6d890dce4438cba4b5ad62b4e22ef988ddd924b4e8e299ab`.

Enemy movement now prioritizes the existing footprint when crossing a radar
cell boundary or moving along a seam. An obsolete queued snapshot loses both
its ready and urgent bits; a freshly composed replacement becomes urgent.
This prevents old ink from being reintroduced after cleanup. Ordinary motion
inside one cell retains its existing scheduling. The limit remains one
80-byte cell publication per physical refresh, with unchanged original pixels,
colors, car drawings, HUD and real sprite limits.

The RAM-only departure/commit helpers use the existing mapper overlay. Two
cleanup bytes follow the visibility/urgent state without overlapping the enemy
records. Isolated execution checks masks, stale-payload invalidation, queued
metadata, native RAM/VRAM preservation, stack/index registers and mapper return.
All 391 tests and 1,534 executed component cases pass, along with 21 independent
cache/HUD/car snapshots, compact-HUD boundaries, two-player and attract probes.
The independent default rebuild matches the ROM below; the bounded Issue 11
image remains byte-identical. Actual round-two scanout was recorded and inspected.

## Current evidence

ROM SHA-256:
`06fb29529e3bb17a3d18ec0f62db43edaf7008cafe32441ad43ad7e8d29514e3`.

| Workload | Active radar samples | Enemy counts observed | Duplicate enemy positions | Unattributed pattern ink | Packet rate |
| --- | ---: | --- | ---: | ---: | ---: |
| Two naturally completed rounds | 2,342 | 1, 2 | 0 | 0 | 29.89–29.96 FPS |
| Controlled round-six setup | 1,230 | 6 initially; 4 after native restart | 0 | 0 | 29.00 FPS |
| Original challenge setup | 853 | 7 | 0 | 0 | 29.93 FPS |

Adjacent one-pixel seam fragments are treated as one moving marker. Actual
normal-pattern VRAM is checked against per-cell committed/staged poses and
base/flag ink; stale pixels without an owner are also rejected. Flag/smoke
deadlines, safe per-refresh radar publication and fixed player/fuel/radar gates
remain enabled. The component covers 1,534 synthetic departure/commit cases.

The loaded setup misses 3.33% of 30 Hz publication slots, versus 1.79% on the
preceding ROM; its native average is about 58 Hz. The former 2.5% slot gate
fails and remains recorded in `issue12-radar-trails-six-v226`. The qualified
follow-up explicitly allows 3.5% as a small measured timing concession for
correct radar cleanup. Maximum packet gap remains below 67 ms. Ordinary rounds
retain the 2.5% limit. This is not an unconditional stable-30-FPS claim.

Evidence is local and ignored under `references/build/issue12-radar-trails-*-v226`.
The natural route completes two rounds using steering margin eight. The
default-margin run completes one round and reaches game over late in round two;
it is not counted as two-round completion. The larger historical matrix and
physical hardware are not requalified by this follow-up.

```sh
gnumake build
ROM=references/build/latest.rom
.venv/bin/python -B -m scripts.msx.radar_motion_verify --rom "$ROM" --output references/build/my-radar-component
.venv/bin/python -B scripts/full_game_route.py --rom "$ROM" --output references/build/my-radar-motion --rounds 2 --steering-margin 8 --avoid-enemies --effects-trace --radar-trace --require-stable-radar --require-stable-fuel --require-stable-player --maximum-scroll-step 8 --maximum-packet-miss-percent 2.5 --maximum-packet-gap-ms 67
```

For the controlled load, use one round, `--fixture-first-round 6`,
`--fixture-enemies 6` and an explicit `--maximum-packet-miss-percent 3.5`.

# Issue #12: flag radar and smoke publication

Collecting a flag left its white radar dot visible. The full-game loop omitted
`Flag_PublishHUD`, and the legacy two-tick/content-window deferrals could also
starve the resulting dirty cell. Its terrain guard described the first of two
physical refreshes, so it could suppress publication throughout the second.

The loop now forwards collections and composes one flag cell independently of
numeric VRAM work. A two-byte urgent mask prioritizes content changes after the
radar has been fetched, including safe idle intervals of the second refresh.
At most one 80-byte cell is uploaded per physical refresh. Ordinary markers
retain the terrain guard, and queued payloads are not repeatedly recomposed.
Pending display metadata commits before another idle publication replaces it.

Smoke used the same FIFO for new clouds and retired-row repairs. Active,
visible native smoke could wait over one second behind cleanup. Successful
placements now promote their deduplicated job to the head, preserving every
displaced cleanup coordinate and partial progress. The existing three-unit
stream budget runs before the variable enemy workload. Graphics, native smoke
activation/fuel/stun rules, real sprite limits and the HUD remain enabled.

## Executed evidence

Qualified/default ROM SHA-256:
`2e8a91d43232b76d6d890dce4438cba4b5ad62b4e22ef988ddd924b4e8e299ab`.

The prior compact-HUD ROM reproduces up to 34.14 seconds of persistent collected
radar dots and 1,036 ms of missing visible smoke in a two-round keyboard route.
The added observer compares native flags with HUD state, RAM base masks and
actual radar VRAM masks; live visible smoke is compared with published tiles.
Enemy-overlapped radar pixels are excluded. These are sampled foreground lag
observations, not exact input-to-photon timings.

| Workload | Completion | Flag lag, maximum | Smoke lag, maximum | Packet rate | Missed slots |
| --- | --- | --- | --- | --- | --- |
| Natural keyboard route | Two rounds | 58 ms | 76 ms | 29.96 FPS | 0% |
| Six enemies, explicit round-six setup | One controlled round | 187 ms | 136 ms | 29.44 FPS | 1.79% |
| Original seven-car challenge setup | One controlled round | 135 ms | No smoke requested | 29.93 FPS | 0.12% |

All three pass the 250/200 ms flag/smoke limits, real VDP timing, one radar
publication per refresh and fixed radar/fuel/player checks. They retain the
reviewed 2.5% missed-slot and 67 ms packet-gap limits. The same round-six setup
on the preceding ROM measured 29.25 FPS and 2.44% missed slots. Intermediate
candidates that uploaded ordinary markers in every idle window failed the
timing profile and were rejected.

Local evidence is ignored under `references/build/issue12-effects-*-v222`.
All 388 tests and 1,440 executed queue cases pass, including ring wrap, full
queues, deduplication, partial cleanup preservation and stack/index registers.
Nineteen independent cache/HUD/car pixel snapshots, compact-HUD boundaries,
two-player sessions and attract pass. The default rebuild matches the qualified
ROM; the bounded Issue 11 build remains byte-identical.
The original larger eight-round v210 matrix remains historical; this correction
does not claim a renewed eight-round qualification or physical hardware pass.

## Reproduction

```sh
gnumake build
ROM=references/build/latest.rom
.venv/bin/python -B src/toolchain/legacy/full_game_route.py --rom "$ROM" --output references/build/my-effects --rounds 2 --avoid-enemies --effects-trace --radar-trace --require-stable-radar --require-stable-fuel --require-stable-player --maximum-scroll-step 8 --maximum-packet-miss-percent 2.5 --maximum-packet-gap-ms 67
.venv/bin/python -B scripts/full_game_evidence.py --rom "$ROM" --capture references/build/my-effects --output references/build/my-effects-pixels
```

For the controlled load case add `--fixture-first-round 6 --fixture-enemies 6`
and use `--rounds 1`. For the challenge use `--fixture-first-round 3` and one
round. Fixtures change setup explicitly; the natural route does not write guest
state. Smoke-free captures report `smoke_observed=false` and do not qualify it.

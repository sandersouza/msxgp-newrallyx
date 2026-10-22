# Native clock, input and replay-state contracts

`scripts/msx/native_contract.py` implements #18. These are reference contracts
for the forthcoming Z80 adapter and acquisition harness, not proof of native
boot, phase alignment or game equivalence.

## Exact cadence

`advance_clock(remainder, elapsed_cycles)` returns due ticks and the next
remainder using integer division of `remainder + elapsed_cycles * 2000` by
`3579545 * 33 = 118124985`. The initial remainder is zero. Elapsed cycles are
actual cycles since the previous scheduling event, not an assumed 60 Hz period.
Do not drop due ticks or round away the remainder.

For 100,000 display frames, the independently calculated reference results are:

| Display timing | Cycles per frame | Logical ticks | Final remainder |
| --- | ---: | ---: | ---: |
| 313 lines, nominal 50 Hz | 71,364 | 120,827 | 112,437,405 |
| 262 lines, nominal 60 Hz | 59,736 | 101,140 | 39,017,100 |

Both modes occasionally require two logical updates. The maximum intermediate
accumulator for one 50 Hz frame is 260,852,984; for 60 Hz it is 237,596,984.
A 32-bit accumulator can represent both. A native caller accumulating longer
intervals must bound or split them before multiplication/addition; Python's
unbounded integers do not prove absence of Z80 overflow. Task #19 must reserve
four bytes for the accumulator, and #20 must validate the executed arithmetic.

The authored sjasmplus arithmetic probe in ignored
`references/build/issue-18-clock-contract/clock.asm` checks constants, the tick
threshold and the maximum intermediate values. It assembles without errors or
warnings. It is a constant/arithmetic probe, not a native ISR performance test.

## Input levels and independent hardware writes

`input_bytes(pressed, dip)` accepts a set/frozenset of named pressed controls
and a raw DIP byte. It returns three independent bytes: P1, released P2 with
upright cabinet bit set, and unchanged DIP. It does not maintain input edges,
perform debounce, normalize opposite directions or modify hardware shadows.
The original logic owns coin/start edge detection and game behavior.

| Control | P1 active-low mask | Pressed alone |
| --- | ---: | ---: |
| Coin | `$80` | `$7f` |
| Start | `$40` | `$bf` |
| Up | `$20` | `$df` |
| Down | `$10` | `$ef` |
| Right | `$08` | `$f7` |
| Left | `$04` | `$fb` |
| Smoke | `$02` | `$fd` |

Provenance: MAME 0.289 commit
`f34f02505e32c1993c6a782b6814232cbfc74e36`,
[`rallyx.cpp`, input definitions](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/mame/namco/rallyx.cpp#L321).
`nrallyx` inherits P1/P2 from `rallyx` and modifies DIP definitions. The port
does not use `rallyxeg`'s alternate direction wiring. Service, player two and
cocktail control bindings are outside the initial single-player segment.

At runtime, publish input bytes to `$a200..$a202`. Radar, watchdog and sound
writes retain separate original-address shadows; do not write these input
bytes into the overlapping arcade read/write addresses.

## Snapshot comparison

Frozen `Snapshot(tick, phase, video, work, shadows)` records validate a
nonnegative logical tick, an explicit boundary phase and
exact immutable payload lengths:

Phases are `initialization-entry`, `pre-game-irq`, `post-game-irq` and
`post-game-irq-transfer`. The last phase represents an evidenced nonreturning
IRQ transition, such as coin acceptance; it cannot be compared as a normal
return. See [runtime acquisition](native-runtime.md).

| Region | Original addresses | Bytes |
| --- | --- | ---: |
| Video/state | `$8000..$8fff` | 4096 |
| Work | `$9800..$9fff` | 2048 |
| Hardware shadows | `$a000..$a187` | 392 |

`first_difference(expected, actual, exclusions=())` rejects missing or
tick/phase-mismatched records and returns the first differing original address
in region/address order, with tick, region and expected/actual byte values.
Identical records return `None`.

`Exclusion(address, reason, evidence)` identifies exactly one captured byte and
requires nonempty justification/evidence. Duplicate exclusions and addresses in
unrecorded gaps are rejected even when snapshots otherwise match. No region
masking or automatic stack exclusions are provided.

Equal tick/phase labels do not prove that two acquisitions sampled the same
logical boundary. #20/#21 must establish reset, inputs and pre-/post-IRQ alignment
with actual traces. No live state was excluded or declared equivalent by #18.

## Verification

```sh
.venv/bin/python -B -m unittest discover -s tests -p 'test_native_*.py' -v
make test
```

The 14 contract tests use synthetic snapshots and cover long-run clock counts,
input combinations/levels, malformed records, sparse addresses, phase mismatch
and individually documented exclusions. They require no original game data.

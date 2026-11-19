# Issue 42: original maze construction and flag variation

Issue: https://github.com/sandersouza/msxgp-newrallyx/issues/42

**Research baseline findings.** The initial investigation preserved the accepted
cartridge and executable packages byte-for-byte. The owner subsequently authorized
correction/optimization; [the local correction and its qualification](issue42-rng-correction.md)
are documented separately. Release publication still requires owner approval.

## Findings

1. **Flag repetition at a fresh MSX game is confirmed.** The original placement
   algorithm is present, but `Full_FirstBody` explicitly resets its state to 1.
   New-game loading also restores a captured seed image. Changing Start timing
   therefore does not provide the ongoing original arcade RNG state.
2. **The cached terrain does not require fixed flags.** A diagnostic that changes
   only the RNG word before placement generates another original-valid flag
   set. The unchanged cartridge renders it correctly, including the independent
   world/HUD/car oracle. No terrain cache or presentation code was replaced.
3. **Later MSX rounds are not universally fixed.** Two different active-play
   durations followed by the real F5 advance produce different second-round
   placements. This is a controlled transition check, not naturally earned
   ten-flag completion. The confirmed defect concerns fresh-game initialization;
   a claim that every phase is always fixed would be too broad.
4. **Normal maze geometry uses four compact predefined wall bitmaps and tile
   composition.** It is not newly randomized for each game. The original also
   expands a complete **32x56 = 1,792-byte logical board in RAM** before drawing.
   Compact ROM representation and an expanded working map coexist.

The owner's numbered-block analogy captures the opportunity to represent
scenery compactly. The observed format is specifically wall bits, neighborhood
masks and tile selectors, rather than a demonstrated BASIC-like command stream.
Values 1/2/3/4 in the logical board identify ordinary flag/L/rock/S objects;
wall shape comes from connectivity masks. Do not assign illustrative corner
numbers to the original format without evidence.

## Original-code mechanism

The contributor's validated main program is **16,384 bytes**, SHA-256
`d6943e556fcd6ffc32bcc1cc4abbec2249c16a2059a3cdc0ba9c942dbb765d4c`.
Disassembly and raw states stay in ignored `references/`, never in this report.

| Original address | Role established by code and execution |
| --- | --- |
| `3A52..3A67` | Bootstrap seed selection from DIP-switch bits and a small ROM table; stores the RNG word at `8000..8001`. |
| `03CA` → `0F24` | Ongoing frame-path RNG advance, including time before Start. |
| `0F24..0F3D` | Rotate the 16-bit state left once; add `4080` modulo 65536 when the rotated low byte AND `49` is zero. |
| `08BF..08D3` | Advance round, select parameters, place rocks (`1343`) and flags (`1379`). |
| `1343..1378` | Clear position records and select rock candidates from the layout's fixed candidate pool using RNG state. |
| `1379..1416` | Rejection-sample ten flag cells; updates position/cell tables referenced through `8992/8994`. |
| `141B..143C` | Reject nearby objects or fixed exclusion points. |
| `14E0..150B` | Query wall bits/bounds in the selected layout. |
| `14B3..14DF` | Form a logical wall cell from its 3x3 neighborhood. |
| `090E..0927` | Expand all 1,792 logical cells at `9800..9EFF`. |
| `0928..0951` | Overlay flags/S/L and rocks in that board. |
| `150C` and tables `2505`, `2529`, `2531`, `2552` | Select the 3x3 drawing tiles, orientation/color and object glyphs. |
| `1B1F` | Select normal layout page `30..33` from the round, along with parameters/colors. |

Normal geometry occupies **896 wall-bitmap bytes**: four layouts times
56 rows times four bytes. Their four 256-byte pages also contain 32 bytes each
of rock candidate coordinates, making **1,024 bytes** with those pools.
The existing `stage_one.cells_from_rom`/`tile` helpers reconstruct the same
compact mechanism. The native bitmap pages are already retained byte-for-byte
inside the current cartridge's native bank. Attract-specific data is separate
and must remain in scope for any later replacement.

For flags, candidate X is the low five state bits and Y is six high-byte bits.
Wall/out-of-range candidates are rejected. Accepted coordinates must avoid
other flags within distance 4 on both axes, rocks within distance 3, and two
fixed exclusion points within distance 5. This is a rectangular proximity
test, not Euclidean distance. Rock placement uses its ROM candidate pool.
The first eight records become ordinary flags, the ninth S, and the tenth L.
The research model reads all original tables from supplied ROMs; it embeds
neither coordinates nor extracted tables.

## Reproduction and independent checks

### Natural original sessions

MAME 0.289, isolated settings, original ROM unchanged, real credit/start input.
Seven cold boots cover Start delays of 0/1/2/7/60/180 arcade frames and one
repeat of the zero-delay trial. Read taps observe code/state; there are no
seed, PC or RAM injections in these natural runs.

- Four distinct first-round flag sets occur among the six delays.
- Repeating the same reset/input sequence reproduces the same flag set.
- The 0/1/2-frame delays happen to converge to the same accepted candidates.
  Not every timing change must produce a different result; imposing uniqueness
  would change the original algorithm.
- All runs contain eight ordinary flags, one S and one L. Entire logical
  geometry, flag types/positions and RNG transitions match the independent model.

### Controlled original matrix

A separate fixture supplies explicit RAM seeds and invokes original `08BF`
and `08E7` with interrupts disabled. It does not patch original ROM bytes.
**64 cases: native rounds 2..33, seeds 1 and 1234 hex**, covering all four normal
layouts and their rock counts. Every case matches the host model's final RNG,
flag/rock tables and **all 1,792 board bytes**. This proves initializer/expansion
semantics; it is not evidence of natural 32-round progression or full death/
alternating-player lifecycle equivalence.

### Accepted MSX cartridge

openMSX 21.0, WSX with **64 KiB main RAM**, HUD/audio and hardware sprite limits.
The exact accepted `dist/newrallyx.rom` is run; no replacement program is linked.

| Trial | Result |
| --- | --- |
| Wait 0, 0.5 or 2 seconds before Start | All reset RNG to 1 and produce the same first-stage flags; final placement RNG is 5676 decimal. |
| Wait 0.2 or 0.6 seconds in active play, then press F5 | Both reach native round 3 and produce different flag sets, matching the original initializer model including rocks. |
| Separate diagnostic: set RNG to 1234 hex immediately before placement | Produces a different exact original-valid flag set; independent display oracle passes. Only this diagnostic writes one declared RAM word. |

All six MSX probes pass the independent stable world/HUD/complete-car oracle.
The baseline script intentionally diagnoses the known fixed-seed behavior;
**its reset-to-1/repetition assertions are not acceptance criteria for a fix**.
The original-code model and documented lifecycle requirements are the authority.
Prior deterministic graphics/state fixtures did not cover variation between
fresh games; their success did not establish original seed lifecycle fidelity.

## Implications for performance and size

The safest first change is to restore the original RNG lifecycle while retaining
the current renderer and caches. Investigate both the copied seed word and the
explicit reset. Removing only the constant assignment would still load the same
captured state. Preserve the original PRNG, seed initialization and advance order;
do not substitute host randomness or an arbitrary timer seed. Avoid double
advances during active play and keep RNG state independent of accidental
presentation cadence. Credit/menu/attract/death/player-switch semantics still
need targeted lifecycle traces before choosing the implementation.

Current map construction already overlays objects from native records, and the
new seed diagnostic proves that it can present another placement. Consequently,
discarding the terrain cache is unnecessary to address this confirmed defect.
The two 16 KiB rendered-name map segments and the separate 2 KiB navigation
binding serve different purposes; they should not be conflated with RNG state.

| Candidate | Assessment / acceptance requirement |
| --- | --- |
| Correct RNG lifecycle, retain caches | First priority. Original placement is already available. Measure the eventual change; no active-time saving is claimed today. |
| Original compact geometry plus cold generation into existing RAM maps | Plausible separate ROM optimization. Keep hot accesses, include tile-ID conversion, code/tables and full transition cost. No feasibility/performance approval yet. |
| Generate or query drawing tiles during scrolling | Recurring decode/cache risk. Reject unless matched mean/P95/maximum, cadence and responsiveness remain unchanged or improve. |
| Remove rendered-map RAM entirely | Broader architecture change; not required for the bug and not established by this investigation. |

The compact backend currently represents eight 16 KiB map halves using
**24,576 live descriptor bytes and 35,105 constructor bytes** (1,003 constructors).
These occupy pages/gaps shared with other owners. Their 59,681 live bytes are
**not a demonstrated whole-ROM saving**: removing them requires repacking,
replacement code/tables and preservation of neighboring replay/renderer data.
The accepted copy routine costs 304,540 reference cycles per half; any cold
replacement must be measured against complete current transition behavior.
No existing cycle workbook is relabeled and no new FPS claim is made here.

## Preservation, remaining work and commands

The cartridge remains **1,007,616 bytes**, SHA-256
`b5684933f5dcae72d5552b51cbca64a28458fa980795334d6491ce3f55c66e4a`.
Both executable ZIP hashes also match the accepted release metadata. This is
binary preservation, not a new runtime qualification of a corrected algorithm.
The existing 64 KiB, below-1-MiB, executable and MegaRAM contracts remain binding.

Remaining research work: natural original multi-game/death/two-player RNG lifecycle traces,
attract-specific sampling, a minimal proposed correction, and exact-hash
cartridge/executable/MegaRAM performance/audio/gameplay qualification if that
correction is authorized. The subsequent authorized correction is recorded in
the linked implementation report; this section preserves the research-stage
artifact identities. No release may be published without owner approval.

```sh
make build
.venv/bin/python -B scripts/arcade_maze_flags_probe.py
.venv/bin/python -B scripts/msx_flag_seed_probe.py
```

Required: contributor arcade ROMs, supplied MSX BIOS, existing project environment,
MAME 0.289 and openMSX. `make build` is a local build, not release publication.
Durable evidence is in `docs/measurements/cartridge/issue42-{arcade-maze-flags,msx-flag-seed}.json`.
Source owners: those two Python scripts and
`src/toolchain/screen4/arcade-maze-{flags,matrix}.lua`. Private disassembly,
positions, boards and emulator sessions are disposable after summarization.

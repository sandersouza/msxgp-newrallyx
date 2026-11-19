# Timing workbook retention

The current integrated measurement is [cycle-budget.xlsx](../../cycle-budget.xlsx).
Its [source ledger](cycle-ledger.json) records the ROM SHA-256, workload,
machine, CPU/video settings, inclusive/self routine costs, tails, waits and
budget assumptions. [workbooks.json](workbooks.json) records workbook hashes
and the source path of each historical copy.

The canonical workbook now measures the complete **761,856-byte ASCII8** local
candidate, SHA-256 `c82e85db4d47bbc2c72797de0982998642f952208aeecfd1edbd1b8de2a87160`.
Its ten scoped current profiles include **fixed64KiB, zero mapper** WSX ASCII8/MegaRAM with three/five/six
enemies and ASCII8 WSX128/Sony64/ST256/GT512 with three enemies. The primary
sample presents30.029FPS at59.922743Hz refresh; existing heavy-scene tails remain.
[Fixed-RAM qualification](../../issue42-fixedram64.md) compares the correction
with the previous mapper-backed cartridge: all356 state/tick/PSG rows match in
each of ten workloads and every paired active frame costs the same or less.
The previous44be6037 workbook/ledger retain their original hashes under
`archive/retained-c19093e1953486e3/`. Current F10, audio and natural game-over
proofs are separate from active FPS. The
[preceding size/performance report](../../issue42-768-optimization.md) retains
its original hash, route/state scopes and longer individual spans. DOS/BASIC loading uses768KiB MegaRAM; the separate
512KiB standard-mapper edition remains experimental.
Earlier matrices and workbooks retain their original ROM hashes. No release
publication is implied by this local workbook update.

The [512KiB integration workbook](mapper512-integrated.xlsx) and its
[separate ledger](mapper512-integrated.json) measure the experimental full-game
RAM-active relink, with four RAM-image seals rather than a new cartridge hash.
They retain both input schedules, identical-state comparisons and the slower
three-enemy presentation-clock route. Bootstrap/cold loading remain host-assisted;
this does not qualify a standalone512KiB executable or replace canonical timing.
See [scope and reproduction](../../issue42-512-integration.md).

The [cold-I/O workbook](mapper512-cold-io.xlsx) and
[ledger](mapper512-cold-io.json) separately measure actual DOS1/BASIC resource
loading, OS/file batching and world finalization. They also retain the occupied
storage active-game checks. Filesystem fixtures and host-assisted gameplay are
distinct proofs, not an end-to-end512KiB executable. See the
[cold ownership report](../../issue42-512-cold-io.md); canonical timing is unchanged.

`archive/` preserves earlier full-session, first-stage, free-camera and
component workbooks previously kept only in ignored `outputs/`. These files are
byte-identical snapshots with their own measurement scopes. Future canonical
workbook replacements retain the prior workbook here by content hash.

Run `make timing-workbook` from the repository root after profiling the intended
ROM. The report rejects a stale ROM/profile match. The generator recalculates
formulas and checks for formula errors before publication. Commit the XLSX,
ledger and manifest together when measurements change. Preview renders, raw
traces, ROMs and emulator dumps remain local and ignored.
## Native512KiB loader continuation

`mapper512-native-game.json` and `mapper512-native-game.xlsx` retain the
real DOS/BASIC boot, family transitions and short-route timing continuation.
They are experimental, pinned to separate bridge/resource/hot-image hashes.
The strict no-regression verdict remains open; see
[the native-loader report](../../issue42-512-native-game.md). The supported
ROM's canonical workbook is unchanged.

`mapper512-lifecycle.json` and `mapper512-lifecycle.xlsx` record the subsequent
special-flag/challenge corrections,23 lifecycle cases and six fresh active-game
routes. Both carry their current bridge/resource/test-carrier hashes. Raw
aggregate unchanged/slower cases remain visible; they do not close the earlier
divergent-route pacing question. See [the lifecycle report](../../issue42-512-lifecycle.md).

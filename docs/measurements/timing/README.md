# Timing workbook retention

The current integrated measurement is [cycle-budget.xlsx](../../cycle-budget.xlsx).
Its [source ledger](cycle-ledger.json) records the ROM SHA-256, workload,
machine, CPU/video settings, inclusive/self routine costs, tails, waits and
budget assumptions. [workbooks.json](workbooks.json) records workbook hashes
and the source path of each historical copy.

The canonical workbook measures the default 2,048,000-byte 64 KiB cartridge,
SHA-256 `661c41bd7332fee8b06bef03a20555a44863435fc13747e8150f738c32cc13a5`:
29.46772 presented FPS in the three-enemy sample at 59.92274 Hz refresh.
`RAM profiles` compares retained before/current 64 KiB and unchanged `MAPPER=1`
samples with three/five/six native enemies. Their exact hashes, active partitions
and controlled component costs are in [ram-profile-comparison.json](ram-profile-comparison.json).
See the [validation scope](../../ram-profile-validation.md).

`archive/` preserves earlier full-session, first-stage, free-camera and
component workbooks previously kept only in ignored `outputs/`. These files are
byte-identical snapshots with their own measurement scopes. Future canonical
workbook replacements retain the prior workbook here by content hash.

Run `make timing-workbook` from the repository root after profiling the intended
ROM. The report rejects a stale ROM/profile match. The generator recalculates
formulas and checks for formula errors before publication. Commit the XLSX,
ledger and manifest together when measurements change. Preview renders, raw
traces, ROMs and emulator dumps remain local and ignored.

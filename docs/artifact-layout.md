# Build artifacts and disk use

The playable cartridge is **`dist/newrallyx.rom`**, accompanied by its compact
`manifest.json`. `make run` loads this exact file; `MAPPER=1` changes only the
emulated RAM to128KiB. Explicit test/diagnostic/legacy modes use named `dist/`
subdirectories. Select ASCII8 for the default game in WebMSX; named diagnostics
may use other explicit mappers. The experimental512KiB RAM-backend test carrier
at `dist/experimental/mapper512/newrallyx-512-test.rom` uses ASCII8 and requires
512KiB main mapper RAM. It is distinct from the default744KiB cartridge for64KiB
machines; see [its scope and controls](issue42-512-lifecycle.md).
The corrected fixed64KiB test cartridge is also retained at
`dist/experimental/fixedram/newrallyx.rom`, with identical bytes to the default
cartridge and its own manifest. It needs no RAM mapper. Its MegaRAM test package
is under `dist/experimental/fixedram/megaram/`; the normal local package remains
`dist/compact/megaram/newrallyx-megaram.zip`. No release is implied.
No duplicate filename-hint ROM is made.

## Retention policy

Disk space is constrained. Keep results, ROM hashes, test counts, workload
descriptions and timing workbooks in `docs/`. Raw builds, screenshots, videos,
traces, emulator states, logs and issue working directories are disposable.
Do not move them into a growing archive instead of deleting them.

| Location | Purpose | Cleanup |
| --- | --- | --- |
| `dist/` | Playable ROM and manifest | Preserved by `make clean`. |
| `references/roms`, `msxbios`, `assets`, `scenes` | Contributor build inputs | Protected. |
| `references/stage-one/` | Small base native acquisitions used by generators | Protected. |
| `references/build/`, `cache/`, `baselines/` | Temporary compilation and reproducible reference data | Deleted by clean; regenerated when requested. |
| `references/sessions/`, `validation/`, `issue*`, `analysis/`, `archive/` | Raw development and test data | Deleted by clean, including raw measurement snapshots. |
| `docs/measurements/`, `docs/cycle-budget.xlsx` | Curated results and previous workbook hashes | Versioned and retained. |

```sh
make run
make run MAPPER=1
make clean-preview
make clean
```

Cleanup never follows linked input directories and preserves tracked repository
files/placeholders. It keeps the final distribution and deletes caches as well
as raw evidence. After a benchmark, record the compact result and clean the raw
data instead of retaining every attempt. Compiler logs are overwritten in the
current work directory. A baseline needed by `make verify-module-layout` is
rebuilt on demand from its recorded source configuration.

## Cleanup on2026-10-30

The earlier archival approach retained about80GB, plus7GB of issue39 work and
1.2GB of analysis. The user explicitly requested deleting this material.
`docs/artifact-retention.json` records compact matrix summaries, ROM hashes,
former disk usage and protected-input fingerprints. Raw traces, replay files,
per-issue builds and the archives themselves have been deleted. Old paths in
historical ledgers are provenance, not promises that the raw files still exist.

`references/` fell from about89GB to62MiB. Contributor inputs and the current
2,048,000-byte ROM were compared by hash and remained unchanged.

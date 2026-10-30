# Developer guide and reusable code

Start here rather than searching deleted experiment directories. The maintained
knowledge is the source, its contracts and the documents linked below. Raw
builds, videos, dumps and logs are disposable; recorded results are not.

## Reading order

1. [Engineering lessons](engineering-lessons.md): what worked, what failed,
   why, and where the implementation lives.
2. [Architecture](architecture.md): build ownership and the boundary between
   current SCREEN4 adapters and pinned/shared SCREEN5 sources.
3. [Module contracts](../src/screen4/modules/README.md) and
   [the registry](../src/screen4/modules/contracts.json): callable APIs,
   register/IFF ownership, memory lifetimes and limits on reuse.
4. [Setup](setup.md): pinned assembler, Python environment, original local
   inputs and emulator tools. [Artifact policy](artifact-layout.md): output
   locations and cleanup.

## Follow a feature through the pipeline

| Question | Start in | Next boundary |
| --- | --- | --- |
| Which ROM does a command build/run? | `Makefile`, `src/toolchain/screen4/targets.mk` | `dist/newrallyx.rom`; MAPPER affects emulator RAM only. |
| Where do input graphics and native state come from? | `src/toolchain/msx/stage_one.py`, `src/toolchain/screen4/game_build.py` | Contributor ROM validation, base acquisition and original-size resource generation. |
| Why does the final assembly differ from the checked-in base? | `src/toolchain/screen4/session_build.py` | Generated assembly view; then RAM64, automatic mapper and turbo adapters in that order. |
| Which RAM layout is selected? | `session_ram64.py`, `session_auto.py`, `session-auto.inc` | Startup probe, cold allocation and one-time API patching. |
| What may execute accelerated? | `session_turbo.py`, `session-turbo.inc` | CPU-only wrappers and the Page3 BIOS bridge. |
| Where is hardware I/O owned? | `modules/vdp/`, `modules/mapper/`, `modules/audio/` | Check source headers before calling: shared names do not imply shared ABIs. |
| Where is a complete picture published? | `lab.asm`, `game-main.inc`, `modules/renderer/` | Inactive preparation, blanking wait and coherent commit. |
| How is a claim checked? | `session_verify.py`, `session_profile.py`, `session_report.py` | Gameplay/pixels, guest-time measurement and compact ROM-bound ledger. |

Unqualified filenames in the table belong to `src/screen4/`. The base
`lab.asm` is transformed before linking; never infer the final bindings from
that template alone. Generated files are for inspection, not manual patches.

## Reusing an include

Read the inline contract first: inputs, outputs, registers, flags/IFF, mapped
banks, scratch lifetime and initialization order. Then identify the host aliases
and resources in the registry. A transfer primitive can be reused independently;
a native flag renderer or session transition requires a game-specific adapter.

Do not add wrappers or allocations merely to reorganize source. Source-only
module changes must preserve ROM bytes and the complete symbol map for the
matching frozen configuration. Copying only a helper while omitting its mapper,
VRAM or IRQ assumptions does not constitute reuse. The module README contains
small independently assemblable transfer/mapper examples.

## Work and validation loop

```sh
make environment-check
make build
make run                 #64KiB reference
make run MAPPER=1        #same ROM,128KiB reference
make test
make verify-module-layout
make clean
```

Use targeted emulator checks for the changed path; a full performance matrix is
appropriate when CPU policy, timing, cache geometry or hardware ownership changes.
For example, `session_verify.py --bundle references/build/game --headless
--scenario start --contracts` checks a real keyboard start and graphics contracts.
Specify `.venv/bin/python -B src/screen4/` before that script name when invoking it.

For timing work, retain hash/configuration, workload/population, guest-time units,
inclusive/self costs, waits, tails and presentation rate in a compact ledger.
Do not add parent and child inclusive costs together. Update the maintained
workbook using `make timing-workbook`; then delete raw working data with
`make clean`. The playable distribution and contributor inputs survive cleanup.

## Documentation that survives an experiment

For each technique record the problem, constraints, chosen mechanism, rejected
alternatives, measurable outcome, limitations, source owners and reproduction
command. Separate observed results from estimates and pending acceptance.
Record a failed approach when it prevents repeating an expensive mistake.

For code blocks explain the invariant and why the ordering matters. At public
boundaries document inputs/outputs, clobbers, IFF, hardware ownership, memory
lifetime and forbidden contexts. Keep inline summaries synchronized with
`modules/contracts.json`. Avoid comments that merely translate each opcode.

Historical documents retain old ROM hashes and artifact paths as provenance.
They are not current build instructions or promises that deleted traces exist.
The current handoff is this guide, the engineering lessons, the source contracts
and the compact [retention/result record](artifact-retention.json).

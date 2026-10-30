# Source-only assembly modules

Delivered locally as the user-authorized modularization subtask of
[issue 36](https://github.com/sandersouza/msxgp-newrallyx/issues/36), coordinated
with issue 32. The [module catalog](../src/screen4/modules/README.md) and
[contract registry](../src/screen4/modules/contracts.json) define the public
interfaces and reuse limits. This extraction follows the lossless ROM packing;
its baseline is the already reduced cartridge.

This frozen report describes the preserved 128 KiB profile, now selected with
`MAPPER=1`. The default functional 64 KiB adapter has separate
[validation and timing evidence](ram-profile-validation.md); it is not a
zero-byte-delta modularization of the 128 KiB image.

## Result and acceptance gate

**No cartridge byte, symbol value, runtime instruction, memory allocation or
execution schedule changes.** The complete default ROM remains 2,048,000 bytes,
SHA-256 `b80c7b72ace0ee0e9686127a156249d3cceaa3292ddea767ad1497950badbfb1`.
Its 1,589 assembler symbols, including RAM aliases and private labels, match
the pre-extraction map exactly. There is no additional call, jump, wrapper,
dispatch, stack use, mapper/VDP traffic, wait or frame latency at a module boundary.

The mandatory gate checks both full ROM hash/size and a canonical digest of
every symbol name/value; it rejects a same-size opcode change and a changed
non-emitted memory alias. The independent local verification additionally
compared the actual before/after ROM bytes and parsed symbol maps.

| Matching profile | Bytes before/after | Symbols before/after | Identity |
| --- | ---: | ---: | --- |
| Complete default | 2,048,000 | 1,589 | ROM and map identical |
| Test mode | 2,048,000 | 1,593 | ROM and map identical |
| Classic HUD | 2,048,000 | 1,585 | ROM and map identical |
| Hardware check omitted | 2,048,000 | 1,562 | ROM and map identical |
| Three-enemy first-stage | 3,604,480 | 956 | ROM and map identical |
| Independent SCREEN 5 legacy | 2,097,152 | Sources untouched | ROM identical |

Hashes, complete symbol-map digests and resolved module exports are in the
[metadata evidence](measurements/modules/issue36-module-layout.json).
Original ROMs/maps and raw captures remain ignored under
`references/issue36/modules/` and the existing generated bundles.

## Implementation

The renderer, native core, world sprites and first-stage audio now have public
assembly composition entries. Full-session resident/cold code is split into
state, bootstrap, mapper, source-bank/prewarm, video, round/map loading, radar
cache/color/blink, audio, lifecycle, input/motion and interface sources.
The VDP streaming primitive and Page0 mapper can be assembled independently
with another host's compatible bindings. Existing HUD, pattern-address, input,
phase-cache and optional startup modules retain their direct interfaces.

`session-resident.inc` and `session-cold.inc` remain ordered compatibility entry
points. Include hierarchy and local-label scope are preserved; private generated
sources are still transformed in the existing assembly directory before linking.
No original payload is moved into versioned assets. The host frame/clock driver
and native game rules remain host-specific, rather than being hidden behind a
new runtime plugin or scheduler.

Each contract states input/output, registers/flags, IFF, sequence/reentrancy,
RAM/VRAM/mapper ownership and lifetime, generated dependencies and reuse limits.
Assembly-time aliases and caller-owned resources permit reuse without a runtime
adapter. This does not make the two audio ABIs or native game encodings mutually
interchangeable; another port must supply and validate its own bindings.

## Validation and timing

- General tests: 446 passed. Component tests: 88 run, 87 passed, one explicit
  emulator-dependent skip. Five new checks cover same-size byte drift, symbol
  alias drift, contract completeness and standalone assembly reuse.
- `make test-experiments` passed the full default boot, keyboard controls,
  two-player, round/flag/attract/radar/smoke, rocks, speed, 16,000-refresh steering,
  audio and sprite contracts. No graphics, hardware-limit or input concession
  was introduced.
- The matched profile again uses openMSX 21.0, Panasonic FS-A1WSX_NR128,
  3,579,545 Hz Z80, real sprite limits, HUD and PSG enabled, native round 5,
  layout 1 and three moving enemies. All exposed player/camera/enemy/input/tick
  records match across 356 intervals. Each run has its uninstrumented control;
  observation jitter is bounded by the existing five-cycle limit, with equal
  total duration within 0.01 cycle.
- Active sample: 238 intervals at **29.90315 presented FPS**, unchanged. Physical
  refresh is separately 59.92274 Hz. Mean work is 81,013.56 CPU cycles; P95
  109,983 and maximum 127,375, with the same one three-refresh interval. The
  existing worst-case deadline limitation is retained, not hidden by a tolerance.
- [cycle-budget.xlsx](cycle-budget.xlsx) and its source ledger were refreshed for
  the matching post-extraction profile. Inclusive/self costs, waits and budget
  assumptions remain distinct; no parent/child double counting is introduced.

ROM/map identity proves the absence of extraction overhead for the matching
configurations, rather than relying on an average FPS comparison. The profile
is a short deterministic active-play workload, not a complete-course or physical
hardware qualification. Another host, asset/layout choice or flag combination
requires its own accepted configuration and integration checks.

## Reproduce

```sh
make build
make verify-module-layout
make build TEST_MODE=1
make verify-module-layout TEST_MODE=1
make build HUD_VARIANT=classic
make verify-module-layout HUD_VARIANT=classic
make build HARDWARE_CHECK=0
make verify-module-layout HARDWARE_CHECK=0
make test-experiments
make profile-experiments
make timing-workbook
```

For the first-stage profile, build with `make build-first-stage ENEMIES=3`, then
run `module_contracts.py --profile first_stage --bundle
references/experiments/stage-one-3-enemies --output <ignored-report.json>`.
The frozen fingerprints describe this extraction, not a permanent prohibition
on separately authorized feature changes. Updating them requires a reviewed
new baseline, never a silent rebaseline after a failed structural gate.

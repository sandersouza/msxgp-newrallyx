# Mandatory hardware delivery matrix

Tracking: [issue42 hardware gate](https://github.com/sandersouza/msxgp-newrallyx/issues/42#issuecomment-6983050094).
The failure below is historical. The [fixed-RAM correction](issue42-fixedram64.md)
now passes the genuine zero-mapper emulator gate; physical acceptance remains open.
The owner approved this exact744KiB/768KiB target for stable
[1.0.2](https://github.com/sandersouza/msxgp-newrallyx/releases/tag/1.0.2) on2026-11-18.

The owner clarified these requirements on2026-11-18. A64KiB memory mapper is
not evidence for a machine with64KiB fixed RAM and **no RAM mapper**. MSX2+,
V9958/128KiB VRAM, existing graphics/audio/gameplay/performance and F10 remain
required. Cartridge banking, standard RAM mapper and MegaRAM are different
devices/interfaces.

|Delivery|Required main RAM|Additional game storage|Current evidence|
|---|---|---|---|
|ROM / cartridge|64KiB fixed RAM; no RAM mapper|Compatible ASCII8 cartridge bank controller|Stable1.0.2: fixed64KiB, separate/shared primary and unexpanded RAM pass|
|BIN / COM main-mapper edition|Compatible standard RAM mapper with enough capacity|Game resources held in that mapper|512KiB experimental lifecycle matrix;4MiB legacy edition preserved; broader qualification open|
|MegaRAM|64KiB fixed RAM; no RAM mapper|Compatible MegaRAM with enough capacity; current image fits768KiB|Stable1.0.2: DOS1/BASIC with fixed64KiB, including shared-primary and unexpanded RAM, pass|

The512KiB diagnostic `.rom` in `dist/experimental/mapper512/` is explicitly a
carrier for testing the RAM-backend game. It requires512KiB RAM mapper. It is
not the owner-required cartridge target. The744KiB default and768KiB MegaRAM
fallback cannot be promoted stable solely because their size targets pass.

## A real fixed-RAM regression profile

`mapper_reference.tcl` now supports `NRX_REFERENCE_RAM_KIND=plain` with64KiB.
It replaces the FS-A1WSX reference XML's `MemoryMapper` with a fixed `RAM`
device at0000..FFFF, retains its slot and V9958/128KiB VRAM topology and removes
`MapperReadBackBits`. It asserts that the emulator has **zero** devices whose
description is `memory mapper`, plus a65,536-byte main RAM device. Input BIOS
files and system machine configuration are unchanged. The default reference
mapper behavior remains intact.

`compact_game_verify.py --ram-kind plain` uses a separate session and records
actual main-RAM kind and mapper bytes. The synthetic configuration test verifies
that no mapper device/setting survives. Do not infer fixed RAM from bank count,
port-readback masking, a64KiB mapper or a successful title screen.
The current512 general tests pass, alongside94 component tests with one skipped.
Host tests alone are not hardware evidence. The corrected ROM and both MegaRAM
launchers also pass actual emulator gameplay, lifecycle and matched performance
tests; [current evidence](measurements/cartridge/issue42-fixedram64.json).

## Historical failure and retained evidence

All three earlier exact-artifact tests reached the title and accepted coin/start, but failed
before the first gameplay presentation. Both MegaRAM launchers first verify
all761,856 loaded game bytes in the768KiB MegaRAM. Thus this failure is in the
shared game backend, not a short MegaRAM transfer.

The first `GameSession_CopyMap` selects destination1 through portFC, then uses
SP4000/PUSH to materialize16KiB at0000..3FFF. On fixed RAM, FC reads255 before
and after the write and no alternate bank is selected. A read-only observer
around that first construction confirms that the live Page0 code at0000..07DF
is overwritten. Restoring FC cannot recover it; the return into overwritten
code reenters unrelated startup/UI paths. `GameAuto_Init` also reports only
one16KiB Page0 window, which is not the total fixed-RAM capacity.

Changing capacity reporting or suppressing this constructor would not solve
the hardware dependency: `GameSession_MapPage`, object patches and active world
queries also assume interchangeable Page0 RAM banks. Those lifetimes and
accessors need a genuine fixed-RAM binding with a measured no-regression result.
The machine still physically has64KiB; this finding is not a memory-capacity
impossibility proof. No slower drawing path, graphical simplification, clock
change or larger main-RAM minimum is accepted as a workaround.

The [compact failing-gate result](measurements/cartridge/issue42-plain64-gate.json)
retains artifact/configuration/observer hashes, actual zero-mapper evidence,
load/start observations and before/after code hashes, without original payloads.
Reference openMSX evidence is separate from physical-hardware qualification.

The earlier [512KiB lifecycle results](issue42-512-lifecycle.md) remain valid
for their explicitly measured mapper configurations. Their preserved64KiB
cartridge/MegaRAM tests used a64KiB **mapper**, not fixed RAM. They do not close
this new mandatory gate or authorize a release.

## Reproduce the corrected binding

With contributor inputs and current normal/MegaRAM bundles prepared:

```sh
.venv/bin/python -B -m unittest discover -s tests -p test_mapper_reference.py
.venv/bin/python -B scripts/compact_game_verify.py --fixed-ram --mode rom --ram-kind plain
.venv/bin/python -B scripts/compact_game_verify.py --fixed-ram --mode dos --size 768 --ram-kind plain
.venv/bin/python -B scripts/compact_game_verify.py --fixed-ram --mode basic --size 768 --ram-kind plain
.venv/bin/python -B scripts/fixedram_qualify.py
```

These commands now pass with the new binding. The historical
`plainram64_report.py` intentionally targets the preceding sealed failing
artifacts; do not relabel its report or run it against new symbols/bytes.
The current correction preserves the main-mapper executable payloads and F10;
the512KiB diagnostic carrier remains separate. Physical hardware, owner acceptance
and broader issue42 work remain open. Publication approval is recorded in the
1.0.2 release notes; it does not relabel historical failed or experimental tests.

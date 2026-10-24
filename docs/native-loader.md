# Native loader and mapper proof

Issue #19 adds a loader proof to the approved #11 memory architecture. It
loads a complete 16 KB original-address program, resident test code, game-state
RAM and four preloaded asset segments. It deliberately runs an authored test
entry instead of the original reset or gameplay. Its cartridge is labelled
`mode: loader-probe`, `gameplay: false` in a sealed build report; it does not
replace `references/build/newrallyx.rom`.

## Boot and ownership

The cartridge derives the page-3 RAM slot from the current primary/secondary
slot configuration, selects that slot in page 2 and copies the loader into
fixed host RAM. It detects the active host segment with a changing marker and
allocates seven further independent segments using reversible alias tests.
It never assumes segment IDs and never reads mapper ports to discover RAM.

| CPU range | Selected payload |
| --- | --- |
| `$0000..$3fff` | Complete original-address program, unchanged in this proof |
| `$4000..$7fff` | Resident cartridge/test code copied to RAM |
| `$8000..$bfff` | Game-state segment or one of four asset segments |
| `$c000..$ffff` | Fixed host RAM, loader, IM2 vectors and host stack |

Existing host reservations remain protected. New generated allocations are
`$c500..$c57f` (state, including clock, queue, logical IFF and publication),
`$c580..$c6ff` (separate host IRQ stack), `$c700..$c701`
(temporary reversible discovery marker), and `$d400..$dfff` (loader-code
reservation). The assembler asserts that actual loader code fits its region.
The host stack begins at `$f380`; vectors use `$d000..$d100` and `$d2d2`.

Cartridge bank copies run entirely from host RAM. After loading all segments,
BIOS ENASLT selects page-1 RAM. The final page-0 slot change executes directly
from host RAM, preserving other pages' slot bits: making that change from a
BIOS routine would remove its executing code. No BIOS calls follow that change.

`Native_MapAssets` accepts an index 0–3 only while native execution is marked
suspended and no asset mapping is already active. Invalid/nested requests set
an error without changing ownership. `Native_RestoreGame` restores page 2.
Both preserve registers/flags and interrupt state. The current host IRQ uses
only resident code/state, preserves main/alternate registers and acknowledges
VDP status. Issue #20 adds a separate host IRQ stack and proves preservation
when the interrupted SP lies in the game window; original game IRQ delivery
remains pending. See [runtime validation](native-runtime.md).

References: Grauw's authored [RAM-slot selection routine](https://map.grauw.nl/sources/raminpage1.php)
and [mapper-port description](https://map.grauw.nl/resources/msx_io_ports.php).
Mapper readback is not a portable ownership mechanism. The debugger's controlled
host-relocation test reads its emulated machine state; the cartridge does not.

## Reset policy

This standalone cartridge supports machine reset, which restarts BIOS slot/
mapper initialization and reruns discovery/loading. It saves initial primary/
secondary slot selections for verification, and the harness checks that these
selections are restored after an actual reset from the active native mapping.
It does not return into an old BASIC/DOS session or claim to restore unknown
write-only mapper-register values. A future soft exit requires its own contract.
Original in-game restart/death handling belongs to #20 and later replay evidence.

## Active resource inventory

The contributor-input build validates all 13 source ROMs and candidate hook
hashes, a sealed renderer reference and extracted-asset provenance. It keeps
all original tiles, sprites and dots as losslessly packed two-bit pen indices;
original dimensions, pens and palettes are preserved. It also preloads the
current HUD font/patterns, lookup/RGB data, sprite resources, atlas and stage IDs.
Stage IDs omit only unused padding columns from the existing 128-column table,
retaining every one of the 102x174 source cells.

The measured working set is **48,596 bytes**, padded to four 16 KB segments;
16,940 bytes remain available. This proves storage fit for the inventoried
resources, not final palette composition, converted actor resources, full
renderer linkage or performance. Those remain #22 gates. No cartridge refill
path or extra RAM is required for this inventory.

## Reproduce the proof

Use the existing managed assembler, openMSX and contributor-supplied BIOS.
Choose fresh output paths; existing evidence is never overwritten. Run this
Python snippet from the repository root:

```python
from pathlib import Path
from scripts.msx.native_build import build_probe
from scripts.msx.native_probe import verify_probe

root = Path.cwd()
rom = build_probe(root, root / 'references/build/loader-probe',
                  root / '.tools/sjasmplus/1.24.0/sjasmplus', hz=50)
result = verify_probe(root, rom, root / 'references/build/loader-proof',
                      root / 'references/msxbios')
print(result)
```

For a contributor-input load proof, use `native_build.build(root, args)` with
`output`, `assets`, `assembler`, `hz` and `logic_only=True`. Supply `reference`
as a sealed renderer bundle; if omitted, the builder searches for a sealed
bundle matching the existing default cartridge's hash. The test entry still
runs instead of the original program. Use `host_segment=5` in `verify_probe`
to exercise a relocated host. `small_memory=True` checks refusal on the stock
64 KB FS-A1WSX configuration instead of the session-local 128 KB variant.

## Measured evidence — 2026-10-21

Real openMSX 21.0, pinned sjasmplus 1.24.0 and supplied BIOS were used at
3,579,545 Hz with isolated settings and session-local machine XML. Each positive
run includes an actual machine reset and **256 resource switches**, including
VBlank IRQs while assets are mapped. Main/alternate registers and SP match
before/after every map/restore; the final evidence includes 257 serviced IRQs.
The fixture also rejects unsuspended and nested mappings.

| Case | Local sealed evidence | Result |
| --- | --- | --- |
| Original program/resources, 50 Hz | `references/build/issue19-proof-original/` | Copies, visible mappings, game restoration, host canary and reset pass |
| Synthetic, host segment 5 | `references/build/issue19-proof-host5/` | Roles discovered as `[5,0,1,2,3,4,6,7]`; same preservation checks pass |
| Stock 64 KB mapper | `references/build/issue19-proof-small/` | Cartridge detects four independent segments and refuses startup |
| Synthetic, 60 Hz | `references/build/issue19-proof-60/` | Same copy/register/reset checks pass |

The original-input bundle is `references/build/issue19-original-1/`.
Reports contain source/build/BIOS hashes, emulator version, symbols, physical
RAM, visible pages and exact resource offsets. Emulator persistent/cache files
live in separate ignored `*-session/` directories; only strict evidence files
are sealed, and their manifests are verified after publication.

The initial integration test exposed the unsafe page-0 BIOS transition; after
moving that transition to resident RAM the same test passed. Evidence validation
also rejects malformed/partial reports, changed copied bytes and incomplete
physical segments. All authored test data is synthetic. Original files and
generated cartridges/captures remain ignored.

Run `.venv/bin/python -B -m unittest discover -s tests -p 'test_native_*.py' -v`
for the native safety checks and `make test` for the full suite. A concurrent
test process deleting system temporary directories affected one full-suite run;
the passing run isolated `TMPDIR` below ignored `references/build/issue19-suite-tmp/`.

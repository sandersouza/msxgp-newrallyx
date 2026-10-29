# Cartridge graphics storage audit

Issue: [#36](https://github.com/sandersouza/msxgp-newrallyx/issues/36).
Status: read-only audit and storage simulation, 2026-10-29. No production
generator, mapper layout or ROM has been changed by this audit.

## Baseline and scope

The default full-session SCREEN 4 build is **4,177,920 bytes**, or 255 banks of
16,384 bytes (3.984375 MiB). It has only 16,384 bytes of headroom below 4 MiB.
Reaching 2 MiB requires saving 2,080,768 bytes. The baseline checkout is
`435180f87439938ef2ea2b7f41c355070ce1d3b3`; the build command is `make build`.
ROM SHA-256:
`98ce0135b628a1837a3d6df2910f572e466b4bffe465344238f4c44a9015346a`.

This audit classifies every bank, decodes the emitted graphics-transfer
programs and compares their literal payloads with existing graphics tables.
It checks all 14,618 compiled CALL/JP relocation sites against build metadata.
It does not establish gameplay timing, hardware mapper compatibility or
equivalence of a future repacked ROM. SCREEN 5 is a separate 2 MiB baseline;
the packing model below applies to the maintained full-session SCREEN 4 build.

The [metadata snapshot](issue36-rom-audit.json) contains counts, hashes and
allocation ranges only. Original ROMs, graphics and complete generated audit
reports remain under ignored `references/issue36/`.

## Whole-ROM allocation

These are allocated bank sizes, including internal gaps, not payload sizes.

| Owner | Banks | Bytes |
| --- | ---: | ---: |
| Resident code | 1 | 16,384 |
| Initial terrain and map | 3 | 49,152 |
| Phase HUD tables and embedded workers | 64 | 1,048,576 |
| Compiled HUD transfers | 100 | 1,638,400 |
| Initial boundary packets | 3 | 49,152 |
| Native game, player data, audio and navigation | 4 | 65,536 |
| Round terrain and maps | 12 | 196,608 |
| World-edge tables | 32 | 524,288 |
| Compiled world-boundary transfers | 18 | 294,912 |
| Session image, data, resident module, cold module and decor | 5 | 81,920 |
| Cold startup replay streams | 12 | 196,608 |
| Shared boot/HUD worker | 1 | 16,384 |
| **Total** | **255** | **4,177,920** |

There are no identical complete banks. The 448,271 bytes of trailing `FF` and
17,382 bytes of trailing zero candidates are not automatically free space:
fixed-address fields and intentional table padding must remain protected.

## Largest opportunity: reuse the graphics already in the mapped bank

| Transfer family | Pointer entries | Unique programs | Code bytes | Inline graphics bytes |
| --- | ---: | ---: | ---: | ---: |
| HUD | 4,096 | 2,887 | 296,861 | 1,310,922 |
| World boundary | 288 | 260 | 77,850 | 177,428 |

The compiled transfer programs duplicate **1,488,350 bytes** of graphics that
already exist in raw tables. Every proposed alias was compared byte for byte
with its existing inline source. Normalizing code pointers finds only 20 bytes
of additional identical-program savings; deduplicating whole programs is not
the useful optimization here.

HUD programs can use pattern/color data in their destination phase bank.
Boundary programs can use the corresponding world-edge bank. Moving their
instructions into gaps in those same banks allows `LD HL` to point at the
existing table, preserving the transfer instruction sequence and span lengths.
The model places 375,166 code bytes, including copies needed for phase-local
execution, with **zero spills** into new banks.

The simulation protects the padded phase name/pattern/color tables, old
atlases, name-upload code, pointer tables, radar/probe fields, complete cost
blocks, the bank-4 ring worker and the first `0x2920` bytes of each world-edge
bank. It does not rely on deleting old graphic assets. After placement,
347,060 bytes remain in fragmented holes; 335,781 bytes are in holes at least
260 bytes long.

Removing the 118 dedicated transfer banks would project a **2,244,608-byte**
image. This is an allocation model, not a linked ROM. Existing bank/address
consumers and the linker must be adapted and verified before any saving is real.
No additional active-transfer instructions are needed by the proposed alias
design; complete-frame costs and synchronization remain unmeasured.

## Reuse the remaining holes for cold replay

The existing startup codec already supports a bank/address chain and same-bank
literal references. The audit expands all 71 replay records, verifies the
239,262-byte unshared and 182,392-byte encoded stream accounting, then simulates
packing unchanged command spans into the remaining graphics-bank holes.

The simulated encoded stream occupies 186,591 bytes in 52 fragments, using
51 chains instead of 11. It fits without the current 12 dedicated replay banks.
The projected combined image is **2,048,000 bytes**, or 125 banks
(1.953125 MiB), with **49,152 bytes below 2 MiB**. This would save 2,129,920
bytes (about 51%) from the baseline. The two savings are sequential and must
not be added again to the duplicated-literal byte count.

More chains and changed literal reuse affect cold execution. This simulation
checks storage capacity, not VDP destinations, register effects, skip behavior
or native replay deadlines. Validate all of those on an actual repacked build.

## Ranked alternatives and deferred cleanup

1. **Same-bank graphics aliases and code packing:** largest useful saving,
   preserves every graphics byte and the active transfer instruction sequence.
   Prototype this first; update all bank/address consumers explicitly.
2. **Existing-codec cold replay packing:** completes the modeled path below
   2 MiB without a new decompressor. Verify boot frame timing and skip handling.
3. **Superseded atlas/packet removal:** the legacy R18 atlas accounts for 49,216
   bytes of phase fields; base boundary atlas reservations account for 196,608
   bytes; initial boundary packets reserve three banks. These are candidates,
   not proven dead resources. Conditional/standalone presenters and generated
   callers need separate reachability proof. They remain in the model above.
4. **Raw tile dictionaries:** HUD pattern/color repetition is 16,576 bytes and
   world-edge repetition is 30,144 bytes, before dictionary overhead. Sharing
   these requires tile-ID/address changes and possibly reconstruction work;
   returns are much smaller than eliminating transfer literal duplication.
5. **Fewer cached transitions or runtime decompression:** defer. Restricting
   cached HUD transitions to matching X/Y parity models only 30 program banks,
   but sends 3,072 transition pairs through a fallback and changes timing.
   Filtering programs already slower than the full-copy heuristic removes none.
   No performance or perceptual concession is justified by this storage audit.

## Reproduction and implementation acceptance

With the contributor-provided inputs and the existing virtual environment:

```sh
make build
.venv/bin/python -B -m scripts.msx.cartridge_size --rom references/experiments/full-session/fixed-hud.rom --bundle references/experiments/full-session --output references/issue36/size-ledger.json --build-command 'make build'
.venv/bin/python -B src/screen4/rom_audit.py --output references/issue36/graphics-audit.json
.venv/bin/python -B -m unittest discover -s tests -p test_cartridge_size.py
.venv/bin/python -B -m unittest discover -s src/screen4 -p 'test_*.py'
```

The graphics audit records the checkout and hashes of its relevant source and
bundle metadata. The tool intentionally recognizes the current full-session
layout and rejects unaccounted banks or compiled relocations; it is not a
general-purpose arbitrary-ROM optimizer.

Before accepting an implemented layout:

- Independently compare every HUD/boundary transition's writes and pixels,
  including all rounds, phase changes, sprite/HUD interactions and fallback paths.
- Verify all 71 boot states, timing, native deadlines, skip and input behavior.
- Build default, test and legacy profiles; verify unrelated ROM contracts.
- Measure the matched three-moving-enemy workload with HUD enabled and the
  existing CPU/video settings. Record ROM hash, calls, inclusive/self cycles,
  mean/tail/maximum costs, synchronization waits and presentation rate.
- Add the requested size gate before publication, with failed builds preserving
  the last valid artifact. Keep the 2 MiB target and 4 MiB hard limit distinct.
- Verify ASCII16 bank relocation/address assumptions in the actual linker and
  emulator. Physical-cartridge compatibility remains an explicit open check.

The read-only audit changes no game ROM. Its synthetic tests cover inventory
boundaries, emitted transfer decoding, exact aliases, protected holes, replay
references, cyclic-chain rejection and packing overflow. Emulator equivalence
and performance acceptance belong to the subsequent implementation.

Audit verification: five inventory tests passed; the SCREEN 4 component suite
ran 77 tests with 76 passing and one explicit emulator-dependent skip. The ROM
hash remained identical after the scan. All 255 banks and 14,618 compiled
relocations were accounted for.

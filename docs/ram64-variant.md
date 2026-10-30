# 64 KiB default cartridge

The default full-session cartridge uses 64 KiB of system RAM and 128 KiB VRAM.
`MAPPER=1` preserves the version requiring at least 128 KiB of mapper RAM.
Both cartridges use ASCII16 and remain **2,048,000 bytes**, 125 banks.
System RAM is independent of cartridge Flash capacity and VRAM.

```sh
make build
make run
make build MAPPER=1
make run MAPPER=1
# Use the unexpanded Panasonic machine definition:
NRX_REFERENCE_MACHINE=Panasonic_FS-A1FX make run
```

| Profile | Bundle / exported filename | SHA-256 |
| --- | --- | --- |
| Default, 64 KiB | `references/experiments/full-session-64k/fixed-hud.rom`; `outputs/test-roms/newrallyx-screen4-full-game-64k.rom` | `661c41bd7332fee8b06bef03a20555a44863435fc13747e8150f738c32cc13a5` |
| `MAPPER=1`, 128 KiB | `references/experiments/full-session/fixed-hud.rom`; `outputs/test-roms/newrallyx-screen4-full-game.rom` | `b80c7b72ace0ee0e9686127a156249d3cceaa3292ddea767ad1497950badbfb1` |

The launcher selects a private FS-A1WSX_NR64 or FS-A1WSX_NR128 definition and
checks actual mapper capacity. It never edits installed machine definitions.
Verification tools read `session-build.json` and reject conflicting RAM
overrides. The 64 KiB profile still uses the standard MSX RAM-mapper port
interface; arbitrary unmapped 64 KiB memory is not the same configuration.
The bracketed ` [ASCII16].rom` export is byte-identical for WebMSX selection.
The old `RAM_KB` flag fails with guidance; use `MAPPER=1` or omit it.

## Storage and calling contract

Four physical 16 KiB RAM segments contain main Page0 state, the two unchanged
world-map halves and Page3 state/stack/IM2. Bootstrap masks FC/FF readback with
`3`, allocates two map segments, and omits two separate flag-cache segments.
This removes the Page3 alias behind the [original startup failure](fs-a1fx-ram-start.md).

| Storage | Ownership and lifetime |
| --- | --- |
| Main Page0 `3800..3FFF` | Eight 256-byte CPU records, one per VRAM pattern set. Navigation remains at `3000..37FF`. |
| Each of eight VRAM sets, `+1000..17FF` | Eight immutable 256-byte slots per set; 64 phases, 16 KiB total. The first 242 bytes of each slot are used. |
| CPU record offsets `F2/F3` | Mutable phase-valid key and S-blink key, outside the immutable payload. |
| `C0D3`, `GameSession_AnyCaptured` | Boolean alias of the unused 128 KiB flag-segment variable; initialized from ten native flags and set on capture. No new RAM allocation. |

Record payload: count at 0, executable names at 1..51, pattern bytes at 52..131,
color bytes at 132..211, ten offset/reserved/mask triples at 212..241. The record
page is implicit in H; stored metadata high bytes are not dereferenced.

VRAM records avoid patterns `+0000..07FF`, names `0800/0C00`, colors
`+2000..27FF`, sprite colors/SAT `1800..1A7F` and sprite patterns `2800..2E3F`.
SCREEN5 UI owns all VRAM. Every `GameSession_Video` return to SCREEN4 rebuilds
the immutable cache with display disabled, including challenge-reveal resume.

`GameSession_EnsureFlags` requires main Page0 mapped, current phase/back set,
and foreground VDP ownership. It clobbers AF/BC/DE/HL/IX/IY and leaves
`Game_RadarCount` unchanged. A miss reads 242 bytes with paced, unrolled `INI`,
applies captured masks when needed, then applies the original S blink.
Foreground entry has interrupts enabled; address setup restores enabled IFF
as in `GamePattern_Address`. IRQ handlers may read status but must not change
the foreground VDP data pointer. The read worker requires BC=`F298`, returns
B=0 and HL advanced 242 bytes, with H unchanged. Default worker range is
`2C7C..2E60`, within the existing startup-worker reservation below `3000`.

Collection clears the known bit in every valid CPU record. Refill applies
native active flags so collected dots cannot reappear; blinking never restores
a collected S. Actor overlaps retain the original color merger and full glyphs.
Flag-name execution tail-returns to its original caller. Direct 16-byte glyph
copies and paced uploads require main Page0 and the inactive target set.

The motion adapter keeps the existing 44-byte snapshot buffer, stack and
register ownership. It looks ahead six native motion units on both axes before
allowing the existing corner rollback; unrolled copies still finish with BC=0.
No fuel, score, enemy state or native clock is added to the rollback scope.

`session_ram64.py` transforms an ignored assembly view with checked anchors.
The preserved 128 KiB source view stays byte-identical. This functional adapter
is separate from source-only module extraction: `make verify-module-layout`
checks the frozen 128 KiB counterpart, not a claim of identical 64/128 ROMs.

See the [validation and timing report](ram-profile-validation.md), current
[workbook](cycle-budget.xlsx), and [comparison ledger](measurements/timing/ram-profile-comparison.json).
The earlier [64 KiB trial metadata](measurements/hardware/ram64-variant.json)
remains historical and explicitly identifies its older `428a775d...` ROM.

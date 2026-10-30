# Start failure on an unexpanded 64 KiB Panasonic

The user reported a black screen after coin/start on an original, unexpanded
Panasonic FS-FX with a physical RBSC MultiMapper v3.0 configured as ASCII16.
The selected file is `references/experiments/full-session/fixed-hud.rom`:
2,048,000 bytes, SHA-256
`b80c7b72ace0ee0e9686127a156249d3cceaa3292ddea767ad1497950badbfb1`.

The investigated cartridge requires **at least 128 KiB of system RAM with a memory
mapper**, separately from **128 KiB VRAM** and the cartridge's Flash storage.
An ASCII16 ROM mapper does not supply the required system RAM.

## Controlled reproduction, 2026-10-29

Using openMSX 21.0, contributor-supplied BIOS and the
[FS-A1FX machine definition](https://raw.githubusercontent.com/openMSX/openMSX/master/share/machines/Panasonic_FS-A1FX.xml),
with the exact same cartridge, keyboard sequence, 3,579,545 Hz CPU and 128 KiB VRAM:

| System RAM | Observed result |
| --- | --- |
| Original 64 KiB | Cast/title, coin and intro states reached; start hangs during cold map loading. Gameplay/movement never reached. |
| Session-local 128 KiB mapper | Cast/title, coin, intro, gameplay and movement reached successfully. |

The 128 KiB variant changes only RAM capacity and the corresponding mapper
readback bits. The reproduction uses actual keymatrix input and read-only
debugging; no replacement guest routine or injected game state is used.
The [metadata evidence](measurements/hardware/fs-a1fx-ram-start.json) records
hashes, snapshots and the alias trace. Raw snapshots and probes remain ignored
under `references/issue36/hardware-repro/` and the generated session directories.

## Cause

64 KiB contains four physical 16 KiB RAM segments. The investigated bootstrap assumes
at least eight and masks the mapper readback with `7`. With the original
64 KiB readback behavior, the selected map destination aliases the physical
segment containing Page3 state, interrupt vectors and stack. The real map copy
overwrites the vector table at CPU address D000. Its subsequent stack overwrite
prevents a valid return; the display, disabled for cold loading, stays black.

With 128 KiB, the same allocation chooses distinct physical segments and the
same start path succeeds. This establishes insufficient RAM as a fatal condition
for the reported unexpanded configuration; it does not certify the multicart's
firmware or programming readback on actual hardware.

The emulator launcher checks the minimum RAM, but the direct cartridge boot has
no equivalent refusal/message yet. A clearer hardware error screen is a separate
behavior change; this investigation leaves the production ROM untouched.
Supporting 64 KiB would require changing map/cache storage and then revalidating
graphics, timing and ROM-size budgets. It is not achieved by changing the ASCII16
jumper or padding/reflashing the same image. This is not caused by the source-only
module extraction: the affected binary is identical to its pre-extraction version.

The [64 KiB default cartridge](ram64-variant.md) now adapts allocation and cache
storage. It has its own filename/hash and validation; this historical failure
still describes the preserved 128 KiB image selected with `MAPPER=1`.

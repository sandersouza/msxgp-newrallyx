# SCREEN 5 legacy presenter and shared Z80 helpers

This directory contains the 73 authored assembly/include files formerly stored
directly under `src/`. Their source bytes and assembly INCLUDE names are
unchanged by the move. [The migration ledger](../../docs/screen5-migration.json)
records paths, hashes and validation; [the architecture](../../docs/architecture.md)
describes the maintained SCREEN 4/5 integration.

## Build and launch

```sh
make build LEGACY=1
make run LEGACY=1
```

Lowercase `legacy=1` is equivalent. The legacy cartridge remains
`references/build/newrallyx.rom`; fresh sealed build directories and the latest
legacy publisher keep their existing paths. HUD and PSG are enabled in the
default full-game legacy build. TEST_MODE=1 belongs to SCREEN 4 and is rejected
with LEGACY=1. Maintained bounded-stage flags also require LEGACY=1.

The legacy build/launch owners remain `scripts/project.py` and
`src/toolchain/msx/raster_scroll.py`. Native diagnostic builders remain in
`src/toolchain/msx/native_build.py`. Shared Python asset/reference tools and their
tests stay in `scripts/` and `tests/`; they serve both presenters.

## Source ownership

`raster-scroll.asm` is the legacy assembly entry point. The `native-*` files
provide the maintained native-loader/runtime diagnostics; the `full-*` files
provide complete-session, round, terrain, enemy and audio support. The other
includes retain their existing player, score, fuel, life, smoke, collision,
HUD/radar and publication contracts. Generators stage these files into ignored
assembly bundles using their unchanged basenames.

SCREEN 4 continues to reuse selected helpers from this directory. Its
`game_core.prepare()` defaults explicitly to `src/screen5/`. Complete-session
integration instead selects the original flat `src/` of the manifest-verified
pinned Git source view via `source_directory=`. The historical export is left
untouched, and a missing current directory does not silently select old sources.
Changing the integration revision still requires deliberate adapter validation.

No original ROM, extracted graphics, BIOS or generated cartridge belongs here.
Contributor inputs and raw emulator evidence remain ignored under `references/`;
generated exports remain ignored under `outputs/`.

# Port scaffold and resource ownership

The runtime source tree contains Z80 assembly and its module/HUD contracts.
Host tools are separate; moving files introduces no runtime dispatch or buffers.

| Location | Owner and lifetime |
| --- | --- |
| `src/screen4/` | Optimized Z80 presenter, adapters, assembly includes and module contracts |
| `src/screen5/` | Shared/legacy Z80 presenter and hardware helpers |
| `src/toolchain/screen4/` | SCREEN4 generator, linker transformations, emulator contracts, profiling and component tests |
| `src/toolchain/msx/` | Shared MSX conversion, assembly, cartridge, emulator and native-rule tooling |
| `src/toolchain/graphics/` | Arcade ROM inventory, decoding, guarded extraction and canonical promotion |
| `src/toolchain/scenes/` | Capture/replay, exact reconstruction and sealed input bundles |
| `src/toolchain/environment/` | Provisioning and pinned-tool verification |
| `src/toolchain/legacy/` | Maintained legacy generators and diagnostic drivers |
| `scripts/` | Public human/Makefile entry points only |
| `tests/` | Synthetic host tests; component tests also run through `make test` |
| `assets/` | User-supplied MSX bitmap and approved native-size arcade wordmark |
| `assets/arcade/nrallyx/` | Validated original indices, palette and extraction manifest |
| `assets/arcade/scenes/` | Two approved reconstruction inputs and five capture fixtures needed by the renderer |
| `assets/arcade/native/` | Three sealed native state acquisitions needed by conversion and accuracy checks |
| `assets/arcade/msx/<configuration>/` | Exact final linked resource banks and cartridge-offset/hash manifest |
| `dist/` | Delivered ROM and manifest; default is `dist/newrallyx.rom` |
| `references/roms/`, `references/msxbios/` | Contributor inputs; never downloaded by tools |
| Other `references/` outputs | Disposable build/cache/session evidence; remove with `make clean` |
| `docs/` | Maintained architecture, lessons, measurements, hashes and migration decisions |

Original pixels, captures, converted banks and ROMs remain ignored by Git. The
wordmark is `assets/namco-title-56x8.png`; it is verified at 56x8 against the
approved RGBA digest. The supplied `assets/msxlogo.bmp` remains 54x20 at 1:1.

## Extraction and conversion

`make extract-graphics` writes directly to `assets/arcade/nrallyx`. An explicit
`GRAPHICS_OUTPUT=references/assets/nrallyx` is supported as a temporary extraction.
Before conversion, the build validates and promotes that bundle to the canonical
location. It deletes an existing temporary copy only after checking that every
file equals the canonical copy; divergent or edited data is preserved with an
error. Unknown output files, tracked files and symlink output paths are rejected.

`make build` and normal `make run` invoke `prepare-assets` before linking. This
checks supplied ROMs and all canonical bundles, generates missing stages and the
wordmark, and stops on edited or incompatible data. `make extract-all` exposes
the same complete preparation explicitly. `make extract-scenes` (also
`make prepare-scenes`) produces canonical capture and reconstruction bundles.
Native state acquisition is regenerated from contributor ROMs when missing.
The former `references/scenes` and `references/stage-one` directories are not
active game input locations. Only their necessary small sealed inputs were
retained under `assets/arcade`; historical research outputs were removed.

A successful delivered build publishes the exact final nonresident 16KiB banks
under `assets/arcade/msx/<configuration>`. They contain the linker's actual packed
resources, including interleaved native code and padding, rather than re-encoded
preview pictures. The manifest records each bank's ROM offset and SHA-256, plus
the complete ROM hash. The resident bank belongs to the ROM in `dist`. Modified
or unrecognized resource publications are preserved rather than overwritten.

Pinned historical source exports retain their original authored bytes. A private
compatibility layout inside the disposable source cache hardlinks only the
explicit canonical inputs into the paths expected by that revision. This does
not restore old input directories in the working repository.

## Using and maintaining the scaffold

Run `make environment-check`, `make extract-graphics`, `make prepare-scenes`,
`make build`, `make test`, and `make verify-module-layout` as appropriate.
`make run` uses the delivered default ROM; `MAPPER=1` selects 128KiB in openMSX
without selecting another ROM. The default remains compatible with 64KiB.
All cartridge publications enforce the 2,097,152-byte maximum.

`src/toolchain/screen4/source_paths.py` resolves runtime include files separately
from host-tool siblings. New tooling should use that resolver instead of assuming
that Python modules and assembly includes occupy the same directory. Local CLI
entry points initialize their import path so they also work outside the repo cwd.

Keep emulator proof commands that verify live contracts, bounded workloads and
reusable conversion methods. Retire one-off report drivers once their result and
method are documented. `docs/toolchain-migration.json` lists every moved or
retired tool, its previous hash and the reason for retirement. Do not retain raw
experiment trees as an archive. Record compact evidence in docs, then clean.

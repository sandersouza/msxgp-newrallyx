# Host tools

This tree runs on the development computer. It is not assembled into the MSX
runtime. SCREEN4-specific generators and validators live in `screen4`; shared
MSX conversion/linking/emulation in `msx`; arcade decoding in `graphics`; sealed
capture/reconstruction in `scenes`; machine provisioning in `environment`.
`legacy` retains shared older presenter generators and useful diagnostic CLIs.

Use the public Makefile targets and scripts first. Internal probes are retained
when they test maintained contracts or provide a reproducible bounded workload.
Their raw ROMs, traces and screenshots are disposable; document the method and
compact results under `docs` before cleaning. Both host and component unit tests
are included in `make test`.

See [repository layout](../../docs/repository-layout.md),
[developer guide](../../docs/developer-guide.md), and
[migration inventory](../../docs/toolchain-migration.json).

`src/toolchain/graphics/prepare.py` orchestrates the complete absent-input path.
The public `scripts/prepare_assets.py` entry point is invoked by build targets
before either linker, and by `make extract-all`. It validates contributor ROMs,
reuses sealed compatible bundles, regenerates missing stages, and stops on edited
inputs. See [first-build instructions](../../docs/building.md).

For a first build, follow [Build your first MSX ROM](building.md). Missing arcade assets are prepared automatically by `make build` and `make run`.

# Development environment

From the repository root, run:

```sh
make environment
```

The Makefile invokes `scripts/setup.sh` through Bash. The dispatcher identifies
macOS (Darwin), Linux (including WSL), Windows shells (MINGW/MSYS/CYGWIN or the
Windows_NT environment fallback), and unknown systems. Only macOS has an
implementation today. Other platforms fail before installation. Native Windows
make/shell prerequisites and provisioning belong to a future implementation.

## Current build and launch selection

After supplying the original arcade ROMs (and BIOS for openMSX), run commands from the intended checkout:

| Command | Selection |
| --- | --- |
| `make build` / `make run` | Default integrated SCREEN 4 gameplay, SCREEN 5 menus, HUD and PSG enabled |
| `make build MAPPER=1` / `make run MAPPER=1` | Same automatic ROM; run selects128 KiB emulator RAM |
| `make build TEST_MODE=1` / `make run TEST_MODE=1` | Separate optimized test ROM; Enter advances a round, equals toggles collision invulnerability; walls remain solid |
| `make build LEGACY=1` / `make run LEGACY=1` | Maintained SCREEN 5 sprite-HUD/PSG build; `legacy=1` is an alias |
| `make run ROM=<path>` | Existing cartridge, no rebuild |
| `make run CHECKPOINT=<name>` | Existing named local checkpoint, no rebuild |
| `make run LATEST=1` | Latest sealed legacy build, no rebuild |

Unqualified `run` rebuilds even if its output already exists. Test mode is rejected
with `LEGACY=1`. `STAGE`, `FULL_GAME`, `AUDIO` and `HZ` select legacy diagnostics;
use `LEGACY=1` with those flags. The optimized complete session uses native enemy
progression; `ENEMIES=3` selects the earlier first-stage benchmark, not a complete
session population override. `make run-experiments` remains a default-presenter
alias; see [all build profiles](../src/screen4/BUILD-PROFILES.md).

The default optimized artifact is `references/experiments/full-session-64k/fixed-hud.rom`
(or `full-session-test-64k/` for test mode). `MAPPER=1` selects `full-session/`
or `full-session-test/`. Exports in `outputs/test-roms/` include
an identical copy ending in ` [ASCII16].rom`; retain that filename hint when
loading through WebMSX AUTO, or explicitly select ASCII16. Export manifests
record both names and the SHA-256. Legacy builds publish
`references/build/newrallyx.rom` separately.

The optimized source integration depends on local Git commit
`6d562a791b0cc242119a31dd686ff8e93eb94fe0`. A verified source view under
`references/experiments/source-views/` is rebuilt without changing the checkout.
Do not substitute another revision silently or edit cached source exports.
See [source ownership](architecture.md#build-ownership),
[graphics regeneration](graphics-extraction.md), [scene preparation](arcade-scenes.md)
and [maintenance/validation](maintenance.md). These procedures use contributor
inputs only; setup does not obtain game ROMs or BIOS.

## macOS prerequisites

The default requires **64 KiB system RAM and128 KiB VRAM**; `MAPPER=1` requires
**at least128 KiB mapper RAM**. Run and verification tools use private FS-A1WSX
definitions with exactly the selected capacity. Installed machine XML/global
settings stay untouched. Probes bind RAM capacity to `session-build.json` and
reject conflicting overrides, so a64 KiB claim cannot silently use128 KiB.

Both profiles require the standard RAM-mapper page interface; the64 KiB profile
is verified on stock Panasonic FS-A1FX and a private64 KiB FS-A1WSX. ASCII16
cartridge Flash does not add system RAM. The [original start failure](fs-a1fx-ram-start.md)
describes the unchanged128 KiB image on an unexpanded machine.

The default export is `outputs/test-roms/newrallyx-screen4-full-game-64k.rom`;
`MAPPER=1` exports `newrallyx-screen4-full-game.rom`. Both use ASCII16 and128 KiB
VRAM. Set `NRX_REFERENCE_MACHINE=Panasonic_FS-A1FX` to use the stock FX definition
with the default64 KiB build. See the [profile validation](ram-profile-validation.md).

Use a native Apple Silicon or Intel terminal and stock Bash 3.2 or newer. Install
[Xcode Command Line Tools](https://developer.apple.com/xcode/resources/) manually
with `xcode-select --install`, then complete the installer. GNU Make is supplied
by the developer tools. Install [Homebrew](https://brew.sh/) by following its
official instructions yourself; setup never runs its downloaded installer or sudo.

The selected developer directory is read with `xcode-select -p`. Make and Clang
are resolved directly under that directory (including the full Xcode default
toolchain layout). Setup also selects `SDKs/MacOSX.sdk` under Command Line Tools,
or `Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk` under full Xcode, and
exports that path as `SDKROOT` for the invocation. This replaces an inherited
SDKROOT so the compiler and SDK come from the same selected installation. Direct
Clang needs this explicit SDK selection to find the C++ standard library headers.
A missing SDK stops all modes with repair guidance before installation.
Setup does not use `xcrun` or `/usr/bin` developer shims for
its internal probes, because those can populate lookup caches even during checks.

Homebrew is discovered through PATH, falling back to `/opt/homebrew/bin/brew` on
Apple Silicon or `/usr/local/bin/brew` on Intel. Its actual prefix is obtained
with `brew --prefix`; package paths use that prefix. Rosetta shells and standard
prefix/CPU mismatches are rejected. Python's architecture is checked independently.
Custom prefixes must still contain Homebrew's standard `opt/<formula>/bin` layout.

The committed Brewfile declares Python 3.14, Git, GitHub CLI, z80dasm, MAME,
openMSX and ShellCheck. Setup installs
only missing formulae, disables automatic Homebrew updates/analytics, and does not
upgrade installed formulae. Installed Git must be at least 2.30 and GitHub CLI
at least 2.0. Older or broken installed tools require manual repair; macOS-supplied
executables do not satisfy the declared Homebrew dependency contract.

## Commands and Python contract

| Command | Behavior |
| --- | --- |
| `make environment` | Install missing packages, build/reuse pinned sjasmplus, verify synthetic cross-assembly, create/reuse `.venv` and verify pinned Python dependencies |
| `make environment-check` | Read-only requirements, toolchain, cached build evidence, ShellCheck, environment, import and pip checks; fail if unmet |
| `bash scripts/setup.sh --dry-run` | Read-only diagnostics and preview of planned changes |
| `bash scripts/setup.sh --help` | Show shell entry-point usage |

The shell entry point also supports `--check` and `--dry-run`. It resolves the
repository from its own location, including paths with spaces, so it can be
invoked by absolute path from another directory. Run Make targets from the root
or use `make -C /path/to/repository environment`.

Use `.venv/bin/python` for project scripts. Shell activation is optional:

```sh
.venv/bin/python -B -c 'from PIL import Image; print(Image.__version__)'
.venv/bin/python -B -m pip check
python3 -B -m unittest discover -s tests -v
```

Setup uses interpreter isolation and disables bytecode and pip cache/version-check
writes during verification. It avoids Homebrew `bundle`, `info`, and `list` in
check/preview modes because those may fetch metadata. A missing `.venv` does not
get created by either read-only mode. Preview succeeds when changes can be planned,
but fails for manual prerequisites, incompatible environments or installed tools.

`requirements.txt` pins `Pillow==13.0.0`, used by the graphics extractor.
The [published release](https://pypi.org/project/pillow/13.0.0/) provides CPython
3.14 wheels for both macOS arm64 and x86_64. Setup accepts binary wheels only.
Pillow has no mandatory Python package dependencies in this environment.
Exact pins control Python package versions; Homebrew patch versions and pip's
bundled version may vary. This is not a bit-for-bit lock of system packages or
wheel hashes. Update the pin deliberately, inspect release metadata, then repeat
setup, checks, rerun and image validation on the supported hosts. No global pip
install or unconditional pip/package upgrade is performed.

GitHub authentication is a separate manual action when needed:

```sh
gh auth login
```

Setup does not authenticate, request tokens, or print stored credentials.

## Recovery and exit codes

- Missing Homebrew/Command Line Tools: finish the official installation and rerun.
- Rosetta/prefix mismatch: open a native terminal and use its native Homebrew.
- Old or broken formula: repair/update that specific formula manually and rerun.
- Existing incompatible, foreign, symlinked or incomplete `.venv`: preserve it by
  moving it to a backup location of your choice, then rerun. Setup never deletes
  or overwrites it. A moved repository or Homebrew Python replacement can require
  this recovery, even within the same Python minor release.
- Existing `.venv` with missing Homebrew Python: setup cannot establish base
  compatibility and stops before installation. Restore `python@3.14` manually,
  or preserve and move `.venv` aside before rerunning setup.
- Interrupted dependency install/network failure: correct connectivity/index
  configuration and rerun `make environment`. A valid `.venv` is reused and pinned
  dependencies are retried. A partial venv creation may require the backup step.
- `pip check` conflicts: resolve the reported local dependency conflict, or preserve
  and move the environment aside to create a fresh one.
- Unknown, changed or partial assembler directory: preserve and move the named
  `.tools/sjasmplus/<version>` directory aside. Setup never overwrites it.
- Invalid smoke cache: preserve and move the specific `.tools/smoke/<key>`
  directory reported by setup aside, then rerun. Other cached versions are retained.
- Homebrew reports unwritable directories while running in a managed execution
  session: run `make environment` from your normal terminal. This may be a session
  restriction, not an ownership problem; do not apply recursive chown/chmod merely
  because Homebrew suggests it.

Shell exit codes are 0 (success/help/valid preview), 1 (unmet prerequisites or
unsupported platform), 2 (usage), 3 (incompatible existing environment), and
4 (installation/final verification failure). GNU Make normally returns its own
nonzero code while printing the shell's code as `Error N`.

## Complete Z80 toolchain

| Purpose | Tool and provisioning |
| --- | --- |
| Host C++ build | GNU Make and Clang C++17 from Command Line Tools |
| Z80 cross-assembly, symbols/listing | sjasmplus 1.24.0, built locally from a pinned upstream commit |
| Static disassembly | Homebrew z80dasm |
| Original arcade execution/debugging | Homebrew MAME, with debugger available through `-debug` |
| MSX2+ execution/debugging | Homebrew openMSX |
| Shell static analysis | Homebrew ShellCheck, executed by setup/check |
| Extraction and ROM-processing scripts | Local Python/Pillow environment |

`src/toolchain/environment/toolchain-lock.json` pins sjasmplus version 1.24.0 to upstream
commit `d379eeac9ad3857fb48fd3a3929175d0a56038ce`. Setup clones the official release
tag and verifies the commit before running GNU Make with `USE_LUA=0`. The
[upstream installation instructions](https://github.com/z00m128/sjasmplus/blob/v1.24.0/INSTALL.md)
and [Makefile](https://github.com/z00m128/sjasmplus/blob/v1.24.0/Makefile) support
this source build. Disabling Lua avoids optional LuaBridge/test submodules; Z80
assembly, symbols and listings remain enabled. Projects using embedded assembler
Lua would need a deliberate toolchain update. No system `make install` is run.

The managed executable is `.tools/sjasmplus/1.24.0/sjasmplus`, with a provenance
file containing the locked source information and binary SHA-256. Existing
installations are reused only when provenance, hash and version agree; a random
sjasmplus on PATH is not substituted. Build temporary files are removed by the
invocation that created them. Installed tools from this mechanism are not added
to global PATH. Use the managed executable by its explicit path in future builds.

`tests/fixtures/toolchain-smoke.asm` is entirely synthetic. Setup assembles a
16 KiB MSX cartridge with an `AB` header, entry at `$4010`, known Z80 instructions
and `$ff` padding. It compares every byte, requires symbols/listing, and runs
z80dasm on the nine instruction bytes. The code writes `$42` to `$c000` and loops;
it is an assembler check, not an emulator boot or game build.

Build outputs and a hash manifest are cached under `.tools/smoke/<key>`. The key
covers the source, assembler, disassembler and verification recipe. A compatible
rerun reuses this evidence. `make environment-check` only reads and validates it;
it never compiles or creates temporary files. Changed inputs require a new setup
run; corrupt existing output is preserved and reported for manual recovery.

Emulator probes use `mame -help` and `openmsx --version`, without starting a machine.
Setting up an MSX2+ machine's user-supplied BIOS and running the cartridge remain
separate from provisioning. No proprietary BIOS or game ROM is obtained by setup.
The [MAME debugger manual](https://docs.mamedev.org/debugger/index.html) and
[openMSX CLI manual](https://openmsx.org/manual/user.html) cover later debugging.
Homebrew provides [openMSX](https://formulae.brew.sh/formula/openmsx),
[z80dasm](https://formulae.brew.sh/formula/z80dasm),
[MAME](https://formulae.brew.sh/formula/mame) and
[ShellCheck](https://formulae.brew.sh/formula/shellcheck); bottle support varies by
OS/architecture. C/SDCC compilation is not required for this Z80 Assembly workflow.

## Machine and contributor-supplied BIOS

Local validation uses openMSX **21.0**, session-local `Panasonic_FS-A1WSX_NR64`
and `Panasonic_FS-A1WSX_NR128` configurations, V9958 with 128 KiB VRAM and the
selected 64/128 KiB main RAM mapper. The launcher derives these configurations
from `Panasonic_FS-A1WSX`; the stock FS-A1FX is also checked for the 64 KiB build.
The launcher follows
the machine's CPU clock, sets emulator speed 100%, firmware off and a 212-line
display. The full game detects factory Panasonic turbo and uses **5,369,318 Hz
for pure CPU work, 3,579,545 Hz for VDP access and raster IRQs**. Unsupported
machines keep their base clock. In openMSX, `z80_freq_locked true` follows
hardware clock switching; `false` forces the user's frequency override. The
bounded reference retains its original base-clock behavior. The full-game default
sets 60 Hz through VDP R9; bounded stages retain 50 Hz. `make build LEGACY=1 HZ=50` selects
an explicit full-game 50 Hz diagnostic. BIOS calls require an MSX2 or later machine; the recorded
integration target is MSX2+.

Supply compatible system ROMs under `references/msxbios`. The launcher adds
that directory as a session-local `system_rom` file pool **before** loading the
machine. openMSX resolves files by the machine definition's SHA-1, recursively;
renaming files or copying BIOS into a global emulator directory is unnecessary.
The launcher isolates `OPENMSX_HOME` and `OPENMSX_USER_DATA` inside the run output,
disables saving settings and leaves global emulator configuration untouched.

These split ROMs are the compatible inputs for the selected machine:

| Filename in machine definition | SHA-1 |
| --- | --- |
| `fs-a1wsx_basic-bios2p.rom` | `f4433752d3bf876bfefb363c749d4d2e08a218b6` |
| `fs-a1wsx_msx2psub.rom` | `fe0254cbfc11405b79e7c86c7769bd6322b04995` |
| `fs-a1wsx_fmbasic.rom` | `aad42ba4289b33d8eed225d42cea930b7fc5c228` |
| `fs-a1wsx_kanjibasic.rom` | `dcc3a67732aa01c4f2ee8d1ad886444a4dbafe06` |
| `fs-a1wsx_disk.rom` | `7ed7c55e0359737ac5e68d38cb6903f9e5d7c2b6` |
| `fs-a1wsx_firmware.rom` | `3330d9b6b76e3c4ccb7cf252496ed15d08b95d3f` |
| `fs-a1wsx_kanjifont.rom` | `5aff2d9b6efc723bc395b0f96f0adfa83cc54a49` |

openMSX also accepts combined IC18/IC17 dumps and an alternate FM-BASIC hash;
see the installed `share/machines/Panasonic_FS-A1WSX.xml` for alternatives.
Local supplied combined dumps have SHA-1 `28cc0fbab62d9b4ff5d16971795ebb8a4e02f1f6`
and `9da0306506640ea89acaa9516cb836233a9221ec`, respectively. These identifiers are
metadata only. No BIOS payload belongs in Git.

On missing/mismatched BIOS, inspect the run's `emulator.log`: openMSX identifies
the failed ROM lookup and the launcher reports the selected machine/BIOS
diagnostic. Verify hashes against that machine's XML, or use the renderer CLI
options `--machine` and `--bios` with compatible contributor-supplied inputs. No global settings edits
or BIOS downloads are required. A first-run missing `firmwareswitch` persistent
file warning is expected in the isolated, initially empty home directory.

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

## macOS prerequisites

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
| `make environment-dry-run` | Read-only diagnostics and preview of planned changes |
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

## Validation evidence — 2026-10-20

Current result: the complete environment is ready on the arm64 host below.
The earlier blocked attempts are retained as historical evidence.

- `make environment`: built real sjasmplus 1.24.0 from the locked commit and
  verified the synthetic 16 KiB cartridge byte for byte, symbols, listing and
  real z80dasm output. openMSX 21.0 and ShellCheck 0.11.0 are now installed.
- The first resumed native build failed with `fatal error: 'cassert' file not
  found`. Direct Clang lacked an SDK selection; the header exists in the selected
  macOS SDK. Explicit `SDKROOT` fixes the build without reintroducing developer
  shims or their external cache writes. Three regressions observed RED then GREEN
  cover Command Line Tools, full Xcode and a missing SDK.
- `make environment-check`, `make environment-dry-run` and a second
  `make environment`: all passed. SHA-256, symlink-target and file-mtime snapshots
  of `.venv/` and `.tools/` were unchanged across each command; no rebuild,
  dependency reinstall, upgrade or environment replacement was needed.
- `.venv/bin/python -I -B`: real Pillow 13.0.0 import and in-memory PNG round
  trip passed; pip 26.2.1 reports no broken requirements.
- `python3 -B -m unittest discover -s tests`: 41 tests passed. Real ShellCheck,
  Bash syntax and `git diff --check` passed. Generated tools, environment and
  reference ROM paths remain ignored. Native Intel/full Xcode are still simulated;
  emulator probes check help/version only, without a machine or BIOS boot.

### Earlier attempts and review history

Observed host: macOS 27.0.1 arm64, stock Bash 3.2.57, Python 3.14.7,
Git 2.55.0, GNU Make 3.81, Apple Clang 21.0.0, z80dasm 1.2.0, MAME 0.289.
Latest inspection found Homebrew 7.0.10 and GitHub CLI 2.102.0; earlier extraction-only
validation observed Homebrew 7.0.6 and GitHub CLI 2.98.0. Command Line Tools are present.

- `python3 -B -m unittest discover -s tests -v`: 38 tests passed. Shell tests use
  isolated executable stubs; Python verification tests use real temporary venvs
  and synthetic dependency metadata/import modules. Toolchain tests simulate clone,
  compiler, assembler and emulators; the real installed z80dasm also successfully
  disassembled the synthetic code. This does not validate the real sjasmplus build.
  No game data is used.
- `bash -n scripts/setup.sh scripts/environment/macos.sh`: passed.
- `make environment-dry-run`: passed on the real host without installation.
- `make environment-check`: correctly reports missing openMSX/ShellCheck after
  scope expansion. Earlier extraction-only checks also detected missing `.venv`
  and Pillow. The installed z80dasm requires `-V`; its broken long version flag
  was detected on the host and is covered by a regression test.
- `PIP_RETRIES=0 PIP_TIMEOUT=8 make environment`: created `.venv` and failed at
  Pillow installation, preserving the environment. A second run reused it and
  failed at the same dependency step. DNS/network access is restricted here;
  `curl` could not resolve pypi.org. The successful dependency installation and
  no-op rerun are covered only with stubs, not verified end to end on this host.
- Expanded `make environment`: stopped at `brew install openmsx` because this
  execution session cannot write Homebrew's directories. openMSX, ShellCheck and
  the real pinned assembler remain uninstalled here. No claim is made that the
  real compiler, real assembler, full toolchain lint, or emulators passed validation.
- `.venv/bin/python -I -B -m pip check`: found no broken requirements, but this
  environment contains no Pillow; this does not demonstrate a ready environment.
- ShellCheck is not installed, so static analysis remains pending. When available:
  `shellcheck -s bash scripts/setup.sh scripts/environment/macos.sh`.
- Follow-up after the user's local installation: real ShellCheck exposed SC1007
  on three empty CDPATH assignments. Explicit `CDPATH=''` fixed the warnings;
  actual ShellCheck and Bash syntax checks now pass. The earlier unavailable-tool
  result above is historical, not the current static-analysis status.
- Native Intel and other macOS versions remain unverified. Routing/architecture
  cases are simulated; this is not a physical-platform validation matrix.
- Independent review found a missing-base-Python environment-validation gap; a
  regression test now verifies that all modes preserve the existing environment
  and stop with recovery instructions. The two standard Homebrew fallback
  locations are implemented but do not have isolated automated coverage; tests
  supply brew on PATH and exercise discovery through its custom prefix.
- Toolchain review caught an external xcrun cache write in read-only modes;
  direct compiler/Make resolution replaces that lookup, and a regression checks
  the external cache as well as repository files. Another regression ensures
  dry-run reports a corrupt smoke-cache recovery blocker consistently with setup.

To repeat host validation, run `make environment`, `make environment-check`, and
`make environment` again, then a synthetic image round trip:

```sh
.venv/bin/python -B -c 'from io import BytesIO; from PIL import Image; b=BytesIO(); Image.new("RGB", (2, 2), "red").save(b, format="PNG"); b.seek(0); im=Image.open(b); assert im.size == (2, 2) and im.getpixel((0, 0)) == (255, 0, 0); print("PNG round trip passed")'
```

`.venv/`, `.tools/`, bytecode/cache files and reference data remain ignored. Tools, tests,
requirements and documentation are suitable for version control.

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

`scripts/environment/toolchain-lock.json` pins sjasmplus version 1.24.0 to upstream
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

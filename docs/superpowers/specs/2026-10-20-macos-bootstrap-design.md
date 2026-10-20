# macOS bootstrap design — issue #2

Status: design and implementation plan approved on 2026-10-20; implementation and
independent code review complete locally. Full host dependency validation and
ShellCheck remain blocked as recorded in docs/setup.md.
Issue: https://github.com/sandersouza/msxgp-newrallyx/issues/2

## Purpose and scope

Prepare a repeatable local environment for the graphics extractor in issue #1.
Support native Apple Silicon and Intel macOS installations using stock Bash 3.2.
Keep original game data under the existing ignored reference directories.
Do not implement extraction, install system prerequisites with elevated privileges,
authenticate GitHub, or obtain ROMs or BIOS files.

## Approach

Use a small Bash entry point, a Brewfile, and an exactly pinned Python dependency
file. This keeps the environment inspectable without introducing another package
manager. Alternatives considered: a manual-only checklist fails the repeatability
requirement; introducing uv adds a dependency without a current consumer need.

The public interface is `make environment`. A portable Makefile invokes the
dispatcher through `bash`, without assuming `/bin/bash` on future Windows hosts.
The dispatcher identifies Darwin, Linux, Windows shells (MINGW/MSYS/CYGWIN and
Windows_NT), and unknown systems, and prints the detected platform. Only Darwin
dispatches to an implementation today. Other systems fail with a clear unsupported
platform message before any mutation. WSL is identified as Linux. Native Windows
execution will need a future implementation and documented make/shell prerequisites;
this issue does not claim native Windows support.

Proposed files:

- `Makefile`: public environment, environment-check, and environment-dry-run targets.
- `scripts/setup.sh`: OS detection, argument validation, and platform dispatch.
- `scripts/environment/macos.sh`: macOS diagnostics, check, preview, and installation.
- `Brewfile`: `python@3.14`, `git`, and `gh`.
- `requirements.txt`: an exact Pillow release selected and verified during
  implementation, with its supported Python version and update policy documented.
- `tests/test_setup.py`: standard-library tests with synthetic executable stubs.
- `README.md` and `docs/setup.md`: entry commands, recovery, and validation evidence.
- `.gitignore`: add environment/cache exclusions while preserving existing rules.

Use Python 3.14, already installed on the validation host. Declare that minor
version explicitly; permit security/patch updates without requiring a fixed
Homebrew revision. Pin Pillow exactly for repeatability. No unbounded pip upgrade
or global pip install is permitted. Document deliberate dependency updates and
their required validation. Resolve the exact Pillow pin before implementation.

## Interface and behavior

- `make environment` (also `bash scripts/setup.sh`): install missing declared formulae, create or reuse
  `.venv`, install the declared Python dependencies, then verify the environment.
- `make environment-check` (also `bash scripts/setup.sh --check`): report requirements and versions; return
  nonzero for missing or incompatible components; never install or write files.
- `make environment-dry-run` (also `bash scripts/setup.sh --dry-run`): show diagnostics and intended changes;
  never install or write files. Missing manual prerequisites remain explicit.
- `--help`: explain usage; invalid arguments fail before mutations.

Resolve the repository from the script location so invocation works from another
directory. Disable Homebrew automatic updates and analytics for bootstrap calls.
Discover Homebrew through PATH and standard architecture-appropriate locations;
derive formula paths through Homebrew rather than assuming `/opt/homebrew`.
Check the OS, architecture, Command Line Tools, executable versions, and Python
venv/pip availability. Reject unsupported architectures with an actionable error.
Report Rosetta or prefix mismatches explicitly rather than selecting an unrelated
interpreter from PATH.

Missing Xcode tools or Homebrew produce official manual installation references
and rerun instructions. Never run sudo or a downloaded installation script.
Install only missing Brewfile packages, avoiding upgrades of installed formulae.
Check-only/preview must avoid Homebrew calls that download metadata or write caches.

Use `.venv/bin/python` for all project Python invocations, without requiring shell
activation. Verify Python minor version, environment ownership/location, pip, and
Pillow import/version. Do not silently replace an incompatible or broken `.venv`;
explain how the user can move it aside and rerun setup. Reuse compatible
environments and skip installation when the pinned dependency already passes.
Disable bytecode generation during read-only checks.

Return distinct nonzero results for usage errors, unmet manual prerequisites,
incompatible existing environments, and installation/verification failures. Print
the failing operation and a recovery step without credentials.

## Z80 toolchain — user-approved scope expansion

The user explicitly expanded the environment after the first implementation:
`make environment` must prepare the complete port toolchain, not only extraction.
This supersedes the earlier optional assembler/emulator boundary.

Required Homebrew tools now include z80dasm, MAME, openMSX and ShellCheck. Use
GNU Make and native Clang C++ from Command Line Tools. Build sjasmplus locally
at version 1.24.0 from commit d379eeac9ad3857fb48fd3a3929175d0a56038ce, with Lua
disabled. Verify the source commit before building, preserve unknown or modified
existing tool directories, and retain binary-hash/source provenance. Install no
global assembler and do not substitute an unrelated sjasmplus from PATH.

Setup must assemble an entirely synthetic 16 KiB MSX cartridge, verify every
byte against a known header/opcode/padding sequence, require symbols/listing,
and exercise z80dasm on its instruction bytes. Cache outputs by source, binary
and recipe hashes under ignored .tools. Check mode validates existing evidence
without compiling or writing temporary files; changed inputs require setup again.
Emulator diagnostics use non-launching help/version commands; machine/BIOS setup,
original game disassembly and the actual game build remain out of scope. No
proprietary system/game ROMs are included or downloaded. SDCC is not required
for the selected Assembly workflow. See docs/setup.md for the final behavior.

## Verification and delivery

Run Bash syntax checks and ShellCheck when available. Test missing prerequisites,
Linux, Windows, unknown OS, unsupported architecture, both Homebrew prefixes, paths containing spaces,
installation errors, incompatible environments, and repeat runs using stubs.
Assert that check and preview do not invoke mutating commands or change fixtures.
Perform real setup, check, preview, second setup, and a Pillow image round trip
using synthetic pixels on the available host. Confirm reference and environment
paths remain ignored. Record blocked checks accurately.

Observed host on 2026-10-20: macOS 27.0.1, arm64, Bash 3.2.57,
Homebrew 7.0.6, Python 3.14.7, Git 2.55.0, GH CLI 2.98.0; Command Line Tools
are present. This is discovery evidence, not a successful bootstrap validation.
Intel and other macOS releases remain unverified until actually tested.
The current execution sandbox blocks CLI network access and writes to Homebrew's
external cache. Do not bypass that restriction or report installation as tested.

When implementation starts, use `chore/2-macos-bootstrap` and set the project item
to In Progress if the available connection permits it. Preserve existing user
changes to AGENTS.md, .gitignore, and Makefile. Keep the local issue draft aligned
with material tracking changes. Do not commit, push, or close the issue without
the applicable delivery authorization and verification evidence.

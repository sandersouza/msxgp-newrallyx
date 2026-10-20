"""Synthetic host tools; never download or execute an emulator in unit tests."""

import hashlib
import json
from pathlib import Path
import shutil
import sys

COMMIT = "d379eeac9ad3857fb48fd3a3929175d0a56038ce"
VERSION = "1.24.0"
EXPECTED_ROM = b"AB\x10\x40" + bytes(12) + bytes.fromhex("f3 3e 42 32 00 c0 c3 10 40") + b"\xff" * (16384 - 25)


def executable(path, text, python=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(("#!" + sys.executable if python else "#!/bin/bash\nset -eu") + "\n" + text + "\n")
    path.chmod(0o755)


def create_tools(repo, prefix, bin_dir, env):
    env["FIXTURE_REAL_PYTHON"] = sys.executable
    env["FIXTURE_COMMIT"] = COMMIT
    env["FIXTURE_PREFIX"] = str(prefix)
    source = repo / "tests/fixtures/toolchain-smoke.asm"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('    org $4000\n    db "AB"\n    dw start\n    dw 0,0,0\n    ds 6,0\nstart:\n    di\n    ld a,$42\n    ld ($c000),a\n    jp start\n    ds $8000-$,$ff\n')
    executable(prefix / "tool-sjasmplus", '''import os, pathlib, sys
with open(os.environ["FIXTURE_LOG"], "a") as log:
    log.write("assembler " + " ".join(sys.argv[1:]) + "\\n")
if "--version" in sys.argv:
    print("1.24.0")
    raise SystemExit(0)
if os.environ.get("FIXTURE_ASSEMBLER_FAIL"):
    raise SystemExit(42)
rom = b"AB\\x10\\x40" + bytes(12) + bytes.fromhex("f3 3e 42 32 00 c0 c3 10 40") + b"\\xff" * (16384-25)
if os.environ.get("FIXTURE_BAD_ROM"):
    rom = b"wrong"
for argument in sys.argv[1:]:
    if argument.startswith("--raw="):
        pathlib.Path(argument.split("=",1)[1]).write_bytes(rom)
    if argument.startswith("--sym="):
        pathlib.Path(argument.split("=",1)[1]).write_text("start: EQU 0x00004010\\n")
    if argument.startswith("--lst="):
        pathlib.Path(argument.split("=",1)[1]).write_text("4010 F3 di\\n")
''', python=True)
    executable(prefix / "opt/git/bin/git", '''printf 'git %s\\n' "$*" >> "$FIXTURE_LOG"
case "$1" in
 --version) echo 'git version 2.55.0';;
 clone)
  [ "${FIXTURE_CLONE_FAIL:-0}" = 0 ] || exit 42
  for argument in "$@"; do destination=$argument; done
  mkdir -p "$destination";;
 -C) printf '%s\\n' "${FIXTURE_COMMIT_OVERRIDE:-$FIXTURE_COMMIT}";;
 *) exit 90;;
esac''')
    executable(bin_dir / "make", '''printf 'make %s\\n' "$*" >> "$FIXTURE_LOG"
if [ "$1" = --version ]; then echo 'GNU Make 3.81'; exit 0; fi
[ "${FIXTURE_BUILD_FAIL:-0}" = 0 ] || exit 43
[ "$1" = -C ] || exit 91
if [ "${FIXTURE_REQUIRE_SDK:-0}" = 1 ]; then
 [ "${SDKROOT:-}" = "$FIXTURE_EXPECTED_SDK" ] || { echo 'cassert not found: selected SDK missing'; exit 44; }
fi
cp "$FIXTURE_PREFIX/tool-sjasmplus" "$2/sjasmplus"''')
    executable(bin_dir / "clang++", "echo 'Apple clang version 18.0.0'")
    executable(bin_dir / "xcrun", 'command -v clang++')
    developer = repo.parent / "Developer Tools"
    (developer / "usr/bin").mkdir(parents=True, exist_ok=True)
    (developer / "SDKs/MacOSX.sdk").mkdir(parents=True, exist_ok=True)
    shutil.copy2(bin_dir / "clang++", developer / "usr/bin/clang++")
    shutil.copy2(bin_dir / "make", developer / "usr/bin/make")
    env["FIXTURE_DEVELOPER_DIR"] = str(developer)
    executable(prefix / "opt/openmsx/bin/openmsx", '''printf 'openmsx %s\\n' "$*" >> "$FIXTURE_LOG"
[ "$1" = --version ] || exit 92
echo 'openMSX 21.0' ''')
    executable(prefix / "opt/mame/bin/mame", '''printf 'mame %s\\n' "$*" >> "$FIXTURE_LOG"
[ "$1" = -help ] || exit 93
echo 'MAME v0.289' ''')
    executable(prefix / "opt/z80dasm/bin/z80dasm", '''printf 'z80dasm %s\\n' "$*" >> "$FIXTURE_LOG"
if [ "$1" = -V ]; then echo 'z80dasm 1.2.0'; else echo 'ld a,042h'; echo 'jp 04010h'; fi''')
    executable(prefix / "opt/shellcheck/bin/shellcheck", '''printf 'shellcheck %s\\n' "$*" >> "$FIXTURE_LOG"
if [ "$1" = --version ]; then echo 'ShellCheck version: 0.11.0'; exit 0; fi
[ "${FIXTURE_LINT_FAIL:-0}" = 0 ]''')


def install_assembler(repo, prefix):
    import shutil
    destination = repo / ".tools/sjasmplus" / VERSION
    destination.mkdir(parents=True)
    binary = destination / "sjasmplus"
    shutil.copy2(prefix / "tool-sjasmplus", binary)
    provenance = {
        "version": VERSION, "commit": COMMIT,
        "repository": "https://github.com/z00m128/sjasmplus.git", "lua": False,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }
    (destination / "provenance.json").write_text(json.dumps(provenance))
    return binary

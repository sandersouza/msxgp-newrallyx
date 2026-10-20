"""Provision and verify local Z80 development tools without system installation."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

EXPECTED_ROM = b"AB\x10\x40" + bytes(12) + bytes.fromhex("f3 3e 42 32 00 c0 c3 10 40") + b"\xff" * (16384 - 25)
ARTIFACTS = ("toolchain.rom", "toolchain.sym", "toolchain.lst", "code.bin", "toolchain.disasm.asm")


class SetupError(Exception):
    def __init__(self, message, code=4):
        super().__init__(message)
        self.code = code


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(arguments):
    result = subprocess.run([str(arg) for arg in arguments], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, errors="replace")
    if result.returncode:
        raise SetupError(f"{Path(arguments[0]).name} failed ({result.returncode}):\n{result.stdout[-2000:]}\nResolve the error and rerun make environment.")
    return result.stdout.strip()


def executable(path):
    return path.is_file() and os.access(path, os.X_OK)


def lock_data():
    data = json.loads(Path(__file__).with_name("toolchain-lock.json").read_text())
    if (not re.fullmatch(r"\d+\.\d+\.\d+", data["version"])
            or not re.fullmatch(r"[0-9a-f]{40}", data["commit"])
            or data["repository"] != "https://github.com/z00m128/sjasmplus.git"
            or data["lua"] is not False):
        raise SetupError("Invalid toolchain lock; restore the committed toolchain-lock.json.")
    return data


def verify_assembler(destination, lock):
    """Return False for absent tools; never repair or overwrite an existing tree."""
    if not destination.exists() and not destination.is_symlink():
        return False
    try:
        binary = destination / "sjasmplus"
        receipt = json.loads((destination / "provenance.json").read_text())
        if destination.is_symlink() or binary.is_symlink() or not executable(binary):
            raise ValueError("invalid executable")
        if receipt != dict(lock, binary_sha256=digest(binary)):
            raise ValueError("provenance or binary hash changed")
        if command([binary, "--nologo", "--version"]) != lock["version"]:
            raise ValueError("assembler version changed")
    except (OSError, ValueError, SetupError) as error:
        raise SetupError(f"Existing assembler at {destination} cannot be verified ({error}). Preserve and move that directory aside, then rerun make environment.", 3) from error
    return True


def install_assembler(tools, destination, lock, git, make, cxx):
    tools.mkdir(exist_ok=True)
    # Only this invocation's temporary workspace is removed on failure.
    with tempfile.TemporaryDirectory(prefix="build-sjasmplus-", dir=tools) as workspace:
        source = Path(workspace) / "source"
        command([git, "clone", "--depth", "1", "--single-branch", "--branch",
                 "v" + lock["version"], lock["repository"], source])
        actual = command([git, "-C", source, "rev-parse", "HEAD"])
        if actual != lock["commit"]:
            raise SetupError(f"sjasmplus source commit mismatch: expected {lock['commit']}, found {actual}. Build was not run.")
        command([make, "-C", source, "USE_LUA=0", "CXX=" + shlex.quote(str(cxx)), "all"])
        binary = source / "sjasmplus"
        if not executable(binary) or command([binary, "--nologo", "--version"]) != lock["version"]:
            raise SetupError("Built sjasmplus did not report its pinned version.")
        staged = Path(workspace) / "install"
        staged.mkdir()
        shutil.copy2(binary, staged / "sjasmplus")
        (staged / "provenance.json").write_text(json.dumps(dict(lock, binary_sha256=digest(binary)), indent=2) + "\n")
        destination.parent.mkdir(exist_ok=True)
        if destination.exists() or destination.is_symlink():
            raise SetupError(f"Assembler destination appeared during build: {destination}. Preserve it and rerun.", 3)
        staged.rename(destination)
    print(f"Installed local sjasmplus {lock['version']} from verified commit {lock['commit']} (Lua disabled).")


def smoke_state(root, assembler, disassembler):
    inputs = {
        "source": digest(root / "tests/fixtures/toolchain-smoke.asm"),
        "assembler": digest(assembler), "disassembler": digest(disassembler),
        "recipe": digest(Path(__file__)),
    }
    key = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    return root / ".tools/smoke" / key, inputs


def valid_smoke(directory, inputs):
    try:
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest["inputs"] != inputs or directory.is_symlink():
            return False
        for name in ARTIFACTS:
            artifact = directory / name
            if artifact.is_symlink() or not artifact.stat().st_size or manifest["outputs"][name] != digest(artifact):
                return False
        return ((directory / "toolchain.rom").read_bytes() == EXPECTED_ROM
                and (directory / "code.bin").read_bytes() == EXPECTED_ROM[16:25])
    except (OSError, ValueError, KeyError):
        return False


def assemble_smoke(root, directory, inputs, assembler, disassembler):
    if directory.exists() or directory.is_symlink():
        raise SetupError(f"Existing synthetic build cache is invalid: {directory}. Preserve and move it aside, then rerun make environment.", 3)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="smoke-", dir=directory.parent) as workspace:
        stage = Path(workspace) / "result"
        stage.mkdir()
        command([assembler, "--nologo", "--raw=" + str(stage / "toolchain.rom"),
                 "--sym=" + str(stage / "toolchain.sym"), "--lst=" + str(stage / "toolchain.lst"),
                 root / "tests/fixtures/toolchain-smoke.asm"])
        if (stage / "toolchain.rom").read_bytes() != EXPECTED_ROM:
            raise SetupError("Synthetic cross-assembly produced incorrect MSX header, opcodes, padding or ROM size.")
        if "start" not in (stage / "toolchain.sym").read_text().lower() or not (stage / "toolchain.lst").stat().st_size:
            raise SetupError("Synthetic cross-assembly did not produce symbols/listing.")
        (stage / "code.bin").write_bytes(EXPECTED_ROM[16:25])
        disassembly = command([disassembler, "-g", "0x4010", "-a", "-l", "-t", stage / "code.bin"])
        if not re.search(r"\bjp\b", disassembly, flags=re.I):
            raise SetupError("Synthetic Z80 disassembly did not contain the expected jump instruction.")
        (stage / "toolchain.disasm.asm").write_text(disassembly + "\n")
        manifest = {"inputs": inputs, "outputs": {name: digest(stage / name) for name in ARTIFACTS}}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        stage.rename(directory)
    print("Synthetic cross-assembly passed: 16 KiB MSX ROM, exact header/opcodes, symbols, listing and Z80 disassembly.")


def prepare(root, prefix, make, cxx, mode):
    lock = lock_data()
    tools = root / ".tools"
    destination = tools / "sjasmplus" / lock["version"]
    for path in [tools, tools / "sjasmplus", tools / "smoke", destination]:
        if path.is_symlink():
            raise SetupError(f"Preserve and move the symlinked tool path aside: {path}", 3)
    installed = verify_assembler(destination, lock)
    probes = [
        ("GNU Make", make, ["--version"], r"GNU Make"),
        ("C++ compiler", cxx, ["--version"], r"clang"),
        ("Git", prefix / "opt/git/bin/git", ["--version"], r"git version"),
        ("z80dasm", prefix / "opt/z80dasm/bin/z80dasm", ["-V"], r"z80dasm"),
        ("MAME", prefix / "opt/mame/bin/mame", ["-help"], r"MAME"),
        ("openMSX", prefix / "opt/openmsx/bin/openmsx", ["--version"], r"openMSX"),
        ("ShellCheck", prefix / "opt/shellcheck/bin/shellcheck", ["--version"], r"[Ss]hell[Cc]heck"),
    ]
    missing = []
    for name, path, flags, pattern in probes:
        if not executable(path):
            print(f"MISSING tool: {name}")
            missing.append(name)
            continue
        output = command([path, *flags])
        if not re.search(pattern, output):
            raise SetupError(f"Unexpected {name} version output; repair the installed tool.", 1)
        version_line = next((line for line in output.splitlines() if re.search(r"\d+\.\d+", line)), output.splitlines()[0])
        print(f"{name}: {version_line}")
    if mode == "dry-run":
        if not installed:
            print(f"Would build local sjasmplus {lock['version']} from pinned commit {lock['commit']} using GNU Make/Clang (USE_LUA=0).")
        if not installed or missing:
            print("Would assemble and verify the synthetic MSX ROM after dependencies are ready.")
        else:
            directory, inputs = smoke_state(root, destination / "sjasmplus", prefix / "opt/z80dasm/bin/z80dasm")
            if not valid_smoke(directory, inputs):
                if directory.exists() or directory.is_symlink():
                    raise SetupError(f"Existing synthetic build cache is invalid: {directory}. Preserve and move it aside, then rerun make environment.", 3)
                print("Would assemble and verify the synthetic MSX ROM.")
        print("Would run ShellCheck. No emulator, BIOS or game ROM is launched or downloaded.")
        return 0
    if missing:
        raise SetupError("Missing toolchain dependencies: " + ", ".join(missing) + ". Run make environment; repair Command Line Tools if the compiler or Make is missing.", 1)
    command([prefix / "opt/shellcheck/bin/shellcheck", "-s", "bash", root / "scripts/setup.sh", root / "scripts/environment/macos.sh"])
    if not installed:
        if mode == "check":
            raise SetupError("Pinned local sjasmplus is missing. Run make environment.", 1)
        install_assembler(tools, destination, lock, prefix / "opt/git/bin/git", make, cxx)
    directory, inputs = smoke_state(root, destination / "sjasmplus", prefix / "opt/z80dasm/bin/z80dasm")
    if not valid_smoke(directory, inputs):
        if mode == "check":
            raise SetupError("Synthetic cross-assembly evidence is missing, stale or corrupt. Run make environment.", 1)
        assemble_smoke(root, directory, inputs, destination / "sjasmplus", prefix / "opt/z80dasm/bin/z80dasm")
    else:
        print("Synthetic cross-assembly evidence verified (read-only; no rebuild).")
    print(f"Toolchain ready. Assembler: {destination / 'sjasmplus'}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("install", "check", "dry-run"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--make", type=Path, required=True)
    parser.add_argument("--cxx", type=Path, required=True)
    args = parser.parse_args()
    try:
        return prepare(args.root, args.prefix, args.make, args.cxx, args.mode)
    except SetupError as error:
        print(f"Toolchain: {error}", file=sys.stderr)
        return error.code
    except (OSError, ValueError, KeyError) as error:
        print(f"Toolchain verification failed: {error}. Resolve the error and rerun make environment.", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())

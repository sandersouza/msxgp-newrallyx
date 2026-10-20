"""Shell integration tests: every external installer is an isolated executable stub."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from toolchain_fixtures import create_tools

ROOT = Path(__file__).resolve().parents[1]


class MacOSEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="macos environment ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo with spaces"
        self.bin = self.root / "bin"
        self.prefix = self.root / "custom brew prefix"
        self.repo.mkdir()
        self.bin.mkdir()
        shutil.copytree(ROOT / "scripts", self.repo / "scripts")
        for name in ["Brewfile", "requirements.txt"]:
            if (ROOT / name).exists():
                shutil.copy(ROOT / name, self.repo)
        self.log = self.root / "commands.log"
        self.log.touch()
        self.env = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin",
                        FIXTURE_PREFIX=str(self.prefix), FIXTURE_REPO=str(self.repo),
                        FIXTURE_LOG=str(self.log), FIXTURE_ARCH="arm64")
        self.env.pop("OS", None)
        self.write_exec(self.bin / "uname", '''case "$1" in
  -s) echo Darwin;; -m) echo "$FIXTURE_ARCH";; esac''')
        self.write_exec(self.bin / "sw_vers", "echo 27.0.1")
        self.write_exec(self.bin / "sysctl", 'echo "${FIXTURE_ROSETTA:-0}"')
        self.write_exec(self.bin / "xcode-select", '''[ "${FIXTURE_NO_CLT:-0}" = 0 ] || exit 1
echo "$FIXTURE_DEVELOPER_DIR"''')
        self.write_exec(self.bin / "brew", '''printf 'brew %s\\n' "$*" >> "$FIXTURE_LOG"
case "$1" in
  --prefix) echo "$FIXTURE_PREFIX";;
  --version) echo 'Homebrew 7.0.6';;
  install)
    [ "${HOMEBREW_NO_AUTO_UPDATE:-}" = 1 ] || exit 90
    [ "${HOMEBREW_NO_INSTALL_UPGRADE:-}" = 1 ] || exit 91
    [ "${HOMEBREW_NO_ANALYTICS:-}" = 1 ] || exit 92
    [ "${FIXTURE_BREW_FAIL:-0}" = 0 ] || exit 42
    case "$2" in
      gh) mkdir -p "$FIXTURE_PREFIX/opt/gh/bin"
          cp "$FIXTURE_PREFIX/tool-gh" "$FIXTURE_PREFIX/opt/gh/bin/gh";;
      *) exit 93;;
    esac;;
  *) exit 94;;
esac''')
        self.write_exec(self.prefix / "opt/git/bin/git", "echo 'git version 2.55.0'")
        self.write_exec(self.prefix / "opt/gh/bin/gh", "echo 'gh version 2.98.0'")
        shutil.copy(self.prefix / "opt/gh/bin/gh", self.prefix / "tool-gh")
        self.write_exec(self.prefix / "opt/python@3.14/bin/python3.14", '''printf 'python %s\\n' "$*" >> "$FIXTURE_LOG"
if [ "$#" -ge 3 ]; then
    case "$3" in */toolchain.py) exec "$FIXTURE_REAL_PYTHON" "$@";; esac
fi
if [ "$1" = -m ] && [ "$2" = venv ]; then
    mkdir -p "$3/bin"
    cp "$0" "$3/bin/python"
    printf 'home = fixture\\n' > "$3/pyvenv.cfg"
    exit 0
fi
if [ "$1" = -I ] && [ "$2" = -B ]; then
    case "$4" in
      base) [ "${FIXTURE_BAD_PYTHON:-0}" = 0 ] || exit 1; echo 'Python 3.14.7'; exit 0;;
      environment) [ "${FIXTURE_BAD_VENV:-0}" = 0 ] || exit 1; exit 0;;
      dependencies) [ -f "$FIXTURE_REPO/.venv/dependencies-ready" ]; exit $?;;
    esac
fi
if [ "$1" = -I ] && [ "$2" = -B ] && [ "$3" = -m ] && [ "$4" = pip ]; then
    case "$5" in
      --version) echo 'pip 26.0'; exit 0;;
      check) exit 0;;
      install)
        [ "${FIXTURE_PIP_FAIL:-0}" = 0 ] || exit 43
        touch "$FIXTURE_REPO/.venv/dependencies-ready"; exit 0;;
    esac
fi
exit 95''')
        create_tools(self.repo, self.prefix, self.bin, self.env)

    def write_exec(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/bash\nset -eu\n" + body + "\n")
        path.chmod(0o755)

    def run_setup(self, *args):
        return subprocess.run(["/bin/bash", str(self.repo / "scripts/setup.sh"), *args],
                              cwd=self.root, env=self.env, capture_output=True, text=True)

    def assert_code(self, result, code):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)

    def snapshot(self):
        return {str(p.relative_to(self.repo)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.repo.rglob("*") if p.is_file()}

    def test_preview_is_read_only_and_lists_changes(self):
        (self.prefix / "opt/gh/bin/gh").unlink()
        before = self.snapshot()
        result = self.run_setup("--dry-run")
        self.assert_code(result, 0)
        self.assertIn("brew install gh", result.stdout)
        self.assertIn(".venv", result.stdout)
        self.assertEqual(before, self.snapshot())
        self.assertNotIn("brew install", self.log.read_text())

    def test_environment_prepares_the_full_toolchain(self):
        result = self.run_setup()
        self.assert_code(result, 0)
        self.assertIn("Synthetic cross-assembly passed", result.stdout)
        self.assertTrue(list((self.repo / ".tools/smoke").rglob("toolchain.rom")))
        self.assertIn("shellcheck -s bash", self.log.read_text())

    def test_native_build_uses_sdk_from_selected_developer_directory(self):
        developer = Path(self.env["FIXTURE_DEVELOPER_DIR"])
        self.env["FIXTURE_REQUIRE_SDK"] = "1"
        self.env["SDKROOT"] = "/foreign/sdk"
        self.env["FIXTURE_EXPECTED_SDK"] = str(developer / "SDKs/MacOSX.sdk")
        self.assert_code(self.run_setup(), 0)

    def test_full_xcode_build_uses_selected_macos_sdk(self):
        developer = Path(self.env["FIXTURE_DEVELOPER_DIR"])
        sdk = developer / "Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk"
        (developer / "SDKs/MacOSX.sdk").rmdir()
        sdk.mkdir(parents=True)
        compiler = developer / "usr/bin/clang++"
        xcode_compiler = developer / "Toolchains/XcodeDefault.xctoolchain/usr/bin/clang++"
        xcode_compiler.parent.mkdir(parents=True)
        compiler.rename(xcode_compiler)
        self.env["FIXTURE_REQUIRE_SDK"] = "1"
        self.env["FIXTURE_EXPECTED_SDK"] = str(sdk)
        self.assert_code(self.run_setup(), 0)

    def test_missing_selected_macos_sdk_stops_without_mutation(self):
        developer = Path(self.env["FIXTURE_DEVELOPER_DIR"])
        (developer / "SDKs/MacOSX.sdk").rmdir()
        before = self.snapshot()
        for args in [(), ("--check",), ("--dry-run",)]:
            result = self.run_setup(*args)
            self.assert_code(result, 1)
            self.assertIn("SDK", result.stderr)
            self.assertEqual(before, self.snapshot())
        self.assertNotIn("brew install", self.log.read_text())

    def test_preview_lists_missing_toolchain_packages_without_mutation(self):
        (self.prefix / "opt/openmsx/bin/openmsx").unlink()
        before = self.snapshot()
        result = self.run_setup("--dry-run")
        self.assert_code(result, 0)
        self.assertIn("brew install openmsx", result.stdout)
        self.assertIn("sjasmplus", result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_readonly_modes_do_not_create_external_xcrun_cache(self):
        cache = self.root / "external-xcrun-cache"
        self.env["FIXTURE_XCRUN_CACHE"] = str(cache)
        self.write_exec(self.bin / "xcrun", 'touch "$FIXTURE_XCRUN_CACHE"; command -v clang++')
        for args in [("--dry-run",), ("--check",)]:
            self.run_setup(*args)
            self.assertFalse(cache.exists(), "read-only mode populated xcrun cache outside the repository")

    def test_check_requires_assembler_and_smoke_even_when_python_is_ready(self):
        self.assert_code(self.run_setup(), 0)
        directory = self.repo / ".tools/sjasmplus/1.24.0"
        if directory.exists():
            shutil.rmtree(directory)
        before = self.snapshot()
        result = self.run_setup("--check")
        self.assert_code(result, 1)
        self.assertIn("sjasmplus", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_check_reports_missing_packages_and_environment_without_mutation(self):
        (self.prefix / "opt/gh/bin/gh").unlink()
        before = self.snapshot()
        result = self.run_setup("--check")
        self.assert_code(result, 1)
        self.assertIn("gh", result.stdout + result.stderr)
        self.assertIn(".venv", result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertNotIn("brew install", self.log.read_text())

    def test_install_and_repeat_skip_unnecessary_mutations(self):
        (self.prefix / "opt/gh/bin/gh").unlink()
        self.assert_code(self.run_setup(), 0)
        log = self.log.read_text()
        self.assertEqual(log.count("brew install gh"), 1)
        self.assertIn("pip install", log)
        self.log.write_text("")
        before = self.snapshot()
        self.assert_code(self.run_setup(), 0)
        self.assertEqual(before, self.snapshot())
        self.assertNotIn("brew install", self.log.read_text())
        self.assertNotIn("pip install", self.log.read_text())
        self.assertNotIn("-m venv", self.log.read_text())
        self.assert_code(self.run_setup("--check"), 0)

    def test_missing_manual_prerequisites(self):
        self.env["FIXTURE_NO_CLT"] = "1"
        result = self.run_setup()
        self.assert_code(result, 1)
        self.assertIn("xcode-select --install", result.stderr)
        self.assertNotIn("install", self.log.read_text())

    def test_missing_homebrew_reports_official_manual_installation(self):
        # A brew found on PATH but unable to run must not trigger another installation.
        self.write_exec(self.bin / "brew", "exit 1")
        result = self.run_setup()
        self.assert_code(result, 1)
        self.assertIn("https://brew.sh", result.stderr)

    def test_architecture_and_rosetta_are_rejected_before_installation(self):
        self.env["FIXTURE_ARCH"] = "ppc"
        self.assert_code(self.run_setup(), 1)
        self.env["FIXTURE_ARCH"] = "x86_64"
        self.env["FIXTURE_ROSETTA"] = "1"
        result = self.run_setup()
        self.assert_code(result, 1)
        self.assertIn("Rosetta", result.stderr)
        self.assertNotIn("install", self.log.read_text())

    def test_native_intel_uses_discovered_prefix(self):
        self.env["FIXTURE_ARCH"] = "x86_64"
        self.assert_code(self.run_setup(), 0)
        self.assertIn(str(self.prefix), self.log.read_text())

    def test_incompatible_base_python_is_not_replaced(self):
        self.env["FIXTURE_BAD_PYTHON"] = "1"
        self.assert_code(self.run_setup(), 1)
        self.assertFalse((self.repo / ".venv").exists())

    def test_outdated_installed_tools_are_reported_in_check_and_preview(self):
        self.write_exec(self.prefix / "opt/git/bin/git", "echo 'git version 1.0.0'")
        before = self.snapshot()
        for args in [("--check",), ("--dry-run",)]:
            result = self.run_setup(*args)
            self.assert_code(result, 1)
            self.assertIn("Requires >= 2.30", result.stderr)
            self.assertEqual(before, self.snapshot())

    def test_broken_environment_is_preserved_in_all_modes(self):
        (self.repo / ".venv").mkdir()
        (self.repo / ".venv/keep").write_text("user data")
        before = self.snapshot()
        for args in [(), ("--check",), ("--dry-run",)]:
            result = self.run_setup(*args)
            self.assert_code(result, 3)
            self.assertIn("move", result.stderr.lower())
            self.assertEqual(before, self.snapshot())

    def test_foreign_environment_is_preserved(self):
        self.assert_code(self.run_setup(), 0)
        self.env["FIXTURE_BAD_VENV"] = "1"
        before = self.snapshot()
        self.assert_code(self.run_setup(), 3)
        self.assertEqual(before, self.snapshot())

    def test_existing_environment_is_not_assumed_valid_when_base_python_is_missing(self):
        self.assert_code(self.run_setup(), 0)
        (self.prefix / "opt/python@3.14/bin/python3.14").unlink()
        self.env["FIXTURE_BAD_VENV"] = "1"
        before = self.snapshot()
        self.log.write_text("")
        for args in [(), ("--check",), ("--dry-run",)]:
            result = self.run_setup(*args)
            self.assert_code(result, 3)
            self.assertIn(".venv", result.stderr)
            self.assertIn("move", result.stderr.lower())
            self.assertEqual(before, self.snapshot())
        self.assertNotIn("brew install", self.log.read_text())

    def test_installation_failures_have_actionable_exit_codes(self):
        (self.prefix / "opt/gh/bin/gh").unlink()
        self.env["FIXTURE_BREW_FAIL"] = "1"
        result = self.run_setup()
        self.assert_code(result, 4)
        self.assertIn("gh", result.stderr)
        self.env["FIXTURE_BREW_FAIL"] = "0"
        self.env["FIXTURE_PIP_FAIL"] = "1"
        result = self.run_setup()
        self.assert_code(result, 4)
        self.assertIn("pip", result.stderr)


if __name__ == "__main__":
    unittest.main()

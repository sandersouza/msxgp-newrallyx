"""Test toolchain orchestration and its byte-level cross-assembly contract."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from toolchain_fixtures import create_tools, install_assembler, executable, EXPECTED_ROM

ROOT = Path(__file__).resolve().parents[1]


class ToolchainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="toolchain test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo with spaces"
        self.repo.mkdir()
        shutil.copytree(ROOT / "scripts", self.repo / "scripts")
        self.prefix = self.root / "brew prefix"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "commands.log"
        self.log.touch()
        self.env = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin", FIXTURE_LOG=str(self.log))
        create_tools(self.repo, self.prefix, self.bin, self.env)

    def run_toolchain(self, mode):
        return subprocess.run([sys.executable, "-I", "-B", str(self.repo / "scripts/environment/toolchain.py"),
                               "--mode", mode, "--root", str(self.repo), "--prefix", str(self.prefix),
                               "--make", str(self.bin / "make"), "--cxx", str(self.bin / "clang++")],
                              capture_output=True, text=True, env=self.env)

    def assert_code(self, result, code):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)

    def snapshot(self):
        return {str(p.relative_to(self.repo)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.repo.rglob("*") if p.is_file()}

    def test_preview_and_missing_check_do_not_create_tools(self):
        before = self.snapshot()
        result = self.run_toolchain("dry-run")
        self.assert_code(result, 0)
        self.assertIn("sjasmplus", result.stdout)
        self.assertIn("synthetic", result.stdout)
        self.assertEqual(before, self.snapshot())
        result = self.run_toolchain("check")
        self.assert_code(result, 1)
        self.assertIn("sjasmplus", result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.repo / ".tools").exists())

    def test_z80dasm_version_uses_compatible_short_option(self):
        executable(self.prefix / "opt/z80dasm/bin/z80dasm", '''
case "$1" in
 -V) echo 'z80dasm 1.2.0';;
 --version) echo 'Error: No input file specified' >&2; exit 1;;
 *) exit 99;;
esac''')
        self.assert_code(self.run_toolchain("dry-run"), 0)

    def test_multiline_version_banner_reports_the_actual_version(self):
        executable(self.prefix / "opt/shellcheck/bin/shellcheck", "echo 'ShellCheck - shell script analysis tool'; echo 'version: 0.11.0'")
        result = self.run_toolchain("dry-run")
        self.assert_code(result, 0)
        self.assertIn("ShellCheck: version: 0.11.0", result.stdout)

    @unittest.skipUnless(shutil.which("z80dasm"), "real z80dasm is not installed")
    def test_real_disassembler_accepts_the_synthetic_code(self):
        target = self.prefix / "opt/z80dasm/bin/z80dasm"
        target.unlink()
        target.symlink_to(Path(shutil.which("z80dasm")).resolve())
        self.assert_code(self.run_toolchain("install"), 0)
        assembly = next((self.repo / ".tools/smoke").rglob("toolchain.disasm.asm")).read_text()
        self.assertIn("ld a,042h", assembly)
        self.assertIn("jp", assembly)

    def test_install_compiles_pinned_source_and_checks_rom_disassembly_and_lint(self):
        result = self.run_toolchain("install")
        self.assert_code(result, 0)
        self.assertIn("cross-assembly", result.stdout)
        roms = list((self.repo / ".tools/smoke").rglob("toolchain.rom"))
        self.assertEqual(len(roms), 1)
        self.assertEqual(roms[0].read_bytes(), EXPECTED_ROM)
        commands = self.log.read_text()
        self.assertIn("--branch v1.24.0", commands)
        self.assertIn("USE_LUA=0", commands)
        self.assertIn("z80dasm -g 0x4010", commands)
        self.assertIn("shellcheck -s bash", commands)
        self.assertIn("mame -help", commands)
        self.assertIn("openmsx --version", commands)

    def test_rerun_and_check_preserve_files_and_do_not_rebuild(self):
        self.assert_code(self.run_toolchain("install"), 0)
        before = self.snapshot()
        self.log.write_text("")
        for mode in ["install", "check", "dry-run"]:
            self.assert_code(self.run_toolchain(mode), 0)
            self.assertEqual(before, self.snapshot())
        commands = self.log.read_text()
        self.assertNotIn("git clone", commands)
        self.assertNotIn("USE_LUA=0", commands)
        self.assertNotIn("--raw=", commands)

    def test_source_commit_mismatch_stops_before_build(self):
        self.env["FIXTURE_COMMIT_OVERRIDE"] = "0" * 40
        result = self.run_toolchain("install")
        self.assert_code(result, 4)
        self.assertIn("commit", result.stderr)
        self.assertNotIn("USE_LUA=0", self.log.read_text())
        self.assertFalse((self.repo / ".tools/sjasmplus/1.24.0").exists())

    def test_download_build_assembly_and_lint_failures_are_reported(self):
        for variable in ["FIXTURE_CLONE_FAIL", "FIXTURE_BUILD_FAIL", "FIXTURE_ASSEMBLER_FAIL", "FIXTURE_BAD_ROM", "FIXTURE_LINT_FAIL"]:
            with self.subTest(variable=variable):
                self.env[variable] = "1"
                result = self.run_toolchain("install")
                self.assert_code(result, 4)
                self.env.pop(variable)

    def test_unknown_existing_assembler_directory_is_preserved(self):
        path = self.repo / ".tools/sjasmplus/1.24.0"
        path.mkdir(parents=True)
        (path / "user-file").write_text("keep")
        before = self.snapshot()
        for mode in ["install", "check", "dry-run"]:
            result = self.run_toolchain(mode)
            self.assert_code(result, 3)
            self.assertIn("preserv", result.stderr.lower())
            self.assertEqual(before, self.snapshot())

    def test_changed_binary_does_not_reuse_provenance_or_smoke(self):
        binary = install_assembler(self.repo, self.prefix)
        binary.write_text(binary.read_text() + "\n# changed\n")
        before = self.snapshot()
        self.assert_code(self.run_toolchain("install"), 3)
        self.assertEqual(before, self.snapshot())

    def test_corrupt_smoke_is_reported_without_mutation_in_check_mode(self):
        self.assert_code(self.run_toolchain("install"), 0)
        rom = next((self.repo / ".tools/smoke").rglob("toolchain.rom"))
        rom.write_bytes(b"corrupted")
        before = self.snapshot()
        self.assert_code(self.run_toolchain("check"), 1)
        self.assertEqual(before, self.snapshot())

    def test_preview_reports_existing_corrupt_smoke_recovery_blocker(self):
        self.assert_code(self.run_toolchain("install"), 0)
        rom = next((self.repo / ".tools/smoke").rglob("toolchain.rom"))
        rom.write_bytes(b"corrupted")
        before = self.snapshot()
        result = self.run_toolchain("dry-run")
        self.assert_code(result, 3)
        self.assertIn("Preserve and move", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_fixture_change_requires_new_cross_assembly(self):
        self.assert_code(self.run_toolchain("install"), 0)
        source = self.repo / "tests/fixtures/toolchain-smoke.asm"
        source.write_text(source.read_text() + "; changed fixture\n")
        self.assert_code(self.run_toolchain("check"), 1)
        self.assert_code(self.run_toolchain("install"), 0)


if __name__ == "__main__":
    unittest.main()

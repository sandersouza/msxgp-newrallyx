"""Exercise the real shell entry point using isolated, synthetic hosts."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rally setup ")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo with spaces"
        self.bin = Path(self.temp.name) / "bin"
        self.repo.mkdir()
        self.bin.mkdir()
        if (ROOT / "scripts").exists():
            shutil.copytree(ROOT / "scripts", self.repo / "scripts")
        if (ROOT / "Makefile").exists():
            shutil.copy(ROOT / "Makefile", self.repo)
        (self.repo / "src/toolchain/environment").mkdir(parents=True, exist_ok=True)
        self.executable(self.repo / "src/toolchain/environment/macos.sh",
                        '#!/bin/bash\nprintf "macos-mode:%s\\n" "$*"\n')
        self.env = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin")
        self.env.pop("OS", None)

    def executable(self, path, content):
        path.write_text(content)
        path.chmod(0o755)

    def run_setup(self, system="Darwin", *args, windows=False):
        self.executable(self.bin / "uname", f"#!/bin/bash\nprintf '%s\\n' '{system}'\n")
        env = dict(self.env)
        if windows:
            env["OS"] = "Windows_NT"
        return subprocess.run(["/bin/bash", str(self.repo / "scripts/setup.sh"), *args],
                              env=env, cwd=self.temp.name, text=True, capture_output=True)

    def test_macos_dispatch_preserves_mode_and_paths(self):
        for args in [(), ("--check",), ("--dry-run",)]:
            with self.subTest(args=args):
                result = self.run_setup("Darwin", *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Detected OS: macOS", result.stdout)
                self.assertIn("macos-mode:" + " ".join(args), result.stdout)

    def test_unsupported_platforms_do_not_dispatch(self):
        for system, label in [("Linux", "Linux"), ("MINGW64_NT", "Windows"),
                              ("MSYS_NT", "Windows"), ("CYGWIN_NT", "Windows"),
                              ("FreeBSD", "Unknown")]:
            with self.subTest(system=system):
                result = self.run_setup(system)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(label, result.stdout)
                self.assertIn("not supported yet", result.stderr)
                self.assertNotIn("macos-mode", result.stdout)

    def test_windows_environment_is_detected(self):
        result = self.run_setup("unknown", windows=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Detected OS: Windows", result.stdout)

    def test_help_and_invalid_options(self):
        result = self.run_setup("Linux", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)
        for args in [("--unknown",), ("--check", "--dry-run")]:
            result = self.run_setup("Darwin", *args)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("macos-mode", result.stdout)

    def test_make_targets_forward_modes(self):
        self.executable(self.bin / "uname", "#!/bin/bash\necho Darwin\n")
        for target, mode in [("environment", ""), ("environment-check", "--check")]:
            with self.subTest(target=target):
                result = subprocess.run(["make", "-C", str(self.repo), target], env=self.env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("macos-mode:" + mode, result.stdout)


if __name__ == "__main__":
    unittest.main()

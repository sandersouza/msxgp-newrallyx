"""Test interpreter/environment checks with real Python and synthetic packages."""

from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
import venv

VERIFY = Path(__file__).resolve().parents[1] / "scripts/environment/verify_python.py"


class PythonVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="python verification ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "requirements.txt").write_text("Pillow==13.0.0\n")

    def run_verify(self, mode, python=sys.executable, arch=None):
        return subprocess.run([str(python), "-I", "-B", str(VERIFY), mode,
                               "--root", str(self.root), "--base", sys.executable,
                               "--architecture", arch or platform.machine()],
                              capture_output=True, text=True)

    def create_environment(self):
        directory = self.root / ".venv"
        venv.EnvBuilder(with_pip=False).create(directory)
        site = directory / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
        # A local synthetic pip module lets environment validation exercise discovery
        # without downloading or installing anything. Dependency checks are separate.
        (site / "pip.py").write_text("")
        return directory / "bin/python", site

    def test_base_checks_python_minor_and_architecture(self):
        result = self.run_verify("base")
        expected = 0 if sys.version_info[:2] == (3, 14) else 1
        self.assertEqual(result.returncode, expected, result.stderr)
        result = self.run_verify("base", arch="unsupported")
        self.assertNotEqual(result.returncode, 0)

    def test_global_python_is_not_accepted_as_repository_venv(self):
        result = self.run_verify("environment")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(".venv", result.stderr)

    def test_real_environment_and_pinned_dependency(self):
        python, site = self.create_environment()
        result = self.run_verify("environment", python)
        expected = 0 if sys.version_info[:2] == (3, 14) else 1
        self.assertEqual(result.returncode, expected, result.stderr)
        result = self.run_verify("dependencies", python)
        self.assertEqual(result.returncode, 1)
        package = site / "PIL"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "Image.py").write_text("# synthetic import fixture\n")
        metadata = site / "pillow-13.0.0.dist-info"
        metadata.mkdir()
        metadata_file = metadata / "METADATA"
        metadata_file.write_text("Name: pillow\nVersion: 13.0.0\n")
        result = self.run_verify("dependencies", python)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(list(self.root.rglob("__pycache__")))
        metadata_file.write_text("Name: pillow\nVersion: 12.0.0\n")
        self.assertEqual(self.run_verify("dependencies", python).returncode, 1)


if __name__ == "__main__":
    unittest.main()

"""Read-only interpreter, virtual environment, and dependency validation."""

import argparse
import importlib.metadata
import importlib.util
from pathlib import Path
import platform
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("base", "environment", "dependencies"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--architecture", required=True)
    args = parser.parse_args()
    try:
        if args.mode in ("base", "environment"):
            if sys.version_info[:2] != (3, 14):
                raise ValueError("Python 3.14 is required")
            if platform.machine() != args.architecture:
                raise ValueError("Python CPU architecture does not match the native shell")
        if args.mode == "base":
            if sys.prefix != sys.base_prefix:
                raise ValueError("Homebrew Python must not be another virtual environment")
            if importlib.util.find_spec("venv") is None or importlib.util.find_spec("ensurepip") is None:
                raise ValueError("Python venv/ensurepip support is missing")
            print(f"Python {platform.python_version()} ({platform.machine()})")
        elif args.mode == "environment":
            expected = (args.root / ".venv").resolve()
            if Path(sys.prefix).resolve() != expected or sys.prefix == sys.base_prefix:
                raise ValueError("Python is not running in this repository's .venv")
            base_prefix = subprocess.check_output(
                [args.base, "-I", "-B", "-c", "import sys; print(sys.base_prefix)"],
                text=True,
            ).strip()
            if Path(sys.base_prefix).resolve() != Path(base_prefix).resolve():
                raise ValueError(".venv uses a different base Python; move it aside and rerun setup")
            if importlib.util.find_spec("pip") is None:
                raise ValueError(".venv has no pip; move it aside and rerun setup")
        else:
            for line in (args.root / "requirements.txt").read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)", line)
                if not match:
                    raise ValueError("requirements.txt must contain exact package==version pins")
                package, version = match.groups()
                actual = importlib.metadata.version(package)
                if actual != version:
                    raise ValueError(f"{package}: expected {version}, found {actual}")
                print(f"{package} {actual}")
            # Metadata alone is insufficient: validate the extractor's actual import.
            from PIL import Image

            if Image is None:
                raise ValueError("Pillow image support is unavailable")
    except (ValueError, OSError, ImportError, subprocess.SubprocessError) as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

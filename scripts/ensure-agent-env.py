#!/usr/bin/env python3
"""Create/update the ignored development venv only when requirements change."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
STAMP = VENV / ".agent-requirements.sha256"
REQS = [ROOT / "requirements.txt", ROOT / "requirements-dev.txt"]
MINIMUM_PYTHON = (3, 12)


def digest() -> str:
    value = hashlib.sha256()
    for path in REQS:
        value.update(path.name.encode())
        value.update(b"\0")
        value.update(path.read_bytes())
        value.update(b"\0")
    return value.hexdigest()


def run(*args: str) -> None:
    print(">>>", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def venv_interpreter() -> str:
    """Return an interpreter compatible with the repository runtime."""
    if sys.version_info >= MINIMUM_PYTHON:
        return sys.executable
    candidate = shutil.which("python3.12")
    if candidate is not None:
        return candidate
    required = ".".join(str(part) for part in MINIMUM_PYTHON)
    actual = f"{sys.version_info.major}.{sys.version_info.minor}"
    raise RuntimeError(
        f"Python {required} or newer is required; bootstrap is running on {actual} "
        "and python3.12 is not available on PATH"
    )


def main() -> int:
    expected = digest()
    python = VENV / "bin" / "python"
    if not python.exists():
        run(venv_interpreter(), "-m", "venv", str(VENV))
    current = STAMP.read_text().strip() if STAMP.exists() else ""
    if current != expected:
        run(
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(ROOT / "requirements-dev.txt"),
        )
        STAMP.write_text(expected + "\n")
    print(f"Development environment ready: {python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

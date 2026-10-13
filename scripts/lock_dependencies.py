"""Resolve pyproject dependencies and lock the local container toolchain."""

import subprocess
import sys
import tomllib
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    dependencies = project["dependencies"] + project["optional-dependencies"]["dev"]

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", *dependencies],
        check=True,
    )
    frozen = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    (root / "requirements.lock").write_text(
        "# Generated from pyproject.toml in a Python 3.13 Linux container.\n"
        "# See README.md for the regeneration command.\n\n" + frozen,
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

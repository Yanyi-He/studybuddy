"""Install a built wheel with locked dependencies and run it outside this checkout."""

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT = Path(__file__).resolve().parent.parent


def check_wheel(wheel: Path) -> None:
    wheel = wheel.resolve(strict=True)
    with TemporaryDirectory(prefix="studybuddy-wheel-") as temporary:
        root = Path(temporary)
        environment = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(root / "venv")}
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        subprocess.run(
            [
                "uv",
                "sync",
                "--offline",
                "--locked",
                "--no-dev",
                "--no-install-project",
                "--project",
                str(PROJECT),
                "--python",
                sys.executable,
            ],
            check=True,
            env=environment,
            cwd=root,
        )
        python = root / "venv" / "bin" / "python"
        subprocess.run(
            ["uv", "pip", "install", "--offline", "--no-deps", "--python", str(python), str(wheel)],
            check=True,
            env=environment,
            cwd=root,
        )
        verification = (
            "import pathlib, sys, studybuddy; "
            "location = pathlib.Path(studybuddy.__file__).resolve(); "
            "assert location.is_relative_to(pathlib.Path(sys.prefix).resolve()); "
            "print('Verified wheel import from site-packages')"
        )
        subprocess.run(
            [str(python), "-I", "-c", verification], check=True, env=environment, cwd=root
        )
        subprocess.run(
            [str(python), "-I", str(PROJECT / "examples" / "demo.py")],
            check=True,
            env=environment,
            cwd=root,
        )


if __name__ == "__main__":
    if len(sys.argv) > 2:
        raise SystemExit("Usage: python scripts/smoke_wheel.py [PATH_TO_CURRENT_WHEEL]")
    metadata = tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))
    current = PROJECT / "dist" / f"studybuddy-{metadata['project']['version']}-py3-none-any.whl"
    check_wheel(Path(sys.argv[1]) if len(sys.argv) == 2 else current)

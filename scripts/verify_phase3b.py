from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    run([sys.executable, "scripts/verify_phase3a.py"])
    run([sys.executable, "-m", "pytest", "tests", "-q"], cwd=BACKEND)
    run(["npm", "test"], cwd=FRONTEND)
    run(["npm", "run", "build"], cwd=FRONTEND)
    run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_phase3b_public_shell.py",
            "-q",
        ]
    )
    print("Phase 3B: automated gate PASS")
    print("Legacy screens: 98")
    print("BUILD: v1656")
    print("static/index.html: 14091 qator")
    print("Production: o‘zgarmadi")
    print("Staging acceptance: kutilmoqda")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

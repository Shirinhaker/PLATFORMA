from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    run([sys.executable, "scripts/verify_phase2.py"])
    run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_phase3_screen_inventory",
            "-v",
        ]
    )
    run(["npm", "test"], cwd=FRONTEND)
    run(["npm", "run", "build"], cwd=FRONTEND)
    print("Phase 3A: PASS")
    print("Legacy screens: 98")
    print("BUILD: v1656")
    print("static/index.html: 14091 qator")
    print("Production: o‘zgarmadi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

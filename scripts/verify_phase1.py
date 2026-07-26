from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.export_legacy_inventory import collect_inventory


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    expected = json.loads(
        (ROOT / "docs/architecture/legacy-v1656-inventory.json").read_text(
            encoding="utf-8"
        )
    )
    if collect_inventory(ROOT) != expected:
        raise SystemExit("Legacy v1656 contract o‘zgargan.")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    for smoke in (
        "tests/admin-ui-smoke.cjs",
        "tests/ad-upload-ui-smoke.cjs",
        "tests/district-offers-ui-smoke.cjs",
        "tests/story-ui-smoke.cjs",
        "tests/subscription-ui-smoke.cjs",
    ):
        run(["node", smoke])
    run([sys.executable, "-m", "pytest", "tests", "-v"], ROOT / "backend")
    run(["npm", "test"], ROOT / "frontend")
    run(["npm", "run", "build"], ROOT / "frontend")
    print("BUILD: v1656")
    print("static/index.html: 14091 qator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

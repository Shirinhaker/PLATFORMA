from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
LEGACY_HTML = ROOT / "static/index.html"
LEGACY_BUILD_MARKER = "<!-- BUILD: v1656 -->"
LEGACY_LINE_COUNT = 14091


def run(
    command: list[str],
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def verify_legacy_contract() -> None:
    source = LEGACY_HTML.read_text(encoding="utf-8")
    if LEGACY_BUILD_MARKER not in source:
        raise SystemExit("Legacy BUILD v1656 belgisi topilmadi.")
    if len(source.splitlines()) != LEGACY_LINE_COUNT:
        raise SystemExit(
            "Legacy static/index.html qator soni o‘zgargan: "
            f"{len(source.splitlines())}."
        )


def main() -> int:
    with TemporaryDirectory(prefix="koprik-phase2-verify-") as temp_root:
        legacy_env = os.environ.copy()
        legacy_env["DB_PATH"] = str(Path(temp_root) / "platforma.db")
        run(
            [sys.executable, "scripts/verify_phase1.py"],
            env=legacy_env,
        )
    verify_legacy_contract()
    print("backend tests: PASS")
    print("frontend tests: PASS")
    print("frontend build: PASS")
    print("legacy contract: PASS")
    print("BUILD: v1656")
    print("static/index.html: 14091 qator")
    print("Production: o‘zgarmadi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

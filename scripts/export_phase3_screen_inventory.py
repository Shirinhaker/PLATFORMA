#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re
import sys


BUILD_RE = re.compile(r"<!-- BUILD: (v\d+) -->")
SCREEN_RE = re.compile(r'data-screen="([^"]+)"')
AUTH_SCREENS = {"login", "register", "regform"}
STAFF_SCREENS = {"staff-login", "staff-home"}
PUBLIC_SCREENS = {
    "home",
    "taxi-call",
    "listings",
    "catalog",
    "cat-types",
    "loc",
    "list",
    "business",
    "user-page",
    "person",
    "help",
}


def screen_group(name: str) -> str:
    if name in AUTH_SCREENS:
        return "auth"
    if name in STAFF_SCREENS:
        return "staff"
    if name == "cabinet" or name.startswith("cab-"):
        return "business-cabinet"
    if name == "ucab" or name.startswith("ucab-"):
        return "user-cabinet"
    if name in PUBLIC_SCREENS:
        return "public"
    return "shared"


def collect_screen_inventory(root: Path) -> dict[str, object]:
    source = (root / "static/index.html").read_text(encoding="utf-8")
    build_match = BUILD_RE.search(source)
    names = list(dict.fromkeys(SCREEN_RE.findall(source)))
    return {
        "build": build_match.group(1) if build_match else "",
        "screen_count": len(names),
        "screens": [
            {
                "name": name,
                "group": screen_group(name),
                "phase3_status": "legacy",
            }
            for name in names
        ],
    }


def write_screen_inventory(root: Path, destination: Path) -> None:
    destination.write_text(
        json.dumps(
            collect_screen_inventory(root),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    destination = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else root / "docs/architecture/legacy-v1656-screens.json"
    )
    write_screen_inventory(root, destination)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

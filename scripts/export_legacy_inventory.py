#!/usr/bin/env python3
"""Ko‘prik v1656 uchun takrorlanuvchi legacy kontrakt inventari."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import sys


ROUTE_FILES = ("api.py", "admin_api.py", "payment_api.py", "main.py")
RUNTIME_FILES = (
    "api.py",
    "database.py",
    "main.py",
    "static/index.html",
    "admin/app.js",
    "admin/index.html",
    "admin/styles.css",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _routes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            target = decorator.func
            if not isinstance(target, ast.Attribute):
                continue
            if target.attr not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                continue
            route = decorator.args[0].value
            if isinstance(route, str):
                result.append(f"{target.attr.upper()} {route}")
    return sorted(result)


def collect_inventory(root: Path) -> dict[str, object]:
    main_text = (root / "main.py").read_text(encoding="utf-8")
    build = re.search(r'APP_BUILD\s*=\s*"([^"]+)"', main_text)
    table_count = len(
        re.findall(
            r"CREATE TABLE IF NOT EXISTS",
            (root / "database.py").read_text(encoding="utf-8"),
        )
    )
    return {
        "build": build.group(1) if build else "",
        "frontend_line_count": len(
            (root / "static/index.html").read_text(encoding="utf-8").splitlines()
        ),
        "database_table_declarations": table_count,
        "routes": {
            name: _routes(root / name)
            for name in ROUTE_FILES
        },
        "sha256": {
            name: _sha256(root / name)
            for name in RUNTIME_FILES
        },
    }


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    json.dump(
        collect_inventory(root),
        sys.stdout,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""`ARCHITECTURE.md` dagi hajm raqamlarini kod bilan moslashtiradi.

## Muammo

Hujjatda modul hajmlari qo'lda yozilgan. Har bir refaktordan keyin ular
eskiradi va hech kim sezmaydi. Bu bir marta tuzatilgan edi — ikki PR
o'tgach yana noto'g'ri bo'lib qoldi. Qo'lda yozilgan raqam har doim
yolg'onga aylanadi.

## Yechim

Raqamlar belgilangan hududlar ichida avtomatik yangilanadi:

    <!-- STATS:boshlanish backend/app -->
    | `orders` | `/api/v1/orders` | 2 143 | buyurtmalar |
    <!-- STATS:tugadi -->

Belgi ichidagi har bir jadval qatorida: `` `nom` `` katakchasidan
**keyingi** katakcha raqam bo'lsa, o'sha raqam yangilanadi. Qolgan
hamma narsa — sarlavhalar, izohlar, ⚠️ belgilari — tegilmaydi.

Shu sababli ustun tartibi jadvaldan jadvalga farq qilsa ham ishlaydi.

## Ishlatish

    python scripts/update_architecture_stats.py           # yangilash
    python scripts/update_architecture_stats.py --check   # eskirgan bo'lsa xato
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "ARCHITECTURE.md"

START = re.compile(r"<!--\s*STATS:boshlanish\s+(\S+)\s*-->")
END = re.compile(r"<!--\s*STATS:tugadi\s*-->")

SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".css")
SKIP_PARTS = {"__pycache__", "node_modules", "dist"}

# `nom` katakchasi: backtick ichidagi **nisbiy** yo'l.
#
# Diqqat: `/` bilan boshlanmasligi shart. Jadvalda URL prefiksi ham
# backtick ichida (`` `/api/v1/orders` ``) va uni yo'l deb qabul qilsak,
# `ROOT / "/"` butun diskning ildiziga aylanadi — skript esa butun
# diskni skanerlab osilib qoladi.
NAME_CELL = re.compile(r"^`(?!/)([\w.-]+(?:/[\w.-]+)*)`$")
# Raqam katakchasi: ichida bo'shliq bo'lishi mumkin ("2 143"), oxirida ⚠️.
NUMBER_CELL = re.compile(r"^(\d[\d\s ]*)(\s*.*)$")


def count_lines(folder: Path) -> int:
    total = 0
    for path in folder.rglob("*"):
        if not path.is_file() or not path.name.endswith(SOURCE_SUFFIXES):
            continue
        if SKIP_PARTS & set(path.relative_to(folder).parts):
            continue
        total += len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    return total


def grouped(number: int) -> str:
    """1234 -> "1 234" — hujjatdagi mavjud uslub."""
    return f"{number:,}".replace(",", " ")


def rewrite(text: str) -> tuple[str, list[str]]:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    changes: list[str] = []
    root: Path | None = None

    for line in lines:
        start = START.search(line)
        if start:
            root = ROOT / start.group(1)
            out.append(line)
            continue
        if END.search(line):
            root = None
            out.append(line)
            continue
        if root is None or not line.lstrip().startswith("|"):
            out.append(line)
            continue

        cells = line.rstrip("\n").split("|")
        touched = False
        used: set[int] = set()
        for i in range(1, len(cells) - 1):
            name = NAME_CELL.match(cells[i].strip())
            if not name:
                continue
            folder = (root / name.group(1)).resolve()
            # Ikkinchi to'siq: `..` orqali hududdan chiqib ketmasin.
            if not folder.is_dir() or not folder.is_relative_to(root.resolve()):
                continue

            # Nomdan keyingi **birinchi raqamli** katakcha. Qat'iy "keyingi"
            # emas, chunki backend jadvalida orada URL prefiksi ustuni bor:
            #   | `orders` | `/api/v1/orders` | 2 143 | ... |
            target = None
            for j in range(i + 1, len(cells) - 1):
                if j in used:
                    break
                if NAME_CELL.match(cells[j].strip()):
                    break  # keyingi juftlik boshlandi
                number = NUMBER_CELL.match(cells[j].strip())
                if number:
                    target = (j, number)
                    break
            if target is None:
                continue

            j, number = target
            used.add(j)
            fresh = grouped(count_lines(folder))
            old = number.group(1).strip()
            if old != fresh:
                changes.append(f"{name.group(1)}: {old} -> {fresh}")
                cells[j] = f" {fresh}{number.group(2)} ".replace("  ", " ")
                touched = True
        out.append("|".join(cells) + "\n" if touched else line)

    return "".join(out), changes


def main() -> int:
    parser = argparse.ArgumentParser(description="ARCHITECTURE.md raqamlari")
    parser.add_argument(
        "--check", action="store_true", help="yozmaydi; eskirgan bo'lsa 1 qaytaradi"
    )
    args = parser.parse_args()

    text = DOC.read_text(encoding="utf-8")
    if not START.search(text):
        raise SystemExit(
            "ARCHITECTURE.md da `<!-- STATS:boshlanish <papka> -->` belgisi yo'q"
        )

    fresh, changes = rewrite(text)

    if args.check:
        if changes:
            print("ARCHITECTURE.md eskirgan:\n")
            for row in changes:
                print(f"  {row}")
            print(
                "\nTuzatish uchun:\n"
                "    python scripts/update_architecture_stats.py"
            )
            return 1
        print("ARCHITECTURE.md raqamlari kodga mos.")
        return 0

    if not changes:
        print("ARCHITECTURE.md allaqachon kodga mos.")
        return 0

    DOC.write_text(fresh, encoding="utf-8")
    print(f"ARCHITECTURE.md yangilandi ({len(changes)} ta raqam):\n")
    for row in changes:
        print(f"  {row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

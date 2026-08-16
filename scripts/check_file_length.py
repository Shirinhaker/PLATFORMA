"""Fayl uzunligi qo'riqchisi — "ratchet" usulida.

## Muammo

500 qatordan oshgan fayl ochilganda dasturchi uni butunlay o'qiy olmaydi.
Xato qidirish, o'zgartirish kiritish va kod ko'rigi — hammasi sekinlashadi.
Bu loyihada bir vaqtlar bitta faylda 2 154 qator bor edi.

## Nega ratchet

Barcha katta fayllarni bir kunda bo'lib bo'lmaydi — ular bosqichma-bosqich
tozalanmoqda. Shu sababli bu tekshiruv "hozirgi qarz" ro'yxatini
(`BASELINE`) biladi va uchta qoidani qo'llaydi:

1. **Yangi katta fayl qo'shib bo'lmaydi.** Ro'yxatda yo'q fayl chegaradan
   oshsa — xato.
2. **Ro'yxatdagi fayl o'sa olmaydi.** Faqat kichrayishi mumkin.
3. **Tozalangan fayl ro'yxatdan chiqarilishi shart.** Chegaradan tushgan
   fayl ro'yxatda qolsa — xato. Shusiz ro'yxat abadiy qolib ketardi.

Ya'ni g'ildirak faqat bir tomonga aylanadi: qarz o'sa olmaydi, kamayadi.

## Ishlatish

    python scripts/check_file_length.py            # tekshirish (CI shuni chaqiradi)
    python scripts/check_file_length.py --report   # hozirgi holat ro'yxati
    python scripts/check_file_length.py --update   # BASELINE ni qayta yozish
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from file_length_baseline import BASELINE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 500

# Qaysi fayllar tekshiriladi.
INCLUDE = (
    "backend/app/**/*.py",
    "frontend/src/**/*.ts",
    "frontend/src/**/*.tsx",
)

# Tekshiruvdan chetda qoladiganlar va sababi.
EXCLUDE_PARTS = {
    # Alembic migratsiyalari — bir marta yoziladi, hech qachon tahrirlanmaydi.
    "migrations",
    # Testlar uzun bo'lishi tabiiy: har bir holat alohida yoziladi.
    "tests",
    "node_modules",
    "dist",
}
EXCLUDE_SUFFIXES = (".test.ts", ".test.tsx", ".d.ts")

BASELINE_PATH = Path(__file__).resolve().parent / "file_length_baseline.py"


def _tracked_files() -> list[Path]:
    seen: set[Path] = set()
    for pattern in INCLUDE:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            if EXCLUDE_PARTS & set(path.relative_to(ROOT).parts):
                continue
            if path.name.endswith(EXCLUDE_SUFFIXES):
                continue
            seen.add(path)
    return sorted(seen)


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def current_sizes() -> dict[str, int]:
    return {
        path.relative_to(ROOT).as_posix(): _line_count(path)
        for path in _tracked_files()
    }


def over_limit() -> dict[str, int]:
    return {name: n for name, n in current_sizes().items() if n > LIMIT}


def check() -> int:
    actual = over_limit()
    problems: list[str] = []

    for name, size in sorted(actual.items()):
        allowed = BASELINE.get(name)
        if allowed is None:
            problems.append(
                f"  YANGI katta fayl: {name} — {size} qator "
                f"(chegara {LIMIT}). Uni modullarga bo'ling."
            )
        elif size > allowed:
            problems.append(
                f"  O'SDI: {name} — {size} qator, ilgari {allowed}. "
                f"Yangi kodni alohida modulga yozing."
            )

    for name, allowed in sorted(BASELINE.items()):
        if name not in actual:
            problems.append(
                f"  TOZALANGAN: {name} endi {LIMIT} dan kichik "
                f"(ilgari {allowed}). Uni BASELINE dan o'chiring: "
                f"python scripts/check_file_length.py --update"
            )

    if problems:
        print("Fayl uzunligi tekshiruvi o'tmadi:\n")
        print("\n".join(problems))
        print(f"\nJami {len(problems)} ta muammo.")
        return 1

    print(f"Fayl uzunligi tekshiruvi o'tdi. Qarzdagi fayllar: {len(BASELINE)}.")
    return 0


def report() -> int:
    sizes = sorted(over_limit().items(), key=lambda kv: -kv[1])
    for name, size in sizes:
        print(f"{size:6}  {name}")
    print(f"\n{len(sizes)} ta fayl {LIMIT} qatordan oshgan.")
    return 0


def update() -> int:
    """`BASELINE` ni bugungi holat bilan qayta yozadi.

    Fayl bo'lingandan keyin chaqiriladi — qarz ro'yxati qisqaradi.
    """

    rows = sorted(over_limit().items())
    body = "".join(f'    "{name}": {size},\n' for name, size in rows)
    BASELINE_PATH.write_text(
        '"""Fayl uzunligi qarzi — `check_file_length.py` uchun.\n\n'
        "Bu ro'yxatni qo'lda tahrirlamang. Faylni bo'lgach:\n\n"
        "    python scripts/check_file_length.py --update\n"
        '"""\n\n'
        "BASELINE: dict[str, int] = {\n" + body + "}\n",
        encoding="utf-8",
    )
    print(f"BASELINE yangilandi: {len(rows)} ta fayl.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="hozirgi holatni ko'rsatish")
    parser.add_argument("--update", action="store_true", help="BASELINE ni qayta yozish")
    args = parser.parse_args()
    if args.report:
        return report()
    if args.update:
        return update()
    return check()


if __name__ == "__main__":
    sys.exit(main())

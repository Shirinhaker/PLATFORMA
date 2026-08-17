"""Uzunlik qo'riqchisi — qarz faqat kamayadi.

## Muammo

500 qatordan oshgan fayl ochilganda dasturchi uni butunlay o'qiy olmaydi.
Xato qidirish, o'zgartirish kiritish va kod ko'rigi — hammasi sekinlashadi.
Bu loyihada bir vaqtlar bitta faylda 2 154 qator bor edi.

## Qoida

Barcha katta fayllarni bir kunda bo'lib bo'lmaydi, shuning uchun tekshiruv
"ratchet" usulida ishlaydi: har bir o'lchov uchun bitta qoida.

    hozirgi <= max(chegara, `main` dagi qiymat)

Ya'ni: chegaradan past narsa oshmasin; allaqachon oshib ketgani esa
o'smasin, faqat kichraysin. G'ildirak bir tomonga aylanadi.

## Uchta o'lchov

| O'lchov | Chegara | Nega shuncha |
|---|---:|---|
| Ishlab chiqarish fayli | 500 | Bir o'tirishda o'qiladigan hajm |
| Test fayli | 900 | Testda har bir holat alohida yoziladi — tabiiy uzunroq |
| Python funksiyasi | 120 | 499 qatorli faylda 400 qatorli funksiya yashirinishi mumkin |

## Nega saqlanadigan ro'yxat yo'q

Ilgari qarz `scripts/file_length_baseline.py` da saqlanardi va **har bir**
tartiblash PR'i o'sha faylga tegardi. Parallel ishlaganda merge konflikti
kafolatlangan edi, konflikt hal qilinganda esa raqam jimgina noto'g'ri
bo'lib qolishi mumkin — ya'ni qo'riqchi yolg'on gapira boshlardi.

Endi o'lchov `origin/main` ning o'zidan olinadi. Saqlanadigan ro'yxat
yo'q, demak konflikt ham yo'q.

## Ishlatish

    python scripts/check_file_length.py                 # tekshirish (CI shuni chaqiradi)
    python scripts/check_file_length.py --report        # hozirgi qarz ro'yxati
    python scripts/check_file_length.py --base <ref>    # boshqa nuqtaga solishtirish
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LIMIT = 500
TEST_LIMIT = 900
FUNCTION_LIMIT = 120

DEFAULT_BASE = "origin/main"

# Qaysi papkalar o'lchanadi.
SCOPE = ("backend/app", "backend/tests", "frontend/src")

SOURCE_SUFFIXES = (".py", ".ts", ".tsx")

# Tekshiruvdan chetda qoladiganlar va sababi.
EXCLUDE_PARTS = {
    # Alembic migratsiyalari — bir marta yoziladi, hech qachon tahrirlanmaydi.
    "migrations",
    "node_modules",
    "dist",
    "__pycache__",
}
EXCLUDE_SUFFIXES = (".d.ts",)


def is_test(name: str) -> bool:
    """Test fayllari uchun chegara yumshoqroq."""
    return (
        name.startswith("backend/tests/")
        or name.endswith((".test.ts", ".test.tsx"))
        or Path(name).name.startswith("test_")
    )


def in_scope(name: str) -> bool:
    if not name.startswith(SCOPE):
        return False
    if not name.endswith(SOURCE_SUFFIXES):
        return False
    if name.endswith(EXCLUDE_SUFFIXES):
        return False
    return not (EXCLUDE_PARTS & set(Path(name).parts))


def limit_for(name: str) -> int:
    return TEST_LIMIT if is_test(name) else LIMIT


# ---------------------------------------------------------------- o'lchash


def function_lengths(source: str, name: str) -> dict[str, int]:
    """Fayldagi har bir Python funksiyasining uzunligi.

    Nom bo'yicha kalitlanadi (klass emas): funksiya boshqa modulga
    ko'chirilganda ham tanilsin. Bu biroz bo'sh, lekin maqsad — **yangi**
    ulkan funksiyani to'xtatish, ko'chirilganini emas.
    """
    if not name.endswith(".py"):
        return {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    found: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            for decorator in node.decorator_list:
                start = min(start, decorator.lineno)
            length = node.end_lineno - start + 1
            found[node.name] = max(found.get(node.name, 0), length)
    return found


def current_state() -> tuple[dict[str, int], dict[str, tuple[int, str]]]:
    """(fayl -> qator, funksiya -> (qator, fayl)) — ishchi nusxadan."""
    files: dict[str, int] = {}
    functions: dict[str, tuple[int, str]] = {}
    for folder in SCOPE:
        base = ROOT / folder
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            name = path.relative_to(ROOT).as_posix()
            if not in_scope(name):
                continue
            source = path.read_text(encoding="utf-8", errors="ignore")
            files[name] = len(source.splitlines())
            for func, length in function_lengths(source, name).items():
                if length > functions.get(func, (0, ""))[0]:
                    functions[func] = (length, name)
    return files, functions


def base_state(ref: str) -> tuple[dict[str, int], dict[str, int]]:
    """`ref` dagi holat: (fayl -> qator, funksiya -> eng uzun qator)."""
    listing = subprocess.run(
        ["git", "ls-tree", "-r", ref, "--", *SCOPE],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if listing.returncode != 0:
        raise SystemExit(
            f"'{ref}' topilmadi. Avval uni oling:\n"
            f"    git fetch origin main\n"
            f"yoki boshqa nuqta ko'rsating: --base <ref>"
        )

    blobs: list[tuple[str, str]] = []
    for line in listing.stdout.splitlines():
        meta, _, name = line.partition("\t")
        parts = meta.split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        if in_scope(name):
            blobs.append((parts[2], name))

    if not blobs:
        return {}, {}

    # Bitta jarayonda hammasini o'qiymiz — fayl boshiga `git show` sekin.
    batch = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=ROOT,
        input=("\n".join(sha for sha, _ in blobs) + "\n").encode(),
        capture_output=True,
        timeout=120,
    )
    if batch.returncode != 0:
        raise SystemExit("git cat-file muvaffaqiyatsiz tugadi")

    files: dict[str, int] = {}
    functions: dict[str, int] = {}
    stream = batch.stdout
    offset = 0
    for _, name in blobs:
        newline = stream.index(b"\n", offset)
        header = stream[offset:newline].decode()
        size = int(header.split()[-1])
        body = stream[newline + 1 : newline + 1 + size]
        offset = newline + 1 + size + 1  # mazmun + yakuniy \n
        source = body.decode("utf-8", errors="ignore")
        files[name] = len(source.splitlines())
        for func, length in function_lengths(source, name).items():
            functions[func] = max(functions.get(func, 0), length)
    return files, functions


# ---------------------------------------------------------------- qoidalar


def check(ref: str) -> int:
    files, functions = current_state()
    base_files, base_functions = base_state(ref)
    problems: list[str] = []

    for name, size in sorted(files.items()):
        limit = limit_for(name)
        allowed = max(limit, base_files.get(name, 0))
        if size <= allowed:
            continue
        if name in base_files and base_files[name] > limit:
            problems.append(
                f"  O'SDI: {name} — {size} qator, `{ref}` da {base_files[name]}. "
                f"Yangi kodni alohida modulga yozing."
            )
        else:
            kind = "test fayli" if is_test(name) else "fayl"
            problems.append(
                f"  KATTA {kind}: {name} — {size} qator (chegara {limit}). "
                f"Uni modullarga bo'ling."
            )

    for func, (length, where) in sorted(functions.items()):
        allowed = max(FUNCTION_LIMIT, base_functions.get(func, 0))
        if length <= allowed:
            continue
        if func in base_functions and base_functions[func] > FUNCTION_LIMIT:
            problems.append(
                f"  FUNKSIYA O'SDI: {func}() — {length} qator ({where}), "
                f"`{ref}` da {base_functions[func]}."
            )
        else:
            problems.append(
                f"  KATTA FUNKSIYA: {func}() — {length} qator ({where}, "
                f"chegara {FUNCTION_LIMIT}). Uni bo'laklarga ajrating."
            )

    if problems:
        print("Uzunlik tekshiruvi o'tmadi:\n")
        print("\n".join(problems))
        print(f"\nJami {len(problems)} ta muammo.")
        return 1

    debt_files = sum(1 for n, s in files.items() if s > limit_for(n))
    debt_funcs = sum(1 for _, (n, _w) in functions.items() if n > FUNCTION_LIMIT)
    print(
        f"Uzunlik tekshiruvi o'tdi ({ref} ga nisbatan). "
        f"Qarz: {debt_files} fayl, {debt_funcs} funksiya."
    )
    return 0


def report() -> int:
    files, functions = current_state()

    over = sorted(
        ((n, s) for n, s in files.items() if s > limit_for(n)),
        key=lambda kv: -kv[1],
    )
    print(f"=== Chegaradan oshgan fayllar ({len(over)} ta)")
    for name, size in over:
        print(f"{size:6}  {name}  [chegara {limit_for(name)}]")

    long_funcs = sorted(
        ((f, n, w) for f, (n, w) in functions.items() if n > FUNCTION_LIMIT),
        key=lambda row: -row[1],
    )
    print(f"\n=== Chegaradan oshgan funksiyalar ({len(long_funcs)} ta, "
          f"chegara {FUNCTION_LIMIT})")
    for func, length, where in long_funcs:
        print(f"{length:6}  {func}()  —  {where}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Uzunlik qo'riqchisi")
    parser.add_argument(
        "--report", action="store_true", help="hozirgi qarzni ko'rsatish"
    )
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE,
        help=f"solishtirish nuqtasi (standart: {DEFAULT_BASE})",
    )
    args = parser.parse_args()
    if args.report:
        return report()
    return check(args.base)


if __name__ == "__main__":
    sys.exit(main())

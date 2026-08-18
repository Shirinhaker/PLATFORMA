"""Jonli domenlar bir martalik migratsiya paketiga bog'lanib qolmasin.

`app/legacy_migration/` — v1656 dan ma'lumot ko'chirish uchun yozilgan.
Ko'chirish tugagan. Ammo ilgari `catalog`, `listings`, `advertisements`,
`orders`, `education`, `public_discovery` va hatto `auth` shu paketdan
import qilardi — chunki umumiy enumlar va parol tekshiruvi tasodifan
o'sha yerda yozilgan edi.

Oqibati: yangi dasturchi "migratsiya tugagan, papkani o'chiraman" desa,
ishlayotgan sayt sinardi. Bu test shu chalkashlik qaytmasligini
ta'minlaydi.

Ruxsat etilgan istisnolar quyida sanab o'tilgan va har biriga sabab
yozilgan. Yangi istisno qo'shish — ongli qaror bo'lishi kerak, tasodif
emas.
"""

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

# Modul -> nega bu bog'liqlik haqli.
ALLOWED = {
    # Migratsiya modellarini ham yuklashi shart, aks holda SQLAlchemy
    # jadvallar orasidagi ForeignKey'ni topa olmaydi.
    "app/db/all_models.py": "barcha modellarni ataylab yuklaydi",
    # Nomida "legacy_import" bor — bu modullarning butun vazifasi eski
    # ma'lumotni o'qish.
    "app/ai_assistant/legacy_import.py": "vazifasi eski ma'lumotni o'qish",
    "app/taxi/legacy_import.py": "vazifasi eski ma'lumotni o'qish",
    # `legacy_id_map` jadvali migratsiyadan keyin ham qoladi va eski
    # v1656 ID'lari bo'yicha qidiruv ish vaqtida shunga tayanadi.
    "app/education/repository.py": "legacy_id_map ni ish vaqtida o'qiydi",
}


def _imports_legacy_migration(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").startswith("app.legacy_migration"):
                return True
        elif isinstance(node, ast.Import) and any(
            a.name.startswith("app.legacy_migration") for a in node.names
        ):
            return True
    return False


def _production_modules() -> list[Path]:
    return [
        path
        for path in sorted(APP.rglob("*.py"))
        if "legacy_migration" not in path.parts
    ]


def test_production_code_does_not_depend_on_the_migration_package():
    offenders = sorted(
        path.relative_to(APP.parent).as_posix()
        for path in _production_modules()
        if _imports_legacy_migration(path)
    )
    unexpected = [name for name in offenders if name not in ALLOWED]
    assert unexpected == [], (
        "Bu modullar bir martalik migratsiya paketidan import qilmoqda. "
        "Umumiy narsani `app/core/` ga chiqaring, yoki ALLOWED ga sabab "
        f"bilan qo'shing: {unexpected}"
    )


def test_allowlist_has_no_stale_entries():
    """Ruxsatnoma o'sib ketmasin — bog'liqlik yo'qolsa, qatori ham ketsin."""

    actual = {
        path.relative_to(APP.parent).as_posix()
        for path in _production_modules()
        if _imports_legacy_migration(path)
    }
    stale = sorted(set(ALLOWED) - actual)
    assert stale == [], f"ALLOWED da keraksiz qatorlar qoldi: {stale}"


def test_shared_enums_live_outside_the_migration_package():
    """`ReviewState`/`OwnerState` — domen holati, migratsiya artefakti emas."""

    core = (APP / "core" / "enums.py").read_text(encoding="utf-8")
    assert "class OwnerState" in core
    assert "class ReviewState" in core
    assert "OWNER_STATE_ENUM" in core
    assert "REVIEW_STATE_ENUM" in core

    legacy = (APP / "legacy_migration" / "model.py").read_text(encoding="utf-8")
    # Migratsiya kodi ularni ishlatishi mumkin, lekin **egasi** emas.
    assert not re.search(r"^class (OwnerState|ReviewState)\b", legacy, re.M)
    assert "from app.core.enums import" in legacy


def test_legacy_password_check_belongs_to_auth():
    """Eski parol xeshlari bazada qoladi — bu ish-vaqti masalasi."""

    assert (APP / "auth" / "legacy_passwords.py").exists()
    assert not (APP / "legacy_migration" / "passwords.py").exists()
    security = (APP / "auth" / "security.py").read_text(encoding="utf-8")
    assert "from app.auth.legacy_passwords import" in security

"""Domenlar o'rtasida umumiy enumlar va ularning SQL tiplari.

`OwnerState` va `ReviewState` ilgari `app/legacy_migration/model.py` da
turardi — chunki ularni birinchi bo'lib migratsiya kodi yozgan edi.

Natijada `catalog`, `listings`, `advertisements`, `orders`, `education`,
`public_discovery` — ya'ni **jonli production domenlari** — bir martalik
ko'chirish paketidan import qilardi. Yangi dasturchi uchun bu "migratsiya
papkasini o'chirsam bo'ladimi?" degan savolga noto'g'ri javob berardi:
o'chirsa, ishlayotgan kod sinardi.

Bu enumlar migratsiyaga tegishli emas — ular oddiy domen holatlari:
yozuvning egasi bormi (`OwnerState`) va yozuv ko'rikdan o'tganmi
(`ReviewState`). Shuning uchun ular shu yerda, umumiy joyda turadi.

SQL ENUM tiplari (`OWNER_STATE_ENUM`, `REVIEW_STATE_ENUM`) ham shu yerda,
chunki bir nechta jadval **aynan bitta** nusxani ulashishi kerak —
har bir jadval o'zi yaratsa, PostgreSQL'da nom to'qnashuvi bo'ladi.
"""

from enum import Enum

from sqlalchemy import Enum as SqlEnum


class OwnerState(str, Enum):
    """Yozuv real akkauntga bog'langanmi."""

    LINKED = "linked"
    UNLINKED = "unlinked"


class ReviewState(str, Enum):
    """Yozuv qo'lda ko'rikni talab qiladimi."""

    READY = "ready"
    REVIEW_REQUIRED = "review_required"


def enum_type(enum: type[Enum], name: str) -> SqlEnum:
    """Enum'ni SQL tipiga aylantiradi.

    `values_callable` shart: usiz SQLAlchemy enum **nomlarini**
    (`LINKED`) yozadi, bizga esa **qiymatlari** (`linked`) kerak.
    """

    return SqlEnum(
        enum,
        name=name,
        values_callable=lambda enum_class: [item.value for item in enum_class],
        validate_strings=True,
    )


OWNER_STATE_ENUM = enum_type(OwnerState, "owner_state")
REVIEW_STATE_ENUM = enum_type(ReviewState, "review_state")

"""Barcha model modullarini `Base.metadata` ga yuklaydi.

Modellar orasida domenlararo tashqi kalitlar bor — masalan
`stories.created_by_staff_id` → `staff_members.id`. SQLAlchemy bunday
kalitni faqat **ikkala** model yuklangandagina yechadi. Ilova ishlaganda
muammo ko'rinmaydi, chunki `app.main` hammasini import qiladi; alohida
kirish nuqtalari (migratsiya CLI, alembic) esa o'zi yuklashi kerak edi va
yuklamagani uchun quyidagicha yiqilardi:

    sqlalchemy.exc.NoReferencedTableError: Foreign key associated with
    column 'stories.created_by_staff_id' could not find table
    'staff_members'

Ro'yxat ochiq yozilgan (loyihadagi uslub). `tests/test_all_models.py`
uni `app/*/model*.py` fayllari bilan solishtiradi, ya'ni yangi domen
qo'shilib bu yerga yozilmasa test ogohlantiradi.
"""

from app.accounts import model as accounts_model  # noqa: F401
from app.admin import model as admin_model  # noqa: F401
from app.admin import moderation_model as admin_moderation_model  # noqa: F401
from app.advertisements import model as advertisements_model  # noqa: F401
from app.ai_assistant import model as ai_assistant_model  # noqa: F401
from app.auth import model as auth_model  # noqa: F401
from app.cabinet_records import model as cabinet_records_model  # noqa: F401
from app.cash_register import model as cash_register_model  # noqa: F401
from app.catalog import model as catalog_model  # noqa: F401
from app.debt_ledger import model as debt_ledger_model  # noqa: F401
from app.dining import model as dining_model  # noqa: F401
from app.documents import model as documents_model  # noqa: F401
from app.education import model as education_model  # noqa: F401
from app.expenses import model as expenses_model  # noqa: F401
from app.follows import model as follows_model  # noqa: F401
from app.inventory import model as inventory_model  # noqa: F401
from app.legacy_migration import model as legacy_migration_model  # noqa: F401
from app.listings import model as listings_model  # noqa: F401
from app.messages import model as messages_model  # noqa: F401
from app.notifications import model as notifications_model  # noqa: F401
from app.orders import model as orders_model  # noqa: F401
from app.outbox import model as outbox_model  # noqa: F401
from app.payments import model as payments_model  # noqa: F401
from app.profiles import model as profiles_model  # noqa: F401
from app.queues import model as queues_model  # noqa: F401
from app.reviews import model as reviews_model  # noqa: F401
from app.specialists import model as specialists_model  # noqa: F401
from app.staff import model as staff_model  # noqa: F401
from app.stories import model as stories_model  # noqa: F401
from app.taxi import model as taxi_model  # noqa: F401

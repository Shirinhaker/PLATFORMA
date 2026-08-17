"""Admin panel yo'llari.

Ilgari bitta 535 qatorlik `router.py` edi, 30 ta endpoint bilan.
Endi mavzu bo'yicha: deps, auth, payments, moderation, reports, audit.

**Tartib muhim.** FastAPI yo'llarni ro'yxatga tushgan tartibda
solishtiradi: masalan `/audit/export.csv` `/audit/{audit_id}` dan
oldin turishi shart, aks holda `export.csv` ID deb qabul qilinadi.

Shuning uchun bu yerda `include_router` aniq yozilgan. Ilgari modullar
umumiy `router` obyektiga import yon ta'siri orqali yozilardi — va
linter importlarni alifbo bo'yicha qayta tartiblab, yo'llar tartibini
jimgina buzdi. Bu usulda bunday bo'lmaydi.
"""

from fastapi import APIRouter

from app.admin.router_parts import audit, auth, moderation, payments, reports

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Tartib asl `router.py` dagidek.
for _part in (auth, payments, moderation, reports, audit):
    router.include_router(_part.router)

__all__ = ["router"]

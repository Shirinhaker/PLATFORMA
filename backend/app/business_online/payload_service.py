"""Eski nom — `app.business_online.payload` paketiga qayta-eksport.

Fayl 2 159 qator edi va bitta o'tirishda o'qib bo'lmasdi. Mazmuni
`payload/` paketiga mavzu bo'yicha bo'lindi (`payload/__init__.py` da
xarita bor).

Bu qobiq ataylab qoldirildi: `service.py` va testlar shu nomdan import
qiladi, ya'ni chaqiruv joylari umuman o'zgarmadi. Yangi kod to'g'ridan
to'g'ri `app.business_online.payload.<modul>` dan import qilsin.
"""

from app.business_online.payload.actions import *  # noqa: F403
from app.business_online.payload.advertisements import *  # noqa: F403
from app.business_online.payload.constants import *  # noqa: F403
from app.business_online.payload.dining import *  # noqa: F403
from app.business_online.payload.education import *  # noqa: F403
from app.business_online.payload.helpers import *  # noqa: F403
from app.business_online.payload.medical import *  # noqa: F403
from app.business_online.payload.medical_queue import *  # noqa: F403
from app.business_online.payload.service import *  # noqa: F403
from app.business_online.payload.spec import *  # noqa: F403

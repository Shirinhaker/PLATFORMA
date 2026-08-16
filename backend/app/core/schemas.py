"""Domenlar o'rtasida umumiy javob sxemalari.

`CreatedRead` va `MutationRead` ilgari `documents/schemas.py` va
`specialists/schemas.py` da alohida-alohida, lekin **bir xil nom bilan**
e'lon qilingan edi. FastAPI ikkalasini OpenAPI'da bitta sxemaga
qo'shib yuborardi — hozircha zararsiz, chunki tuzilishi aynan bir xil.

Tuzoq shundaki: biriga maydon qo'shilsa, OpenAPI ikkinchi domenni
**jimgina noto'g'ri** tasvirlab qolardi va generatsiya qilingan mijozlar
xato shakl bilan ishlardi.

Yagona ta'rif bu xavfni butunlay yo'q qiladi va OpenAPI sxema nomini
o'zgartirmaydi.
"""

from pydantic import BaseModel


class CreatedRead(BaseModel):
    """Yangi yozuv yaratildi."""

    ok: bool = True
    id: int


class MutationRead(BaseModel):
    """Yozuv o'zgartirildi yoki o'chirildi."""

    ok: bool = True

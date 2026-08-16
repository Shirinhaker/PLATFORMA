import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentContext:
    firma: str
    rahbar: str
    inn: str
    address: str
    phone: str
    sana: str
    raqam: str
    title: str
    contr: str
    contr_dir: str
    contr_inn: str
    contr_acc: str
    contr_bank: str
    contr_mfo: str
    contr_addr: str


def pick_document_type(
    prompt: str,
    direction: str = "",
    doc_type: str = "",
) -> tuple[str, str]:
    lowered = prompt.lower()
    if doc_type and doc_type != "Erkin shakldagi hujjat":
        return direction or "ichki", doc_type
    if any(
        token in lowered for token in ("shartnoma", "xizmat ko'rsatish", "oldi-sotdi")
    ):
        return "chiquvchi", "Shartnoma"
    if any(token in lowered for token in ("hisob", "invoice", "faktura")):
        return "chiquvchi", "Hisob-faktura"
    if any(token in lowered for token in ("yuk", "tovar topshir", "yetkaz")):
        return "chiquvchi", "Yuk xati"
    if "ishonchnoma" in lowered:
        return "chiquvchi", "Ishonchnoma"
    if "solishtirma" in lowered:
        return "chiquvchi", "Solishtirma dalolatnoma"
    if "akt" in lowered or "bajarilgan" in lowered:
        return "chiquvchi", "Akt"
    if "dalolatnoma" in lowered:
        return direction or "ichki", "Dalolatnoma"
    if "buyruq" in lowered:
        return "ichki", "Buyruq"
    if "ariza" in lowered:
        return "ichki", "Ariza"
    if "bayonnoma" in lowered:
        return direction or "ichki", "Bayonnoma"
    if "tilxat" in lowered or "qarz" in lowered:
        return "ichki", "Tilxat"
    if "xabarnoma" in lowered or "ogohlantirish" in lowered:
        return "ichki", "Xabarnoma"
    return direction or "ichki", doc_type or "Erkin shakldagi hujjat"


def build_document_context(
    business, body, contractor, *, today: str
) -> DocumentContext:
    def contractor_value(field: str) -> str:
        return str(getattr(contractor, field, "") or "").strip()

    return DocumentContext(
        firma=body.firm_name.strip() or business.name or "[Firma nomi]",
        rahbar=body.director.strip() or business.director or "[Rahbar F.I.Sh.]",
        inn=body.inn.strip() or business.tax_id or "[STIR]",
        address=business.address or "[Manzil]",
        phone=business.phone or "[Telefon]",
        sana=body.doc_date.strip() or today,
        raqam=body.number.strip() or "___",
        title=body.title.strip(),
        contr=contractor_value("name") or "[Kontragent / mijoz nomi]",
        contr_dir=contractor_value("director") or "[Kontragent rahbari]",
        contr_inn=contractor_value("inn") or "[STIR]",
        contr_acc=contractor_value("account") or "[hisob raqam]",
        contr_bank=contractor_value("bank") or "[bank]",
        contr_mfo=contractor_value("mfo") or "[MFO]",
        contr_addr=contractor_value("address") or "[manzil]",
    )


def contractor_snapshot(contractor) -> dict[str, str | int]:
    if contractor is None:
        return {}
    return {
        "id": contractor.id,
        "name": contractor.name or "",
        "director": contractor.director or "",
        "phone": contractor.phone or "",
        "address": contractor.address or "",
        "inn": contractor.inn or "",
        "account": contractor.account or "",
        "bank": contractor.bank or "",
        "mfo": contractor.mfo or "",
    }


def document_prompt_context(
    context: DocumentContext,
    contractor: dict[str, str | int],
    *,
    direction: str,
    doc_type: str,
    prompt: str,
) -> dict:
    return {
        "business": {
            "name": context.firma,
            "director": context.rahbar,
            "inn": context.inn,
            "address": context.address,
            "phone": context.phone,
        },
        "contractor": contractor,
        "requested_direction": direction,
        "requested_doc_type": doc_type,
        "date": context.sana,
        "number": context.raqam,
        "user_prompt": prompt,
    }


def local_document_body(
    prompt: str,
    direction: str,
    doc_type: str,
    context: DocumentContext,
) -> str:
    del direction
    amount = _amount_from_prompt(prompt)
    title = context.title or prompt[:80].strip() or doc_type
    c = context
    if doc_type == "Shartnoma":
        return f"""{c.firma}

XIZMAT KO'RSATISH SHARTNOMASI
№ {c.raqam}                                      {c.sana}

1. TOMONLAR
Ijrochi: {c.firma}, rahbari {c.rahbar}.
Buyurtmachi: {c.contr}, rahbari {c.contr_dir}.

2. SHARTNOMA PREDMETI
Ijrochi Buyurtmachiga quyidagi xizmat/tovar bo'yicha ish bajaradi:
{prompt}

3. SHARTNOMA SUMMASI
Umumiy summa: {amount}.
To'lov tartibi: tomonlar kelishuviga asosan naqd, karta yoki bank orqali amalga oshiriladi.

4. BAJARISH MUDDATI
Xizmat/tovar topshirish muddati: [muddatni kiriting].

5. TOMONLARNING MAJBURIYATLARI
Ijrochi ishni sifatli bajarish va o'z vaqtida topshirish majburiyatini oladi.
Buyurtmachi bajarilgan ishni qabul qilish va to'lovni amalga oshirish majburiyatini oladi.

6. NIZOLARNI HAL QILISH
Nizolar muzokara yo'li bilan, kelishilmasa amaldagi qonunchilik tartibida hal qilinadi.

7. REKVIZITLAR
Ijrochi: {c.firma}
STIR: {c.inn}
Manzil: {c.address}
Telefon: {c.phone}
Rahbar: {c.rahbar}

Buyurtmachi: {c.contr}
STIR: {c.contr_inn}
Manzil: {c.contr_addr}
Bank: {c.contr_bank} MFO: {c.contr_mfo}
Hisob raqami: {c.contr_acc}

Imzolar:
Ijrochi: ____________________     Buyurtmachi: ____________________
M.O'.                              M.O'.
"""
    if doc_type in ("Akt", "Dalolatnoma"):
        return f"""{c.firma}

BAJARILGAN ISHLAR DALOLATNOMASI
№ {c.raqam}                                      {c.sana}

Biz, quyida imzo chekuvchilar:
Ijrochi: {c.firma} nomidan {c.rahbar},
Buyurtmachi: {c.contr} nomidan {c.contr_dir},

quyidagi ish/xizmatlar bajarilganligini tasdiqlaymiz:
{prompt}

Umumiy summa: {amount}.

Buyurtmachi bajarilgan ish/xizmatlarni qabul qildi va e'tirozi yo'q.
Mazkur dalolatnoma ikki nusxada tuzildi.

Ijrochi: ____________________  {c.rahbar}
Buyurtmachi: _________________  {c.contr_dir}
"""
    if doc_type == "Hisob-faktura":
        return f"""{c.firma}

HISOB / INVOICE
№ {c.raqam}                                      {c.sana}

Yetkazib beruvchi: {c.firma}
STIR: {c.inn}
Manzil: {c.address}
Telefon: {c.phone}

Xaridor: {c.contr}
STIR: {c.contr_inn}

Tovar/xizmat nomi:
{prompt}

To'lov summasi: {amount}
To'lov muddati: [muddat]
To'lov usuli: [naqd/karta/bank]

Rahbar: ____________________ {c.rahbar}
M.O'.
"""
    if doc_type == "Yuk xati":
        return f"""{c.firma}

YUK XATI
№ {c.raqam}                                      {c.sana}

Jo'natuvchi: {c.firma}
Qabul qiluvchi: {c.contr}

Tovarlar / yuk tavsifi:
{prompt}

Miqdor: [miqdor]
Summa: {amount}
Yetkazish manzili: {c.contr_addr}

Topshirdi: ____________________ {c.rahbar}
Qabul qildi: __________________ {c.contr_dir}
"""
    if doc_type == "Buyruq":
        return f"""{c.firma}

BUYRUQ
№ {c.raqam}                                      {c.sana}

{title.upper()}

BUYURAMAN:
1. {prompt}
2. Mas'ul shaxs: [F.I.Sh.]
3. Ijro muddati: [muddat]

Asos: [asos hujjat]

Rahbar: ____________________ {c.rahbar}
M.O'.
"""
    if doc_type == "Tilxat":
        return f"""TILXAT

Sana: {c.sana}

Men, [F.I.Sh.], {c.firma} / {c.rahbar}dan quyidagilarni oldim yoki majburiyat oldim:
{prompt}

Summa: {amount}
Qaytarish muddati: [muddat]

Tilxat beruvchi: ____________________ [F.I.Sh.]
Pasport/JShShIR: [ma'lumot]
Telefon: [telefon]

Guvoh: ____________________ [F.I.Sh.]
"""
    if doc_type == "Xabarnoma":
        return f"""{c.firma}

XABARNOMA
№ {c.raqam}                                      {c.sana}

Kimga: {c.contr}

Hurmatli hamkor/mijoz,

Sizga quyidagi masala bo'yicha xabar beramiz:
{prompt}

Iltimos, ushbu xabarnomani ko'rib chiqib, belgilangan muddatda javob berishingizni so'raymiz.

Hurmat bilan,
{c.firma}
Rahbar: ____________________ {c.rahbar}
"""
    return f"""{c.firma}

{doc_type.upper()}
№ {c.raqam}                                      {c.sana}

Sarlavha: {title}

Hujjat mazmuni:
{prompt}

Qo'shimcha ma'lumotlar:
- Firma: {c.firma}
- Rahbar: {c.rahbar}
- Kontragent: {c.contr}
- Summa: {amount}

Imzo: ____________________ {c.rahbar}
M.O'.
"""


def _amount_from_prompt(prompt: str) -> str:
    match = re.search(
        r"(\d[\d\s.,]{2,})\s*(?:so['’`]?m|sum|uzs|сум)?",
        prompt,
        flags=re.IGNORECASE,
    )
    if not match:
        return "[summa]"
    raw = re.sub(r"[^0-9]", "", match.group(1))
    return _money(raw) if raw else match.group(1).strip()


def _money(value: str) -> str:
    try:
        return f"{int(value):,}".replace(",", " ") + " so'm"
    except (TypeError, ValueError):
        return "0 so'm"

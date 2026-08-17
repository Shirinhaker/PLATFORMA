# 3-bosqich — yakuniy hisobot

**Sana:** 2026-08-18 · **Maqsad:** 500 qatordan katta fayllarni o'qiladigan
modullarga bo'lish, funksional xatti-harakatni o'zgartirmasdan.

## Natija

**Boshlang'ich qarz: 53 ta fayl → hozir 0 ta ishlab chiqarish fayli.**

500 qatordan oshgan faol kod fayli na backendda, na frontendda qolmadi.

Qolgan 7 ta fayl — **test fayllari**. Ular asl 53 talik ro'yxatda yo'q
edi: test fayllari qo'riqchiga PR #211 da qo'shildi va shundan keyin
ko'rindi. Ular alohida ish (pastda).

## Bosqichlar bo'yicha

| Bosqich | Vazifa | Holat |
|---|---|---|
| 3.1 | Frontend ekranlari | ✅ 25 ta target, PR #194–#208 |
| 3.2 | Backend `service.py` | ✅ 14 ta xizmat, PR #199, #202, #209 |
| 3.3 | Repositoriylar | ✅ 4 ta, PR #202, #212 |
| 3.4 | `api/client.ts` | ✅ 1 863 → 366, 12 ta domen klienti |
| 3.5 | Qolgan fayllar | ✅ 8 ta fayl + 4 ta audit |

## 3.4 — `api/client.ts`

| | Qator | Metod |
|---|---:|---:|
| Boshida | 1 863 | 63 + domenlar |
| PR #197 dan keyin | 492 | 63 |
| Hozir | **366** | 38 |

Rejalashtirilgan uchta domen yopildi: `auth-client.ts` (84),
`profiles-client.ts` (77), `payments-client.ts` (49).

Tashqi `ApiClient` interfeysi **o'zgarmadi** — 63 ta metodning hech biri
yo'qolmadi, chaqiruv joylari ommaviy almashtirilmadi.

`client.ts` da qolgan 38 metod: taksi (11), mutaxassislar (8), reklama
(5), AI (4), biznes-onlayn (5), media (2), boshqa (3). Bular 3.4
rejasida sanalmagan — keyingi ishga qoldirildi.

## 3.5 — to'rtta audit

### 1. Katta schema/type fayllari

| Fayl | Qator |
|---|---:|
| `backend/app/education/schemas.py` | 470 |

**1 ta topildi**, chegaradan past. Frontend type fayllari PR #194 da
23 ta domen moduliga bo'lingan edi. Harakat talab qilinmaydi.

### 2. Takrorlangan umumiy yordamchi funksiyalar

**12 ta takror topildi**, 4 ta nom bo'yicha:

| Funksiya | Nechta ta'rif |
|---|---:|
| `money` | 6 |
| `initials` | 2 |
| `isService` | 2 |
| `isServiceOrder` | 2 |

**Diqqat: bularni shunchaki birlashtirib bo'lmaydi.** Oltita `money`
bir xil emas:

```
education/…/shared.tsx      Math.trunc(...)  + " so'm"   (to'g'ri apostrof)
inventory/WarehouseShared   trunc yo'q       + " so‘m"   (egri apostrof)
business-profile-config     trunc yo'q       + " so‘m"
profiles/StatisticsChart    trunc yo'q       + qo'shimchasiz
orders/order-store          qo'lda bo'sh joy + " so'm"
```

Ular kasrni turlicha ishlaydi, apostrof belgisi turlicha va biri
umuman "so'm" yozmaydi. Birlashtirish **foydalanuvchi ko'radigan matnni
o'zgartiradi**, bu esa refaktor qoidasiga zid.

**Xulosa:** bu texnik qarz emas, **hal qilinmagan mahsulot qarori** —
"pul qanday ko'rsatiladi?". Qaror qabul qilingach birlashtirish bir
soatlik ish.

### 3. Takrorlangan komponentlar

**5 ta nom, 13 ta ta'rif:**

| Komponent | Nechta fayl |
|---|---:|
| `Empty` | 4 |
| `AppToast` | 2 |
| `ErrorBox` | 2 |
| `ListingForm` | 2 |
| `PaymentsView` | 2 |

`Empty` va `ErrorBox` — sof UI, birlashtirish xavfsiz.
`ListingForm` va `PaymentsView` — bir xil nomli, **lekin har xil
vazifadagi** ekranlar (biri e'lon, biri kabinet ichidagi shakl).
Ularni birlashtirish emas, **qayta nomlash** kerak.

### 4. Takrorlangan validatsiyalar

Telefon/narx/sana uchun takroriy **regex topilmadi (0 ta)**.

Lekin bir xil xato **matni** bir necha faylda takrorlanadi:

| Matn | Nechta joy |
|---|---:|
| `"Hududingizni tanlang"` | 4 |
| `"Biznes nomini kiriting."` | 4 |
| `"To'lov summasini kiriting."` | 3 |
| `"Telefon raqamini kiriting."` | 3 |

**8 ta takroriy xabar** topildi. Bu xavfli emas, lekin matn
o'zgartirilganda bir joyda unutilishi mumkin.

## Tekshiruvlar

| Tekshiruv | Natija |
|---|---|
| Backend testlar | **821 passed**, 22 skipped |
| Frontend testlar | **556 passed** (92 fayl) |
| `ruff check` / `format` | toza |
| `tsc --noEmit` | xato yo'q |
| Production build | ✓ |
| **OpenAPI yuzasi** | 269 → 269, **tartibi bilan** aynan bir xil |
| Uzunlik qo'riqchisi | o'tdi |
| `ARCHITECTURE.md` | kodga mos |

## Qolgan qarz

### 7 ta test fayli

| Fayl | Qator |
|---|---:|
| `backend/tests/test_queue_domain_v1656.py` | 1 399 |
| `frontend/src/api/client.test.ts` | 1 260 |
| `backend/tests/test_orders_live_v1656.py` | 1 230 |
| `backend/tests/test_business_online_payload_service.py` | 1 218 |
| `backend/tests/test_legacy_reconcile.py` | 1 155 |
| `frontend/src/profiles/Profiles.test.tsx` | 987 |
| `frontend/src/app/App.test.tsx` | 902 |

Chegara 900. Ular o'sa olmaydi (ratchet), lekin bo'lish alohida ish:
test bo'lishda qoplama yo'qolishi xavfi bor, shuning uchun har birini
alohida tekshirish kerak.

### 48 ta uzun funksiya

Chegara 120 qator. Eng kattalari:

```
249  load_public_profile()          public_discovery/queries/profile.py
248  apply_medical_queue_action()   business_online/payload/medical_queue.py
237  apply_action()                 business_online/payload/actions.py
234  create_app()                   app/main.py
231  create_move()                  inventory/service_parts/moves.py
```

Bu qarz PR #211 gacha umuman ko'rinmasdi. U ham o'sa olmaydi.

## Yo'l-yo'lakay topilgan va tuzatilgan xatolar

Bo'lish jarayoni mavjud mo'rtlikni ko'rsatdi:

| # | Nima | Oqibati |
|---:|---|---|
| 1 | Bo'luvchi skript modul darajasidagi `Index(...)` larni **jimgina tashlab ketdi** | `education` da UNIQUE cheklov yo'qolgan; test ushladi. Skript endi tanimagan bayonotda to'xtaydi |
| 2 | Linter `admin/router` importlarini alifbo bo'yicha qayta tartibladi | Yo'llar ro'yxatga tushish tartibi buzildi; `/audit/export.csv` `{audit_id}` deb qabul qilinishi mumkin edi |
| 3 | 8 ta test manba faylining **matnini** o'qirdi | Bo'lgandan keyin yiqildi; endi paket bo'ylab qidiradi |
| 4 | `test_session_rollback_guard` 13 ta xizmatni yo'l bo'yicha ro'yxatga olgan | Yo'l o'zgargach qo'riqchi **jimgina ko'r bo'lardi** |
| 5 | 8 ta monkeypatch nomni e'lon qilingan joyda almashtirardi | Bo'lgandan keyin almashtirish ishlamay qolardi |
| 6 | 6 ta aylanma import | Har biri funksiyani to'g'ri modulga ko'chirish bilan yechildi |

## Tavsiya

1. **`money()` bo'yicha qaror** — pul qanday ko'rsatiladi? Qaror bo'lmasa
   bu takror abadiy qoladi.
2. **`ListingForm` va `PaymentsView` ni qayta nomlash** — bir xil nom,
   har xil vazifa chalkashlik beradi.
3. Test fayllarini bo'lish — alohida, ehtiyotkor ish.

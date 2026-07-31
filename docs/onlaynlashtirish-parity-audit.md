# Onlaynlashtirish v1656 paritet auditi

Sana: 2026-07-31

Haqiqat manbai: `static/index.html` (`BUILD v1656`) va guruh chegarasi uchun
`docs/kabinet-2-guruh-yonalishlar.md`.

## Audit chegarasi

Bu hujjat faqat Onlaynlashtirish guruhidagi 20 ekranni tekshiradi. Kassa,
Xarajatlar, Qarz daftari, Ombor, Statistika, ta'limning ichki bo'limlari,
AI yordamchi, Ma'muriyat, Hisobot, Sozlamalar, Xodimlar, Tabel, Hujjatlar va
Kontragentlar audit va keyingi implementatsiya chegarasidan tashqarida.

Holatlar:

- `migrated` — maxsus React ekran/View mavjud va kamida ekran oqimini
  tekshiradigan test bor;
- `partial` — React ekran/View mavjud, lekin ma'lum paritet nuqsoni yoki
  majburiy test qoplamasi yetishmaydi;
- `missing` — monolit ekrani uchun maxsus React View va
  `BusinessOnlineScreen.tsx` case mavjud emas.

Joriy React qamrovi: **20/20 ekran mavjud**. Qat'iy paritet holati:
**20 migrated, 0 partial, 0 missing**.

## 20 ekran inventari

| # | Ekran | Holat | React fayli | Monolitdagi qator oralig'i | Test fayli |
|---:|---|---|---|---|---|
| 1 | Profil — `cab-profil` | migrated | `frontend/src/profiles/BusinessProfileV3.tsx`; `frontend/src/profiles/BusinessProfileEditorV2.tsx` | `static/index.html:1814–1892, 11079–11197, 12446–12514` | `frontend/src/profiles/BusinessProfileParity.test.tsx` |
| 2 | Obunalar — `cab-subscriptions` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`SubscriptionsView`) | `static/index.html:1894–1934, 11907–11978` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx` |
| 3 | To'lovlar — `cab-payments` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`PaymentsView`) | `static/index.html:1936–1944, 11731–11895` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineClaudeReviewParity.test.tsx` |
| 4 | Mahsulot/Xizmatlar va guruhlar — `cab-items`, `cab-item-form` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessItemsV1656View.tsx`; `frontend/src/profiles/BusinessItemsV1656Forms.tsx` | `static/index.html:1956–1968, 2111–2139, 12716–13108` | `frontend/src/profiles/BusinessItemsV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineEditing.test.tsx`; `frontend/src/profiles/BusinessOnlineDirectionPlanV1656Parity.test.ts` |
| 5 | Stollar va xonalar — `cab-dining` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessDiningV1656View.tsx` | `static/index.html:1970–1976, 11531–11616` | `frontend/src/profiles/BusinessDiningV1656Parity.test.tsx` |
| 6 | Stol/xona zakazi — `cab-dining-order` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessDiningV1656View.tsx` (`DiningOrderView`) | `static/index.html:1978–1980, 11617–11632` | `frontend/src/profiles/BusinessDiningV1656Parity.test.tsx` |
| 7 | Xizmat ko'rsatuvchilar — `cab-medical-doctors` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessMedicalV1656View.tsx` (`BusinessMedicalProvidersV1656View`) | `static/index.html:2107, 11637–11641` | `frontend/src/profiles/BusinessMedicalV1656Parity.test.tsx` |
| 8 | Xizmat ko'rsatuvchi formasi — `cab-medical-doctor-form` | migrated | `frontend/src/profiles/BusinessMedicalV1656View.tsx` (xizmat ko'rsatuvchi formasi) | `static/index.html:2108, 11638–11641` | `frontend/src/profiles/BusinessMedicalV1656Parity.test.tsx` |
| 9 | Navbat — `cab-medical-queue` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessMedicalV1656View.tsx` (`BusinessMedicalQueueV1656View`) | `static/index.html:2109, 11642–11669` | `frontend/src/profiles/BusinessMedicalV1656Parity.test.tsx` |
| 10 | Kursga yozilishlar — `cab-education-enrollments` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessEducationEnrollmentsV1656View.tsx` | `static/index.html:1770, 2086, 5425, 9138–9141, 12005, 12140–12158, 12318`; `api.py:2675–2687, 3406–3438` | `frontend/src/profiles/BusinessEducationEnrollmentsV1656Parity.test.tsx`; `backend/tests/test_business_online_service.py`; `backend/tests/test_business_online_relational_service.py` |
| 11 | Buyurtmalar — `cab-orders` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`OrdersView`) | `static/index.html:2222–2230, 6296–6357, 6964–7132` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineClaudeReviewParity.test.tsx`; `frontend/src/profiles/BusinessOnlineDirectionPlanV1656Parity.test.ts` |
| 12 | Xizmat buyurtmalari — `cab-service-orders` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`OrdersView`) | `static/index.html:2231–2233, 6296–6357, 6964–7132` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineClaudeReviewParity.test.tsx`; `frontend/src/profiles/BusinessOnlineDirectionPlanV1656Parity.test.ts` |
| 13 | Suhbatlar — `chats`, `chat` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`MessagesView`) | `static/index.html:2630–2648, 7272–7489` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineClaudeReviewParity.test.tsx`; `frontend/src/profiles/BusinessOnlineParity.test.tsx` |
| 14 | Mijoz fikrlari — `cab-reviews` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`ReviewsView`) | `static/index.html:1946–1954, 11507–11529` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineMutations.test.tsx` |
| 15 | E'lonlar — `cab-elon` (`listings` tabi), `cab-elon-form` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineCrudEditorView.tsx` | `static/index.html:2141–2156, 2195–2220, 13214–13250, 13753–13852` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineClaudeReviewParity.test.tsx` |
| 16 | Reklamalar — `cab-elon` (`ads` tabi), `cab-ad-form` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineCrudEditorView.tsx` | `static/index.html:2141–2193, 13252–13596` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineClaudeReviewParity.test.tsx`; `frontend/src/profiles/BusinessOnlineParity.test.tsx` |
| 17 | Istoriyalar — `cab-stories` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineCrudEditorView.tsx` | `static/index.html:2746–2754, 3170–3650` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineClaudeReviewParity.test.tsx`; `frontend/src/profiles/BusinessOnlineParity.test.tsx` |
| 18 | Bildirishnomalar — `notify` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`NotificationsView`) | `static/index.html:2664–2706, 7531–7704` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineClaudeReviewParity.test.tsx`; `frontend/src/profiles/BusinessOnlineMutations.test.tsx` |
| 19 | Obunachilar — `cab-followers` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`PeopleView`) | `static/index.html:2756–2759, 12054–12060` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx`; `frontend/src/profiles/BusinessHeaderFollowCounts.test.tsx` |
| 20 | Kuzatilayotganlar — `cab-following` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`PeopleView`) | `static/index.html:2761–2764, 12047–12053` | `frontend/src/profiles/BusinessExistingOnlineV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineMutations.test.tsx` |

## Obunalar va to'lovlar test qoplamasi

Blok 4da `cab-subscriptions` va `cab-payments` uchun v1656 matni, klassi,
holati, kartasi va bo'sh holatini tekshiradigan alohida parity testlari
`BusinessExistingOnlineV1656Parity.test.tsx`da qaytarildi.

## Mahsulot/Xizmatlardagi tasdiqlangan paritet nuqsonlari

`cab-items`dagi to'rtta ma'lum nuqson Blok 4da yopildi:

1. mahsulot va guruh o'chirish tasdiqlash oynalari qaytarildi;
2. `Guruhini o'zgartirish` monolitdagi `openItemForm(item)` kabi aynan shu
   to'liq tahrirlash formasini ochadi;
3. formatlangan narx matni kartada o'zgartirilmasdan ko'rsatiladi;
4. bo'sh mahsulot va guruh nomi monolitdagi aniq xabarni ko'rsatadi.

Bularning barchasi `BusinessItemsV1656Parity.test.tsx`da qizil testdan
boshlab tasdiqlangan.

## Yo'nalishga moslashuv auditi

Monolit etaloni:

- 14 ta navbatli yo'nalish:
  `static/index.html:3680–3681`;
- dinamik xizmat ko'rsatuvchi/navbat matnlari va menyulari:
  `static/index.html:12076–12078`;
- 20 yo'nalish uchun `CAB_PLANS`:
  `static/index.html:12080–12110`;
- standart holatga qaytarish, maxsus ekranlarni ko'rsatish, `labels` va `hide`
  qoidalarini qo'llash:
  `static/index.html:12140–12177`.

Reactdagi yakuniy holat:

- `ONLINE_MENUS` Blok 1dan keyin ovqatlanishning `Stollar va xonalar`
  kartasini ham qamraydi; u faqat `Umumiy ovqatlanish` yo'nalishida
  Onlaynlashtirish ichida ko'rinadi:
  `frontend/src/profiles/business-profile-config.ts:245–261`;
- xizmat ko'rsatuvchilar va navbat kartalari `ONLINE_MENUS` ichida va faqat
  monolitdagi 14 navbatli yo'nalishda ko'rinadi; tibbiy yo'nalishda
  `Shifokor/Bemor`, qolganlarida `Xizmat ko‘rsatuvchi/Mijoz` matnlari
  qo'llanadi. Eski tibbiyot kartalari `DIRECTION_MENUS`dan olib tashlandi;
- `Kursga yozilishlar` kartasi `ONLINE_MENUS` ichida faqat
  `Ta'lim faoliyati` yo'nalishida ko'rinadi va qizil badge faqat yangi
  arizalar sonini ko'rsatadi;
- `BusinessProfileV3.tsx` ushbu kartalarni maxsus `BusinessOnlineScreen`ga,
  u esa uchta v1656 React ekraniga yo'naltiradi;
- `CAB_PLANS.labels` va `CAB_PLANS.hide`ning Onlaynlashtirishga tegishli
  qismi 20 yo'nalish uchun `business-profile-config.ts`da ko'chirildi;
- barcha 20 yo'nalishning mahsulot, buyurtma va xizmat buyurtmasi nom/tavsifi,
  ta'limdagi yashirish qoidasi hamda maxsus ekranlar ko'rinishi
  `BusinessOnlineDirectionPlanV1656Parity.test.ts`dagi 21 matritsa testi
  bilan, yo'nalishga xos kartalarning haqiqiy kabinetda chiqishi esa
  `BusinessOnlineDirectionRenderParity.test.tsx`dagi render testlari bilan
  tekshiriladi;
- `CAB_PLANS`ning Tizimlashtirishga tegishli label/hide qatorlari bu blokda
  ko'chirilmadi va Tizimlashtirish komponentlariga o'zgartirish kiritilmadi.

## Bloklar bo'yicha yakuniy holat

1. **Blok 1:** `cab-dining`, `cab-dining-order` maxsus React View va parity
   testlaridan o'tdi.
2. **Blok 2:** `cab-medical-doctors`, `cab-medical-doctor-form`,
   `cab-medical-queue` maxsus React View va 14 navbatli yo'nalish matritsasidan
   o'tdi.
3. **Blok 3:** `cab-education-enrollments` maxsus React View va faqat
   `Ta'lim faoliyati` ko'rinish qoidasidan o'tdi.
4. **Blok 4:** mavjud 14 ekran monolit bilan matn, CSS klass, xatti-harakat,
   bo'sh holat va tasdiqlash oynasi darajasida qayta tekshirildi; ushbu
   auditdagi barcha `partial` qatorlar yopildi.

Blok 4 yakuniy sharti:
`Onlaynlashtirish: 20/20 ekran migrated, qolgani: yo'q`.

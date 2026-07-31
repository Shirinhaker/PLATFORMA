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

Joriy React qamrovi: **14/20 ekran mavjud**. Qat'iy paritet holati:
**10 migrated, 4 partial, 6 missing**.

## 20 ekran inventari

| # | Ekran | Holat | React fayli | Monolitdagi qator oralig'i | Test fayli |
|---:|---|---|---|---|---|
| 1 | Profil — `cab-profil` | migrated | `frontend/src/profiles/BusinessProfileV3.tsx`; `frontend/src/profiles/BusinessProfileEditorV2.tsx` | `static/index.html:1814–1892, 11079–11197, 12446–12514` | `frontend/src/profiles/BusinessProfileParity.test.tsx` |
| 2 | Obunalar — `cab-subscriptions` | partial | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`SubscriptionsView`) | `static/index.html:1894–1934, 11907–11978` | **Yo'q** — Blok 4 ma'lum kamchiligi №5 |
| 3 | To'lovlar — `cab-payments` | partial | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`PaymentsView`) | `static/index.html:1936–1944, 11731–11868` | **Yo'q** — Blok 4 ma'lum kamchiligi №5 |
| 4 | Mahsulot/Xizmatlar va guruhlar — `cab-items`, `cab-item-form` | partial | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessItemsV1656View.tsx`; `frontend/src/profiles/BusinessItemsV1656Forms.tsx` | `static/index.html:1956–1968, 2111–2139, 12716–13108` | `frontend/src/profiles/BusinessItemsV1656Parity.test.tsx`; `frontend/src/profiles/BusinessOnlineEditing.test.tsx` |
| 5 | Stollar va xonalar — `cab-dining` | missing | **Yo'q**; hozir `DIRECTION_MENUS` kartasi umumiy `CabinetDataView`ga tushadi | `static/index.html:1970–1976, 11531–11616` | **Yo'q** — Blok 1 |
| 6 | Stol/xona zakazi — `cab-dining-order` | missing | **Yo'q**; `BusinessOnlineScreen.tsx` case mavjud emas | `static/index.html:1978–1980, 11617–11632` | **Yo'q** — Blok 1 |
| 7 | Xizmat ko'rsatuvchilar — `cab-medical-doctors` | missing | **Yo'q**; hozirgi `medical-queues` kartasi maxsus View ochmaydi | `static/index.html:2107, 11637–11641` | **Yo'q** — Blok 2 |
| 8 | Xizmat ko'rsatuvchi formasi — `cab-medical-doctor-form` | missing | **Yo'q**; `BusinessOnlineScreen.tsx` case mavjud emas | `static/index.html:2108, 11638–11641` | **Yo'q** — Blok 2 |
| 9 | Navbat — `cab-medical-queue` | missing | **Yo'q**; hozirgi `medical-queues` kartasi umumiy `CabinetDataView`ga tushadi | `static/index.html:2109, 11642–11669` | **Yo'q** — Blok 2 |
| 10 | Kursga yozilishlar — `cab-education-enrollments` | missing | **Yo'q**; React menyu va `BusinessOnlineScreen.tsx` case mavjud emas | `static/index.html:2086, 9138–9141` | **Yo'q** — Blok 3 |
| 11 | Buyurtmalar — `cab-orders` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`OrdersView`) | `static/index.html:2222–2230, 6964–7053` | `frontend/src/profiles/BusinessOnlineParity.test.tsx` |
| 12 | Xizmat buyurtmalari — `cab-service-orders` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`OrdersView`) | `static/index.html:2231–2233, 6964–7053` | `frontend/src/profiles/BusinessOnlineParity.test.tsx` |
| 13 | Suhbatlar — `chats`, `chat` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`MessagesView`) | `static/index.html:2630–2648, 7272–7489` | `frontend/src/profiles/BusinessOnlineParity.test.tsx` |
| 14 | Mijoz fikrlari — `cab-reviews` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`ReviewsView`) | `static/index.html:1946–1954, 11507–11529` | `frontend/src/profiles/BusinessOnlineParity.test.tsx`; `frontend/src/profiles/BusinessOnlineMutations.test.tsx` |
| 15 | E'lonlar — `cab-elon` (`listings` tabi), `cab-elon-form` | partial | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineCrudEditorView.tsx` | `static/index.html:2141–2156, 2195–2220, 13214–13250, 13753–13852` | **Biznes ekraniga alohida parity assert yo'q** — Blok 4 |
| 16 | Reklamalar — `cab-elon` (`ads` tabi), `cab-ad-form` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineCrudEditorView.tsx` | `static/index.html:2141–2193, 13252–13596` | `frontend/src/profiles/BusinessOnlineParity.test.tsx` |
| 17 | Istoriyalar — `cab-stories` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineCrudEditorView.tsx` | `static/index.html:2746–2754, 3170–3640` | `frontend/src/profiles/BusinessOnlineParity.test.tsx` |
| 18 | Bildirishnomalar — `notify` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`NotificationsView`) | `static/index.html:2664–2706, 7531–7704` | `frontend/src/profiles/BusinessOnlineParity.test.tsx`; `frontend/src/profiles/BusinessOnlineMutations.test.tsx` |
| 19 | Obunachilar — `cab-followers` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`PeopleView`) | `static/index.html:2756–2759, 12054–12060` | `frontend/src/profiles/BusinessOnlineParity.test.tsx`; `frontend/src/profiles/BusinessHeaderFollowCounts.test.tsx` |
| 20 | Kuzatilayotganlar — `cab-following` | migrated | `frontend/src/profiles/BusinessOnlineScreen.tsx`; `frontend/src/profiles/BusinessOnlineViews.tsx` (`PeopleView`) | `static/index.html:2761–2764, 12047–12053` | `frontend/src/profiles/BusinessOnlineParity.test.tsx`; `frontend/src/profiles/BusinessOnlineMutations.test.tsx` |

## Mahsulot/Xizmatlardagi tasdiqlangan paritet nuqsonlari

`cab-items` React View mavjud, lekin quyidagi to'rtta sabab bilan `partial`:

1. mahsulot yoki guruhni o'chirishda monolitdagi tasdiqlash oynasi yo'q;
2. `Guruhini o'zgartirish` oddiy tahrirlash formasini ochadi;
3. formatlangan narx matni son sifatida o'qilmasa kartada
   `Narx kelishiladi` chiqadi;
4. bo'sh nom bilan saqlashda foydalanuvchiga xato ko'rsatilmaydi.

Bu nuqsonlar Blok 4da avval qizil parity testlari bilan mahkamlanadi.

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

Reactdagi joriy holat:

- `ONLINE_MENUS` faqat mavjud 14 ekranni qamraydi:
  `frontend/src/profiles/business-profile-config.ts:245–260`;
- ovqatlanish va tibbiyot kartalari `DIRECTION_MENUS` ichida, kursga
  yozilishlar esa umuman yo'q:
  `frontend/src/profiles/business-profile-config.ts:280–288`;
- `BusinessProfileV3.tsx` faqat `ONLINE_MENUS` elementlarini maxsus
  `BusinessOnlineScreen`ga yo'naltiradi; `DIRECTION_MENUS` elementlari
  umumiy `CabinetDataView`ga tushadi:
  `frontend/src/profiles/BusinessProfileV3.tsx:94–103, 198–245`;
- `CAB_PLANS.labels` va `CAB_PLANS.hide`ning React ekvivalenti mavjud emas;
  yo'nalishga xos kartalar monolitdagidek Onlaynlashtirish ichida emas,
  alohida `Yo'nalishga xos bo'limlar` guruhida chiqadi:
  `frontend/src/profiles/BusinessProfileV3.tsx:373–382`.

Shuning uchun Blok 1–3 ekran Viewlarini ko'chirish bilan birga ularning aynan
monolitdagi yo'nalishlarda, nomlarda va Onlaynlashtirish guruhida chiqishini
parity testlari bilan majburiy qiladi. `CAB_PLANS`ning Tizimlashtirishga
tegishli qatorlari bu vazifa doirasida tahrirlanmaydi.

## Bloklar bo'yicha chiqish mezoni

1. **Blok 1:** `cab-dining`, `cab-dining-order` maxsus React View va parity
   testlaridan o'tadi.
2. **Blok 2:** `cab-medical-doctors`, `cab-medical-doctor-form`,
   `cab-medical-queue` maxsus React View va 14 navbatli yo'nalish matritsasidan
   o'tadi.
3. **Blok 3:** `cab-education-enrollments` maxsus React View va faqat
   `Ta'lim faoliyati` ko'rinish qoidasidan o'tadi.
4. **Blok 4:** mavjud 14 ekran monolit bilan matn, CSS klass, xatti-harakat,
   bo'sh holat va tasdiqlash oynasi darajasida qayta tekshiriladi; ushbu
   auditdagi barcha `partial` qatorlar yopiladi.

Blok 4 yakuniy sharti:
`Onlaynlashtirish: 20/20 ekran migrated, qolgani: yo'q`.

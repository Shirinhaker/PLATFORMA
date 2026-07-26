# Ko‘prik v1616 — xavfsizlik va 20 ta demo taklif

## Buzilmasligi shart bo‘lgan qoidalar

- Istoriya ishlashi tariflardan mustaqil qoladi.
- Pro biznes xaritada maxsus rang yoki alohida metka bilan ajratilmaydi.
- Oddiy foydalanuvchining yashash tumani boshqa foydalanuvchilarga berilmaydi.
- Vaqtinchalik yopiq rejim o‘chirilmaydi; faqat berilgan Telegram IDlar kiradi.
- Avvalgi 126 testning barchasi yashil qolishi kerak.

## P0 — TEST_MODE OTP sizishi

**Talab:** TEST_MODE bir martalik kodni HTTP javobida, maxsus endpointda yoki frontendda ko‘rsatmasligi kerak.

**Qabul mezoni:** kod faqat xesh ko‘rinishida bazaga yoziladi; `request-code` javobida `test_code` yo‘q; `/_test/last_code` yo‘q; interfeys “Sinov kodi”ni chiqarmaydi. Avtomatik sinovda zarur bo‘lsa, kod server muhitidagi `TEST_OTP_CODE` orqali belgilanadi va mijozga qaytarilmaydi.

**Test:** `test_v1616_security_contract.V1616SecurityContractTests.test_test_mode_never_returns_otp_to_http_client`.

## P0 — media va yuklangan statik fayllar bloki

**Talab:** vaqtinchalik yopiq rejim `/media/`, `/profile-media/` va `/uploads/` fayllarini ham qamrashi kerak.

**Qabul mezoni:** ruxsatsiz to‘g‘ridan-to‘g‘ri fayl so‘rovi 403; ruxsatli foydalanuvchining tekshirilgan API so‘rovi qisqa muddatli, imzolangan, HttpOnly cookie beradi; shu cookie bilan media ochiladi; yopiq rejimdagi media javobi `private, no-store` bo‘ladi.

**Test:** `test_temporary_access_control.TemporaryAccessControlTests.test_media_and_uploaded_static_files_need_privileged_access_cookie`.

## P1 — diagnostika endpointlari

**Talab:** diagnostika odatda mavjud bo‘lmasligi, yoqilganda ham faqat maxsus IDlarga va shaxsiy ma’lumotsiz ishlashi kerak; sozlash GET orqali holatni o‘zgartirmasligi kerak.

**Qabul mezoni:** `PRIVILEGED_DIAGNOSTICS_ENABLED` yo‘q bo‘lsa `/_dbinfo` 404; yoqilganda faqat umumiy sonlar va build qaytadi; DB yo‘li, login, Telegram ID va ism qaytmaydi; `GET /_setup` 405, o‘zgartirish faqat himoyalangan POST orqali.

**Test:** `test_temporary_access_control.TemporaryAccessControlTests.test_diagnostics_are_off_by_default_and_safe_when_explicitly_enabled`.

## P1 — Bearer/initData tartibi

**Talab:** bitta so‘rovda faqat bitta autentifikatsiya usuli yuborilishi va qabul qilinishi kerak.

**Qabul mezoni:** frontend Staff, aks holda Bearer, aks holda Telegram initData yuboradi; Bearer va initData birga kelsa server 400 va `ambiguous_authentication` qaytaradi.

**Test:** `test_v1616_security_contract.V1616SecurityContractTests.test_frontend_sends_exactly_one_authentication_mechanism` va `test_temporary_access_control.TemporaryAccessControlTests.test_mixed_bearer_and_init_data_is_rejected_as_ambiguous`.

## P1 — profil tumani jimgina o‘chmasligi

**Talab:** noto‘g‘ri tuman eski tumanni o‘chirib yubormasligi kerak.

**Qabul mezoni:** ro‘yxatda yo‘q, bo‘sh bo‘lmagan qiymat 400 qaytaradi va eski qiymat saqlanadi; faqat aniq bo‘sh satr tumanni tozalaydi; maydon yuborilmasa o‘zgarmaydi.

**Test:** `test_location_keys.LocationKeyApiTests.test_invalid_manual_district_is_rejected_without_erasing_existing_value` va `test_explicit_empty_district_still_clears_location`.

## P2 — regions.js bog‘liqligi

**Talab:** backend tumanlarni frontend JavaScript faylini regex bilan o‘qib olmasligi kerak.

**Qabul mezoni:** backend alohida tuzilmali `district_catalog.py` katalogidan foydalanadi; `location_keys.py` ichida `regions.js` va `pathlib.Path` yo‘q.

**Test:** `test_location_keys.LocationKeysUnitTests.test_backend_catalog_does_not_parse_frontend_regions_javascript`.

## P2 — karusel avto-yangilanishi

**Talab:** tuman takliflari 30 daqiqalik navbat chegarasida sahifani qayta ochmasdan yangilanishi kerak.

**Qabul mezoni:** keyingi slot chegarasiga timer qo‘yiladi; chegara kelganda majburiy yuklanadi; yashirin sahifa qayta ko‘ringanda ham yangi ma’lumot olinadi.

**Test:** `test_district_offers_frontend_contract.DistrictOffersFrontendContractTests.test_carousel_schedules_refresh_at_the_next_rotation_slot`.

## P2 — tarif oshkorligi

**Talab:** xarita javobi profilning Pro yoki obuna orqali chiqqanini oshkor qilmasligi kerak.

**Qabul mezoni:** Pro va kuzatiladigan profillar bir xil oddiy metka ma’lumotiga ega; javobda `source`, `is_pro` va `marker_style` yo‘q; oddiy foydalanuvchi tumani ham yo‘q.

**Test:** `test_pro_follow_map_api.ProAndFollowMapApiTests.test_map_contains_active_pro_and_followed_businesses_with_normal_markers`.

## Xarita ostidagi 20 ta demo taklif

**Talab:** loyiha egasi turli kartalar qanday ishlashini bitta tumanda tekshira olishi kerak.

**Qabul mezoni:** yopiq rejimda faqat maxsus ID `POST /api/home/district-offers/demo-seed` orqali 20 ta idempotent demo biznes yaratadi; 10 tasi mahsulot, 10 tasi e’lon; Plus va Pro navbat bilan beriladi; karusel bir slotda 20 tagacha kartani qaytaradi. Bosh sahifadagi “20 ta demo taklif qo‘shish” tugmasi shu amalni bajaradi.

**Test:** `test_pro_follow_map_api.ProAndFollowMapApiTests.test_z_privileged_demo_seed_creates_twenty_varied_test_offers` va district-offers limit/rotatsiya testlari.

# Biznes ochish v1656 migratsiyasi

Bu modul monolitdagi `Biznes ochish` oqimini typed FastAPI va React qatlamiga
ko‘chiradi. Eski `static/index.html` va `main.py` manba sifatida saqlanadi.

## Parity oqimi

1. Biznesi yo‘q foydalanuvchi kabinetida `🏪 Biznes ochish` tugmasi ko‘rinadi.
2. Forma biznes nomi, yo‘nalish, faoliyat turi, telefon va manzilni qabul qiladi.
3. `POST /api/v1/business-opening` faqat user kabineti egasi va to‘g‘ri CSRF
   tokeni bilan ishlaydi.
4. Bitta tranzaksiyada business account, business profile va profile link
   yaratiladi hamda user profilidagi `has_business` yoqiladi.
5. Yangi login/parol javobda bir marta ko‘rsatiladi; Telegram uchun outboxda
   faqat shifrlangan ko‘rinishi saqlanadi.
6. `Biznes kabinetga o'tish` mavjud typed cabinet-switch endpointidan
   foydalanadi; qayta login talab qilinmaydi.

Mavjud `accounts`, `business_profiles`, `user_profiles` va `profile_links`
jadvallari barcha zarur constraintlarni allaqachon beradi. Shu sababli yangi
Alembic schema migratsiyasi talab qilinmaydi.

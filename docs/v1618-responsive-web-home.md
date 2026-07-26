# Ko‘prik v1618 — responsive web bosh sahifa va Reklamalar

**Talab:** dastlabki Ko‘prik web maketi hozirgi istoriya, xarita, 20 ta tuman taklifi, e’lon, tarif va xavfsizlik funksiyalariga moslashtirilsin. Yuqoridagi `Reklama` tugmasi alohida reklama bo‘limini ochsin.

**Qabul mezoni:** 1080 px va undan katta ekranda to‘liq kenglikdagi Ko‘prik headeri, `Bosh sahifa / E’lonlar / Reklama` menyusi, qidiruv paneli va xarita bilan ikki ustunli bosh qism chiqadi. Telefon va iPad maketi ishlashda davom etadi. `Reklama` tugmasi `ads` ekranini ochadi; faol reklamalar kartalarda ko‘rinadi; reklama kartasi egasining sahifasiga, `Reklama joylashtirish` esa joriy user/biznes reklama boshqaruviga olib boradi.

**Test:** `test_web_home_frontend_contract.py` header, responsive tuzilma, reklama navigatsiyasi va avvalgi funksiyalar mavjudligini tekshiradi. To‘liq regressiya barcha eski testlarni ham ishga tushiradi.

# Ko‘prik v1619 — alohida E’lonlar oynasi

**Talab:** yuqori web menyusida alohida `Reklama` tugmasi bo‘lmasin. `E’lonlar` bosh sahifada turmasin va menyudan alohida oynada ochilsin. Reklama banneri dastlabki web maketdagidek bosh sahifaning o‘rtasida tursin.

**Qabul mezoni:** headerda `Bosh sahifa` va `E’lonlar` qoladi. `E’lonlar` bosilganda `listings` ekrani ochiladi; toifalar va natijalar shu ekranda ishlaydi. Bosh sahifada e’lon sarlavhasi/toifalari yo‘q. Reklama banneri xarita va tuman takliflaridan keyin joylashadi. Istoriya, xarita, tarif, maxfiylik, vaqtinchalik blok va 68 soniyalik karusel o‘zgarmaydi.

**Test:** `test_web_home_frontend_contract.py` alohida e’lon oynasi, reklamaning elementlar tartibidagi o‘rni va `Reklama` menyusi olib tashlanganini tekshiradi. To‘liq regressiya avvalgi testlarni ham bajaradi.

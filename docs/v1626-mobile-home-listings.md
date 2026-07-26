# Ko‘prik v1626 — telefonda bosh sahifadagi E’lonlar tuzatishi

## Sabab

v1619 da `E’lonlar` bosh sahifadan alohida `listings` oynasiga ko‘chirilgan edi.
Bu oynaga faqat yuqoridagi web menyu (`webListingsBtn`) orqali kirilardi, menyu esa
`web-only` bo‘lib, 1080 px dan kichik ekranlarda yashiringan. Natijada telefonda
e’lonlar na bosh sahifada ko‘rinar, na boshqa yo‘l bilan ochilar edi.

## Tuzatish

- Bosh sahifaga `homeElonMount` joyi qo‘shildi (tuman takliflaridan keyin).
- `listings` oynasidagi kontent `elonSection` konteyneriga o‘raldi.
- `placeElonSection()` funksiyasi ekran kengligiga qarab bo‘limni ko‘chiradi:
  - `<1080px` — E’lonlar bo‘limi bosh sahifada turadi (v1619 dan avvalgidek,
    toifalar bosh sahifadagi xarita bilan ishlashda davom etadi);
  - `>=1080px` — bo‘lim alohida `listings` oynasiga qaytadi, yuqori menyudagi
    `E’lonlar` tugmasi avvalgidek ishlaydi.
- Oyna kengligi o‘zgarsa (`matchMedia change`), joylashuv avtomatik yangilanadi;
  telefon o‘lchamiga o‘tilganda bo‘sh `listings` oynasida qolib ketilmaydi.
- DOM tugunlari ko‘chiriladi (nusxa olinmaydi), shuning uchun `elonRow` va
  `elonList` dagi mavjud event listenerlar o‘z holicha ishlaydi.

## Qabul mezoni

Telefonda bosh sahifa: istoriyalar → qidiruv/xarita → reklama → tuman takliflari →
E’lonlar (toifalar va ro‘yxat). Desktopda (>=1080px) bosh sahifa o‘zgarmaydi,
`E’lonlar` menyudan alohida oynada ochiladi. Reklama banneri o‘rni, 68 soniyalik
karusel va avvalgi funksiyalar o‘zgarmaydi.

## Test

- `tests/test_mobile_home_listings_contract.py` — mount joyi, elementlar tartibi,
  `placeElonSection()` va desktop kontrakt saqlanganini tekshiradi.
- Versiya tekshiruvlari `v1626` ga yangilandi; to‘liq regressiya barcha eski
  testlarni ham bajaradi.

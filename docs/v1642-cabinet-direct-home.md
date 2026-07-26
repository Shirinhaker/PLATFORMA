# v1642 — Kabinetdan bosh sahifaga to‘g‘ridan-to‘g‘ri chiqish

## Muammo

Kabinetga login yoki boshqa ichki sahifa orqali kirilganda brauzer tarixidagi oldingi
sahifa ko‘pincha bosh sahifa bo‘lmaydi. Shu sabab yuqoridagi orqaga tugmasi
foydalanuvchini avval login yoki kabinetning ichki sahifalariga olib borishi mumkin.

## Yechim

- Biznes va oddiy foydalanuvchi kabinetida yuqori o‘ng tomonda **Bosh sahifa**
  tugmasi ko‘rsatiladi.
- Tugma kabinetning ichki `cab-*` va `ucab-*` bo‘limlarida ham ko‘rinadi.
- Tugma brauzer tarixiga bog‘liq emas va to‘g‘ridan-to‘g‘ri `home` sahifasini ochadi.
- Chapdagi orqaga tugmasi kabinet ichida oldingi bo‘limga qaytish uchun saqlanadi.
- Juda kichik telefon ekranida joy tejash uchun tugmada faqat uy belgisi ko‘rinadi.

## Qabul mezonlari

- Oddiy kabinetdan bosh sahifaga bir bosishda chiqish mumkin.
- Biznes kabinetidan bosh sahifaga bir bosishda chiqish mumkin.
- Kabinetning ichki bo‘limlarida ham bosh sahifa tugmasi mavjud.
- Bosh sahifa tugmasi login yoki brauzer tarixiga qaytmaydi.
- Mavjud orqaga tugmasi ishlashda davom etadi.

## Test

`tests/test_browser_history_navigation_contract.py` ichidagi
`test_cabinet_has_direct_home_action_independent_of_history` testi tugma,
kabinet yo‘nalishlarini aniqlash va to‘g‘ridan-to‘g‘ri `nav("home")` chaqirig‘ini
tekshiradi.

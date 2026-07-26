# Ko‘prik v1647 — manzil, kirish va profil dizayni

## Natija

Berilgan qoramtir Ko‘prik dizayni amaldagi loyiha ichiga ko‘rinish qatlami
sifatida o‘rnatildi.

Yangilangan qismlar:

1. Manzilni belgilash.
2. Kabinetga kirish va Telegram tasdiqlash kodi.
3. Oddiy yoki biznes profil sifatida ro‘yxatdan o‘tish.
4. Xodimlar kirishi.
5. Oddiy foydalanuvchi, mutaxassis va biznes profil/kabinet ekranlari.

## Saqlangan funksiyalar

- Barcha mavjud element IDlari va JavaScript hodisalari saqlandi.
- API endpointlari va ma’lumotlar bazasi o‘zgarmadi.
- Telegram kod yuborish va 30 kunlik sessiya tartibi o‘zgarmadi.
- Firma logini, xodim logini, parol va ruxsatlar o‘zgarmadi.
- Oddiy va biznes kabinet ma’lumotlari aralashmadi.
- Foydalanuvchi tumani maxfiyligi saqlandi.
- Qidiruv, xarita metkalari, obunalar va istoriyalar mantiqiga tegilmadi.

## Responsive ko‘rinish

- Telefon: bitta ustunli, to‘liq kenglikdagi panellar.
- Planshet: ro‘yxatdan o‘tish tanlovlari va manzil maydonlari ikki ustun.
- Kompyuter: kabinet menyusi va so‘nggi faoliyat yonma-yon.

## Texnik o‘zgarish

- Yangi UI belgisi: `data-ui-release="v1647"`.
- Yangi scoped sinflar:
  - `koprik-flow-shell`
  - `koprik-auth-shell`
  - `koprik-location-shell`
  - `koprik-profile-surface`
  - `koprik-role-grid`
  - `koprik-staff-shell`
- Yangi kontrakt testi:
  `tests/test_auth_profile_design_v1647_contract.py`.

## BUILD

`v1647`


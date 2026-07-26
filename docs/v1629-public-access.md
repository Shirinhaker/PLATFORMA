# Ko‘prik v1629 — loyiha hamma uchun ochildi

## Talab

Vaqtinchalik yopiq rejim tugatilsin: loyiha barcha foydalanuvchilar uchun
ochiq bo‘lsin.

## O‘zgarishlar

- `access_config.py`: `PROJECT_ACCESS_RESTRICTED` standarti `True` dan
  `False` ga o‘tdi — endi hech qanday muhit o‘zgaruvchisisiz loyiha ochiq.
- `runtime_config.py`: production tekshiruvi ham ochiq standartga moslandi;
  `PRIVILEGED_TG_IDS` talabi faqat yopiq rejim yoqilganda amal qiladi.
- `/api/build` flaglari haqiqiy holatni ko‘rsatadi: `public_access: true`,
  `temporary_privileged_access_only: false`, yangi `public_launch_v1629`.
- Yopiq rejim mexanizmi kodda saqlanadi: zarur bo‘lsa Railway’da
  `PROJECT_ACCESS_RESTRICTED=1` berish bilan loyiha yana vaqtincha yopiladi —
  kod almashtirish shart emas. «Loyiha vaqtincha yopiq» ekrani ham shu holat
  uchun turadi.

## Diqqat (deploy)

Agar Railway muhitida `PROJECT_ACCESS_RESTRICTED` o‘zgaruvchisi ilgari `1`
qilib qo‘yilgan bo‘lsa, u kod standartidan ustun turadi — ochish uchun uni
o‘chirib tashlang yoki `0` qiling.

## Test

`tests/test_public_access_contract.py`: standart ochiqlik (manba va mantiq),
flaglar, hamda env orqali vaqtincha yopish hali ham ishlashi. Versiya
tekshiruvlari `v1629`.

# Koprik v1656 → Phase 3 parity xaritasi

## Holat lug‘ati

- `legacy`: faqat amaldagi v1656 production interfeysida ishlaydi.
- `in-progress`: React stagingga ko‘chirilmoqda, qabul qilinmagan.
- `staging-accepted`: stagingda avtomatik va qo‘lda qabul qilingan.
- `production-accepted`: production cutover’dan keyin kuzatuvdan o‘tgan.

## Kritik oqimlar

| Oqim | Boshlang‘ich holat | Phase 3 navbati |
| --- | --- | --- |
| Bosh sahifa → qidiruv → katalog → lokatsiya | legacy | Phase 3B |
| Kirish → Telegram kodi → sessiya | in-progress | Phase 3A |
| Oddiy kabinet → profil → avatar | in-progress | Phase 3A |
| Biznes kabinet → profil → logotip | in-progress | Phase 3A |
| E’lon → buyurtma → to‘lov | legacy | Phase 3C |
| Staff va admin oqimlari | legacy | Phase 3E |

## Qabul qoidasi

Ekran faqat avtomatik test, desktop/mobil qo‘lda tekshiruv va rollback
yo‘li tasdiqlangandan keyin `staging-accepted` holatiga o‘tadi.

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

## Phase 3B ekran egaligi

| Legacy ekran | Holat | React egasi |
| --- | --- | --- |
| `home` | in-progress | `frontend/src/legacy/public/HomeScreen.tsx` |
| `catalog` | in-progress | `frontend/src/legacy/public/CatalogScreen.tsx` |
| `cat-types` | in-progress | `frontend/src/legacy/public/CategoryScreen.tsx` |
| `loc` | in-progress | `frontend/src/legacy/public/LocationScreen.tsx` |

`home`ning v1656 manbalari, modul xaritasi, ichki tayyor qismi va hali
ko‘chirilmagan bog‘langan ekranlari
[`docs/public-home-v1656-parity.md`](../public-home-v1656-parity.md) da
alohida qayd etilgan.

## Qabul qoidasi

Ekran faqat avtomatik test, desktop/mobil qo‘lda tekshiruv va rollback
yo‘li tasdiqlangandan keyin `staging-accepted` holatiga o‘tadi.

Phase 3B avtomatik gate’i `python scripts/verify_phase3b.py` orqali,
qo‘lda qabul va rollback esa `docs/deploy-phase3b-staging.md` bo‘yicha
bajariladi. Qabul tugamaguncha Phase 3B qatorlari `in-progress` bo‘lib
qoladi; production `web` va `koprik.uz` o‘zgartirilmaydi.

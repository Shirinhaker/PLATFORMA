# Ko‘prik v1656 — desktop xarita, Taxi guard va to‘liq MVP source

> Tarixiy hujjat: bu yerda Taxi yopiq bo‘lgan dastlabki v1656 holati
> tasvirlangan. Joriy ochilgan holat `docs/v1656-unlocked-sections.md`da.

## Talab

1. Bosh sahifa xaritasidagi `+ / −` boshqaruvi kompyuterda ham chiqmasin.
2. MVPda Taxi chaqirish tugmasi bloklansin.
3. Loyihaning deploy qilinadigan to‘liq MVP kodi alohida topshirilsin.

## Qabul mezonlari

- `leafletMap` `zoomControl:false` bilan yaratiladi.
- Yuqori menyudagi Taxi va xaritadagi Taxi tugmasi yashirin.
- `taxi-call` yoki `taxidrv` ekranini kod orqali ochish urinishi bloklanadi.
- Buyurtma va yetkazib berish backend oqimlari o‘zgarmaydi.
- `/api/build` `v1656`, `taxi_call_enabled:false` va v1656 markerlarini
  qaytaradi.
- MVP ZIPda backend, frontend, admin, testlar, deploy fayllari va hujjatlar
  bor; sirlar, DB, uploadlar, virtual muhit va cache yo‘q.

## O‘zgargan asosiy fayllar

- `static/index.html`
- `main.py`
- `MVP_README.md`
- `tests/test_mvp_map_taxi_v1656_contract.py`
- build markeriga bog‘langan regressiya testlari

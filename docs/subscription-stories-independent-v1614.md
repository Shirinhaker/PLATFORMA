# Ko‘prik v1614 — istoriyalar obunalardan mustaqil

## Qaror

Istoriyalar Bepul, Plus yoki Pro tarifining imtiyozi hisoblanmaydi. Tarif
katalogi, API entitlement javobi va `Obunalarim` ekranida istoriyaga oid band
yo‘q.

## Nima o‘zgarmadi

- rasm va 1 daqiqagacha video istoriya joylash;
- istoriya ko‘rish va ko‘rilgan holatini saqlash;
- o‘z istoriyalarini boshqarish;
- amaldagi istoriya lentasi va tartiblash qoidalari;
- barcha mavjud istoriya endpointlari.

## Tariflarda qolgan farqlar

- Bepul: asosiy biznes profil va mahsulot/xizmatlarni cheksiz joylash;
- Plus: Bepul imkoniyatlari va bosh sahifadagi tuman takliflariga chiqish huquqi;
- Pro: Plus imkoniyatlari va biznes metkasini xaritada ko‘rsatish huquqi.

`subscriptions.py` faqat mahsulot/xizmat va ko‘rinish entitlementlarini qaytaradi.
Istoriya kodlari obuna holatini tekshirmaydi.

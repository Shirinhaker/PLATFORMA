# Ko‘prik — tumandagi Plus/Pro takliflari dizayni

## Maqsad

Bosh sahifada foydalanuvchining profilida saqlangan tumanga mos Plus va Pro
bizneslarning mahsulotlari, xizmatlari va ommaviy e’lonlarini ko‘rsatish.
Hozirgi bosqichda masofa va koordinatalar hisoblanmaydi. Bu yondashuv dastlabki
ishga tushirishda server yukini past saqlaydi; masofaga asoslangan tizim loyiha
rivojlangandan keyin alohida bosqichda qo‘shiladi.

## Joylashuvi va ko‘rinishi

- Kartochkalar bosh sahifada xaritadan keyin joylashadi.
- Bo‘limda nom, sarlavha yoki `Sizga yaqin` yozuvi bo‘lmaydi.
- Telegram Mini App bir so‘rovda ko‘pi bilan 6 ta kartochka oladi.
- Web-saytga o‘tilganda kartochkalar soni va joylashuvi alohida responsive
  dizayn bilan qayta belgilanadi; bu versiya web uchun sonni majburan belgilamaydi.
- Kartochkalar o‘ngdan chapga uzluksiz va sekin oqib turadi.
- Foydalanuvchi kartochkaga tegsa, fokus qilsa yoki sichqoncha bilan ustiga
  kelsa animatsiya vaqtincha to‘xtaydi.
- Qo‘lda gorizontal surish mumkin.
- Harakat kamaytirilishini so‘ragan qurilmalarda (`prefers-reduced-motion`)
  avtomatik oqish o‘chadi, qo‘lda surish saqlanadi.
- Faqat bitta kartochka bo‘lsa u harakatsiz turadi; ikki yoki undan ko‘p bo‘lsa
  uzluksiz karusel ishlaydi.

## Kartochka tarkibi

Har bir kartochkada quyidagilar ko‘rsatiladi:

- mahsulot, xizmat yoki e’lon rasmi;
- kontent nomi;
- biznes nomi;
- narxi mavjud bo‘lsa narxi;
- `Mahsulot`, `Xizmat` yoki `E’lon` belgisi.

Kontent rasmi bo‘lmasa biznes logotipi, logotip ham bo‘lmasa standart belgi
ko‘rsatiladi. Mahsulot yoki xizmat kartochkasi biznes sahifasini, e’lon
kartochkasi esa e’lon tafsilotini ochadi.

## Tuman qoidasi

- Foydalanuvchi tumani `users.district` maydonidan olinadi.
- Biznes tumani biznes egasining `users.district` maydonidan olinadi.
- Tuman nomi solishtirishdan oldin bosh-oxir bo‘shliqlari, harf registri va
  apostrofning odatiy variantlari bo‘yicha normallashtiriladi.
- Foydalanuvchida tuman belgilanmagan bo‘lsa taklif kartochkalari yuklanmaydi;
  ularning o‘rnida `Tumanni tanlang` tugmasi ko‘rsatiladi.
- Tugma amaldagi manzil/tuman tanlash ekranini ochadi.
- Bu bosqichda koordinata, radius yoki kilometr hisoblanmaydi.

## Obuna va biznes talablari

Kartochkaga faqat quyidagi biznes kiradi:

- biznes holati `active`;
- joriy obunasi Plus yoki Pro va muddati tugamagan;
- biznes tumani foydalanuvchi tumaniga teng;
- biznesda kamida bitta ko‘rsatish mumkin bo‘lgan kontent bor.

Plus va Pro teng navbatga ega. Pro uchun bu bo‘limda qo‘shimcha ustunlik yoki
ko‘proq slot berilmaydi. Obuna muddati tugagan biznes navbatdan avtomatik
chiqadi.

## Kontent talablari

- Har bir tanlangan biznesdan bir vaqtda faqat bitta kontent qaytariladi.
- Mahsulot va xizmatlar `items` jadvalidan olinadi va biznesning ommaviy
  sahifasida qo‘llanadigan amaldagi ko‘rinish qoidalariga rioya qiladi.
- E’lon faqat `status='active'` va `visibility='all'` bo‘lsa olinadi.
- Kontent turi mahsulot → xizmat → e’lon tartibida vaqt bo‘yicha navbatlanadi;
  biznesda bir tur bo‘lmasa keyingi mavjud tur olinadi.
- Bitta tur ichida o‘sha biznesning kontentlari ham navbat bilan almashadi.
- Kontenti qolmagan yoki mos kontenti yo‘q biznes o‘tkazib yuboriladi.

## Adolatli navbat algoritmi

- Vaqt 30 daqiqalik bo‘laklarga ajratiladi.
- Tuman va vaqt bo‘lagi asosida barqaror boshlanish nuqtasi hisoblanadi.
- Mos bizneslar barqaror tartibda joylashtirilib, boshlanish nuqtasidan boshlab
  eng ko‘pi bilan 6 ta noyob biznes olinadi.
- Keyingi 30 daqiqalik bo‘lakda boshlanish nuqtasi siljiydi va navbatdagi
  bizneslar chiqadi.
- Natijada har bir vaqt bo‘lagida bitta biznesdan ko‘pi bilan bitta kartochka
  bo‘ladi.
- Algoritm navbatni yuritish uchun har bir sahifa ochilishida bazaga yozuv
  kiritmaydi.
- Tumanda 6 tadan kam mos biznes bo‘lsa mavjudlari qaytariladi.

## API

Yangi yengil endpoint qo‘shiladi:

`GET /api/home/district-offers`

Javob holatlari:

- tuman yo‘q: `needs_district=true`, `items=[]`;
- mos taklif yo‘q: `needs_district=false`, `items=[]`;
- mos taklif bor: ko‘pi bilan 6 ta kartochka va joriy 30 daqiqalik vaqt
  bo‘lagining identifikatori.

Endpoint foydalanuvchi tumanini, ismini yoki shaxsiy ma’lumotlarini bizneslarga
yubormaydi. Tuman faqat server ichida filtrlash uchun ishlatiladi. Bu cheklov
platformaning boshqa ommaviy profil ekranlarida tuman ko‘rsatilishi haqidagi
amaldagi qoidalarni o‘zgartirmaydi.

## Frontend ishlashi

- Bosh sahifa ochilganda endpoint bir marta chaqiriladi.
- Bir xil 30 daqiqalik davr ichida qayta render qilish qo‘shimcha so‘rov
  yubormasligi uchun natija frontend xotirasida saqlanadi.
- Foydalanuvchi tizimga kirsa, chiqsa yoki tumanini o‘zgartirsa ushbu xotira
  darhol tozalanadi va yangi tuman bo‘yicha qayta so‘rov yuboriladi.
- Kartochkalar mavjud bo‘lsa sarlavhasiz rail render qilinadi.
- Uzluksiz animatsiya uchun ko‘rinadigan kartochkalar frontendda takrorlanadi;
  bu serverdan takroriy ma’lumot yuklamaydi.
- Touch, pointer, hover va keyboard fokusda animatsiya pauza qilinadi.
- Kartochka bosilganda mavjud navigatsiya funksiyalari orqali tegishli sahifa
  ochiladi.
- API xatosida bosh sahifaning qolgan qismlari ishlashda davom etadi; takliflar
  joyi jim yashiriladi va qayta kirishda yana uriniladi.

## Maxfiylik

Foydalanuvchining tumani mos bizneslarni tanlash uchun faqat server ichida
ishlatiladi. Biznes egasiga kim ko‘rgani, foydalanuvchi tumani yoki shaxsi
berilmaydi. Bu versiya ko‘rishlar bo‘yicha yangi shaxsiy kuzatuv yozuvini
yaratmaydi.

## Sinovlar

Avtomatik testlar quyidagilarni tekshiradi:

- tumansiz foydalanuvchi uchun `needs_district` javobi;
- boshqa tumandagi biznes chiqmasligi;
- Free va muddati tugagan obunalar chiqmasligi;
- Plus va Pro teng huquqda qatnashishi;
- faqat faol bizneslar va ommaviy kontent olinishi;
- bir biznesdan ko‘pi bilan bitta kartochka;
- bir javobda ko‘pi bilan 6 ta noyob biznes;
- bir 30 daqiqalik davrda barqaror, keyingi davrda siljigan navbat;
- mahsulot, xizmat va e’lon kontentining navbatlanishi;
- frontendda joylashuv, sarlavhasiz rail, pauza va kamaytirilgan harakat
  shartnomalari;
- mavjud testlarning regressiyasiz o‘tishi.

## Ushbu bosqichga kirmaydi

- kilometr yoki radius bo‘yicha saralash;
- GPS/koordinata hisoblash;
- Pro’ga ushbu rail ichida alohida ustunlik berish;
- haqiqiy to‘lov tizimi;
- web-sayt uchun yakuniy kartochkalar soni va grid dizayni;
- ko‘rishlar analitikasi yoki foydalanuvchi shaxsini biznesga berish.

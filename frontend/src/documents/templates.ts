import type {
  DocumentCounterparty,
  DocumentDirection,
} from "../api/types";


export const DOCUMENT_TYPES: Record<DocumentDirection, string[]> = {
  ichki: ["Buyruq", "Ariza", "Dalolatnoma", "Bayonnoma", "Tilxat", "Xabarnoma"],
  chiquvchi: [
    "Shartnoma",
    "Hisob-faktura",
    "Yuk xati",
    "Ishonchnoma",
    "Akt",
    "Solishtirma dalolatnoma",
    "Bayonnoma",
    "Erkin shakldagi hujjat",
  ],
  kiruvchi: ["Erkin shakldagi hujjat"],
};

export type DocumentTemplateContext = {
  firm: string;
  director: string;
  date: string;
  number: string;
  title: string;
  taxId: string;
  counterparty?: DocumentCounterparty;
};

function value(value: string, fallback: string) {
  return value.trim() || fallback;
}

export function generateDocumentTemplate(
  type: string,
  context: DocumentTemplateContext,
): string {
  const c = {
    firma: value(context.firm, "[Firma nomi]"),
    rahbar: value(context.director, "[Rahbar F.I.Sh.]"),
    sana: context.date || "____-__-__",
    raqam: value(context.number, "___"),
    title: context.title.trim(),
    contr: context.counterparty?.name ?? "",
    firmaInn: value(context.taxId, "[_______]"),
    contrInn: value(context.counterparty?.inn ?? "", "[_______]"),
    contrAcc: value(context.counterparty?.account ?? "", "[_______]"),
    contrBank: value(context.counterparty?.bank ?? "", "[_______]"),
    contrMfo: value(context.counterparty?.mfo ?? "", "[____]"),
  };

  const templates: Record<string, () => string> = {
    Buyruq: () => (
      `${c.firma}\n\nBUYRUQ\n№ ${c.raqam}                                   ${c.sana}\n`
      + (c.title ? `\n${c.title.toUpperCase()}\n` : "\n[Buyruq sarlavhasi]\n")
      + "\nBUYURAMAN:\n\n1. ________________________________________________\n2. ________________________________________________\n3. ________________________________________________\n\n"
      + "Asos: [asos hujjat / ariza / bayonnoma]\n\n"
      + "Buyruq ijrosini nazorat qilishni o'z zimmamga qoldiraman.\n\n\n"
      + `Rahbar: _______________________  ${c.rahbar}\n\n`
      + "M.O'.  (muhr o'rni)\n\n"
      + "Buyruq bilan tanishdim: _______________________ ( _______________ )\n"
    ),
    Ariza: () => (
      `                                        ${c.firma} rahbari\n`
      + `                                        ${c.rahbar} ga\n\n`
      + "                                        [Ariza beruvchi F.I.Sh.]\n"
      + "                                        [lavozimi]\n"
      + "                                        tel: [telefon]\n\n"
      + "                       A R I Z A\n\n"
      + "Men, [F.I.Sh.], sizdan ________________________________________\n"
      + "________________________________________________________________\n"
      + "________________________________________________ so'rayman.\n\n"
      + "Sabab: ________________________________________________________\n\n"
      + `Sana: ${c.sana}                          Imzo: _______________\n`
    ),
    Dalolatnoma: () => (
      `${c.firma}\n\nDALOLATNOMA\n№ ${c.raqam}                                   ${c.sana}\n`
      + "                                        [tuzilgan joy]\n\n"
      + (c.title ? `${c.title}\n\n` : "[Dalolatnoma mavzusi]\n\n")
      + "Biz, quyida imzo chekuvchilar:\n"
      + "1. [F.I.Sh., lavozim]\n"
      + "2. [F.I.Sh., lavozim]\n"
      + "3. [F.I.Sh., lavozim]\n\n"
      + "ushbu dalolatnomani quyidagilar to'g'risida tuzdik:\n\n"
      + "________________________________________________________________\n"
      + "________________________________________________________________\n"
      + "________________________________________________________________\n\n"
      + "Mazkur dalolatnoma 3 (uch) nusxada tuzildi.\n\n"
      + "Imzolar:\n1. _______________\n2. _______________\n3. _______________\n"
    ),
    Bayonnoma: () => (
      `${c.firma}\n\nBAYONNOMA\n№ ${c.raqam}                                   ${c.sana}\n\n`
      + (c.title ? `${c.title}\n\n` : "[Yig'ilish / majlis nomi]\n\n")
      + "Rais: [F.I.Sh.]\nKotib: [F.I.Sh.]\nIshtirok etdilar: [ro'yxat / soni]\n\n"
      + "KUN TARTIBI:\n1. ________________________________________________\n2. ________________________________________________\n\n"
      + "ESHITILDI: ____________________________________________________\n\n"
      + "QAROR QILINDI:\n1. ________________________________________________\n2. ________________________________________________\n\n"
      + "Rais: _______________  ( _______________ )\nKotib: _______________  ( _______________ )\n"
    ),
    Tilxat: () => (
      "                       T I L X A T\n\n"
      + `Sana: ${c.sana}                          Joy: [shahar/tuman]\n\n`
      + "Men, [F.I.Sh.], [pasport seriya/raqam], [manzil], \n"
      + `${c.firma} dan / [kimdan] quyidagilarni oldim:\n\n`
      + "________________________________________________________________\n"
      + "Miqdori / summasi: [______________] (_____________________ so'm)\n\n"
      + "Yuqoridagilarni to'liq va tegishli holatda olganimni tasdiqlayman.\n"
      + "Majburiyat: [qaytarish muddati / shartlari, agar bo'lsa]\n\n"
      + "Imzo: _______________  ( [F.I.Sh.] )\n"
    ),
    Xabarnoma: () => (
      `${c.firma}\n№ ${c.raqam}                                   ${c.sana}\n\n`
      + "                                        [Kimga: F.I.Sh. / tashkilot]\n\n"
      + "                       XABARNOMA\n\n"
      + (c.title ? `${c.title}\n\n` : "")
      + "Sizga ma'lum qilamizki, ______________________________________\n"
      + "________________________________________________________________\n"
      + "________________________________________________________________\n\n"
      + "Iltimos, mazkur xabarnomani inobatga olishingizni so'raymiz.\n\n"
      + `Hurmat bilan,\n${c.rahbar}\nRahbar: _______________   M.O'.\n`
    ),
    Shartnoma: () => (
      `                       SHARTNOMA № ${c.raqam}\n\n`
      + `[shahar/tuman]                                   ${c.sana}\n\n`
      + `${c.firma}, keyingi o'rinlarda "Yetkazib beruvchi" (rahbar ${c.rahbar}) bir tomondan, va \n`
      + `${c.contr || "[Kontragent nomi]"}, keyingi o'rinlarda "Buyurtmachi" ikkinchi tomondan, \n`
      + "ushbu shartnomani quyidagilar to'g'risida tuzdilar:\n\n"
      + "1. SHARTNOMA PREDMETI\n1.1. ____________________________________________________\n\n"
      + "2. SHARTNOMA SUMMASI VA TO'LOV TARTIBI\n2.1. Summa: [__________] (___________________) so'm.\n2.2. To'lov: ______________________________________\n\n"
      + "3. TOMONLARNING MAJBURIYATLARI\n3.1. ____________________________________________________\n\n"
      + "4. TOMONLAR JAVOBGARLIGI\n4.1. ____________________________________________________\n\n"
      + "5. NIZOLARNI HAL QILISH\n5.1. Nizolar muzokara yo'li bilan, kelishilmasa qonun bo'yicha hal etiladi.\n\n"
      + `6. SHARTNOMA MUDDATI\n6.1. Amal qilish muddati: ${c.sana} dan [_________] gacha.\n\n`
      + "7. TOMONLARNING REKVIZITLARI VA IMZOLARI\n\n"
      + "Yetkazib beruvchi:                        Buyurtmachi:\n"
      + `${c.firma}                                  ${c.contr || "[nomi]"}\n`
      + `STIR: ${c.firmaInn}                      STIR: ${c.contrInn}\n`
      + `h/r: [_______]                            h/r: ${c.contrAcc}\n`
      + `Bank: [_______], MFO: [____]              Bank: ${c.contrBank}, MFO: ${c.contrMfo}\n\n`
      + `_______________ ${c.rahbar}              _______________ [F.I.Sh.]\n`
      + "M.O'.                                     M.O'.\n"
    ),
    "Hisob-faktura": () => (
      `HISOB-FAKTURA № ${c.raqam}   sana: ${c.sana}\n`
      + "(Shartnoma: № ______ , sana ________ )\n\n"
      + `Yetkazib beruvchi: ${c.firma}\n  STIR: ${c.firmaInn}   h/r: [_______]   Bank: [_______], MFO: [____]\n\n`
      + `Xaridor: ${c.contr || "[Kontragent nomi]"}\n  STIR: ${c.contrInn}   h/r: ${c.contrAcc}   Bank: ${c.contrBank}, MFO: ${c.contrMfo}\n\n`
      + "№ | Tovar/xizmat nomi          | O'lchov | Soni | Narxi     | Summasi\n"
      + "--+----------------------------+---------+------+-----------+-----------\n"
      + "1 | __________________________ | ______  | ____ | _________ | _________\n"
      + "2 | __________________________ | ______  | ____ | _________ | _________\n"
      + "3 | __________________________ | ______  | ____ | _________ | _________\n"
      + "--+----------------------------+---------+------+-----------+-----------\n"
      + "                                              Jami:      | _________\n"
      + "                                              QQS (12%): | _________\n"
      + "                                     Umumiy summa:       | _________\n\n"
      + `Rahbar: _______________ ${c.rahbar}\nBosh hisobchi: _______________\nM.O'.\n`
    ),
    "Yuk xati": () => (
      `YUK XATI (nakladnoy) № ${c.raqam}        sana: ${c.sana}\n\n`
      + `Jo'natuvchi: ${c.firma}\nQabul qiluvchi: ${c.contr || "[Kontragent nomi]"}\n\n`
      + "№ | Tovar nomi                 | O'lchov | Soni | Narxi   | Summasi\n"
      + "--+----------------------------+---------+------+---------+---------\n"
      + "1 | __________________________ | ______  | ____ | _______ | _______\n"
      + "2 | __________________________ | ______  | ____ | _______ | _______\n"
      + "--+----------------------------+---------+------+---------+---------\n"
      + "                                    Jami summa:        | _______\n\n"
      + "Topshirdi: _______________ ( _______________ )\n"
      + "Qabul qildi: _______________ ( _______________ )\n"
      + "M.O'.\n"
    ),
    Ishonchnoma: () => (
      "                       ISHONCHNOMA\n\n"
      + `[shahar/tuman]                                   ${c.sana}\n\n`
      + `${c.firma} (STIR: ${c.firmaInn}) nomidan rahbar ${c.rahbar} \n`
      + "ushbu ishonchnoma bilan [F.I.Sh.] (pasport: [seriya/raqam]) ga \n"
      + "quyidagi vakolatlarni ishonib topshiradi:\n\n"
      + "________________________________________________________________\n"
      + "________________________________________________________________\n\n"
      + "Mazkur ishonchnoma [_________] gacha amal qiladi.\n"
      + "Imzo namunasi ishonchnoma egasi: _______________ tasdiqlanadi.\n\n"
      + `Rahbar: _______________ ${c.rahbar}\nM.O'.\n`
    ),
    Akt: () => (
      `BAJARILGAN ISHLAR (XIZMATLAR) AKTI № ${c.raqam}\n`
      + `sana: ${c.sana}    (Shartnoma № ______ , ________ )\n\n`
      + `Ijrochi: ${c.firma}\nBuyurtmachi: ${c.contr || "[Kontragent nomi]"}\n\n`
      + "Quyidagi ishlar (xizmatlar) bajarilganligi to'g'risida akt tuzildi:\n\n"
      + "№ | Ish/xizmat nomi            | Soni | Summasi\n"
      + "--+----------------------------+------+---------\n"
      + "1 | __________________________ | ____ | _______\n"
      + "2 | __________________________ | ____ | _______\n"
      + "--+----------------------------+------+---------\n"
      + "                       Jami:          | _______\n\n"
      + "Tomonlar bir-biriga da'vosi yo'q.\n\n"
      + `Topshirdi (Ijrochi): _______________ ${c.rahbar}\n`
      + "Qabul qildi (Buyurtmachi): _______________\nM.O'.\n"
    ),
    "Solishtirma dalolatnoma": () => (
      "O'ZARO HISOB-KITOB SOLISHTIRMA DALOLATNOMASI\n"
      + `sana: ${c.sana}   davr: [__.__.____ dan __.__.____ gacha]\n\n`
      + `${c.firma} va ${c.contr || "[Kontragent nomi]"} o'rtasidagi \n`
      + "o'zaro hisob-kitoblar quyidagicha solishtirildi:\n\n"
      + `Ko'rsatkich                         | ${c.firma} | Kontragent\n`
      + "------------------------------------+-----------+-----------\n"
      + "Davr boshiga qoldiq                 | _________ | _________\n"
      + "Davrda hisoblangan (debet)          | _________ | _________\n"
      + "Davrda to'langan (kredit)           | _________ | _________\n"
      + "Davr oxiriga qoldiq                 | _________ | _________\n\n"
      + "Kelishilgan yakuniy qoldiq: [_______________] (___________________) so'm.\n\n"
      + `${c.firma}:                              Kontragent:\n`
      + `_______________ ${c.rahbar}           _______________ [F.I.Sh.]\n`
      + "M.O'.                                  M.O'.\n"
    ),
    "Erkin shakldagi hujjat": () => (
      `${c.firma}\n№ ${c.raqam}                                   ${c.sana}\n\n`
      + (c.title ? `${c.title}\n\n` : "")
      + "________________________________________________________________\n"
      + "________________________________________________________________\n"
      + "________________________________________________________________\n"
      + "________________________________________________________________\n\n"
      + `Hurmat bilan,\n${c.rahbar}\n_______________   M.O'.\n`
    ),
  };

  const template = templates[type] ?? templates["Erkin shakldagi hujjat"];
  return template ? template() : "";
}

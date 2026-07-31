export type Metric = {
  label: string;
  key: string;
  sub: string;
  view: string;
  money?: boolean;
};

export type PayloadSource = string | readonly string[];

export type Menu = {
  icon: string;
  label: string;
  caption: string;
  view: string;
  payload?: PayloadSource;
  directions?: readonly string[];
};

export type BusinessDirection = {
  name: string;
  icon: string;
  activities: readonly string[];
};

export const BUSINESS_DIRECTIONS: readonly BusinessDirection[] = [
  {
    name: "Savdo",
    icon: "🛒",
    activities: [
      "Oziq-ovqat do'koni", "Kiyim-kechak", "Poyabzal", "Elektronika",
      "Maishiy texnika", "Telefon va aksessuar", "Qurilish mollari",
      "Mebel do'koni", "Uy jihozlari", "Dorixona", "Optika",
      "Parfyumeriya va kosmetika", "Zargarlik", "Bolalar mollari",
      "Kanselyariya", "Gullar do'koni", "Sport mollari", "Kitob do'koni",
      "Avtoehtiyot qismlar", "Bozor rastasi",
    ],
  },
  {
    name: "Transport va logistika",
    icon: "🚕",
    activities: [
      "Taxi", "Yo'lovchi tashish", "Yuk tashish", "Yetkazib berish",
      "Kuryer xizmati", "Evakuator", "Avto ijara", "Ombor xizmati",
      "Konteyner tashish", "Refrijerator tashish",
    ],
  },
  {
    name: "Xizmat ko'rsatish",
    icon: "🧰",
    activities: [
      "Kunlik ishchi", "Uy tozalash", "Santexnik", "Elektrik",
      "Konditsioner ta'miri", "Muzlatgich ta'miri",
      "Kir yuvish mashinasi ta'miri", "Kompyuter ta'miri",
      "Telefon ta'miri", "Payvandchi", "Bo'yoqchi", "Mebel yig'uvchi",
      "Eshik-deraza ustasi", "Uy ko'chirish", "Bog'bon",
    ],
  },
  {
    name: "Maishiy xizmatlar",
    icon: "💇",
    activities: [
      "Sartaroshxona", "Go'zallik saloni", "Manikur-pedikur", "Kosmetolog",
      "Massaj", "Qosh-kiprik", "Makiyaj ustasi", "Tikuvchilik",
      "Poyabzal ta'miri", "Kimyoviy tozalash", "Solaryum", "Hammom va sauna",
    ],
  },
  {
    name: "Umumiy ovqatlanish",
    icon: "🍽️",
    activities: [
      "Kafe", "Restoran", "Fast-food", "Milliy taomlar", "Choyxona",
      "Pitseriya", "Sushi bar", "Kofeynya", "Nonvoyxona", "Qandolatxona",
      "Oshxona", "Yetkazib beruvchi oshxona",
    ],
  },
  {
    name: "Qurilish",
    icon: "🏗️",
    activities: [
      "Quruvchi brigada", "Ta'mirlash (remont)", "Montaj ishlari",
      "Loyihalash", "Tom yopish", "Beton quyish", "Gips-karton",
      "Kafel-plitka", "Elektromontaj", "Santexmontaj", "Fasad ishlari",
      "Landshaft dizayni", "Quduq qazish",
    ],
  },
  {
    name: "Tibbiy xizmatlar",
    icon: "🩺",
    activities: [
      "Klinika", "Stomatologiya", "Laboratoriya", "Shifokor konsultatsiyasi",
      "Hamshira xizmati", "Ginekologiya", "Pediatriya", "UZI diagnostika",
      "Fizioterapiya", "Oftalmologiya", "Massaj kabineti", "Veterinariya",
    ],
  },
  {
    name: "Ta'lim faoliyati",
    icon: "📚",
    activities: [
      "O'quv markazi", "Repetitor", "Til kurslari", "IT kurslari",
      "Avtomaktab", "Musiqa maktabi", "Sport maktabi", "Rassomlik",
      "Xoreografiya", "Bog'cha", "Onlayn kurslar", "Imtihonga tayyorlash",
    ],
  },
  {
    name: "Ko'chmas mulk",
    icon: "🏢",
    activities: [
      "Rieltor", "Kvartira sotish", "Uy sotish", "Yer uchastkasi",
      "Ijaraga berish", "Tijorat ko'chmas mulki", "Bino boshqaruvi",
      "Baholash xizmati",
    ],
  },
  {
    name: "Qishloq xo'jaligi",
    icon: "🌾",
    activities: [
      "Dehqonchilik", "Chorvachilik", "Parrandachilik", "Asalarichilik",
      "Bog'dorchilik", "Issiqxona", "Baliqchilik", "Urug' va ko'chat",
      "Em-xashak", "Sut mahsulotlari",
    ],
  },
  {
    name: "Axborot texnologiyalari",
    icon: "💻",
    activities: [
      "Dasturlash", "Veb-sayt yaratish", "Mobil ilova", "Grafik dizayn",
      "SMM", "1C dasturlash", "Kompyuter tarmoqlari", "Kiberxavfsizlik",
      "Video montaj", "IT xizmat",
    ],
  },
  {
    name: "Konsalting va professional",
    icon: "⚖️",
    activities: [
      "Advokat", "Yuridik maslahat", "Buxgalteriya", "Soliq maslahati",
      "Audit", "Notarius", "Tarjimon", "Biznes-reja", "HR xizmati",
      "Litsenziya olish",
    ],
  },
  {
    name: "Madaniyat, sport, ko'ngilochar",
    icon: "🏟️",
    activities: [
      "Sport zali", "Fitnes klub", "Suzish havzasi", "Bilyard", "Bouling",
      "Kvest xona", "Foto-video", "To'yxona", "Tadbir tashkil etish",
      "DJ xizmati", "Tamada", "Sharlar bilan bezash",
    ],
  },
  {
    name: "Turizm va mehmonxona",
    icon: "🏨",
    activities: [
      "Mehmonxona", "Hostel", "Kvartira sutkalik", "Dam olish maskani",
      "Sanatoriy", "Turagentlik", "Ekskursiya", "Aviachipta", "Viza xizmati",
    ],
  },
  {
    name: "Ishlab chiqarish",
    icon: "🏭",
    activities: [
      "Oziq-ovqat ishlab chiqarish", "Mebel", "Tikuv sexi",
      "Metall konstruksiyalar", "Plastik buyumlar", "Qurilish materiallari",
      "Ichimliklar", "Qadoqlash", "Oyna-deraza",
    ],
  },
  {
    name: "Hunarmandchilik",
    icon: "🧵",
    activities: [
      "Yog'och buyumlar", "Charm buyumlar", "Kulolchilik", "Kashtachilik",
      "Zardo'zlik", "Gilamdo'zlik", "Milliy liboslar", "Suvenir",
      "Qo'lda yasalgan buyumlar",
    ],
  },
  {
    name: "Reklama va marketing",
    icon: "📣",
    activities: [
      "SMM", "Targetolog", "Kontekst reklama", "Banner va dizayn",
      "Kontent yaratish", "Blogger reklama", "Reklama agentligi",
    ],
  },
  {
    name: "Poligrafiya va nashriyot",
    icon: "🖨️",
    activities: [
      "Chop etish", "Vizitka va buklet", "Banner bosish", "Muhr-tamg'a",
      "Stiker", "Futbolkaga bosish", "Lazer o'yish", "Kitob nashri",
      "Kalendar",
    ],
  },
  {
    name: "Moliyaviy faoliyat",
    icon: "💳",
    activities: [
      "Sug'urta", "Mikroqarz", "Pul o'tkazmalari", "Valyuta ayirboshlash",
      "Lizing", "Kredit maslahati", "Investitsiya maslahati",
    ],
  },
  {
    name: "Import-eksport",
    icon: "🚢",
    activities: [
      "Import", "Eksport", "Bojxona vositachiligi", "Xalqaro logistika",
      "Sertifikatlash", "Tashqi savdo maslahati",
    ],
  },
] as const;

export const DEFAULT_METRICS: Metric[] = [
  { label: "Bugungi tushum", key: "revenue", sub: "Bugungi savdo tushumi", view: "sales", money: true },
  { label: "Yangi buyurtmalar", key: "new_orders", sub: "Qabul qilinmagan buyurtmalar", view: "orders" },
  { label: "Faol buyurtmalar", key: "active_orders", sub: "Jarayondagi buyurtmalar", view: "orders" },
  { label: "Bildirishnomalar", key: "problem_orders", sub: "E’tibor talab holatlar", view: "notifications" },
];

export const METRICS: Record<string, Metric[]> = {
  Savdo: [
    { label: "Bugungi savdo", key: "revenue", sub: "Bugungi tushum", view: "sales", money: true },
    { label: "Yangi buyurtma", key: "new_orders", sub: "Qabul qilinmagan buyurtmalar", view: "orders" },
    { label: "Umumiy qarz", key: "debt_total", sub: "Qarz daftaridagi qoldiq", view: "debtors", money: true },
    { label: "Ombor ogohlantirishi", key: "low_stock", sub: "Kam qolgan mahsulotlar", view: "warehouse" },
  ],
  "Umumiy ovqatlanish": [
    { label: "Bugungi savdo", key: "sales_count", sub: "Bugungi savdolar soni", view: "sales" },
    { label: "Ochiq buyurtmalar", key: "active_orders", sub: "Jarayondagi buyurtmalar", view: "orders" },
    { label: "Band stol/xona", key: "occupied_places", sub: "Faol band joylar", view: "dining-places" },
    { label: "Ombor ogohlantirishi", key: "low_stock", sub: "Kam qolgan masalliqlar", view: "warehouse" },
  ],
  "Ta'lim faoliyati": [
    { label: "Bugungi darslar", key: "today_lessons", sub: "Bugungi jadval", view: "education-groups" },
    { label: "Guruhlar", key: "groups", sub: "Faol guruhlar", view: "education-groups" },
    { label: "O‘quvchilar", key: "students", sub: "Faol o‘quvchilar", view: "education-students" },
    { label: "Muddati o‘tgan to‘lov", key: "debt_total", sub: "To‘lov nazoratidagi qarz", view: "debtors", money: true },
  ],
  "Tibbiy xizmatlar": [
    { label: "Bugungi qabullar", key: "service_today", sub: "Bugungi yozilishlar", view: "service-orders" },
    { label: "Navbat", key: "service_active", sub: "Kutayotgan va qabuldagi", view: "medical-queues" },
    { label: "Yangi yozilishlar", key: "new_orders", sub: "Yangi qabul so‘rovlari", view: "service-orders" },
    { label: "Bugungi to‘lovlar", key: "revenue", sub: "Bugungi tushum", view: "sales", money: true },
  ],
};

export const ONLINE_MENUS: Menu[] = [
  { icon: "🏪", label: "Profil / Mening sahifam", caption: "Mijozlar ko‘radigan ma’lumotlar", view: "profile" },
  { icon: "💎", label: "Obunalarim", caption: "Bepul, Plus va Pro tariflari", view: "subscriptions", payload: "business_subscriptions" },
  { icon: "💳", label: "To‘lovlarim", caption: "Yuborilgan to‘lovlar va tarix", view: "payments", payload: "subscription_payments" },
  { icon: "🛍️", label: "Mahsulot va xizmatlar", caption: "Guruhlar va katalog yozuvlari", view: "items", payload: ["item_groups", "items"] },
  { icon: "🍽️", label: "Stollar va xonalar", caption: "Zal rejasini joylashtirish", view: "dining-places", payload: "dining_places", directions: ["Umumiy ovqatlanish"] },
  { icon: "📢", label: "E’lonlarim", caption: "Biznes nomidan joylangan e’lonlar", view: "listings", payload: "listings" },
  { icon: "📦", label: "Buyurtmalar", caption: "Mahsulot buyurtmalari", view: "orders", payload: "orders" },
  { icon: "🧰", label: "Xizmat buyurtmalari", caption: "Xizmat va navbatlar", view: "service-orders", payload: "orders" },
  { icon: "💬", label: "Suhbatlar", caption: "Mijozlar bilan xabarlar", view: "messages", payload: "messages" },
  { icon: "⭐", label: "Mijoz fikrlari", caption: "Baholar va javoblar", view: "reviews", payload: "business_reviews" },
  { icon: "📣", label: "Reklamalarim", caption: "Banner va ko‘rsatish tarixi", view: "advertisements", payload: "advertisements" },
  { icon: "🎞️", label: "Istoriya arxivi", caption: "Faol va arxivdagi istoriyalar", view: "stories", payload: "stories" },
  { icon: "🔔", label: "Bildirishnomalarim", caption: "Biznes xabarlari", view: "notifications", payload: "notifications" },
  { icon: "👥", label: "Obunachilar", caption: "Biznesni kuzatayotgan profillar", view: "followers", payload: "followers" },
  { icon: "🔗", label: "Biznes obunalari", caption: "Biznes nomidan kuzatilayotgan profillar", view: "following", payload: "following" },
];

export const SYSTEM_MENUS: Menu[] = [
  { icon: "🧾", label: "Kassa", caption: "Savdo daftari va kassa harakatlari", view: "sales", payload: ["sales", "cash_transactions", "cash_register_transactions"] },
  { icon: "💸", label: "Xarajatlar", caption: "Kunlik xarajatlar hisobi", view: "expenses", payload: "expenses" },
  { icon: "📒", label: "Qarz daftari", caption: "Mijozlar qarzi va tranzaksiyalar", view: "debtors", payload: ["debtors", "qarz_transactions"] },
  { icon: "📦", label: "Ombor", caption: "Qoldiq va kirim-chiqim", view: "warehouse", payload: ["warehouse_items", "warehouse_tx"] },
  { icon: "📊", label: "Statistika", caption: "Tushum, xarajat va faoliyat", view: "statistics" },
  { icon: "📄", label: "Hisobotlar", caption: "Ko‘chirilgan davriy ko‘rsatkichlar", view: "reports" },
];

export const ADMIN_MENUS: Menu[] = [
  { icon: "👨‍💼", label: "Xodimlar", caption: "Xodim va kirish ma’lumotlari", view: "staff", payload: ["staff", "business_staff", "employees"] },
  { icon: "🗃️", label: "Mening hujjatlarim", caption: "Biznesga tegishli hujjatlar", view: "documents", payload: ["documents", "business_documents"] },
  { icon: "📥", label: "Kiruvchi hujjatlar", caption: "Qabul qilingan hujjatlar", view: "incoming-documents", payload: "incoming_documents" },
  { icon: "📤", label: "Chiquvchi hujjatlar", caption: "Yuborilgan hujjatlar", view: "outgoing-documents", payload: "outgoing_documents" },
  { icon: "📝", label: "Ichki hujjatlar", caption: "Ichki buyruq va yozuvlar", view: "internal-documents", payload: "internal_documents" },
  { icon: "🤝", label: "Kontragentlar", caption: "Hamkor va ta’minotchilar", view: "counterparties", payload: "counterparties" },
];

export const DIRECTION_MENUS: Menu[] = [
  { icon: "👨‍🏫", label: "Ta’lim guruhlari", caption: "Guruh va dars ma’lumotlari", view: "education-groups", payload: "education_groups", directions: ["Ta'lim faoliyati", "Ta’lim faoliyati"] },
  { icon: "🎓", label: "O‘quvchilar", caption: "O‘quvchi va to‘lov holatlari", view: "education-students", payload: "education_students", directions: ["Ta'lim faoliyati", "Ta’lim faoliyati"] },
  { icon: "🧑‍🏫", label: "O‘qituvchilar", caption: "O‘qituvchi ma’lumotlari", view: "education-teachers", payload: "education_teachers", directions: ["Ta'lim faoliyati", "Ta’lim faoliyati"] },
  { icon: "🏥", label: "Tibbiy navbat", caption: "Kutayotgan va qabuldagi bemorlar", view: "medical-queues", payload: "medical_queues", directions: ["Tibbiy xizmatlar"] },
  { icon: "🩺", label: "Tibbiy qabullar", caption: "Yozilish va qabul ma’lumotlari", view: "medical-appointments", payload: "medical_appointments", directions: ["Tibbiy xizmatlar"] },
];

export const TERMINAL_STATUSES = new Set([
  "done", "delivered", "cancelled", "canceled", "rejected",
  "pickup_waiting_customer",
]);

export function directionActivities(direction: string, current = ""): string[] {
  const found = BUSINESS_DIRECTIONS.find((item) => item.name === direction);
  const activities = found ? [...found.activities] : [];
  if (current && !activities.includes(current)) activities.unshift(current);
  return activities;
}

export function money(value: number) {
  return `${Number(value || 0).toLocaleString("uz-UZ")} so‘m`;
}

export function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.length
    ? words.slice(0, 2).map((word) => word[0]?.toUpperCase()).join("")
    : "B";
}

export function activityDate(value: number) {
  return value
    ? new Date(value * 1000).toLocaleString("uz-UZ")
    : "Vaqt ko‘rsatilmagan";
}

export function isService(row: unknown) {
  if (!row || typeof row !== "object") return false;
  const data = row as Record<string, unknown>;
  return ["booking", "service", "queue", "medical"].includes(
    String(data.order_type ?? data.kind ?? data.order_category ?? ""),
  );
}

export function payloadRows(
  payload: Record<string, unknown>,
  source: PayloadSource,
): unknown[] {
  const keys = typeof source === "string" ? [source] : source;
  return keys.flatMap((key) => {
    const value = payload[key];
    return Array.isArray(value) ? value : [];
  });
}

export function hasPayload(
  payload: Record<string, unknown>,
  source?: PayloadSource,
): boolean {
  return Boolean(source && payloadRows(payload, source).length);
}

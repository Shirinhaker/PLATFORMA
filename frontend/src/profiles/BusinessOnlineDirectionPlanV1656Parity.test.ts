import { describe, expect, it } from "vitest";

import {
  ONLINE_MENUS,
  adaptMenuForDirection,
  isOnlineMenuVisibleForDirection,
} from "./business-profile-config";


const plans: Record<string, {
  items: [string, string];
  order?: string;
  service?: string;
  hide?: string[];
}> = {
  Savdo: {
    items: ["Mahsulotlar", "Tovar, narx va rasm qo'shish"],
    order: "Onlayn mahsulot buyurtmalari",
  },
  "Transport va logistika": {
    items: ["Xizmatlar va tariflar", "Yo'nalish, tarif va narxlar"],
    service: "Zakaz va yo'l buyurtmalari",
  },
  "Xizmat ko'rsatish": {
    items: ["Xizmatlarim", "Xizmat turlari va narxlar"],
    service: "Chaqiruv va navbatlar",
  },
  "Maishiy xizmatlar": {
    items: ["Xizmatlar va narxlar", "Salon xizmatlari ro'yxati"],
    service: "Yozilish va navbatlar",
  },
  "Umumiy ovqatlanish": {
    items: ["Menyu va xizmatlarimiz", "Taomlar, narx va rasm"],
    order: "Onlayn zakazlar",
  },
  Qurilish: {
    items: ["Xizmatlar va ishlar", "Ish turlari va taxminiy narxlar"],
    service: "Obyekt va chaqiruvlar",
  },
  "Tibbiy xizmatlar": {
    items: ["Xizmatlar va narxlar", "Qabul, tahlil va muolajalar"],
    service: "Qabulga yozilishlar",
  },
  "Ta'lim faoliyati": {
    items: ["Kurslar va xizmatlar", "Kurslar, narx va davomiylik"],
    hide: ["orders", "service-orders"],
  },
  "Ko'chmas mulk": {
    items: ["Obyektlar bazasi", "Sotuv va ijara obyektlari"],
    service: "Ko'rik va murojaatlar",
  },
  "Qishloq xo'jaligi": {
    items: ["Mahsulotlarim", "Hosil, narx va o'lchov birligi"],
  },
  "Axborot texnologiyalari": {
    items: ["Xizmatlar va paketlar", "Loyiha, xizmat va narxlar"],
    service: "Loyiha buyurtmalari",
  },
  "Konsalting va professional": {
    items: ["Xizmatlar va narxlar", "Maslahat va hujjat xizmatlari"],
    service: "Qabul va murojaatlar",
  },
  "Madaniyat, sport, ko'ngilochar": {
    items: ["Xizmatlar va narxlar", "Mashg'ulot, ijara va tadbirlar"],
    service: "Bron va yozilishlar",
  },
  "Turizm va mehmonxona": {
    items: ["Xonalar va turpaketlar", "Xona, tur va narxlar"],
    service: "Bron buyurtmalari",
  },
  "Ishlab chiqarish": {
    items: ["Mahsulotlar katalogi", "Tayyor mahsulot va narxlar"],
    order: "Ulgurji buyurtmalar",
  },
  Hunarmandchilik: {
    items: ["Buyumlarim", "Qo'l mehnati buyumlari va narxlar"],
    order: "Buyurtma va zakazlar",
  },
  "Reklama va marketing": {
    items: ["Xizmatlar va paketlar", "SMM, target va kontent narxlari"],
    service: "Loyiha buyurtmalari",
  },
  "Poligrafiya va nashriyot": {
    items: ["Xizmatlar va narxlar", "Chop etish turlari va narxlar"],
    order: "Chop buyurtmalari",
  },
  "Moliyaviy faoliyat": {
    items: ["Xizmatlar va tariflar", "Sug'urta, qarz va boshqa tariflar"],
    service: "Murojaat va arizalar",
  },
  "Import-eksport": {
    items: ["Tovarlar va xizmatlar", "Tovar pozitsiyalari va xizmatlar"],
    order: "Partiya buyurtmalari",
  },
};

function menu(direction: string, view: string) {
  const source = ONLINE_MENUS.find((row) => row.view === view);
  if (!source || !isOnlineMenuVisibleForDirection(source, direction)) return null;
  return adaptMenuForDirection(source, direction);
}

describe("v1656 CAB_PLANS Onlaynlashtirish matritsasi", () => {
  it.each(Object.entries(plans))(
    "%s yo'nalishida labels va hide qoidalarini aynan qo'llaydi",
    (direction, plan) => {
      expect(menu(direction, "items")).toMatchObject({
        label: plan.items[0],
        caption: plan.items[1],
      });

      const order = menu(direction, "orders");
      const service = menu(direction, "service-orders");
      if (plan.hide?.includes("orders")) expect(order).toBeNull();
      else expect(order?.caption).toBe(plan.order ?? "Mahsulot buyurtmalari");
      if (plan.hide?.includes("service-orders")) expect(service).toBeNull();
      else expect(service?.caption).toBe(plan.service ?? "Xizmat va navbatlar");
    },
  );

  it("maxsus ekranlarni faqat monolitdagi yo'nalishlarda ko'rsatadi", () => {
    expect(menu("Umumiy ovqatlanish", "dining-places")?.label)
      .toBe("Stollar va xonalar");
    expect(menu("Savdo", "dining-places")).toBeNull();
    expect(menu("Ta'lim faoliyati", "education-enrollments")?.label)
      .toBe("Kursga yozilishlar");
    expect(menu("Savdo", "education-enrollments")).toBeNull();
    expect(menu("Tibbiy xizmatlar", "medical-providers")?.label)
      .toBe("Shifokorlar");
    expect(menu("Transport va logistika", "medical-providers")?.label)
      .toBe("Xizmat ko‘rsatuvchilar");
    expect(menu("Savdo", "medical-providers")).toBeNull();
  });
});

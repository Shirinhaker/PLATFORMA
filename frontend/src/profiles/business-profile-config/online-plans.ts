// Onlayn vitrina rejalari: qaysi yo'nalishda qaysi menyu ko'rinadi.

import { queueUiLabels } from "./directions";
import type { Menu } from "./types";

type OnlineDirectionPlan = {
  labels: Partial<Record<string, { label?: string; caption?: string }>>;
  hide?: readonly string[];
};

const ONLINE_DIRECTION_PLANS: Record<string, OnlineDirectionPlan> = {
  Savdo: {
    labels: {
      items: { label: "Mahsulotlar", caption: "Tovar, narx va rasm qo'shish" },
      orders: { caption: "Onlayn mahsulot buyurtmalari" },
    },
  },
  "Transport va logistika": {
    labels: {
      items: { label: "Xizmatlar va tariflar", caption: "Yo'nalish, tarif va narxlar" },
      "service-orders": { caption: "Zakaz va yo'l buyurtmalari" },
    },
  },
  "Xizmat ko'rsatish": {
    labels: {
      items: { label: "Xizmatlarim", caption: "Xizmat turlari va narxlar" },
      "service-orders": { caption: "Chaqiruv va navbatlar" },
    },
  },
  "Maishiy xizmatlar": {
    labels: {
      items: { label: "Xizmatlar va narxlar", caption: "Salon xizmatlari ro'yxati" },
      "service-orders": { caption: "Yozilish va navbatlar" },
    },
  },
  "Umumiy ovqatlanish": {
    labels: {
      items: { label: "Menyu va xizmatlarimiz", caption: "Taomlar, narx va rasm" },
      orders: { caption: "Onlayn zakazlar" },
    },
  },
  Qurilish: {
    labels: {
      items: {
        label: "Xizmatlar va ishlar",
        caption: "Ish turlari va taxminiy narxlar",
      },
      "service-orders": { caption: "Obyekt va chaqiruvlar" },
    },
  },
  "Tibbiy xizmatlar": {
    labels: {
      items: { label: "Xizmatlar va narxlar", caption: "Qabul, tahlil va muolajalar" },
      "service-orders": { caption: "Qabulga yozilishlar" },
    },
  },
  "Ta'lim faoliyati": {
    hide: ["orders", "service-orders"],
    labels: {
      items: { label: "Kurslar va xizmatlar", caption: "Kurslar, narx va davomiylik" },
    },
  },
  "Ko'chmas mulk": {
    labels: {
      items: { label: "Obyektlar bazasi", caption: "Sotuv va ijara obyektlari" },
      "service-orders": { caption: "Ko'rik va murojaatlar" },
    },
  },
  "Qishloq xo'jaligi": {
    labels: {
      items: { label: "Mahsulotlarim", caption: "Hosil, narx va o'lchov birligi" },
    },
  },
  "Axborot texnologiyalari": {
    labels: {
      items: { label: "Xizmatlar va paketlar", caption: "Loyiha, xizmat va narxlar" },
      "service-orders": { caption: "Loyiha buyurtmalari" },
    },
  },
  "Konsalting va professional": {
    labels: {
      items: {
        label: "Xizmatlar va narxlar",
        caption: "Maslahat va hujjat xizmatlari",
      },
      "service-orders": { caption: "Qabul va murojaatlar" },
    },
  },
  "Madaniyat, sport, ko'ngilochar": {
    labels: {
      items: {
        label: "Xizmatlar va narxlar",
        caption: "Mashg'ulot, ijara va tadbirlar",
      },
      "service-orders": { caption: "Bron va yozilishlar" },
    },
  },
  "Turizm va mehmonxona": {
    labels: {
      items: { label: "Xonalar va turpaketlar", caption: "Xona, tur va narxlar" },
      "service-orders": { caption: "Bron buyurtmalari" },
    },
  },
  "Ishlab chiqarish": {
    labels: {
      items: { label: "Mahsulotlar katalogi", caption: "Tayyor mahsulot va narxlar" },
      orders: { caption: "Ulgurji buyurtmalar" },
    },
  },
  Hunarmandchilik: {
    labels: {
      items: { label: "Buyumlarim", caption: "Qo'l mehnati buyumlari va narxlar" },
      orders: { caption: "Buyurtma va zakazlar" },
    },
  },
  "Reklama va marketing": {
    labels: {
      items: {
        label: "Xizmatlar va paketlar",
        caption: "SMM, target va kontent narxlari",
      },
      "service-orders": { caption: "Loyiha buyurtmalari" },
    },
  },
  "Poligrafiya va nashriyot": {
    labels: {
      items: {
        label: "Xizmatlar va narxlar",
        caption: "Chop etish turlari va narxlar",
      },
      orders: { caption: "Chop buyurtmalari" },
    },
  },
  "Moliyaviy faoliyat": {
    labels: {
      items: {
        label: "Xizmatlar va tariflar",
        caption: "Sug'urta, qarz va boshqa tariflar",
      },
      "service-orders": { caption: "Murojaat va arizalar" },
    },
  },
  "Import-eksport": {
    labels: {
      items: {
        label: "Tovarlar va xizmatlar",
        caption: "Tovar pozitsiyalari va xizmatlar",
      },
      orders: { caption: "Partiya buyurtmalari" },
    },
  },
};

export function isOnlineMenuVisibleForDirection(
  menu: Menu,
  direction: string,
): boolean {
  if (menu.directions && !menu.directions.includes(direction)) return false;
  if (menu.excludedDirections?.includes(direction)) return false;
  return !(ONLINE_DIRECTION_PLANS[direction]?.hide ?? []).includes(menu.view);
}

export function adaptMenuForDirection(menu: Menu, direction: string): Menu {
  const planLabel = ONLINE_DIRECTION_PLANS[direction]?.labels[menu.view];
  const adapted = planLabel ? { ...menu, ...planLabel } : menu;
  if (menu.view !== "medical-providers") return adapted;
  const labels = queueUiLabels(direction);
  return {
    ...adapted,
    label: labels.providers,
    caption: `${labels.provider} kartasi, xizmat va ish jadvali`,
  };
}

// Bosh sahifadagi ko'rsatkichlar, yo'nalish bo'yicha.

import { money } from "./helpers";
import type { Metric } from "./types";

export const DEFAULT_METRICS: Metric[] = [
  {
    label: "Bugungi tushum",
    key: "revenue",
    sub: "Bugungi savdo tushumi",
    view: "sales",
    money: true,
  },
  {
    label: "Yangi buyurtmalar",
    key: "new_orders",
    sub: "Qabul qilinmagan buyurtmalar",
    view: "orders",
  },
  {
    label: "Faol buyurtmalar",
    key: "active_orders",
    sub: "Jarayondagi buyurtmalar",
    view: "orders",
  },
  {
    label: "Bildirishnomalar",
    key: "problem_orders",
    sub: "E’tibor talab holatlar",
    view: "notifications",
  },
];

export const METRICS: Record<string, Metric[]> = {
  Savdo: [
    {
      label: "Bugungi savdo",
      key: "revenue",
      sub: "Bugungi tushum",
      view: "sales",
      money: true,
    },
    {
      label: "Yangi buyurtma",
      key: "new_orders",
      sub: "Qabul qilinmagan buyurtmalar",
      view: "orders",
    },
    {
      label: "Umumiy qarz",
      key: "debt_total",
      sub: "Qarz daftaridagi qoldiq",
      view: "debtors",
      money: true,
    },
    {
      label: "Ombor ogohlantirishi",
      key: "low_stock",
      sub: "Kam qolgan mahsulotlar",
      view: "warehouse",
    },
  ],
  "Umumiy ovqatlanish": [
    {
      label: "Bugungi savdo",
      key: "sales_count",
      sub: "Bugungi savdolar soni",
      view: "sales",
    },
    {
      label: "Ochiq buyurtmalar",
      key: "active_orders",
      sub: "Jarayondagi buyurtmalar",
      view: "orders",
    },
    {
      label: "Band stol/xona",
      key: "occupied_places",
      sub: "Faol band joylar",
      view: "dining-places",
    },
    {
      label: "Ombor ogohlantirishi",
      key: "low_stock",
      sub: "Kam qolgan masalliqlar",
      view: "warehouse",
    },
  ],
  "Ta'lim faoliyati": [
    {
      label: "Bugungi darslar",
      key: "today_lessons",
      sub: "Bugungi jadval",
      view: "education-schedule",
    },
    {
      label: "Guruhlar",
      key: "groups",
      sub: "Faol guruhlar",
      view: "education-groups",
    },
    {
      label: "O‘quvchilar",
      key: "students",
      sub: "Faol o‘quvchilar",
      view: "education-students",
    },
    {
      label: "Muddati o‘tgan to‘lov",
      key: "debt_total",
      sub: "To‘lov nazoratidagi qarz",
      view: "education-payments",
      money: true,
    },
  ],
  "Tibbiy xizmatlar": [
    {
      label: "Bugungi qabullar",
      key: "service_today",
      sub: "Bugungi yozilishlar",
      view: "service-orders",
    },
    {
      label: "Navbat",
      key: "service_active",
      sub: "Kutayotgan va qabuldagi",
      view: "medical-queues",
    },
    {
      label: "Yangi yozilishlar",
      key: "new_orders",
      sub: "Yangi qabul so‘rovlari",
      view: "service-orders",
    },
    {
      label: "Bugungi to‘lovlar",
      key: "revenue",
      sub: "Bugungi tushum",
      view: "sales",
      money: true,
    },
  ],
};

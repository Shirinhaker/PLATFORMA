import { findCatalogDirection } from "../legacy/public/catalog-data";
import type { PublicNavigationState } from "../legacy/public/public-navigation";
import type { PublicView } from "../legacy/public/public-contract";

export function appTitle(navigation: PublicNavigationState) {
  const category = navigation.categoryId
    ? findCatalogDirection(navigation.categoryId)
    : null;
  const titles: Record<PublicView, string | undefined> = {
    auth: "Kirish",
    cabinet: "Mening kabinetim",
    catalog: "Katalog",
    category: category?.name ?? "Yo‘nalish",
    home: undefined,
    listings: "E’lonlar",
    location: "Manzil",
    cart: "Savat",
    "taxi-call": "Taxi chaqirish",
    taxidrv: "Taxi — haydovchi",
  };
  return titles[navigation.view];
}

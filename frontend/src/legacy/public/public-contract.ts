export const PUBLIC_VIEWS = [
  "home",
  "catalog",
  "category",
  "listings",
  "location",
  "auth",
  "cabinet",
] as const;

export type PublicView = (typeof PUBLIC_VIEWS)[number];

export const PUBLIC_HEADER_ACTIONS = ["home", "location", "account"] as const;

export type PublicHeaderAction = (typeof PUBLIC_HEADER_ACTIONS)[number];

export const CATALOG_SEARCH_TYPES = [
  "all",
  "product",
  "service",
  "business",
  "specialist",
  "user",
] as const;

export type CatalogSearchType = (typeof CATALOG_SEARCH_TYPES)[number];

export const PHASE3B_OUT_OF_SCOPE = [
  "taxi",
  "cart",
  "payments",
  "admin",
  "staff",
] as const;

export type Phase3BOutOfScope = (typeof PHASE3B_OUT_OF_SCOPE)[number];

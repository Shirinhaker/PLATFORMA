const API_STORAGE_KEY = "koprik_api_base_url";
const RAILWAY_STAGING_API = "https://platforma-production-f753.up.railway.app";

function clean(value: string | null | undefined): string {
  return String(value ?? "").trim().replace(/\/+$/, "");
}

function safeHttps(value: string): string {
  if (!value) return "";
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "https:") return "";
    return parsed.origin;
  } catch {
    return "";
  }
}

function railwayDefault(origin: string): string {
  try {
    const parsed = new URL(origin);
    if (parsed.protocol !== "https:") return "";
    if (!parsed.hostname.endsWith(".up.railway.app")) return "";
    if (parsed.origin === RAILWAY_STAGING_API) return parsed.origin;
    return RAILWAY_STAGING_API;
  } catch {
    return "";
  }
}

export function resolveApiBaseUrl(
  configured: string | undefined,
  location: Pick<Location, "origin" | "search"> = window.location,
  storage: Pick<Storage, "getItem" | "setItem"> = window.localStorage,
): string {
  const query = new URLSearchParams(location.search).get("api");
  const fromQuery = safeHttps(clean(query));
  if (fromQuery) {
    storage.setItem(API_STORAGE_KEY, fromQuery);
    return fromQuery;
  }

  const fromBuild = safeHttps(clean(configured));
  if (fromBuild) {
    storage.setItem(API_STORAGE_KEY, fromBuild);
    return fromBuild;
  }

  // Query orqali tekshirilgan ishlaydigan API manzili localStorage’da
  // saqlanadi. Sahifa yangilanganda shu qiymat Railway fallbackdan oldin
  // olinishi shart; aks holda refresh to‘g‘ri manzilni yana eskisiga almashtiradi.
  const fromStorage = safeHttps(clean(storage.getItem(API_STORAGE_KEY)));
  if (fromStorage) return fromStorage;

  // Faqat yangi brauzerda hali saqlangan qiymat bo‘lmasa staging fallback.
  const fromRailway = railwayDefault(clean(location.origin));
  if (fromRailway) {
    storage.setItem(API_STORAGE_KEY, fromRailway);
    return fromRailway;
  }

  return clean(location.origin);
}

export { RAILWAY_STAGING_API };

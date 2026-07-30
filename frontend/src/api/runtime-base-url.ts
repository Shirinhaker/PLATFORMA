const API_STORAGE_KEY = "koprik_api_base_url";
const API_STORAGE_SOURCE_KEY = "koprik_api_base_url_source";
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
    storage.setItem(API_STORAGE_SOURCE_KEY, "query");
    return fromQuery;
  }

  const fromBuild = safeHttps(clean(configured));
  if (fromBuild) {
    storage.setItem(API_STORAGE_KEY, fromBuild);
    storage.setItem(API_STORAGE_SOURCE_KEY, "build");
    return fromBuild;
  }

  const fromStorage = safeHttps(clean(storage.getItem(API_STORAGE_KEY)));
  const storageSource = storage.getItem(API_STORAGE_SOURCE_KEY);
  const fromRailway = railwayDefault(clean(location.origin));

  // Query yoki build orqali aniq tasdiqlangan manzil refreshdan keyin saqlanadi.
  // Eski versiyalar qoldirgan belgisiz va noto‘g‘ri Railway URL esa ma’lum
  // staging API manzilini bosib ketmasligi kerak.
  if (
    fromStorage
    && (
      !fromRailway
      || fromStorage === fromRailway
      || storageSource === "query"
      || storageSource === "build"
    )
  ) {
    return fromStorage;
  }

  if (fromRailway) {
    storage.setItem(API_STORAGE_KEY, fromRailway);
    storage.setItem(API_STORAGE_SOURCE_KEY, "railway");
    return fromRailway;
  }

  return fromStorage || clean(location.origin);
}

export { RAILWAY_STAGING_API };

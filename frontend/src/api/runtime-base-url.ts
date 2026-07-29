const API_STORAGE_KEY = "koprik_api_base_url";

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
  if (fromBuild) return fromBuild;

  const fromStorage = safeHttps(clean(storage.getItem(API_STORAGE_KEY)));
  if (fromStorage) return fromStorage;

  return clean(location.origin);
}

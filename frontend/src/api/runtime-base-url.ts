const LEGACY_STORAGE_KEYS = [
  "koprik_api_base_url",
  "koprik_api_base_url_source",
] as const;


type RuntimeLocation = Pick<Location, "origin" | "search">;
type LegacyStorage = Pick<Storage, "removeItem">;


type RuntimeConfig = {
  apiBaseUrl?: unknown;
  sameOriginApiProxy?: unknown;
};


export class ApiConfigurationError extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "ApiConfigurationError";
  }
}


function clean(value: unknown): string {
  return String(value ?? "").trim().replace(/\/+$/, "");
}


function safeHttpsOrigin(value: unknown): string {
  const text = clean(value);
  if (!text) return "";
  try {
    const parsed = new URL(text);
    if (parsed.protocol !== "https:") return "";
    if (parsed.pathname !== "/" || parsed.search || parsed.hash) return "";
    return parsed.origin;
  } catch {
    return "";
  }
}


function removeLegacyStorage(storage: LegacyStorage): void {
  for (const key of LEGACY_STORAGE_KEYS) {
    try {
      storage.removeItem(key);
    } catch {
      // Storage can be blocked by privacy settings. It is no longer required.
    }
  }
}


async function readJsonObject(response: Response): Promise<Record<string, unknown>> {
  const text = await response.text();
  try {
    const parsed = JSON.parse(text) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // The Railway SPA server can return index.html with status 200.
  }
  throw new ApiConfigurationError("runtime_config_not_json");
}


async function sameOriginProxyAvailable(
  fetcher: typeof fetch,
  origin: string,
): Promise<boolean> {
  try {
    const response = await fetcher(`${origin}/api/v1/build`, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return false;
    const payload = await readJsonObject(response);
    return (
      typeof payload.api_version === "string"
      && typeof payload.foundation === "string"
    );
  } catch {
    return false;
  }
}


export async function loadApiBaseUrl(
  fetcher: typeof fetch = window.fetch.bind(window),
  location: RuntimeLocation = window.location,
  storage: LegacyStorage = window.localStorage,
): Promise<string> {
  removeLegacyStorage(storage);

  const query = new URLSearchParams(location.search).get("api");
  if (query !== null) {
    const debugOrigin = safeHttpsOrigin(query);
    if (!debugOrigin) {
      throw new ApiConfigurationError("api_debug_origin_invalid");
    }
    return debugOrigin;
  }

  const origin = safeHttpsOrigin(location.origin);
  if (!origin) {
    throw new ApiConfigurationError("frontend_origin_invalid");
  }

  const configUrl = `${origin}/runtime-config.json`;
  let runtimeConfigFailure = "api_runtime_configuration_missing";
  try {
    const response = await fetcher(configUrl, {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (response.ok) {
      const payload = await readJsonObject(response) as RuntimeConfig;
      const runtimeOrigin = safeHttpsOrigin(payload.apiBaseUrl);
      if (runtimeOrigin && payload.sameOriginApiProxy === true) {
        if (await sameOriginProxyAvailable(fetcher, origin)) {
          return origin;
        }
        throw new ApiConfigurationError(
          "same_origin_api_proxy_unavailable",
        );
      }
      if (runtimeOrigin) return runtimeOrigin;
      runtimeConfigFailure = "runtime_config_api_origin_invalid";
    } else if (response.status !== 404) {
      runtimeConfigFailure = `runtime_config_http_${response.status}`;
    }
  } catch (error) {
    if (error instanceof ApiConfigurationError) {
      if (error.code === "same_origin_api_proxy_unavailable") {
        throw error;
      }
      runtimeConfigFailure = error.code;
    } else {
      runtimeConfigFailure = "runtime_config_unreachable";
    }
  }

  if (await sameOriginProxyAvailable(fetcher, origin)) {
    return origin;
  }

  throw new ApiConfigurationError(runtimeConfigFailure);
}

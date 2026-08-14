import { describe, expect, it, vi } from "vitest";

import {
  ApiConfigurationError,
  loadApiBaseUrl,
} from "./runtime-base-url";


type FetchResponse = {
  status: number;
  ok: boolean;
  text: () => Promise<string>;
};

function response(status: number, body: string): FetchResponse {
  return {
    status,
    ok: status >= 200 && status < 300,
    text: async () => body,
  };
}

function location(search = "") {
  return {
    origin: "https://frontend-staging-production-6c41.up.railway.app",
    search,
  } as Location;
}

function storage() {
  return {
    removeItem: vi.fn(),
  };
}

function missingConfigRequest() {
  const fetcher = vi.fn()
    .mockResolvedValueOnce(response(404, "missing"))
    .mockResolvedValueOnce(response(404, "missing"));
  return loadApiBaseUrl(
    fetcher as unknown as typeof fetch,
    location(),
    storage(),
  );
}


describe("loadApiBaseUrl", () => {
  it("uses an HTTPS query only as a non-persistent debug override", async () => {
    const fetcher = vi.fn();
    const legacyStorage = storage();

    const result = await loadApiBaseUrl(
      fetcher as unknown as typeof fetch,
      location("?api=https%3A%2F%2Fdebug-api.example%2F"),
      legacyStorage,
    );

    expect(result).toBe("https://debug-api.example");
    expect(fetcher).not.toHaveBeenCalled();
    expect(legacyStorage.removeItem).toHaveBeenCalledWith(
      "koprik_api_base_url",
    );
    expect(legacyStorage.removeItem).toHaveBeenCalledWith(
      "koprik_api_base_url_source",
    );
  });

  it("loads the API origin from runtime-config.json", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(
      200,
      JSON.stringify({ apiBaseUrl: "https://api-staging.example/" }),
    ));

    await expect(loadApiBaseUrl(
      fetcher as unknown as typeof fetch,
      location(),
      storage(),
    )).resolves.toBe("https://api-staging.example");

    expect(fetcher).toHaveBeenCalledWith(
      "https://frontend-staging-production-6c41.up.railway.app/runtime-config.json",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("uses the frontend origin when Railway requires the first-party API proxy", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response(
        200,
        JSON.stringify({
          apiBaseUrl: "https://api-staging.example",
          sameOriginApiProxy: true,
        }),
      ))
      .mockResolvedValueOnce(response(
        200,
        JSON.stringify({ api_version: "v1", foundation: "phase1" }),
      ));

    await expect(loadApiBaseUrl(
      fetcher as unknown as typeof fetch,
      location(),
      storage(),
    )).resolves.toBe(
      "https://frontend-staging-production-6c41.up.railway.app",
    );

    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "https://frontend-staging-production-6c41.up.railway.app/api/v1/build",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("fails closed when the required first-party API proxy is unavailable", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response(
        200,
        JSON.stringify({
          apiBaseUrl: "https://api-staging.example",
          sameOriginApiProxy: true,
        }),
      ))
      .mockResolvedValueOnce(response(404, "not found"));

    await expect(loadApiBaseUrl(
      fetcher as unknown as typeof fetch,
      location(),
      storage(),
    )).rejects.toMatchObject({
      code: "same_origin_api_proxy_unavailable",
    });
  });

  it("uses the same runtime config in a fresh tab or incognito session", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(
      200,
      JSON.stringify({ apiBaseUrl: "https://api-staging.example" }),
    ));

    const first = await loadApiBaseUrl(
      fetcher as unknown as typeof fetch,
      location(),
      storage(),
    );
    const second = await loadApiBaseUrl(
      fetcher as unknown as typeof fetch,
      location(),
      storage(),
    );

    expect(first).toBe("https://api-staging.example");
    expect(second).toBe(first);
  });

  it("accepts same-origin only when /api/v1/build proves a proxy exists", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response(404, "not found"))
      .mockResolvedValueOnce(response(
        200,
        JSON.stringify({ api_version: "v1", foundation: "phase1" }),
      ));

    await expect(loadApiBaseUrl(
      fetcher as unknown as typeof fetch,
      location(),
      storage(),
    )).resolves.toBe(
      "https://frontend-staging-production-6c41.up.railway.app",
    );
  });

  it("rejects the SPA index fallback returned as runtime-config.json", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response(200, "<!doctype html><div id='root'></div>"))
      .mockResolvedValueOnce(response(200, "<!doctype html>"));

    await expect(loadApiBaseUrl(
      fetcher as unknown as typeof fetch,
      location(),
      storage(),
    )).rejects.toMatchObject({
      code: "runtime_config_not_json",
    });
  });

  it("fails clearly instead of guessing a Railway API domain", async () => {
    await expect(missingConfigRequest()).rejects.toEqual(
      expect.any(ApiConfigurationError),
    );
    await expect(missingConfigRequest()).rejects.toMatchObject({
      code: "api_runtime_configuration_missing",
    });
  });

  it("rejects an insecure debug API origin", async () => {
    await expect(loadApiBaseUrl(
      vi.fn() as unknown as typeof fetch,
      location("?api=http%3A%2F%2Finsecure.local"),
      storage(),
    )).rejects.toMatchObject({ code: "api_debug_origin_invalid" });
  });
});

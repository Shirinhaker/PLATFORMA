import { describe, expect, it, vi } from "vitest";

import {
  RAILWAY_STAGING_API,
  resolveApiBaseUrl,
} from "./runtime-base-url";


describe("resolveApiBaseUrl", () => {
  it("uses and stores an HTTPS api query parameter", () => {
    const storage = {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
    };

    const result = resolveApiBaseUrl(
      undefined,
      {
        origin: "https://web-production.up.railway.app",
        search: "?api=https%3A%2F%2Fapi-staging.up.railway.app%2F",
      } as Location,
      storage,
    );

    expect(result).toBe("https://api-staging.up.railway.app");
    expect(storage.setItem).toHaveBeenCalledWith(
      "koprik_api_base_url",
      "https://api-staging.up.railway.app",
    );
  });

  it("prefers a configured build URL over stored and Railway values", () => {
    const storage = {
      getItem: vi.fn().mockReturnValue("https://stored-api.up.railway.app"),
      setItem: vi.fn(),
    };

    expect(resolveApiBaseUrl(
      "https://configured-api.up.railway.app/",
      {
        origin: "https://web-production.up.railway.app",
        search: "",
      } as Location,
      storage,
    )).toBe("https://configured-api.up.railway.app");
  });

  it("uses the stored API URL when the build variable is missing", () => {
    const storage = {
      getItem: vi.fn().mockReturnValue("https://stored-api.up.railway.app"),
      setItem: vi.fn(),
    };

    expect(resolveApiBaseUrl(
      undefined,
      {
        origin: "https://web-production.up.railway.app",
        search: "",
      } as Location,
      storage,
    )).toBe("https://stored-api.up.railway.app");
  });

  it("automatically routes a Railway web deployment to api-staging", () => {
    const storage = {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
    };

    expect(resolveApiBaseUrl(
      undefined,
      {
        origin: "https://web-production-aed95.up.railway.app",
        search: "",
      } as Location,
      storage,
    )).toBe(RAILWAY_STAGING_API);
    expect(storage.setItem).toHaveBeenCalledWith(
      "koprik_api_base_url",
      RAILWAY_STAGING_API,
    );
  });

  it("rejects insecure query configuration on a custom domain", () => {
    const storage = {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
    };

    expect(resolveApiBaseUrl(
      undefined,
      {
        origin: "https://koprik.uz",
        search: "?api=http%3A%2F%2Finsecure.local",
      } as Location,
      storage,
    )).toBe("https://koprik.uz");
    expect(storage.setItem).not.toHaveBeenCalled();
  });
});

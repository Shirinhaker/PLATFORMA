// @vitest-environment node

import { describe, expect, it } from "vitest";

import { resolvePreviewApiTarget } from "../../vite.config";


describe("resolvePreviewApiTarget", () => {
  it("uses the Railway API origin for the same-origin preview proxy", () => {
    expect(resolvePreviewApiTarget({
      VITE_API_BASE_URL: "https://api-staging.example/",
    })).toBe("https://api-staging.example");
  });

  it("rejects an insecure or path-scoped proxy target", () => {
    expect(() => resolvePreviewApiTarget({
      VITE_API_BASE_URL: "http://api-staging.example",
    })).toThrow("preview_api_proxy_target_must_use_https");
    expect(() => resolvePreviewApiTarget({
      VITE_API_BASE_URL: "https://api-staging.example/v1",
    })).toThrow("preview_api_proxy_target_must_be_an_origin");
  });

  it("leaves local preview without a proxy when no API origin is configured", () => {
    expect(resolvePreviewApiTarget({})).toBe("");
  });
});

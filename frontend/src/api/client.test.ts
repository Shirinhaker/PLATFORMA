import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";


describe("ApiClient", () => {
  it("uses the versioned API and exactly one auth mechanism", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          api_version: "v1",
          foundation: "phase1",
          legacy_build: "v1656",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const client = new ApiClient("https://api.koprik.uz", fetcher, {
      kind: "telegram",
      initData: "signed-init-data",
    });
    await client.getBuild();
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.koprik.uz/api/v1/build",
      expect.objectContaining({
        credentials: "include",
        headers: expect.objectContaining({
          "X-Telegram-Init-Data": "signed-init-data",
        }),
      }),
    );
  });
});

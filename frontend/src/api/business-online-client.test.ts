import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";


function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}


describe("business online API client", () => {
  it("reads a versioned business resource with cookie credentials", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({
      resource: "items",
      items: [{ id: 1, name: "Muhr" }],
    }));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getBusinessOnlineResource("items");

    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example/api/v1/business-online/items",
      expect.objectContaining({
        method: "GET",
        credentials: "include",
      }),
    );
    expect(fetcher.mock.calls[0]?.[1]?.headers).not.toHaveProperty(
      "X-CSRF-Token",
    );
  });

  it("sends online actions with the active CSRF token", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(json({
        account_id: 7,
        account_type: "business",
        name: "Muhr",
        login: "muhr1",
        csrf_token: "csrf-online",
        expires_at: "2026-08-30T08:00:00Z",
      }))
      .mockResolvedValueOnce(json({
        resource: "notifications",
        item: null,
        items: [],
      }));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getSession();
    await client.applyBusinessOnlineAction(
      "notifications",
      "mark_all_read",
      {},
    );

    expect(fetcher).toHaveBeenLastCalledWith(
      "https://api.example/api/v1/business-online/notifications/actions/mark_all_read",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          "X-CSRF-Token": "csrf-online",
        }),
        body: JSON.stringify({
          record_id: undefined,
          payload: {},
        }),
      }),
    );
  });
});

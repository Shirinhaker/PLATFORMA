import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";


function response(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  };
}


describe("typed v1656 account settings API client", () => {
  it("uses the versioned owner endpoint and CSRF-protects credential writes", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response({
        account_id: 7,
        account_type: "business",
        name: "Turon",
        login: "turondokon",
        csrf_token: "settings-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValue(response({ ok: true, login: "turondokon" }));
    const client = new ApiClient("https://api.test", fetcher, { kind: "web" });
    await client.getSession();

    await client.getBusinessCredentials();
    await client.updateBusinessCredentials({
      new_login: "yangi_login",
      new_password: "parol123",
    });

    expect(fetcher.mock.calls.slice(1).map(([url, init]) => [
      url,
      init?.method,
      init?.body,
    ])).toEqual([
      [
        "https://api.test/api/v1/account-settings/business-credentials",
        "GET",
        undefined,
      ],
      [
        "https://api.test/api/v1/account-settings/business-credentials",
        "PUT",
        JSON.stringify({ new_login: "yangi_login", new_password: "parol123" }),
      ],
    ]);
    expect(fetcher.mock.calls[1]?.[1]?.headers)
      .not.toHaveProperty("X-CSRF-Token");
    expect(fetcher.mock.calls[2]?.[1]?.headers).toMatchObject({
      "X-CSRF-Token": "settings-csrf",
    });
  });
});

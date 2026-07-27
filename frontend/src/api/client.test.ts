import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";


function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}


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

  it("restores the cookie session with credentials", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      account_id: 7,
      account_type: "business",
      name: "Turon",
      login: "b_turon",
      csrf_token: "csrf",
      expires_at: "2026-08-27T08:00:00Z",
    }));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getSession();

    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example/api/v1/auth/session",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("adds csrf only to state-changing authenticated requests", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 7,
        account_type: "user",
        name: "Test",
        login: "u_test",
        csrf_token: "csrf-value",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValueOnce(jsonResponse({
        account_id: 7,
        name: "Yangi ism",
        phone: "",
        public_username: "",
        region: "",
        district: "",
        mahalla: "",
        latitude: null,
        longitude: null,
        location_exact: false,
        avatar_object_key: "",
        avatar_x: 50,
        avatar_y: 50,
        avatar_zoom: 1,
      }));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getSession();
    await client.updateUserProfile({ name: "Yangi ism" });

    expect(fetcher.mock.calls[0]?.[1]?.headers).not.toHaveProperty(
      "X-CSRF-Token",
    );
    expect(fetcher.mock.calls[1]?.[1]?.headers).toMatchObject({
      "X-CSRF-Token": "csrf-value",
    });
  });

  it("throws a typed API error body", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      code: "authentication_required",
      message: "Avval tizimga kiring.",
      request_id: "request-1",
    }, 401));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await expect(client.getSession()).rejects.toMatchObject({
      status: 401,
      code: "authentication_required",
      requestId: "request-1",
    });
  });

  it("uploads granted bytes without browser credentials", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(null, {
      status: 200,
    }));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );
    const file = new File(["image"], "avatar.png", {
      type: "image/png",
    });

    await client.uploadGrantedFile({
      object_key: "private/user/7/avatar/key.png",
      upload_url: "https://r2.example/upload",
      method: "PUT",
      headers: { "Content-Type": "image/png" },
      expires_in_seconds: 900,
    }, file);

    expect(fetcher).toHaveBeenCalledWith(
      "https://r2.example/upload",
      expect.objectContaining({
        method: "PUT",
        credentials: "omit",
        body: file,
      }),
    );
  });
});

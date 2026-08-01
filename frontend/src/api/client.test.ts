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

  it("encodes public discovery filters without requiring a session", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      items: [],
      page: 2,
      page_size: 12,
      total: 0,
      pages: 0,
    }));
    const client = new ApiClient(
      "https://api.example/",
      fetcher,
      { kind: "web" },
    );

    await client.searchPublic({
      q: "telefon ta’miri",
      result_type: "business",
      direction: "Savdo",
      district: "Qumqo‘rg‘on",
      page: 2,
      page_size: 12,
    });

    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example/api/v1/public/search"
        + "?q=telefon+ta%E2%80%99miri"
        + "&result_type=business"
        + "&direction=Savdo"
        + "&district=Qumqo%E2%80%98rg%E2%80%98on"
        + "&page=2&page_size=12",
      expect.objectContaining({
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      }),
    );
  });

  it("serializes catalog filters without auth or CSRF", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      items: [],
      page: 2,
      page_size: 20,
      total: 0,
      pages: 0,
    }));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getCatalogItems({
      kind: "service",
      district: "Qumqo‘rg‘on",
      page: 2,
      page_size: 20,
    });

    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example/api/v1/public/catalog/items"
        + "?kind=service"
        + "&district=Qumqo%E2%80%98rg%E2%80%98on"
        + "&page=2&page_size=20",
      expect.objectContaining({
        method: "GET",
        headers: { Accept: "application/json" },
      }),
    );
    expect(fetcher.mock.calls[0]?.[1]?.headers).not.toHaveProperty(
      "X-CSRF-Token",
    );
  });

  it("serializes public advertisement location without CSRF", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse([]));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getAdvertisements({
      placement: "home",
      region: "Surxondaryo",
      district: "Qumqo‘rg‘on",
    });

    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example/api/v1/public/advertisements"
        + "?placement=home"
        + "&region=Surxondaryo"
        + "&district=Qumqo%E2%80%98rg%E2%80%98on",
      expect.objectContaining({
        method: "GET",
        headers: { Accept: "application/json" },
      }),
    );
    expect(fetcher.mock.calls[0]?.[1]?.headers).not.toHaveProperty(
      "X-CSRF-Token",
    );
  });

  it("serializes public E'lonlar filters without auth or CSRF", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse([]));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getPublicListings({ cat: "uy", q: "3 xonali uy" });

    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example/api/v1/public/listings?cat=uy&q=3+xonali+uy",
      expect.objectContaining({
        method: "GET",
        headers: { Accept: "application/json" },
      }),
    );
    expect(fetcher.mock.calls[0]?.[1]?.headers).not.toHaveProperty(
      "X-CSRF-Token",
    );
  });

  it("protects E'lon yaratish va saqlash requests with session CSRF", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 7,
        account_type: "user",
        name: "Ali",
        login: "u_ali",
        csrf_token: "listing-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValueOnce(jsonResponse({}))
      .mockResolvedValueOnce(jsonResponse({ saved: true }));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getSession();
    await client.createListing({
      cat: "uy",
      title: "Uy sotiladi",
      price: "Kelishilgan",
      descr: "Markazda",
      address: "Qumqo'rg'on",
      lat: 37.82,
      lng: 67.58,
      visibility: "all",
      media: [],
    });
    await client.toggleListingSave("l_1234567890abcdef");

    expect(fetcher.mock.calls[1]?.[1]?.headers).toMatchObject({
      "X-CSRF-Token": "listing-csrf",
    });
    expect(fetcher.mock.calls[2]?.[1]?.headers).toMatchObject({
      "X-CSRF-Token": "listing-csrf",
    });
  });

  it("uses the v1656 Home map, offers, followed and feature contracts", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({}));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getHomeMap({ district: "Qumqo‘rg‘on" });
    await client.getDistrictOffers({ district: "Qumqo‘rg‘on" });
    await client.getFollowedProfiles();
    await client.getPublicProfile("business", "b_public");
    await client.getPublicFeatures();

    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
      "https://api.example/api/v1/public/home/map"
        + "?district=Qumqo%E2%80%98rg%E2%80%98on",
      "https://api.example/api/v1/public/home/district-offers"
        + "?district=Qumqo%E2%80%98rg%E2%80%98on",
      "https://api.example/api/v1/public/home/followed-profiles",
      "https://api.example/api/v1/public/profiles/business/b_public",
      "https://api.example/api/v1/public/features",
    ]);
  });

  it("records advertisement views and clicks without CSRF", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(null, {
      status: 204,
    }));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.recordAdvertisementViews(["a_first", "a_second"]);
    await client.recordAdvertisementClick("a_first");

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "https://api.example/api/v1/public/advertisements/views",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ ids: ["a_first", "a_second"] }),
      }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "https://api.example/api/v1/public/advertisements/a_first/click",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetcher.mock.calls[0]?.[1]?.headers).not.toHaveProperty(
      "X-CSRF-Token",
    );
  });

  it("reverse geocodes the exact confirmed map center", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      address: "Beruniy ko‘chasi, Qumqo‘rg‘on tumani",
    }));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.reverseGeocode(37.838933493659454, 67.58345251326438);

    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example/api/geocode"
        + "?lat=37.838933493659454&lng=67.58345251326438",
      expect.objectContaining({
        method: "GET",
        headers: { Accept: "application/json" },
      }),
    );
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

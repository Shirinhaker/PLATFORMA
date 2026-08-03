import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";


function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}


describe("ApiClient", () => {
  it("submits a course enrollment through the authenticated v1 API", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 5,
        account_type: "user",
        name: "Ali",
        login: "u_ali",
        csrf_token: "education-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, id: 91 }, 201));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();
    const body = {
      course_item_public_id: "s_english",
      phone: "+998901234567",
      note: "Kechki guruh",
    };

    await client.createCourseEnrollment(body);

    expect(fetcher).toHaveBeenLastCalledWith(
      "https://api.example/api/v1/education/enrollments",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(body),
        headers: expect.objectContaining({
          "X-CSRF-Token": "education-csrf",
        }),
      }),
    );
  });

  it("uses the typed Q4 customer queue and notification endpoints", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 5,
        account_type: "user",
        name: "Ali",
        login: "u_ali",
        csrf_token: "queue-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValue(jsonResponse([]));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();

    await client.getMyQueues();
    await client.cancelMyQueue(41);
    await client.markQueueNotificationRead(8);

    expect(fetcher.mock.calls.slice(1).map(([url, init]) => [
      url,
      init?.method,
      init?.body,
    ])).toEqual([
      ["https://api.example/api/v1/queues/mine", "GET", undefined],
      ["https://api.example/api/v1/queues/41/cancel", "POST", undefined],
      ["https://api.example/api/v1/queues/notifications/8/read", "POST", undefined],
    ]);
    for (const [, init] of fetcher.mock.calls.slice(2)) {
      expect(init?.headers).toMatchObject({ "X-CSRF-Token": "queue-csrf" });
    }
  });

  it("uses the typed public queue endpoints with the exact Q3 payloads", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 5,
        account_type: "user",
        name: "Ali",
        login: "u_ali",
        csrf_token: "queue-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValue(jsonResponse({}));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();
    const body = {
      business_public_id: "b_shifo",
      item_public_id: "s_qabul",
      provider_id: 5,
      queue_date: "2026-08-02",
      slot_time: "09:20",
      note: "",
    };

    await client.getQueueOptions("b_shifo", "s_qabul", "2026-08-02");
    await client.getQueueSlots("b_shifo", "s_qabul", 5, "2026-08-02");
    await client.createQueue(body);

    expect(fetcher.mock.calls.slice(1).map(([url, init]) => [
      url,
      init?.method,
      init?.body,
    ])).toEqual([
      [
        "https://api.example/api/v1/queues/options?business_public_id=b_shifo&item_public_id=s_qabul&queue_date=2026-08-02",
        "GET",
        undefined,
      ],
      [
        "https://api.example/api/v1/queues/slots?business_public_id=b_shifo&item_public_id=s_qabul&provider_id=5&queue_date=2026-08-02",
        "GET",
        undefined,
      ],
      [
        "https://api.example/api/v1/queues",
        "POST",
        JSON.stringify(body),
      ],
    ]);
    expect(fetcher.mock.calls[3]?.[1]?.headers).toMatchObject({
      "X-CSRF-Token": "queue-csrf",
    });
  });

  it("uses the typed business queue endpoints with the exact Q2 payloads", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 7,
        account_type: "business",
        name: "Klinika",
        login: "b_klinika",
        csrf_token: "queue-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValue(jsonResponse([]));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();
    const provider = {
      staff_id: 11,
      item_public_ids: ["s_qabul"],
      specialty: "Kardiolog",
      experience_years: 8,
      qualification: "Oliy toifa",
      work_days: "1,2,3,4,5,6",
      work_start: "08:00",
      work_end: "17:00",
      avg_minutes: 20,
      room: "12-xona",
      bio: "",
      status: "active" as const,
      mode: "live" as const,
    };
    const offline = {
      item_public_id: "s_qabul",
      provider_id: 5,
      queue_date: "2026-08-02",
      patient_name: "Vali",
      phone: "",
      note: "",
      slot_time: "",
    };

    await client.getBusinessQueueSetup();
    await client.getBusinessQueueProviders();
    await client.createBusinessQueueProvider(provider);
    await client.updateBusinessQueueProvider(5, provider);
    await client.getBusinessQueueEntries("2026-08-02");
    await client.createBusinessOfflineQueue(offline);
    await client.changeBusinessQueueStatus(41, "called");
    await client.swapBusinessQueues(41, 42);

    expect(fetcher.mock.calls.slice(1).map(([url, init]) => [
      url,
      init?.method,
      init?.body,
    ])).toEqual([
      ["https://api.example/api/v1/queues/business/setup", "GET", undefined],
      ["https://api.example/api/v1/queues/business/providers", "GET", undefined],
      ["https://api.example/api/v1/queues/business/providers", "POST", JSON.stringify(provider)],
      ["https://api.example/api/v1/queues/business/providers/5", "PUT", JSON.stringify(provider)],
      ["https://api.example/api/v1/queues/business/entries?queue_date=2026-08-02", "GET", undefined],
      ["https://api.example/api/v1/queues/business/entries", "POST", JSON.stringify(offline)],
      ["https://api.example/api/v1/queues/business/entries/41/status", "PUT", JSON.stringify({ status: "called" })],
      ["https://api.example/api/v1/queues/business/entries/41/swap", "POST", JSON.stringify({ other_queue_id: 42 })],
    ]);
    for (const [, init] of fetcher.mock.calls.slice(3)) {
      if (init?.method !== "GET") {
        expect(init?.headers).toMatchObject({ "X-CSRF-Token": "queue-csrf" });
      }
    }
  });

  it("creates an order through the versioned authenticated API", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 5,
        account_type: "user",
        name: "Ali",
        login: "u_ali",
        csrf_token: "order-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValueOnce(jsonResponse({ id: 91 }));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();
    const body = {
      provider_kind: "business" as const,
      provider_public_id: "b_turon",
      items: [{ public_id: "p_non", qty: 3 }],
      listing_public_id: "",
      title: "Buyurtma: Turon savdo",
      phone: "+998901234567",
      order_type: "pickup" as const,
      address: "",
      desired_time: "bugun 18:00",
      delivery_lat: null,
      delivery_lng: null,
      note: "",
    };

    await client.createOrder(body);

    expect(fetcher).toHaveBeenLastCalledWith(
      "https://api.example/api/v1/orders",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(body),
        headers: expect.objectContaining({ "X-CSRF-Token": "order-csrf" }),
      }),
    );
  });

  it("uses the complete authenticated order flow endpoints", async () => {
    const session = {
      account_id: 5,
      account_type: "user",
      name: "Ali",
      login: "u_ali",
      csrf_token: "order-csrf",
      expires_at: "2026-08-27T08:00:00Z",
    };
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse(session))
      .mockResolvedValue(jsonResponse([]));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();

    await client.getMyOrders();
    await client.getOrderInbox();
    await client.markOrderSeen(91);
    await client.changeOrderStatus(91, "accepted");
    await client.submitOrderPayment(91);
    await client.decideOrderPayment(91, "confirmed");
    await client.openOrderProblem(91, { reason: "amount_short", note: "" });
    await client.chooseOrderProblemSolution(91, "new_receipt");
    await client.handoffOrder(91);
    await client.receiveOrder(91);
    await client.getOrderChat(91);
    await client.sendOrderChatMessage(91, { text: "Salom", reply_to_id: null });
    await client.sendOrderChatImage(91, { object_key: "orders/receipt.jpg", file_name: "receipt.jpg" });
    await client.editOrderChatMessage(91, 7, "Yangilandi");
    await client.deleteOrderChatMessage(91, 7);

    expect(fetcher.mock.calls.slice(1).map(([url, init]) => [url, init?.method])).toEqual([
      ["https://api.example/api/v1/orders/my", "GET"],
      ["https://api.example/api/v1/orders/inbox", "GET"],
      ["https://api.example/api/v1/orders/91/seen", "PUT"],
      ["https://api.example/api/v1/orders/91/status", "PUT"],
      ["https://api.example/api/v1/orders/91/payment/submit", "POST"],
      ["https://api.example/api/v1/orders/91/payment", "POST"],
      ["https://api.example/api/v1/orders/91/problem", "POST"],
      ["https://api.example/api/v1/orders/91/problem/solution", "PUT"],
      ["https://api.example/api/v1/orders/91/handoff", "POST"],
      ["https://api.example/api/v1/orders/91/received", "POST"],
      ["https://api.example/api/v1/orders/91/chat", "GET"],
      ["https://api.example/api/v1/orders/91/chat", "POST"],
      ["https://api.example/api/v1/orders/91/chat/image", "POST"],
      ["https://api.example/api/v1/orders/91/chat/7", "PUT"],
      ["https://api.example/api/v1/orders/91/chat/7", "DELETE"],
    ]);
    for (const [, init] of fetcher.mock.calls.slice(3)) {
      if (init?.method !== "GET") {
        expect(init?.headers).toMatchObject({ "X-CSRF-Token": "order-csrf" });
      }
    }
  });

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

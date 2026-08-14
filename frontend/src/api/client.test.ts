import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";


function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}


describe("ApiClient", () => {
  it("uses the typed Taxi and driver endpoints with CSRF on writes", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 7, account_type: "user", name: "Ali", login: "ali",
        csrf_token: "taxi-csrf", expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValue(jsonResponse({}));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();
    const driver = {
      phone: "+998901234567", car_model: "Cobalt", car_color: "oq",
      car_plate: "01 A 123 BC", service: "both" as const,
    };
    const ride = {
      kind: "taxi" as const, from_addr: "A", to_addr: "B",
      from_lat: 41.3, from_lng: 69.2, to_lat: 41.31, to_lng: 69.21,
      dist_km: 3.6, dur_min: 8, ozim: false, cargo: "", car_type: "", note: "",
    };

    await client.getTaxiPricing();
    await client.getTaxiDriver();
    await client.saveTaxiDriver(driver);
    await client.setTaxiDriverAvailable(true);
    await client.createTaxiRide(ride);
    await client.getMyTaxiRides();
    await client.cancelTaxiRide(12);
    await client.getPendingTaxiRides();
    await client.acceptTaxiRide(12);
    await client.setTaxiRideStatus(12, "arrived");
    await client.updateTaxiRideProgress(12, 1.4);

    expect(fetcher.mock.calls.slice(1).map(([url, init]) => [url, init?.method, init?.body]))
      .toEqual([
        ["https://api.example/api/v1/taxi/pricing", "GET", undefined],
        ["https://api.example/api/v1/taxi/driver", "GET", undefined],
        ["https://api.example/api/v1/taxi/driver", "POST", JSON.stringify(driver)],
        ["https://api.example/api/v1/taxi/driver/available", "PUT", JSON.stringify({ available: true })],
        ["https://api.example/api/v1/taxi/rides", "POST", JSON.stringify(ride)],
        ["https://api.example/api/v1/taxi/rides/my", "GET", undefined],
        ["https://api.example/api/v1/taxi/rides/12/cancel", "POST", undefined],
        ["https://api.example/api/v1/taxi/rides/pending", "GET", undefined],
        ["https://api.example/api/v1/taxi/rides/12/accept", "POST", undefined],
        ["https://api.example/api/v1/taxi/rides/12/status", "POST", JSON.stringify({ status: "arrived" })],
        ["https://api.example/api/v1/taxi/rides/12/progress", "POST", JSON.stringify({ km: 1.4 })],
      ]);
    for (const [, init] of fetcher.mock.calls.slice(1)) {
      if (init?.method !== "GET") {
        expect(init?.headers).toMatchObject({ "X-CSRF-Token": "taxi-csrf" });
      }
    }
  });

  it("uses the typed K2-K4 cash register endpoints", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 7,
        account_type: "business",
        name: "Turon",
        login: "b_turon",
        csrf_token: "cash-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValue(jsonResponse({}));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();
    const body = {
      items: [{ catalog_item_id: 20, name: "", qty: 2, price: 300 }],
      pay_type: "naqd" as const,
      note: "",
      sale_date: "2026-08-04",
    };

    await client.getCashRegister("2026-08-04");
    await client.getCashCatalog();
    await client.createCashReceipt(body);
    await client.updateCashOrderPayment(9, "karta");
    await client.deleteCashReceipt(9);

    expect(fetcher.mock.calls.slice(1).map(([url, init]) => [url, init?.method, init?.body]))
      .toEqual([
        ["https://api.example/api/v1/cash-register?day=2026-08-04", "GET", undefined],
        ["https://api.example/api/v1/cash-register/catalog", "GET", undefined],
        ["https://api.example/api/v1/cash-register/receipts", "POST", JSON.stringify(body)],
        ["https://api.example/api/v1/cash-register/receipts/9/payment", "PUT", JSON.stringify({ pay_type: "karta" })],
        ["https://api.example/api/v1/cash-register/receipts/9", "DELETE", undefined],
      ]);
    for (const [, init] of fetcher.mock.calls.slice(3)) {
      expect(init?.headers).toMatchObject({ "X-CSRF-Token": "cash-csrf" });
    }
  });

  it("uses the typed K5 debt ledger and order debt payloads", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 7,
        account_type: "business",
        name: "Turon",
        login: "b_turon",
        csrf_token: "debt-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValue(jsonResponse({}));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();
    const debtor = {
      name: "Vali Karimov",
      phone: "+998901234567",
      note: "",
      due: "",
      initial_debt: 50_000,
    };
    const payment = {
      type: "payment" as const,
      amount: 20_000,
      note: "Qisman to‘lov",
    };

    await client.getDebtors();
    await client.createDebtor(debtor);
    await client.getDebtor(31);
    await client.addDebtTransaction(31, payment);
    await client.updateCashOrderPayment(9, "qarz", 31);
    await client.decideOrderPayment(91, "debt", 31);

    expect(fetcher.mock.calls.slice(1).map(([url, init]) => [
      url,
      init?.method,
      init?.body,
    ])).toEqual([
      ["https://api.example/api/v1/debt-ledger/debtors", "GET", undefined],
      ["https://api.example/api/v1/debt-ledger/debtors", "POST", JSON.stringify(debtor)],
      ["https://api.example/api/v1/debt-ledger/debtors/31", "GET", undefined],
      ["https://api.example/api/v1/debt-ledger/debtors/31/transactions", "POST", JSON.stringify(payment)],
      ["https://api.example/api/v1/cash-register/receipts/9/payment", "PUT", JSON.stringify({ pay_type: "qarz", debtor_id: 31 })],
      ["https://api.example/api/v1/orders/91/payment", "POST", JSON.stringify({ status: "debt", debtor_id: 31 })],
    ]);
    for (const [, init] of fetcher.mock.calls.slice(2)) {
      if (init?.method !== "GET") {
        expect(init?.headers).toMatchObject({ "X-CSRF-Token": "debt-csrf" });
      }
    }
  });

  it("uses the typed K6 expense endpoints", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 7,
        account_type: "business",
        name: "Turon",
        login: "b_turon",
        csrf_token: "expense-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValue(jsonResponse({}));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();
    const category = { name: "Reklama" };
    const expense = { category: "Reklama", amount: 75_000, note: "Banner" };

    await client.getExpenses("2026-08-04");
    await client.getExpenseCategories();
    await client.createExpenseCategory(category);
    await client.createExpense(expense);
    await client.deleteExpense(13);

    expect(fetcher.mock.calls.slice(1).map(([url, init]) => [
      url,
      init?.method,
      init?.body,
    ])).toEqual([
      ["https://api.example/api/v1/expenses?day=2026-08-04", "GET", undefined],
      ["https://api.example/api/v1/expenses/categories", "GET", undefined],
      ["https://api.example/api/v1/expenses/categories", "POST", JSON.stringify(category)],
      ["https://api.example/api/v1/expenses", "POST", JSON.stringify(expense)],
      ["https://api.example/api/v1/expenses/13", "DELETE", undefined],
    ]);
    for (const [, init] of fetcher.mock.calls.slice(3)) {
      expect(init?.headers).toMatchObject({ "X-CSRF-Token": "expense-csrf" });
    }
  });

  it("uses the typed documents and counterparties endpoints", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 7,
        account_type: "business",
        name: "Turon",
        login: "b_turon",
        csrf_token: "documents-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValue(jsonResponse({}));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();
    const counterparty = {
      name: "Olma Savdo",
      ctype: "Mijoz",
      director: "",
      phone: "",
      address: "",
      inn: "309333444",
      account: "",
      bank: "",
      mfo: "",
      note: "",
    };
    const document = {
      direction: "chiquvchi" as const,
      doc_type: "Shartnoma",
      title: "Yetkazib berish",
      number: "7",
      doc_date: "2026-08-10",
      contractor_id: 9,
      body: "Shartnoma matni",
    };

    await client.getDocumentCounterparties();
    await client.createDocumentCounterparty(counterparty);
    await client.updateDocumentCounterparty(9, counterparty);
    await client.deleteDocumentCounterparty(9);
    await client.getDocuments("chiquvchi");
    await client.getDocument(31);
    await client.createDocument(document);
    await client.updateDocument(31, document);
    await client.deleteDocument(31);
    await client.sendDocument(31, "309333444");
    await client.respondDocument(32, "qabul");

    expect(fetcher.mock.calls.slice(1).map(([url, init]) => [
      url,
      init?.method,
      init?.body,
    ])).toEqual([
      ["https://api.example/api/v1/documents/counterparties", "GET", undefined],
      ["https://api.example/api/v1/documents/counterparties", "POST", JSON.stringify(counterparty)],
      ["https://api.example/api/v1/documents/counterparties/9", "PUT", JSON.stringify(counterparty)],
      ["https://api.example/api/v1/documents/counterparties/9", "DELETE", undefined],
      ["https://api.example/api/v1/documents?direction=chiquvchi", "GET", undefined],
      ["https://api.example/api/v1/documents/31", "GET", undefined],
      ["https://api.example/api/v1/documents", "POST", JSON.stringify(document)],
      ["https://api.example/api/v1/documents/31", "PUT", JSON.stringify(document)],
      ["https://api.example/api/v1/documents/31", "DELETE", undefined],
      ["https://api.example/api/v1/documents/31/send", "POST", JSON.stringify({ receiver_inn: "309333444" })],
      ["https://api.example/api/v1/documents/32/respond", "POST", JSON.stringify({ action: "qabul" })],
    ]);
    for (const [, init] of fetcher.mock.calls.slice(2)) {
      if (init?.method !== "GET") {
        expect(init?.headers).toMatchObject({
          "X-CSRF-Token": "documents-csrf",
        });
      }
    }
  });

  it("uses the typed AI assistant endpoints and protects writes with csrf", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 7,
        account_type: "business",
        name: "Turon",
        login: "b_turon",
        csrf_token: "ai-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValue(jsonResponse({}));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    await client.getSession();
    const draft = {
      prompt: "Xizmat shartnomasi yoz",
      contractor_id: 9,
      firm_name: "Turon Savdo",
      director: "Ali Valiyev",
      inn: "309111222",
    };

    await client.getAIChatHistory(30);
    await client.sendAIChatMessage("Bugungi xulosa");
    await client.getAIStatus();
    await client.generateAIDocumentDraft(draft);

    expect(fetcher.mock.calls.slice(1).map(([url, init]) => [
      url,
      init?.method,
      init?.body,
    ])).toEqual([
      ["https://api.example/api/v1/ai-assistant/history?limit=30", "GET", undefined],
      ["https://api.example/api/v1/ai-assistant/chat", "POST", JSON.stringify({ message: "Bugungi xulosa" })],
      ["https://api.example/api/v1/ai-assistant/status", "GET", undefined],
      ["https://api.example/api/v1/ai-assistant/documents/draft", "POST", JSON.stringify(draft)],
    ]);
    expect(fetcher.mock.calls[2]?.[1]?.headers).toMatchObject({
      "X-CSRF-Token": "ai-csrf",
    });
    expect(fetcher.mock.calls[4]?.[1]?.headers).toMatchObject({
      "X-CSRF-Token": "ai-csrf",
    });
  });

  it("uses the typed K8 statistics report and navigation endpoints", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({}));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });

    await client.getStatistics("chorak", "2026-08-04");
    await client.getStatisticsNav("chorak", -1, "2026-08-04");

    expect(fetcher.mock.calls.map(([url, init]) => [url, init?.method]))
      .toEqual([
        [
          "https://api.example/api/v1/statistics"
            + "?period=chorak&anchor=2026-08-04",
          "GET",
        ],
        [
          "https://api.example/api/v1/statistics/nav"
            + "?period=chorak&dir=-1&anchor=2026-08-04",
          "GET",
        ],
      ]);
  });

  it("uses the typed K9 education statistics endpoint", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({}));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });

    await client.getEducationStatistics("year", "2026-08-04");

    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example/api/v1/education/statistics"
        + "?period=year&date=2026-08-04",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("uses secure staff login and the live staff management endpoints", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 7,
        account_type: "business",
        name: "Ali Valiyev",
        login: "ali01",
        csrf_token: "staff-csrf",
        expires_at: "2026-08-27T08:00:00Z",
        actor_type: "staff",
        staff_id: 11,
        permissions: ["kassa"],
      }))
      .mockResolvedValue(jsonResponse({}));
    const client = new ApiClient("https://api.example", fetcher, { kind: "web" });
    const credentials = {
      firm_login: "b_turon",
      login: "ali01",
      password: "safe-pass-42",
    };
    const member = {
      name: "Vali Karimov",
      profession: "Kassir",
      phone: "",
      salary: 0,
      hire_date: null,
      note: "",
    };

    await client.loginStaff(credentials);
    await client.getStaffSetup();
    await client.createStaffMember(member);
    await client.updateStaffAccess(11, {
      can_login: true,
      login: "vali01",
      password: "new-pass-42",
      permissions: ["kassa"],
    });
    await client.getStaffAttendance("2026-08-03");

    expect(fetcher.mock.calls.map(([url, init]) => [url, init?.method])).toEqual([
      ["https://api.example/api/v1/staff-auth/login", "POST"],
      ["https://api.example/api/v1/staff", "GET"],
      ["https://api.example/api/v1/staff", "POST"],
      ["https://api.example/api/v1/staff/11/access", "PUT"],
      ["https://api.example/api/v1/staff/attendance?day=2026-08-03", "GET"],
    ]);
    expect(fetcher.mock.calls[0]?.[1]?.body).toBe(JSON.stringify(credentials));
    expect(fetcher.mock.calls[2]?.[1]?.headers).toMatchObject({
      "X-CSRF-Token": "staff-csrf",
    });
    expect(fetcher.mock.calls[3]?.[1]?.headers).toMatchObject({
      "X-CSRF-Token": "staff-csrf",
    });
  });

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
        public_id: "u_1234567890abcdef",
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
        avatar_url: "",
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

  it("loads typed followers and following lists with the current session", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({ items: [], count: 0 }));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getFollowers();
    await client.getFollowing();

    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
      "https://api.example/api/v1/follows/followers",
      "https://api.example/api/v1/follows/following",
    ]);
    expect(fetcher.mock.calls[0]?.[1]).toMatchObject({
      method: "GET",
      credentials: "include",
    });
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

  it("uses the typed K23 subscription and payment history endpoints", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({}));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getBusinessSubscription();
    await client.getMyPayments();

    expect(fetcher.mock.calls.map(([url, init]) => [url, init?.method]))
      .toEqual([
        ["https://api.example/api/v1/payments/subscription", "GET"],
        ["https://api.example/api/v1/payments/my", "GET"],
      ]);
  });

  it("uses the typed K24 warehouse endpoints", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({}));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );

    await client.getWarehouseItems();
    await client.getWarehouseMoves(7);
    await client.getWarehouseRecipe(7);
    await client.getWarehouseProduction(25);

    expect(fetcher.mock.calls.map(([url, init]) => [url, init?.method]))
      .toEqual([
        ["https://api.example/api/v1/warehouse/items", "GET"],
        ["https://api.example/api/v1/warehouse/items/7/moves", "GET"],
        ["https://api.example/api/v1/warehouse/items/7/recipe", "GET"],
        ["https://api.example/api/v1/warehouse/production?limit=25", "GET"],
      ]);
  });

  it("opens a v1656 business through the typed CSRF-protected endpoint", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        account_id: 5,
        account_type: "user",
        name: "Ali",
        login: "u_ali",
        csrf_token: "opening-csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }))
      .mockResolvedValueOnce(jsonResponse({
        ok: true,
        business_account_id: 17,
        biz_login: "b_turon",
        biz_password: "maxfiy-parol",
      }));
    const client = new ApiClient(
      "https://api.example",
      fetcher,
      { kind: "web" },
    );
    const body = {
      name: "Turon do‘koni",
      direction: "Savdo",
      activity_type: "Oziq-ovqat do'koni",
      phone: "+998 90 111 22 33",
      address: "Qumqo‘rg‘on",
    };

    await client.getSession();
    await client.openBusiness(body);

    expect(fetcher).toHaveBeenLastCalledWith(
      "https://api.example/api/v1/business-opening",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(body),
        headers: expect.objectContaining({
          "X-CSRF-Token": "opening-csrf",
        }),
      }),
    );
  });
});

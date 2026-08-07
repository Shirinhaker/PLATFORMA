import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminApiClient, AdminApiError } from "./admin-client";


/** Brauzerdagi `fetch` ni taqlid qiladi.
 *
 * Haqiqiy brauzer `fetch` ni `window` dan ajratib chaqirsa
 * "Illegal invocation" bilan rad etadi. Node'da bunday himoya yo'q,
 * shuning uchun uni shu yerda qo'lda qo'yamiz — aks holda bu xato
 * faqat productionda ko'rinadi.
 */
function installWindowBoundFetch(response: unknown, status = 200) {
  const calls: Array<[string, RequestInit | undefined]> = [];
  const guarded = function (
    this: unknown,
    url: string,
    init?: RequestInit,
  ) {
    if (this !== globalThis) {
      throw new TypeError(
        "Failed to execute 'fetch' on 'Window': Illegal invocation",
      );
    }
    calls.push([url, init]);
    return Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      json: async () => response,
    } as Response);
  };
  vi.stubGlobal("fetch", guarded);
  return calls;
}


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("admin API klienti", () => {
  it("fetch window bilan chaqiriladi (Illegal invocation bo'lmaydi)", async () => {
    const calls = installWindowBoundFetch({ telegram_user_id: 42 });

    // Fetcher berilmaydi — standart yo'l tekshiriladi.
    const api = new AdminApiClient("https://api.test");
    const identity = await api.me();

    expect(identity).toEqual({ telegram_user_id: 42 });
    expect(calls).toHaveLength(1);
    expect(calls[0]![0]).toBe("https://api.test/api/v1/admin/auth/me");
  });

  it("har bir so'rov admin cookie'sini olib boradi", async () => {
    const calls = installWindowBoundFetch({ telegram_user_id: 42 });

    await new AdminApiClient("https://api.test").me();

    expect(calls[0]![1]?.credentials).toBe("include");
  });

  it("oxiridagi qiya chiziq ikkilanmaydi", async () => {
    const calls = installWindowBoundFetch([]);

    await new AdminApiClient("https://api.test///").payments("", "");

    expect(calls[0]![0]).toBe("https://api.test/api/v1/admin/payments");
  });

  it("filtrlar so'rov satriga tushadi", async () => {
    const calls = installWindowBoundFetch([]);

    await new AdminApiClient("https://api.test").payments(
      "pending", "subscription",
    );

    expect(calls[0]![0]).toBe(
      "https://api.test/api/v1/admin/payments"
      + "?status=pending&service_type=subscription",
    );
  });

  it("server xabari xatoga o'tkaziladi", async () => {
    installWindowBoundFetch(
      { code: "admin_session_required", message: "Admin sessiyasi topilmadi." },
      401,
    );

    const api = new AdminApiClient("https://api.test");
    await expect(api.me()).rejects.toThrow("Admin sessiyasi topilmadi.");
    await expect(api.me()).rejects.toBeInstanceOf(AdminApiError);
  });

  it("CSV havolasi to'liq manzil qaytaradi", () => {
    installWindowBoundFetch([]);
    const api = new AdminApiClient("https://api.test");

    expect(api.auditExportUrl("")).toBe(
      "https://api.test/api/v1/admin/audit/export.csv",
    );
    expect(api.auditExportUrl("payment.approve")).toBe(
      "https://api.test/api/v1/admin/audit/export.csv?action=payment.approve",
    );
  });
});

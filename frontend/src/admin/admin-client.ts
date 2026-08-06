/** Admin paneli API klienti.

Oddiy foydalanuvchi klientidan alohida: admin sessiyasi o'z HttpOnly
cookie'sida turadi va bu kod hech qachon foydalanuvchi endpointlariga
murojaat qilmaydi.
*/

export type AdminIdentity = { telegram_user_id: number };

export type AdminAuthStarted = {
  challenge_id: number;
  expires_in: number;
};

export type AdminPaymentRow = {
  id: number;
  request_code: string;
  actor_type: string;
  account_id: number;
  account_login: string;
  service_type: string;
  plan_code: string;
  duration_months: number;
  quantity: number;
  amount: number;
  currency: string;
  price_code: string;
  status: string;
  public_reason: string;
  reviewed_by_admin_tg_id: number | null;
  created_at: number;
  updated_at: number;
};

export type AdminPaymentAttempt = {
  attempt_no: number;
  review_status: string;
  review_reason: string;
  submitted_at: number;
  receipt_mime: string;
  receipt_sha256: string;
  has_receipt: boolean;
};

export type AdminPaymentDetail = AdminPaymentRow & {
  target_id: number | null;
  payment_method_id: number;
  payment_method_name: string;
  internal_note: string;
  approved_at: number;
  rejected_at: number;
  cancelled_at: number;
  attempts: AdminPaymentAttempt[];
};

export type AdminReceiptLink = {
  url: string;
  mime: string;
  expires_in: number;
};

export type AdminPriceRow = {
  id: number;
  price_code: string;
  service_type: string;
  amount_uzs: number;
  config: Record<string, unknown>;
  active: boolean;
  updated_at: number;
};

export type AdminMethodRow = {
  id: number;
  method_type: string;
  name: string;
  recipient_name: string;
  instructions: string;
  details: Record<string, unknown>;
  sort_order: number;
  active: boolean;
};

export type AdminMethodWrite = Omit<AdminMethodRow, "id">;

export type AdminDecision = {
  reason: string;
  internal_note: string;
};

type Fetcher = typeof fetch;


export class AdminApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: Fetcher;

  constructor(baseUrl: string, fetcher?: Fetcher) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    // `fetch` obyekt maydonida saqlanganda `this` klient nusxasiga
    // bog'lanadi va brauzer "Illegal invocation" bilan rad etadi.
    // Shu sababli bog'lanish shu yerda qilinadi, chaqiruvchiga
    // qoldirilmaydi.
    this.fetcher = fetcher ?? globalThis.fetch.bind(globalThis);
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      method,
      credentials: "include",
      headers: body === undefined
        ? {}
        : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (response.status === 204) return undefined as T;
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const message = payload && typeof payload === "object"
        && "message" in payload
        ? String((payload as { message: unknown }).message)
        : "So‘rov bajarilmadi.";
      throw new AdminApiError(message, response.status);
    }
    return payload as T;
  }

  startLogin(telegramUserId: number): Promise<AdminAuthStarted> {
    return this.request("POST", "/api/v1/admin/auth/start", {
      telegram_user_id: telegramUserId,
    });
  }

  verifyLogin(challengeId: number, code: string): Promise<AdminIdentity> {
    return this.request("POST", "/api/v1/admin/auth/verify", {
      challenge_id: challengeId,
      code,
    });
  }

  me(): Promise<AdminIdentity> {
    return this.request("GET", "/api/v1/admin/auth/me");
  }

  logout(): Promise<void> {
    return this.request("POST", "/api/v1/admin/auth/logout");
  }

  payments(
    status: string,
    serviceType: string,
  ): Promise<AdminPaymentRow[]> {
    const query = new URLSearchParams();
    if (status) query.set("status", status);
    if (serviceType) query.set("service_type", serviceType);
    const suffix = query.toString() ? `?${query}` : "";
    return this.request("GET", `/api/v1/admin/payments${suffix}`);
  }

  payment(paymentId: number): Promise<AdminPaymentDetail> {
    return this.request("GET", `/api/v1/admin/payments/${paymentId}`);
  }

  receipt(paymentId: number): Promise<AdminReceiptLink> {
    return this.request("GET", `/api/v1/admin/payments/${paymentId}/receipt`);
  }

  decide(
    paymentId: number,
    decision: "approve" | "reject" | "cancel",
    body: AdminDecision,
  ): Promise<unknown> {
    return this.request(
      "POST",
      `/api/v1/admin/payments/${paymentId}/${decision}`,
      body,
    );
  }

  prices(): Promise<AdminPriceRow[]> {
    return this.request("GET", "/api/v1/admin/prices");
  }

  updatePrice(
    priceId: number,
    body: { amount_uzs: number; active: boolean },
  ): Promise<AdminPriceRow> {
    return this.request("PUT", `/api/v1/admin/prices/${priceId}`, body);
  }

  methods(): Promise<AdminMethodRow[]> {
    return this.request("GET", "/api/v1/admin/payment-methods");
  }

  createMethod(body: AdminMethodWrite): Promise<AdminMethodRow> {
    return this.request("POST", "/api/v1/admin/payment-methods", body);
  }

  updateMethod(
    methodId: number,
    body: AdminMethodWrite,
  ): Promise<AdminMethodRow> {
    return this.request(
      "PUT", `/api/v1/admin/payment-methods/${methodId}`, body,
    );
  }
}


export class AdminApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "AdminApiError";
    this.status = status;
  }
}

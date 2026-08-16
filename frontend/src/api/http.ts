import type { AuthContext } from "../auth/adapter";
import type { ApiErrorBody } from "./types";

export class ApiClientError extends Error {
  readonly code: string;
  readonly requestId: string;

  constructor(
    readonly status: number,
    body: ApiErrorBody,
  ) {
    super(body.message);
    this.name = "ApiClientError";
    this.code = body.code;
    this.requestId = body.request_id;
  }
}

export class ApiTransport {
  private csrfToken = "";

  constructor(
    private readonly baseUrl: string,
    private readonly fetcher: typeof fetch,
    private readonly auth: AuthContext,
  ) {}

  clearCsrfToken() {
    this.csrfToken = "";
  }

  async uploadFile(
    url: string,
    method: string,
    headers: Record<string, string>,
    file: File,
  ): Promise<void> {
    const response = await this.fetcher(url, {
      method,
      credentials: "omit",
      headers,
      body: file,
    });
    if (!response.ok) throw new Error("Rasm obyekt saqlash xizmatiga yuklanmadi.");
  }

  async request<T>(
    method: string,
    path: string,
    body?: unknown,
    authenticated = false,
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (this.auth.kind === "telegram") {
      headers["X-Telegram-Init-Data"] = this.auth.initData;
    }
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (authenticated && method !== "GET") {
      if (!this.csrfToken) {
        throw new ApiClientError(403, {
          code: "csrf_unavailable",
          message: "Sessiya xavfsizlik ma’lumoti topilmadi.",
          request_id: "",
        });
      }
      headers["X-CSRF-Token"] = this.csrfToken;
    }

    const response = await this.fetcher(`${this.baseUrl.replace(/\/+$/, "")}${path}`, {
      method,
      credentials: "include",
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (response.status === 204) return undefined as T;

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (!response.ok) {
      const fallback: ApiErrorBody = {
        code: "http_error",
        message: `API xatosi: ${response.status}`,
        request_id: "",
      };
      const error =
        payload && typeof payload === "object"
          ? ({ ...fallback, ...payload } as ApiErrorBody)
          : fallback;
      throw new ApiClientError(response.status, error);
    }
    if (
      payload &&
      typeof payload === "object" &&
      "csrf_token" in payload &&
      typeof payload.csrf_token === "string"
    ) {
      this.csrfToken = payload.csrf_token;
    }
    return payload as T;
  }
}

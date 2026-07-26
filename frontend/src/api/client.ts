import type { AuthContext } from "../auth/adapter";

export type BuildInfo = {
  api_version: "v1";
  foundation: "phase1";
  legacy_build: "v1656";
};

export class ApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly fetcher: typeof fetch,
    private readonly auth: AuthContext,
  ) {}

  async getBuild(): Promise<BuildInfo> {
    const headers: Record<string, string> = {
      Accept: "application/json",
    };
    if (this.auth.kind === "telegram") {
      headers["X-Telegram-Init-Data"] = this.auth.initData;
    }
    const response = await this.fetcher(
      `${this.baseUrl}/api/v1/build`,
      { credentials: "include", headers },
    );
    if (!response.ok) {
      throw new Error(`API xatosi: ${response.status}`);
    }
    return response.json() as Promise<BuildInfo>;
  }
}

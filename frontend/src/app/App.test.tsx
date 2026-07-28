import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";


describe("App", () => {
  it("keeps the authenticated business profile under the cabinet action", async () => {
    const api = {
      getSession: vi.fn().mockResolvedValue({
        account_id: 7,
        account_type: "business",
        name: "Turon",
        login: "b_turon",
        csrf_token: "csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }),
    };

    render(<App api={api} />);

    expect(
      await screen.findByRole("heading", { name: "Biznes kabinet" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kabinet" }))
      .toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kirish" }))
      .not.toBeInTheDocument();
  });

  it("shows one guest login action inside the v1656 shell", async () => {
    const api = {
      getSession: vi.fn().mockRejectedValue(
        Object.assign(new Error("unauthorized"), { status: 401 }),
      ),
      startRegistration: vi.fn(),
      startLogin: vi.fn(),
      verifyRegistration: vi.fn(),
      verifyLogin: vi.fn(),
      resendChallenge: vi.fn(),
    };

    render(<App api={api} />);

    expect(await screen.findByRole("banner")).toHaveTextContent("Koprik");
    expect(
      screen.getByRole("heading", { name: "Koprik’ga kirish" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Kirish")).toHaveLength(2);
  });

  it("shows a retryable Uzbek error for network failures", async () => {
    const api = {
      getSession: vi.fn().mockRejectedValue(new TypeError("offline")),
    };
    render(<App api={api} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Server bilan bog‘lanib bo‘lmadi.",
    );
    expect(screen.getByRole("button", { name: "Qayta urinish" }))
      .toBeInTheDocument();
  });
});

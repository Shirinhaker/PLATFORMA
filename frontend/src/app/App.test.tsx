import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";


describe("App", () => {
  it("shows the business cabinet after session restoration", async () => {
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
    expect(screen.getByRole("banner")).toHaveTextContent("Koprik");
    expect(
      await screen.findByRole("heading", { name: "Biznes kabinet" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Oddiy kabinet" }),
    ).not.toBeInTheDocument();
  });

  it("maps an expired session to guest state", async () => {
    const api = {
      getSession: vi.fn().mockRejectedValue(
        Object.assign(new Error("unauthorized"), { status: 401 }),
      ),
    };
    render(<App api={api} />);
    expect(
      await screen.findByRole("heading", { name: "Koprik’ga kirish" }),
    ).toBeInTheDocument();
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

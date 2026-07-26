import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";


describe("App", () => {
  it("shows the foundation build without replacing v1656 production UI", async () => {
    const api = {
      getBuild: vi.fn().mockResolvedValue({
        api_version: "v1",
        foundation: "phase1",
        legacy_build: "v1656",
      } as const),
    };
    render(<App api={api} />);
    expect(screen.getByRole("banner")).toHaveTextContent("Koprik");
    expect(
      await screen.findByText("Koprik yangi platforma foundation’i tayyor"),
    ).toBeInTheDocument();
    expect(screen.getByText("Eski faol BUILD: v1656")).toBeInTheDocument();
    expect(screen.getByText("API v1")).toBeInTheDocument();
    expect(screen.getByText("Phase 1")).toBeInTheDocument();
    expect(
      screen.getByText(/Mavjud production UI va jarayonlar/),
    ).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";


describe("AppShell", () => {
  it("shows the Koprik brand and a working login action for guests", async () => {
    const onLogin = vi.fn();
    render(
      <AppShell authenticated={false} onLogin={onLogin}>
        <p>Kontent</p>
      </AppShell>,
    );

    expect(screen.getByRole("banner")).toHaveTextContent("Koprik");
    await userEvent.click(screen.getByRole("button", { name: "Kirish" }));
    expect(onLogin).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Kabinet" }))
      .not.toBeInTheDocument();
  });

  it("shows the cabinet action only for authenticated sessions", async () => {
    const onCabinet = vi.fn();
    render(
      <AppShell authenticated onCabinet={onCabinet}>
        <p>Kontent</p>
      </AppShell>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Kabinet" }));
    expect(onCabinet).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Kirish" }))
      .not.toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";


describe("AppShell", () => {
  it("connects public shell actions for guests", async () => {
    const onHome = vi.fn();
    const onLocation = vi.fn();
    const onAccount = vi.fn();
    render(
      <AppShell
        authenticated={false}
        isHome
        onHome={onHome}
        onLocation={onLocation}
        onAccount={onAccount}
        onBack={vi.fn()}
      >
        <p>Kontent</p>
      </AppShell>,
    );

    expect(screen.getByRole("banner")).toHaveTextContent("Koprik");
    await userEvent.click(screen.getByRole("button", { name: "Koprik" }));
    await userEvent.click(screen.getByRole("button", { name: "Manzil" }));
    await userEvent.click(screen.getByRole("button", { name: "Kirish" }));

    expect(onHome).toHaveBeenCalledOnce();
    expect(onLocation).toHaveBeenCalledOnce();
    expect(onAccount).toHaveBeenCalledOnce();
  });

  it("connects subview back and authenticated cabinet actions", async () => {
    const onBack = vi.fn();
    const onAccount = vi.fn();
    render(
      <AppShell
        authenticated
        isHome={false}
        title="Katalog"
        onHome={vi.fn()}
        onLocation={vi.fn()}
        onAccount={onAccount}
        onBack={onBack}
      >
        <p>Kontent</p>
      </AppShell>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Orqaga" }));
    await userEvent.click(screen.getByRole("button", { name: "Kabinet" }));

    expect(onBack).toHaveBeenCalledOnce();
    expect(onAccount).toHaveBeenCalledOnce();
  });
});

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
    await userEvent.click(
      screen.getByRole("button", { name: "Koprik bosh sahifasi" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Manzilim" }));
    await userEvent.click(screen.getByRole("button", { name: "Kabinet" }));

    expect(onHome).toHaveBeenCalledOnce();
    expect(onLocation).toHaveBeenCalledOnce();
    expect(onAccount).toHaveBeenCalledOnce();
  });

  it("shows only the v1656 back/title bar on public subviews", async () => {
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

    expect(onBack).toHaveBeenCalledOnce();
    expect(document.querySelector(".tb-title")).toHaveTextContent("Katalog");
    expect(screen.queryByRole("button", { name: "Kabinet" }))
      .not.toBeInTheDocument();
    expect(onAccount).not.toHaveBeenCalled();
  });

  it("connects the authenticated cabinet action on Home", async () => {
    const onAccount = vi.fn();
    render(
      <AppShell
        authenticated
        isHome
        onHome={vi.fn()}
        onLocation={vi.fn()}
        onAccount={onAccount}
        onBack={vi.fn()}
      >
        <p>Kontent</p>
      </AppShell>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Kabinet" }));

    expect(onAccount).toHaveBeenCalledOnce();
  });
});

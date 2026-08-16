import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AccountSettingsV1656 } from "./AccountSettings";

const businessIdentity = {
  account_id: 7,
  account_type: "business" as const,
  name: "Turon",
  login: "turondokon",
  csrf_token: "csrf",
  expires_at: "2026-08-27T08:00:00Z",
};

describe("AccountSettingsV1656", () => {
  it("keeps the exact v1656 settings rows and routes their actions", async () => {
    const user = userEvent.setup();
    const onNotifications = vi.fn();
    const onLogout = vi.fn();
    render(
      <AccountSettingsV1656
        api={{}}
        identity={businessIdentity}
        onBack={vi.fn()}
        onNotifications={onNotifications}
        onLogout={onLogout}
      />,
    );

    expect(screen.getByRole("button", { name: /Login va parol/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Til — O'zbekcha/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Bildirishnomalar/ }));
    expect(onNotifications).toHaveBeenCalledOnce();
    await user.click(screen.getByRole("button", { name: /Tizimdan chiqish/ }));
    expect(onLogout).toHaveBeenCalledOnce();
  });

  it("loads and safely updates the business login and password", async () => {
    const user = userEvent.setup();
    const updateBusinessCredentials = vi.fn().mockResolvedValue({
      ok: true,
      login: "yangi_login",
    });
    render(
      <AccountSettingsV1656
        api={{
          getBusinessCredentials: vi.fn().mockResolvedValue({
            ok: true,
            login: "turondokon",
          }),
          updateBusinessCredentials,
        }}
        identity={businessIdentity}
        onBack={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Login va parol/ }));
    expect(await screen.findByText("turondokon")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Yangi login/), "Yangi-Login");
    await user.type(screen.getByLabelText(/^Yangi parol$/), "parol123");
    await user.type(screen.getByLabelText(/Yangi parolni takrorlang/), "boshqa");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Parollar mos kelmadi.");

    await user.clear(screen.getByLabelText(/Yangi parolni takrorlang/));
    await user.type(screen.getByLabelText(/Yangi parolni takrorlang/), "parol123");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    await waitFor(() =>
      expect(updateBusinessCredentials).toHaveBeenCalledWith({
        new_login: "yangilogin",
        new_password: "parol123",
      }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("Saqlandi ✅");
    expect(screen.getByText("yangi_login")).toBeInTheDocument();
  });

  it("renders the v1656 FAQ as accessible expandable answers", async () => {
    const user = userEvent.setup();
    render(
      <AccountSettingsV1656
        api={{}}
        identity={businessIdentity}
        onBack={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Yordam/ }));
    const question = screen.getByRole("button", {
      name: /Do'konimni qanday ochaman\?/,
    });
    expect(question).toHaveAttribute("aria-expanded", "false");
    await user.click(question);
    expect(question).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/Biznes ochish/)).toBeInTheDocument();
  });

  it("keeps business credentials owner-only for ordinary users", async () => {
    const user = userEvent.setup();
    render(
      <AccountSettingsV1656
        api={{}}
        identity={{ ...businessIdentity, account_type: "user" }}
        onBack={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Login va parol/ }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Bu bo'lim do'kon egalari uchun.",
    );
    expect(screen.getByRole("button", { name: "Saqlash" })).toBeDisabled();
  });
});

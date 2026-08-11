import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LoginForm } from "./LoginForm";


describe("shared-login cabinet selection", () => {
  it("asks for cabinet type only when the API reports an ambiguous login", async () => {
    const user = userEvent.setup();
    const ambiguous = Object.assign(
      new Error("Oddiy yoki biznes kabinetini tanlang."),
      { code: "account_type_required" },
    );
    const startLogin = vi.fn()
      .mockRejectedValueOnce(ambiguous)
      .mockResolvedValueOnce({
        request_id: 18,
        deep_link: "https://t.me/koprik_bot?start=shared",
        code_sent: false,
        expires_in: 600,
        resend_after: 60,
      });
    const api = { startLogin } as never;

    render(<LoginForm api={api} onStarted={vi.fn()} onStaff={vi.fn()} onRegister={vi.fn()} />);

    expect(screen.queryByLabelText("Kabinet turi")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Login"), "shared_owner");
    await user.type(screen.getByLabelText("Parol"), "secret-42");
    await user.click(screen.getByRole("button", {
      name: "Telegram orqali tasdiqlash",
    }));

    expect(await screen.findByLabelText("Kabinet turi")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Kabinet turi"), "business");
    await user.click(screen.getByRole("button", {
      name: "Telegram orqali tasdiqlash",
    }));

    expect(startLogin).toHaveBeenNthCalledWith(1, {
      login: "shared_owner",
      password: "secret-42",
    });
    expect(startLogin).toHaveBeenNthCalledWith(2, {
      login: "shared_owner",
      password: "secret-42",
      cabinet_type: "business",
    });
  });
});

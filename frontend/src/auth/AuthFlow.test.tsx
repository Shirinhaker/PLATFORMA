import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthFlow } from "./AuthFlow";
import { TelegramCodeForm } from "./TelegramCodeForm";


function authApi() {
  return {
    startRegistration: vi.fn().mockResolvedValue({
      request_id: 12,
      deep_link: "https://t.me/koprik_bot?start=token",
      expires_in: 600,
      resend_after: 60,
    }),
    startLogin: vi.fn().mockResolvedValue({
      request_id: 13,
      deep_link: "https://t.me/koprik_bot?start=login-token",
      code_sent: true,
      expires_in: 300,
      resend_after: 60,
    }),
    verifyRegistration: vi.fn().mockResolvedValue({
      account_id: 9,
      account_type: "user",
      csrf_token: "csrf",
      expires_at: "2026-08-27T08:00:00Z",
      login: "u_test",
      password: "generated-pass",
    }),
    verifyLogin: vi.fn().mockResolvedValue({
      account_id: 7,
      account_type: "business",
      csrf_token: "csrf",
      expires_at: "2026-08-27T08:00:00Z",
    }),
    resendChallenge: vi.fn().mockResolvedValue({
      request_id: 12,
      code_version: 2,
      expires_in: 300,
      resend_after: 60,
    }),
    getSession: vi.fn().mockResolvedValue({
      account_id: 9,
      account_type: "user",
      name: "Test",
      login: "u_test",
      csrf_token: "csrf",
      expires_at: "2026-08-27T08:00:00Z",
    }),
  };
}


describe("AuthFlow", () => {
  it("registers a separate business account through telegram code", async () => {
    const user = userEvent.setup();
    const api = authApi();
    render(<AuthFlow api={api} onAuthenticated={vi.fn()} />);

    await user.click(
      screen.getByRole("button", { name: "Ro‘yxatdan o‘tish" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Biznes akkaunt" }),
    );
    await user.type(screen.getByLabelText("Biznes nomi"), "Turon Savdo");
    await user.click(
      screen.getByRole(
        "button",
        { name: "Telegram orqali tasdiqlash" },
      ),
    );

    expect(api.startRegistration).toHaveBeenCalledWith(
      expect.objectContaining({
        account_type: "business",
        name: "Turon Savdo",
      }),
    );
    expect(await screen.findByLabelText("6 xonali kod"))
      .toBeInTheDocument();
  });

  it("logs in without asking for account type", async () => {
    const user = userEvent.setup();
    const api = authApi();
    render(<AuthFlow api={api} onAuthenticated={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Kirish" }));
    await user.type(screen.getByLabelText("Login"), "b_turon");
    await user.type(screen.getByLabelText("Parol"), "secret-42");
    await user.click(screen.getByRole("button", { name: "Davom etish" }));

    expect(api.startLogin).toHaveBeenCalledWith({
      login: "b_turon",
      password: "secret-42",
    });
    expect(screen.queryByText("Akkaunt turini tanlang"))
      .not.toBeInTheDocument();
  });

  it("shows generated credentials once after registration", async () => {
    const user = userEvent.setup();
    const api = authApi();
    const onAuthenticated = vi.fn();
    render(
      <TelegramCodeForm
        api={api}
        purpose="register"
        requestId={12}
        deepLink="https://t.me/koprik_bot?start=token"
        codeSent={false}
        resendAfter={0}
        onAuthenticated={onAuthenticated}
      />,
    );

    await user.type(screen.getByLabelText("6 xonali kod"), "123456");
    await user.click(screen.getByRole("button", { name: "Tasdiqlash" }));

    expect(await screen.findByText("u_test")).toBeInTheDocument();
    expect(screen.getByText("generated-pass")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Kabinetga kirish" }),
    );
    expect(onAuthenticated).toHaveBeenCalledTimes(1);
  });
});

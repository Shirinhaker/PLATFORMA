import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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


describe("AuthFlow v1656 parity", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.spyOn(window, "open").mockReturnValue(null);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("opens directly on the exact v1656 login screen", () => {
    render(
      <AuthFlow
        api={authApi()}
        onAuthenticated={vi.fn()}
        reason="Navbat olish"
      />,
    );

    expect(screen.getByRole("heading", { name: "Kabinetga kirish" }))
      .toBeInTheDocument();
    expect(screen.getByText(
      "Ro'yxatdan o'tganda berilgan login va parolni kiriting.",
    )).toBeInTheDocument();
    expect(screen.getByText(
      "🔒 Navbat olish uchun tizimga kiring yoki ro'yxatdan o'ting.",
    )).toHaveAttribute("id", "loginReason");
    expect(screen.getByPlaceholderText("Login")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Parol")).toBeInTheDocument();
    expect(screen.queryByLabelText("Kabinet turi")).not.toBeInTheDocument();
  });

  it("logs in without asking for an account type and opens Telegram", async () => {
    const user = userEvent.setup();
    const api = authApi();
    render(<AuthFlow api={api} onAuthenticated={vi.fn()} />);

    await user.type(screen.getByLabelText("Login"), "b_turon");
    await user.type(screen.getByLabelText("Parol"), "secret-42");
    await user.click(screen.getByRole("button", {
      name: "Telegram orqali tasdiqlash",
    }));

    expect(api.startLogin).toHaveBeenCalledWith({
      login: "b_turon",
      password: "secret-42",
    });
    expect(window.open).toHaveBeenCalledWith(
      "https://t.me/koprik_bot?start=login-token",
      "_blank",
    );
    expect(await screen.findByLabelText("Tasdiqlash kodi"))
      .toHaveAttribute("placeholder", "000000");
    expect(screen.getByRole("button", { name: "Tasdiqlash va kirish" }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "✈️ Telegramni ochish" }))
      .toBeInTheDocument();
  });

  it("shows the exact role cards and all twenty v1656 directions", async () => {
    const user = userEvent.setup();
    render(<AuthFlow api={authApi()} onAuthenticated={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Ro'yxatdan o'tish" }));
    expect(screen.getByText("Kim sifatida ro'yxatdan o'tmoqchisiz?"))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Biznes Mahsulot/ }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Oddiy foydalanuvchi Bizneslarni/ }))
      .toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Biznes Mahsulot/ }));
    expect(screen.getByRole("heading", { name: "Biznes ro'yxati" }))
      .toBeInTheDocument();
    const directions = screen.getByLabelText("Faoliyat yo'nalishi");
    expect(within(directions).getAllByRole("option")).toHaveLength(21);
    expect(within(directions).getByRole("option", { name: "🛒 Savdo" }))
      .toBeInTheDocument();
    expect(within(directions).getByRole("option", { name: "🚢 Import-eksport" }))
      .toBeInTheDocument();
  });

  it("preserves registration fields when returning from Telegram code", async () => {
    const user = userEvent.setup();
    const api = authApi();
    render(<AuthFlow api={api} onAuthenticated={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Ro'yxatdan o'tish" }));
    await user.click(screen.getByRole("button", { name: /Biznes Mahsulot/ }));
    await user.type(screen.getByLabelText("Biznes nomi"), "Turon Savdo");
    await user.selectOptions(screen.getByLabelText("Faoliyat yo'nalishi"), "Savdo");
    await user.type(screen.getByLabelText("Manzil"), "Qumqo'rg'on");
    await user.type(screen.getByLabelText("Telefon raqami — ixtiyoriy"), "+998901234567");
    await user.click(screen.getByRole("button", {
      name: "✈️ Telegram orqali kod olish",
    }));

    expect(api.startRegistration).toHaveBeenCalledWith({
      account_type: "business",
      name: "Turon Savdo",
      phone: "+998901234567",
      direction: "Savdo",
      address: "Qumqo'rg'on",
    });
    await user.click(screen.getByRole("button", {
      name: "Ma'lumotlarni o'zgartirish",
    }));
    expect(screen.getByLabelText("Biznes nomi")).toHaveValue("Turon Savdo");
    expect(screen.getByLabelText("Faoliyat yo'nalishi")).toHaveValue("Savdo");
    expect(screen.getByLabelText("Manzil")).toHaveValue("Qumqo'rg'on");
  });

  it("restores a live Telegram challenge after the flow remounts", async () => {
    const user = userEvent.setup();
    const api = authApi();
    const first = render(<AuthFlow api={api} onAuthenticated={vi.fn()} />);
    await user.type(screen.getByLabelText("Login"), "b_turon");
    await user.type(screen.getByLabelText("Parol"), "secret-42");
    await user.click(screen.getByRole("button", {
      name: "Telegram orqali tasdiqlash",
    }));
    await screen.findByLabelText("Tasdiqlash kodi");

    first.unmount();
    render(<AuthFlow api={api} onAuthenticated={vi.fn()} />);

    expect(screen.getByLabelText("Tasdiqlash kodi")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "✈️ Telegramni ochish" }))
      .toBeInTheDocument();
  });

  it("lets staff sign in with the exact firm-scoped screen", async () => {
    const user = userEvent.setup();
    const api = {
      ...authApi(),
      loginStaff: vi.fn().mockResolvedValue({
        account_id: 7,
        account_type: "business" as const,
        name: "Ali Valiyev",
        login: "ali01",
        csrf_token: "staff-csrf",
        expires_at: "2026-08-27T08:00:00Z",
        actor_type: "staff" as const,
        staff_id: 11,
        permissions: ["kassa"],
      }),
    };
    const authenticated = vi.fn();
    render(<AuthFlow api={api} onAuthenticated={authenticated} />);

    await user.click(screen.getByRole("button", { name: "👥 Xodimlar uchun kirish" }));
    expect(screen.getByRole("heading", { name: "Xodim kirishi" }))
      .toBeInTheDocument();
    expect(screen.getByText("Do'kon rahbari bergan login va parol bilan kiring."))
      .toBeInTheDocument();
    expect(screen.getByPlaceholderText("masalan: biz123456"))
      .toBeInTheDocument();
    expect(screen.getByPlaceholderText("masalan: vali01"))
      .toBeInTheDocument();
    await user.type(screen.getByLabelText("Firma logini"), "b_turon");
    await user.type(screen.getByLabelText("Xodim logini"), "ali01");
    await user.type(screen.getByLabelText("Xodim paroli"), "safe-pass-42");
    await user.click(screen.getByRole("button", { name: "Kirish" }));

    expect(api.loginStaff).toHaveBeenCalledWith({
      firm_login: "b_turon",
      login: "ali01",
      password: "safe-pass-42",
    });
    expect(authenticated).toHaveBeenCalledWith(expect.objectContaining({
      actor_type: "staff",
      staff_id: 11,
      permissions: ["kassa"],
    }));
  });

  it("shows the exact generated credentials screen once", async () => {
    const user = userEvent.setup();
    const api = authApi();
    const onAuthenticated = vi.fn();
    render(
      <TelegramCodeForm
        api={api}
        purpose="register"
        accountType="user"
        requestId={12}
        deepLink="https://t.me/koprik_bot?start=token"
        codeSent={false}
        resendAfter={0}
        onAuthenticated={onAuthenticated}
      />,
    );

    await user.type(screen.getByLabelText("Tasdiqlash kodi"), "123456");
    await user.click(screen.getByRole("button", { name: "Tasdiqlash va kirish" }));

    expect(await screen.findByRole("heading", { name: "Ro'yxatdan o'tdingiz! ✅" }))
      .toBeInTheDocument();
    expect(screen.getByText("🔑 Login")).toBeInTheDocument();
    expect(screen.getByText("u_test")).toBeInTheDocument();
    expect(screen.getByText("🔐 Parol")).toBeInTheDocument();
    expect(screen.getByText("generated-pass")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kabinetga kirish" }));
    expect(onAuthenticated).toHaveBeenCalledTimes(1);
  });
});

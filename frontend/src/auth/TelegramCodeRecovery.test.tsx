import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TelegramCodeForm } from "./TelegramCodeForm";

function setup(purpose: "register" | "login" = "register") {
  const result = {
    account_id: 9,
    account_type: "user" as const,
    csrf_token: "test-csrf",
    expires_at: "2027-01-01",
    login: "u_test",
    password: "test-password",
  };
  const api = {
    startRegistration: vi.fn(),
    startLogin: vi.fn(),
    verifyRegistration: vi.fn().mockResolvedValue(result),
    verifyLogin: vi.fn().mockResolvedValue(result),
    resendChallenge: vi.fn(),
    getSession: vi
      .fn()
      .mockRejectedValueOnce(new Error("Tarmoq uzildi"))
      .mockResolvedValue({ ...result, name: "Sinov" }),
  };
  const onAuthenticated = vi.fn();
  render(
    <TelegramCodeForm
      api={api}
      purpose={purpose}
      requestId={12}
      deepLink=""
      codeSent
      resendAfter={0}
      onAuthenticated={onAuthenticated}
    />,
  );
  return { api, onAuthenticated };
}

describe("Tasdiqlangan koddan keyin seansni tiklash", () => {
  it.each(["register", "login"] as const)(
    "does not verify the consumed %s code again after session loading fails",
    async (purpose) => {
      const user = userEvent.setup();
      const { api, onAuthenticated } = setup(purpose);
      await user.type(screen.getByLabelText("Tasdiqlash kodi"), "123456");
      await user.click(screen.getByRole("button", { name: "Tasdiqlash va kirish" }));
      expect(await screen.findByRole("alert")).toHaveTextContent("Tarmoq uzildi");
      await user.click(screen.getByRole("button", { name: "Kirishni davom ettirish" }));
      const verify = purpose === "register" ? api.verifyRegistration : api.verifyLogin;
      expect(verify).toHaveBeenCalledTimes(1);
      expect(api.getSession).toHaveBeenCalledTimes(2);
      if (purpose === "register") {
        expect(await screen.findByText("u_test")).toBeVisible();
        expect(screen.getByText("test-password")).toBeVisible();
        await user.click(screen.getByRole("button", { name: "Kabinetga kirish" }));
      }
      expect(onAuthenticated).toHaveBeenCalledOnce();
    },
  );
  it("allows correction after a genuinely wrong code without loading a session", async () => {
    const user = userEvent.setup();
    const { api } = setup();
    api.verifyRegistration.mockRejectedValueOnce(new Error("Kod noto‘g‘ri"));
    api.getSession
      .mockReset()
      .mockResolvedValue({ account_id: 9, account_type: "user", name: "Sinov" });
    const input = screen.getByLabelText("Tasdiqlash kodi");
    await user.type(input, "000000");
    await user.click(screen.getByRole("button", { name: "Tasdiqlash va kirish" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Kod noto‘g‘ri");
    expect(api.getSession).not.toHaveBeenCalled();
    expect(input).toBeEnabled();
    await user.clear(input);
    await user.type(input, "123456");
    await user.click(screen.getByRole("button", { name: "Tasdiqlash va kirish" }));
    expect(await screen.findByText("u_test")).toBeVisible();
    expect(api.verifyRegistration).toHaveBeenCalledTimes(2);
  });
  it("prevents duplicate submissions while verification is pending", async () => {
    const { api } = setup();
    api.verifyRegistration.mockReturnValue(new Promise(() => {}));
    fireEvent.change(screen.getByLabelText("Tasdiqlash kodi"), {
      target: { value: "123456" },
    });
    const form = screen
      .getByRole("button", { name: "Tasdiqlash va kirish" })
      .closest("form")!;
    fireEvent.submit(form);
    fireEvent.submit(form);
    expect(api.verifyRegistration).toHaveBeenCalledTimes(1);
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LoginForm } from "./LoginForm";


describe("shared-login cabinet selection", () => {
  it("sends the selected business cabinet type", async () => {
    const user = userEvent.setup();
    const startLogin = vi.fn().mockResolvedValue({
      request_id: 18,
      deep_link: "https://t.me/koprik_bot?start=shared",
      code_sent: false,
      expires_in: 600,
      resend_after: 60,
    });
    const api = { startLogin } as never;

    render(
      <LoginForm api={api} onStarted={vi.fn()} onBack={vi.fn()} />,
    );

    await user.selectOptions(
      screen.getByLabelText("Kabinet turi"),
      "business",
    );
    await user.type(screen.getByLabelText("Login"), "shared_owner");
    await user.type(screen.getByLabelText("Parol"), "secret-42");
    await user.click(screen.getByRole("button", { name: "Davom etish" }));

    expect(startLogin).toHaveBeenCalledWith({
      login: "shared_owner",
      password: "secret-42",
      cabinet_type: "business",
    });
  });
});

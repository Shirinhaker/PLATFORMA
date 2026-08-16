import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BusinessOpening } from "./BusinessOpening";

describe("BusinessOpening", () => {
  it("keeps the exact v1656 form and reveals new credentials once", async () => {
    const user = userEvent.setup();
    const openBusiness = vi.fn().mockResolvedValue({
      ok: true,
      business_account_id: 17,
      biz_login: "b_turon",
      biz_password: "maxfiy-parol",
    });
    const onSwitch = vi.fn();
    render(
      <BusinessOpening api={{ openBusiness }} onBack={vi.fn()} onSwitch={onSwitch} />,
    );

    await user.click(screen.getByRole("button", { name: "Biznes ochish" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Biznes nomini kiriting.");

    await user.type(screen.getByLabelText("Biznes nomi *"), "Turon do‘koni");
    await user.selectOptions(screen.getByLabelText("Yo'nalish"), "Savdo");
    await user.type(screen.getByLabelText("Faoliyat turi"), "Oziq-ovqat do'koni");
    await user.type(screen.getByLabelText("Telefon"), "+998 90 111 22 33");
    await user.type(screen.getByLabelText("Manzil"), "Qumqo‘rg‘on");
    await user.click(screen.getByRole("button", { name: "Biznes ochish" }));

    await waitFor(() =>
      expect(openBusiness).toHaveBeenCalledWith({
        name: "Turon do‘koni",
        direction: "Savdo",
        activity_type: "Oziq-ovqat do'koni",
        phone: "+998 90 111 22 33",
        address: "Qumqo‘rg‘on",
      }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Biznes ochildi! ✅",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("b_turon")).toBeInTheDocument();
    expect(screen.getByText("maxfiy-parol")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: "Biznes kabinetga o'tish",
      }),
    );
    expect(onSwitch).toHaveBeenCalledOnce();
  });
});

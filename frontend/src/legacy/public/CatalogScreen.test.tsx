import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CatalogScreen } from "./CatalogScreen";


describe("CatalogScreen", () => {
  it("loads safe public results and applies the selected account type", async () => {
    const user = userEvent.setup();
    const searchPublic = vi.fn().mockResolvedValue({
      items: [{
        kind: "business",
        public_id: "b_safe",
        name: "Turon Savdo",
        public_username: "turon",
        description: "Mahalliy telefon va aksessuarlar",
        direction: "Savdo",
        activity_type: "Telefonlar",
        region: "",
        district: "",
        mahalla: "",
        image_url: "",
      }],
      page: 1,
      page_size: 20,
      total: 1,
      pages: 1,
    });

    render(
      <CatalogScreen
        initialQuery="telefon"
        location={{
          region: "Surxondaryo",
          district: "Qumqo‘rg‘on",
          neighborhood: "",
        }}
        searchPublic={searchPublic}
        onOpenCategory={vi.fn()}
      />,
    );

    expect(await screen.findByText("Turon Savdo")).toBeInTheDocument();
    expect(searchPublic).toHaveBeenLastCalledWith(expect.objectContaining({
      q: "telefon",
      result_type: "all",
      district: "Qumqo‘rg‘on",
      page: 1,
      page_size: 20,
    }));

    await user.click(screen.getByRole("button", { name: "Biznes" }));

    await waitFor(() => {
      expect(searchPublic).toHaveBeenLastCalledWith(expect.objectContaining({
        result_type: "business",
      }));
    });
    expect(screen.queryByText("Telefon")).not.toBeInTheDocument();
  });

  it("keeps the static direction catalog usable without the discovery API", () => {
    render(
      <CatalogScreen
        initialQuery=""
        onOpenCategory={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /^Savdo —/ }))
      .toBeInTheDocument();
    expect(screen.getByText("Profil natijalarini yuklab bo‘lmadi"))
      .toBeInTheDocument();
  });

  it("enables product search and loads public catalog cards", async () => {
    const user = userEvent.setup();
    const searchPublic = vi.fn().mockResolvedValue({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
      pages: 0,
    });
    const getCatalogItems = vi.fn().mockResolvedValue({
      items: [{
        kind: "product",
        public_id: "p_public",
        name: "Mebel",
        price_text: "Kelishiladi",
        note: "",
        owner_state: "unlinked",
        owner_public_id: "",
        owner_name: "Turon Savdo",
        owner_label: "Egasi hali akkauntini bog‘lamagan",
        direction: "",
        activity_type: "",
        region: "",
        district: "Qumqo‘rg‘on",
        mahalla: "",
        image_url: "",
        can_order: false,
        can_chat: false,
      }],
      page: 1,
      page_size: 20,
      total: 1,
      pages: 1,
    });

    render(
      <CatalogScreen
        initialQuery=""
        searchPublic={searchPublic}
        getCatalogItems={getCatalogItems}
        onOpenCategory={vi.fn()}
      />,
    );

    expect(await screen.findByText("Mebel")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Mahsulot" }));
    await waitFor(() => {
      expect(searchPublic).toHaveBeenLastCalledWith(
        expect.objectContaining({ result_type: "product" }),
      );
    });
    expect(screen.getByRole("button", { name: "Mahsulot" }))
      .not.toBeDisabled();
  });
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PublicCatalogItem } from "../../api/types";
import { CatalogItemCard } from "./CatalogItemCard";


const unlinkedItem: PublicCatalogItem = {
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
};


describe("CatalogItemCard", () => {
  it("shows the unlinked-owner warning and disables actions", () => {
    render(<CatalogItemCard item={unlinkedItem} />);

    expect(
      screen.getByText("Egasi hali akkauntini bog‘lamagan"),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Buyurtma berish" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Chat" })).toBeDisabled();
    expect(screen.getByRole("img", { name: "Mebel" }))
      .toHaveAttribute("src", "/assets/catalog-placeholder.svg");
  });

  it("opens a linked owner by opaque public id", () => {
    const onOpenOwner = vi.fn();
    render(
      <CatalogItemCard
        item={{
          ...unlinkedItem,
          owner_state: "linked",
          owner_public_id: "b_public",
          owner_label: "Turon Savdo",
          can_order: true,
          can_chat: true,
        }}
        onOpenOwner={onOpenOwner}
      />,
    );

    screen.getByRole("button", { name: "Turon Savdo" }).click();
    expect(onOpenOwner).toHaveBeenCalledWith("b_public");
  });
});


import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HomeDistrictOffersV1656 } from "./HomeDistrictOffersV1656";


const ITEMS = [{
  kind: "service" as const,
  business_id: 41,
  business_public_id: "b_41",
  content_id: 51,
  content_public_id: "s_51",
  title: "Konditsioner ta’miri",
  business_name: "Qumqo‘rg‘on ustalari",
  image: "",
  business_logo: "",
  price: "100 000 so‘m",
  unit: "xizmat",
}, {
  kind: "product" as const,
  business_id: 42,
  business_public_id: "b_42",
  content_id: 52,
  content_public_id: "p_52",
  title: "Konditsioner",
  business_name: "Qumqo‘rg‘on savdo",
  image: "",
  business_logo: "",
  price: "2 000 000 so‘m",
  unit: "dona",
}];


describe("HomeDistrictOffersV1656", () => {
  it("keeps the v1656 hidden mount when the district has no offers", () => {
    render(
      <HomeDistrictOffersV1656
        items={[]}
        needsDistrict={false}
        onOpenLocation={vi.fn()}
        onOpenOffer={vi.fn()}
      />,
    );

    expect(document.querySelector("#districtOffersMount"))
      .toHaveAttribute("hidden");
  });

  it("pauses and resumes the continuous rail on pointer and touch", () => {
    render(
      <HomeDistrictOffersV1656
        items={ITEMS}
        needsDistrict={false}
        onOpenLocation={vi.fn()}
        onOpenOffer={vi.fn()}
      />,
    );
    const mount = document.querySelector("#districtOffersMount")!;

    fireEvent.pointerEnter(mount);
    expect(mount).toHaveClass("is-paused");
    fireEvent.pointerLeave(mount);
    expect(mount).not.toHaveClass("is-paused");

    fireEvent.touchStart(mount);
    expect(mount).toHaveClass("is-paused");
    fireEvent.touchEnd(mount);
    expect(mount).not.toHaveClass("is-paused");
  });

  it("keeps duplicate cards out of the keyboard and accessibility order", () => {
    render(
      <HomeDistrictOffersV1656
        items={ITEMS}
        needsDistrict={false}
        onOpenLocation={vi.fn()}
        onOpenOffer={vi.fn()}
      />,
    );

    const cards = document.querySelectorAll(".district-offer-card");
    expect(cards).toHaveLength(4);
    expect(cards[2]).toHaveAttribute("aria-hidden", "true");
    expect(cards[2]).toHaveAttribute("tabindex", "-1");
  });
});

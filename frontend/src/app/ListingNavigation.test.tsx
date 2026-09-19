import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const listing = {
  public_id: "l_example12345678",
  cat: "uy" as const,
  title: "Sinov uyi",
  price: "100 000",
  descr: "E’lonning to‘liq tavsifi",
  address: "Tuman markazi",
  lat: null,
  lng: null,
  visibility: "all" as const,
  status: "active" as const,
  created_at: "2026-09-01T10:00:00Z",
  media: [],
  owner_kind: "business" as const,
  owner_public_id: "b_example12345678",
  owner_name: "Sinov biznesi",
  is_saved: false,
};
function guestApi() {
  return {
    getSession: vi
      .fn()
      .mockRejectedValue(Object.assign(new Error("unauthorized"), { status: 401 })),
    getPublicFeatures: vi.fn().mockResolvedValue({
      listings: true,
      stories: false,
      chat: false,
      systemization: false,
      taxi: false,
    }),
    getListingCounts: vi.fn().mockResolvedValue({ uy: 1 }),
    getPublicListings: vi.fn().mockResolvedValue([listing]),
    toggleListingSave: vi.fn(),
  };
}
beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, "", "/");
  window.localStorage.setItem(
    "koprik_home_location_v1",
    JSON.stringify({
      region: "Surxondaryo viloyati",
      district: "Qumqo‘rg‘on tumani",
      mahalla: "",
      exact: false,
    }),
  );
});
async function openCategory() {
  await screen.findByRole("heading", {
    name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
  });
  await userEvent.click(await screen.findByRole("button", { name: "E’lonlar" }));
  await userEvent.click(screen.getByRole("button", { name: /Uy-joy/ }));
  return screen.findByRole("button", { name: /Sinov uyi/ });
}
describe("E’lon sahifasi navigatsiyasi", () => {
  it("replaces the list, opens at the top, and restores category, sort, scroll and focus on header Back", async () => {
    const user = userEvent.setup();
    const api = guestApi();
    const { container } = render(<App api={api} />);
    const card = await openCategory();
    await user.click(screen.getByRole("button", { name: "Arzon" }));
    const scroller = container.querySelector(".app-shell__content")!;
    scroller.scrollTop = 420;
    await user.click(card);
    expect(screen.getByRole("heading", { name: listing.title })).toBeInTheDocument();
    expect(screen.getByText(listing.descr)).toBeInTheDocument();
    expect(container.querySelector(".public-listing-card-grid")).toBeNull();
    expect(screen.queryByRole("button", { name: /Uy-joy/ })).not.toBeInTheDocument();
    expect(container.querySelector(".tb-sub")).toHaveTextContent(listing.title);
    expect(scroller.scrollTop).toBe(0);
    expect(screen.getByRole("main", { name: listing.title })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Orqaga" }));
    expect(screen.getByRole("heading", { name: "E’lonlar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Uy-joy/ })).toHaveClass("on");
    expect(screen.getByRole("button", { name: "Arzon" })).toHaveClass("on");
    expect(screen.queryByText(listing.descr)).not.toBeInTheDocument();
    expect(scroller.scrollTop).toBe(420);
    expect(screen.getByRole("button", { name: /Sinov uyi/ })).toHaveFocus();
    expect(api.getPublicListings).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Orqaga" }));
    expect(
      screen.getByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      }),
    ).toBeInTheDocument();
  });
  it("keeps the guest save guard on the separate detail screen", async () => {
    const api = guestApi();
    render(<App api={api} />);
    await userEvent.click(await openCategory());
    await userEvent.click(screen.getByRole("button", { name: "🔖 Saqlash" }));
    expect(api.toggleListingSave).not.toHaveBeenCalled();
    expect(
      screen.getByRole("heading", { name: "Koprik’ga kirish" }),
    ).toBeInTheDocument();
  });
});
